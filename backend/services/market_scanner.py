"""Market scanner — search Google, RSS, B2B platforms for leads."""

import json
import re
from typing import Optional
from datetime import datetime, timezone

from backend.agents import TradeAgent


class MarketScanner:
    """Scan public web sources for potential buyer leads based on target markets."""

    def __init__(self):
        self.agent = TradeAgent(system_prompt="You are a B2B lead generation analyst for a packaging materials exporter.")

    @staticmethod
    async def google_search(query: str, num_results: int = 10) -> list[dict]:
        """Simulate Google search for buyer intent queries.
        
        In production, replace with SerpAPI/Google Custom Search/Playwright.
        For now, returns structured search-like data via LLM.
        """
        agent = TradeAgent(system_prompt="You simulate a web search engine for B2B leads.")
        
        prompt = f"""Generate {num_results} realistic Google search results for the query: "{query}"

Each result should look like a real search result from a B2B perspective — include company names,
industry news, supplier/buyer platforms, and trade directories.

Respond with a JSON array of objects:
[
  {{
    "title": "Company Name - Product/Service",
    "url": "www.example.com/page",
    "snippet": "Brief description of what this result is about..."
  }}
]

Only output the JSON array, nothing else."""
        try:
            response = await agent.chat(prompt, temperature=0.7)
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                results = json.loads(match.group())
                # Add source tracking
                for r in results:
                    r["source"] = "google"
                    r["query"] = query
                return results[:num_results]
        except Exception:
            pass
        
        return [{"title": f"Results for {query}", "url": "", "snippet": "", "source": "google", "query": query}]

    @staticmethod
    async def search_rss(keywords: list[str]) -> list[dict]:
        """Simulate RSS/news feed search for industry news about target markets.
        
        In production, replace with actual RSS feed parsing or news API.
        """
        agent = TradeAgent(system_prompt="You simulate an industry news feed for packaging and trade.")
        
        prompt = f"""Generate 5 recent industry news headlines related to these topics: {', '.join(keywords[:5])}

Focus on: packaging industry, trade shows, new regulations, market trends, plastic/PP materials.

Respond with a JSON array:
[
  {{
    "title": "News headline about the topic",
    "source_name": "Industry News Outlet",
    "snippet": "Brief summary of the article..."
  }}
]

Only output the JSON array."""
        try:
            response = await agent.chat(prompt, temperature=0.7)
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                results = json.loads(match.group())
                for r in results:
                    r["source"] = "news"
                return results
        except Exception:
            pass
        return []

    @staticmethod
    async def extract_leads(texts: list[dict], market_name: str) -> list[dict]:
        """Use LLM to extract potential buyer/lead information from search results.
        
        Returns list of dicts with: company, email, country, product_interest, confidence
        """
        if not texts:
            return []

        # Prepare a sample of the text for the LLM
        sample = "\n\n".join([
            f"Title: {t.get('title', '')}\nSnippet: {t.get('snippet', '')}"
            for t in texts[:8]
        ])

        if not sample.strip():
            return []

        prompt = f"""Analyze the following search results for the market: {market_name}

Extract any companies or potential buyers mentioned. Look for:
- Companies that might import/distribute packaging materials
- RFQs or purchase inquiries
- Companies expanding or in need of packaging solutions
- Trade directory listings of importers

Search results:
{sample}

Respond with a JSON array of extracted leads:
[
  {{
    "company": "Company Name or 'Unknown'",
    "country": "Country or 'Unknown'",
    "product_interest": "What product they might need",
    "confidence": 0.0 to 1.0,
    "source_text": "Key evidence from the text"
  }}
]

If no leads found, respond with empty array [].
Only output JSON."""
        try:
            response = await self.agent.chat(prompt, temperature=0.3)
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                leads = json.loads(match.group())
                return leads
        except Exception:
            pass
        return []

    @staticmethod
    async def match_market(lead_text: str, markets: list[dict]) -> str:
        """Determine which target market a lead belongs to.
        Returns market name or 'general'.
        """
        if not markets:
            return "general"

        market_descriptions = "\n".join([
            f"- {m.get('name')}: keywords={m.get('keywords', '')}, "
            f"products={m.get('products', '')}, industries={m.get('industries', '')}"
            for m in markets
        ])

        prompt = f"""Which target market does this lead belong to?

Target markets:
{market_descriptions}

Lead info: {lead_text[:500]}

Respond with exactly the market name that best matches, or "general" if none match.
Only output the name, nothing else."""
        try:
            agent = TradeAgent(system_prompt="You classify B2B leads into target market segments.")
            response = await agent.chat(prompt, temperature=0.1)
            response = response.strip()
            # Check if response matches a known market
            for m in markets:
                if m.get("name", "").lower() in response.lower():
                    return m["name"]
            return "general"
        except Exception:
            return "general"

    async def scan_market(self, market: dict) -> dict:
        """Run a full scan for one target market. Returns scan results."""
        name = market.get("name", "Unknown")
        
        # Parse keywords
        try:
            keywords = json.loads(market.get("search_keywords", "[]"))
        except (json.JSONDecodeError, TypeError):
            keywords = []
        
        if not keywords:
            try:
                base_kw = json.loads(market.get("keywords", "[]"))
            except (json.JSONDecodeError, TypeError):
                base_kw = []
            keywords = base_kw + [name]

        all_results = []
        all_leads = []

        # 1. Google-style search for each keyword (first 3 only to keep it reasonable)
        for kw in keywords[:3]:
            results = await self.google_search(kw, num_results=5)
            all_results.extend(results)

        # 2. News/RSS search
        news = await self.search_rss(keywords[:3])
        all_results.extend(news)

        # 3. Extract leads from results
        if all_results:
            leads = await self.extract_leads(all_results, name)
            all_leads.extend(leads)

        return {
            "market_name": name,
            "keywords_used": keywords[:5],
            "results_found": len(all_results),
            "leads_extracted": all_leads,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
