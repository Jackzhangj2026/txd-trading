"""Seed the website_templates table from the generated template files."""

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "website_templates"


def load_template_metadata() -> list[dict]:
    """Load template metadata from _metadata.json or define defaults."""
    meta_path = TEMPLATES_DIR / "_metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))

    # Fallback definition
    return [
        {"name": "minimal-corporate", "display_name": "Minimal Corporate", "display_name_zh": "\u7b80\u7ea6\u5546\u52a1", "category": "business"},
        {"name": "modern-tech", "display_name": "Modern Tech", "display_name_zh": "\u73b0\u4ee3\u79d1\u6280", "category": "tech"},
        {"name": "nature-green", "display_name": "Nature Green", "display_name_zh": "\u81ea\u7136\u7eff", "category": "eco"},
        {"name": "luxury-gold", "display_name": "Luxury Gold", "display_name_zh": "\u5962\u534e\u91d1", "category": "premium"},
        {"name": "startup-vibrant", "display_name": "Startup Vibrant", "display_name_zh": "\u521b\u4e1a\u6d3b\u529b", "category": "startup"},
        {"name": "industrial-bold", "display_name": "Industrial Bold", "display_name_zh": "\u5de5\u4e1a\u7c97\u72c2", "category": "industry"},
        {"name": "minimal-white", "display_name": "Pure White", "display_name_zh": "\u7eaf\u767d\u6781\u7b80", "category": "minimal"},
        {"name": "dark-elegance", "display_name": "Dark Elegance", "display_name_zh": "\u6697\u9ed1\u4f18\u96c5", "category": "dark"},
        {"name": "gradient-modern", "display_name": "Gradient Flow", "display_name_zh": "\u6e10\u53d8\u6d41\u52a8", "category": "modern"},
        {"name": "neo-brutalism", "display_name": "Neo Brutalism", "display_name_zh": "\u65b0\u7c97\u91ce\u4e3b\u4e49", "category": "bold"},
        {"name": "glassmorphism", "display_name": "Glassmorphism", "display_name_zh": "\u73bb\u7483\u62df\u6001", "category": "modern"},
        {"name": "cyberpunk", "display_name": "Cyberpunk", "display_name_zh": "\u8d5b\u535a\u670b\u514b", "category": "edgy"},
        {"name": "japanese-minimal", "display_name": "Japanese Zen", "display_name_zh": "\u548c\u98ce\u7985\u610f", "category": "zen"},
        {"name": "bold-typography", "display_name": "Bold Type", "display_name_zh": "\u5927\u5b57\u6392\u7248", "category": "editorial"},
        {"name": "card-based", "display_name": "Card Grid", "display_name_zh": "\u5361\u7247\u7f51\u683c", "category": "clean"},
        {"name": "magazine", "display_name": "Magazine", "display_name_zh": "\u6742\u5fd7\u98ce\u683c", "category": "editorial"},
        {"name": "retro-vintage", "display_name": "Retro Vintage", "display_name_zh": "\u590d\u53e4\u98ce", "category": "vintage"},
        {"name": "material-design", "display_name": "Material Design", "display_name_zh": "Material \u8bbe\u8ba1", "category": "google"},
        {"name": "brutalist", "display_name": "Brutalist Heavy", "display_name_zh": "\u7c97\u91ce\u4e3b\u4e49", "category": "raw"},
        {"name": "fluid-organic", "display_name": "Fluid Organic", "display_name_zh": "\u6d41\u4f53\u6709\u673a", "category": "creative"},
    ]


async def seed_templates(db_session):
    """Seed templates if table is empty."""
    from sqlalchemy import select, func
    from backend.models.website_template import WebsiteTemplate

    result = await db_session.execute(select(func.count()).select_from(WebsiteTemplate))
    count = result.scalar() or 0
    if count > 0:
        return {"seeded": 0, "reason": "templates already exist"}

    meta = load_template_metadata()
    seeded = 0
    for m in meta:
        name = m["name"]
        tpl_file = TEMPLATES_DIR / f"{name}.html"
        if not tpl_file.exists():
            continue
        tpl = WebsiteTemplate(
            name=name,
            display_name=m["display_name"],
            display_name_zh=m.get("display_name_zh", ""),
            category=m.get("category", "general"),
            description=f"{m['display_name']} — a {m.get('category', 'general')} style template for company websites.",
            popularity=0,
            active=True,
        )
        db_session.add(tpl)
        seeded += 1

    await db_session.commit()
    return {"seeded": seeded}
