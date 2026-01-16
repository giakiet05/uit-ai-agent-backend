"""
Reasoning-based search using ToC structures.

3-step workflow:
1. Select documents: LLM reads toc_index.json, selects relevant docs
2. Select nodes: LLM reads ToC structure, selects relevant nodes
3. Retrieve text: Get full text from selected nodes
"""

import json
from typing import List, Dict, Any, Optional

from openai import OpenAI

from ..config.settings import settings
from ..utils.logger import logger
from .toc_loader import TocLoader


class ReasoningSearch:
    """3-step reasoning-based document search."""

    def __init__(
        self,
        document_selection_model: str = "gpt-5-nano",
        node_selection_model: str = "gpt-5-mini",
        answer_generation_model: str = "gpt-5-mini",
        max_docs: int = 3,
        max_nodes: int = 5,
    ):
        """
        Initialize reasoning search.

        Args:
            document_selection_model: LLM model for step 1 (document selection from index)
            node_selection_model: LLM model for step 2 (node selection from ToC tree)
            answer_generation_model: LLM model for step 4 (answer generation from context)
            max_docs: Maximum documents to select in step 1
            max_nodes: Maximum nodes to select per document in step 2
        """
        self.client = OpenAI(api_key=settings.credentials.OPENAI_API_KEY)
        self.document_selection_model = document_selection_model
        self.node_selection_model = node_selection_model
        self.answer_generation_model = answer_generation_model
        self.max_docs = max_docs
        self.max_nodes = max_nodes

        self.toc_loader = TocLoader()

        logger.info(
            f"[REASONING SEARCH] Initialized with "
            f"doc_selection={document_selection_model}, "
            f"node_selection={node_selection_model}, "
            f"answer_gen={answer_generation_model}, "
            f"max_docs={max_docs}, max_nodes={max_nodes}"
        )

    def search(self, query: str) -> Dict[str, Any]:
        """
        Execute 3-step reasoning search.

        Args:
            query: User query

        Returns:
            Dict with selected_docs, selected_nodes, and retrieved_text
        """
        logger.info(f"[REASONING SEARCH] Starting search for query: {query[:100]}...")

        # Step 1: Select documents
        logger.info("[REASONING SEARCH] Step 1: Selecting documents from index...")
        selected_docs = self._select_documents(query)

        if not selected_docs:
            logger.warning("[REASONING SEARCH] No relevant documents found")
            return {
                "query": query,
                "selected_docs": [],
                "selected_nodes": {},
                "retrieved_text": [],
                "error": "Không tìm thấy tài liệu liên quan"
            }

        logger.info(f"[REASONING SEARCH] Step 1 complete: Selected {len(selected_docs)} docs: {selected_docs}")

        # Step 2: Select nodes from each document
        logger.info("[REASONING SEARCH] Step 2: Selecting nodes from documents...")
        all_nodes = {}
        for doc_id in selected_docs:
            try:
                logger.info(f"[REASONING SEARCH] Loading ToC for: {doc_id}")
                nodes = self._select_nodes(query, doc_id)
                if nodes:
                    all_nodes[doc_id] = nodes
                    logger.info(f"[REASONING SEARCH] Selected nodes from {doc_id}: {nodes}")
                else:
                    logger.warning(f"[REASONING SEARCH] No relevant nodes found in {doc_id}")
            except FileNotFoundError as e:
                logger.error(f"[REASONING SEARCH] ToC file not found for {doc_id}: {e}")
                continue

        if not all_nodes:
            logger.warning("[REASONING SEARCH] No relevant nodes found in any document")
            return {
                "query": query,
                "selected_docs": selected_docs,
                "selected_nodes": {},
                "retrieved_text": [],
                "error": "Không tìm thấy mục liên quan trong các tài liệu đã chọn"
            }

        total_nodes = sum(len(nodes) for nodes in all_nodes.values())
        logger.info(f"[REASONING SEARCH] Step 2 complete: Selected {total_nodes} nodes from {len(all_nodes)} docs")

        # Step 3: Retrieve text from selected nodes
        logger.info("[REASONING SEARCH] Step 3: Retrieving text from selected nodes...")
        retrieved_text = []
        for doc_id, node_ids in all_nodes.items():
            texts = self.toc_loader.get_node_text(doc_id, node_ids)
            for node_id, text in texts.items():
                if text:
                    retrieved_text.append({
                        "doc_id": doc_id,
                        "node_id": node_id,
                        "text": text
                    })
                    logger.info(f"[REASONING SEARCH] Retrieved text from {doc_id}:{node_id} ({len(text)} chars)")

        logger.info(f"[REASONING SEARCH] Step 3 complete: Retrieved {len(retrieved_text)} text sections")
        logger.info(f"[REASONING SEARCH] Search complete for query: {query[:50]}...")

        return {
            "query": query,
            "selected_docs": selected_docs,
            "selected_nodes": all_nodes,
            "retrieved_text": retrieved_text
        }

    def _select_documents(self, query: str) -> List[str]:
        """
        Step 1: LLM selects relevant documents from index.

        Args:
            query: User query

        Returns:
            List of selected document IDs
        """
        logger.info("[REASONING SEARCH] Loading document index...")
        index_text = self.toc_loader.get_index_for_llm()
        logger.info(f"[REASONING SEARCH] Index loaded ({len(index_text)} chars)")

        prompt = f"""Bạn là trợ lý chọn tài liệu. Dựa trên câu hỏi của người dùng, hãy chọn các tài liệu liên quan nhất từ danh sách bên dưới.

Câu hỏi: {query}

Danh sách tài liệu:
{index_text}

Hướng dẫn:
- Chọn tối đa {self.max_docs} tài liệu liên quan nhất
- CHỈ trả về một JSON array chứa các document ID
- Ví dụ: ["doc_id_1", "doc_id_2"]
- Nếu không có tài liệu nào liên quan, trả về []

Các document ID được chọn (chỉ JSON array):"""

        logger.info(f"[REASONING SEARCH] Calling LLM ({self.document_selection_model}) to select documents...")
        response = self.client.chat.completions.create(
            model=self.document_selection_model,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content.strip()
        logger.info(f"[REASONING SEARCH] LLM response: {response_text}")

        try:
            selected = json.loads(response_text)
            if isinstance(selected, list):
                available_docs = self.toc_loader.get_all_doc_ids()
                valid_docs = [doc_id for doc_id in selected if doc_id in available_docs]
                logger.info(f"[REASONING SEARCH] Valid document IDs: {valid_docs}")
                return valid_docs
        except json.JSONDecodeError as e:
            logger.error(f"[REASONING SEARCH] Failed to parse LLM response as JSON: {e}")

        return []

    def _select_nodes(self, query: str, doc_id: str) -> List[str]:
        """
        Step 2: LLM selects relevant nodes from document ToC.

        Args:
            query: User query
            doc_id: Document ID to search within

        Returns:
            List of selected node IDs
        """
        logger.info(f"[REASONING SEARCH] Loading ToC structure for {doc_id}...")
        toc_text = self.toc_loader.get_toc_for_llm(doc_id, include_text=False)
        logger.info(f"[REASONING SEARCH] ToC loaded ({len(toc_text)} chars)")

        prompt = f"""Bạn là trợ lý chọn mục trong tài liệu. Dựa trên câu hỏi của người dùng và cấu trúc tài liệu, hãy chọn các mục có khả năng chứa câu trả lời nhất.

Câu hỏi: {query}

Cấu trúc tài liệu:
{toc_text}

Hướng dẫn:
- Chọn tối đa {self.max_nodes} mục liên quan nhất
- Dựa vào tiêu đề và tóm tắt của các mục để quyết định
- CHỈ trả về một JSON array chứa các node ID (giá trị trong ngoặc vuông như [1], [1.1], v.v.)
- Ví dụ: ["1", "1.2", "2.3.1"]
- Nếu không có mục nào liên quan, trả về []

Các node ID được chọn (chỉ JSON array):"""

        logger.info(f"[REASONING SEARCH] Calling LLM ({self.node_selection_model}) to select nodes...")
        response = self.client.chat.completions.create(
            model=self.node_selection_model,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content.strip()
        logger.info(f"[REASONING SEARCH] LLM response: {response_text}")

        try:
            selected = json.loads(response_text)
            if isinstance(selected, list):
                node_ids = [str(node_id) for node_id in selected]
                logger.info(f"[REASONING SEARCH] Selected node IDs: {node_ids}")
                return node_ids
        except json.JSONDecodeError as e:
            logger.error(f"[REASONING SEARCH] Failed to parse LLM response as JSON: {e}")

        return []

    def format_for_answer(self, search_result: Dict[str, Any]) -> str:
        """
        Format search result for answer generation.

        Args:
            search_result: Result from search() method

        Returns:
            Formatted context string for LLM
        """
        logger.info("[REASONING SEARCH] Formatting search result for answer generation...")

        if not search_result.get("retrieved_text"):
            logger.warning("[REASONING SEARCH] No retrieved text to format")
            return "Không tìm thấy thông tin liên quan."

        sections = []
        for item in search_result["retrieved_text"]:
            section = f"[Nguồn: {item['doc_id']}, Mục: {item['node_id']}]\n{item['text']}"
            sections.append(section)

        formatted = "\n\n---\n\n".join(sections)
        logger.info(f"[REASONING SEARCH] Formatted context: {len(formatted)} chars, {len(sections)} sections")

        return formatted

    def generate_answer(self, query: str, context: str, search_result: Dict[str, Any]) -> str:
        """
        Generate answer from retrieved context.

        Args:
            query: User query
            context: Formatted context from format_for_answer()
            search_result: Search result dict for source info

        Returns:
            Generated answer with sources
        """
        logger.info("[REASONING SEARCH] Step 4: Generating answer from context...")

        if not context or context == "Không tìm thấy thông tin liên quan.":
            logger.warning("[REASONING SEARCH] No context available for answer generation")
            return "Không tìm thấy thông tin liên quan để trả lời câu hỏi này."

        prompt = f"""Bạn là trợ lý AI của Trường Đại học Công nghệ Thông tin (UIT). Hãy trả lời câu hỏi của người dùng dựa trên thông tin được cung cấp.

Câu hỏi: {query}

Thông tin tham khảo:
{context}

Hướng dẫn:
- Trả lời bằng tiếng Việt, rõ ràng và chính xác
- CHỈ sử dụng thông tin từ nội dung được cung cấp
- Nếu thông tin không đủ để trả lời, hãy nói rõ
- Trích dẫn nguồn khi cần thiết (ví dụ: "Theo Điều X...")
- Không bịa đặt thông tin

Câu trả lời:"""

        logger.info(f"[REASONING SEARCH] Calling LLM ({self.answer_generation_model}) to generate answer...")
        response = self.client.chat.completions.create(
            model=self.answer_generation_model,
            messages=[{"role": "user", "content": prompt}],
        )

        answer = response.choices[0].message.content.strip()
        logger.info(f"[REASONING SEARCH] Answer generated ({len(answer)} chars)")

        # Add source references
        sources = []
        for doc_id in search_result.get("selected_docs", []):
            nodes = search_result.get("selected_nodes", {}).get(doc_id, [])
            if nodes:
                sources.append(f"- {doc_id}: {', '.join(nodes)}")

        if sources:
            answer += "\n\n---\nNguồn tham khảo:\n" + "\n".join(sources)

        logger.info("[REASONING SEARCH] Answer generation complete")
        return answer

    def search_and_answer(self, query: str) -> Dict[str, Any]:
        """
        Execute full RAG pipeline: search and generate answer.

        Args:
            query: User query

        Returns:
            Dict with answer, selected_docs, selected_nodes, and error if any
        """
        logger.info(f"[REASONING SEARCH] Starting full RAG pipeline for: {query[:100]}...")

        # Search for relevant content
        search_result = self.search(query)

        # Check for errors
        if search_result.get("error"):
            return {
                "query": query,
                "answer": search_result["error"],
                "selected_docs": search_result.get("selected_docs", []),
                "selected_nodes": search_result.get("selected_nodes", {}),
                "error": search_result["error"]
            }

        # Format context
        context = self.format_for_answer(search_result)

        # Generate answer
        answer = self.generate_answer(query, context, search_result)

        logger.info("[REASONING SEARCH] Full RAG pipeline complete")

        return {
            "query": query,
            "answer": answer,
            "selected_docs": search_result.get("selected_docs", []),
            "selected_nodes": search_result.get("selected_nodes", {}),
            "error": None
        }
