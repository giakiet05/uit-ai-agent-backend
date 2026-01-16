"""
LangGraph agent workflow definition.
"""
import asyncio

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from functools import partial
from langchain_core.messages import ToolMessage

from .state import AgentState
from .nodes import agent_node, should_continue, classifier_node, direct_search_node
from ..utils.logger import logger


def _create_tool_node_with_logging_and_timeout(tools, timeout=120):
    """
    Create custom tool execution node with timeout and logging.

    Args:
        tools: List of tools
        timeout: Timeout in seconds for tool execution (default: 120s for MCP cold start)
    """


    # Create tool lookup dict
    tools_by_name = {tool.name: tool for tool in tools}

    async def tool_node_with_timeout(state):
        """
        Custom tool execution node with timeout protection.

        Executes tools in parallel with timeout for each tool.
        """
        messages = state["messages"]
        last_message = messages[-1]

        # Extract tool calls from last AI message
        tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else []

        if not tool_calls:
            return {"messages": []}

        logger.info(f"[TOOLS] Executing {len(tool_calls)} tool(s) with {timeout}s timeout each")

        # Execute tools in parallel with timeout
        async def execute_tool_with_timeout(tool_call):
            """Execute single tool with timeout."""
            tool_name = tool_call["name"]
            tool_call_id = tool_call["id"]
            args = tool_call.get("args", {})

            logger.info(f"[{tool_name}] Starting... Args: {args}")

            try:
                # Lookup tool
                if tool_name not in tools_by_name:
                    error_msg = f"Error: Tool '{tool_name}' not found"
                    logger.error(f"    Status: ERROR - {error_msg}")
                    return ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id,
                        status="error"
                    )

                tool = tools_by_name[tool_name]

                # Execute with timeout
                # Try async first (MCP tools), fallback to sync in thread
                if hasattr(tool, 'ainvoke'):
                    result = await asyncio.wait_for(
                        tool.ainvoke(args),
                        timeout=timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(tool.invoke, args),
                        timeout=timeout
                    )

                # Truncate for logging
                result_str = str(result)
                preview = result_str[:500] + "..." if len(result_str) > 500 else result_str

                logger.info(f"    [{tool_name}] Status: SUCCESS | Output: {preview}")

                return ToolMessage(
                    content=result,
                    tool_call_id=tool_call_id,
                )

            except asyncio.TimeoutError:
                error_msg = (
                    f"Tool '{tool_name}' timed out after {timeout}s. "
                    f"The MCP server may be unresponsive or the operation is taking too long."
                )
                logger.error(f"    [{tool_name}] Status: TIMEOUT - {error_msg}")
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                    status="error"
                )

            except Exception as e:
                error_msg = f"Tool '{tool_name}' failed: {str(e)}"
                logger.error(f"    [{tool_name}] Status: ERROR - {error_msg}")
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                    status="error"
                )

        # Execute all tools in parallel
        tool_messages = await asyncio.gather(*[
            execute_tool_with_timeout(tc) for tc in tool_calls
        ])

        return {"messages": tool_messages}

    return tool_node_with_timeout


def create_agent_graph(llm, tools, checkpointer=None, tool_timeout=120):
    """
    Create LangGraph agent with ReAct-style workflow.

    Workflow:
        START -> agent -> [tools | END]
                  ^----------|

    Args:
        llm: Language model instance
        tools: List of tools (MCP tools + native tools)
        checkpointer: State persistence layer (PostgresSaver or RedisSaver)
        tool_timeout: Timeout for tool execution in seconds (default: 30)

    Returns:
        Compiled graph ready for invocation
    """
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Create partial function with LLM
    agent_with_llm = partial(agent_node, llm_with_tools=llm_with_tools)

    # Define graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_with_llm)  # LLM reasoning node
    # ToolNode with logging, error handling, and timeout
    workflow.add_node("tools", _create_tool_node_with_logging_and_timeout(tools, timeout=tool_timeout))

    # Set entry point using START
    workflow.add_edge(START, "agent")

    # Add conditional edges from agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,  # Routing function
        {
            "tools": "tools",  # If LLM calls tools -> go to tools node
            "end": END         # Otherwise -> finish
        }
    )

    # After tools execute -> back to agent for next reasoning step
    workflow.add_edge("tools", "agent")

    # Compile graph with checkpointer for state persistence
    graph = workflow.compile(
        checkpointer=checkpointer,
    )

    return graph


def route_by_intent(state: AgentState) -> Literal["direct_search", "agent"]:
    """
    Router function: route based on intent classification.

    Args:
        state: Current agent state

    Returns:
        "direct_search" if intent is search, "agent" otherwise
    """
    intent = state.get("intent", "agent")
    
    if intent == "search":
        logger.info("[ROUTER] Intent=search → Routing to direct_search")
        return "direct_search"
    else:
        logger.info("[ROUTER] Intent=agent → Routing to agent loop")
        return "agent"


def create_agent_graph_with_classifier(llm, tools, checkpointer=None, tool_timeout=120):
    """
    Create LangGraph agent with classifier-based routing.

    Workflow:
        START -> classifier -> [direct_search | agent]
                                      ↓            ↓
                                     END     [tools | END]
                                               ↓
                                            agent

    Args:
        llm: Language model instance
        tools: List of tools (MCP tools + native tools)
        checkpointer: State persistence layer (PostgresSaver or RedisSaver)
        tool_timeout: Timeout for tool execution in seconds (default: 120)

    Returns:
        Compiled graph ready for invocation
    """
    # Find search_documents tool
    search_tool = None
    for tool in tools:
        if tool.name == "search_documents":
            search_tool = tool
            break
    
    if not search_tool:
        logger.warning("[GRAPH] search_documents tool not found, direct_search will fail")
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Create partial functions
    agent_with_llm = partial(agent_node, llm_with_tools=llm_with_tools)
    direct_search_with_tool = partial(direct_search_node, search_tool=search_tool)

    # Define graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classifier", classifier_node)  # Intent classification
    workflow.add_node("direct_search", direct_search_with_tool)  # Direct search bypass
    workflow.add_node("agent", agent_with_llm)  # LLM reasoning node
    workflow.add_node("tools", _create_tool_node_with_logging_and_timeout(tools, timeout=tool_timeout))

    # Set entry point: START -> classifier
    workflow.add_edge(START, "classifier")

    # Route from classifier based on intent
    workflow.add_conditional_edges(
        "classifier",
        route_by_intent,
        {
            "direct_search": "direct_search",
            "agent": "agent"
        }
    )

    # Direct search goes straight to END
    workflow.add_edge("direct_search", END)

    # Agent loop (original flow)
    workflow.add_conditional_edges(
        "agent",
        should_continue,  # Routing function
        {
            "tools": "tools",  # If LLM calls tools -> go to tools node
            "end": END         # Otherwise -> finish
        }
    )

    # After tools execute -> back to agent for next reasoning step
    workflow.add_edge("tools", "agent")

    # Compile graph with checkpointer for state persistence
    graph = workflow.compile(
        checkpointer=checkpointer,
    )

    return graph
