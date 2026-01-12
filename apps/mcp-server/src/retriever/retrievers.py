"""
Retrieval components for QueryEngine.

Contains all retrieval implementations:
- DenseRetriever: Vector similarity search
- BM25Retriever: Lexical keyword search with Vietnamese tokenization
- SparseRetriever: SPLADE (future)
"""

import json
from pathlib import Path
from typing import List, Optional, Callable

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.retrievers.bm25 import BM25Retriever

from ..utils.logger import logger


def vietnamese_tokenizer(text: str) -> List[str]:
    """
    Vietnamese word tokenizer for BM25.

    Uses underthesea for accurate Vietnamese word segmentation.
    This ensures compound words like "Học phí" are treated as single tokens.

    Args:
        text: Input text to tokenize

    Returns:
        List of tokens (lowercase)

    Examples:
        >>> vietnamese_tokenizer("Học phí sinh viên UIT")
        ['học_phí', 'sinh_viên', 'uit']
    """
    try:
        from underthesea import word_tokenize

        # word_tokenize returns space-separated tokens with underscores for compound words
        # e.g., "Học phí" -> "Học_phí"
        tokenized = word_tokenize(text, format="text")
        # Split and lowercase
        tokens = tokenized.lower().split()
        return tokens
    except Exception as e:
        logger.warning(
            f"[TOKENIZER] underthesea failed, falling back to simple split: {e}"
        )
        # Fallback to simple space-based tokenization
        return text.lower().split()


class DenseRetriever:
    """
    Dense vector retriever using semantic embeddings.

    Uses VectorStoreIndex (ChromaDB + OpenAI embeddings) for similarity search.
    """

    def __init__(self, similarity_top_k: int = 10, min_score_threshold: float = 0.25):
        """
        Initialize DenseRetriever.

        Args:
            similarity_top_k: Number of top results to retrieve
            min_score_threshold: Minimum similarity score threshold
        """
        self.similarity_top_k = similarity_top_k
        self.min_score_threshold = min_score_threshold
        logger.info(
            f"[DENSE RETRIEVER] Initialized (top_k={similarity_top_k}, min_score={min_score_threshold})"
        )

    def retrieve(self, query: str, collection: VectorStoreIndex) -> List[NodeWithScore]:
        """
        Retrieve using dense vector embeddings.

        Args:
            query: User query
            collection: VectorStoreIndex to retrieve from

        Returns:
            List of retrieved nodes with scores
        """
        logger.info(f"[DENSE RETRIEVER] Querying vector index...")
        retriever = collection.as_retriever(similarity_top_k=self.similarity_top_k)
        nodes = retriever.retrieve(query)
        logger.info(f"[DENSE RETRIEVER] Found {len(nodes)} nodes")

        # Filter by minimum score threshold
        filtered_nodes = [
            node for node in nodes if node.score >= self.min_score_threshold
        ]

        if len(filtered_nodes) < len(nodes):
            logger.info(
                f"[DENSE RETRIEVER] Filtered {len(nodes) - len(filtered_nodes)} nodes (score < {self.min_score_threshold})"
            )

        return filtered_nodes


class BM25RetrieverWrapper:
    """
    BM25 lexical retriever wrapper.

    Loads corpus from chunks.json files and provides BM25 keyword search.
    """

    def __init__(self, similarity_top_k: int = 10):
        """
        Initialize BM25 retriever.

        Args:
            similarity_top_k: Number of top results to retrieve
        """
        self.similarity_top_k = similarity_top_k
        self.retriever = None
        self._setup()

    def _setup(self):
        """Initialize BM25 retriever from chunks.json files with Vietnamese tokenizer."""
        logger.info("[BM25 RETRIEVER] Initializing with Vietnamese tokenizer...")
        try:
            nodes = self._load_corpus()
            if nodes:
                self.retriever = BM25Retriever.from_defaults(
                    nodes=nodes,
                    similarity_top_k=self.similarity_top_k,
                    tokenizer=vietnamese_tokenizer,  # Use Vietnamese word segmentation
                )
                logger.info(
                    f"[BM25 RETRIEVER] Initialized with {len(nodes)} nodes (Vietnamese tokenizer)"
                )
            else:
                logger.warning("[BM25 RETRIEVER] No nodes found for corpus")
                self.retriever = None
        except Exception as e:
            logger.error(f"[BM25 RETRIEVER] Failed to initialize: {e}")
            self.retriever = None

    def _load_corpus(self) -> List[TextNode]:
        """Load text nodes from chunks.json files for BM25."""
        nodes = []

        # Define base data path
        project_root = Path(__file__).parents[5]

        # Try finding the data directory
        possible_paths = [
            Path("data/stages/regulation"),
            Path("/app/data/stages/regulation"),
            project_root / "data/stages/regulation",
            Path(
                "/home/giakiet05/programming/projects/uit-ai-assistant/data/stages/regulation"
            ),
        ]

        data_path = None
        for p in possible_paths:
            if p.exists() and p.is_dir():
                data_path = p
                logger.info(f"[BM25 RETRIEVER] Loading corpus from: {data_path}")
                break

        if not data_path:
            logger.warning(
                "[BM25 RETRIEVER] Could not find data/stages/regulation directory"
            )
            return []

        # Scan for chunks.json files
        chunk_files = list(data_path.glob("*/chunks.json"))

        for cf in chunk_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                    for chunk in chunks:
                        text = chunk.get("text", "")
                        metadata = chunk.get("metadata", {})

                        # Add doc_id to metadata if present
                        if "doc_id" in chunk:
                            metadata["document_id"] = chunk["doc_id"]

                        node = TextNode(
                            text=text,
                            metadata=metadata,
                            id_=chunk.get("id") or chunk.get("chunk_id"),
                        )
                        nodes.append(node)
            except Exception as e:
                logger.warning(f"[BM25 RETRIEVER] Error reading {cf}: {e}")
                continue

        return nodes

    def retrieve(self, query: str) -> List[NodeWithScore]:
        """
        Retrieve using BM25 lexical search.

        Args:
            query: User query

        Returns:
            List of retrieved nodes with BM25 scores
        """
        if not self.retriever:
            return []

        logger.info(f"[BM25 RETRIEVER] Querying BM25 index...")
        nodes = self.retriever.retrieve(query)
        logger.info(f"[BM25 RETRIEVER] Found {len(nodes)} nodes")
        return nodes


class SparseRetriever:
    """
    Sparse vector retriever (SPLADE).

    TODO: Implement SPLADE retrieval.
    """

    def __init__(self):
        logger.info("[SPARSE RETRIEVER] Not implemented yet")

    def retrieve(self, query: str) -> List[NodeWithScore]:
        """Retrieve using sparse vectors (SPLADE)."""
        return []
