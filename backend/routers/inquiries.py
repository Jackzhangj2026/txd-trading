"""Inquiry API routes — submit, classify, list, manage."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.inquiry import Inquiry
from backend.models.customer import Customer
from backend.schemas.inquiry import InquiryCreate, InquiryUpdate, InquiryResponse, InquiryList
from backend.agents import TradeAgent

router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])


async def classify_inquiry(message: str) -> tuple[str, str, str]:
    """Classify inquiry using LLM or keyword fallback.
    Returns (classification, ai_summary, target_market).
    """
    try:
        agent = TradeAgent(system_prompt="You are an inquiry classifier for a PP hollow board trading company.")
        result = await agent.chat(f"""Classify this buyer inquiry:
- Classification: high (real purchase intent) / medium (potential) / low (unclear) / spam
- Extract: product interest, estimated quantity, urgency level
- Target market: what industry/application does this relate to?

Inquiry: {message}

Respond in format:
CLASSIFICATION: <high|medium|low|spam>
SUMMARY: <one-line summary>
MARKET: <target market or "general">""")

        lines = result.strip().split("\n")
        classification = "medium"
        summary = ""
        market = "general"

        for line in lines:
            if line.startswith("CLASSIFICATION:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in ("high", "medium", "low", "spam"):
                    classification = val
            elif line.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif line.startswith("MARKET:"):
                market = line.split(":", 1)[1].strip()

        return classification, summary, market
    except Exception:
        # Keyword fallback if LLM unavailable
        msg_lower = message.lower()
        high_signals = ["order", "quote", "price", "buy", "purchase", "urgent"]
        low_signals = ["hi", "hello", "test", "info", "whatsapp"]
        spam_signals = ["seo", "rank", "marketing", "social media"]

        high_count = sum(1 for s in high_signals if s in msg_lower)
        low_count = sum(1 for s in low_signals if s in msg_lower)
        spam_count = sum(1 for s in spam_signals if s in msg_lower)

        if spam_count > 0:
            return "spam", "Spam detected", "general"
        elif high_count >= 2:
            return "high", "High purchase intent detected", "packaging"
        elif high_count >= 1:
            return "medium", "Potential inquiry", "packaging"
        else:
            return "low", "Low relevance inquiry", "general"


@router.post("", response_model=InquiryResponse, status_code=201)
async def create_inquiry(data: InquiryCreate, db: AsyncSession = Depends(get_db)):
    """Submit a new inquiry — auto-classifies, creates/links customer, auto-scores."""
    from backend.services.lead_scoring import LeadScoringEngine

    customer = None
    customer_id = data.customer_id

    # Auto-create or find customer by email
    if data.customer_email:
        result = await db.execute(select(Customer).where(Customer.email == data.customer_email))
        customer = result.scalar_one_or_none()
        if not customer:
            customer = Customer(
                name=data.customer_name or data.customer_email.split("@")[0],
                email=data.customer_email,
                company=data.customer_company,
                country=data.customer_country,
                source=data.source,
                notes=data.message[:500],
            )
            db.add(customer)
            await db.flush()
        else:
            # Update existing customer info
            if data.customer_name and not customer.name:
                customer.name = data.customer_name
            if data.customer_company and not customer.company:
                customer.company = data.customer_company
            if data.customer_country and not customer.country:
                customer.country = data.customer_country

        customer_id = customer.id

    elif data.customer_id:
        result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
        customer = result.scalar_one_or_none()

    # Classify the inquiry
    classification, summary, market = await classify_inquiry(data.message)

    # Create inquiry
    inquiry = Inquiry(
        customer_id=customer_id,
        product_id=data.product_id,
        message=data.message,
        source=data.source,
        classification=classification,
        ai_summary=summary,
        status="classified" if classification != "spam" else "closed",
    )
    db.add(inquiry)
    await db.flush()

    # Auto-score the customer
    if customer:
        score = LeadScoringEngine.calculate_score(
            company=customer.company or "",
            email=customer.email or "",
            phone=customer.phone or "",
            country=customer.country or "",
            intent_text=customer.notes or " " + data.message,
            source=customer.source or data.source,
            matched_market=market,
        )
        customer.score = score
        customer.matched_market = market

    await db.commit()
    await db.refresh(inquiry)
    return inquiry


@router.get("", response_model=InquiryList)
async def list_inquiries(
    status: str | None = None,
    classification: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Inquiry)

    if status:
        query = query.where(Inquiry.status == status)
    if classification:
        query = query.where(Inquiry.classification == classification)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(Inquiry.created_at))
    result = await db.execute(query)
    items = result.scalars().all()

    return InquiryList(items=items, total=total)


@router.get("/{inquiry_id}", response_model=InquiryResponse)
async def get_inquiry(inquiry_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Inquiry).where(Inquiry.id == inquiry_id))
    inquiry = result.scalar_one_or_none()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return inquiry


@router.put("/{inquiry_id}", response_model=InquiryResponse)
async def update_inquiry(inquiry_id: str, data: InquiryUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Inquiry).where(Inquiry.id == inquiry_id))
    inquiry = result.scalar_one_or_none()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(inquiry, key, value)

    await db.commit()
    await db.refresh(inquiry)
    return inquiry
