"""Social media publisher — browser automation for RED/Xiaohongshu posting."""
import asyncio
import os
import json
import shutil
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
        headless: bool = True,
    ) -> dict:
        """Publish a RED note with the given title and HTML body.
        Body may contain <img> tags with data: URIs which will be extracted and uploaded."""
        state_path = self.user_data / "red_state.json"
        if not state_path.exists():
            return {
                "success": False,
                "message": "Not logged in. Call /login first to authenticate.",
                "action": "login_required",
            }

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    storage_state=str(state_path),
                )
                page = await context.new_page()

                # Go to publish page
                await page.goto(RED_PUBLISH_URL, wait_until="networkidle", timeout=30000)

                # Check if still logged in
                current_url = page.url
                if "login" in current_url.lower():
                    await browser.close()
                    return {
                        "success": False,
                        "message": "Session expired. Call /login to re-authenticate.",
                        "action": "login_required",
                    }

                # Wait for the publish form to load
                await page.wait_for_timeout(2000)

                # Extract plain text from HTML body (strip tags) for RED's text editor
                import re
                plain_text = re.sub(r'<img\b[^>]*>', '', body)  # Remove img tags
                plain_text = re.sub(r'<[^>]+>', '', plain_text)  # Strip HTML tags
                plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

                # Try to fill the title
                title_inputs = page.locator('input[placeholder*="title"], input[placeholder*="标题"], [class*="title"] input')
                if await title_inputs.count() > 0:
                    await title_inputs.first.fill(title)
                    await page.wait_for_timeout(500)

                # Try to find and fill the content editor
                # RED uses a rich text editor — try multiple selectors
                editor_selectors = [
                    '[contenteditable="true"]',
                    '[class*="editor"]',
                    '[class*="content"] [contenteditable]',
                    '[class*="ql-editor"]',
                    'div[placeholder*="正文"]',
                    'div[placeholder*="content"]',
                ]
                editor = None
                for sel in editor_selectors:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        editor = el
                        break

                if editor:
                    await editor.click()
                    await page.wait_for_timeout(300)
                    # Type content (plain text, since rich paste is unreliable)
                    await editor.fill(plain_text)
                    await page.wait_for_timeout(1000)

                # Handle image uploads — extract data: URIs from body
                import base64
                import tempfile
                img_pattern = re.findall(r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>', body)
                if img_pattern:
                    # Find file upload input
                    upload_inputs = page.locator('input[type="file"]')
                    # Click upload button first if needed
                    upload_btns = page.locator('[class*="upload"], [class*="addImg"], button:has-text("图片"), span:has-text("添加图片")')
                    for i, (fmt, b64data) in enumerate(img_pattern):
                        try:
                            img_bytes = base64.b64decode(b64data)
                            ext = "png" if fmt.lower() == "png" else "jpg"
                            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
                            tmp.write(img_bytes)
                            tmp.close()
                            # Click upload button if exists
                            if await upload_btns.count() > 0:
                                await upload_btns.first.click()
                                await page.wait_for_timeout(500)
                            # Upload
                            if await upload_inputs.count() > 0:
                                await upload_inputs.first.set_input_files(tmp.name)
                                await page.wait_for_timeout(2000)
                            os.unlink(tmp.name)
                        except Exception as e:
                            print(f"[REDPublisher] Image upload {i} failed: {e}")

                # Wait a bit for images to process
                await page.wait_for_timeout(2000)

                # Click publish button
                publish_selectors = [
                    'button:has-text("发布")',
                    'button:has-text("Publish")',
                    '[class*="publish"] button',
                    'button[class*="submit"]',
                ]
                published = False
                for sel in publish_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_enabled():
                        await btn.click()
                        published = True
                        await page.wait_for_timeout(3000)
                        break

                if not published:
                    await browser.close()
                    return {
                        "success": False,
                        "message": "Could not find publish button. Page structure may have changed.",
                    }

                # Check for success
                await page.wait_for_timeout(2000)
                current_url = page.url
                success = "login" not in current_url.lower()

                await browser.close()
                return {
                    "success": success,
                    "message": "Published to RED" if success else "Publish may have failed — check RED manually",
                    "url": current_url if success else None,
                }

        except Exception as e:
            return {"success": False, "message": f"Publish error: {str(e)}"}

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
