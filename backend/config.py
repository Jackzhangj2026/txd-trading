"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Provider
    active_llm: Literal["deepseek", "openai", "claude", "gemini", "qwen", "ollama"] = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./trade_agent.db"

    # App
    secret_key: str = "change-this-to-a-random-string"
    debug: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
