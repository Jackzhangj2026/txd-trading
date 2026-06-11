"""AI-powered blog post generator for SEO content."""

import os
import re
from datetime import datetime
from pathlib import Path

from backend.agents import TradeAgent

BLOG_DIR = Path("blog")
TOPICS = [
    "PP Hollow Sheet Applications in Automotive Packaging",
    "Why Choose Corrugated Plastic Boxes Over Cardboard for Logistics",
    "ESD Protection: Anti-Static PP Sheets for Electronics",
    "Cost Comparison: PP Hollow Board vs Wood vs Cardboard",
    "Custom PP Box Design Guide for International Buyers",
    "PP Hollow Sheet Thickness Guide: 2mm to 12mm Explained",
    "How to Choose the Right Packaging Material for Global Logistics",
    "Environmental Benefits of Recyclable PP Packaging Solutions",
    "PP Hollow Board for Agriculture: Greenhouse and Produce Boxes",
    "Quality Standards for PP Hollow Sheet Manufacturing and Export",
]


class BlogGenerator:
    """Generates SEO-optimized blog posts using LLM."""

    def __init__(self):
        self.agent = TradeAgent(system_prompt="You are an expert SEO content writer for the PP hollow board and packaging industry.")

    def pick_topic(self) -> str:
        """Pick a topic that hasn't been published recently."""
        published = set()
        if BLOG_DIR.exists():
            for f in BLOG_DIR.glob("*.html"):
                if f.name == "index.html":
                    continue
                published.add(f.stem.replace("-", " ").lower())

        # Find first unpublished topic
        for topic in TOPICS:
            slug = topic.lower().replace(" ", "-").replace(":", "").replace("'", "").replace("&", "and")
            slug = re.sub(r"[^a-z0-9-]", "", slug)
            if slug not in published:
                return topic

        # All published — pick by date rotation
        day = datetime.now().day
        return TOPICS[day % len(TOPICS)]

    async def generate_post(self, topic: str) -> dict:
        """Generate a complete blog post HTML. Returns {title, slug, html, excerpt, tags}."""
        slug = topic.lower().replace(" ", "-").replace(":", "").replace("'", "").replace("&", "and")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        date_str = datetime.now().strftime("%Y-%m-%d")
        display_date = datetime.now().strftime("%B %d, %Y")

        # Generate content via LLM
        prompt = f"""Write a complete SEO-optimized blog post HTML about: {topic}

The post is for TXD CO., LTD Trading, a PP hollow sheet and corrugated plastic box manufacturer/exporter.

Write in this structure:
1. Introduction (1 paragraph about the topic)
2. Key Considerations section with 4 sub-sections
3. Why Choose TXD CO., LTD section
4. Call-to-action box at the end

Generate these outputs:
- TITLE: the blog post title (SEO optimized, include "PP" or "corrugated" or key keyword)
- EXCERPT: one sentence summary (max 200 chars) for the blog listing
- TAGS: comma-separated keywords (3-5 tags)
- BODY: The full HTML content inside the <article> tag (starting from the container div)

Use this exact HTML structure for the body:
```
<div class="container">
    <a href="index.html" class="back-link">&larr; Back to Blog</a>
    <h1>TITLE_HERE</h1>
    <div class="post-meta">Published: {display_date} | Reading time: 5 minutes</div>
    ... content with <h2>, <h3>, <p>, <ul>, <li> tags ...
    <div class="cta-box">
        <p><strong>Interested in this topic?</strong></p>
        <p>Contact our sales team for a competitive quote within 24 hours.</p>
        <a href="../index.html#contact" class="btn">Request a Quote</a>
    </div>
    <hr>
    <p style="color:#555;font-size:0.82rem;">
        <em>TXD CO., LTD Trading Co. — Your trusted PP hollow board partner since 2015.</em>
    </p>
</div>
```

Respond ONLY with:
TITLE: <title>
EXCERPT: <excerpt>
TAGS: <tag1, tag2, tag3>
BODY: <full body html>
"""
        response = await self.agent.chat(prompt, temperature=0.7)

        # Parse response
        title = ""
        excerpt = ""
        tags = []
        body = ""

        lines = response.split("\n")
        in_body = False
        body_lines = []

        for line in lines:
            if line.startswith("TITLE:"):
                title = line.split(":", 1)[1].strip()
            elif line.startswith("EXCERPT:"):
                excerpt = line.split(":", 1)[1].strip()
            elif line.startswith("TAGS:"):
                tags_raw = line.split(":", 1)[1].strip()
                tags = [t.strip() for t in tags_raw.split(",")]
            elif line.startswith("BODY:"):
                in_body = True
                body_lines.append(line.split(":", 1)[1].strip())
            elif in_body:
                body_lines.append(line)

        if in_body:
            body = "\n".join(body_lines)

        if not title:
            title = topic
        if not excerpt:
            excerpt = f"Expert insights on {topic.lower()} from TXD CO., LTD Trading."
        if not tags:
            tags = ["PP hollow board", "packaging", topic.lower().replace(" ", "-")]

        # Build full HTML
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - TXD CO., LTD Blog</title>
<meta name="description" content="{excerpt}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<nav>
  <a href="../index.html" class="nav-logo">TXD<span> CO., LTD</span></a>
  <ul class="nav-links">
    <li><a href="../index.html">Home</a></li>
    <li><a href="../index.html#products">Products</a></li>
    <li><a href="../index.html#services">Services</a></li>
    <li><a href="index.html">Blog</a></li>
  </ul>
</nav>

<article class="post-article">
{body}
</article>

<footer>
  <p>&copy; 2026 <a href="../index.html">TXD CO., LTD Trading</a>. All rights reserved. | <a href="index.html">Blog</a></p>
</footer>

</body>
</html>"""

        return {
            "title": title,
            "slug": slug,
            "html": full_html,
            "excerpt": excerpt,
            "tags": tags,
            "date": date_str,
        }

    def save_post(self, post: dict) -> str:
        """Save post HTML to blog/{slug}.html."""
        BLOG_DIR.mkdir(exist_ok=True)
        filepath = BLOG_DIR / f"{post['slug']}.html"
        filepath.write_text(post["html"], encoding="utf-8")
        return str(filepath)

    def register_in_index(self, post: dict):
        """Register the post in blog/index.html's posts array."""
        index_path = BLOG_DIR / "index.html"
        if not index_path.exists():
            return

        content = index_path.read_text(encoding="utf-8")

        # Build the JS entry
        tags_str = ", ".join(f'"{t}"' for t in post["tags"])
        entry = f"""    {{
    title: "{post['title']}",
    date: "{post['date']}",
    url: "{post['slug']}.html",
    excerpt: "{post['excerpt']}",
    tags: [{tags_str}]
  }},
];"""

        # Replace the closing "];" with our entry
        if "];" in content:
            content = content.replace("];", entry)
            index_path.write_text(content, encoding="utf-8")

    async def run_daily(self) -> dict | None:
        """Run the daily blog generation. Returns post dict or None if skipped."""
        topic = self.pick_topic()

        # Check if already published today
        slug = topic.lower().replace(" ", "-").replace(":", "").replace("'", "").replace("&", "and")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        post_path = BLOG_DIR / f"{slug}.html"
        if post_path.exists():
            return None  # Already published

        post = await self.generate_post(topic)
        filepath = self.save_post(post)
        self.register_in_index(post)
        return post
