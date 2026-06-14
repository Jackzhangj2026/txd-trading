"""Campaign model — persists email campaigns across restarts."""

from sqlalchemy import String, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    campaign_name: Mapped[str] = mapped_column(String(200), default="")
    mailbox_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    customer_count: Mapped[int] = mapped_column(Integer, default=0)
    subject_preview: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / running / completed / failed
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    delay_min: Mapped[int] = mapped_column(Integer, default=30)
    delay_max: Mapped[int] = mapped_column(Integer, default=180)
    image_filenames: Mapped[str] = mapped_column(Text, default="[]")
    error_message: Mapped[str] = mapped_column(Text, default="")
