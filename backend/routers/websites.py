"""Website and website-template API routes."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.website import Website
from backend.models.website_template import WebsiteTemplate
from backend.schemas.website import (
    WebsiteCreate, WebsiteUpdate, WebsiteResponse, WebsiteList,
    TemplateResponse, TemplateList,
    GenerateRequest, BatchGenerateRequest, DeployRequest,
)
from backend.services.website_generator import WebsiteGenerator

router = APIRouter(prefix="/api/websites", tags=["websites"])
generator = WebsiteGenerator()
TEMPLATES_DIR = Path(__file__).parent.parent / "website_templates"


# ─── Website Templates ──────────────────────────────────────────────────────

@router.get("/templates", response_model=TemplateList)
async def list_templates(
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(WebsiteTemplate).where(WebsiteTemplate.active)
    if category:
        query = query.where(WebsiteTemplate.category == category)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(WebsiteTemplate.popularity.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    return TemplateList(items=items, total=total)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.get("/templates/{template_id}/preview")
async def preview_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """Show a preview of a template with sample content."""
    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    template_path = TEMPLATES_DIR / f"{tpl.name}.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")

    sample_data = {
        "company_name": "Sample Trading Co., Ltd",
        "tagline": "Your Trusted Global Sourcing Partner Since 2015",
        "industry_name": "International Trade",
        "about_us": "<p>Sample Trading Co., Ltd is a professional international trading company with years of experience in global sourcing, export, and logistics management.</p><p>We are committed to providing high-quality products and exceptional service to clients worldwide.</p>",
        "services": [
            {"title": "Global Sourcing", "description": "Source high-quality products from verified suppliers worldwide with competitive pricing."},
            {"title": "Quality Control", "description": "Comprehensive inspection and quality assurance at every stage of production."},
            {"title": "Logistics Management", "description": "End-to-end shipping, customs clearance, and warehousing solutions."},
            {"title": "Trade Consulting", "description": "Expert guidance on international trade regulations, documentation, and market entry."},
        ],
        "contact_email": "info@sample-trading.com",
        "contact_phone": "+1 (555) 123-4567",
        "contact_address": "123 Trade Center, New York, NY 10001",
        "seo_keywords": ["trading", "global sourcing", "export", "import", "international trade"],
        "seo_description": "Sample Trading Co., Ltd — Your trusted partner in global trade and sourcing.",
        "logo_url": "",
        "hero_image_url": "",
        "favicon_url": "",
        "custom_css": "",
        "extra_pages": [],
        "industry_keywords": ["international trade", "sourcing"],
        "generated_at": "",
    }

    html = generator.render_site(sample_data, tpl.name)
    return HTMLResponse(content=html)


# ─── Websites ───────────────────────────────────────────────────────────────

@router.get("", response_model=WebsiteList)
async def list_websites(
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Website)
    if status:
        query = query.where(Website.status == status)
    if search:
        query = query.where(Website.company_name.ilike(f"%{search}%"))
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Website.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    # Enrich with template name
    enriched = []
    for site in items:
        resp = WebsiteResponse.model_validate(site)
        if site.template_id:
            tpl_result = await db.execute(select(WebsiteTemplate.name).where(WebsiteTemplate.id == site.template_id))
            tpl_name = tpl_result.scalar()
            resp.template_name = tpl_name or ""
        enriched.append(resp)

    return WebsiteList(items=enriched, total=total)


@router.get("/{website_id}", response_model=WebsiteResponse)
async def get_website(website_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    resp = WebsiteResponse.model_validate(site)
    if site.template_id:
        tpl_result = await db.execute(select(WebsiteTemplate.name).where(WebsiteTemplate.id == site.template_id))
        tpl_name = tpl_result.scalar()
        resp.template_name = tpl_name or ""
    return resp


@router.post("", response_model=WebsiteResponse, status_code=201)
async def create_website(data: WebsiteCreate, db: AsyncSession = Depends(get_db)):
    site = Website(**data.model_dump())
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.put("/{website_id}", response_model=WebsiteResponse)
async def update_website(website_id: str, data: WebsiteUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(site, key, value)
    await db.commit()
    await db.refresh(site)
    return site


@router.delete("/{website_id}", status_code=204)
async def delete_website(website_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    site.active = False
    await db.commit()


# ─── Generation ─────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_website(data: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate AI content for a website and render it into its template."""
    result = await db.execute(select(Website).where(Website.id == data.website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == site.template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Update popularity
    tpl.popularity = (tpl.popularity or 0) + 1

    try:
        content = await generator.generate_and_render(
            {
                "industry_keywords": site.industry_keywords,
                "company_name": site.company_name,
                "template_id": site.template_id,
                "extra_pages": site.extra_pages,
                "logo_url": site.logo_url,
                "hero_image_url": site.hero_image_url,
                "favicon_url": site.favicon_url,
                "custom_css": site.custom_css,
            },
            tpl.name,
            lang=data.lang,
            temperature=data.temperature,
        )

        # Save generated content to website
        site.company_name = content.get("company_name", site.company_name)
        site.company_name_zh = content.get("company_name_zh", site.company_name_zh)
        site.tagline = content.get("tagline", site.tagline)
        site.tagline_zh = content.get("tagline_zh", site.tagline_zh)
        site.about_us = content.get("about_us", site.about_us)
        site.about_us_zh = content.get("about_us_zh", site.about_us_zh)
        site.services = content.get("services", site.services)
        site.seo_keywords = content.get("seo_keywords", site.seo_keywords)
        site.seo_description = content.get("seo_description", site.seo_description)
        site.contact_email = content.get("contact_email", site.contact_email)
        site.contact_phone = content.get("contact_phone", site.contact_phone)
        site.contact_address = content.get("contact_address", site.contact_address)
        site.status = "generated"

        # Save HTML file
        output_path = generator.save_site(content.get("html", ""), site.domain or site.company_name.lower().replace(" ", "-"))
        await db.commit()

        return {
            "status": "success",
            "website_id": site.id,
            "domain": site.domain,
            "html_path": str(output_path),
        }
    except Exception as e:
        site.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/batch-generate")
async def batch_generate(data: BatchGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Batch generate multiple websites from industry presets."""
    # Get or verify template
    result = await db.execute(select(WebsiteTemplate).where(
        WebsiteTemplate.id == data.template_id, WebsiteTemplate.active
    ))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    created = []
    for industry in data.industries[:data.count]:
        site = Website(
            template_id=data.template_id,
            company_name=f"{industry.title()} Trading Co., Ltd",
            industry_keywords=json.dumps([industry]),
            domain=f"{industry.lower().replace(' ', '-')}-trading",
            status="draft",
        )
        db.add(site)
        await db.flush()
        created.append({
            "id": site.id,
            "company_name": site.company_name,
            "industry": industry,
        })

    tpl.popularity = (tpl.popularity or 0) + len(created)
    await db.commit()

    return {"status": "success", "created": created}


# ─── Industry Presets ──────────────────────────────────────────────────────

@router.get("/presets/industries")
async def get_industry_presets():
    """Get preset industries for batch generation."""
    return {"presets": generator.get_presets()}


from fastapi.responses import HTMLResponse

# ─── Preview ────────────────────────────────────────────────────────────────

@router.get("/preview/{website_id}")
async def preview_generated_website(website_id: str, db: AsyncSession = Depends(get_db)):
    """Preview a generated website by re-rendering from stored content."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == site.template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        html = generator.render_site({
            "company_name": site.company_name,
            "company_name_zh": site.company_name_zh,
            "tagline": site.tagline,
            "tagline_zh": site.tagline_zh,
            "about_us": site.about_us,
            "about_us_zh": site.about_us_zh,
            "services": site.services,
            "contact_email": site.contact_email,
            "contact_phone": site.contact_phone,
            "contact_address": site.contact_address,
            "seo_keywords": site.seo_keywords,
            "seo_description": site.seo_description,
            "logo_url": site.logo_url,
            "hero_image_url": site.hero_image_url,
            "favicon_url": site.favicon_url,
            "custom_css": site.custom_css,
            "extra_pages": site.extra_pages,
            "industry_keywords": site.industry_keywords,
            "generated_at": str(site.updated_at),
        }, tpl.name)
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")
