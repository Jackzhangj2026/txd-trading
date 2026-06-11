"""Email log model — sent/received email history."""

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class EmailLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_logs"

    mailbox_id: Mapped[str] = mapped_column(String(36), ForeignKey("mailboxes.id"), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), default="out")  # in / out
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent / draft / failed / received
    message_id: Mapped[str] = mapped_column(String(200), default="")  # Email Message-ID for threading
    sent_at: Mapped[str] = mapped_column(String(50), default="")  # ISO datetime
