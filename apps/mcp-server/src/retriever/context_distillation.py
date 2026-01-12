"""
Context Distillation Module for MCP Server.

This module extracts only the relevant information from retrieved chunks
to reduce noise and improve LLM's focus on answering the user's question.

Why Context Distillation:
1. Retrieved chunks often contain MORE info than needed
2. Multiple chunks can confuse LLM (information overload)
3. Reduce tokens sent to expensive LLM = faster + cheaper
4. Better accuracy by removing irrelevant noise

How it works:
1. Retrieve N chunks as usual (vector search + rerank)
2. Use fast/cheap LLM to extract ONLY sentences relevant to query
3. Return distilled context to agent

Example:
  Query: "Điểm TOEIC tốt nghiệp là bao nhiêu?"
  
  Retrieved chunk (500 tokens):
    "Điều 15. Yêu cầu tốt nghiệp
    1. Hoàn thành 140 tín chỉ...
    2. GPA >= 2.0...
    3. TOEIC: CTC cần 450, CTTN cần 550...
    4. Không vi phạm nội quy..."
  
  Distilled (50 tokens):
    "TOEIC: Chương trình chuẩn (CTC) cần 450 điểm, 
     Chương trình tài năng (CTTN) cần 550 điểm."
"""

from typing import List
from llama_index.core.schema import NodeWithScore
from llama_index.llms.openai import OpenAI
from ..config.settings import Settings

settings = Settings()


class ContextDistiller:
    """
    Distills retrieved chunks to extract only relevant information.
    """
    
    def __init__(self, model: str = None):
        """
        Initialize context distiller.
        
        Args:
            model: LLM model to use for distillation (default from settings)
        """
        self.model = model or settings.retrieval.DISTILLATION_MODEL
        self.llm = OpenAI(
            model=self.model,
            api_key=settings.credentials.OPENAI_API_KEY,
            timeout=120.0  # 2 minutes for distillation
        )
        print(f"[CONTEXT-DISTILL] Initialized with model: {self.model}")
    
    def distill(self, query: str, nodes: List[NodeWithScore]) -> str:
        """
        Distill retrieved chunks to extract only relevant information.
        
        Args:
            query: User's question
            nodes: Retrieved and reranked chunks
            
        Returns:
            Distilled context as a single string
            
        Note:
            This method ALWAYS returns a valid string. If distillation fails,
            it falls back to raw chunks to ensure tool call gets response.
        """
        # Skip distillation if too few chunks
        min_chunks = settings.retrieval.DISTILLATION_MIN_CHUNKS
        if len(nodes) < min_chunks:
            print(f"[CONTEXT-DISTILL] Skipping - only {len(nodes)} chunks (min: {min_chunks})")
            return self._format_chunks_raw(nodes)
        
        print(f"[CONTEXT-DISTILL] Distilling {len(nodes)} chunks for query: {query[:100]}...")
        
        try:
            # Build context from chunks
            chunks_text = []
            for i, node in enumerate(nodes, 1):
                chunk = f"--- Chunk {i} ---\n{node.node.get_content()}\n"
                chunks_text.append(chunk)
            
            full_context = "\n".join(chunks_text)
            
            # Distillation prompt
            prompt = self._build_distillation_prompt(query, full_context)
            
            # Call LLM with timeout protection
            print(f"[CONTEXT-DISTILL] Calling {self.model} for distillation...")
            response = self.llm.complete(prompt)
            distilled = response.text.strip()
            
            # Check if LLM explicitly said no relevant info found
            if "KHÔNG TÌM THẤY" in distilled.upper() and len(distilled) < 50:
                print(f"[CONTEXT-DISTILL] LLM determined no relevant info found")
                return "KHÔNG TÌM THẤY"  # Return as-is for agent to read
            
            # Validation: Check if distillation actually reduced content
            original_len = len(full_context)
            distilled_len = len(distilled)
            
            if distilled_len == 0:
                print(f"[ERROR] Distillation returned empty string, using raw chunks")
                return self._format_chunks_raw(nodes)
            
            reduction_ratio = 1 - (distilled_len / original_len)
            
            print(f"[CONTEXT-DISTILL] Reduced from {original_len} to {distilled_len} chars ({reduction_ratio:.1%} reduction)")
            
            # If distillation failed to reduce (model returned everything), use raw
            if reduction_ratio < 0.1:  # Less than 10% reduction
                print(f"[WARNING] Distillation did not reduce content enough, using raw chunks")
                return self._format_chunks_raw(nodes)
            
            print(f"[CONTEXT-DISTILL] ✓ Distillation successful")
            return distilled
            
        except Exception as e:
            print(f"[ERROR] Context distillation failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            print(f"[CONTEXT-DISTILL] Falling back to raw chunks")
            return self._format_chunks_raw(nodes)
    
    def _build_distillation_prompt(self, query: str, context: str) -> str:
        """
        Build prompt for context distillation with confidence scoring.
        
        Args:
            query: User's question
            context: Full context from all chunks
            
        Returns:
            Distillation prompt
        """
        return f"""Bạn là chuyên gia trích xuất thông tin từ văn bản quy định. Nhiệm vụ: TÌM và TRÍCH XUẤT **CHỈ** thông tin TRỰC TIẾP trả lời câu hỏi.

CÂU HỎI: {query}

HƯỚNG DẪN TRÍCH XUẤT:

1. **ĐÁNH GIÁ ĐỘ LIÊN QUAN:**
   - Đọc kỹ câu hỏi - xác định CHÍNH XÁC user muốn biết gì
   - Kiểm tra context có chứa đáp án TRỰC TIẾP không
   - Nếu KHÔNG TÌM THẤY đáp án → Trả về "KHÔNG TÌM THẤY"

2. **TRÍCH XUẤT (nếu tìm thấy):**
   - Copy y nguyên text từ context (KHÔNG sửa, KHÔNG diễn giải)
   - CHỈ lấy phần trả lời TRỰC TIẾP câu hỏi
   - Giữ nguyên số liệu, điều khoản, điều kiện
   - Loại bỏ info liên quan NHƯNG KHÔNG trả lời trực tiếp

3. **VÍ DỤ PHÂN BIỆT:**

✅ ĐÚNG:
- Query: "TOEIC tốt nghiệp?"
- Context có: Bảng xếp lớp + Bảng tốt nghiệp
- Trích xuất: CHỈ bảng tốt nghiệp (bỏ bảng xếp lớp)

✅ ĐÚNG:
- Query: "Giới hạn tín chỉ?"
- Context có: Điều 16 về cảnh báo học vụ
- Trích xuất: "KHÔNG TÌM THẤY" (context không nói về giới hạn tín chỉ)

❌ SAI:
- Query: "TOEIC tốt nghiệp?"
- Trích xuất: Cả 3 bảng (xếp lớp + miễn học + tốt nghiệp)
- Lỗi: Lấy thừa info không trả lời trực tiếp

❌ SAI:
- Query: "Điều kiện tốt nghiệp?"
- Context: "Sinh viên cần có TOEIC ≥ 450 điểm"
- Trích xuất: "Sinh viên cần TOEIC 450+"
- Lỗi: Sửa text gốc (≥ 450 → 450+), có thể sai nghĩa

CONTEXT ĐỂ TRÍCH XUẤT:
{context}

OUTPUT (chỉ trả về text được trích xuất hoặc "KHÔNG TÌM THẤY", KHÔNG giải thích):"""
    
    def _format_chunks_raw(self, nodes: List[NodeWithScore]) -> str:
        """
        Format chunks without distillation (fallback).
        
        Args:
            nodes: Retrieved chunks
            
        Returns:
            Formatted context string
        """
        chunks = []
        for i, node in enumerate(nodes, 1):
            # Include source metadata for context
            metadata = node.node.metadata
            source = metadata.get('file_name', 'Unknown')
            
            chunk_text = f"[Nguồn {i}: {source}]\n{node.node.get_content()}"
            chunks.append(chunk_text)
        
        return "\n\n---\n\n".join(chunks)


def create_context_distiller() -> ContextDistiller:
    """
    Factory function to create context distiller.
    
    Returns:
        ContextDistiller instance or None if disabled
    """
    if not settings.retrieval.USE_CONTEXT_DISTILLATION:
        return None
    
    return ContextDistiller()
