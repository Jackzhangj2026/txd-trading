"""Social media content API — generate, queue, schedule, publish."""

import json
import os
import random
import base64
import io
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


FACTORY_IMAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "factory image")


def _embed_factory_images(body: str, max_images: int = 4) -> str:
    """Ensure real factory images are embedded in the body as base64 <img> tags.
    If {{image_N}} placeholders exist, replace them. Otherwise, auto-inject images
    after the first paragraph and before the last paragraph."""
    import re
    from PIL import Image

    # Find available factory images
    img_dir = os.path.normpath(FACTORY_IMAGE_DIR)
    if not os.path.isdir(img_dir):
        return body

    all_imgs = [f for f in os.listdir(img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    if not all_imgs:
        return body

    def _make_img_tag(filename: str, idx: int) -> str:
        img_path = os.path.join(img_dir, filename)
        try:
            img = Image.open(img_path)
            w, h = img.size
            if w > 600:
                ratio = 600 / w
                img = img.resize((600, int(h * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            if img.format and img.format.upper() in ('PNG', 'WEBP'):
                img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=60, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return f'<img src="data:image/jpeg;base64,{b64}" alt="Product Image {idx}" style="max-width:100%;border-radius:12px;margin:12px 0;display:block;">'
        except Exception as e:
            print(f"[ContentMedia] Image embed failed for {filename}: {e}")
            return ""

    # Strategy 1: Replace {{image_N}} placeholders
    placeholders = re.findall(r'\{\{image_(\d+)\}\}', body)
    if placeholders:
        chosen = random.sample(all_imgs, min(len(placeholders), len(all_imgs)))
        for i, filename in enumerate(chosen):
            placeholder = f"{{image_{i + 1}}}"
            if placeholder in body:
                tag = _make_img_tag(filename, i + 1)
                if tag:
                    body = body.replace(placeholder, tag)
        return body

    # Strategy 2: No placeholders — auto-inject images into HTML structure
    # Find <p> tags to insert images between them
    paras = list(re.finditer(r'<p\b[^>]*>.*?</p>', body, re.DOTALL))
    if len(paras) < 2:
        # Too few paragraphs, just append images at the end
        chosen = random.sample(all_imgs, min(max_images, len(all_imgs)))
        tags = []
        for i, fn in enumerate(chosen):
            tag = _make_img_tag(fn, i + 1)
            if tag:
                tags.append(f'<p style="text-align:center;color:#999;font-size:13px;">▲ Product photo {i + 1}</p>{tag}')
        if tags:
            body += "\n" + "\n".join(tags)
        return body

    # Insert images: 1 after first paragraph, rest before last paragraph
    chosen = random.sample(all_imgs, min(max_images, len(all_imgs)))
    result_parts = []
    # Everything before first paragraph
    result_parts.append(body[:paras[0].start()])
    # First paragraph
    result_parts.append(body[paras[0].start():paras[0].end()])
    # First image after first paragraph
    if len(chosen) >= 1:
        tag = _make_img_tag(chosen[0], 1)
        if tag:
            result_parts.append(f'\n<p style="text-align:center;color:#999;font-size:13px;margin-top:8px;">▲ Product photo 1</p>\n{tag}\n')

    # Middle paragraphs (between first and last)
    for p in paras[1:-1]:
        result_parts.append(body[p.start():p.end()])

    # More images before last paragraph
    for i in range(1, min(len(chosen), 3)):
        tag = _make_img_tag(chosen[i], i + 1)
        if tag:
            result_parts.append(f'\n<p style="text-align:center;color:#999;font-size:13px;margin-top:8px;">▲ Product photo {i + 1}</p>\n{tag}\n')

    # Remaining images (4th)
    if len(chosen) >= 4:
        tag = _make_img_tag(chosen[3], 4)
        if tag:
            result_parts.append(f'\n<p style="text-align:center;color:#999;font-size:13px;margin-top:8px;">▲ Product photo 4</p>\n{tag}\n')

    # Last paragraph + everything after
    result_parts.append(body[paras[-1].start():])
    return "".join(result_parts)


# ─── RED Auto-Publish Settings ──────────────────────────────────

RED_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "red_auto_settings.json")


def _load_red_settings() -> dict:
    if not os.path.exists(RED_SETTINGS_FILE):
        return {"enabled": False, "publish_time": "09:00", "daily_count": 1}
    with open(RED_SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_red_settings(settings: dict):
    os.makedirs(os.path.dirname(RED_SETTINGS_FILE), exist_ok=True)
    with open(RED_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


@router.get("/red-settings")
async def get_red_settings():
    """Get RED auto-publish settings."""
    settings = _load_red_settings()
    state_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "browser_data", "red_state.json"
    )
    settings["logged_in"] = os.path.exists(state_path)
    return settings


@router.put("/red-settings")
async def update_red_settings(data: dict):
    """Update RED auto-publish settings."""
    settings = _load_red_settings()
    for key in ("enabled", "publish_time", "daily_count"):
        if key in data:
            settings[key] = data[key]
    _save_red_settings(settings)
    state_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "browser_data", "red_state.json"
    )
    settings["logged_in"] = os.path.exists(state_path)
    return settings


@router.post("/red-publish-now")
async def red_publish_now():
    """Generate one RED note + auto-publish via Playwright."""
    from backend.services.social_publisher import publisher
    from backend.services.content_generator import ContentGenerator
    from backend.models.content_piece import ContentPiece
    from backend.database import async_session

    # Generate content
    topics = [
        "PP hollow board packaging advantages for e-commerce",
        "Custom PP corrugated boxes for electronics protection",
        "Sustainable packaging trends 2025 — PP hollow board solutions",
        "Factory tour: How PP hollow boards are made",
        "Why plastic corrugated sheets beat cardboard for export packaging",
    ]
    import random
    topic = random.choice(topics)

    generator = ContentGenerator()
    result = await generator.generate_for_platform(topic, "red")
    body = _embed_factory_images(result.get("body", ""))
    title = result.get("title", topic)[:300]

    # Publish (auto-login if needed)
    pub_result = await publisher.publish(title=title, body=body, headless=False)

    # Publish
    pub_result = await publisher.publish(title=title, body=body, headless=False)

    # Save to DB
    async with async_session() as db:
        piece = ContentPiece(
            title=title, platform="red", content_type="post",
            status="published" if pub_result.get("success") else "draft",
            body=body, media_urls=json.dumps([]), language="en",
        )
        if pub_result.get("success"):
            piece.published_at = datetime.now(timezone.utc).isoformat()
        db.add(piece)
        await db.commit()

    return {
        "success": pub_result.get("success", False),
        "message": pub_result.get("message", ""),
        "title": title,
    }


# ─── RED Auto-Publish + Manual Copy ──────────────────────────────

@router.post("/red-login")
async def red_login():
    """Open browser for manual RED creator login. Saves browser state for auto-publish."""
    from backend.services.social_publisher import publisher
    result = await publisher.login_and_save_state()
    return result


@router.post("/{content_id}/publish-to-red")
async def publish_to_red(
    content_id: str,
    headless: bool = Query(True, description="Run browser headless"),
    db: AsyncSession = Depends(get_db),
):
    """Auto-publish a content piece to RED via browser automation."""
    from backend.services.social_publisher import publisher
    from backend.models.content_piece import ContentPiece

    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Content not found")

    pub_result = await publisher.publish(
        title=piece.title,
        body=piece.body or "",
        headless=headless,
    )

    if pub_result.get("success"):
        piece.status = "published"
        piece.published_at = datetime.now(timezone.utc).isoformat()
        await db.commit()

    return pub_result


@router.get("/{content_id}/copy")
async def get_copy_content(content_id: str, db: AsyncSession = Depends(get_db)):
    """Get content + extract images to files for manual RED publishing."""
    import re, base64 as _b64

    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Not found")

    body = piece.body or ""

    # Extract base64 images and save to export folder
    export_dir = os.path.join(os.path.dirname(__file__), "..", "..", "browser_data", "red_export")
    os.makedirs(export_dir, exist_ok=True)
    for old in os.listdir(export_dir):
        if old.startswith("red_img_"):
            try: os.remove(os.path.join(export_dir, old))
            except: pass

    img_idx = 1
    def save_img(m):
        nonlocal img_idx
        fmt = m.group(1) or "jpeg"
        b64data = m.group(2)
        ext = "png" if fmt.lower() == "png" else "jpg"
        fname = f"red_img_{img_idx}.{ext}"
        fpath = os.path.join(export_dir, fname)
        try:
            with open(fpath, "wb") as f:
                f.write(_b64.b64decode(b64data))
            img_idx += 1
            return f'<img src="file:///{fpath.replace(chr(92), "/")}" alt="Product {img_idx - 1}" style="max-width:100%;border-radius:12px;margin:12px 0;display:block;">'
        except:
            img_idx += 1
            return m.group(0)

    body_with_local = re.sub(r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>', save_img, body)

    plain_text = re.sub(r'<img\b[^>]*>', '[Image]', body_with_local)
    plain_text = re.sub(r'<[^>]+>', '', plain_text)
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

    return {
        "success": True, "id": piece.id, "title": piece.title,
        "body": body_with_local, "plain_text": plain_text,
        "platform": piece.platform, "images_saved": img_idx - 1,
        "export_dir": export_dir.replace("\\", "/"),
    }


@router.post("/open-red-export")
async def open_red_export():
    """Open the RED image export folder in Windows Explorer."""
    import subprocess
    export_dir = os.path.join(os.path.dirname(__file__), "..", "..", "browser_data", "red_export")
    os.makedirs(export_dir, exist_ok=True)
    try:
        subprocess.Popen(["explorer", os.path.abspath(export_dir)])
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ─── RED Auto-Publish + Manual Copy ──────────────────────────────


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
        body = _embed_factory_images(result.get("body", ""))

        piece = ContentPiece(
            title=result.get("title", data.topic)[:300],
            content_type="post" if platform in ("linkedin", "twitter", "facebook", "pinterest") else "script",
            platform=platform,
            status="draft",
            body=body,
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
                "published_at": c.published_at or "",
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
