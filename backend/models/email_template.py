"""Email template model — reusable email templates with Jinja2 variables."""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class EmailTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_templates"

    name: Mapped[str] = mapped_column(String(100), index=True)  # "first_contact", "quotation"
    category: Mapped[str] = mapped_column(String(50), default="")  # cold / quote / followup / holiday
    subject_template: Mapped[str] = mapped_column(String(500), default="")
    body_template: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of variable names
    active: Mapped[bool] = mapped_column(Boolean, default=True)
