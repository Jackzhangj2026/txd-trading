"""Social media content API — generate, queue, schedule, publish."""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.content_piece import ContentPiece
from backend.models.platform_account import PlatformAccount
from backend.services.content_generator import ContentGenerator

router = APIRouter(prefix="/api/content-media", tags=["content-media"])


PIATFORM_DISPLAY = {
    "linkedin": "LinkedIn", "twitter": "Twitter/X", "youtube": "YouTube",
    "tiktok": "TikTok", "pinterest": "Pinterest", "facebook": "Facebook",
    "red": "小红书 RED", "douyin": "抖音", "wechat_article": "微信 公众号",
    "wechat_moment": "微信 朋友圈",
}


class GenerateRequest(BaseModel):
    topic: str
    platforms: list[str] = ["linkedin", "twitter", "red"]


class GenerateResponse(BaseModel):
    items: list[dict]
    total: int


@router.post("/generate")
async def generate_content(data: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate social media content for a topic across platforms."""
    generator = ContentGenerator()
    created = []

    for platform in data.platforms:
        result = await generator.generate_for_platform(data.topic, platform)

        piece = ContentPiece(
            title=result.get("title", data.topic)[:300],
            content_type="post" if platform in ("linkedin", "twitter", "facebook", "pinterest") else "script",
            platform=platform,
            status="draft",
            body=result.get("body", ""),
            media_urls=json.dumps(result.get("media_urls", [])),
            language="zh" if platform in ("douyin", "wechat_article", "wechat_moment") else "en",
        )
        db.add(piece)
        created.append({"platform": platform, "title": piece.title, "id": piece.id})

    await db.commit()
    return {"items": created, "total": len(created)}


@router.get("/queue")
async def list_content_queue(
    platform: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List content queue."""
    query = select(ContentPiece)
    if platform:
        query = query.where(ContentPiece.platform == platform)
    if status:
        query = query.where(ContentPiece.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(ContentPiece.created_at))
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "platform": c.platform,
                "platform_display": PIATFORM_DISPLAY.get(c.platform, c.platform),
                "content_type": c.content_type,
                "status": c.status,
                "body": c.body or "",
                "body_preview": c.body[:200] if c.body else "",
                "scheduled_at": c.scheduled_at,
                "language": c.language,
                "created_at": str(c.created_at) if c.created_at else "",
            }
            for c in items
        ],
        "total": total,
    }


@router.put("/{content_id}")
async def update_content(content_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    """Update a content piece (edit body, schedule, etc)."""
    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    for key, value in data.items():
        if hasattr(piece, key):
            setattr(piece, key, value)

    await db.commit()
    await db.refresh(piece)
    return {"id": piece.id, "status": piece.status}


@router.post("/{content_id}/publish")
async def publish_content(content_id: str, db: AsyncSession = Depends(get_db)):
    """Mark content as published (actual platform API publishing in future)."""
    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    piece.status = "published"
    piece.published_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    return {"id": piece.id, "status": "published"}


@router.post("/{content_id}/schedule")
async def schedule_content(content_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    """Schedule content for future publishing."""
    scheduled = data.get("scheduled_at", "")
    if not scheduled:
        raise HTTPException(status_code=400, detail="scheduled_at is required")

    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    piece.status = "scheduled"
    piece.scheduled_at = scheduled
    await db.commit()
    return {"id": piece.id, "status": "scheduled", "scheduled_at": scheduled}


@router.get("/calendar")
async def content_calendar(
    week_start: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get content calendar for a week."""
    query = select(ContentPiece).where(
        ContentPiece.status.in_(["scheduled", "published"])
    ).order_by(ContentPiece.scheduled_at)

    result = await db.execute(query)
    items = result.scalars().all()

    # Group by date
    calendar = {}
    for c in items:
        date_key = (c.scheduled_at or c.published_at or str(c.created_at))[:10]
        if date_key not in calendar:
            calendar[date_key] = []
        calendar[date_key].append({
            "id": c.id,
            "title": c.title,
            "platform": c.platform,
            "platform_display": PIATFORM_DISPLAY.get(c.platform, c.platform),
            "status": c.status,
            "body": c.body or "",
            "language": c.language,
            "created_at": str(c.created_at) if c.created_at else "",
        })


@router.get("/platforms")
async def list_platforms():
    """List available social media platforms."""
    return {
        "platforms": [
            {"id": "linkedin", "name": "LinkedIn", "region": "Global", "language": "en"},
            {"id": "twitter", "name": "Twitter/X", "region": "Global", "language": "en"},
            {"id": "youtube", "name": "YouTube", "region": "Global", "language": "en"},
            {"id": "pinterest", "name": "Pinterest", "region": "Global", "language": "en"},
            {"id": "tiktok", "name": "TikTok", "region": "Global", "language": "en"},
            {"id": "facebook", "name": "Facebook", "region": "Global", "language": "en"},
            {"id": "red", "name": "小红书 RED", "region": "China", "language": "zh"},
            {"id": "douyin", "name": "抖音 Douyin", "region": "China", "language": "zh"},
            {"id": "wechat_article", "name": "微信 公众号", "region": "China", "language": "zh"},
            {"id": "wechat_moment", "name": "微信 朋友圈", "region": "China", "language": "zh"},
        ]
    }
