# -*- coding: utf-8 -*-
"""RED publish: auto-fill everything, user clicks publish button manually."""
import sys, os, json, asyncio, re, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == 'win32': sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

FACTORY = Path(__file__).parent.parent.parent / "factory image"
BASE = Path(__file__).parent.parent.parent / "browser_data"
PAYLOAD = BASE / "red_payload.json"
DEBUG = BASE / "debug"
DEBUG.mkdir(parents=True, exist_ok=True)

async def shot(page, name):
    try: await page.screenshot(path=str(DEBUG / f"{name}.png"))
    except: pass

async def main():
    if not PAYLOAD.exists():
        print(json.dumps({"success":False,"message":"No payload"})); return
    d = json.load(open(PAYLOAD,"r",encoding="utf-8"))
    title = d["title"][:20]
    body = d.get("body","")

    all_imgs = [str(f) for f in FACTORY.glob("*") if f.suffix.lower() in ('.jpg','.jpeg','.png','.webp')]
    imgs = random.sample(all_imgs, min(random.randint(3,4), len(all_imgs)))
    print(f"  Images: {len(imgs)}")
    print(f"  Title: {title}")
    print()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BASE / "chrome_profile"),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # 1. Navigate
            print("[1/6] Opening RED...")
            await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000)
            await page.wait_for_timeout(8000)

            if "login" in page.url.lower():
                print("      ⚠️ Please scan QR code with RED app (90s)...")
                try:
                    await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=90000)
                    print("      ✅ Logged in!")
                    await page.wait_for_timeout(5000)
                except:
                    print("      ❌ Login timeout")
                    return

            await shot(page, "01_page")

            # 2. Click 发布笔记 → 上传图文
            print("[2/6] Creating note...")
            for txt in ['发布笔记', '上传图文']:
                await page.evaluate("""([t]) => {
                    for(const e of document.querySelectorAll('*')) {
                        if(e.textContent.trim()===t){e.click();break;}
                    }
                }""", [txt])
                await page.wait_for_timeout(5000)
            await shot(page, "02_note_created")

            # 3. Upload images
            print(f"[3/6] Uploading {len(imgs)} images...")
            for i, img in enumerate(imgs):
                fi = page.locator('input[type="file"]').first
                if await fi.count() > 0:
                    await fi.set_input_files(img)
                    print(f"      {i+1}/{len(imgs)}")
                    await page.wait_for_timeout(2500)
            await page.wait_for_timeout(3000)
            await shot(page, "03_images")

            # 4. Fill title
            print("[4/6] Filling title...")
            for i in range(10):
                try:
                    el = page.locator('input:visible').nth(i)
                    if '标题' in (await el.get_attribute('placeholder') or ''):
                        await el.fill(title)
                        print(f"      ✅ {title}")
                        break
                except: pass

            # 5. Fill content
            print("[5/6] Filling content...")
            plain = re.sub(r'<img[^>]*>','',body)
            plain = re.sub(r'<[^>]+>','',plain)
            lines = [l.strip() for l in plain.split('\n') if l.strip()
                     and not re.match(r'^(photo|image|picture|▲|△)\s*\d*', l.strip(), re.I)]
            ce = page.locator('[contenteditable="true"]:visible').first
            if await ce.count() > 0:
                body_text = '\n'.join(lines)[:1000]  # Hard limit 1000 chars
                await ce.fill(body_text)
                print(f"      ✅ {len(body_text)} chars")
            await page.wait_for_timeout(1000)

            # 6. Fill topics + dismiss dropdown
            print("[6/6] Filling topics...")
            for i in range(15):
                try:
                    el = page.locator('input:visible').nth(i)
                    if '话题' in (await el.get_attribute('placeholder') or ''):
                        await el.fill("#PPhollowBoard #SustainablePackaging #FactoryDirect")
                        print("      ✅ Topics filled")
                        break
                except: pass
            # Dismiss topic dropdown (safe)
            try: await page.evaluate("document.body.click()")
            except: pass
            await page.wait_for_timeout(500)
            try: await page.keyboard.press('Escape')
            except: pass
            await page.wait_for_timeout(300)
            try:
                if await ce.count() > 0: await ce.click()
            except: pass
            await page.wait_for_timeout(300)
            try: await page.evaluate("document.body.click()")
            except: pass
            await page.wait_for_timeout(1000)

            await shot(page, "04_ready")

            # Done — wait for user to click publish
            print()
            print("=" * 50)
            print("  ✅ All content filled!")
            print(f"  📷 {len(imgs)} images uploaded")
            print(f"  📝 Title: {title}")
            print()
            print("  👆 Please click the RED [发布] button manually")
            print("  ⏳ Browser will stay open until you close it...")
            print("=" * 50)
            print(json.dumps({"success": True, "message": "Ready — user click publish", "images": len(imgs)}))

            # Keep browser open for 5 minutes (or until user closes it)
            await page.wait_for_timeout(300000)

        except Exception as e:
            import traceback; traceback.print_exc()
            print(json.dumps({"success": False, "message": str(e)}))
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(main())
