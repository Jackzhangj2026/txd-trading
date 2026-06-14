"""Email campaign API — send development emails with human-like behavior."""

import asyncio
import base64
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.customer import Customer
from backend.models.email_log import EmailLog
from backend.models.mailbox import Mailbox
from backend.models.email_template import EmailTemplate
from backend.services.email_service import EmailService

router = APIRouter(prefix="/api/campaign", tags=["campaign"])

FACTORY_IMG_DIR = Path(__file__).parent.parent.parent / "factory image"


# ─── Factory Image List ─────────────────────────────────────────────

@router.get("/images")
async def list_factory_images():
    """List all available factory images."""
    if not FACTORY_IMG_DIR.exists():
        return {"images": []}
    images = []
    for f in sorted(FACTORY_IMG_DIR.iterdir()):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp") and not f.name.startswith("."):
            images.append({
                "filename": f.name,
                "url": f"/factory-images/{f.name}",
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return {"images": images}


# ─── AI Template Generator ─────────────────────────────────────────

@router.post("/generate-template")
async def generate_email_template():
    """Generate a cold outreach email template using LLM."""
    from backend.services.email_generator import EmailGenerator
    gen = EmailGenerator()
    result = await gen.generate_email(
        customer_name="{{name}}",
        company_name="{{company}}",
        country="{{country}}",
        product_interest="PP hollow sheets and packaging solutions",
        template_style="professional",
    )
    return result


# ─── Campaign Send ─────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    mailbox_ids: list[str]  # One or more mailboxes to send from
    customer_filters: dict = {}  # {"status": "lead", "source": "auto_crm_search", "score_min": 30}
    customer_ids: list[str] = []  # Specific customers (overrides filters)
    subject: str = ""
    body: str = ""
    template_id: str = ""  # Optional: use body from template
    max_emails: int = 20  # Total cap
    human_delay_min: int = 30  # Seconds between sends (min)
    human_delay_max: int = 180  # Seconds between sends (max)
    image_filenames: list[str] = []  # Factory image filenames to embed in email


class CampaignStatus(BaseModel):
    campaign_id: str
    total_target: int
    sent: int = 0
    failed: int = 0
    status: str = "pending"  # pending / running / completed / failed
    message: str = ""


@router.post("/send")
async def send_campaign(data: CampaignRequest, db: AsyncSession = Depends(get_db)):
    """Send development emails to selected customers via selected mailboxes."""
    campaign_id = f"camp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

    # 1. Get mailboxes
    mailbox_ids = list(set(data.mailbox_ids))
    mailboxes = []
    for mid in mailbox_ids:
        result = await db.execute(select(Mailbox).where(Mailbox.id == mid, Mailbox.active == True))
        mb = result.scalar_one_or_none()
        if mb:
            mailboxes.append(mb)

    if not mailboxes:
        raise HTTPException(status_code=400, detail="No valid active mailboxes found")

    # 2. Get customers
    if data.customer_ids:
        customers = []
        for cid in data.customer_ids:
            result = await db.execute(select(Customer).where(Customer.id == cid))
            c = result.scalar_one_or_none()
            if c and c.email:
                customers.append(c)
    else:
        filters = data.customer_filters
        query = select(Customer).where(Customer.email != "")
        status = filters.get("status")
        source = filters.get("source")
        score_min = filters.get("score_min")
        market = filters.get("market")

        if status:
            query = query.where(Customer.status == status)
        if source:
            query = query.where(Customer.source.like(f"%{source}%"))
        if score_min is not None:
            query = query.where(Customer.score >= score_min)
        if market:
            query = query.where(Customer.matched_market == market)

        query = query.order_by(Customer.score.desc()).limit(data.max_emails)
        result = await db.execute(query)
        customers = list(result.scalars().all())

    if not customers:
        raise HTTPException(status_code=400, detail="No customers found matching criteria")

    # Cap at max_emails
    customers = customers[:data.max_emails]

    # 3. Build email content
    subject = data.subject
    body = data.body

    if data.template_id and not body:
        result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == data.template_id))
        tpl = result.scalar_one_or_none()
        if tpl:
            body = tpl.body_template
            if not subject:
                subject = tpl.subject_template

    if not subject or not body:
        raise HTTPException(status_code=400, detail="Subject and body are required (or provide a template_id)")

    # 4. Send with human-like delays (fire-and-forget in background)
    # Return immediately with campaign_id, actual sending is async

    asyncio.create_task(
        _run_campaign(campaign_id, mailboxes, customers, subject, body,
                      data.human_delay_min, data.human_delay_max, data.image_filenames, db)
    )

    return {
        "campaign_id": campaign_id,
        "mailboxes": [m.email_address for m in mailboxes],
        "total_target": len(customers),
        "status": "started",
        "message": f"Campaign started: {len(customers)} emails via {len(mailboxes)} mailbox(es) with human-like delays",
    }


async def _run_campaign(campaign_id: str, mailboxes: list[Mailbox], customers: list[Customer],
                         subject_template: str, body_template: str,
                         delay_min: int, delay_max: int,
                         image_filenames: list[str] = None, db: AsyncSession = None):
    """Run the campaign in background with human-like delays."""
    print(f"[Campaign {campaign_id}] Starting: {len(customers)} customers, {len(mailboxes)} mailboxes")

    # Pre-load images as base64
    inline_images = []
    if image_filenames:
        from pathlib import Path
        img_dir = Path(__file__).parent.parent.parent / "factory image"
        for fname in image_filenames:
            img_path = img_dir / fname
            if img_path.exists():
                ext = img_path.suffix.lower()
                mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
                mime_type = mime.get(ext.lstrip("."), "image/jpeg")
                b64 = base64.b64encode(img_path.read_bytes()).decode()
                inline_images.append(f'<img src="data:{mime_type};base64,{b64}" alt="{fname}" style="max-width:100%;margin:10px 0;border-radius:4px;">')

    sent_count = 0
    failed_count = 0
    mailbox_idx = 0

    # Track today's sends per mailbox for rate limiting
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_counts = {m.id: 0 for m in mailboxes}

    # Check existing today's sends from email_logs
    from sqlalchemy import func as sa_func
    for mb in mailboxes:
        count_result = await db.execute(
            select(sa_func.count()).select_from(
                select(EmailLog).where(
                    EmailLog.mailbox_id == mb.id,
                    EmailLog.sent_at >= today_start.isoformat(),
                ).subquery()
            )
        )
        today_counts[mb.id] = count_result.scalar() or 0

    for i, customer in enumerate(customers):
        if not customer.email:
            continue

        # Rotate mailboxes
        mb = mailboxes[mailbox_idx % len(mailboxes)]
        mailbox_idx += 1

        # Check daily limit
        if today_counts[mb.id] >= (mb.daily_send_limit or 200):
            print(f"  [Campaign] Mailbox {mb.email_address} hit daily limit, skipping")
            continue

        # Personalize
        personalized_subject = subject_template.replace("{{name}}", customer.name or "")\
            .replace("{{company}}", customer.company or "")\
            .replace("{{country}}", customer.country or "")
        personalized_body = body_template.replace("{{name}}", customer.name or "Valued Partner")\
            .replace("{{company}}", customer.company or "your company")\
            .replace("{{country}}", customer.country or "")

        # Randomize subject slightly (lowercase/first name variation)
        name_variants = [customer.name or "there", customer.name.split()[0] if customer.name else "there"]
        greeting_name = random.choice(name_variants)
        personalized_body = personalized_body.replace("{{greeting_name}}", greeting_name)

        # Embed images: replace {{image_1}}..{{image_N}} placeholders with base64 inline images
        if inline_images:
            for idx, img_html in enumerate(inline_images, 1):
                placeholder = f"{{image_{idx}}}"
                if placeholder in personalized_body:
                    personalized_body = personalized_body.replace(placeholder, img_html)
            # Append any remaining images as gallery at the bottom
            remaining = [img for idx, img in enumerate(inline_images, 1)
                         if f"{{image_{idx}}}" not in body_template]
            if remaining:
                gal = '<div style="margin-top:20px;text-align:center;"><h3 style="color:#333;margin-bottom:10px;">Our Products</h3></div>'
                personalized_body = personalized_body.replace("</body>", "") if "</body>" in personalized_body else personalized_body
                personalized_body += gal + "".join(remaining)
                if "</body>" in body_template:
                    personalized_body += "</body>"

        # Send
        from_addr = f"{mb.name or 'Sales'} <{mb.email_address}>"
        success = await EmailService.send_email(
            smtp_host=mb.smtp_host, smtp_port=mb.smtp_port,
            smtp_user=mb.smtp_username, smtp_pass=mb.smtp_password_enc,
            from_addr=from_addr, to_addr=customer.email,
            subject=personalized_subject, body=personalized_body,
        )

        # Log
        now = datetime.now(timezone.utc)
        log = EmailLog(
            mailbox_id=mb.id, customer_id=customer.id, direction="out",
            subject=personalized_subject,
            body=f"[Campaign {campaign_id}] {personalized_body[:200]}",
            status="sent" if success else "failed",
            sent_at=now.isoformat(),
        )
        db.add(log)
        today_counts[mb.id] += 1

        if success:
            sent_count += 1
            customer.status = "contacted"
        else:
            failed_count += 1

        await db.commit()

        # Human-like delay between sends
        if i < len(customers) - 1:
            delay = random.randint(delay_min, delay_max)
            print(f"  [Campaign] Sent {i+1}/{len(customers)} to {customer.email} via {mb.email_address}. Waiting {delay}s...")
            await asyncio.sleep(delay)

    print(f"[Campaign {campaign_id}] Done: {sent_count} sent, {failed_count} failed")
