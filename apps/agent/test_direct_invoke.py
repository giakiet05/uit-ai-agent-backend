"""Test agent directly to see actual tool message content."""
import asyncio
import sys
sys.path.insert(0, '.')

from src.config.llm_provider import create_llm
from src.config.settings import settings
from src.tools.mcp_loader import load_mcp_tools
from src.tools.credential_tool import get_user_credential
from src.graph.agent_graph import create_agent_graph
from src.graph.checkpointer import create_checkpointer

async def test():
    # Create components
    llm = create_llm(provider=settings.llm.PROVIDER, model=settings.llm.MODEL)
    mcp_tools = await load_mcp_tools()  # Fixed: await
    all_tools = mcp_tools + [get_user_credential]
    checkpointer = create_checkpointer(backend="memory")
    graph = create_agent_graph(llm, all_tools, checkpointer, tool_timeout=120)
    
    # Invoke
    result = await graph.ainvoke(
        {"messages": [("user", "KLTN là gì?")], "user_id": "test"},
        {"configurable": {"thread_id": "test"}}
    )
    
    # Check messages
    print(f"\n✅ Total messages: {len(result['messages'])}")
    for i, msg in enumerate(result["messages"]):
        msg_type = type(msg).__name__
        if msg_type == "ToolMessage":
            print(f"\n[{i}] {msg_type}:")
            print(f"Content length: {len(msg.content)}")
            print(f"Content preview: {msg.content[:800]}")
        else:
            print(f"[{i}] {msg_type}")

asyncio.run(test())
