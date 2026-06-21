"""Daily RED auto-publish task — respects auto-settings (time, count, enabled)."""
import asyncio
import json
import os
import random
from datetime import datetime, timezone
from backend.services.content_generator import ContentGenerator
from backend.services.social_publisher import publisher as red_publisher
from backend.database import async_session_maker
from backend.models.content_piece import ContentPiece
from backend.routers.content_media import _embed_factory_images, _load_red_settings

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "red_auto_settings.json")

RED_TOPICS = [
    "PP hollow board packaging advantages for e-commerce",
    "Why plastic corrugated sheets beat cardboard for export packaging",
    "Factory tour: How PP hollow boards are made in Xiamen",
    "Sustainable packaging trends 2025 — PP hollow board solutions",
    "Custom PP corrugated boxes for electronics protection",
    "Lightweight vs durable: The PP hollow board advantage",
    "How European importers save on shipping with PP hollow sheets",
    "Eco-friendly packaging materials — PP hollow board deep dive",
    "Behind the scenes at TXD CO., LTD packaging factory",
    "PP hollow board applications you haven't thought of",
]


async def generate_and_publish_red():
    """Generate + publish RED notes based on auto-settings.
    Called every 30 min by scheduler but only runs if current hour matches setting."""
    settings = _load_red_settings()

    if not settings.get("enabled", False):
        return  # Disabled — silent skip

    # Check if current hour matches configured publish time (±30 min window)
    publish_time = settings.get("publish_time", "09:00")
    now = datetime.now(timezone.utc)
    # Convert UTC to Beijing time for comparison
    beijing_hour = (now.hour + 8) % 24
    beijing_minute = now.minute
    try:
        target_h, target_m = map(int, publish_time.split(":"))
    except ValueError:
        target_h, target_m = 9, 0

    # Only run within 30 min of target time
    current_minutes = beijing_hour * 60 + beijing_minute
    target_minutes = target_h * 60 + target_m
    if abs(current_minutes - target_minutes) > 30:
        return  # Not time yet — silent skip

    daily_count = settings.get("daily_count", 1)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check how many published today
    async with async_session_maker() as db:
        from sqlalchemy import select, func
        result = await db.execute(
            select(func.count()).select_from(ContentPiece).where(
                ContentPiece.platform == "red",
                ContentPiece.status == "published",
                ContentPiece.published_at >= today,
            )
        )
        published_today = result.scalar() or 0

    remaining = daily_count - published_today
    if remaining <= 0:
        print(f"[RedDaily] Already published {published_today} today (limit: {daily_count})")
        return

    # Check login
    state_path = red_publisher.user_data / "red_state.json"
    logged_in = state_path.exists()
    if not logged_in:
        print("[RedDaily] Not logged in — generating draft only")

    # Pick random topics
    chosen_topics = random.sample(RED_TOPICS, min(remaining, len(RED_TOPICS)))
    generator = ContentGenerator()

    for idx, topic in enumerate(chosen_topics):
        print(f"[RedDaily] Generating ({idx + 1}/{len(chosen_topics)}): {topic[:50]}")
        result = await generator.generate_for_platform(topic, "red")
        body = _embed_factory_images(result.get("body", ""))
        title = result.get("title", topic)[:300]

        async with async_session_maker() as db:
            piece = ContentPiece(
                title=title, platform="red", content_type="post",
                status="draft", body=body, media_urls=json.dumps([]), language="en",
            )
            db.add(piece)
            await db.commit()

            if logged_in:
                print(f"[RedDaily] Auto-publishing...")
                pub_result = await red_publisher.publish(title=title, body=body, headless=True)
                if pub_result.get("success"):
                    piece.status = "published"
                    piece.published_at = datetime.now(timezone.utc).isoformat()
                    await db.commit()
                    print(f"[RedDaily] ✅ Published: {title[:50]}")
                else:
                    print(f"[RedDaily] Publish failed: {pub_result.get('message')}")
            else:
                print(f"[RedDaily] Saved as draft: {title[:50]}")


if __name__ == "__main__":
    asyncio.run(generate_and_publish_red())
