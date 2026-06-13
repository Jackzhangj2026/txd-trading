"""Website content generator — uses LLM to generate company website content."""

import json
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from backend.agents import TradeAgent

TEMPLATES_DIR = Path(__file__).parent.parent / "website_templates"
GENERATED_DIR = Path("generated_sites")

# Industry presets for batch generation
INDUSTRY_PRESETS = [
    {"industry": "packaging", "keywords": ["PP hollow board", "corrugated plastic", "packaging solutions"], "zh": "包装"},
    {"industry": "logistics", "keywords": ["logistics equipment", "supply chain", "warehouse"], "zh": "物流"},
    {"industry": "construction", "keywords": ["building materials", "construction", "PP products"], "zh": "建筑"},
    {"industry": "agriculture", "keywords": ["agricultural products", "greenhouse", "farming"], "zh": "农业"},
    {"industry": "electronics", "keywords": ["electronic components", "ESD protection", "printed circuit"], "zh": "电子"},
    {"industry": "automotive", "keywords": ["auto parts", "automotive packaging", "car accessories"], "zh": "汽车"},
    {"industry": "food", "keywords": ["food packaging", "food grade", "packaging containers"], "zh": "食品"},
    {"industry": "chemical", "keywords": ["chemical trading", "industrial chemicals", "raw materials"], "zh": "化工"},
    {"industry": "textile", "keywords": ["textile products", "fabric", "garment accessories"], "zh": "纺织"},
    {"industry": "medical", "keywords": ["medical devices", "healthcare", "medical supplies"], "zh": "医疗"},
]


class WebsiteGenerator:
    """Generates complete company website content and renders into templates."""

    def __init__(self):
        self.agent = TradeAgent(
            system_prompt="You are an expert B2B marketing copywriter specializing in creating compelling "
                          "company websites for international trade businesses. Generate professional, "
                          "SEO-optimized content that converts visitors into leads."
        )
        self.jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    def get_template_names(self) -> list[str]:
        """List available template names (files without .html in templates dir)."""
        if not TEMPLATES_DIR.exists():
            return []
        return sorted([f.stem for f in TEMPLATES_DIR.glob("*.html")])

    async def generate_content(self, industry_keywords: list[str], lang: str = "en",
                                company_name_hint: str = "", temperature: float = 0.7) -> dict:
        """Generate full website content via LLM."""
        lang_label = "Chinese" if lang == "zh" else "English"
        keywords_str = ", ".join(industry_keywords)

        prompt = f"""Generate complete {lang_label} website content for a B2B trading/export company.

Industry keywords: {keywords_str}
Company name hint: {company_name_hint or "Auto-generate a professional trading company name"}

Generate the following content (respond in {lang_label} only):

COMPANY_NAME: A professional trading company name
TAGLINE: A compelling tagline (1 sentence, max 15 words)
ABOUT_US: 2-3 paragraphs of HTML about the company (use <p> tags). Focus on expertise, global reach, quality commitment.
SERVICES: JSON array of 4-6 services offered, each with "title" and "description"
SEO_KEYWORDS: JSON array of 8-12 SEO keywords relevant to this company
SEO_DESCRIPTION: A meta description (max 160 chars)
CONTACT_EMAIL: A professional email address
CONTACT_PHONE: A phone number with country code
CONTACT_ADDRESS: A generic business address

Format your response exactly as:
COMPANY_NAME: <value>
TAGLINE: <value>
ABOUT_US: <html>
SERVICES: <json array>
SEO_KEYWORDS: <json array>
SEO_DESCRIPTION: <value>
CONTACT_EMAIL: <value>
CONTACT_PHONE: <value>
CONTACT_ADDRESS: <value>
"""
        response = await self.agent.chat(prompt, temperature=temperature)

        # Parse structured response
        result = self._parse_response(response, lang)
        result["industry_keywords"] = json.dumps(industry_keywords)
        return result

    def _parse_response(self, response: str, lang: str) -> dict:
        """Parse LLM response into structured dict."""
        result = {
            "company_name": "",
            "company_name_zh": "",
            "tagline": "",
            "tagline_zh": "",
            "about_us": "",
            "about_us_zh": "",
            "services": "[]",
            "seo_keywords": "[]",
            "seo_description": "",
            "contact_email": "",
            "contact_phone": "",
            "contact_address": "",
        }

        # Parse by prefix
        parsers = {
            "COMPANY_NAME": "company_name",
            "TAGLINE": "tagline",
            "ABOUT_US": "about_us",
            "SERVICES": "services",
            "SEO_KEYWORDS": "seo_keywords",
            "SEO_DESCRIPTION": "seo_description",
            "CONTACT_EMAIL": "contact_email",
            "CONTACT_PHONE": "contact_phone",
            "CONTACT_ADDRESS": "contact_address",
        }

        for prefix, key in parsers.items():
            pattern = rf"{prefix}:\s*(.+?)(?=\n[A-Z_]+\:|$)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                value = match.group(1).strip()
                result[key] = value

        # If zh, put in zh fields
        if lang == "zh":
            result["company_name_zh"] = result.pop("company_name", "")
            result["tagline_zh"] = result.pop("tagline", "")
            result["about_us_zh"] = result.pop("about_us", "")
            result["company_name"] = ""
            result["tagline"] = ""
            result["about_us"] = ""

        # Validate JSON fields
        for json_field in ["services", "seo_keywords"]:
            val = result.get(json_field, "[]")
            try:
                json.loads(val)
            except (json.JSONDecodeError, TypeError):
                # Try to extract JSON array from the value
                arr_match = re.search(r'\[.*?\]', val, re.DOTALL)
                if arr_match:
                    result[json_field] = arr_match.group()
                else:
                    result[json_field] = "[]"

        return result

    def render_site(self, website: dict, template_name: str, css_variables: dict | None = None) -> str:
        """Render a full website HTML from template + content."""
        template_path = TEMPLATES_DIR / f"{template_name}.html"
        if not template_path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found")

        services = json.loads(website.get("services", "[]"))
        seo_keywords = json.loads(website.get("seo_keywords", "[]"))
        extra_pages = json.loads(website.get("extra_pages", "[]"))
        industry_keywords = json.loads(website.get("industry_keywords", "[]"))

        template_code = template_path.read_text(encoding="utf-8")
        template = self.jinja_env.from_string(template_code)

        html = template.render(
            # Content
            company_name=website.get("company_name", ""),
            company_name_zh=website.get("company_name_zh", ""),
            tagline=website.get("tagline", ""),
            tagline_zh=website.get("tagline_zh", ""),
            about_us=website.get("about_us", ""),
            about_us_zh=website.get("about_us_zh", ""),
            services=services,
            contact_email=website.get("contact_email", ""),
            contact_phone=website.get("contact_phone", ""),
            contact_address=website.get("contact_address", ""),
            seo_keywords=seo_keywords,
            seo_description=website.get("seo_description", ""),

            # Media
            logo_url=website.get("logo_url", ""),
            hero_image_url=website.get("hero_image_url", ""),
            favicon_url=website.get("favicon_url", ""),

            # Extra pages
            extra_pages=extra_pages,

            # Industry context
            industry_keywords=industry_keywords,
            industry_name=industry_keywords[0] if industry_keywords else "",

            # Custom CSS overrides
            custom_css=website.get("custom_css", ""),

            # Version
            generated_at=website.get("generated_at", ""),
        )
        return html

    def save_site(self, html: str, domain: str) -> Path:
        """Save generated website to disk."""
        output_dir = GENERATED_DIR / domain
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / "index.html"
        filepath.write_text(html, encoding="utf-8")
        return filepath

    async def generate_and_render(self, website: dict, template_name: str,
                                   lang: str = "en", temperature: float = 0.7) -> dict:
        """One-step: generate content then render into template. Returns full result."""
        industry_keywords = json.loads(website.get("industry_keywords", "[]"))
        company_hint = website.get("company_name", "")

        content = await self.generate_content(industry_keywords, lang, company_hint, temperature)
        content["generated_at"] = str(__import__("datetime").datetime.now())

        # Merge generated content back
        for k, v in content.items():
            website[k] = v

        html = self.render_site(website, template_name)
        content["html"] = html
        return content

    def get_presets(self) -> list[dict]:
        """Get industry presets for batch generation UI."""
        return INDUSTRY_PRESETS
