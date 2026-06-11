"""Content piece model — social media posts, blog articles, video scripts."""

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class ContentPiece(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_pieces"

    title: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(50), default="post")  # post / article / script / note
    platform: Mapped[str] = mapped_column(String(50), index=True)  # linkedin / twitter / youtube / tiktok / red / douyin / wechat / pinterest / facebook
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / scheduled / published / failed
    body: Mapped[str] = mapped_column(Text, default="")
    media_urls: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    scheduled_at: Mapped[str] = mapped_column(String(50), default="")
    published_at: Mapped[str] = mapped_column(String(50), default="")
    source_blog_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_pieces.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")  # en / zh
