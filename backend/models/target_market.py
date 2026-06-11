"""Target market model — user-defined market segments for intelligence gathering."""

from sqlalchemy import String, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class TargetMarket(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "target_markets"

    name: Mapped[str] = mapped_column(String(100), index=True)  # "Packaging", "Automotive Parts"
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Keyword dimensions
    keywords: Mapped[str] = mapped_column(Text, default="[]")        # JSON: ["packaging", "corrugated"]
    products: Mapped[str] = mapped_column(Text, default="[]")        # JSON: ["PP hollow board", "plastic box"]
    industries: Mapped[str] = mapped_column(Text, default="[]")      # JSON: ["logistics", "packaging"]
    customer_types: Mapped[str] = mapped_column(Text, default="[]")  # JSON: ["importer", "distributor"]

    # Auto-generated search queries from LLM
    search_keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON: ["PP hollow board buyer", ...]

    # Configuration
    scan_frequency: Mapped[str] = mapped_column(String(20), default="daily")  # daily / weekly
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1-10

    # Stats
    leads_count: Mapped[int] = mapped_column(Integer, default=0)
    last_scanned: Mapped[str] = mapped_column(String(50), default="")
