"""Per-website blog post model — each website has its own blog with daily posts."""

from sqlalchemy import String, Boolean, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class WebsiteBlogPost(UUIDMixin, TimestampMixin, Base):
    """A blog post for a specific website."""

    __tablename__ = "website_blog_posts"

    website_id: Mapped[str] = mapped_column(String(36), ForeignKey("websites.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    slug: Mapped[str] = mapped_column(String(200), default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")  # Full HTML content
    tags: Mapped[str] = mapped_column(String(500), default="[]")  # JSON array
    cover_image: Mapped[str] = mapped_column(String(500), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[str] = mapped_column(String(20), default="")  # YYYY-MM-DD
