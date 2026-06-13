"""LLM settings API — view and change provider at runtime."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.llm_config import (
    load_runtime_config, save_runtime_config, LLM_PROVIDERS,
    get_active_provider, get_api_key,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMConfigOut(BaseModel):
    active_llm: str
    available_providers: list[dict]
    has_api_key: bool = False


class LLMConfigIn(BaseModel):
    active_llm: str
    api_key: str = ""


@router.get("/llm")
async def get_llm_config():
    """Get current LLM provider config (never expose full API key)."""
    runtime = load_runtime_config()
    active = get_active_provider()
    key = get_api_key(active, runtime)

    providers = []
    for pid, info in LLM_PROVIDERS.items():
        providers.append({
            "id": pid,
            "label": info["label"],
            "model": info["model"],
        })

    return LLMConfigOut(
        active_llm=active,
        available_providers=providers,
        has_api_key=bool(key),
    )


@router.put("/llm")
async def update_llm_config(data: LLMConfigIn):
    """Update LLM provider and API key at runtime."""
    if data.active_llm not in LLM_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {data.active_llm}")

    runtime = load_runtime_config()
    runtime["active_llm"] = data.active_llm

    # Store API key for this provider
    key_map = {
        "deepseek": "deepseek_api_key",
        "openai": "openai_api_key",
        "claude": "anthropic_api_key",
    }
    db_key = key_map.get(data.active_llm)
    if db_key:
        if data.api_key:
            runtime[db_key] = data.api_key
        else:
            runtime.pop(db_key, None)

    save_runtime_config(runtime)
    return {"status": "ok", "active_llm": data.active_llm, "has_api_key": bool(get_api_key(data.active_llm, runtime))}
