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
    """Click first element with exact text, trying different visibility checks."""
    return await page.evaluate("""([text]) => {
        const all = document.querySelectorAll('span, div, button, a, li');
        // First try: visible elements
        for (const el of all) {
            if (el.textContent.trim() === text && el.offsetParent !== null) {
                el.click(); return 'clicked visible';
            }
        }
        // Fallback: any element (might be hidden but clickable)
        for (const el of all) {
            if (el.textContent.trim() === text && el.tagName !== 'BODY' && el.tagName !== 'HTML') {
                el.click(); return 'clicked any';
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
            # ── 1. Navigate (force fresh start) ──
            # Go to creator home first, then publish page
            await page.goto("https://creator.xiaohongshu.com", timeout=30000)
            await page.wait_for_timeout(5000)
            if "login" in page.url.lower():
                print("  Login: scan QR...")
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=180000)
                await ctx.storage_state(path=str(STATE))
                await page.wait_for_timeout(5000)

            # Now go to publish page
            await page.goto(RED_URL, timeout=30000)
            await page.wait_for_timeout(8000)
            await shot(page, "01_page")

            # Login check
            if "login" in page.url.lower():
                print(json.dumps({"success": False, "message": "Login required — please scan QR"}))
                return

            # ── 2. Click 发布笔记 (on dashboard/publish page) ──
            r = await click_by_text(page, "发布笔记")
            print(f"  发布笔记: {r}")
            await page.wait_for_timeout(5000)
            await shot(page, "02_after_fabubiji")

            # ── 4. Now should be on publish page with tabs. Click 上传图文 ──
            r = await click_by_text(page, "上传图文")
            if r == "not found":
                # Page might have changed URL — wait and retry
                await page.wait_for_timeout(3000)
                r = await click_by_text(page, "上传图文")
            print(f"  上传图文: {r}")
            if r == "not found":
                # Dump texts to debug
                all_text = await page.evaluate("""() => {
                    const all = document.querySelectorAll('*');
                    const found = [];
                    for (const el of all) {
                        const t = el.textContent.trim();
                        if (t && t.length >= 2 && t.length <= 15 && el.offsetParent !== null) found.push(t);
                    }
                    return [...new Set(found)].slice(0, 30);
                }""")
                print(f"  Page texts: {all_text}")
                print(json.dumps({"success": False, "message": f"上传图文 not found. Texts: {all_text[:15]}"}))
                return
            await page.wait_for_timeout(5000)
            await shot(page, "03_after_tuwen")

            # ── 5. Upload images (direct to input, no Windows dialog) ──
            print(f"  Uploading {len(image_files)} images...")

            # Find all file inputs
            all_fi = page.locator('input[type="file"]')
            fi_count = await all_fi.count()
            print(f"  File inputs: {fi_count}")

            for i, img_path in enumerate(image_files):
                uploaded = False
                try:
                    # Try direct set_input_files FIRST (no dialog)
                    for j in range(fi_count):
                        try:
                            await all_fi.nth(j).set_input_files(img_path)
                            print(f"    [{i+1}] uploaded via input #{j}")
                            await page.wait_for_timeout(2000)
                            uploaded = True
                            break
                        except Exception as e:
                            if 'multiple' not in str(e).lower():
                                raise
                            # Non-multiple input — try file_chooser
                            pass

                    if not uploaded:
                        # Click "上传图片" to make file input appear + trigger chooser
                        for ut in ['上传图片', '添加图片']:
                            r = await click_by_text(page, ut)
                            if r == "clicked":
                                print(f"    [{i+1}] Clicked '{ut}'")
                                await page.wait_for_timeout(800)
                                break
                        # Try file chooser
                        try:
                            async with page.expect_file_chooser(timeout=5000) as fc_info:
                                pass  # already clicked above
                            fc = await fc_info.value
                            await fc.set_files(img_path)
                            print(f"    [{i+1}] via file_chooser")
                            await page.wait_for_timeout(2000)
                            uploaded = True
                        except:
                            pass

                    if not uploaded:
                        print(f"    [{i+1}] FAILED")
                except Exception as e:
                    print(f"    [{i+1}] error: {e}")

                # Close any dialog
                try:
                    for _ in range(3):
                        await page.keyboard.press('Escape')
                        await page.wait_for_timeout(200)
                except: pass

            # After all images, dismiss modals
            await page.wait_for_timeout(2000)
            for _ in range(3):
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(300)
            for txt in ['取消', '完成', '确定', '知道了']:
                try:
                    r = await click_by_text(page, txt)
                    if r.startswith("clicked"): await page.wait_for_timeout(500)
                except: pass
            await shot(page, "03_images_uploaded")

            await page.wait_for_timeout(3000)
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
            # Scroll to bottom (publish button might be below viewport)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            # Try scrolling back up a bit
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 300)")
            await page.wait_for_timeout(500)

            for pub_text in ['发布', '发布笔记']:
                r = await click_by_text(page, pub_text)
                if r.startswith("clicked"):
                    await page.wait_for_timeout(5000)
                    await shot(page, "05_published")
                    print(json.dumps({"success": True, "message": f"Published via '{pub_text}'", "images": len(image_files)}))
                    break
            else:
                # Dump all buttons to debug
                btns = await page.evaluate("""() => {
                    const all = document.querySelectorAll('button, span[class*="btn"], div[class*="btn"]');
                    const found = [];
                    for (const el of all) {
                        const t = el.textContent.trim();
                        if (t && t.length < 20) found.push(t);
                    }
                    return found;
                }""")
                print(f"  Buttons on page: {btns}")
                print(json.dumps({"success": False, "message": f"Publish button not found. Buttons: {btns[:10]}"}))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(json.dumps({"success": False, "message": f"{type(e).__name__}: {e}"}))
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
