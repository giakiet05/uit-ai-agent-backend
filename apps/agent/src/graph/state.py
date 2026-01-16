"""
AgentState definition for LangGraph workflow.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State schema for UIT AI Assistant agent.

    Fields:
        messages: Chat history with automatic message deduplication/merging
        user_id: User ID for credential lookup (from Redis)
        intent: Intent classification ("search" or "agent")
    """
    # Chat messages with automatic state updates
    # add_messages reducer handles appending new messages
    messages: Annotated[list, add_messages]

    # User context
    user_id: str
    
    # Intent classification for routing
    intent: Optional[str]
