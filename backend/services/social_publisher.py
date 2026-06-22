"""Social media publisher — browser automation for RED/Xiaohongshu posting."""
import asyncio
import os
import sys
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
        """Publish via standalone subprocess (avoids event loop conflicts)."""
        import subprocess, json as _json

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "tasks", "red_publish_standalone.py"
        )
        payload_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "browser_data", "red_payload.json"
        )
        os.makedirs(os.path.dirname(payload_file), exist_ok=True)
        with open(payload_file, "w", encoding="utf-8") as f:
            _json.dump({"title": title, "body": body}, f)

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, os.path.abspath(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=150.0)

            if stderr:
                print(f"[REDPublisher stderr] {stderr.decode('utf-8', errors='replace')[:500]}")

            output = stdout.decode("utf-8", errors="replace").strip()
            # Find JSON in output (might have print() noise before it)
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return _json.loads(line)
                    except: pass

            if output:
                try:
                    return _json.loads(output.split("\n")[-1])
                except: pass

            return {"success": False, "message": f"Subprocess: {output[:200] or 'no output'}"}

        except asyncio.TimeoutError:
            return {"success": False, "message": "Publish timed out (150s)"}
        except Exception as e:
            return {"success": False, "message": f"Subprocess error: {e}"}

    # Legacy async publish kept for reference
    async def _publish_direct(self, title, body, headless=False):

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
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
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

                # Step 2: Dismiss any overlay/mask/popup
                mask_selectors = [
                    '[class*="mask"]', '[class*="overlay"]', '[class*="modal"]',
                    '[class*="dialog"]', '[class*="popup"]', '[class*="tip"]',
                    'button:has-text("知道了")', 'button:has-text("确定")',
                    'button:has-text("OK")', 'button:has-text("Got it")',
                    '[class*="close"]', 'button:has-text("跳过")',
                ]
                for mask_sel in mask_selectors:
                    try:
                        masks = page.locator(mask_sel)
                        count = await masks.count()
                        for mi in range(count):
                            m = masks.nth(mi)
                            if await m.is_visible():
                                await m.click(timeout=2000)
                                await page.wait_for_timeout(500)
                                print(f"[REDPublisher] Dismissed: {mask_sel}")
                    except: pass

                # Step 3: Upload images
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

                # Step 3: Fill title — try every visible text input
                title_filled = False
                all_inputs = page.locator('input:visible')
                input_count = await all_inputs.count()
                for i in range(min(input_count, 20)):
                    inp = all_inputs.nth(i)
                    try:
                        inp_type = await inp.get_attribute('type') or 'text'
                        if inp_type in ('text', 'search', '') and not title_filled:
                            await inp.click()
                            await page.wait_for_timeout(100)
                            await inp.fill('')
                            await inp.fill(title)
                            title_filled = True
                            print(f"[REDPublisher] Title filled in input #{i}")
                    except: pass
                if not title_filled:
                    print("[REDPublisher] WARNING: No title input found")

                # Step 4: Fill content — plain text, strip HTML
                plain_text = re.sub(r'<img\b[^>]*>', '', body)
                plain_text = re.sub(r'<[^>]+>', '', plain_text)
                plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

                content_filled = False
                editables = page.locator('[contenteditable="true"]:visible')
                editable_count = await editables.count()
                for i in range(min(editable_count, 10)):
                    el = editables.nth(i)
                    try:
                        await el.click()
                        await page.wait_for_timeout(200)
                        await el.fill(plain_text)
                        content_filled = True
                        print(f"[REDPublisher] Content filled in editable #{i}")
                        break
                    except: pass
                if not content_filled:
                    print("[REDPublisher] WARNING: No editable content area found")

                await page.wait_for_timeout(1000)
                await _shot(page, "03_content_filled")

                # Step 6: Click publish — force click via JS to bypass mask
                published = False
                # Try to find the publish button text
                publish_texts = ['发布', '发布笔记', 'Publish', '提交']
                for pt in publish_texts:
                    btn = page.locator(f'text="{pt}"').last
                    if await btn.count() > 0 and await btn.is_visible():
                        try:
                            # Force click via JS to bypass mask overlays
                            await btn.evaluate('el => el.click()')
                            published = True
                            print(f"[REDPublisher] Published via JS click on '{pt}'")
                            await page.wait_for_timeout(5000)
                            break
                        except Exception as e:
                            print(f"[REDPublisher] Click failed: {e}")

                if not published:
                    # Last resort: find any button-like element
                    btns = page.locator('button, [role="button"], span[class*="btn"]')
                    btn_count = await btns.count()
                    for i in range(min(btn_count, 30)):
                        b = btns.nth(i)
                        try:
                            text = (await b.text_content() or '').strip()
                            if text and len(text) < 10:
                                print(f"[REDPublisher] Button #{i}: '{text}'")
                            if any(pt in (text or '') for pt in publish_texts):
                                await b.evaluate('el => el.click()')
                                published = True
                                print(f"[REDPublisher] Published via button #{i}: '{text}'")
                                await page.wait_for_timeout(5000)
                                break
                        except: pass

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
            import traceback
            tb = traceback.format_exc()
            print(f"[REDPublisher] ERROR: {tb}")
            return {"success": False, "message": f"Error: {type(e).__name__}: {str(e) or repr(e)}"}

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
