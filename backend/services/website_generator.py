"""Website content generator — multi-page sites with LLM content + blog."""

import json
import re
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from backend.agents import TradeAgent

TEMPLATES_DIR = Path(__file__).parent.parent / "website_templates"
GENERATED_DIR = Path("generated_sites")

INDUSTRY_PRESETS = [
    {"industry": "packaging", "keywords": ["PP hollow board", "corrugated plastic", "packaging solutions"], "zh": "\u5305\u88c5"},
    {"industry": "logistics", "keywords": ["logistics equipment", "supply chain", "warehouse"], "zh": "\u7269\u6d41"},
    {"industry": "construction", "keywords": ["building materials", "construction", "PP products"], "zh": "\u5efa\u7b51"},
    {"industry": "agriculture", "keywords": ["agricultural products", "greenhouse", "farming"], "zh": "\u519c\u4e1a"},
    {"industry": "electronics", "keywords": ["electronic components", "ESD protection", "printed circuit"], "zh": "\u7535\u5b50"},
    {"industry": "automotive", "keywords": ["auto parts", "automotive packaging", "car accessories"], "zh": "\u6c7d\u8f66"},
    {"industry": "food", "keywords": ["food packaging", "food grade", "packaging containers"], "zh": "\u98df\u54c1"},
    {"industry": "chemical", "keywords": ["chemical trading", "industrial chemicals", "raw materials"], "zh": "\u5316\u5de5"},
    {"industry": "textile", "keywords": ["textile products", "fabric", "garment accessories"], "zh": "\u7eba\u7ec7"},
    {"industry": "medical", "keywords": ["medical devices", "healthcare", "medical supplies"], "zh": "\u533b\u7597"},
]

BLOG_TOPICS = [
    "Industry Trends and Market Analysis",
    "Product Quality Standards and Certifications",
    "Supply Chain Best Practices",
    "Export Documentation Guide",
    "Packaging Innovation",
    "Cost Optimization Strategies",
    "Global Trade Regulations Update",
    "Customer Success Stories",
    "New Product Launch Announcement",
    "Sustainability in our Industry",
    "Quality Control Processes",
    "Logistics and Shipping Guide",
]


class WebsiteGenerator:
    """Multi-page website generator with LLM content, blog, and products."""

    def __init__(self):
        self.agent = TradeAgent(
            system_prompt="You are an expert B2B marketing copywriter for international trade companies. "
                          "Generate professional, SEO-optimized website content."
        )
        self.jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    @staticmethod
    def _safe_json(val, default=None):
        """Parse JSON safely — handles string, bytes, or already-parsed list/dict."""
        if isinstance(val, (list, dict)):
            return val
        if val and isinstance(val, (str, bytes)):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        return default if default is not None else ([] if isinstance(default, list) else "[]")

    def get_template_names(self) -> list[str]:
        """List available template folder names."""
        if not TEMPLATES_DIR.exists():
            return []
        return sorted([d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()])

    def template_has_page(self, template_name: str, page: str) -> bool:
        """Check if a template folder has a specific page file."""
        return (TEMPLATES_DIR / template_name / f"{page}.html").exists()

    # ─── Content Generation ──────────────────────────────────────────────

    async def generate_content(self, industry_keywords: list[str], lang: str = "en",
                                company_name_hint: str = "", temperature: float = 0.7) -> dict:
        """Generate full website content including products via LLM."""
        lang_label = "Chinese" if lang == "zh" else "English"
        keywords_str = ", ".join(industry_keywords)

        prompt = f"""Generate complete {lang_label} website content for a B2B trading/export company.

Industry keywords: {keywords_str}
Company name hint: {company_name_hint or "Auto-generate a professional trading company name"}

Generate the following content (respond in {lang_label} only):

COMPANY_NAME: A professional trading company name
TAGLINE: A compelling tagline (1 sentence, max 15 words)
ABOUT_US: 2-3 paragraphs of HTML about the company (use <p> tags)
SERVICES: JSON array of 4-6 services, each with "title" and "description"
PRODUCTS: JSON array of 4-8 products, each with "title" (product name), "description" (2 sentence description), "category" (product category)
SEO_KEYWORDS: JSON array of 8-12 SEO keywords
SEO_DESCRIPTION: A meta description (max 160 chars)
CONTACT_EMAIL: A professional email address
CONTACT_PHONE: A phone number with country code
CONTACT_ADDRESS: A generic business address

Format your response exactly as:
COMPANY_NAME: <value>
TAGLINE: <value>
ABOUT_US: <html>
SERVICES: <json array>
PRODUCTS: <json array>
SEO_KEYWORDS: <json array>
SEO_DESCRIPTION: <value>
CONTACT_EMAIL: <value>
CONTACT_PHONE: <value>
CONTACT_ADDRESS: <value>
"""
        response = await self.agent.chat(prompt, temperature=temperature)
        result = self._parse_response(response, lang)
        result["industry_keywords"] = json.dumps(industry_keywords)

        # If no products were generated, provide defaults
        products = json.loads(result.get("products", "[]"))
        if not products:
            for kw in industry_keywords[:4]:
                products.append({
                    "title": f"Premium {kw.title()}",
                    "description": f"High-quality {kw} sourced from trusted manufacturers with competitive pricing and reliable delivery.",
                    "category": kw,
                    "image_urls": []
                })
            result["products"] = json.dumps(products)

        return result

    def _parse_response(self, response: str, lang: str) -> dict:
        """Parse LLM response into structured dict."""
        result = {
            "company_name": "", "company_name_zh": "",
            "tagline": "", "tagline_zh": "",
            "about_us": "", "about_us_zh": "",
            "services": "[]", "products": "[]",
            "seo_keywords": "[]", "seo_description": "",
            "contact_email": "", "contact_phone": "", "contact_address": "",
        }
        prefixes = {
            "COMPANY_NAME": "company_name", "TAGLINE": "tagline",
            "ABOUT_US": "about_us", "SERVICES": "services",
            "PRODUCTS": "products",
            "SEO_KEYWORDS": "seo_keywords", "SEO_DESCRIPTION": "seo_description",
            "CONTACT_EMAIL": "contact_email", "CONTACT_PHONE": "contact_phone",
            "CONTACT_ADDRESS": "contact_address",
        }
        for prefix, key in prefixes.items():
            pattern = rf"{prefix}:\s*(.+?)(?=\n[A-Z_]+\:|$)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                result[key] = match.group(1).strip()

        if lang == "zh":
            result["company_name_zh"] = result.pop("company_name", "")
            result["tagline_zh"] = result.pop("tagline", "")
            result["about_us_zh"] = result.pop("about_us", "")
            result["company_name"] = result["tagline"] = result["about_us"] = ""

        for json_field in ["services", "products", "seo_keywords"]:
            val = result.get(json_field, "[]")
            try:
                json.loads(val)
            except (json.JSONDecodeError, TypeError):
                arr_match = re.search(r'\[.*?\]', val, re.DOTALL)
                result[json_field] = arr_match.group() if arr_match else "[]"

        return result

    # ─── Multi-page Rendering ────────────────────────────────────────────

    def render_site(self, website: dict, template_name: str) -> dict[str, str]:
        """Render ALL pages of a site. Returns {page_name: html_string}."""
        template_folder = TEMPLATES_DIR / template_name
        if not template_folder.is_dir():
            raise FileNotFoundError(f"Template folder '{template_name}' not found")

        services = self._safe_json(website.get("services", "[]"))
        products = self._safe_json(website.get("products", "[]"))
        seo_keywords = self._safe_json(website.get("seo_keywords", "[]"))
        industry_keywords = self._safe_json(website.get("industry_keywords", "[]"))
        blog_posts = self._safe_json(website.get("_blog_posts", "[]"))

        context = {
            "company_name": website.get("company_name", ""),
            "company_name_zh": website.get("company_name_zh", ""),
            "tagline": website.get("tagline", ""),
            "tagline_zh": website.get("tagline_zh", ""),
            "about_us": website.get("about_us", ""),
            "about_us_zh": website.get("about_us_zh", ""),
            "services": services,
            "products": products,
            "contact_email": website.get("contact_email", ""),
            "contact_phone": website.get("contact_phone", ""),
            "contact_address": website.get("contact_address", ""),
            "seo_keywords": seo_keywords,
            "seo_description": website.get("seo_description", ""),
            "logo_url": website.get("logo_url", ""),
            "hero_image_url": website.get("hero_image_url", ""),
            "favicon_url": website.get("favicon_url", ""),
            "extra_pages": self._safe_json(website.get("extra_pages", "[]")),
            "industry_keywords": industry_keywords,
            "industry_name": industry_keywords[0] if industry_keywords else "",
            "custom_css": website.get("custom_css", ""),
            "generated_at": website.get("generated_at", ""),
            "blog_posts": blog_posts,
        }

        pages = {}
        for page_name in ["index", "products", "about", "blog", "contact"]:
            page_path = template_folder / f"{page_name}.html"
            if not page_path.exists():
                continue
            page_context = dict(context)
            page_context["page_title"] = {
                "index": website.get("company_name", ""),
                "products": "Our Products",
                "about": "About Us",
                "blog": "Blog",
                "contact": "Contact Us",
            }.get(page_name, "")
            template_code = page_path.read_text(encoding="utf-8")
            template = self.jinja_env.from_string(template_code)
            pages[page_name] = template.render(**page_context)

        return pages

    def save_site(self, pages: dict[str, str], domain: str) -> Path:
        """Save all pages to disk. Returns the output directory."""
        output_dir = GENERATED_DIR / domain
        output_dir.mkdir(parents=True, exist_ok=True)

        for page_name, html in pages.items():
            (output_dir / f"{page_name}.html").write_text(html, encoding="utf-8")

        # Write a simple _config.yml for GitHub Pages
        (output_dir / "_config.yml").write_text("""theme: null
""", encoding="utf-8")

        return output_dir

    async def generate_and_render(self, website: dict, template_name: str,
                                   lang: str = "en", temperature: float = 0.7) -> dict:
        """Generate content then render all pages."""
        industry_keywords = self._safe_json(website.get("industry_keywords", "[]"))
        company_hint = website.get("company_name", "")

        content = await self.generate_content(industry_keywords, lang, company_hint, temperature)
        content["generated_at"] = str(datetime.now())

        for k, v in content.items():
            website[k] = v

        pages = self.render_site(website, template_name)
        content["pages"] = pages
        return content

    # ─── Blog Generation ─────────────────────────────────────────────────

    async def generate_blog_post(self, website: dict, topic: str = "", lang: str = "en") -> dict:
        """Generate a single blog post for a specific website."""
        company = website.get("company_name", "Our Company")
        industry = ", ".join(self._safe_json(website.get("industry_keywords", "[]")))
        lang_label = "Chinese" if lang == "zh" else "English"

        if not topic:
            # Pick a topic based on day of month
            day = datetime.now().day
            topic = BLOG_TOPICS[day % len(BLOG_TOPICS)]

        prompt = f"""Write a professional blog post in {lang_label} for {company}, a company in the {industry} industry.

Topic: {topic}

Generate:
TITLE: SEO-optimized blog post title
EXCERPT: One sentence summary (max 200 chars)
TAGS: comma-separated keywords (3-5)
BODY: Complete HTML content with <h2>, <p>, <ul> tags. Write 3-4 sections.
Include a call-to-action at the end about contacting {company} for more information.

Respond ONLY with:
TITLE: <title>
EXCERPT: <excerpt>
TAGS: <tag1, tag2, tag3>
BODY: <full html body>
"""
        response = await self.agent.chat(prompt, temperature=0.7)
        return self._parse_blog_response(response, topic)

    def _parse_blog_response(self, response: str, default_topic: str) -> dict:
        """Parse blog post from LLM response."""
        result = {"title": default_topic, "excerpt": "", "tags": "[]", "body_html": ""}
        lines = response.split("\n")
        in_body = False
        body_lines = []

        for line in lines:
            if line.startswith("TITLE:"):
                result["title"] = line.split(":", 1)[1].strip()
            elif line.startswith("EXCERPT:"):
                result["excerpt"] = line.split(":", 1)[1].strip()
            elif line.startswith("TAGS:"):
                tags_raw = line.split(":", 1)[1].strip()
                result["tags"] = json.dumps([t.strip() for t in tags_raw.split(",")])
            elif line.startswith("BODY:"):
                in_body = True
                body_lines.append(line.split(":", 1)[1].strip())
            elif in_body:
                body_lines.append(line)

        if in_body:
            result["body_html"] = "\n".join(body_lines)

        # Build slug
        slug = result["title"].lower().replace(" ", "-").replace(":", "").replace("'", "").replace("&", "and")
        slug = re.sub(r"[^a-z0-9-]", "", slug)[:80]
        result["slug"] = slug
        result["published_at"] = datetime.now().strftime("%Y-%m-%d")
        return result

    def render_blog_post_page(self, post: dict, website: dict, template_name: str) -> str:
        """Render a single blog post as a complete HTML page."""
        template_folder = TEMPLATES_DIR / template_name
        blog_post_template = template_folder / "blog.html"
        if not blog_post_template.exists():
            return ""

        company = website.get("company_name", "")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{post['title']} — {company} Blog</title>
<meta name="description" content="{post.get('excerpt', '')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
body {{ font-family: 'Inter', sans-serif; line-height: 1.8; max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; }}
h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
.post-meta {{ color: #888; font-size: 0.9rem; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem; }}
.post-body h2 {{ margin-top: 2rem; }}
.post-body p {{ margin-bottom: 1rem; }}
.back-link {{ display: inline-block; margin-bottom: 2rem; color: #3182ce; }}
.cta-box {{ background: #f7fafc; padding: 1.5rem; border-radius: 8px; margin: 2rem 0; text-align: center; }}
.cta-box .btn {{ display: inline-block; background: #3182ce; color: white; padding: 0.75rem 2rem; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 0.5rem; }}
footer {{ margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #eee; text-align: center; font-size: 0.85rem; color: #888; }}
</style>
</head>
<body>
<a href="../blog.html" class="back-link">&larr; Back to Blog</a>
<h1>{post['title']}</h1>
<div class="post-meta">Published: {post.get('published_at', '')}</div>
<div class="post-body">{post['body_html']}</div>
<div class="cta-box">
  <p><strong>Interested in learning more?</strong></p>
  <p>Contact our team for expert advice and competitive quotes.</p>
  <a href="../contact.html" class="btn">Contact Us</a>
</div>
<footer>
  <p>&copy; 2025 <a href="../index.html">{company}</a>. All rights reserved.</p>
</footer>
</body>
</html>"""

    # ─── Presets ──────────────────────────────────────────────────────────

    def get_presets(self) -> list[dict]:
        return INDUSTRY_PRESETS

    def get_blog_topics(self) -> list[str]:
        return BLOG_TOPICS
