"""Database engine, session factory, and lifecycle."""

from backend.config import settings

# Lazy-loaded async engine (Python 3.13 requires sqlalchemy.ext.asyncio
# to be imported inside an async context)
_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
    return _engine


def _get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
        _async_session_factory = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


def async_session(**kwargs):
    """Lazy proxy — returns a new AsyncSession context manager."""
    return _get_async_session_factory()(**kwargs)


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
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed website templates on first run (non-blocking)
    try:
        from backend.tasks.seed_templates import seed_templates
        async with async_session() as session:
            result = await seed_templates(session)
            if result["seeded"] > 0:
                print(f"  [OK] Seeded {result['seeded']} website templates")
    except Exception as e:
        print(f"  [SKIP] Template seeding: {e}")

    # Auto-import auto-crm leads if customers table is empty (non-blocking)
    try:
        from backend.models.customer import Customer
        from sqlalchemy import select, func
        async with async_session() as session:
            count = (await session.execute(
                select(func.count()).select_from(select(Customer).subquery())
            )).scalar() or 0
            if count == 0:
                from backend.tasks.import_auto_crm import import_all
                result = await import_all(session)
                print(f"  [OK] Auto-imported {result['customers_imported']} auto-crm customers, {result['logs_imported']} email logs")
                
                from backend.tasks.update_crm_status import update_contacted_status
                update_result = await update_contacted_status(session)
                print(f"  [OK] Marked {update_result['updated']} customers as contacted")
    except Exception as e:
        print(f"  [SKIP] Auto-import: {e}")
