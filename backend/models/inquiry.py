"""Inquiry model — contact form submissions and their classifications."""

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Inquiry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inquiries"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new / classified / replied / closed
    classification: Mapped[str] = mapped_column(String(20), default="")  # high / medium / low / spam
    source: Mapped[str] = mapped_column(String(50), default="website")  # website / email / alibaba
    ai_summary: Mapped[str] = mapped_column(Text, default="")
