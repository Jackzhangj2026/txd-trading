"""Test email template with base64 images"""
import sys, re
from pathlib import Path

# Force fresh import
for mod in list(sys.modules.keys()):
    if 'email_sender' in mod:
        del sys.modules[mod]

sys.path.insert(0, str(Path(__file__).parent))
from email_sender import _image_to_base64, build_email_html

img_dir = Path(__file__).parent / "email_images"

# Convert all 4 images to base64
b64s = []
for name in ["product1-board.jpg", "product2-box.jpg", "product3-box.jpg", "product4-esd.jpg"]:
    b64 = _image_to_base64(img_dir / name)
    ok = b64.startswith("data:image") if b64 else False
    print(f"  {'✅' if ok else '❌'} {name}: {len(b64)} chars")
    b64s.append(b64)

# Build email
html = build_email_html(
    contact_name="John Smith",
    company_name="Test Co",
    website_url="https://jackzhangj2026.github.io/txd-trading/",
    image_1=b64s[0], image_2=b64s[1], image_3=b64s[2], image_4=b64s[3],
)

images = re.findall(r'src="([^"]+)"', html)
data_uris = [i for i in images if i.startswith('data:image')]

print(f"\n📧 Email size: {len(html)/1024:.0f}KB")
print(f"🖼️  Total images: {len(images)}")
print(f"🔒  Base64 embedded: {len(data_uris)}")
print("✅ All images embedded!" if len(data_uris) == len(images) else "❌ Some images are external URLs")

# Save a preview
out = Path(__file__).parent / "data" / "email_preview.html"
out.write_text(html, encoding='utf-8')
print(f"\n💾 Preview saved to: {out}")
print("   Open in browser to see exactly what customers will receive")
