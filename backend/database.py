"""Database engine, session factory, and lifecycle."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables (dev convenience — use Alembic in prod)."""
    from backend.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed website templates on first run
    from backend.tasks.seed_templates import seed_templates
    async with async_session() as session:
        result = await seed_templates(session)
        if result["seeded"] > 0:
            print(f"  [OK] Seeded {result['seeded']} website templates")
