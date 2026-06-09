import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    MCP tool-server settings loaded from environment variables.
    Only the settings the tools and the MCP server actually use are kept here.
    """

    # OpenAI — used for RAG embeddings (tools/research.py)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Pinecone — RAG vector store (tools/research.py)
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "trading-bot")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))

    # PostgreSQL — portfolio/alerts (tools/portfolio.py, asyncpg format)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # MCP server bind address. Defaults to 0.0.0.0 so it works on hosting platforms
    # (Render/Railway/Fly) out of the box. When the platform injects $PORT, that wins;
    # otherwise MCP_SERVER_PORT (or 8001 locally) is used. Binding 0.0.0.0 is also
    # reachable via localhost for local dev.
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    MCP_SERVER_PORT: int = int(os.getenv("PORT") or os.getenv("MCP_SERVER_PORT", "8001"))

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()


settings = get_settings()
