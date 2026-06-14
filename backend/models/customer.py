"""Customer/Lead model — tracks prospects and clients."""

from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), index=True, default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    company: Mapped[str] = mapped_column(String(200), index=True, default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(50), default="")  # website / email / alibaba / linkedin / import
    status: Mapped[str] = mapped_column(String(20), default="lead")  # lead / contacted / interested
    score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100 lead score
    matched_market: Mapped[str] = mapped_column(String(100), default="")  # Target market name
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
