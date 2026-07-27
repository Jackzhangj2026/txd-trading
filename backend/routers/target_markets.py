"""Target market API routes — define markets, generate keywords, trigger scans."""

import json
import re
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.target_market import TargetMarket
from backend.models.customer import Customer
from backend.models.mailbox import Mailbox
from backend.models.email_template import EmailTemplate
from backend.models.email_log import EmailLog
from backend.agents import TradeAgent

router = APIRouter(prefix="/api/target-markets", tags=["target-markets"])


class TargetMarketCreate(BaseModel):
    name: str
    keywords: str = "[]"
    products: str = "[]"
    industries: str = "[]"
    customer_types: str = "[]"
    priority: int = 5
    scan_frequency: str = "daily"


class TargetMarketUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    keywords: str | None = None
    products: str | None = None
    industries: str | None = None
    customer_types: str | None = None
    priority: int | None = None
    scan_frequency: str | None = None


def market_to_dict(m: TargetMarket) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "active": m.active,
        "keywords": m.keywords,
        "products": m.products,
        "industries": m.industries,
        "customer_types": m.customer_types,
        "search_keywords": m.search_keywords,
        "priority": m.priority,
        "scan_frequency": m.scan_frequency,
        "leads_count": m.leads_count,
        "last_scanned": m.last_scanned,
        "created_at": str(m.created_at) if m.created_at else "",
        "updated_at": str(m.updated_at) if m.updated_at else "",
    }


@router.get("")
async def list_markets(active: bool | None = None, db: AsyncSession = Depends(get_db)):
    query = select(TargetMarket)
    if active is not None:
        query = query.where(TargetMarket.active == active)
    query = query.order_by(desc(TargetMarket.priority), TargetMarket.name)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [market_to_dict(m) for m in items], "total": len(items)}


@router.get("/{market_id}")
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")
    return market_to_dict(m)


@router.post("", status_code=201)
async def create_market(data: TargetMarketCreate, db: AsyncSession = Depends(get_db)):
    m = TargetMarket(**data.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return market_to_dict(m)


@router.put("/{market_id}")
async def update_market(market_id: str, data: TargetMarketUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(m, key, value)
    await db.commit()
    await db.refresh(m)
    return market_to_dict(m)


@router.delete("/{market_id}", status_code=204)
async def delete_market(market_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")
    await db.delete(m)
    await db.commit()


class GenerateKeywordsRequest(BaseModel):
    name: str
    keywords: list[str] = []
    products: list[str] = []
    industries: list[str] = []


@router.post("/generate-keywords")
async def generate_keywords(data: GenerateKeywordsRequest):
    """Use LLM to generate effective search keywords for a target market."""
    agent = TradeAgent(system_prompt="You are an international trade SEO expert.")

    prompt = f"""Generate 10 effective search queries for finding buyers of the following packaging products/market:

Market: {data.name}
Keywords: {', '.join(data.keywords) if data.keywords else 'N/A'}
Products: {', '.join(data.products) if data.products else 'N/A'}
Industries: {', '.join(data.industries) if data.industries else 'N/A'}

The queries should be things real buyers would search for on Google and B2B platforms.
Include buyer-intent phrases like: "buyer", "importer", "supplier", "wholesale", "distributor", "RFQ", "quotation"

Cover these packaging segments where relevant:
- Gift boxes / rigid boxes / luxury packaging
- Carton boxes / paper boxes / corrugated packaging
- Fruit packaging / agricultural produce boxes
- Logistics / shipping / transport packaging
- PP hollow board / plastic packaging

Respond with a JSON array of strings only, no explanation.
Example: ["gift box buyer USA", "carton box importer Europe", "fruit packaging supplier", ...]"""
    try:
        response = await agent.chat(prompt, temperature=0.7)
        # Extract JSON array
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            keywords = json.loads(match.group())
            return {"keywords": keywords[:15]}
        return {"keywords": [data.name]}
    except Exception:
        # Fallback: generate basic keywords with packaging industry coverage
        base = data.name.lower().replace(" ", " ")
        return {
            "keywords": [
                f"{base} buyer",
                f"{base} importer",
                f"{base} wholesale",
                f"{base} distributor",
                f"{base} RFQ",
                f"{base} quotation",
                f"buy {base} from China",
                f"{base} manufacturer China",
                f"{base} supplier",
                f"{base} price",
                "gift box buyer",
                "carton box importer",
                "fruit packaging supplier",
                "logistics packaging wholesale",
                "rigid box manufacturer",
            ]
        }


@router.get("/{market_id}/leads")
async def get_market_leads(
    market_id: str,
    score_min: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List customers/leads matched to this target market."""
    # First get the market to know its name
    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")

    query = select(Customer).where(Customer.matched_market == m.name)
    if score_min is not None:
        query = query.where(Customer.score >= score_min)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(Customer.score))
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "market_name": m.name,
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "company": c.company,
                "email": c.email,
                "country": c.country,
                "score": c.score,
                "source": c.source,
                "created_at": str(c.created_at) if c.created_at else "",
            }
            for c in items
        ],
        "total": total,
    }


class ScanResponse(BaseModel):
    market_name: str
    keywords_used: list[str] = []
    results_found: int
    leads_extracted: list[dict]
    scanned_at: str
    emails_sent: int = 0


@router.post("/{market_id}/scan", response_model=ScanResponse)
async def scan_market(market_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger a market scan — search web for leads."""
    from backend.services.market_scanner import MarketScanner

    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")

    scanner = MarketScanner()
    market_dict = {
        "name": m.name,
        "keywords": m.keywords,
        "products": m.products,
        "industries": m.industries,
        "customer_types": m.customer_types,
        "search_keywords": m.search_keywords,
    }

    try:
        scan_result = await scanner.scan_market(market_dict)
    except Exception as e:
        import traceback, sys, json as _json
        err = traceback.format_exc()
        print(f"[ScanError] {err}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=_json.dumps({"error": str(e), "traceback": err.split(chr(10))[-3:]}, ensure_ascii=False))

    # Save extracted leads as customers
    from backend.models.customer import Customer
    saved_count = 0
    print(f"[ScanAPI] Saving {len(scan_result.get('leads_extracted', []))} leads...")
    for lead in scan_result.get("leads_extracted", []):
        company = lead.get("company", "Unknown")
        country = lead.get("country", "Unknown")
        product = lead.get("product_interest", "")
        email = lead.get("email", "")
        website = lead.get("website", "")

        # Skip if no useful data
        if company in ("Unknown", "") and not email:
            continue

        # Match market directly (skip LLM call to avoid timeout with local model)
        matched = m.name

        # Build notes with enriched info
        notes_parts = []
        if lead.get("source_text"):
            notes_parts.append(f"Source: {lead['source_text'][:200]}")
        if lead.get("linkedin_dms"):
            dm_names = [dm.get("title", "").split(" - ")[0] for dm in lead["linkedin_dms"][:3]]
            notes_parts.append(f"LinkedIn DMs: {', '.join(dm_names)}")

        # Score the lead
        from backend.services.lead_scoring import LeadScoringEngine
        final_score = LeadScoringEngine.calculate_score(
            company=company, email=email, country=country,
            intent_text=str(lead.get("source_text", "")),
            source=f"market_scan_{m.name}",
            matched_market=matched,
        )
        # Boost score if email found
        if email:
            final_score = min(final_score + 15, 100)

        # Check if customer already exists (by company name or email)
        existing = None
        if email:
            existing_result = await db.execute(
                select(Customer).where(Customer.email == email)
            )
            existing = existing_result.scalar_one_or_none()
        if not existing and company not in ("Unknown", ""):
            existing_result = await db.execute(
                select(Customer).where(Customer.company.ilike(f"%{company[:50]}%"))
            )
            existing = existing_result.scalar_one_or_none()

        if not existing:
            customer = Customer(
                name=company,
                company=company,
                email=email,
                website=website,
                country=country,
                source=f"market_scan_{m.name}",
                score=min(final_score, 100),
                matched_market=matched,
                notes=" | ".join(notes_parts) if notes_parts else lead.get("source_text", ""),
            )
            db.add(customer)
            saved_count += 1

    # Update market stats
    m.leads_count = (m.leads_count or 0) + saved_count
    m.last_scanned = datetime.now(timezone.utc).isoformat()
    await db.commit()

    # ── Step 1: Enrich customers without emails by scraping their websites ──
    import asyncio as aio
    enriched = 0
    print(f"[ScanAPI] Enrichment: saved={saved_count}")
    if saved_count > 0:
        # Get customers just saved that have website but no email
        no_email_result = await db.execute(
            select(Customer).where(
                Customer.source == f"market_scan_{m.name}",
                Customer.email == "",
                Customer.website != "",
            ).limit(10)
        )
        no_email_customers = list(no_email_result.scalars().all())

        for cust in no_email_customers:
            if not cust.website:
                continue
            try:
                # Try homepage + /contact for better email coverage
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    page_text = ""
                    resp = await aio.wait_for(
                        client.get(cust.website, headers={"User-Agent": "Mozilla/5.0"}),
                        timeout=8.0
                    )
                    if resp.status_code == 200:
                        page_text = resp.text[:50000]
                    for suffix in ["/contact", "/about", "/kontakt"]:
                        if "@" not in page_text:
                            try:
                                r2 = await aio.wait_for(
                                    client.get(cust.website.rstrip("/") + suffix, headers={"User-Agent": "Mozilla/5.0"}),
                                    timeout=6.0
                                )
                                if r2.status_code == 200:
                                    page_text += r2.text[:30000]
                            except:
                                pass
                    if page_text and "@" in page_text:
                        import re as _re
                        _email_re = _re.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', _re.IGNORECASE)
                        found = set()
                        for m in _email_re.findall(page_text):
                            email = m.strip().lower()
                            # Filter out image/asset false positives
                            if email and "@" in email and not email.endswith((".png",".jpg",".gif",".svg",".css",".js")):
                                found.add(email)
                        if found:
                            # Take the first non-role email
                            from backend.services.email_intel import is_role_account
                            best = None
                            for e in found:
                                if not is_role_account(e):
                                    best = e; break
                            if not best:
                                best = next(iter(found))
                            cust.email = best
                            enriched += 1
                            print(f"  [Scan] Found email for {cust.company}: {best}")
            except (aio.TimeoutError, Exception):
                pass

        if enriched > 0:
            await db.commit()
            print(f"  [Scan] Enriched {enriched} customers with emails from websites")

    # ── Step 2: Auto-send development emails ──
    sent_count = 0
    if saved_count > 0:
        # Get mailbox
        mailbox_result = await db.execute(
            select(Mailbox).where(Mailbox.active == True).order_by(Mailbox.created_at.desc()).limit(1)
        )
        mailbox = mailbox_result.scalar_one_or_none()
        # Get template
        tpl_result = await db.execute(
            select(EmailTemplate).where(EmailTemplate.name == "auto_crm_first_contact").limit(1)
        )
        template = tpl_result.scalar_one_or_none()

        if mailbox and template:
            from backend.tasks.auto_crm_daily import send_development_email
            import asyncio as aio

            # Get newly saved customers (those created in the last few seconds)
            recent_result = await db.execute(
                select(Customer).where(
                    Customer.source == f"market_scan_{m.name}",
                    Customer.status == "lead",
                    Customer.email != "",
                ).order_by(Customer.created_at.desc()).limit(saved_count)
            )
            recent_customers = recent_result.scalars().all()

            for customer in recent_customers:
                if not customer.email:
                    continue
                try:
                    success = await aio.wait_for(
                        send_development_email(customer, mailbox, template),
                        timeout=15.0
                    )
                except aio.TimeoutError:
                    success = False
                if success:
                    customer.status = "contacted"
                    sent_count += 1
                    # Log
                    log = EmailLog(
                        mailbox_id=mailbox.id, customer_id=customer.id, direction="out",
                        subject=f"Introduction from TXD CO., LTD - {customer.company}",
                        body=f"Market scan auto-send to {customer.email}",
                        status="sent", sent_at=datetime.now(timezone.utc).isoformat(),
                    )
                    db.add(log)

            if sent_count > 0:
                await db.commit()
                print(f"  [Scan] Auto-sent {sent_count} emails")

    scan_result["leads_extracted"] = scan_result.get("leads_extracted", [])[:10]
    scan_result["emails_sent"] = sent_count
    return scan_result


@router.post("/{market_id}/score-leads")
async def score_market_leads(market_id: str, db: AsyncSession = Depends(get_db)):
    """Re-score all leads for a target market."""
    from backend.services.lead_scoring import LeadScoringEngine

    result = await db.execute(select(TargetMarket).where(TargetMarket.id == market_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Target market not found")

    # Get all customers for this market
    cust_result = await db.execute(
        select(Customer).where(Customer.matched_market == m.name)
    )
    customers = cust_result.scalars().all()

    updated = 0
    for customer in customers:
        score = LeadScoringEngine.calculate_score(
            company=customer.company or "",
            email=customer.email or "",
            phone=customer.phone or "",
            country=customer.country or "",
            intent_text=customer.notes or "",
            source=customer.source or "",
            matched_market=customer.matched_market or "",
            market_priority=m.priority,
        )
        if customer.score != score:
            customer.score = score
            updated += 1

    await db.commit()
    return {"customers_found": len(customers), "scores_updated": updated}
