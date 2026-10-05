"""Generate sitemap.xml and robots.txt for TXD CO., LTD website."""
import os
from datetime import datetime, timezone

BASE_URL = "https://jackzhangj2026.github.io/txd-trading"
PAGES = [
    ("index.html", "0.9", "daily"),
]

# Discover blog posts
blog_dir = "blog"
if os.path.isdir(blog_dir):
    for f in sorted(os.listdir(blog_dir)):
        if f.endswith(".html") and f != "index.html":
            PAGES.append((f"blog/{f}", "0.6", "weekly"))

blog_index = (f"{blog_dir}/index.html", "0.7", "daily")
PAGES.insert(1, blog_index)

# Generate sitemap.xml
now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
]
for path, priority, changefreq in PAGES:
    mtime = now
    abs_path = os.path.join(os.getcwd(), path)
    if os.path.exists(abs_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(abs_path), timezone.utc).strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{path}" if path != "index.html" else BASE_URL
    lines.append("  <url>")
    lines.append(f"    <loc>{url}</loc>")
    lines.append(f"    <lastmod>{mtime}</lastmod>")
    lines.append(f"    <changefreq>{changefreq}</changefreq>")
    lines.append(f"    <priority>{priority}</priority>")
    lines.append("  </url>")
lines.append("</urlset>")

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"sitemap.xml generated with {len(PAGES)} URLs")

# Generate robots.txt
with open("robots.txt", "w", encoding="utf-8") as f:
    f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
print("robots.txt generated")
