"""Customer stats endpoint — total, daily increase, source distribution."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.customer import Customer

router = APIRouter(prefix="/api/customer-stats", tags=["customer-stats"])


@router.get("")
async def get_customer_stats(db: AsyncSession = Depends(get_db)):
    """Get customer statistics: total, today's new, source distribution."""
    now = datetime.now(timezone.utc)

    total_result = await db.execute(select(func.count()).select_from(select(Customer).subquery()))
    total = total_result.scalar() or 0

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count()).select_from(
            select(Customer).where(Customer.created_at >= today_start).subquery()
        )
    )
    today_new = today_result.scalar() or 0

    week_start = today_start - timedelta(days=today_start.weekday())
    week_result = await db.execute(
        select(func.count()).select_from(
            select(Customer).where(Customer.created_at >= week_start).subquery()
        )
    )
    week_new = week_result.scalar() or 0

    source_query = await db.execute(
        select(Customer.source, func.count()).group_by(Customer.source)
    )
    sources = {row[0] or "unknown": row[1] for row in source_query.fetchall()}

    hot = (await db.execute(
        select(func.count()).select_from(select(Customer).where(Customer.score >= 80).subquery())
    )).scalar() or 0
    warm = (await db.execute(
        select(func.count()).select_from(select(Customer).where(Customer.score >= 60, Customer.score < 80).subquery())
    )).scalar() or 0
    cold = (await db.execute(
        select(func.count()).select_from(select(Customer).where(Customer.score >= 30, Customer.score < 60).subquery())
    )).scalar() or 0

    return {
        "total": total,
        "today_new": today_new,
        "week_new": week_new,
        "sources": sources,
        "scores": {"hot": hot, "warm": warm, "cold": cold},
    }
