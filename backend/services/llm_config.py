"""Runtime LLM provider config — persisted to JSON, overrides .env at runtime."""

import json
import os
from pathlib import Path
from typing import Optional

RUNTIME_FILE = Path(__file__).parent / ".llm_runtime.json"

# Available providers
LLM_PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "model": "deepseek-chat", "api_base": "https://api.deepseek.com", "key_var": "DEEPSEEK_API_KEY"},
    "openai": {"label": "OpenAI", "model": "gpt-4o-mini", "api_base": "https://api.openai.com/v1", "key_var": "OPENAI_API_KEY"},
    "claude": {"label": "Claude (Anthropic)", "model": "claude-sonnet-4-20250514", "api_base": "https://api.anthropic.com", "key_var": "ANTHROPIC_API_KEY"},
    "gemini": {"label": "Google Gemini", "model": "gemini/gemini-2.0-flash", "api_base": "https://generativelanguage.googleapis.com", "key_var": ""},
    "qwen": {"label": "Alibaba Qwen", "model": "openai/qwen-turbo", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "key_var": ""},
    "ollama": {"label": "Ollama (Local)", "model": "ollama/llama3.2", "api_base": "http://localhost:11434", "key_var": ""},
    "lmstudio": {"label": "LM Studio (Local)", "model": "openai/qwen3-vl-4b-instruct", "api_base": "http://localhost:1234/v1", "key_var": ""},
}


def load_runtime_config() -> dict:
    """Load runtime LLM config. Returns {active_llm, api_key} or empty dict."""
    if RUNTIME_FILE.exists():
        try:
            data = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, Exception):
            pass
    return {}


def save_runtime_config(config: dict) -> dict:
    """Save runtime LLM config to JSON file. Returns the saved config."""
    RUNTIME_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config


def get_active_provider() -> str:
    """Get the active provider name, checking runtime config first."""
    runtime = load_runtime_config()
    return runtime.get("active_llm") or os.environ.get("ACTIVE_LLM", "deepseek")


def get_api_key(provider: str, runtime_config: Optional[dict] = None) -> str:
    """Get the API key for a provider, checking runtime config first."""
    if runtime_config is None:
        runtime_config = load_runtime_config()

    # Runtime config has explicit key per provider
    key_map = {
        "deepseek": "deepseek_api_key",
        "openai": "openai_api_key",
        "claude": "anthropic_api_key",
    }
    db_key = key_map.get(provider)
    if db_key and runtime_config.get(db_key):
        return runtime_config[db_key]

    # Fallback to env
    env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        return os.environ.get(env_var, "")
    return ""
