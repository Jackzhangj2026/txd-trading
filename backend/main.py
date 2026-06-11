"""TXD Trade Agent System — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.scheduler import start_scheduler
from backend.admin.router import router as admin_router
from backend.routers import content, customers, products, inquiries, mailboxes, emails, target_markets
from backend.routers import content_media as content_media_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield


app = FastAPI(
    title="TXD Trade Agent API",
    description="International trade intelligence agent system for TXD CO., LTD",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow GitHub Pages frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(inquiries.router)
app.include_router(mailboxes.router)
app.include_router(emails.router)
app.include_router(target_markets.router)
app.include_router(admin_router)
app.include_router(content_media_router.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0", "llm_provider": settings.active_llm}
