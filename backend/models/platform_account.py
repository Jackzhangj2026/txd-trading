"""Platform account model — social media account credentials."""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class PlatformAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "platform_accounts"

    platform: Mapped[str] = mapped_column(String(50), index=True)
    account_name: Mapped[str] = mapped_column(String(200), default="")
    account_type: Mapped[str] = mapped_column(String(50), default="personal")  # personal / business / official
    credentials_enc: Mapped[str] = mapped_column(Text, default="{}")  # Encrypted JSON
    active: Mapped[bool] = mapped_column(Boolean, default=True)
