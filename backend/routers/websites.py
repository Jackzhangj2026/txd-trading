"""Website and website-template API routes — multi-page, blog, products, image upload."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.website import Website
from backend.models.website_template import WebsiteTemplate
from backend.models.website_blog_post import WebsiteBlogPost
from backend.schemas.website import (
    WebsiteCreate, WebsiteUpdate, WebsiteResponse, WebsiteList,
    TemplateResponse, TemplateList,
    GenerateRequest, BatchGenerateRequest, DeployRequest,
    ProductAddRequest, ProductUpdateRequest,
    BlogPostCreate, BlogPostUpdate, BlogPostResponse, BlogPostList,
    BlogGenerateRequest,
)
from backend.services.website_generator import WebsiteGenerator

router = APIRouter(prefix="/api/websites", tags=["websites"])
generator = WebsiteGenerator()
TEMPLATES_DIR = Path(__file__).parent.parent / "website_templates"
UPLOAD_DIR = Path("generated_sites")



# ═══════════════════════════════════════════════════════════════════════════
#  TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/templates", response_model=TemplateList)
async def list_templates(category: str = None, page: int = 1, page_size: int = 50, db: AsyncSession = Depends(get_db)):
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
async def preview_template(template_id: str, page: str = "index", db: AsyncSession = Depends(get_db)):
    """Preview a template page with sample content."""
    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    sample_data = {
        "company_name": "Sample Trading Co., Ltd",
        "tagline": "Your Trusted Global Sourcing Partner Since 2015",
        "industry_name": "International Trade",
        "page_title": {"index":"Sample Trading Co., Ltd","products":"Our Products","about":"About Us","blog":"Blog","contact":"Contact Us"}.get(page, ""),
        "about_us": "<p>Sample Trading Co., Ltd is a professional international trading company with years of experience in global sourcing, export, and logistics management.</p><p>We are committed to providing high-quality products and exceptional service to clients worldwide.</p>",
        "services": [
            {"title": "Global Sourcing", "description": "Source high-quality products from verified suppliers worldwide."},
            {"title": "Quality Control", "description": "Comprehensive inspection at every stage of production."},
            {"title": "Logistics Management", "description": "End-to-end shipping and warehousing solutions."},
            {"title": "Trade Consulting", "description": "Expert guidance on international trade regulations."},
        ],
        "products": [
            {"title": "Premium Product A", "description": "High-quality product with competitive pricing for global markets.", "category": "category-1", "image_urls": []},
            {"title": "Premium Product B", "description": "Reliable and durable product trusted by clients worldwide.", "category": "category-1", "image_urls": []},
            {"title": "Premium Product C", "description": "Innovative solution designed for modern industry needs.", "category": "category-2", "image_urls": []},
            {"title": "Premium Product D", "description": "Cost-effective option without compromising on quality.", "category": "category-2", "image_urls": []},
        ],
        "blog_posts": [
            {"title": "Industry Trends 2025", "slug": "industry-trends-2025", "excerpt": "Latest trends and insights in the international trade industry.", "published_at": "2025-01-15", "cover_image": "", "tags": "[\"trends\", \"industry\"]"},
            {"title": "Quality Standards Guide", "slug": "quality-standards-guide", "excerpt": "A comprehensive guide to quality standards and certifications.", "published_at": "2025-01-10", "cover_image": "", "tags": "[\"quality\", \"standards\"]"},
        ],
        "contact_email": "info@sample-trading.com",
        "contact_phone": "+1 (555) 123-4567",
        "contact_address": "123 Trade Center, New York, NY 10001",
        "seo_keywords": ["trading", "global sourcing", "export", "import"],
        "seo_description": "Sample Trading Co., Ltd — Your trusted partner in global trade.",
        "logo_url": "", "hero_image_url": "", "favicon_url": "",
        "custom_css": "", "extra_pages": [],
        "industry_keywords": ["international trade", "sourcing"],
        "generated_at": "",
    }

    pages = generator.render_site(sample_data, tpl.name)
    html = pages.get(page) or pages.get("index", "")
    return HTMLResponse(content=html)


# ═══════════════════════════════════════════════════════════════════════════
#  WEBSITES CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.get("", response_model=WebsiteList)
async def list_websites(status: str = None, search: str = None, page: int = 1, page_size: int = 20,
                        db: AsyncSession = Depends(get_db)):
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
    enriched = []
    for site in items:
        resp = WebsiteResponse.model_validate(site)
        if site.template_id:
            tpl_name = (await db.execute(select(WebsiteTemplate.name).where(WebsiteTemplate.id == site.template_id))).scalar()
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
        tpl_name = (await db.execute(select(WebsiteTemplate.name).where(WebsiteTemplate.id == site.template_id))).scalar()
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


# ═══════════════════════════════════════════════════════════════════════════
#  CONTENT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_website(data: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate AI content and render ALL pages."""
    result = await db.execute(select(Website).where(Website.id == data.website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == site.template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    tpl.popularity = (tpl.popularity or 0) + 1

    # Load existing products so they're not overwritten
    existing_products = json.loads(site.products or "[]")

    try:
        content = await generator.generate_and_render(
            {
                "industry_keywords": site.industry_keywords,
                "company_name": site.company_name,
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

        site.company_name = content.get("company_name", site.company_name)
        site.tagline = content.get("tagline", site.tagline)
        site.about_us = content.get("about_us", site.about_us)
        site.services = content.get("services", site.services)

        # Merge products — keep existing, add new ones from LLM
        new_products = json.loads(content.get("products", "[]"))
        merged = existing_products + [p for p in new_products if p["title"] not in {ep["title"] for ep in existing_products}]
        site.products = json.dumps(merged)

        site.seo_keywords = content.get("seo_keywords", site.seo_keywords)
        site.seo_description = content.get("seo_description", site.seo_description)
        site.contact_email = content.get("contact_email", site.contact_email)
        site.contact_phone = content.get("contact_phone", site.contact_phone)
        site.contact_address = content.get("contact_address", site.contact_address)
        site.status = "generated"

        # Load blog posts for rendering
        blog_posts_result = await db.execute(
            select(WebsiteBlogPost).where(WebsiteBlogPost.website_id == site.id, WebsiteBlogPost.published == True)
            .order_by(WebsiteBlogPost.published_at.desc()).limit(20)
        )
        blog_posts = []
        for bp in blog_posts_result.scalars().all():
            blog_posts.append({
                "title": bp.title, "slug": bp.slug, "excerpt": bp.excerpt,
                "published_at": bp.published_at, "cover_image": bp.cover_image,
                "tags": bp.tags,
            })

        website_dict = {
            "company_name": site.company_name, "tagline": site.tagline,
            "about_us": site.about_us, "services": site.services,
            "products": site.products, "contact_email": site.contact_email,
            "contact_phone": site.contact_phone, "contact_address": site.contact_address,
            "seo_keywords": site.seo_keywords, "seo_description": site.seo_description,
            "industry_keywords": site.industry_keywords,
            "logo_url": site.logo_url, "hero_image_url": site.hero_image_url,
            "favicon_url": site.favicon_url, "custom_css": site.custom_css,
            "extra_pages": site.extra_pages, "generated_at": str(site.updated_at),
            "_blog_posts": json.dumps(blog_posts),
        }

        pages = generator.render_site(website_dict, tpl.name)
        output_dir = generator.save_site(pages, site.domain or site.company_name.lower().replace(" ", "-"))
        await db.commit()

        return {"status": "success", "website_id": site.id, "domain": site.domain, "pages": list(pages.keys()), "path": str(output_dir)}
    except Exception as e:
        site.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/batch-generate")
async def batch_generate(data: BatchGenerateRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == data.template_id, WebsiteTemplate.active))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    created = []
    for industry in data.industries[:data.count]:
        site = Website(template_id=data.template_id, company_name=f"{industry.title()} Trading Co., Ltd",
                       industry_keywords=json.dumps([industry]),
                       domain=f"{industry.lower().replace(' ', '-')}-trading", status="draft")
        db.add(site)
        await db.flush()
        created.append({"id": site.id, "company_name": site.company_name, "industry": industry})
    tpl.popularity = (tpl.popularity or 0) + len(created)
    await db.commit()
    return {"status": "success", "created": created}


# ═══════════════════════════════════════════════════════════════════════════
#  PREVIEW
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/preview/{website_id}")
async def preview_website(website_id: str, page: str = "index", db: AsyncSession = Depends(get_db)):
    """Preview a generated website page."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == site.template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    blog_posts_result = await db.execute(
        select(WebsiteBlogPost).where(WebsiteBlogPost.website_id == site.id, WebsiteBlogPost.published == True)
        .order_by(WebsiteBlogPost.published_at.desc()).limit(20)
    )
    blog_posts = [{"title": bp.title, "slug": bp.slug, "excerpt": bp.excerpt,
                   "published_at": bp.published_at, "cover_image": bp.cover_image, "tags": bp.tags}
                  for bp in blog_posts_result.scalars().all()]

    try:
        pages = generator.render_site({
            "company_name": site.company_name, "tagline": site.tagline,
            "about_us": site.about_us, "services": site.services,
            "products": site.products, "contact_email": site.contact_email,
            "contact_phone": site.contact_phone, "contact_address": site.contact_address,
            "seo_keywords": site.seo_keywords, "seo_description": site.seo_description,
            "industry_keywords": site.industry_keywords,
            "logo_url": site.logo_url, "hero_image_url": site.hero_image_url,
            "favicon_url": site.favicon_url, "custom_css": site.custom_css,
            "extra_pages": site.extra_pages, "generated_at": str(site.updated_at),
            "_blog_posts": json.dumps(blog_posts),
        }, tpl.name)
        html = pages.get(page, pages.get("index", ""))
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
#  IMAGE UPLOAD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{website_id}/upload-image")
async def upload_website_image(website_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload an image for a website's product gallery."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")

    domain = site.domain or site.company_name.lower().replace(" ", "-")
    img_dir = UPLOAD_DIR / domain / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        raise HTTPException(status_code=400, detail="Only jpg/png/gif/webp allowed")

    filepath = img_dir / f"{Path(file.filename).stem}{ext}"
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    url = f"/{domain}/images/{filepath.name}"
    return {"status": "uploaded", "url": url, "path": str(filepath)}


# ═══════════════════════════════════════════════════════════════════════════
#  PRODUCT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{website_id}/products")
async def list_website_products(website_id: str, db: AsyncSession = Depends(get_db)):
    """List products for a website."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    return {"products": json.loads(site.products or "[]")}


@router.post("/{website_id}/products")
async def add_website_product(website_id: str, data: ProductAddRequest, db: AsyncSession = Depends(get_db)):
    """Add a product to a website."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    products = json.loads(site.products or "[]")
    products.append({
        "title": data.title, "title_zh": data.title_zh,
        "description": data.description, "description_zh": data.description_zh,
        "category": data.category, "image_urls": json.loads(data.image_urls),
    })
    site.products = json.dumps(products)
    await db.commit()
    return {"status": "success", "products": products}


@router.put("/{website_id}/products/{product_index}")
async def update_website_product(website_id: str, product_index: int, data: ProductUpdateRequest,
                                  db: AsyncSession = Depends(get_db)):
    """Update a product by index."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    products = json.loads(site.products or "[]")
    if product_index < 0 or product_index >= len(products):
        raise HTTPException(status_code=404, detail="Product not found")
    update_data = data.model_dump(exclude_unset=True)
    if "image_urls" in update_data:
        update_data["image_urls"] = json.loads(update_data["image_urls"])
    products[product_index].update(update_data)
    site.products = json.dumps(products)
    await db.commit()
    return {"status": "success", "product": products[product_index]}


@router.delete("/{website_id}/products/{product_index}")
async def delete_website_product(website_id: str, product_index: int, db: AsyncSession = Depends(get_db)):
    """Delete a product by index."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    products = json.loads(site.products or "[]")
    if product_index < 0 or product_index >= len(products):
        raise HTTPException(status_code=404, detail="Product not found")
    products.pop(product_index)
    site.products = json.dumps(products)
    await db.commit()
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════════════════
#  BLOG MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{website_id}/blog", response_model=BlogPostList)
async def list_blog_posts(website_id: str, page: int = 1, page_size: int = 50,
                          db: AsyncSession = Depends(get_db)):
    """List blog posts for a website."""
    query = select(WebsiteBlogPost).where(WebsiteBlogPost.website_id == website_id)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(WebsiteBlogPost.published_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    return BlogPostList(items=items, total=total)


@router.post("/{website_id}/blog", response_model=BlogPostResponse, status_code=201)
async def create_blog_post(website_id: str, data: BlogPostCreate, db: AsyncSession = Depends(get_db)):
    """Create a blog post."""
    slug = data.title.lower().replace(" ", "-").replace(":", "").replace("'", "").replace("&", "and")
    slug = re.sub(r"[^a-z0-9-]", "", slug)[:80]
    from backend.models.website_blog_post import WebsiteBlogPost
    post = WebsiteBlogPost(
        website_id=website_id, title=data.title, slug=slug,
        body_html=data.body_html, excerpt=data.excerpt,
        tags=data.tags, cover_image=data.cover_image,
        published=data.published, published_at=datetime.now().strftime("%Y-%m-%d"),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


from datetime import datetime
import re


@router.post("/{website_id}/blog/generate")
async def generate_blog_post(website_id: str, data: BlogGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate a blog post via LLM for a specific website."""
    result = await db.execute(select(Website).where(Website.id == website_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await db.execute(select(WebsiteTemplate).where(WebsiteTemplate.id == site.template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        post_data = await generator.generate_blog_post(
            {"company_name": site.company_name, "industry_keywords": site.industry_keywords},
            topic=data.topic,
        )

        # Save to DB
        bp = WebsiteBlogPost(
            website_id=website_id, title=post_data["title"], slug=post_data["slug"],
            body_html=post_data["body_html"], excerpt=post_data["excerpt"],
            tags=post_data["tags"], published=True,
            published_at=post_data["published_at"],
        )
        db.add(bp)
        await db.commit()
        await db.refresh(bp)

        # Re-render site with updated blog
        blog_posts_result = await db.execute(
            select(WebsiteBlogPost).where(WebsiteBlogPost.website_id == website_id, WebsiteBlogPost.published == True)
            .order_by(WebsiteBlogPost.published_at.desc()).limit(20)
        )
        blog_posts = [{"title": bp2.title, "slug": bp2.slug, "excerpt": bp2.excerpt,
                       "published_at": bp2.published_at, "cover_image": bp2.cover_image, "tags": bp2.tags}
                      for bp2 in blog_posts_result.scalars().all()]

        website_dict = {
            "company_name": site.company_name, "tagline": site.tagline,
            "about_us": site.about_us, "services": site.services,
            "products": site.products, "contact_email": site.contact_email,
            "contact_phone": site.contact_phone, "contact_address": site.contact_address,
            "seo_keywords": site.seo_keywords, "seo_description": site.seo_description,
            "industry_keywords": site.industry_keywords,
            "logo_url": site.logo_url, "hero_image_url": site.hero_image_url,
            "favicon_url": site.favicon_url, "custom_css": site.custom_css,
            "extra_pages": site.extra_pages, "generated_at": str(datetime.now()),
            "_blog_posts": json.dumps(blog_posts),
        }
        pages = generator.render_site(website_dict, tpl.name)

        # Save blog post as separate HTML file
        domain = site.domain or site.company_name.lower().replace(" ", "-")
        blog_html = generator.render_blog_post_page(post_data, website_dict, tpl.name)
        blog_dir = UPLOAD_DIR / domain / "blog"
        blog_dir.mkdir(parents=True, exist_ok=True)
        (blog_dir / f"{post_data['slug']}.html").write_text(blog_html, encoding="utf-8")

        generator.save_site(pages, domain)

        return {"status": "success", "post": {"id": bp.id, "title": bp.title, "slug": bp.slug}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blog generation failed: {str(e)}")


@router.put("/{website_id}/blog/{post_id}", response_model=BlogPostResponse)
async def update_blog_post(website_id: str, post_id: str, data: BlogPostUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebsiteBlogPost).where(
        WebsiteBlogPost.id == post_id, WebsiteBlogPost.website_id == website_id
    ))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(post, key, value)
    await db.commit()
    await db.refresh(post)
    return post


@router.delete("/{website_id}/blog/{post_id}", status_code=204)
async def delete_blog_post(website_id: str, post_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebsiteBlogPost).where(
        WebsiteBlogPost.id == post_id, WebsiteBlogPost.website_id == website_id
    ))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    await db.delete(post)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  PRESETS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/presets/industries")
async def get_industry_presets():
    return {"presets": generator.get_presets()}


@router.get("/presets/blog-topics")
async def get_blog_topics():
    return {"topics": generator.get_blog_topics()}
