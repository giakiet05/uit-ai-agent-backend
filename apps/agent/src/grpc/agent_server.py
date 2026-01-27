"""
gRPC server for LangGraph agent.

This server:
1. Loads LangGraph agent with checkpointer for state persistence
2. Receives requests with user_id + thread_id (no history needed)
3. Uses thread_id to load conversation state from checkpointer
4. Invokes agent graph with state management
5. Returns response to API server (which stores in MongoDB for UI)
"""

import asyncio
from concurrent import futures
import grpc
import json

from langchain_core.messages import ToolMessage

from src.config.llm_provider import create_llm
from src.config.settings import settings
from src.tools.mcp_loader import load_mcp_tools
from src.tools.credential_tool import get_user_credential
from src.graph.agent_graph import create_agent_graph_with_classifier, create_agent_graph
from src.graph.checkpointer import create_checkpointer
from src.grpc.pb import agent_pb2, agent_pb2_grpc
from src.utils.logger import logger


class AgentServicer(agent_pb2_grpc.AgentServicer):
    """gRPC servicer for agent with LangGraph state management."""

    def __init__(self, graph):
        """
        Initialize agent servicer.

        Args:
            graph: Compiled LangGraph agent with checkpointer
        """
        self.graph = graph
        logger.info("[AGENT SERVER] AgentServicer initialized")

    def Chat(self, request, context):
        """
        Handle chat request (stateful with LangGraph checkpointer).

        Args:
            request: ChatRequest with message, user_id, thread_id
            context: gRPC context

        Returns:
            ChatResponse with agent's reply
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"[AGENT SERVER] Received request:")
        logger.info(f"  - User ID: {request.user_id}")
        logger.info(f"  - Thread ID: {request.thread_id}")
        logger.info(f"  - Message: {request.message[:100]}...")
        logger.info(f"{'='*70}\n")

        try:
            # Run async graph invocation in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self._ainvoke_agent(request.message, request.user_id, request.thread_id)
            )
            loop.close()

            return response

        except Exception as e:
            logger.exception(f"[AGENT SERVER] Error during chat invocation")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Agent error: {str(e)}")
            return agent_pb2.ChatResponse(content=f"Xin lỗi, đã xảy ra lỗi: {str(e)}")

    async def _ainvoke_agent(self, message: str, user_id: str, thread_id: str):
        """
        Invoke agent graph asynchronously.

        Args:
            message: User's message
            user_id: User ID (for credential lookup)
            thread_id: Thread ID (for state persistence)

        Returns:
            ChatResponse protobuf message
        """
        # Build config with thread_id for checkpointer
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50  # Increased from default 25 to handle complex tool chains
        }

        # Invoke graph (will automatically load state from checkpointer if exists)
        result = await self.graph.ainvoke(
            {
                "messages": [("user", message)],
                "user_id": user_id
            },
            config=config
        )

        # Extract agent's response (last message)
        agent_message = result["messages"][-1]
        content = agent_message.content

        # Extract sources from tool outputs
        logger.info(f"[EXTRACT] Total messages: {len(result['messages'])}")
        for i, msg in enumerate(result["messages"]):
            msg_type = type(msg).__name__
            if msg_type == "ToolMessage":
                logger.info(f"[EXTRACT]   [{i}] {msg_type} - content preview: {msg.content[:200]}")
            else:
                logger.info(f"[EXTRACT]   [{i}] {msg_type}")
        sources = self._extract_sources_from_messages(result["messages"])

        logger.info(f"\n[AGENT SERVER] Response sent:")
        logger.info(f"  - Content length: {len(content)} chars")
        logger.info(f"  - Preview: {content[:200]}...")
        logger.info(f"  - Sources: {len(sources)} documents")

        # Build ChatResponse
        return agent_pb2.ChatResponse(
            content=content,
            sources=sources,
            tokens_used=0,  # TODO: Add token counting
            latency_ms=0
        )

    def _extract_sources_from_messages(self, messages):
        """
        Extract reasoning sources from tool outputs.
        
        Searches for ToolMessage containing search_documents output,
        then extracts doc_id + node_ids for each source.
        
        Args:
            messages: List of LangChain messages from agent execution
            
        Returns:
            List of ReasoningSource protobuf messages
        """
        sources = []
        
        # Search from end (most recent tool calls first)
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                try:
                    logger.info(f"[EXTRACT] Found ToolMessage, content type: {type(msg.content)}")
                    
                    # Handle both string and list formats
                    content_str = msg.content
                    if isinstance(msg.content, list) and len(msg.content) > 0:
                        # MCP tools return [{'type': 'text', 'text': '...'}]
                        if isinstance(msg.content[0], dict) and 'text' in msg.content[0]:
                            content_str = msg.content[0]['text']
                            logger.info(f"[EXTRACT] Extracted text from content array")
                    
                    tool_output = json.loads(content_str)
                    logger.info(f"[EXTRACT] Parsed JSON keys: {list(tool_output.keys())}")
                    
                    # Check if it's search_documents output
                    if "selected_docs" in tool_output and "selected_nodes" in tool_output:
                        selected_docs = tool_output.get("selected_docs", [])
                        selected_nodes = tool_output.get("selected_nodes", {})
                        
                        logger.info(f"[EXTRACT] Found search_documents output: {len(selected_docs)} docs")
                        
                        for doc_id in selected_docs:
                            node_ids = selected_nodes.get(doc_id, [])
                            logger.info(f"[EXTRACT] Adding source: {doc_id} with {len(node_ids)} nodes")
                            sources.append(
                                agent_pb2.ReasoningSource(
                                    doc_id=doc_id,
                                    node_ids=node_ids
                                )
                            )
                        
                        # Only extract from latest search_documents call
                        break
                    else:
                        logger.info(f"[EXTRACT] Not search_documents output (missing keys)")
                        
                except (json.JSONDecodeError, AttributeError, TypeError) as e:
                    # Skip malformed tool outputs
                    logger.info(f"[EXTRACT] Failed to parse ToolMessage: {e}")
                    continue
        
        if not sources:
            logger.warning("[EXTRACT] No sources found in messages!")
        
        return sources


async def _initialize_agent():
    """
    Initialize LangGraph agent with all components.

    Returns:
        Compiled graph ready for invocation
    """
    logger.info("\n" + "="*70)
    logger.info("Initializing LangGraph Agent Server")
    logger.info("="*70 + "\n")

    # Step 1: Create LLM
    logger.info("[1/5] Creating LLM...")
    llm = create_llm(
        provider=settings.llm.PROVIDER,
        model=settings.llm.MODEL
    )
    logger.info(f"✅ LLM created: {settings.llm.PROVIDER}/{settings.llm.MODEL}\n")

    # Step 2: Load MCP tools
    logger.info("[2/5] Loading MCP tools...")
    try:
        mcp_tools = await load_mcp_tools()
        logger.info(f"✅ MCP tools loaded: {len(mcp_tools)} tools\n")
    except Exception as e:
        logger.warning(f"⚠️  MCP tools failed to load: {e}")
        logger.warning("⚠️  Continuing with native tools only...\n")
        mcp_tools = []

    # Step 3: Add native tools
    logger.info("[3/5] Adding native tools...")
    native_tools = [get_user_credential]
    all_tools = mcp_tools + native_tools
    logger.info(f"✅ Total tools: {len(all_tools)}")
    logger.info(f"   - MCP tools: {len(mcp_tools)}")
    logger.info(f"   - Native tools: {len(native_tools)}\n")

    # Step 4: Create checkpointer
    logger.info("[4/5] Creating checkpointer...")
    try:
        checkpointer = create_checkpointer(backend=settings.checkpointer.BACKEND)
        logger.info("✅ Checkpointer created\n")
    except Exception as e:
        logger.warning(f"⚠️  Checkpointer failed: {e}")
        logger.warning("⚠️  Running without persistence...\n")
        checkpointer = None

    # Step 5: Create agent graph with classifier
    logger.info("[5/5] Creating agent graph with classifier...")
    graph = create_agent_graph(
        llm=llm,
        tools=all_tools,
        checkpointer=checkpointer,
        tool_timeout=120  # 2 minutes for MCP tools (handles cold start)
    )
    logger.info("✅ Agent graph created\n")

    logger.info("="*70)
    logger.info("✅ Agent server initialization complete!")
    logger.info("="*70 + "\n")

    return graph


def serve():
    """Start gRPC server."""
    # Initialize agent (runs async initialization)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    graph = loop.run_until_complete(_initialize_agent())
    loop.close()

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_AgentServicer_to_server(
        AgentServicer(graph),
        server
    )

    # Bind to port
    port = settings.grpc.PORT
    server.add_insecure_port(f"[::]:{port}")

    logger.info(f"[AGENT SERVER] Starting gRPC server on port {port}...")
    server.start()
    logger.info(f"[AGENT SERVER] ✅ Server running on port {port}\n")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\n[AGENT SERVER] Shutting down...")
        server.stop(0)


if __name__ == "__main__":
    serve()
