# -*- coding: utf-8 -*-
"""RED auto-publish: 发布笔记 → 上传图文 → 上传图片 → 填标题 → 填正文 → 填话题 → 发布"""
import sys, os, json, asyncio, re, base64, tempfile, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

RED_URL = "https://creator.xiaohongshu.com/publish/publish"
FACTORY_IMG = Path(__file__).parent.parent.parent / "factory image"
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
    return await page.evaluate("""([text]) => {
        const all = document.querySelectorAll('span, div, button, a');
        for (const el of all) {
            if (el.textContent.trim() === text && el.offsetParent !== null) {
                el.click(); return 'clicked';
            }
        }
        return 'not found';
    }""", [text])


def pick_factory_images(count=4):
    """Pick random images from factory image folder."""
    if not FACTORY_IMG.is_dir():
        return []
    all_imgs = [str(FACTORY_IMG / f) for f in os.listdir(FACTORY_IMG)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    if len(all_imgs) <= count:
        return all_imgs
    return random.sample(all_imgs, count)


async def main():
    if not PAYLOAD.exists():
        print(json.dumps({"success": False, "message": "No payload file"}))
        return
    with open(PAYLOAD, "r", encoding="utf-8") as f:
        payload = json.load(f)
    title = payload.get("title", "Test")
    body = payload.get("body", "<p>Test content</p>")

    # Pick 3-4 random factory images
    image_files = pick_factory_images(random.randint(3, 4))
    print(f"  Selected {len(image_files)} factory images")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=str(STATE) if STATE.exists() else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await ctx.new_page()

        try:
            # ── 1. Navigate ──
            await page.goto(RED_URL, timeout=30000)
            await page.wait_for_timeout(8000)
            await shot(page, "01_page")

            # ── 2. Login if needed ──
            if "login" in page.url.lower():
                print("  Login: scan QR...")
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=180000)
                await ctx.storage_state(path=str(STATE))
                await page.wait_for_timeout(5000)
            if "login" in page.url.lower():
                print(json.dumps({"success": False, "message": "Login failed"})); return

            # ── 3. Click 发布笔记 ──
            r = await click_by_text(page, "发布笔记")
            print(f"  发布笔记: {r}")
            await page.wait_for_timeout(3000)

            # ── 4. Click 上传图文 ──
            r = await click_by_text(page, "上传图文")
            print(f"  上传图文: {r}")
            await page.wait_for_timeout(5000)
            await shot(page, "02_after_upload_tuwen")

            # ── 5. Upload images ──
            print(f"  Uploading {len(image_files)} images...")
            for i, img_path in enumerate(image_files):
                try:
                    # Click upload area to trigger file dialog
                    # On RED note editor, there's usually a "+" or image area
                    upload_triggers = ['上传图片', '添加图片']
                    for ut in upload_triggers:
                        r = await click_by_text(page, ut)
                        if r == "clicked":
                            print(f"  Clicked '{ut}'")
                            break
                    await page.wait_for_timeout(500)

                    # Try file input
                    fi = page.locator('input[type="file"]').first
                    if await fi.count() > 0:
                        await fi.set_input_files(img_path)
                        print(f"  Image {i+1}/{len(image_files)} uploaded")
                        await page.wait_for_timeout(1500)
                    else:
                        # Try file chooser
                        try:
                            async with page.expect_file_chooser(timeout=3000) as fc:
                                # Click any upload-like element
                                for cls in ['[class*="upload"]', '[class*="add"]', '[class*="image"]']:
                                    el = page.locator(cls).first
                                    if await el.count() > 0 and await el.is_visible():
                                        await el.click(); break
                            fc_obj = await fc.value
                            await fc_obj.set_files(img_path)
                            print(f"  Image {i+1}/{len(image_files)} via filechooser")
                            await page.wait_for_timeout(1500)
                        except:
                            print(f"  Image {i+1}: no upload method found")
                except Exception as e:
                    print(f"  Image {i+1} error: {e}")

            await page.wait_for_timeout(2000)
            await shot(page, "03_images_uploaded")

            # ── 6. Fill title ──
            for i in range(min(await page.locator('input:visible').count(), 10)):
                try:
                    el = page.locator('input:visible').nth(i)
                    ph = (await el.get_attribute('placeholder') or '')
                    tp = await el.get_attribute('type') or 'text'
                    if '标题' in ph or 'title' in ph.lower() or (tp == 'text' and not ph):
                        await el.fill(title)
                        print(f"  Title filled")
                        break
                except: pass

            # ── 7. Fill content ──
            plain = re.sub(r'<img[^>]*>', '', body)
            plain = re.sub(r'<[^>]+>', '', plain).strip()
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0:
                await ce.fill(plain)
                print("  Content filled")
            await page.wait_for_timeout(1000)

            # ── 8. Fill topics/hashtags ──
            # RED has a topic input — try to find it
            for i in range(min(await page.locator('input:visible').count(), 15)):
                try:
                    el = page.locator('input:visible').nth(i)
                    ph = (await el.get_attribute('placeholder') or '')
                    if '话题' in ph or '标签' in ph or 'tag' in ph.lower() or 'topic' in ph.lower():
                        await el.fill("#PPhollowBoard #SustainablePackaging #FactoryDirect")
                        print(f"  Topics filled")
                        break
                except: pass

            await page.wait_for_timeout(1000)
            await shot(page, "04_filled")

            # ── 9. Publish ──
            for pub_text in ['发布', '发布笔记']:
                r = await click_by_text(page, pub_text)
                if r == "clicked":
                    await page.wait_for_timeout(5000)
                    await shot(page, "05_published")
                    print(json.dumps({"success": True, "message": f"Published via '{pub_text}'", "images": len(image_files)}))
                    break
            else:
                print(json.dumps({"success": False, "message": "Publish button not found"}))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(json.dumps({"success": False, "message": f"{type(e).__name__}: {e}"}))
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
