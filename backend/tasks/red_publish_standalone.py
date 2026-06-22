# -*- coding: utf-8 -*-
"""RED auto-publish standalone script."""
import sys, os, json, asyncio, re, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright

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


async def click_text(page, text):
    return await page.evaluate("""([text]) => {
        for (const el of document.querySelectorAll('*')) {
            if (el.textContent.trim() === text && el.offsetParent !== null) {
                el.click(); return 'ok';
            }
        }
        return 'no';
    }""", [text])


async def main():
    if not PAYLOAD.exists():
        print(json.dumps({"success": False, "message": "No payload"})); return
    d = json.load(open(PAYLOAD, "r", encoding="utf-8"))
    title = d["title"][:20]
    body = d.get("body", "")

    # Pick random factory images
    imgs = list(FACTORY_IMG.glob("*.jpg")) + list(FACTORY_IMG.glob("*.png"))
    imgs = random.sample(imgs, min(random.randint(3, 4), len(imgs)))
    print(f"  {len(imgs)} images")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900},
            storage_state=str(STATE) if STATE.exists() else None)
        page = await ctx.new_page()

        try:
            # 1. Navigate
            await page.goto("https://creator.xiaohongshu.com", timeout=30000)
            await page.wait_for_timeout(5000)
            if "login" in page.url.lower():
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=180000)
                await ctx.storage_state(path=str(STATE))
                await page.wait_for_timeout(5000)

            await page.goto(RED_URL, timeout=30000)
            await page.wait_for_timeout(8000)
            await shot(page, "01")

            # 2. Click 发布笔记 → 上传图文
            r = await click_text(page, "发布笔记")
            print(f"  发布笔记: {r}")
            await page.wait_for_timeout(5000)

            r = await click_text(page, "上传图文")
            print(f"  上传图文: {r}")
            await page.wait_for_timeout(5000)

            # 3. Upload images (direct, no dialog)
            fi = page.locator('input[type="file"]').first
            for i, img in enumerate(imgs):
                await fi.set_input_files(str(img))
                await page.wait_for_timeout(2000)
                print(f"  img {i+1}/{len(imgs)}")
            await page.wait_for_timeout(2000)
            await shot(page, "04_imgs")

            # 4. Fill title
            for i in range(min(await page.locator('input:visible').count(), 10)):
                try:
                    el = page.locator('input:visible').nth(i)
                    ph = (await el.get_attribute('placeholder') or '')
                    if '标题' in ph:
                        await el.fill(title)
                        print(f"  title: {title}")
                        break
                except: pass

            # 5. Fill content (strip image captions)
            plain = re.sub(r'<img[^>]*>', '', body)
            plain = re.sub(r'<[^>]+>', '', plain)
            lines = [l.strip() for l in plain.split('\n') if l.strip()
                     and not re.match(r'^(photo|image|picture|▲|△)\s*\d*', l.strip(), re.I)]
            plain = '\n'.join(lines)
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0:
                await ce.fill(plain)
                print(f"  content: {len(plain)} chars")

            # 6. Topics + dismiss
            for i in range(min(await page.locator('input:visible').count(), 15)):
                try:
                    el = page.locator('input:visible').nth(i)
                    ph = (await el.get_attribute('placeholder') or '')
                    if '话题' in ph:
                        await el.fill("#PPhollowBoard #SustainablePackaging")
                        break
                except: pass
            await page.wait_for_timeout(500)
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(300)
            await page.evaluate("document.body.click()")
            await page.wait_for_timeout(500)
            await shot(page, "05_content")

            # 7. Trigger UI update — click body, blur inputs
            await page.evaluate("document.body.click()")
            await page.wait_for_timeout(1000)
            
            # Click content area then body again to trigger validation
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0:
                await ce.click()
                await page.wait_for_timeout(300)
            await page.evaluate("document.body.click()")
            await page.wait_for_timeout(1000)
            await shot(page, "05_content")

            # 8. Wait for bottom publish bar (fixed OR sticky)
            print("  waiting for bottom publish bar...")
            for attempt in range(10):
                has = await page.evaluate("""() => {
                    for (const el of document.querySelectorAll('*')) {
                        const t = el.textContent.trim();
                        if (t === '发布' || t === '发布笔记') {
                            let p = el;
                            while (p && p !== document.body) {
                                const pos = getComputedStyle(p).position;
                                if (pos === 'fixed' || pos === 'sticky') return true;
                                p = p.parentElement;
                            }
                            // Also check if element is at very bottom of viewport
                            const rect = el.getBoundingClientRect();
                            if (rect.bottom > window.innerHeight - 60 && rect.top > window.innerHeight * 0.6) {
                                return true;
                            }
                        }
                    }
                    return false;
                }""")
                if has:
                    print(f"  bar visible at attempt {attempt+1}")
                    break
                await page.wait_for_timeout(2000)

            # 9. Click red publish button in bottom bar (next to 暂存离开)
            r = await page.evaluate("""() => {
                // Find bottom bar: look for "暂存离开" as anchor, then find nearby "发布"
                let saveBtn = null;
                for (const el of document.querySelectorAll('*')) {
                    if (el.textContent.trim() === '暂存离开' && el.offsetParent !== null) {
                        saveBtn = el;
                        break;
                    }
                }
                if (saveBtn) {
                    // Get parent container (bottom bar)
                    let bar = saveBtn;
                    while (bar && bar !== document.body) {
                        const pos = getComputedStyle(bar).position;
                        if (pos === 'fixed' || pos === 'sticky') break;
                        bar = bar.parentElement;
                    }
                    if (bar && bar !== document.body) {
                        // Find "发布" button inside the same bar
                        const pubBtns = bar.querySelectorAll('*');
                        for (const b of pubBtns) {
                            const t = b.textContent.trim();
                            if (t === '发布' && b.offsetParent !== null) {
                                b.click();
                                return 'ok bar ' + b.tagName;
                            }
                        }
                    }
                }
                // Fallback: find bottom-most red clickable element
                let best = null, bestBottom = -1;
                for (const el of document.querySelectorAll('button, span, div, a')) {
                    const t = el.textContent.trim();
                    if ((t === '发布' || t === '发布笔记') && el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        if (rect.bottom > bestBottom) {
                            bestBottom = rect.bottom;
                            best = el;
                        }
                    }
                }
                if (best) { best.click(); return 'ok best ' + best.tagName; }
                
                // Last resort: click the parent of any visible "发布"
                for (const el of document.querySelectorAll('*')) {
                    if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                        && el.childNodes[0].textContent.trim() === '发布'
                        && el.offsetParent !== null) {
                        el.click(); return 'ok textNode ' + el.tagName;
                    }
                }
                return 'not found';
            }""")
            print(f"  publish: {r}")
            print(f"  publish: {r}")
            await page.wait_for_timeout(5000)
            await shot(page, "99_done")

            print(json.dumps({"success": r.startswith("ok"), "message": r, "images": len(imgs)}))

        except Exception as e:
            import traceback; traceback.print_exc()
            print(json.dumps({"success": False, "message": str(e)}))
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
