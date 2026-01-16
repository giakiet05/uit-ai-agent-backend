"""
Message trimming utilities for reducing token usage.

Removes tool calls and tool outputs from message history,
keeping only user inputs and final AI answers.
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage


def trim_messages_for_llm(messages, max_turns=10):
    """
    Trim messages for LLM to reduce token usage.
    
    Removes:
    - ToolMessage (tool outputs can be 2K-5K tokens each)
    - AIMessage with tool_calls (intermediate reasoning)
    
    Keeps:
    - SystemMessage (always first)
    - HumanMessage (user inputs)
    - AIMessage without tool_calls (final answers)
    
    Args:
        messages: Full message history from state
        max_turns: Maximum number of conversation turns to keep (default: 10)
    
    Returns:
        Trimmed messages with SystemMessage + last N user/ai pairs
    """
    # Extract system message
    system_msg = None
    start_idx = 0
    if messages and isinstance(messages[0], SystemMessage):
        system_msg = messages[0]
        start_idx = 1
    
    # Filter: Only keep HumanMessage and final AIMessage (no tool_calls)
    conversation = []
    for msg in messages[start_idx:]:
        if isinstance(msg, HumanMessage):
            conversation.append(msg)
        elif isinstance(msg, AIMessage):
            # Only keep final answer (no tool_calls)
            if not hasattr(msg, "tool_calls") or not msg.tool_calls:
                if msg.content:  # Skip empty AI messages
                    conversation.append(msg)
        # ToolMessage: SKIP completely
    
    # Trim to last N turns (each turn = user + ai)
    max_messages = max_turns * 2
    recent = conversation[-max_messages:]
    
    # Return system message + recent conversation
    return [system_msg] + recent if system_msg else recent
