"""
Centralized configuration management for the entire application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration Groups (as nested classes) ---


class Credentials:
    """API keys and sensitive credentials."""

    def __init__(self):
        """Load credentials from environment."""
        load_dotenv()
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class LLM:
    """LLM configuration (models, providers)."""

    def __init__(self):
        """Load LLM configs from environment."""
        load_dotenv()
        self.PROVIDER = os.getenv("LLM_PROVIDER", "openai")
        self.MODEL = os.getenv("LLM_MODEL", "gpt-5-nano")
        
        # Classifier model for intent routing
        self.CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "gpt-5-nano")


class Checkpointer:
    """LangGraph checkpointer configuration for state persistence."""

    def __init__(self):
        """Load checkpointer configs from environment."""
        load_dotenv()
        # Options: "memory" (in-memory, testing only), "postgres" (production)
        self.BACKEND = os.getenv("CHECKPOINTER_BACKEND", "memory")

        # PostgreSQL connection string (only used if BACKEND="postgres")
        # Format: postgresql://user:password@host:port/dbname
        self.POSTGRES_URI = os.getenv(
            "CHECKPOINTER_POSTGRES_URI",
            "postgresql://postgres:postgres@localhost:5432/langgraph",
        )


class MCP:
    """MCP server configuration."""

    def __init__(self):
        """Load MCP configs from environment."""
        load_dotenv()
        self.SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")


class Redis:
    """Redis configuration."""

    def __init__(self):
        """Load Redis configs from environment."""
        load_dotenv()
        self.URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class GRPC:
    """gRPC server configuration."""

    def __init__(self):
        """Load gRPC configs from environment."""
        load_dotenv()
        self.PORT = int(os.getenv("GRPC_PORT", "50051"))


# --- Main Settings Singleton Class ---


class Settings:
    """
    The main singleton class that holds all configuration objects.
    """

    def __init__(self):
        print("[CONFIG] Initializing application settings...")

        # Load credentials first (used by other modules)
        self.credentials = Credentials()
        self.llm = LLM()
        self.mcp = MCP()
        self.redis = Redis()
        self.grpc = GRPC()
        self.checkpointer = Checkpointer()


# --- Singleton Instance ---
settings = Settings()
