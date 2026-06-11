"""Mailbox API routes — manage email accounts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.models.mailbox import Mailbox

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])


class MailboxCreate(BaseModel):
    name: str = ""
    email_address: str
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password_enc: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password_enc: str = ""
    use_ssl: bool = True
    assigned_to: str = ""
    daily_send_limit: int = 200


class MailboxUpdate(BaseModel):
    name: str | None = None
    email_address: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_password_enc: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password_enc: str | None = None
    use_ssl: bool | None = None
    assigned_to: str | None = None
    daily_send_limit: int | None = None
    active: bool | None = None


class MailboxResponse(BaseModel):
    id: str
    name: str
    email_address: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    use_ssl: bool
    routing_rules: str
    assigned_to: str
    daily_send_limit: int
    active: bool
    last_checked: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MailboxList(BaseModel):
    items: list[MailboxResponse]
    total: int


class TestConnectionRequest(BaseModel):
    imap_host: str
    imap_port: int = 993
    imap_username: str
    imap_password_enc: str
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password_enc: str = ""


class TestConnectionResponse(BaseModel):
    imap_ok: bool
    smtp_ok: bool
    message: str = ""


def mailbox_to_response(m: Mailbox) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "email_address": m.email_address,
        "imap_host": m.imap_host,
        "imap_port": m.imap_port,
        "smtp_host": m.smtp_host,
        "smtp_port": m.smtp_port,
        "use_ssl": m.use_ssl,
        "routing_rules": m.routing_rules,
        "assigned_to": m.assigned_to,
        "daily_send_limit": m.daily_send_limit,
        "active": m.active,
        "last_checked": m.last_checked,
        "created_at": str(m.created_at) if m.created_at else "",
        "updated_at": str(m.updated_at) if m.updated_at else "",
    }


@router.get("", response_model=MailboxList)
async def list_mailboxes(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    query = select(Mailbox)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(desc(Mailbox.created_at))
    result = await db.execute(query)
    items = result.scalars().all()
    return MailboxList(items=[mailbox_to_response(m) for m in items], total=total)


@router.get("/{mailbox_id}")
async def get_mailbox(mailbox_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == mailbox_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox_to_response(m)


@router.post("", status_code=201)
async def create_mailbox(data: MailboxCreate, db: AsyncSession = Depends(get_db)):
    m = Mailbox(**data.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return mailbox_to_response(m)


@router.put("/{mailbox_id}")
async def update_mailbox(mailbox_id: str, data: MailboxUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == mailbox_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(m, key, value)
    await db.commit()
    await db.refresh(m)
    return mailbox_to_response(m)


@router.delete("/{mailbox_id}", status_code=204)
async def delete_mailbox(mailbox_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == mailbox_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    await db.delete(m)
    await db.commit()


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(data: TestConnectionRequest):
    """Test IMAP and SMTP connections without saving."""
    imap_ok = False
    smtp_ok = False
    message = ""

    # Test IMAP
    if data.imap_host and data.imap_username:
        try:
            import imaplib
            imap = imaplib.IMAP4_SSL(data.imap_host, data.imap_port)
            imap.login(data.imap_username, data.imap_password_enc)
            imap.logout()
            imap_ok = True
        except Exception as e:
            message = f"IMAP: {str(e)[:80]}"

    # Test SMTP
    if data.smtp_host and data.smtp_username:
        try:
            import smtplib
            if data.smtp_port == 465:
                smtp = smtplib.SMTP_SSL(data.smtp_host, data.smtp_port)
            else:
                smtp = smtplib.SMTP(data.smtp_host, data.smtp_port)
                smtp.starttls()
            smtp.login(data.smtp_username, data.smtp_password_enc)
            smtp.quit()
            smtp_ok = True
        except Exception as e:
            if message:
                message += "; "
            message += f"SMTP: {str(e)[:80]}"

    if imap_ok and smtp_ok:
        message = "Connection successful"
    elif imap_ok:
        message = message or "IMAP OK, SMTP not tested"
    else:
        message = message or "Connection failed"

    return TestConnectionResponse(imap_ok=imap_ok, smtp_ok=smtp_ok, message=message)
