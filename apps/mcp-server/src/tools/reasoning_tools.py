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
            document_selection_model=settings.reasoning.DOCUMENT_SELECTION_MODEL,
            node_selection_model=settings.reasoning.NODE_SELECTION_MODEL,
            answer_generation_model=settings.reasoning.ANSWER_GENERATION_MODEL,
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
        Truy vấn thông tin quy định và chương trình đào tạo của Trường Đại học Công nghệ Thông tin - ĐHQG TP.HCM.

        Dùng tool này khi cần biết về:
        - Quy định, quy chế, chính sách của trường
        - Chương trình đào tạo của các ngành (ví dụ: môn học, lộ trình học, cơ hội nghề nghiệp, v.v.)

        Tool này sử dụng phương pháp reasoning-based RAG, cách hoạt động như sau:
        1. Dựa vào câu hỏi, chọn tài liệu phù hợp.
        2. Từ các tài liệu đã chọn, chọn các phần (node) liên quan.
        3. Dựa vào các phần đã chọn, tạo câu trả lời chi tiết cho câu hỏi.

        Args:
            query: Câu hỏi về quy định, quy chế, chính sách, hoặc chương trình đào tạo. Lưu ý: câu hỏi nên tự nhiên, không dùng cách đặt câu hỏi giống như cho vector search.

        Returns:
            Câu trả lời chi tiết kèm nguồn tham khảo (tên tài liệu và node liên quan)
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
