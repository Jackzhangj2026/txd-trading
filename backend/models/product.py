"""Product model — PP hollow sheets, boxes, and future categories."""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    name_zh: Mapped[str] = mapped_column(String(200), default="")
    name_en: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # sheet / box / catalog
    description: Mapped[str] = mapped_column(Text, default="")
    description_zh: Mapped[str] = mapped_column(Text, default="")
    specs: Mapped[str] = mapped_column(Text, default="{}")  # JSON string
    images: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of URLs
    active: Mapped[bool] = mapped_column(Boolean, default=True)
