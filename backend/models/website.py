"""Website model — a generated company website ready for deployment."""

from sqlalchemy import String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Website(UUIDMixin, TimestampMixin, Base):
    """A generated company website — one per target market / domain."""

    __tablename__ = "websites"

    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("website_templates.id"), nullable=False)

    # Identity
    domain: Mapped[str] = mapped_column(String(200), default="", index=True)
    company_name: Mapped[str] = mapped_column(String(300), default="")
    company_name_zh: Mapped[str] = mapped_column(String(300), default="")

    # Industry / market targeting
    industry_keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON

    # LLM-generated content
    tagline: Mapped[str] = mapped_column(Text, default="")
    tagline_zh: Mapped[str] = mapped_column(Text, default="")
    about_us: Mapped[str] = mapped_column(Text, default="")  # HTML
    about_us_zh: Mapped[str] = mapped_column(Text, default="")
    services: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    contact_phone: Mapped[str] = mapped_column(String(100), default="")
    contact_address: Mapped[str] = mapped_column(String(500), default="")
    seo_keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    seo_description: Mapped[str] = mapped_column(Text, default="")
    custom_css: Mapped[str] = mapped_column(Text, default="")  # overrides
    extra_pages: Mapped[str] = mapped_column(Text, default="[]")  # JSON: [{slug, title}]

    # Media
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    hero_image_url: Mapped[str] = mapped_column(String(500), default="")
    favicon_url: Mapped[str] = mapped_column(String(500), default="")

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / generated / deployed / failed
    github_repo: Mapped[str] = mapped_column(String(500), default="")
    deploy_url: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
