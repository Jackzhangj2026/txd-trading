"""Daily RED auto-publish task — generates and optionally publishes content."""
import asyncio
import json
import os
from datetime import datetime, timezone
from backend.services.content_generator import ContentGenerator
from backend.services.social_publisher import publisher as red_publisher
from backend.database import async_session_maker
from backend.models.content_piece import ContentPiece

# Topics to rotate through
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
    """Generate one RED note and optionally auto-publish it."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check if already generated today
    async with async_session_maker() as db:
        from sqlalchemy import select, func
        result = await db.execute(
            select(func.count()).select_from(ContentPiece).where(
                ContentPiece.platform == "red",
                ContentPiece.created_at >= today,
            )
        )
        if result.scalar() > 0:
            print(f"[RedDaily] Already generated RED content today ({today})")
            return

    # Pick topic based on day of month
    day = datetime.now().day
    topic = RED_TOPICS[day % len(RED_TOPICS)]

    print(f"[RedDaily] Generating RED note for: {topic}")

    generator = ContentGenerator()
    result = await generator.generate_for_platform(topic, "red")

    body = result.get("body", "")
    title = result.get("title", topic)

    # Embed factory images
    from backend.routers.content_media import _embed_factory_images
    body = _embed_factory_images(body)

    # Save as draft
    async with async_session_maker() as db:
        piece = ContentPiece(
            title=title[:300],
            platform="red",
            content_type="post",
            status="draft",
            body=body,
            media_urls=json.dumps([]),
            language="en",
        )
        db.add(piece)
        await db.commit()
        print(f"[RedDaily] RED note saved: {title[:60]}")

        # Auto-publish if login state exists
        state_path = red_publisher.user_data / "red_state.json"
        if state_path.exists():
            print("[RedDaily] Login state found — attempting auto-publish...")
            pub_result = await red_publisher.publish(
                title=title,
                body=body,
                headless=True,
            )
            if pub_result.get("success"):
                piece.status = "published"
                piece.published_at = datetime.now(timezone.utc).isoformat()
                await db.commit()
                print("[RedDaily] ✅ Auto-published to RED!")
            else:
                print(f"[RedDaily] Auto-publish failed: {pub_result.get('message')}")
        else:
            print("[RedDaily] No login state — saved as draft. Use '🔑 Login RED' then '🚀 Auto' to publish.")


if __name__ == "__main__":
    asyncio.run(generate_and_publish_red())
