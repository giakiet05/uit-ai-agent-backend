"""
MCP tools for reasoning-based document retrieval.

Uses ToC structures instead of vector embeddings for retrieval.
"""

import json
from typing import Optional

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..reasoning_retriever import ReasoningSearch


class ReasoningRetrievalResult(BaseModel):
    """Result from reasoning-based retrieval."""

    query: str = Field(description="Original query")
    answer: str = Field(description="Generated answer from RAG pipeline")
    selected_docs: list[str] = Field(description="Document IDs selected by LLM")
    selected_nodes: dict[str, list[str]] = Field(
        description="Node IDs selected per document"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")


_reasoning_search: Optional[ReasoningSearch] = None


def _get_reasoning_search() -> ReasoningSearch:
    """Get or initialize reasoning search singleton."""
    global _reasoning_search

    if _reasoning_search is None:
        _reasoning_search = ReasoningSearch(
            model=settings.reasoning.MODEL,
            max_docs=settings.reasoning.MAX_DOCS,
            max_nodes=settings.reasoning.MAX_NODES,
        )

    return _reasoning_search


def register_reasoning_tools(mcp: FastMCP):
    """
    Register reasoning-based retrieval tools with MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    async def search_documents(query: str) -> ToolResult:
        """
        Tìm kiếm và trả lời câu hỏi về các văn bản quy định của UIT.

        Tool này thực hiện full RAG pipeline:
        1. Chọn tài liệu liên quan từ index
        2. Chọn các mục liên quan từ cấu trúc tài liệu
        3. Trích xuất nội dung từ các mục đã chọn
        4. Sinh câu trả lời dựa trên nội dung

        Sử dụng cho các câu hỏi về:
        - Quy chế, quy định đào tạo
        - Chương trình học, môn học
        - Các văn bản hành chính của UIT

        Args:
            query: Câu hỏi bằng tiếng Việt

        Returns:
            Câu trả lời kèm nguồn tham khảo
        """
        try:
            search = _get_reasoning_search()
            result = search.search_and_answer(query)

            output = ReasoningRetrievalResult(
                query=query,
                answer=result.get("answer", ""),
                selected_docs=result.get("selected_docs", []),
                selected_nodes=result.get("selected_nodes", {}),
                error=result.get("error"),
            )

            return ToolResult(content=output.model_dump_json(indent=2))

        except FileNotFoundError as e:
            error_result = ReasoningRetrievalResult(
                query=query,
                answer="",
                selected_docs=[],
                selected_nodes={},
                error=f"Không tìm thấy dữ liệu ToC: {str(e)}",
            )
            return ToolResult(content=error_result.model_dump_json(indent=2))

        except Exception as e:
            error_result = ReasoningRetrievalResult(
                query=query,
                answer="",
                selected_docs=[],
                selected_nodes={},
                error=f"Lỗi tìm kiếm: {str(e)}",
            )
            return ToolResult(content=error_result.model_dump_json(indent=2))
