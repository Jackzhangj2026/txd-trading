"""Lead scoring engine — score leads 0-100 based on completeness, intent, market match."""

import json
from typing import Optional
from backend.agents import TradeAgent


class LeadScoringEngine:
    """Score potential customer leads based on multiple factors."""

    # Source quality weights
    SOURCE_WEIGHTS = {
        "alibaba_rfq": 20,
        "alibaba": 15,
        "linkedin": 12,
        "google": 8,
        "news": 5,
        "website": 10,
        "email": 10,
        "import": 15,
        "market_scan": 10,
    }

    # High-intent keywords
    HIGH_INTENT_KEYWORDS = [
        "urgent", "order", "purchase", "buy", "need", "require",
        "looking for", "seeking", "interested in", "quote",
        "price", "quotation", "importer", "distributor", "wholesale",
    ]

    @staticmethod
    def score_completeness(company: str, email: str, phone: str, country: str) -> int:
        """Score based on information completeness (max 30)."""
        score = 0
        if company and company not in ("Unknown", "unknown", ""):
            score += 10
        if email and "@" in email:
            score += 10
        if phone:
            score += 5
        if country and country not in ("Unknown", "unknown", ""):
            score += 5
        return score

    @staticmethod
    def score_intent(text: str) -> int:
        """Score based on purchase intent signals (max 30)."""
        if not text:
            return 0
        text_lower = text.lower()
        score = 0
        for kw in LeadScoringEngine.HIGH_INTENT_KEYWORDS:
            if kw in text_lower:
                score += 3
        return min(score, 30)

    @staticmethod
    def score_source(source: str) -> int:
        """Score based on data source quality (max 10)."""
        return LeadScoringEngine.SOURCE_WEIGHTS.get(source, 5)

    @staticmethod
    def score_market_match(matched_market: str, market_priority: int = 5) -> int:
        """Score based on target market match (max 30)."""
        if matched_market and matched_market not in ("general", "Unknown", ""):
            # Base match score + priority bonus
            return 15 + min(market_priority, 15)
        return 0

    @classmethod
    def calculate_score(
        cls,
        company: str = "",
        email: str = "",
        phone: str = "",
        country: str = "",
        intent_text: str = "",
        source: str = "",
        matched_market: str = "",
        market_priority: int = 5,
    ) -> int:
        """Calculate total lead score (0-100)."""
        completeness = cls.score_completeness(company, email, phone, country)
        intent = cls.score_intent(intent_text)
        source_score = cls.score_source(source)
        market = cls.score_market_match(matched_market, market_priority)

        total = completeness + intent + source_score + market
        return min(total, 100)

    @classmethod
    def get_grade(cls, score: int) -> tuple:
        """Get grade label and color for a score."""
        if score >= 80:
            return ("Hot", "🔥", "#f43f5e")
        elif score >= 60:
            return ("Warm", "🔵", "#3b82f6")
        elif score >= 30:
            return ("Cold", "🟡", "#eab308")
        else:
            return ("Lead", "⚪", "#6b7280")
