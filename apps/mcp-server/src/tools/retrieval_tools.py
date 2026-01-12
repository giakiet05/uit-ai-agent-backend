"""
MCP tools for document retrieval from UIT knowledge base.
"""

import asyncio
import chromadb
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings as LlamaSettings

from ..config.settings import settings
from ..retriever.query_engine import QueryEngine
from ..retriever.schemas import RegulationRetrievalResult, CurriculumRetrievalResult
from ..utils.logger import logger


def _init_query_engine() -> QueryEngine:
    """Initialize QueryEngine with all collections."""
    logger.info("[RETRIEVAL TOOLS] Initializing QueryEngine...")

    # Setup embeddings
    if not settings.credentials.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found")

    LlamaSettings.embed_model = OpenAIEmbedding(
        model=settings.retrieval.EMBED_MODEL,
        api_key=settings.credentials.OPENAI_API_KEY,
    )

    # Load ChromaDB collections
    db = chromadb.PersistentClient(path=str(settings.paths.VECTOR_STORE_DIR))

    collections = {}
    for category in settings.retrieval.AVAILABLE_COLLECTIONS:
        logger.info(f"[RETRIEVAL TOOLS] Loading collection: {category}")
        chroma_collection = db.get_or_create_collection(category)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        collections[category] = VectorStoreIndex.from_vector_store(vector_store)

    # Initialize QueryEngine
    query_engine = QueryEngine(
        collections=collections,
        use_reranker=True,
        top_k=3,
        retrieval_top_k=10,  # Reduced from 20 for faster reranking
        rerank_score_threshold=0.25,  # Raised from 0.1 to filter low-quality results
        min_score_threshold=0.2,      # Raised from 0.15 for better initial retrieval quality
        use_modal=True,
        use_hyde=settings.retrieval.USE_HYDE,
        hyde_model=settings.retrieval.HYDE_MODEL,
    )

    logger.info(
        f"[RETRIEVAL TOOLS] QueryEngine initialized with {len(collections)} collections"
    )
    return query_engine


def register_retrieval_tools(mcp: FastMCP):
    """Register retrieval tools to FastMCP instance."""

    # Eager load QueryEngine on registration
    query_engine = _init_query_engine()

    @mcp.tool()
    async def retrieve_regulation(query: str) -> ToolResult:
        """
        Truy xuất văn bản quy định từ knowledge base của UIT.

        DÙNG KHI:
        - Hỏi về QUY ĐỊNH, CHÍNH SÁCH, THỦ TỤC CHUNG của trường
        - KHÔNG đề cập đến một ngành học cụ thể

        KHÔNG DÙNG KHI:
        - Hỏi về danh sách môn học, lộ trình của một ngành
        - Đề cập tên ngành: Khoa học máy tính, Kỹ thuật phần mềm, v.v.

        Ví dụ queries phù hợp:
        - "điều kiện tốt nghiệp là gì?"
        - "quy định chuyển ngành"
        - "cách tính điểm trung bình"
        - "học phí năm 2024"

        Args:
            query: Câu hỏi tìm kiếm (tiếng Việt)

        Returns:
            ToolResult chứa các chunk văn bản liên quan dưới dạng JSON (gồm nội dung và metadata)
        """
        import json
        
        try:
            # Run blocking query_engine call in thread pool to avoid blocking event loop
            result_dict = await asyncio.to_thread(
                query_engine.retrieve_structured, query, collection_type="regulation"
            )

            # Validate with Pydantic
            result_model = RegulationRetrievalResult(**result_dict)

            # Serialize to JSON for content (LangChain compatibility)
            json_content = json.dumps(
                result_model.model_dump(), ensure_ascii=False, indent=2
            )

            # Return ToolResult with both text and structured content
            return ToolResult(
                content=json_content,  # JSON string for LangChain
                structured_content=result_model.model_dump(),  # Object for MCP Inspector
            )
            
        except Exception as e:
            # Log error and return error response to prevent tool call hanging
            print(f"[ERROR] retrieve_regulation failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            # Return error as valid tool result
            error_result = {
                'query': query,
                'total_retrieved': 0,
                'documents': [],
                'error': f"{type(e).__name__}: {str(e)}"
            }
            
            error_json = json.dumps(error_result, ensure_ascii=False, indent=2)
            
            return ToolResult(
                content=error_json,
                is_error=True
            )

    @mcp.tool()
    async def retrieve_curriculum(query: str) -> ToolResult:
        """
        Truy xuất thông tin chương trình đào tạo từ knowledge base của UIT.

        DÙNG KHI:
        - Hỏi về thông tin của một ngành cụ thể (Khoa học máy tính, Kỹ thuật phần mềm,...),
          bao gồm: giới thiệu ngành, lộ trình đào tạo, danh sách môn học, cơ hội nghề nghiệp
        - Điều kiện tốt nghiệp RIÊNG của ngành (số tín chỉ chuyên ngành, môn bắt buộc riêng)

        KHÔNG DÙNG KHI:
        - Hỏi về quy định, chính sách chung (áp dụng cho mọi ngành)
        - Điều kiện tốt nghiệp CHUNG (không đề cập ngành cụ thể)

        Ví dụ queries phù hợp:
        - "ngành Khoa học máy tính năm 2025 học những môn gì?"
        - "lộ trình đào tạo ngành Kỹ thuật phần mềm năm 2023"
        - "học ngành Kỹ thuật phần mềm năm 2025 ra làm gì?"
        - "điều kiện tốt nghiệp ngành Khoa học máy tính năm 2022"

        LƯU Ý QUAN TRỌNG:
        - Query PHẢI bao gồm TÊN NGÀNH ĐẦY ĐỦ (không viết tắt)
          Ví dụ: "Khoa học máy tính" thay vì "KHMT"
        - Query PHẢI bao gồm NĂM để tìm đúng phiên bản chương trình đào tạo
          Ví dụ: "ngành KHMT năm 2025" thay vì chỉ "ngành KHMT"

        Args:
            query: Câu hỏi tìm kiếm (tiếng Việt, bao gồm tên ngành đầy đủ + năm)

        Returns:
           ToolResult chứa các chunk văn bản liên quan dưới dạng JSON (gồm nội dung và metadata)
        """
        import json
        
        try:
            # Run blocking query_engine call in thread pool to avoid blocking event loop
            result_dict = await asyncio.to_thread(
                query_engine.retrieve_structured, query, collection_type="curriculum"
            )

            # Validate with Pydantic
            result_model = CurriculumRetrievalResult(**result_dict)

            # Serialize to JSON for content (LangChain compatibility)
            json_content = json.dumps(
                result_model.model_dump(), ensure_ascii=False, indent=2
            )

            # Return ToolResult with both text and structured content
            return ToolResult(
                content=json_content,  # JSON string for LangChain
                structured_content=result_model.model_dump(),  # Object for MCP Inspector
            )
            
        except Exception as e:
            # Log error and return error response to prevent tool call hanging
            print(f"[ERROR] retrieve_curriculum failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            # Return error as valid tool result
            error_result = {
                'query': query,
                'total_retrieved': 0,
                'documents': [],
                'error': f"{type(e).__name__}: {str(e)}"
            }
            
            error_json = json.dumps(error_result, ensure_ascii=False, indent=2)
            
            return ToolResult(
                content=error_json,
                is_error=True
            )
