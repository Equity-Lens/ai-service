import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This is the FastAPI agent/API service. Tool-side settings (Pinecone, Postgres,
    embeddings) live in the separate ai-mcp-service.
    """

    # OpenAI — read from the environment by the Agents SDK; kept here so load_dotenv
    # surfaces it and for explicit documentation.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # MCP tool server (ai-mcp-service) connection.
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8001"))
    # Full URL of the MCP tool server. Set this in production to the private host,
    # e.g. https://ai-mcp-service.internal/mcp. When empty, it is built from
    # MCP_SERVER_HOST/PORT for local dev.
    MCP_URL: str = os.getenv("MCP_URL", "")

    LLM_MODEL: str = os.getenv("LLM_MODEL", "ft:gpt-4o-mini-2024-07-18:personal::Cf7mkyUO")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    """
    return Settings()


settings = get_settings()
