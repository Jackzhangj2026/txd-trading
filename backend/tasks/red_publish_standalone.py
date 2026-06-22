# -*- coding: utf-8 -*-
"""RED auto-publish standalone — login → click 写长文 → 新的创作 → fill → upload images → publish."""
import sys, os, json, asyncio, re, base64, tempfile
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

RED_URL = "https://creator.xiaohongshu.com/publish/publish"
BASE = Path(__file__).parent.parent.parent / "browser_data"
STATE = BASE / "red_state.json"
DEBUG = BASE / "debug"
PAYLOAD = BASE / "red_payload.json"
DEBUG.mkdir(parents=True, exist_ok=True)
BASE.mkdir(parents=True, exist_ok=True)


async def shot(page, name):
    try: await page.screenshot(path=str(DEBUG / f"{name}.png"))
    except: pass


async def click_by_text(page, text):
    """Click first visible element with exact text using JS evaluate."""
    return await page.evaluate("""
        ([text]) => {
            const all = document.querySelectorAll('span, div, button, a');
            for (const el of all) {
                if (el.textContent.trim() === text && el.offsetParent !== null) {
                    el.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }
    """, [text])


async def main():
    # Load payload
    if not PAYLOAD.exists():
        print(json.dumps({"success": False, "message": "No payload file"}))
        return
    with open(PAYLOAD, "r", encoding="utf-8") as f:
        payload = json.load(f)
    title = payload.get("title", "Test")
    body = payload.get("body", "<p>Test content</p>")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=str(STATE) if STATE.exists() else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await ctx.new_page()

        try:
            # 1. Navigate
            await page.goto(RED_URL, timeout=30000)
            await page.wait_for_timeout(8000)
            await shot(page, "00_page_loaded")

            # 2. Login if needed
            if "login" in page.url.lower():
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=180000)
                await ctx.storage_state(path=str(STATE))
                await page.wait_for_timeout(5000)

            if "login" in page.url.lower():
                print(json.dumps({"success": False, "message": "Login failed"}))
                return

            # 3. Click "写长文" tab
            r = await click_by_text(page, "写长文")
            if r != "clicked":
                # Dump page text for debugging
                all_text = await page.evaluate("""() => {
                    const spans = document.querySelectorAll('span, div, button, a');
                    const found = [];
                    for (const el of spans) {
                        const t = el.textContent.trim();
                        if (t && t.length >= 2 && t.length <= 15 && el.offsetParent !== null) {
                            found.push(t);
                        }
                    }
                    return [...new Set(found)].slice(0, 30);
                }""")
                print(f"  Page text: {all_text}", file=sys.stderr)
                await shot(page, "error_write_long_not_found")
                print(json.dumps({"success": False, "message": f"写长文 not found. Page texts: {all_text[:10]}"}))
                return
            await page.wait_for_timeout(3000)

            # 4. Click "新的创作" button
            r = await click_by_text(page, "新的创作")
            if r != "clicked":
                print(json.dumps({"success": False, "message": "新的创作 button not found"}))
                return
            await page.wait_for_timeout(5000)

            # 5. Wait for editor
            await page.wait_for_timeout(3000)
            try:
                await page.wait_for_selector('input:visible, [contenteditable="true"]:visible', timeout=20000)
            except PWTimeout:
                print(json.dumps({"success": False, "message": "Editor did not load"}))
                return
            await shot(page, "editor_loaded")

            # 6. Fill title
            for i in range(min(await page.locator('input:visible').count(), 10)):
                try:
                    el = page.locator('input:visible').nth(i)
                    ph = (await el.get_attribute('placeholder') or '')
                    if '标题' in ph or 'title' in ph.lower() or (not ph and i == 0):
                        await el.fill(title)
                        break
                except: pass

            # 7. Fill content (plain text)
            plain = re.sub(r'<img[^>]*>', '', body)
            plain = re.sub(r'<[^>]+>', '', plain).strip()
            editable = page.locator('[contenteditable="true"]:visible').first
            if await editable.count() > 0:
                await editable.fill(plain)
                await page.wait_for_timeout(1000)

            # 8. Upload images
            imgs = re.findall(r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>', body)
            if imgs:
                print(f"  Uploading {len(imgs)} images...")
                await shot(page, "before_images")

                # Debug: find all file inputs on page
                fi_count = await page.locator('input[type="file"]').count()
                print(f"  File inputs on page: {fi_count}")
                if fi_count == 0:
                    # Check for any input
                    all_in = await page.locator('input').count()
                    print(f"  All inputs: {all_in}")
                    # Dump first 5 input details
                    for j in range(min(all_in, 5)):
                        try:
                            inp = page.locator('input').nth(j)
                            tp = await inp.get_attribute('type') or ''
                            cl = (await inp.get_attribute('class') or '')[:50]
                            print(f"    Input #{j}: type={tp} class={cl}")
                        except: pass

                for i, (fmt, b64) in enumerate(imgs[:9]):
                    uploaded = False
                    try:
                        data = base64.b64decode(b64)
                        ext = "png" if fmt.lower() == "png" else "jpg"
                        tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
                        tmp.write(data); tmp.close()

                        # Strategy 1: Find ANY file input (visible or hidden)
                        all_inputs = page.locator('input[type="file"]')
                        if await all_inputs.count() > 0:
                            await all_inputs.first.set_input_files(tmp.name)
                            print(f"  Image {i+1}/{len(imgs)} uploaded via file input")
                            await page.wait_for_timeout(1500)
                            uploaded = True

                        # Strategy 2: Click toolbar then upload
                        if not uploaded:
                            for img_sel in ['[class*="image"]', '[class*="img"]', '[class*="pic"]', '[class*="upload"]']:
                                btn = page.locator(img_sel).first
                                if await btn.count() > 0 and await btn.is_visible():
                                    await btn.click(); await page.wait_for_timeout(500)
                                    fi = page.locator('input[type="file"]').first
                                    if await fi.count() > 0:
                                        await fi.set_input_files(tmp.name)
                                        print(f"  Image {i+1} via {img_sel}")
                                        await page.wait_for_timeout(1500)
                                        uploaded = True
                                        break

                        # Strategy 3: File chooser event
                        if not uploaded:
                            try:
                                async with page.expect_file_chooser(timeout=3000) as fc_info:
                                    ed = page.locator('[contenteditable="true"]:visible').first
                                    if await ed.count() > 0: await ed.click()
                                fc = await fc_info.value
                                await fc.set_files(tmp.name)
                                print(f"  Image {i+1} via filechooser")
                                await page.wait_for_timeout(1500)
                                uploaded = True
                            except: pass

                        if not uploaded:
                            print(f"  Image {i+1}: no method worked")
                        os.unlink(tmp.name)
                    except Exception as e:
                        print(f"  Image {i+1} error: {e}")
                        try: os.unlink(tmp.name)
                        except: pass

            await page.wait_for_timeout(2000)
            await shot(page, "filled")

            # 9. Click publish
            for pub_text in ['发布', '发布笔记']:
                r = await click_by_text(page, pub_text)
                if r == "clicked":
                    await page.wait_for_timeout(5000)
                    await shot(page, "published")
                    print(json.dumps({"success": True, "message": f"Published via '{pub_text}'"}))
                    break
            else:
                print(json.dumps({"success": False, "message": "Publish button not found"}))

        except Exception as e:
            print(json.dumps({"success": False, "message": f"{type(e).__name__}: {e}"}))
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
