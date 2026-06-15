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

    # Auto-import auto-crm leads if customers table is empty
    from backend.models.customer import Customer
    from sqlalchemy import select, func
    async with async_session() as session:
        count = (await session.execute(select(func.count()).select_from(select(Customer).subquery()))).scalar() or 0
        if count == 0:
            from backend.tasks.import_auto_crm import import_all
            result = await import_all(session)
            print(f"  [OK] Auto-imported {result['customers_imported']} auto-crm customers, {result['logs_imported']} email logs")
            
            # Mark contacted leads
            from backend.tasks.update_crm_status import update_contacted_status
            update_result = await update_contacted_status(session)
            print(f"  [OK] Marked {update_result['updated']} customers as contacted from auto-crm history")
