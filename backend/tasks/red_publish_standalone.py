"""Standalone RED publish script — runs in subprocess to avoid event loop conflicts."""
import sys, json, os, asyncio, re, base64, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

RED_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"
USER_DATA_DIR = Path(__file__).parent.parent / "browser_data"
DEBUG_DIR = USER_DATA_DIR / "debug"
STATE_PATH = USER_DATA_DIR / "red_state.json"


async def main():
    # Read payload from temp file
    payload_file = os.path.join(os.path.dirname(__file__), "..", "..", "browser_data", "red_payload.json")
    if not os.path.exists(payload_file):
        print(json.dumps({"success": False, "message": "No payload file"}))
        return
    with open(payload_file, "r", encoding="utf-8") as f:
        args = json.load(f)
    title = args.get("title", "Test")
    body = args.get("body", "<p>Test</p>")

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    async def shot(page, name):
        try: await page.screenshot(path=str(DEBUG_DIR / f"{name}.png"))
        except: pass

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )

            if STATE_PATH.exists():
                ctx = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    storage_state=str(STATE_PATH),
                )
            else:
                ctx = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )

            page = await ctx.new_page()
            await page.goto(RED_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            await shot(page, "01_page")

            # Auto-login
            if "login" in page.url.lower():
                print("[RED] Waiting for QR scan (120s)...")
                try:
                    await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=120000)
                    await ctx.storage_state(path=str(STATE_PATH))
                    print("[RED] Login saved, navigating to publish page...")
                    # After login, explicitly go to publish page
                    await page.goto(RED_PUBLISH_URL, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                    await shot(page, "01b_after_login")
                except PlaywrightTimeout:
                    print(json.dumps({"success": False, "message": "QR scan timeout (120s)"}))
                    await browser.close()
                    return

            # If still on login page after redirect attempt
            if "login" in page.url.lower():
                print(json.dumps({"success": False, "message": "Login failed"}))
                await browser.close()
                return

            await page.wait_for_timeout(2000)

            # Dismiss masks
            for mask_sel in ['[class*="mask"]', '[class*="overlay"]', 'button:has-text("知道了")', 'button:has-text("跳过")']:
                try:
                    masks = page.locator(mask_sel)
                    for mi in range(min(await masks.count(), 5)):
                        m = masks.nth(mi)
                        if await m.is_visible(): await m.click(timeout=1000)
                except: pass

            # Upload images
            imgs = re.findall(r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>', body)
            for i, (fmt, b64) in enumerate(imgs[:9]):
                try:
                    data = base64.b64decode(b64)
                    ext = "png" if fmt.lower() == "png" else "jpg"
                    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
                    tmp.write(data); tmp.close()
                    try:
                        fc = await page.wait_for_event("filechooser", timeout=3000)
                        await fc.set_files(tmp.name)
                    except:
                        # Try clicking upload trigger
                        for us in ['[class*="upload"]', 'span:has-text("上传")', 'div:has-text("添加图片")']:
                            u = page.locator(us).first
                            if await u.count() > 0 and await u.is_visible():
                                await u.click(); break
                        await page.wait_for_timeout(500)
                        file_input = page.locator('input[type="file"]').first
                        if await file_input.count() > 0:
                            await file_input.set_input_files(tmp.name)
                    os.unlink(tmp.name)
                    await page.wait_for_timeout(1000)
                except: pass

            await shot(page, "02_uploaded")

            # Fill title
            for i in range(min(await page.locator('input:visible').count(), 20)):
                inp = page.locator('input:visible').nth(i)
                try:
                    tp = await inp.get_attribute('type') or 'text'
                    if tp in ('text', 'search', ''):
                        await inp.fill(title)
                        break
                except: pass

            # Fill content
            plain = re.sub(r'<img[^>]*>', '', body)
            plain = re.sub(r'<[^>]+>', '', plain).strip()
            for i in range(min(await page.locator('[contenteditable="true"]:visible').count(), 10)):
                el = page.locator('[contenteditable="true"]:visible').nth(i)
                try: await el.fill(plain); break
                except: pass

            await page.wait_for_timeout(1000)
            await shot(page, "03_filled")

            # Publish — try multiple methods
            published = False
            # Method 1: text search
            for pt in ['发布', '发布笔记', 'Publish']:
                btn = page.locator(f'text="{pt}"').last
                if await btn.count() > 0:
                    try:
                        await btn.evaluate('el => el.click()')
                        published = True
                        print(f"[RED] Published via text '{pt}'")
                        break
                    except: pass

            # Method 2: scan all buttons
            if not published:
                btns = page.locator('button:visible, [role="button"]:visible')
                cnt = await btns.count()
                print(f"[RED] Found {cnt} visible buttons")
                for i in range(min(cnt, 40)):
                    b = btns.nth(i)
                    try:
                        txt = (await b.text_content() or '').strip()
                        if txt and len(txt) < 15:
                            print(f"[RED] Btn #{i}: '{txt}'")
                        if any(kw in (txt or '') for kw in ['发布', '笔记', 'publish', 'Publish', '提交', '确认']):
                            await b.evaluate('el => el.click()')
                            published = True
                            print(f"[RED] Published via btn #{i} '{txt}'")
                            break
                    except: pass

            # Method 3: keyboard shortcut
            if not published:
                try:
                    await page.keyboard.press('Control+Enter')
                    published = True
                    print("[RED] Published via Ctrl+Enter")
                except: pass

            await page.wait_for_timeout(3000)
            await shot(page, "04_result")
            print(json.dumps({"success": published, "message": "Published OK" if published else "No publish method worked"}))
            await browser.close()

    except Exception as e:
        print(json.dumps({"success": False, "message": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    asyncio.run(main())
