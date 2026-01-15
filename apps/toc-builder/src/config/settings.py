"""
Centralized configuration management for ToC Builder.

This service is responsible for:
- OCR scanned PDFs to markdown (using LlamaParse)
- Building table of contents from documents
- Creating ToC index for reasoning-based RAG
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Paths:
    """Path configurations for ToC Builder."""

    # Navigate from settings.py to project root
    # apps/toc-builder/src/config/settings.py -> root
    ROOT_DIR = Path(__file__).resolve().parents[4]
    DATA_DIR = ROOT_DIR / "data"

    # Data directories
    RAW_DATA_DIR = DATA_DIR / "raw"
    MARKDOWN_DIR = DATA_DIR / "markdown"  # NEW: LlamaParse OCR output
    TOC_DIR = DATA_DIR / "toc"  # NEW: ToC structure files

    # ToC index file
    TOC_INDEX_FILE = TOC_DIR / "toc_index.json"

    @staticmethod
    def get_markdown_file(document_id: str) -> Path:
        """
        Get markdown file path for a document.

        Args:
            document_id: Document ID (without extension)

        Returns:
            Path to markdown/{document_id}.md
        """
        return Paths.MARKDOWN_DIR / f"{document_id}.md"

    @staticmethod
    def get_toc_file(document_id: str) -> Path:
        """
        Get ToC structure file path for a document.

        Args:
            document_id: Document ID (without extension)

        Returns:
            Path to toc/{document_id}_structure.json
        """
        return Paths.TOC_DIR / f"{document_id}_structure.json"


class Credentials:
    """API keys and sensitive credentials."""

    def __init__(self):
        """Load credentials from environment."""
        load_dotenv()
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")


class LLM:
    """LLM configuration (models, providers)."""

    def __init__(self):
        """Load LLM configs from environment."""
        load_dotenv()
        self.PROVIDER = os.getenv("LLM_PROVIDER", "openai")
        self.MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")


class PageIndexConfig:
    """Configuration for PageIndex ToC building."""

    def __init__(self):
        """Load PageIndex configs from environment."""
        load_dotenv()

        # Tree building config
        self.ADD_NODE_SUMMARY = os.getenv("ADD_NODE_SUMMARY", "no") == "yes"
        self.ADD_NODE_TEXT = os.getenv("ADD_NODE_TEXT", "yes") == "yes"

        # Model for tree building (if needed)
        self.TREE_BUILD_MODEL = os.getenv("TREE_BUILD_MODEL", "gpt-4o-mini")


class LlamaParseConfig:
    """Configuration for LlamaParse OCR."""

    def __init__(self):
        """Load LlamaParse configs from environment."""
        load_dotenv()

        # LlamaParse configuration
        self.PARSE_MODE = os.getenv("PARSE_MODE", "parse_page_with_agent")
        self.PARSE_MODEL = os.getenv("PARSE_MODEL", "openai-gpt-4-1-mini")
        self.TARGET_PAGES = os.getenv("TARGET_PAGES", None)  # None = all pages


class Settings:
    """
    Main settings singleton for ToC Builder.

    Contains only configurations relevant to:
    - OCR scanned PDFs to markdown
    - Building table of contents
    - Creating ToC index
    """

    def __init__(self):
        print("[CONFIG] Initializing ToC Builder settings...")

        # Load credentials first
        self.credentials = Credentials()
        self.llm = LLM()

        # Static configs
        self.paths = Paths()

        # Dynamic configs (load from env)
        self.pageindex = PageIndexConfig()
        self.llamaparse = LlamaParseConfig()

        self._ensure_directories()

    def _ensure_directories(self):
        """Create all necessary directories if they don't exist."""
        print("[CONFIG] Ensuring all necessary directories exist...")
        directories_to_create = [
            self.paths.RAW_DATA_DIR,
            self.paths.MARKDOWN_DIR,
            self.paths.TOC_DIR,
        ]

        for directory in directories_to_create:
            os.makedirs(directory, exist_ok=True)


# Singleton instance
settings = Settings()
