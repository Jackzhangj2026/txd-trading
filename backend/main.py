"""TXD Trade Agent System — FastAPI Application Entry Point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

app = FastAPI(
    title="TXD Trade Agent API",
    description="International trade intelligence agent system for TXD CO., LTD",
    version="0.1.0",
)

# CORS — allow GitHub Pages frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0", "llm_provider": settings.active_llm}
