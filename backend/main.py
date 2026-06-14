"""TXD Trade Agent System — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.config import settings
from backend.database import init_db
from backend.scheduler import start_scheduler
from backend.admin.router import router as admin_router
from backend.routers import content, customers, products, inquiries, mailboxes, emails, target_markets
from backend.routers import websites as websites_router
from backend.routers.settings import router as settings_router
from backend.routers.auto_crm import router as auto_crm_router
from backend.routers.campaign import router as campaign_router
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

# Mount factory images as static files
factory_img_dir = Path(__file__).parent.parent / "factory image"
if factory_img_dir.exists():
    app.mount("/factory-images", StaticFiles(directory=str(factory_img_dir)), name="factory_images")

app.include_router(content.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(inquiries.router)
app.include_router(mailboxes.router)
app.include_router(emails.router)
app.include_router(target_markets.router)
app.include_router(websites_router.router)
app.include_router(settings_router)
app.include_router(auto_crm_router)
app.include_router(campaign_router)
app.include_router(admin_router)
app.include_router(content_media_router.router)


@app.get("/api/health")
async def health_check():
    db_ok = False
    try:
        from backend.database import async_session
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    
    from backend.services.llm_config import get_active_provider, get_api_key
    provider = get_active_provider()
    has_key = bool(get_api_key(provider))
    
    return {
        "status": "ok",
        "version": "0.1.0",
        "llm_provider": provider,
        "database": "connected" if db_ok else "disconnected",
        "has_api_key": has_key,
    }
