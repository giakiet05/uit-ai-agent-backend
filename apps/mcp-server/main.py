"""
MCP Server for UIT AI Assistant.

Exposes tools for:
- Document retrieval from UIT knowledge base
- DAA portal scraping (grades, schedule)

MCP Protocol: https://modelcontextprotocol.io/
FastMCP: https://github.com/jlowin/fastmcp
"""
from fastmcp import FastMCP
from fastapi import FastAPI

# Import from src package
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.tools.retrieval_tools import register_retrieval_tools
from src.tools.daa_scraping_tools import register_daa_tools
from src.tools.reasoning_tools import register_reasoning_tools

# Initialize FastMCP server
mcp = FastMCP("UIT MCP Server")

# Register all tools
print("[MCP SERVER] Registering tools...")
register_retrieval_tools(mcp)
register_daa_tools(mcp)
register_reasoning_tools(mcp)
print("[MCP SERVER] All tools registered successfully")

# Create MCP ASGI app
mcp_app = mcp.http_app(path='/mcp')

# Create combined FastAPI app with MCP routes
# Note: Not passing lifespan to avoid type mismatch (Starlette vs FastAPI)
# MCP routes are mounted, their lifespan will still work
app = FastAPI(
    title="UIT MCP Server",
    routes=mcp_app.routes,
    lifespan=mcp_app.lifespan
)

# Add custom endpoints (must be after app creation, before uvicorn loads)
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}

print(f"[MCP SERVER] Registered routes: {[route.path for route in app.routes]}")

if __name__ == "__main__":
    import uvicorn
    print("[MCP SERVER] Starting UIT MCP Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

