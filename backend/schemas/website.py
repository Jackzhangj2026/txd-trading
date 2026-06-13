"""Website and WebsiteTemplate Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel


# ─── Templates ──────────────────────────────────────────────────────────────

class TemplateResponse(BaseModel):
    id: str
    name: str
    display_name: str
    display_name_zh: str
    category: str
    thumbnail: str
    description: str
    css_variables: str
    popularity: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TemplateList(BaseModel):
    items: list[TemplateResponse]
    total: int


# ─── Websites ───────────────────────────────────────────────────────────────

class WebsiteCreate(BaseModel):
    template_id: str
    domain: str = ""
    company_name: str = ""
    company_name_zh: str = ""
    industry_keywords: str = "[]"
    tagline: str = ""
    tagline_zh: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    contact_address: str = ""
    logo_url: str = ""
    hero_image_url: str = ""
    favicon_url: str = ""


class WebsiteUpdate(BaseModel):
    template_id: str | None = None
    domain: str | None = None
    company_name: str | None = None
    company_name_zh: str | None = None
    industry_keywords: str | None = None
    tagline: str | None = None
    tagline_zh: str | None = None
    about_us: str | None = None
    about_us_zh: str | None = None
    services: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_address: str | None = None
    seo_keywords: str | None = None
    seo_description: str | None = None
    custom_css: str | None = None
    extra_pages: str | None = None
    logo_url: str | None = None
    hero_image_url: str | None = None
    favicon_url: str | None = None
    status: str | None = None
    github_repo: str | None = None
    deploy_url: str | None = None
    active: bool | None = None


class WebsiteResponse(BaseModel):
    id: str
    template_id: str
    domain: str
    company_name: str
    company_name_zh: str
    industry_keywords: str
    tagline: str
    tagline_zh: str
    about_us: str
    about_us_zh: str
    services: str
    contact_email: str
    contact_phone: str
    contact_address: str
    seo_keywords: str
    seo_description: str
    custom_css: str
    extra_pages: str
    logo_url: str
    hero_image_url: str
    favicon_url: str
    status: str
    github_repo: str
    deploy_url: str
    active: bool
    created_at: datetime
    updated_at: datetime
    template_name: str = ""  # populated by join
    model_config = {"from_attributes": True}


class WebsiteList(BaseModel):
    items: list[WebsiteResponse]
    total: int


# ─── Generation Request ─────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    website_id: str
    lang: str = "en"  # en or zh
    temperature: float = 0.7


class BatchGenerateRequest(BaseModel):
    template_id: str
    count: int = 5
    industries: list[str]
    lang: str = "en"


class DeployRequest(BaseModel):
    website_id: str
    repo_name: str = ""  # optional override
