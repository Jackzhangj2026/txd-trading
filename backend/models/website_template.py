"""Website template model — diverse HTML themes for generating company sites."""

from sqlalchemy import String, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class WebsiteTemplate(UUIDMixin, TimestampMixin, Base):
    """A reusable website template — stores CSS variables and metadata."""

    __tablename__ = "website_templates"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    display_name_zh: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(50), default="general")
    thumbnail: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    css_variables: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    popularity: Mapped[int] = mapped_column(Integer, default=0)  # usage count
    active: Mapped[bool] = mapped_column(Boolean, default=True)
