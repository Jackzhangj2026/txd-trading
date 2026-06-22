# -*- coding: utf-8 -*-
"""RED publish: upload images, fill, click bottom bar publish button."""
import sys, os, json, asyncio, re, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == 'win32': sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

FACTORY = Path(__file__).parent.parent.parent / "factory image"
BASE = Path(__file__).parent.parent.parent / "browser_data"
STATE, PAYLOAD, DEBUG = BASE / "red_state.json", BASE / "red_payload.json", BASE / "debug"
DEBUG.mkdir(parents=True, exist_ok=True); BASE.mkdir(parents=True, exist_ok=True)

async def main():
    if not PAYLOAD.exists(): print(json.dumps({"success":False,"message":"No payload"})); return
    d = json.load(open(PAYLOAD,"r",encoding="utf-8"))
    title, body = d["title"][:20], d.get("body","")
    imgs = random.sample([str(f) for f in FACTORY.glob("*") if f.suffix.lower() in ('.jpg','.jpeg','.png','.webp')], min(random.randint(3,4), len(list(FACTORY.glob("*")))))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width":1280,"height":900}, storage_state=str(STATE) if STATE.exists() else None)
        page = await ctx.new_page()

        try:
            # Nav
            await page.goto("https://creator.xiaohongshu.com", timeout=30000)
            await page.wait_for_timeout(5000)
            if "login" in page.url.lower():
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=180000)
                await ctx.storage_state(path=str(STATE)); await page.wait_for_timeout(3000)
            await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000)
            await page.wait_for_timeout(8000)

            # Click 发布笔记 → 上传图文
            await page.evaluate("""()=>{for(const e of document.querySelectorAll('*')){if(e.textContent.trim()==='发布笔记'&&e.offsetParent!==null){e.click();break;}}}""")
            await page.wait_for_timeout(5000)
            await page.evaluate("""()=>{for(const e of document.querySelectorAll('*')){if(e.textContent.trim()==='上传图文'&&e.offsetParent!==null){e.click();break;}}}""")
            await page.wait_for_timeout(5000)

            # Upload + wait for RED to process and show thumbnails
            for i, img in enumerate(imgs):
                fi = page.locator('input[type="file"]').first
                if await fi.count() > 0:
                    await fi.set_input_files(img)
                    await page.wait_for_timeout(3000)
                    print(f"  img {i+1}/{len(imgs)}")

            # Wait for image thumbnails to appear (indicates processing complete)
            print("  waiting for thumbnails...")
            for attempt in range(10):
                has_thumb = await page.evaluate("""() => {
                    return document.querySelectorAll('img[src*="data"], img[class*="thumb"], img[class*="preview"], [class*="image-item"], [class*="upload-item"]').length > 0;
                }""")
                if has_thumb: print("  thumbnails visible"); break
                await page.wait_for_timeout(2000)

            await page.wait_for_timeout(3000)

            # Fill title (only after entering editor)
            for i in range(min(await page.locator('input:visible').count(), 10)):
                try:
                    el = page.locator('input:visible').nth(i)
                    if '标题' in (await el.get_attribute('placeholder') or ''):
                        await el.fill(title)
                        print(f"  title: {title}"); break
                except: pass

            # Fill content
            plain = re.sub(r'<img[^>]*>','',body); plain = re.sub(r'<[^>]+>','',plain)
            lines = [l.strip() for l in plain.split('\n') if l.strip() and not re.match(r'^(photo|image|picture|▲|△)\s*\d*',l.strip(),re.I)]
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0:
                await ce.fill('\n'.join(lines))
                print(f"  content: {len(''.join(lines))} chars")

            # Topics + dismiss
            for i in range(min(await page.locator('input:visible').count(), 15)):
                try:
                    el = page.locator('input:visible').nth(i)
                    if '话题' in (await el.get_attribute('placeholder') or ''):
                        await el.fill("#PPhollowBoard #SustainablePackaging"); break
                except: pass
            await page.evaluate("document.body.click()"); await page.wait_for_timeout(500)
            await page.keyboard.press('Escape'); await page.wait_for_timeout(300)
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0: await ce.click(); await page.wait_for_timeout(300)
            await page.evaluate("document.body.click()"); await page.wait_for_timeout(1000)

            # Try clicking "笔记预览" to enter preview/publish mode
            r = await page.evaluate("""() => {
                for (const el of document.querySelectorAll('*')) {
                    if (el.textContent.trim() === '笔记预览') { el.click(); return 'ok'; }
                }
                return 'no';
            }""")
            print(f"  笔记预览 click: {r}")
            await page.wait_for_timeout(3000)

            # Check for publish bar now
            has = await page.evaluate("""() => {
                for (const el of document.querySelectorAll('*')) {
                    const t = el.textContent.trim();
                    if (t === '暂存离开' || t === '发布') return t;
                }
                return 'none';
            }""")
            print(f"  bottom bar elements: {has}")

            # Check if page navigated away (published)
            final_url = page.url
            published = 'publish' not in final_url.lower()

            await page.screenshot(path=str(DEBUG / "after_publish.png"))
            print(json.dumps({"success": published, "images": len(imgs), "url": final_url[:80]}))

            # Dump ALL unique visible texts on the entire page
            all_t = await page.evaluate("""() => {
                const s = new Set();
                for (const el of document.querySelectorAll('*')) {
                    const t = el.textContent.trim();
                    if (t && t.length >= 2 && t.length <= 15 && el.offsetParent !== null) s.add(t);
                }
                return [...s].sort();
            }""")
            print("ALL page texts:")
            for t in all_t: print(f"  '{t}'")

            # Wait up to 30s for bottom bar with "暂存离开" + "发布" or standalone "发布"
            clicked = False
            for attempt in range(15):
                r = await page.evaluate("""() => {
                    // Method 1: find "暂存离开", then find sibling/child "发布"
                    for (const el of document.querySelectorAll('*')) {
                        if (el.textContent.trim() === '暂存离开') {
                            let bar = el.parentElement;
                            for (let d = 0; d < 5 && bar; d++) {
                                const pub = bar.querySelector('*');
                                for (const c of bar.querySelectorAll('*')) {
                                    if (c.textContent.trim() === '发布' && c.offsetParent !== null) {
                                        c.click(); return 'ok via bar';
                                    }
                                }
                                bar = bar.parentElement;
                            }
                        }
                    }
                    // Method 2: find "发布" (exact) in fixed/sticky container
                    for (const el of document.querySelectorAll('*')) {
                        if (el.textContent.trim() === '发布' && el.offsetParent !== null) {
                            let p = el;
                            while (p && p !== document.body) {
                                const pos = getComputedStyle(p).position;
                                if (pos === 'fixed' || pos === 'sticky') { el.click(); return 'ok fixed'; }
                                p = p.parentElement;
                            }
                        }
                    }
                    // Method 3: find exact-text "发布" (NOT "定时发布") at document bottom
                    let best = null, bestBottom = -1;
                    for (const el of document.querySelectorAll('button,span,div')) {
                        if (el.textContent.trim() === '发布' && el.offsetParent !== null) {
                            const r = el.getBoundingClientRect();
                            if (r.bottom > bestBottom) { bestBottom = r.bottom; best = el; }
                        }
                    }
                    if (best) { best.click(); return 'ok best'; }
                    // Method 4: find parent of text-only "发布" node
                    for (const el of document.querySelectorAll('*')) {
                        if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                            && el.childNodes[0].textContent.trim() === '发布'
                            && el.offsetParent !== null) {
                            el.click(); return 'ok textNode';
                        }
                    }
                    return 'not';
                }""")
                if r.startswith('ok'):
                    print(f"  publish clicked: {r}")
                    clicked = True; break
                if attempt == 0:
                    # Debug: dump what's near viewport bottom
                    btns = await page.evaluate("""() => {
                        const f = [];
                        for (const el of document.querySelectorAll('*')) {
                            const t = el.textContent.trim();
                            const r = el.getBoundingClientRect();
                            if (t && t.length >= 2 && t.length <= 10 && r.bottom > window.innerHeight - 120 && r.bottom < window.innerHeight + 20 && el.offsetParent !== null)
                                f.push({t: t, b: Math.round(r.bottom)});
                        }
                        return f.sort((a,b)=>b.b-b.a).slice(0,10);
                    }""")
                    print(f"  viewport bottom: {json.dumps(btns, ensure_ascii=False)}")
                await page.wait_for_timeout(2000)

            await page.wait_for_timeout(3000)
            print(json.dumps({"success": clicked, "images": len(imgs)}))

        except Exception as e:
            import traceback; traceback.print_exc()
            print(json.dumps({"success": False, "message": str(e)}))
        finally:
            await page.wait_for_timeout(2000); await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
