"""Mailbox model — multi-email account configuration."""

from sqlalchemy import String, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Mailbox(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "mailboxes"

    name: Mapped[str] = mapped_column(String(100), default="")  # "General Inquiries"
    email_address: Mapped[str] = mapped_column(String(200), index=True)

    # IMAP
    imap_host: Mapped[str] = mapped_column(String(200), default="")
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_username: Mapped[str] = mapped_column(String(200), default="")
    imap_password_enc: Mapped[str] = mapped_column(String(500), default="")

    # SMTP
    smtp_host: Mapped[str] = mapped_column(String(200), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_username: Mapped[str] = mapped_column(String(200), default="")
    smtp_password_enc: Mapped[str] = mapped_column(String(500), default="")
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)

    # Routing
    routing_rules: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    assigned_to: Mapped[str] = mapped_column(String(100), default="")
    daily_send_limit: Mapped[int] = mapped_column(Integer, default=200)

    # Status
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[str] = mapped_column(String(50), default="")  # ISO datetime string
