"""Customer/Lead API routes — manage prospects and clients."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.customer import Customer
from backend.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerList

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=CustomerList)
async def list_customers(
    source: str | None = None,
    market: str | None = None,
    score_min: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Customer)

    if source:
        query = query.where(Customer.source.startswith(source))
    if market:
        query = query.where(Customer.matched_market == market)
    if score_min is not None:
        query = query.where(Customer.score >= score_min)
    if status:
        query = query.where(Customer.status == status)
    if search:
        query = query.where(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.company.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
                Customer.country.ilike(f"%{search}%"),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(Customer.score), desc(Customer.created_at))
    result = await db.execute(query)
    items = result.scalars().all()

    return CustomerList(items=items, total=total)


@router.get("/stats/info")
async def get_customer_stats(db: AsyncSession = Depends(get_db)):
    """Get customer statistics: total, new, status breakdown."""
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    from datetime import timedelta

    total = (await db.execute(select(func.count()).select_from(select(Customer).subquery()))).scalar() or 0
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.created_at >= today_start).subquery()))).scalar() or 0
    week_start = today_start - timedelta(days=today_start.weekday())
    week_new = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.created_at >= week_start).subquery()))).scalar() or 0

    source_query = await db.execute(select(Customer.source, func.count()).group_by(Customer.source))
    sources = {row[0] or "unknown": row[1] for row in source_query.fetchall()}

    hot = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.score >= 80).subquery()))).scalar() or 0
    warm = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.score >= 60, Customer.score < 80).subquery()))).scalar() or 0
    cold = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.score >= 30, Customer.score < 60).subquery()))).scalar() or 0

    # Status breakdown
    leads = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.status == "lead").subquery()))).scalar() or 0
    contacted = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.status == "contacted").subquery()))).scalar() or 0
    interested = (await db.execute(select(func.count()).select_from(select(Customer).where(Customer.status == "interested").subquery()))).scalar() or 0

    return {
        "total": total,
        "today_new": today_new,
        "week_new": week_new,
        "sources": sources,
        "scores": {"hot": hot, "warm": warm, "cold": cold},
        "statuses": {"lead": leads, "contacted": contacted, "interested": interested},
    }


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(data: CustomerCreate, db: AsyncSession = Depends(get_db)):
    from backend.services.lead_scoring import LeadScoringEngine

    if data.email:
        result = await db.execute(select(Customer).where(Customer.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.model_dump(exclude_unset=True).items():
                if value:
                    setattr(existing, key, value)
            existing.score = LeadScoringEngine.calculate_score(
                company=existing.company or "", email=existing.email or "",
                phone=existing.phone or "", country=existing.country or "",
                intent_text=existing.notes or "", source=existing.source or "",
            )
            await db.commit()
            await db.refresh(existing)
            return existing

    customer = Customer(**data.model_dump())
    customer.status = "lead"  # New customers always start as lead
    customer.score = LeadScoringEngine.calculate_score(
        company=customer.company or "", email=customer.email or "",
        phone=customer.phone or "", country=customer.country or "",
        intent_text=customer.notes or "", source=customer.source or "",
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: str, data: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)
    return customer


@router.post("/{customer_id}/mark-interested")
async def mark_customer_interested(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a customer as interested."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.status = "interested"
    await db.commit()
    return {"status": "ok", "message": "Customer marked as interested"}


@router.post("/{customer_id}/unmark-interested")
async def unmark_customer_interested(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Revert a customer from interested back to lead."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.status = "lead"
    await db.commit()
    return {"status": "ok", "message": "Customer reverted to lead"}
    return {"status": "ok", "message": "Customer marked as interested"}


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(customer)
    await db.commit()


@router.get("/export/csv")
async def export_customers_csv(db: AsyncSession = Depends(get_db)):
    """Export all customers as CSV file."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
    customers = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    # Header
    writer.writerow(["Name", "Email", "Company", "Country", "Website", "Source", "Status", "Score", "Notes", "Created"])
    for c in customers:
        writer.writerow([
            c.name or "", c.email or "", c.company or "", c.country or "",
            c.website or "", c.source or "", c.status or "", c.score or 0,
            (c.notes or "")[:500], str(c.created_at or "")[:19],
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )
