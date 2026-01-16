"""
Centralized configuration for MCP Server.

This service is responsible for:
- Document retrieval from vector store
- DAA portal scraping (grades, schedule)
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Paths:
    """Path configurations for MCP Server."""

    load_dotenv()
    # Get DATA_DIR from env or use default (mounted volume in Docker)
    DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))

    # Vector store path (read-only, built by knowledge-builder)
    VECTOR_STORE_DIR = DATA_DIR / "vector_store"

    # ToC structures path (read-only, built by toc-builder)
    TOC_DIR = DATA_DIR / "toc"
    TOC_INDEX_FILE = TOC_DIR / "toc_index.json"


class Credentials:
    """API keys and sensitive credentials."""

    def __init__(self):
        """Load credentials from environment."""
        load_dotenv()
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class Retrieval:
    """Configuration for retrieval and vector search."""

    # Available ChromaDB collections
    AVAILABLE_COLLECTIONS = ["regulation", "curriculum"]

    # Retrieval configuration
    SIMILARITY_TOP_K = 7
    MINIMUM_SCORE_THRESHOLD = 0.15

    def __init__(self):
        """Load retrieval configs from environment."""
        load_dotenv()
        self.EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
        self.MODAL_RERANKER_URL = os.getenv(
            "MODAL_RERANKER_URL",
            "https://giakiet05--viranker-reranker-rerank-endpoint.modal.run"
        )
        
        # HyDE (Hypothetical Document Embeddings) configuration
        self.USE_HYDE = os.getenv("USE_HYDE", "false").lower() == "true"
        self.HYDE_MODEL = os.getenv("HYDE_MODEL", "gpt-5-nano")
        
        # Context Distillation configuration
        self.USE_CONTEXT_DISTILLATION = os.getenv("USE_CONTEXT_DISTILLATION", "false").lower() == "true"
        self.DISTILLATION_MODEL = os.getenv("DISTILLATION_MODEL", "gpt-5-nano")
        self.DISTILLATION_MIN_CHUNKS = int(os.getenv("DISTILLATION_MIN_CHUNKS", "3"))  # Only distill if >= N chunks


class ReasoningRetrieval:
    """Configuration for reasoning-based retrieval using ToC structures."""

    def __init__(self):
        """Load reasoning retrieval configs from environment."""
        load_dotenv()
        
        # Model configurations for each step
        self.DOCUMENT_SELECTION_MODEL = os.getenv("REASONING_DOC_SELECTION_MODEL", "gpt-5-nano")
        self.NODE_SELECTION_MODEL = os.getenv("REASONING_NODE_SELECTION_MODEL", "gpt-5-mini")
        self.ANSWER_GENERATION_MODEL = os.getenv("REASONING_ANSWER_GEN_MODEL", "gpt-5-mini")
        
        # Search constraints
        self.MAX_DOCS = int(os.getenv("REASONING_MAX_DOCS", "3"))
        self.MAX_NODES = int(os.getenv("REASONING_MAX_NODES", "3"))


class Settings:
    """
    Main settings singleton for MCP Server.

    Contains only configurations relevant to:
    - Reading vector store
    - Retrieving documents
    - Scraping DAA portal
    """

    def __init__(self):
        print("[CONFIG] Initializing MCP Server settings...")

        # Load credentials first (used by other modules)
        self.credentials = Credentials()

        # Static configs
        self.paths = Paths()

        # Dynamic configs (load from env)
        self.retrieval = Retrieval()
        self.reasoning = ReasoningRetrieval()

        print(f"[CONFIG] Vector store path: {self.paths.VECTOR_STORE_DIR}")
        print(f"[CONFIG] ToC path: {self.paths.TOC_DIR}")
        print(f"[CONFIG] Embed model: {self.retrieval.EMBED_MODEL}")


# Singleton instance
settings = Settings()
