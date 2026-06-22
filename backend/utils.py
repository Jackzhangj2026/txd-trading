"""Shared utilities — paginate, get_or_404, constants."""
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate(query, page: int, page_size: int, db: AsyncSession) -> dict:
    """Execute a paginated query. Returns {items, total, page, page_size}."""
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    return {
        "items": result.scalars().all(),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_or_404(db: AsyncSession, model, obj_id: str, label: str = "Item"):
    """Fetch a single object by ID or raise 404."""
    result = await db.execute(select(model).where(model.id == obj_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj
