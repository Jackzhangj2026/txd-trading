"""Customer/Lead API routes — manage prospects and clients."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.customer import Customer
from backend.models.inquiry import Inquiry
from backend.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerList

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=CustomerList)
async def list_customers(
    source: str | None = None,
    market: str | None = None,
    score_min: int | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Customer)

    if source:
        query = query.where(Customer.source == source)
    if market:
        query = query.where(Customer.matched_market == market)
    if score_min is not None:
        query = query.where(Customer.score >= score_min)
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

    # Check if customer with same email exists
    if data.email:
        result = await db.execute(select(Customer).where(Customer.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            # Update existing instead of creating duplicate
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


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(customer)
    await db.commit()


