"""Scheduled task — scan all active target markets for new leads."""

from datetime import datetime, timezone
from sqlalchemy import select

from backend.database import async_session
from backend.models.target_market import TargetMarket
from backend.services.market_scanner import MarketScanner


async def scheduled_market_scan():
    """Scan all active daily markets for new leads."""
    async with async_session() as db:
        result = await db.execute(
            select(TargetMarket).where(TargetMarket.active == True)
            .where(TargetMarket.scan_frequency == "daily")
        )
        markets = result.scalars().all()

    if not markets:
        print(f"[MarketScan] No active daily markets to scan")
        return

    scanner = MarketScanner()
    total_leads = 0

    for market in markets:
        market_dict = {
            "name": market.name,
            "keywords": market.keywords,
            "products": market.products,
            "industries": market.industries,
            "customer_types": market.customer_types,
            "search_keywords": market.search_keywords,
        }

        scan_result = await scanner.scan_market(market_dict)
        leads = scan_result.get("leads_extracted", [])
        total_leads += len(leads)

        # Save leads to DB (reuse async_session)
        async with async_session() as db:
            from backend.models.customer import Customer

            saved = 0
            for lead in leads:
                company = lead.get("company", "")
                if not company or company in ("Unknown", "unknown"):
                    continue

                # Check duplicate
                existing = await db.execute(
                    select(Customer).where(Customer.company.ilike(f"%{company[:50]}%"))
                )
                if existing.scalar_one_or_none():
                    continue

                customer = Customer(
                    name=company[:200],
                    company=company[:200],
                    country=lead.get("country", "")[:100],
                    source=f"market_scan_{market.name}",
                    score=min(int(lead.get("confidence", 0) * 100), 100),
                    matched_market=market.name,
                    notes=lead.get("source_text", "")[:1000],
                )
                db.add(customer)
                saved += 1

            # Update market stats
            market.leads_count = (market.leads_count or 0) + saved
            market.last_scanned = datetime.now(timezone.utc).isoformat()
            await db.commit()

        print(f"[MarketScan] {market.name}: {len(leads)} leads found, {saved} new")

    print(f"[MarketScan] Complete — {total_leads} total leads from {len(markets)} markets")
