"""Debug source extraction from messages."""
import sys
sys.path.insert(0, '.')

from src.grpc.agent_server import AgentServicer
from langchain_core.messages import ToolMessage
import json

# Mock ToolMessage with search_documents output
mock_tool_msg = ToolMessage(
    content=json.dumps({
        "query": "KLTN là gì?",
        "answer": "KLTN là khóa luận tốt nghiệp...",
        "selected_docs": ["159-qd-dhcntt_05-03-2024", "583-qd-dhcntt_12-6-2023"],
        "selected_nodes": {
            "159-qd-dhcntt_05-03-2024": ["0001", "0002"],
            "583-qd-dhcntt_12-6-2023": ["0004", "0005", "0006"]
        }
    }),
    tool_call_id="test"
)

servicer = AgentServicer(None)
sources = servicer._extract_sources_from_messages([mock_tool_msg])

print(f"Extracted {len(sources)} sources:")
for i, source in enumerate(sources, 1):
    print(f"{i}. doc_id={source.doc_id}, nodes={list(source.node_ids)}")
