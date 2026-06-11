"""Target market API routes — define markets, generate keywords, trigger scans."""

import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.target_market import TargetMarket
from backend.models.customer import Customer
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

    prompt = f"""Generate 10 effective search queries for finding buyers of the following product/market:

Market: {data.name}
Keywords: {', '.join(data.keywords) if data.keywords else 'N/A'}
Products: {', '.join(data.products) if data.products else 'N/A'}
Industries: {', '.join(data.industries) if data.industries else 'N/A'}

The queries should be things real buyers would search for on Google and B2B platforms.
Include buyer-intent phrases like: "buyer", "importer", "supplier", "wholesale", "distributor", "RFQ", "quotation"

Respond with a JSON array of strings only, no explanation.
Example: ["PP hollow sheet buyer USA", "corrugated plastic sheet importer Europe", ...]"""
    try:
        response = await agent.chat(prompt, temperature=0.7)
        # Extract JSON array
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            keywords = json.loads(match.group())
            return {"keywords": keywords[:15]}
        return {"keywords": [data.name]}
    except Exception:
        # Fallback: generate basic keywords
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
