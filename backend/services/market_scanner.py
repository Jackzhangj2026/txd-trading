"""Market scanner — multi-lane B2B lead discovery with email extraction."""

import json
import re
from typing import Optional
from datetime import datetime, timezone

import httpx
from backend.agents import TradeAgent
from backend.config import settings

# ─── Email Extraction (ported from b2b-lead-hunter extract_contacts.py) ───

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)

GENERIC_LOCAL_PARTS = {
    "info", "sales", "contact", "support", "office", "hello", "admin",
    "marketing", "service", "team", "enquiry", "enquiries", "inquiry",
    "inquiries", "export", "exports", "import", "imports", "customerservice",
}

FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "aol.com", "proton.me", "protonmail.com",
    "qq.com", "163.com", "126.com", "mail.ru", "yandex.ru", "gmx.de",
    "web.de", "orange.fr", "libero.it", "naver.com", "daum.net",
}

INVALID_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "localhost",
    "domain.com", "email.com", "yourdomain.com",
}

INVALID_EMAIL_LOCALS = {
    "example", "test", "demo", "noreply", "no-reply", "donotreply",
}

# ─── 6-Lane Query Templates ───

# Product categories for TXD
PRODUCT_TERMS = [
    "PP hollow board", "PP hollow sheet", "corrugated plastic sheet",
    "plastic packaging sheet", "PP corrugated box", "polypropylene twinwall sheet",
    "ESD packaging material", "reusable plastic container",
]

# Countries commonly importing packaging
IMPORT_COUNTRIES = [
    "Germany", "UK", "France", "Italy", "Spain", "Netherlands",
    "Poland", "USA", "Brazil", "Mexico", "UAE", "Saudi Arabia",
    "South Africa", "Australia", "Turkey", "India", "Belgium", "Sweden",
]

# B2B directories
B2B_DIRECTORIES = [
    "europages.com", "kompass.com", "wlw.de", "thomasnet.com",
    "tradeindia.com", "alibaba.com", "made-in-china.com",
]

# Competitor brands in PP hollow board space
COMPETITOR_BRANDS = [
    "Coroplast", "Inteplast", "Primex Plastics", "DS Smith",
    "SIMONA", "Protoplast", "Twinplast",
]

# Trade fairs
TRADE_FAIRS = [
    "Interpack", "FachPack", "PackExpo", "Empack", "Packaging Innovations",
    "K Show Düsseldorf", "Chinaplas",
]


class MarketScanner:
    """Multi-lane B2B market scanner with email extraction and decision-maker discovery."""

    def __init__(self):
        self.agent = TradeAgent(
            system_prompt="You are a B2B lead generation analyst for a PP hollow board packaging exporter."
        )

    # ─── Query Lane Generator ───────────────────────────────────────────

    @staticmethod
    def generate_query_lanes(market: dict) -> list[dict]:
        """Generate diverse search queries across 6 lanes for a target market."""
        name = market.get("name", "")
        try:
            keywords = json.loads(market.get("search_keywords", "[]"))
        except (json.JSONDecodeError, TypeError):
            keywords = []
        if not keywords:
            try:
                keywords = json.loads(market.get("keywords", "[]"))
            except (json.JSONDecodeError, TypeError):
                keywords = [name]
        try:
            products = json.loads(market.get("products", "[]"))
        except (json.JSONDecodeError, TypeError):
            products = PRODUCT_TERMS[:3]

        # Pick representative terms
        product = products[0] if products else keywords[0] if keywords else name
        kw_sample = keywords[:3] if keywords else [product]

        queries = []
        lanes_used = set()

        def add(lane: str, query: str):
            if lane not in lanes_used:
                lanes_used.add(lane)
            queries.append({"lane": lane, "query": query})

        # Use first 3 countries rotated
        country1 = IMPORT_COUNTRIES[hash(name) % len(IMPORT_COUNTRIES)]
        country2 = IMPORT_COUNTRIES[(hash(name) + 3) % len(IMPORT_COUNTRIES)]
        country3 = IMPORT_COUNTRIES[(hash(name) + 7) % len(IMPORT_COUNTRIES)]

        # Lane 1: Organic buyer search
        for country in [country1, country2]:
            add("organic", f'"{product}" importer {country}')
            add("organic", f'"{product}" distributor {country}')
        add("organic", f'"{product}" wholesaler buyer')

        # Lane 2: B2B directory search
        for directory in B2B_DIRECTORIES[:3]:
            add("b2b_directory", f'site:{directory} "{product}" importer')

        # Lane 3: Local/maps-style search
        for country in [country1, country3]:
            add("local", f'"{product}" packaging company {country} contact')

        # Lane 4: Competitor channel
        competitor = COMPETITOR_BRANDS[hash(name) % len(COMPETITOR_BRANDS)]
        add("competitor", f'"{competitor}" distributor {country1}')
        add("competitor", f'"{competitor}" authorized distributor')

        # Lane 5: Trade fair / association
        fair = TRADE_FAIRS[hash(name) % len(TRADE_FAIRS)]
        add("association", f'"{fair}" exhibitors packaging')
        add("association", f'"{product}" trade association members')

        # Lane 6: Brand distributor networks (generalized)
        add("brand_network", f'"{product}" authorized distributor list')

        return queries

    # ─── Search (Serper.dev → Google CSE → LLM fallback) ───────────────

    @staticmethod
    async def google_search(query: str, num_results: int = 10) -> list[dict]:
        """Search Google via Serper.dev API (primary), Google CSE, or LLM fallback."""
        serper_key = settings.serper_api_key
        google_key = settings.google_api_key
        cse_id = settings.google_cse_id

        # 1. Serper.dev (free 2500/month, real Google results)
        if serper_key:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    body = {"q": query, "num": min(num_results, 10)}
                    # Add geo-targeting for European queries
                    if any(c in query.lower() for c in ["germany", "gmbh", "deutschland"]):
                        body["gl"] = "de"
                    elif any(c in query.lower() for c in ["uk", "united kingdom", "england", "london", "ltd"]):
                        body["gl"] = "uk"
                    elif any(c in query.lower() for c in ["france", "paris", "sarl"]):
                        body["gl"] = "fr"
                    elif any(c in query.lower() for c in ["italy", "italia", "srl"]):
                        body["gl"] = "it"
                    elif any(c in query.lower() for c in ["spain", "españa", "barcelona"]):
                        body["gl"] = "es"
                    elif any(c in query.lower() for c in ["netherlands", "holland", "amsterdam"]):
                        body["gl"] = "nl"
                    elif any(c in query.lower() for c in ["poland", "polska"]):
                        body["gl"] = "pl"
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        json=body,
                        headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = []
                        for item in data.get("organic", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "source": "serper",
                                "query": query,
                            })
                        if results:
                            print(f"[MarketScanner] Serper: {len(results)} results for '{query[:50]}'")
                            return results
                    else:
                        print(f"[MarketScanner] Serper error: {resp.status_code}")
            except Exception as e:
                print(f"[MarketScanner] Serper failed: {e}")

        # 2. Google Custom Search (legacy, closing to new users)
        if google_key and cse_id:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={"key": google_key, "cx": cse_id, "q": query, "num": min(num_results, 10)},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = []
                        for item in data.get("items", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "source": "google_cse",
                                "query": query,
                            })
                        if results:
                            return results
            except Exception as e:
                print(f"[MarketScanner] Google CSE failed: {e}")

        # Fallback: LLM simulation
        print(f"[MarketScanner] LLM fallback for: {query[:60]}")
        agent = TradeAgent(
            system_prompt="You are a B2B lead generation specialist. Return realistic company search results."
        )
        prompt = f"""Find {num_results} REALISTIC companies that match this search: "{query}"
Output ONLY a JSON array:
[{{"title":"Company Name - Description","url":"company-website.com","snippet":"What they do, location, evidence they are a buyer/importer."}}]"""
        try:
            response = await agent.chat(prompt, temperature=0.8)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                results = json.loads(match.group())
                for r in results:
                    r["source"] = "google_simulated"
                    r["query"] = query
                return results[:num_results]
        except Exception as e:
            print(f"[MarketScanner] LLM fallback failed: {e}")
        return []

    # ─── Email Extraction ───────────────────────────────────────────────

    @staticmethod
    def extract_emails(text: str, source_url: str = "") -> list[dict]:
        """Extract and classify email addresses from text."""
        seen = set()
        rows = []
        for match in EMAIL_RE.findall(text):
            email = match.strip().lower()
            if email in seen or not MarketScanner._valid_email(email):
                continue
            seen.add(email)
            kind = "generic" if email.split("@")[0].lower() in GENERIC_LOCAL_PARTS else "person"
            domain = email.rsplit("@", 1)[-1].lower()
            relation = "free_mail" if domain in FREE_MAIL_DOMAINS else "business"
            confidence = 0.9 if kind == "person" else 0.85
            if relation == "free_mail":
                confidence -= 0.2
            rows.append({
                "email": email,
                "type": kind,
                "source_url": source_url,
                "domain_relation": relation,
                "confidence": round(max(0.1, min(confidence, 0.98)), 2),
            })
        return rows

    @staticmethod
    def _valid_email(email: str) -> bool:
        if email.count("@") != 1:
            return False
        local, domain = email.lower().split("@", 1)
        if not local or not domain or "." not in domain:
            return False
        if domain in INVALID_EMAIL_DOMAINS:
            return False
        if local in INVALID_EMAIL_LOCALS:
            return False
        if local.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            return False
        return True

    # ─── Tavily LinkedIn Decision-Maker Search ──────────────────────────

    @staticmethod
    async def search_linkedin_dm(company_name: str) -> list[dict]:
        """Search LinkedIn for decision-makers at a company using Tavily API."""
        api_key = settings.tavily_api_key
        if not api_key:
            return []

        roles = ["purchasing manager", "procurement manager", "buyer", "import manager", "CEO", "owner"]
        results = []
        for role in roles[:3]:
            query = f'"{company_name}" {role} site:linkedin.com/in'
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": api_key,
                            "query": query,
                            "search_depth": "basic",
                            "max_results": 3,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "snippet": item.get("content", ""),
                                "query": query,
                                "source": "tavily_linkedin",
                            })
            except Exception as e:
                print(f"[MarketScanner] Tavily error: {e}")

        return results[:5]

    # ─── Lead Extraction (LLM) ──────────────────────────────────────────

    @staticmethod
    async def extract_leads(texts: list[dict], market_name: str) -> list[dict]:
        """LLM-based lead extraction from search results."""
        if not texts:
            return []

        sample = "\n\n".join([
            f"Title: {t.get('title', '')}\nURL: {t.get('url', '')}\nSnippet: {t.get('snippet', '')}"
            for t in texts[:10]
        ])

        if not sample.strip():
            return []

        prompt = f"""Analyze these search results for market: {market_name}

Extract companies that could be buyers/importers of PP hollow board or packaging materials.

{sample}

Output a JSON array:
[{{"company":"Company Name","country":"Country","product_interest":"What they need","confidence":0.0-1.0,"source_text":"Evidence from results"}}]
If no leads, output []."""
        try:
            agent = TradeAgent(system_prompt="Extract B2B leads from search results.")
            response = await agent.chat(prompt, temperature=0.3)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return []

    @staticmethod
    async def match_market(lead_text: str, markets: list[dict]) -> str:
        """Match a lead to a target market."""
        if not markets:
            return "general"
        market_descriptions = "\n".join([
            f"- {m.get('name')}: products={m.get('products','')}, industries={m.get('industries','')}"
            for m in markets
        ])
        prompt = f"Which market does this lead match?\nMarkets:\n{market_descriptions}\nLead: {lead_text[:300]}\nOutput only the market name or 'general'."
        try:
            agent = TradeAgent(system_prompt="Classify B2B leads into market segments.")
            response = await agent.chat(prompt, temperature=0.1)
            response = response.strip()
            for m in markets:
                if m.get("name", "").lower() in response.lower():
                    return m["name"]
            return "general"
        except Exception:
            return "general"

    # ─── Full Scan Orchestrator ─────────────────────────────────────────

    async def scan_market(self, market: dict) -> dict:
        """Multi-lane scan for one target market. Resilient with timeouts for local LLM."""
        import asyncio as aio
        name = market.get("name", "Unknown")

        # Generate diverse queries across 6 lanes
        query_lanes = self.generate_query_lanes(market)
        print(f"[MarketScanner] {name}: {len(query_lanes)} queries across {len(set(q['lane'] for q in query_lanes))} lanes")

        all_results = []
        lane_stats = {}

        # Search: use only 3 queries to stay fast with local LLM
        for q in query_lanes[:3]:
            try:
                results = await aio.wait_for(
                    self.google_search(q["query"], num_results=3), timeout=25.0
                )
            except aio.TimeoutError:
                print(f"[MarketScanner] Timeout on: {q['query'][:50]}")
                results = []
            lane = q["lane"]
            lane_stats[lane] = lane_stats.get(lane, 0) + len(results)
            all_results.extend(results)

        print(f"[MarketScanner] {name}: {len(all_results)} total results")

        # Extract emails from all snippets (regex, no LLM needed)
        all_snippets = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in all_results])
        extracted_emails = self.extract_emails(all_snippets)

        # Simple lead extraction from titles (no LLM, fast and reliable)
        leads = []
        seen_companies = set()
        for r in all_results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            url = r.get("url", "")
            # Extract company name from title (before " - " or first 3 words)
            company = title.split(" - ")[0].strip() if " - " in title else " ".join(title.split()[:3])
            if not company or len(company) < 3 or company.lower() in ("results", "search", "the", "page", "home"):
                continue
            if company.lower() in seen_companies:
                continue
            seen_companies.add(company.lower())

            # Extract website URL from result or snippet
            website = ""
            if url and not any(skip in url.lower() for skip in ("google.com", "youtube.com", "facebook.com", "linkedin.com", "twitter.com", "instagram.com")):
                website = url.split("?")[0].rstrip("/")
            # Also try to find domain-style URLs in snippet
            if not website:
                url_match = re.search(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2})?(?:/[^\s,.!?]*)?)', snippet)
                if url_match:
                    candidate = url_match.group(1)
                    if not any(skip in candidate.lower() for skip in ("google", "youtube", "facebook", "linkedin", "twitter", "instagram")):
                        website = "https://" + candidate.rstrip("/")

            # Guess country from snippet
            country_hints = {
                "Germany": ["germany", "gmbh", "deutschland"],
                "UK": ["united kingdom", "england", "london", "ltd"],
                "France": ["france", "paris", "sarl"],
                "Italy": ["italy", "italia", "srl", "milano"],
                "Spain": ["spain", "españa", "barcelona", "madrid"],
                "Netherlands": ["netherlands", "holland", "amsterdam", "bv"],
                "Poland": ["poland", "polska", "warsaw"],
                "USA": ["usa", "united states", "america", "inc"],
            }
            country = ""
            text_lower = (snippet + " " + title).lower()
            for cname, hints in country_hints.items():
                if any(h in text_lower for h in hints):
                    country = cname
                    break

            leads.append({
                "company": company,
                "country": country,
                "website": website,
                "product_interest": r.get("query", ""),
                "confidence": 0.5,
                "source_text": snippet[:200],
            })

        # Attach extracted emails to matching leads
        for lead in leads:
            company = lead.get("company", "").lower().replace(" ", "")
            lead_emails = []
            for em in extracted_emails:
                email_domain = em["email"].rsplit("@", 1)[-1]
                if company in email_domain or email_domain.replace(".com", "") in company:
                    lead_emails.append(em)
            lead["emails_found"] = lead_emails
            if lead_emails:
                lead["email"] = lead_emails[0]["email"]

        # LinkedIn DM discovery via Tavily (for top 2 leads, with timeout)
        for lead in leads[:2]:
            company = lead.get("company", "")
            if company and company != "Unknown" and settings.tavily_api_key:
                try:
                    dm_results = await aio.wait_for(
                        self.search_linkedin_dm(company), timeout=10.0
                    )
                except aio.TimeoutError:
                    dm_results = []
                if dm_results:
                    lead["linkedin_dms"] = dm_results[:3]

        return {
            "market_name": name,
            "query_lanes": list(set(q["lane"] for q in query_lanes[:3])),
            "queries_run": len(query_lanes[:3]),
            "results_found": len(all_results),
            "results_by_lane": lane_stats,
            "emails_extracted": len(extracted_emails),
            "leads_extracted": leads,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
