"""Email sequence model — follow-up automation."""

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class EmailSequence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_sequences"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("email_templates.id"), nullable=True)
    mailbox_id: Mapped[str] = mapped_column(String(36), ForeignKey("mailboxes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / sent / replied / completed / skipped
    step_number: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_at: Mapped[str] = mapped_column(String(50), default="")  # ISO datetime
    sent_at: Mapped[str] = mapped_column(String(50), default="")
