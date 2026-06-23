"""Email API routes — templates, log, sending."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.email_template import EmailTemplate
from backend.models.email_log import EmailLog
from backend.models.mailbox import Mailbox
from backend.models.customer import Customer

router = APIRouter(prefix="/api/emails", tags=["emails"])


# === Templates ===

class TemplateCreate(BaseModel):
    name: str
    category: str = ""
    subject_template: str = ""
    body_template: str = ""
    variables: str = "[]"


class TemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    subject_template: str | None = None
    body_template: str | None = None
    variables: str | None = None
    active: bool | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    subject_template: str
    body_template: str
    variables: str
    active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TemplateList(BaseModel):
    items: list[TemplateResponse]
    total: int


def template_to_response(t: EmailTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "category": t.category,
        "subject_template": t.subject_template,
        "body_template": t.body_template,
        "variables": t.variables,
        "active": t.active,
        "created_at": str(t.created_at) if t.created_at else "",
        "updated_at": str(t.updated_at) if t.updated_at else "",
    }


@router.get("/templates", response_model=TemplateList)
async def list_templates(category: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(EmailTemplate)
    if category:
        query = query.where(EmailTemplate.category == category)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(EmailTemplate.name)
    result = await db.execute(query)
    items = result.scalars().all()
    return TemplateList(items=[template_to_response(t) for t in items], total=total)


@router.get("/templates/{template_id}")
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return template_to_response(t)


@router.post("/templates", status_code=201)
async def create_template(data: TemplateCreate, db: AsyncSession = Depends(get_db)):
    t = EmailTemplate(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return template_to_response(t)


@router.put("/templates/{template_id}")
async def update_template(template_id: str, data: TemplateUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(t, key, value)
    await db.commit()
    await db.refresh(t)
    return template_to_response(t)


# === Email Log ===

class EmailLogResponse(BaseModel):
    id: str
    mailbox_id: str | None
    customer_id: str | None
    direction: str
    subject: str
    body: str
    status: str
    sent_at: str
    created_at: str

    model_config = {"from_attributes": True}


class EmailLogList(BaseModel):
    items: list[EmailLogResponse]
    total: int


@router.get("/log", response_model=EmailLogList)
async def list_email_log(
    customer_id: str | None = None,
    mailbox_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailLog)
    if customer_id:
        query = query.where(EmailLog.customer_id == customer_id)
    if mailbox_id:
        query = query.where(EmailLog.mailbox_id == mailbox_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(EmailLog.created_at))
    result = await db.execute(query)
    items = result.scalars().all()
    return EmailLogList(items=items, total=total)


# === Send ===

class SendEmailRequest(BaseModel):
    mailbox_id: str
    customer_id: str
    subject: str
    body: str


@router.post("/send")
async def send_email(data: SendEmailRequest, db: AsyncSession = Depends(get_db)):
    """Queue an email for sending (logs it, actual send via service)."""
    # Verify mailbox exists
    result = await db.execute(select(Mailbox).where(Mailbox.id == data.mailbox_id))
    mailbox = result.scalar_one_or_none()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    # Verify customer exists
    result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Create email log entry
    now = datetime.now(timezone.utc).isoformat()
    log = EmailLog(
        mailbox_id=data.mailbox_id,
        customer_id=data.customer_id,
        direction="out",
        subject=data.subject,
        body=data.body,
        status="pending",
        sent_at=now,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return {"id": log.id, "status": "pending", "message": "Email queued for sending"}


# === Email Stats for Dashboard ===

@router.get("/stats")
async def email_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard stats: today's emails, new leads, contacted, interested."""
    from datetime import date
    today = date.today().isoformat()

    sent = (await db.execute(
        select(func.count()).select_from(EmailLog).where(EmailLog.sent_at >= today)
    )).scalar() or 0

    new_today = (await db.execute(
        select(func.count()).select_from(Customer).where(Customer.created_at >= today)
    )).scalar() or 0

    contacted = (await db.execute(
        select(func.count()).select_from(Customer).where(Customer.status == "contacted")
    )).scalar() or 0

    interested = (await db.execute(
        select(func.count()).select_from(Customer).where(Customer.status == "interested")
    )).scalar() or 0

    pending = (await db.execute(
        select(func.count()).select_from(Customer).where(
            Customer.status == "lead", Customer.email == ""
        )
    )).scalar() or 0

    return {
        "today_sent": sent,
        "new_today": new_today,
        "contacted": contacted,
        "interested": interested,
        "pending_leads": pending,
    }


# === Check / Test ===

class CheckInboxRequest(BaseModel):
    mailbox_id: str


@router.post("/check")
async def check_inbox(data: CheckInboxRequest, db: AsyncSession = Depends(get_db)):
    """Check a mailbox for new emails via IMAP."""
    result = await db.execute(select(Mailbox).where(Mailbox.id == data.mailbox_id))
    mailbox = result.scalar_one_or_none()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    from backend.services.email_service import EmailService

    emails = await EmailService.check_inbox(
        imap_host=mailbox.imap_host,
        imap_port=mailbox.imap_port,
        imap_user=mailbox.imap_username,
        imap_pass=mailbox.imap_password_enc,
        use_ssl=mailbox.use_ssl,
    )

    # Update last_checked
    mailbox.last_checked = datetime.now(timezone.utc).isoformat()
    await db.commit()

    # Classify each email
    classified = []
    for email_data in emails:
        classification = await EmailService.classify_email(
            email_data["subject"], email_data["body"]
        )

        # Log it
        log = EmailLog(
            mailbox_id=data.mailbox_id,
            direction="in",
            subject=email_data["subject"],
            body=email_data["body"][:2000],
            status="received",
            message_id=email_data["message_id"],
            sent_at=email_data["date"],
        )
        db.add(log)
        classified.append({**email_data, "classification": classification})

    await db.commit()

    return {
        "emails_found": len(emails),
        "emails": classified,
    }
