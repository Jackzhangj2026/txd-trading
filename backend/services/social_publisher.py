"""Social media publisher — browser automation for RED/Xiaohongshu posting."""
import asyncio
import os
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Browser state dir for persistent login cookies
USER_DATA_DIR = Path(__file__).parent.parent.parent / "browser_data"
RED_CREATOR_URL = "https://creator.xiaohongshu.com"
RED_LOGIN_URL = "https://creator.xiaohongshu.com/login"
RED_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


class REDPublisher:
    """Publish content to Xiaohongshu (RED) via browser automation."""

    def __init__(self):
        self.user_data = USER_DATA_DIR
        self.user_data.mkdir(parents=True, exist_ok=True)

    async def login_and_save_state(self) -> dict:
        """Open browser, let user manually log in, save browser state.
        Returns {"success": bool, "message": str}"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Navigate to RED creator login
                await page.goto(RED_LOGIN_URL, wait_until="networkidle", timeout=30000)

                print("[REDPublisher] Browser opened. Please log in manually within 120 seconds.")

                # Wait for user to log in (check for redirect away from login)
                try:
                    await page.wait_for_url(
                        lambda url: "login" not in url.lower() and "creator" in url.lower(),
                        timeout=120000
                    )
                    print("[REDPublisher] Login detected — saving browser state.")
                    # Save storage state (cookies, localStorage)
                    state_path = self.user_data / "red_state.json"
                    await context.storage_state(path=str(state_path))
                    await browser.close()
                    return {"success": True, "message": "Login saved successfully"}
                except PlaywrightTimeout:
                    await browser.close()
                    return {"success": False, "message": "Login timed out (120s). Please try again."}

        except Exception as e:
            return {"success": False, "message": f"Browser error: {str(e)}"}

    async def publish(
        self,
        title: str,
        body: str,
        tags: list[str] | None = None,
        headless: bool = False,
    ) -> dict:
        """Auto-fill RED editor, leave browser open for user to click publish."""
        import subprocess as _sp, json as _json

        script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "tasks", "red_publish_standalone.py"
        ))
        payload_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "browser_data", "red_payload.json"
        ))
        os.makedirs(os.path.dirname(payload_file), exist_ok=True)

        # Strip image captions from body
        import re
        cleaned = re.sub(r'<img[^>]*>', '', body)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        lines = [l.strip() for l in cleaned.split('\n') if l.strip()
                 and not re.match(r'^(photo|image|picture|▲|△)\s*\d*', l.strip(), re.I)]

        with open(payload_file, "w", encoding="utf-8") as f:
            _json.dump({"title": title[:20], "body": body}, f)

        def _run():
            return _sp.run([sys.executable, script], capture_output=True, text=True,
                          timeout=360, cwd=os.path.dirname(script))

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _run)
            for line in (result.stdout or "").split("\n"):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try: return _json.loads(line)
                    except: pass
            return {"success": True, "message": "Check browser window"}
        except _sp.TimeoutExpired:
            return {"success": True, "message": "Browser still open — click publish"}
        except Exception as e:
            return {"success": False, "message": f"Error: {e}"}


    async def copy_content(self, content_id: str, db) -> dict:
        """Prepare content for manual copy/paste.
        Returns the HTML body that user can copy."""
        from backend.models.content_piece import ContentPiece
        from sqlalchemy import select

        result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
        piece = result.scalar_one_or_none()
        if not piece:
            return {"success": False, "message": "Content not found"}

        return {
            "success": True,
            "id": piece.id,
            "title": piece.title,
            "body": piece.body,
            "platform": piece.platform,
        }


# Singleton
publisher = REDPublisher()
