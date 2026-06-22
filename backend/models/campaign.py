"""Campaign model — persists email campaigns across restarts."""

from sqlalchemy import String, Boolean, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin
from datetime import datetime


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    campaign_name: Mapped[str] = mapped_column(String(200), default="")
    mailbox_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    customer_count: Mapped[int] = mapped_column(Integer, default=0)
    subject_preview: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / running / paused / completed / failed / stopped
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    delay_min: Mapped[int] = mapped_column(Integer, default=30)
    delay_max: Mapped[int] = mapped_column(Integer, default=180)
    daily_limit: Mapped[int] = mapped_column(Integer, default=20)  # max emails per day for this campaign
    last_run_date: Mapped[str] = mapped_column(String(20), default="")  # ISO date of last run
    image_filenames: Mapped[str] = mapped_column(Text, default="[]")
    error_message: Mapped[str] = mapped_column(Text, default="")

    # Full config for resume across restart
    subject_template: Mapped[str] = mapped_column(Text, default="")
    body_template: Mapped[str] = mapped_column(Text, default="")
    customer_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON — full list to send
    sent_customer_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON — already sent
    current_email_index: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[str] = mapped_column(String(50), default="")  # ISO datetime
    completed_at: Mapped[str] = mapped_column(String(50), default="")
