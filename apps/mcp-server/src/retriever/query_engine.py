"""
QueryEngine - Orchestrates blended retrieval and re-ranking.

This engine uses a blended retrieval approach:
1. Retrieves from multiple indexes (dense vector, BM25, sparse vector)
2. Merges and deduplicates results
3. Re-ranks with a reranker model
4. Returns top-k most relevant documents

Design Philosophy:
- Blended: Always query all available indexes and merge results
- Modular: Easy to add new retrieval methods
- Composable: Can be used as MCP tool or standalone
- Configurable: All parameters tunable via settings
"""

from typing import List, Dict, Optional, Literal
from dataclasses import dataclass

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore

from .retrievers import DenseRetriever, BM25RetrieverWrapper
from .reranker import Reranker
from .hyde import HyDEGenerator
from .context_distillation import create_context_distiller
from .filters import normalize_vietnamese_text, filter_by_program_context
from .formatters import ResultFormatter
from ..utils.logger import logger


@dataclass
class RetrievalResult:
    """Result from retrieval + reranking."""
    nodes: List[NodeWithScore]
    retrieval_method: str
    reranked: bool
    total_retrieved: int
    final_count: int


class QueryEngine:
    """
    Main query engine that orchestrates blended retrieval.

    Blended retrieval: Always queries all available indexes and merges results.

    Current support:
    - Dense vector retrieval (OpenAI embeddings)

    Future support (will be automatically included in blended retrieval):
    - BM25 lexical search
    - Sparse vector retrieval (SPLADE)
    """

    def __init__(
        self,
        collections: Dict[str, VectorStoreIndex],
        use_reranker: bool = True,
        reranker_model: Optional[str] = None,
        top_k: int = 3,
        retrieval_top_k: int = 10,  # Retrieve 10 chunks for reranking (reduced from 20 for better performance)
        rerank_score_threshold: float = 0.7,  # Filter out low-confidence results after reranking
        min_score_threshold: float = 0.25,  # Minimum score for initial retrieval
        use_modal: bool = False,  # Use Modal GPU for reranking (faster)
        use_hyde: bool = False,  # Use HyDE (Hypothetical Document Embeddings)
        hyde_model: str = "gpt-5-nano"  # Model for HyDE generation
    ):
        """
        Initialize QueryEngine.

        Args:
            collections: Dict of collection_name -> VectorStoreIndex
            use_reranker: Whether to use reranker after retrieval
            reranker_model: Reranker model name (default: "namdp-ptit/ViRanker" for Vietnamese)
            top_k: Final number of documents to return
            retrieval_top_k: Number of documents to retrieve before reranking
            rerank_score_threshold: Minimum score threshold after reranking (default: 0.4)
                                   Nodes with score < threshold will be filtered out
            min_score_threshold: Minimum score for initial retrieval (default: 0.25)
            use_modal: Use Modal GPU for reranking (default: False, use local CPU)
            use_hyde: Use HyDE for query expansion (default: False)
            hyde_model: Model for generating hypothetical documents (default: gpt-5-nano)
        """
        self.collections = collections
        self.use_reranker = use_reranker
        self.reranker_model = reranker_model or "namdp-ptit/ViRanker"
        self.top_k = top_k
        self.retrieval_top_k = retrieval_top_k
        self.rerank_score_threshold = rerank_score_threshold
        self.min_score_threshold = min_score_threshold
        self.use_modal = use_modal
        self.use_hyde = use_hyde
        self.hyde_model = hyde_model

        # Initialize retrievers
        self.dense_retriever = DenseRetriever(
            similarity_top_k=retrieval_top_k,
            min_score_threshold=min_score_threshold
        )
        self.bm25_retriever = BM25RetrieverWrapper(similarity_top_k=retrieval_top_k)

        # Initialize formatter
        self.formatter = ResultFormatter()

        # Initialize reranker if enabled
        if self.use_reranker:
            from ..config.settings import settings
            self.reranker = Reranker(
                use_modal=use_modal,
                reranker_model=self.reranker_model,
                rerank_score_threshold=rerank_score_threshold,
                modal_reranker_url=settings.retrieval.MODAL_RERANKER_URL if use_modal else None
            )

        # Initialize HyDE generator if enabled
        if self.use_hyde:
            from ..config.settings import settings
            self.hyde_generator = HyDEGenerator(
                model=hyde_model,
                api_key=settings.credentials.OPENAI_API_KEY
            )
        
        # Initialize context distiller if enabled
        self.context_distiller = create_context_distiller()

        logger.info(f"[QUERY ENGINE] Initialized with:")
        logger.info(f"  - Collections: {list(collections.keys())}")
        reranker_mode = "Modal GPU" if use_modal else "Local CPU"
        logger.info(f"  - Reranker: {self.reranker_model if use_reranker else 'disabled'} ({reranker_mode})")
        logger.info(f"  - HyDE: {'enabled' if use_hyde else 'disabled'}")
        logger.info(f"  - Context Distillation: {'enabled' if self.context_distiller else 'disabled'}")
        logger.info(f"  - Retrieval top_k: {retrieval_top_k}")
        logger.info(f"  - Final top_k: {top_k}")
        logger.info(f"  - Min score threshold: {min_score_threshold}")
        logger.info(f"  - Rerank score threshold: {rerank_score_threshold}")
        logger.info(f"  - HyDE: {'enabled' if use_hyde else 'disabled'} (model: {hyde_model if use_hyde else 'N/A'})")

    def _generate_hypothetical_document(
        self,
        query: str,
        collection_type: Literal["regulation", "curriculum"]
    ) -> str:
        """
        Generate hypothetical document using HyDE generator.

        Args:
            query: User's original query
            collection_type: Type of collection (regulation or curriculum)

        Returns:
            Hypothetical document text (or original query if HyDE disabled)
        """
        if not self.use_hyde:
            return query

        return self.hyde_generator.generate(query, collection_type)

    def _retrieve(
        self,
        query: str,
        collection_type: Literal["regulation", "curriculum"],
        use_reranker: Optional[bool] = None
    ) -> RetrievalResult:
        """
        Blended retrieval from specified collection with reranking.
        """
        # Normalize query text
        original_query = normalize_vietnamese_text(query)
        
        # Generate hypothetical document if HyDE is enabled
        if self.use_hyde:
            retrieval_query = self._generate_hypothetical_document(original_query, collection_type)
        else:
            retrieval_query = original_query

        logger.info(f"\n{'='*70}")
        logger.info(f"[QUERY ENGINE] Blended Retrieval")
        logger.info(f"[QUERY ENGINE] Original Query: {original_query}")
        if self.use_hyde:
            logger.info(f"[QUERY ENGINE] HyDE Query: {retrieval_query[:100]}...")
        logger.info(f"[QUERY ENGINE] Collection: {collection_type}")
        logger.info(f"{'='*70}\n")

        selected_collection = self.collections[collection_type]
        
        # Lists to hold candidates from different sources
        dense_nodes = []
        bm25_nodes = []

        # 1. Dense vector retrieval (using HyDE query if enabled)
        logger.info("[QUERY ENGINE] Retrieving from dense vector index...")
        dense_nodes = self.dense_retriever.retrieve(retrieval_query, selected_collection)
        logger.info(f"  → Found {len(dense_nodes)} dense nodes")

        # 2. BM25 retrieval
        if collection_type == "regulation":
            bm25_nodes = self.bm25_retriever.retrieve(retrieval_query)
            logger.info(f"  → Found {len(bm25_nodes)} BM25 nodes")

        # 3. Deduplicate (Union of candidates)
        # We keep the node structure. If a node is in both, it doesn't matter which 'score' we keep
        # because we will overwrite it with the Reranker score anyway.
        combined_nodes_map = {}
        
        # Add dense nodes first
        for node in dense_nodes:
            combined_nodes_map[node.node.node_id] = node
            
        # Add BM25 nodes (if new)
        for node in bm25_nodes:
            if node.node.node_id not in combined_nodes_map:
                combined_nodes_map[node.node.node_id] = node
        
        candidates = list(combined_nodes_map.values())
        logger.info(f"\n[QUERY ENGINE] Total unique candidates for reranking: {len(candidates)}")

        # 3.5 Apply Program Context Filter (Chính quy vs Từ xa)
        # This is critical to avoid mixing regulations from different systems
        candidates = filter_by_program_context(original_query, candidates)

        # 4. Rerank (IMPORTANT: Use ORIGINAL query for reranking, not HyDE query)
        should_rerank = use_reranker if use_reranker is not None else self.use_reranker
        
        if should_rerank and candidates:
            # Pass ALL candidates to reranker (don't pre-filter by raw score)
            # Use original query for reranking (not hypothetical doc)
            top_nodes = self._rerank(original_query, candidates)
            reranked = True
        else:
            # If no reranker, we have a problem merging scores.
            # For now, fallback to just dense nodes or naive sort if forced.
            logger.warning("[WARNING] Reranker disabled in Hybrid mode. Scores are not comparable.")
            # Fallback: Prioritize Dense nodes, append unique BM25 nodes
            # (Assuming Vector is generally better than BM25 for ranking)
            candidates.sort(key=lambda x: x.score, reverse=True) 
            top_nodes = candidates
            reranked = False

        # 5. Final top-k selection
        final_nodes = top_nodes[:self.top_k]

        logger.info(f"[QUERY ENGINE] Final result: {len(final_nodes)} nodes (reranked: {reranked})\n")

        return RetrievalResult(
            nodes=final_nodes,
            retrieval_method=f"blended_{collection_type}",
            reranked=reranked,
            total_retrieved=len(candidates),
            final_count=len(final_nodes)
        )

    def _rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """
        Rerank nodes using Reranker component.

        Args:
            query: User query
            nodes: Retrieved nodes

        Returns:
            Reranked nodes (sorted by reranker score, filtered by threshold)
        """
        if not self.use_reranker:
            return nodes

        if not hasattr(self, 'reranker'):
            logger.warning("[WARNING] Reranker not initialized, skipping reranking")
            return nodes

        return self.reranker.rerank(query, nodes)

    def retrieve_structured(
        self,
        query: str,
        collection_type: Literal["regulation", "curriculum"]
    ) -> Dict:
        """
        Retrieve and return structured format with separated metadata fields.

        Args:
            query: User query
            collection_type: Type of collection ("regulation" or "curriculum")

        Returns:
            Dict following RegulationRetrievalResult or CurriculumRetrievalResult schema
            
        Note:
            This method ALWAYS returns a valid dict, even if distillation fails.
            Errors in distillation are caught and logged, falling back to raw chunks.
        """
        try:
            # Retrieve nodes using existing pipeline
            result = self._retrieve(query, collection_type=collection_type)
            
            # Format nodes to structured output first (ensure we have valid response)
            formatted_result = self.formatter.format(query, result.nodes, collection_type)
            
            # Apply context distillation if enabled (additive feature)
            if self.context_distiller:
                try:
                    logger.info("[QUERY ENGINE] Applying context distillation...")
                    distilled_context = self.context_distiller.distill(query, result.nodes)
                    # Add distilled context to response
                    formatted_result['distilled_context'] = distilled_context
                    logger.info(f"[QUERY ENGINE] ✓ Context distilled ({len(distilled_context)} chars)")
                    
                    # Optimization: Clear document content to save tokens (metadata kept for references)
                    # Agent only needs distilled_context for answering, but metadata for PDF/source links
                    for doc in formatted_result.get('documents', []):
                        doc['content'] = ""
                    logger.info(f"[QUERY ENGINE] ✓ Cleared content from {len(formatted_result.get('documents', []))} documents (metadata kept)")
                    
                except Exception as e:
                    logger.error(f"[QUERY ENGINE] Context distillation failed: {e}")
                    # Continue without distilled context - formatted_result is still valid
                    logger.info("[QUERY ENGINE] Continuing with raw chunks only")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"[QUERY ENGINE] Retrieval failed: {e}")
            import traceback
            traceback.print_exc()
            # Return minimal valid response to prevent tool call hanging
            return {
                'query': query,
                'total_retrieved': 0,
                'documents': [],
                'error': str(e)
            }
