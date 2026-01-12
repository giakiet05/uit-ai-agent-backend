"""
Reranker component for QueryEngine.

Supports both local CPU and Modal GPU reranking with ViRanker (Vietnamese reranking model).
"""

from typing import List

from llama_index.core.schema import NodeWithScore

from .program_filter import apply_program_filter
from ..utils.logger import logger


class Reranker:
    """
    Reranker for improving retrieval results.

    Supports:
    - Modal GPU: Fast reranking via HTTP endpoint (recommended)
    - Local CPU: Deprecated (FlagEmbedding dependency removed)
    """

    def __init__(
        self,
        use_modal: bool = True,
        reranker_model: str = "namdp-ptit/ViRanker",
        rerank_score_threshold: float = 0.1,
        modal_reranker_url: str = None
    ):
        """
        Initialize Reranker.

        Args:
            use_modal: Use Modal GPU endpoint (recommended)
            reranker_model: Model name (for logging)
            rerank_score_threshold: Minimum score threshold after reranking
            modal_reranker_url: Modal HTTP endpoint URL
        """
        self.use_modal = use_modal
        self.reranker_model = reranker_model
        self.rerank_score_threshold = rerank_score_threshold
        self.modal_reranker_url = modal_reranker_url

        if use_modal:
            self._setup_modal()
        else:
            self._setup_local()

        reranker_mode = "Modal GPU" if use_modal else "Local CPU"
        logger.info(f"[RERANKER] Initialized: {reranker_model} ({reranker_mode})")
        logger.info(f"[RERANKER] Score threshold: {rerank_score_threshold}")

    def _setup_modal(self):
        """Setup Modal GPU reranker."""
        if not self.modal_reranker_url:
            raise ValueError("Modal reranker URL is required when use_modal=True")

        logger.info(f"[RERANKER] Using Modal HTTP endpoint: {self.modal_reranker_url}")

    def _setup_local(self):
        """
        Local reranker is no longer supported.

        FlagEmbedding dependency was removed to reduce Docker image size.
        Use Modal GPU reranker instead.
        """
        raise RuntimeError(
            "Local reranker not available. FlagEmbedding dependency removed to reduce Docker image size.\n"
            "Please use Modal GPU reranker by setting use_modal=True.\n"
            "Deploy the Modal reranker with: modal deploy modal/reranker_service.py"
        )

    def rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """
        Rerank nodes using ViRanker.

        Args:
            query: User query
            nodes: Retrieved nodes to rerank

        Returns:
            Reranked and filtered nodes (sorted by score)
        """
        if not nodes:
            return []

        logger.info(f"[RERANKER] Reranking {len(nodes)} nodes with ViRanker...")

        # Prepare texts for reranker
        texts = [node.node.get_content() for node in nodes]

        # Get reranker scores
        if self.use_modal:
            scores = self._rerank_modal(query, texts)
        else:
            scores = self._rerank_local(query, texts)

        # Handle case where reranking failed
        if scores is None:
            logger.warning("[RERANKER] Reranking failed, returning original nodes")
            return nodes

        # Update node scores and sort
        for node, score in zip(nodes, scores):
            node.score = float(score)

        nodes.sort(key=lambda x: x.score, reverse=True)

        # Log top 3 scores
        logger.info(f"[RERANKER] Top 3 scores:")
        for i, node in enumerate(nodes[:3]):
            doc_id = node.node.metadata.get('document_id', 'unknown')
            logger.info(f"  {i+1}. Score: {node.score:.4f} | Doc: {doc_id[:60]}...")

        # Filter out low-confidence results
        filtered_nodes = [node for node in nodes if node.score >= self.rerank_score_threshold]

        if len(filtered_nodes) < len(nodes):
            logger.info(f"[RERANKER] Filtered {len(nodes) - len(filtered_nodes)} low-confidence results (score < {self.rerank_score_threshold})")

        # Log final results
        if len(filtered_nodes) == 0:
            logger.info(f"[RERANKER] No results passed threshold ({self.rerank_score_threshold}), returning empty list")
        else:
            logger.info(f"[RERANKER] Reranking complete. Top score: {filtered_nodes[0].score:.4f}, kept {len(filtered_nodes)}/{len(nodes)} nodes")

        # Apply program-based filtering to avoid confusion between similar majors
        filtered_nodes = apply_program_filter(query, filtered_nodes)

        return filtered_nodes

    def _rerank_modal(self, query: str, texts: List[str]) -> List[float]:
        """
        Rerank using Modal GPU endpoint.

        Args:
            query: User query
            texts: List of texts to rerank

        Returns:
            List of reranker scores (or None if failed)
        """
        logger.info(f"[RERANKER] Using Modal GPU (this may take 10-60s on cold start)...")

        try:
            import requests

            # Call HTTP endpoint with longer timeout for cold start
            response = requests.post(
                self.modal_reranker_url,
                json={
                    "query": query,
                    "texts": texts,
                    "normalize": True
                },
                timeout=120  # 2 minutes to handle cold start
            )
            response.raise_for_status()
            scores = response.json()["scores"]
            logger.info(f"[RERANKER] Modal GPU reranking completed")
            return scores

        except requests.exceptions.Timeout:
            logger.warning(f"[RERANKER] Modal reranking timed out (cold start can take 60s+)")
            logger.warning("            Skipping reranking for this query")
            return None
        except Exception as e:
            logger.warning(f"[RERANKER] Modal reranking failed: {e}")
            logger.warning("            Skipping reranking for this query")
            return None

    def _rerank_local(self, query: str, texts: List[str]) -> List[float]:
        """
        Local reranking (deprecated).

        Raises:
            RuntimeError: Local reranker not available
        """
        raise RuntimeError("Local reranker not available. Use Modal GPU reranker instead.")
