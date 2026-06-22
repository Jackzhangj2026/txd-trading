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
        headless: bool = False,
    ) -> dict:
        """Publish to RED. Auto-login if needed (opens browser for QR scan)."""
        import re, base64, tempfile, time

        debug_dir = self.user_data / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

        state_path = self.user_data / "red_state.json"

        async def _shot(page, name):
            try: await page.screenshot(path=str(debug_dir / f"{name}_{int(time.time())}.png"))
            except: pass

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                # If logged in, restore state; otherwise fresh context
                if state_path.exists():
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 900},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        storage_state=str(state_path),
                    )
                else:
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 900},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    )

                page = await context.new_page()

                # Go to publish page
                await page.goto(RED_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                await _shot(page, "01_publish_page")

                # Auto-login if needed
                if "login" in page.url.lower():
                    print("[REDPublisher] Not logged in — opening login page. Please scan QR code...")
                    # Wait for user to scan QR and redirect
                    try:
                        await page.wait_for_url(
                            lambda url: "login" not in url.lower() and "creator" in url.lower(),
                            timeout=120000,
                        )
                        print("[REDPublisher] Login successful — saving session.")
                        await context.storage_state(path=str(state_path))
                        await page.wait_for_timeout(2000)
                    except PlaywrightTimeout:
                        await browser.close()
                        return {"success": False, "message": "Login timed out (120s). Scan QR code and try again.", "action": "login_required"}

                # Check again
                if "login" in page.url.lower():
                    await browser.close()
                    return {"success": False, "message": "Still on login page. Try again.", "action": "login_required"}

                # Step 2: Upload images (RED: images first, then text)
                img_pattern = re.findall(r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>', body)
                images_uploaded = 0

                if img_pattern:
                    # Find upload trigger — RED has various upload UIs
                    upload_triggers = [
                        'input[type="file"]',
                        '[class*="upload"] input[type="file"]',
                        '[class*="add"] input[type="file"]',
                        'input[accept*="image"]',
                    ]
                    # Try clicking upload area first
                    upload_areas = [
                        '[class*="upload"]',
                        '[class*="addPic"]',
                        'span:has-text("上传图片")',
                        'div:has-text("添加图片")',
                        '[class*="image-upload"]',
                    ]

                    for i, (fmt, b64data) in enumerate(img_pattern[:9]):  # RED max 9 images
                        try:
                            img_bytes = base64.b64decode(b64data)
                            ext = "png" if fmt.lower() == "png" else "jpg"
                            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
                            tmp.write(img_bytes)
                            tmp.close()

                            # Click upload area to trigger file dialog
                            clicked = False
                            for area_sel in upload_areas:
                                area = page.locator(area_sel).first
                                if await area.count() > 0:
                                    await area.click()
                                    await page.wait_for_timeout(800)
                                    clicked = True
                                    break

                            # Upload file
                            uploaded = False
                            for input_sel in upload_triggers:
                                file_input = page.locator(input_sel).first
                                if await file_input.count() > 0:
                                    await file_input.set_input_files(tmp.name)
                                    await page.wait_for_timeout(2000)
                                    uploaded = True
                                    images_uploaded += 1
                                    print(f"[REDPublisher] Image {i+1} uploaded: {tmp.name}")
                                    break

                            if not uploaded and not clicked:
                                # Last resort: try file chooser
                                file_chooser_promise = page.wait_for_event("filechooser", timeout=5000)
                                for area_sel in upload_areas:
                                    area = page.locator(area_sel).first
                                    if await area.count() > 0:
                                        await area.click()
                                        break
                                try:
                                    file_chooser = await file_chooser_promise
                                    await file_chooser.set_files(tmp.name)
                                    images_uploaded += 1
                                    print(f"[REDPublisher] Image {i+1} via filechooser")
                                except: pass

                            os.unlink(tmp.name)
                        except Exception as e:
                            print(f"[REDPublisher] Image {i+1} failed: {e}")

                    await page.wait_for_timeout(2000)
                    await _shot(page, "02_images_uploaded")

                # Step 3: Fill title
                title_selectors = [
                    'input[placeholder*="标题"]',
                    'input[placeholder*="title"]',
                    '[class*="title"] input',
                    'input[class*="title"]',
                    '[class*="publish"] input[type="text"]',
                ]
                title_filled = False
                for sel in title_selectors:
                    inp = page.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible():
                        await inp.click()
                        await page.wait_for_timeout(200)
                        await inp.fill("")
                        await inp.fill(title)
                        title_filled = True
                        print(f"[REDPublisher] Title filled via: {sel}")
                        break
                if not title_filled:
                    print("[REDPublisher] ⚠️ Title field not found")

                # Step 4: Fill content (plain text, strip HTML)
                plain_text = re.sub(r'<img\b[^>]*>', '', body)
                plain_text = re.sub(r'<[^>]+>', '', plain_text)
                plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

                content_selectors = [
                    '[contenteditable="true"]',
                    '[class*="ql-editor"]',
                    '[class*="editor"]',
                    'div[placeholder*="正文"]',
                    'div[placeholder*="content"]',
                    '[class*="note-content"]',
                    '[class*="rich-text"]',
                ]
                content_filled = False
                for sel in content_selectors:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await page.wait_for_timeout(300)
                        await el.fill(plain_text)
                        content_filled = True
                        print(f"[REDPublisher] Content filled via: {sel}")
                        break
                if not content_filled:
                    print("[REDPublisher] ⚠️ Content field not found")

                await page.wait_for_timeout(1000)
                await _shot(page, "03_content_filled")

                # Step 5: Click publish
                publish_selectors = [
                    'button:has-text("发布")',
                    'button:has-text("发布笔记")',
                    '[class*="publish"] button',
                    'button[class*="submit"]',
                    'button[class*="publish"]',
                    'span:has-text("发布")',
                ]
                published = False
                for sel in publish_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        is_enabled = await btn.is_enabled()
                        print(f"[REDPublisher] Publish btn '{sel}': enabled={is_enabled}")
                        if is_enabled:
                            await btn.click()
                            published = True
                            await page.wait_for_timeout(5000)
                            break

                await _shot(page, "04_after_publish")

                if not published:
                    # Dump page HTML for debugging
                    html_snippet = (await page.content())[:2000]
                    print(f"[REDPublisher] Page HTML: {html_snippet}")
                    await browser.close()
                    return {
                        "success": False,
                        "message": f"Could not publish. Uploaded {images_uploaded} images. Title: {title_filled}, Content: {content_filled}. Screenshots saved.",
                    }

                await browser.close()
                return {"success": True, "message": f"Published! ({images_uploaded} images)"}

        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

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
