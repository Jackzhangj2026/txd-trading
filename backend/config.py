"""Application configuration via environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Provider
    active_llm: Literal["deepseek", "openai", "claude", "gemini", "qwen", "ollama"] = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Google Custom Search (for market scanner)
    google_api_key: str = ""
    google_cse_id: str = ""

    # Serper.dev Google Search (free 2500/month)
    serper_api_key: str = ""

    # Tavily Search (for LinkedIn decision-maker discovery)
    tavily_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./trade_agent.db"

    # Factory images directory
    @property
    def factory_image_dir(self):
        from pathlib import Path
        return Path(__file__).parent.parent / "factory image"

    # App
    secret_key: str = "change-this-to-a-random-string"
    debug: bool = True

    model_config = {"env_file": str(Path(__file__).parent / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
