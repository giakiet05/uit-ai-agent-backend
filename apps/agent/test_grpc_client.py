"""
Simple gRPC client to test agent service.

Usage:
    # Start agent server first (in another terminal):
    cd apps/agent && .venv/bin/python main.py
    
    # Then run this client:
    cd apps/agent && .venv/bin/python test_grpc_client.py
"""

import asyncio
import grpc
from src.grpc.pb import agent_pb2, agent_pb2_grpc


async def test_agent():
    """Test agent gRPC service with a reasoning query."""
    
    # Connect to local agent server
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = agent_pb2_grpc.AgentStub(channel)
        
        # Create test request
        request = agent_pb2.ChatRequest(
            message="Khóa luận tốt nghiệp là gì?",
            user_id="test_user",
            thread_id="test_user:test_session"
        )
        
        print("=" * 80)
        print("📤 SENDING REQUEST:")
        print(f"  Message: {request.message}")
        print(f"  User ID: {request.user_id}")
        print(f"  Thread ID: {request.thread_id}")
        print("=" * 80)
        
        # Call agent
        response = await stub.Chat(request)
        
        print("\n📥 RECEIVED RESPONSE:")
        print("=" * 80)
        print(f"\n💬 Content ({len(response.content)} chars):")
        print("-" * 80)
        print(response.content)
        
        print(f"\n📚 Sources ({len(response.sources)} documents):")
        print("-" * 80)
        if response.sources:
            for i, source in enumerate(response.sources, 1):
                print(f"\n{i}. Document: {source.doc_id}")
                print(f"   Nodes: {list(source.node_ids)}")
        else:
            print("(No sources)")
        
        print(f"\n📊 Metadata:")
        print("-" * 80)
        print(f"  Tokens used: {response.tokens_used}")
        print(f"  Latency: {response.latency_ms}ms")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_agent())
