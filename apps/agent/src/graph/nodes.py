"""
Graph nodes for LangGraph agent workflow.
"""

from typing import Literal
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from .state import AgentState
from ..config.prompts import NEW_PROMPT
from ..config.llm_provider import create_llm
from ..config.settings import settings
from ..query_refinement.refiner import QueryRefiner
from ..utils.logger import logger


# System prompt for UIT AI Assistant (imported from config/prompts.py)
SYSTEM_PROMPT = NEW_PROMPT

# Classifier prompt for intent routing
CLASSIFIER_PROMPT = """Phân loại intent của user query. Chỉ trả về 1 trong 2 giá trị:

- "search": Nếu hỏi về quy định, quy chế, chính sách, chương trình đào tạo, môn học, ngành học, điều kiện, thủ tục, thuật ngữ, khái niệm, hoặc bất kỳ thông tin nào về đào tạo của trường
- "agent": Còn lại (xem điểm, xem lịch, chào hỏi, cảm ơn, hỏi về bot, câu hỏi cần clarify)

User query: {query}

Trả về ĐÚNG 1 từ (search hoặc agent):"""

# Initialize query refiner (singleton)
_query_refiner = None
_classifier_llm = None


def get_query_refiner():
    """Get singleton QueryRefiner instance."""
    global _query_refiner
    if _query_refiner is None:
        _query_refiner = QueryRefiner()
    return _query_refiner


def get_classifier_llm():
    """Get singleton classifier LLM instance."""
    global _classifier_llm
    if _classifier_llm is None:
        _classifier_llm = create_llm(
            provider=settings.llm.PROVIDER,
            model=settings.llm.CLASSIFIER_MODEL
        )
    return _classifier_llm


def agent_node(state: AgentState, llm_with_tools):
    """
    Agent reasoning node - LLM decides whether to use tools or respond.

    Pipeline:
    1. Expand acronyms in user query (QueryRefiner)
    2. Add system prompt if needed
    3. Invoke LLM with tools

    Args:
        state: Current agent state
        llm_with_tools: LLM instance bound with tools

    Returns:
        Updated state with LLM response
    """
    messages = state["messages"]
    user_id = state["user_id"]

    # Limit to last 5 turns (10 messages: 5 user + 5 ai) to reduce token usage
    # Keep all message types (including ToolMessage) to avoid breaking tool loops
    max_messages = 10
    if len(messages) > max_messages:
        # Keep first message if it's SystemMessage
        if isinstance(messages[0], SystemMessage):
            messages = [messages[0]] + messages[-(max_messages):]
        else:
            messages = messages[-(max_messages):]
        logger.info(f"[TRIM] Limited to last {max_messages} messages")

    # Step 1: Expand acronyms in latest user message
    refiner = get_query_refiner()
    if messages and isinstance(messages[-1], HumanMessage):
        user_query = messages[-1].content
        refined_query = refiner.refine(user_query, partial=True)

        if refined_query and refined_query != user_query:
            # Replace last message with refined version
            messages = messages[:-1] + [HumanMessage(content=refined_query)]
            logger.info(f"[QUERY REFINER] Expanded: {user_query} -> {refined_query}")

    # Step 2: ALWAYS inject fresh system prompt (ensures instructions are followed every turn)
    # Remove old system prompt if exists
    if messages and isinstance(messages[0], SystemMessage):
        messages = messages[1:]
    
    # Inject fresh system prompt with user_id
    system_prompt_with_user_id = (
        SYSTEM_PROMPT
        + f"\n\n## THÔNG TIN NGƯỜI DÙNG HIỆN TẠI\nUser ID: {user_id}\n\nKhi gọi tool `get_user_credential`, LUÔN LUÔN sử dụng user_id này."
    )
    messages = [SystemMessage(content=system_prompt_with_user_id)] + messages

    # Step 3: Invoke LLM with tools
    response = llm_with_tools.invoke(messages)

    # Log final answer if no tool calls
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        # Find original user query (latest HumanMessage)
        original_query = "Unknown"
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                original_query = msg.content
                break
        logger.info(
            f"[FINAL ANSWER] Query: {original_query} | Answer: {response.content}"
        )

    return {"messages": [response]}


async def classifier_node(state: AgentState):
    """
    Classifier node - Phân loại intent để route đến direct_search hoặc agent.

    Args:
        state: Current agent state

    Returns:
        Updated state with intent classification
    """
    messages = state["messages"]
    
    # Get latest user message
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    if not user_query:
        # Fallback to agent if no user message
        state["intent"] = "agent"
        return state
    
    # Call classifier LLM
    classifier_llm = get_classifier_llm()
    prompt = CLASSIFIER_PROMPT.format(query=user_query)
    
    response = classifier_llm.invoke(prompt)
    intent = response.content.strip().lower()
    
    # Validate intent
    if intent not in ["search", "agent"]:
        logger.warning(f"[CLASSIFIER] Invalid intent '{intent}', defaulting to 'agent'")
        intent = "agent"
    
    state["intent"] = intent
    logger.info(f"[CLASSIFIER] Query: {user_query[:80]}... → Intent: {intent}")
    
    return state


async def direct_search_node(state: AgentState, search_tool):
    """
    Direct search node - Gọi search_documents trực tiếp, bypass agent loop.

    Args:
        state: Current agent state
        search_tool: search_documents tool instance

    Returns:
        Updated state with search result as final answer
    """
    messages = state["messages"]
    
    # Get latest user message
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    logger.info(f"[DIRECT SEARCH] Calling search_documents with query: {user_query[:80]}...")
    
    try:
        # Call search_documents tool directly
        result = await search_tool.ainvoke({"query": user_query})
        
        logger.info(f"[DIRECT SEARCH] Result received ({len(result)} chars)")
        
        # Create AI message with search result
        ai_message = AIMessage(content=result)
        
        return {"messages": [ai_message]}
    
    except Exception as e:
        logger.error(f"[DIRECT SEARCH] Error: {e}")
        error_message = AIMessage(content=f"Xin lỗi, đã xảy ra lỗi khi tìm kiếm: {str(e)}")
        return {"messages": [error_message]}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Routing function: decide whether to call tools or finish.

    Args:
        state: Current agent state

    Returns:
        "tools" if LLM wants to call tools, "end" otherwise
    """
    last_message = state["messages"][-1]

    # If LLM called tools -> route to tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("\n" + "=" * 70)
        logger.info("[AGENT] Tool calls requested:")
        for i, tool_call in enumerate(last_message.tool_calls, 1):
            logger.info(f"  [{i}] Tool: {tool_call['name']}")
            logger.info(f"      Args: {tool_call['args']}")
            logger.info(f"      Call ID: {tool_call['id']}")
        logger.info("=" * 70 + "\n")
        return "tools"

    # Otherwise, finish
    logger.info("\n" + "=" * 70)
    logger.info("[AGENT] No tool calls - finishing")
    logger.info("=" * 70 + "\n")
    return "end"
