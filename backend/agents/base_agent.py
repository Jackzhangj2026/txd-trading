"""LLM provider abstraction — unified interface for any model provider."""

from typing import Any
from litellm import acompletion
from backend.config import settings
from backend.services.llm_config import load_runtime_config, get_api_key

# Provider configuration map
LLM_PROVIDERS = {
    "deepseek": {
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "api_base": "https://api.openai.com/v1",
    },
    "claude": {
        "model": "claude-sonnet-4-20250514",
        "api_base": "https://api.anthropic.com",
    },
    "gemini": {
        "model": "gemini/gemini-2.0-flash",
        "api_base": "https://generativelanguage.googleapis.com",
    },
    "qwen": {
        "model": "openai/qwen-turbo",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "ollama": {
        "model": "ollama/llama3.2",
        "api_base": "http://localhost:11434",
    },
    "lmstudio": {
        "model": "openai/qwen3-vl-4b-instruct",
        "api_base": "http://localhost:1234/v1",
    },
}


def get_provider_config(provider_name: str) -> dict[str, Any]:
    """Get provider configuration, checking runtime config first, then env."""
    provider = LLM_PROVIDERS.get(provider_name, LLM_PROVIDERS["deepseek"])
    config: dict[str, Any] = {
        "model": provider["model"],
        "api_base": provider["api_base"],
    }

    # Check runtime config first (set via admin UI)
    runtime = load_runtime_config()
    key = get_api_key(provider_name, runtime)
    if key:
        config["api_key"] = key
    else:
        # Fallback to .env
        api_key_map = {
            "deepseek": settings.deepseek_api_key,
            "openai": settings.openai_api_key,
            "claude": settings.anthropic_api_key,
        }
        if provider_name in api_key_map and api_key_map[provider_name]:
            config["api_key"] = api_key_map[provider_name]

    return config


class TradeAgent:
    """Base class for all trade intelligence agents.

    Provides a unified LLM interface. All agents subclass this.
    """

    def __init__(self, system_prompt: str | None = None):
        runtime = load_runtime_config()
        active = runtime.get("active_llm") or settings.active_llm
        provider_cfg = get_provider_config(active)
        self.model = provider_cfg["model"]
        self.api_base = provider_cfg["api_base"]
        self.api_key = provider_cfg.get("api_key")
        self.system_prompt = system_prompt or "You are a helpful international trade assistant."

    async def chat(self, message: str, temperature: float = 0.3) -> str:
        """Send a message to the LLM and return the response."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await acompletion(**kwargs)
        return response.choices[0].message.content

    async def classify(self, text: str, categories: list[str]) -> str:
        """Classify text into one of the given categories."""
        prompt = f"""Classify the following text into exactly one of these categories: {', '.join(categories)}

Text: {text}

Category:"""
        result = await self.chat(prompt, temperature=0.1)
        for cat in categories:
            if cat.lower() in result.strip().lower():
                return cat
        return categories[0]  # Default to first
