"""Email campaign API — send with persistence + inbox management."""

import asyncio
import base64
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.campaign import Campaign
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
    from backend.services.email_generator import EmailGenerator
    gen = EmailGenerator()
    result = await gen.generate_email(
        customer_name="{{name}}", company_name="{{company}}",
        country="{{country}}", product_interest="PP hollow sheets and packaging solutions",
        template_style="professional",
    )
    return result

# ─── Campaign Send ─────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    mailbox_ids: list[str]
    customer_filters: dict = {}
    customer_ids: list[str] = []
    subject: str = ""
    body: str = ""
    template_id: str = ""
    max_emails: int = 20
    human_delay_min: int = 30
    human_delay_max: int = 180
    image_filenames: list[str] = []

@router.post("/send")
async def send_campaign(data: CampaignRequest, db: AsyncSession = Depends(get_db)):
    """Send development emails — saves campaign to DB, runs in background."""
    # Save campaign to DB immediately
    campaign = Campaign(
        mailbox_ids=json.dumps(list(set(data.mailbox_ids))),
        customer_count=0,
        subject_preview=data.subject[:200] if data.subject else "",
        status="pending",
        delay_min=data.human_delay_min,
        delay_max=data.human_delay_max,
        image_filenames=json.dumps(data.image_filenames),
    )
    db.add(campaign)
    await db.flush()
    cid = campaign.id

    # 1. Get mailboxes
    mailbox_ids = list(set(data.mailbox_ids))
    mailboxes = []
    for mid in mailbox_ids:
        result = await db.execute(select(Mailbox).where(Mailbox.id == mid, Mailbox.active == True))
        mb = result.scalar_one_or_none()
        if mb:
            mailboxes.append(mb)
    if not mailboxes:
        campaign.status = "failed"
        campaign.error_message = "No valid active mailboxes found"
        await db.commit()
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
        if filters.get("status"):
            query = query.where(Customer.status == filters["status"])
        if filters.get("source"):
            query = query.where(Customer.source.like(f"%{filters['source']}%"))
        if filters.get("score_min") is not None:
            query = query.where(Customer.score >= filters["score_min"])
        query = query.order_by(Customer.score.desc()).limit(data.max_emails)
        result = await db.execute(query)
        customers = list(result.scalars().all())

    if not customers:
        campaign.status = "failed"
        campaign.error_message = "No customers found"
        await db.commit()
        raise HTTPException(status_code=400, detail="No customers found matching criteria")

    customers = customers[:data.max_emails]
    campaign.customer_count = len(customers)

    # 3. Build content
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
        campaign.status = "failed"
        campaign.error_message = "Subject and body required"
        await db.commit()
        raise HTTPException(status_code=400, detail="Subject and body required")

    # 4. Mark as running and launch
    campaign.status = "running"
    campaign.subject_preview = subject[:200]
    await db.commit()

    asyncio.create_task(
        _run_campaign(campaign, mailboxes, customers, subject, body,
                      data.human_delay_min, data.human_delay_max, data.image_filenames)
    )

    return {
        "campaign_id": campaign.id,
        "mailboxes": [m.email_address for m in mailboxes],
        "total_target": len(customers),
        "status": "running",
        "message": f"Campaign started: {len(customers)} emails via {len(mailboxes)} mailbox(es)",
    }

# ─── Campaign History ──────────────────────────────────────────────

@router.get("/history")
async def get_campaign_history(db: AsyncSession = Depends(get_db)):
    """Get all campaigns from DB."""
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(50)
    )
    campaigns = result.scalars().all()
    items = []
    for c in campaigns:
        items.append({
            "id": c.id,
            "campaign_name": c.campaign_name,
            "customer_count": c.customer_count,
            "subject_preview": c.subject_preview,
            "status": c.status,
            "sent_count": c.sent_count,
            "failed_count": c.failed_count,
            "error_message": c.error_message,
            "created_at": str(c.created_at) if c.created_at else "",
        })
    return {"items": items, "total": len(items)}


async def _run_campaign(campaign: Campaign, mailboxes: list[Mailbox], customers: list[Customer],
                         subject_template: str, body_template: str,
                         delay_min: int, delay_max: int,
                         image_filenames: list[str] = None):
    """Run campaign in background (no db param — creates its own session)."""
    from backend.database import async_session as _get_session
    print(f"[Campaign {campaign.id}] Starting: {len(customers)} customers, {len(mailboxes)} mailboxes")
    async with _get_session() as db:
        try:
            # Refresh campaign from DB
            result = await db.execute(select(Campaign).where(Campaign.id == campaign.id))
            camp = result.scalar_one_or_none()
            if not camp:
                return

            # Pre-load images as base64
            inline_images = []
            if image_filenames:
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
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_counts = {m.id: 0 for m in mailboxes}

            for mb in mailboxes:
                count_result = await db.execute(
                    select(sa_func.count()).select_from(
                        select(EmailLog).where(EmailLog.mailbox_id == mb.id, EmailLog.sent_at >= today_start.isoformat()).subquery()
                    )
                )
                today_counts[mb.id] = count_result.scalar() or 0

            for i, customer in enumerate(customers):
                if not customer.email:
                    continue
                mb = mailboxes[mailbox_idx % len(mailboxes)]
                mailbox_idx += 1
                if today_counts[mb.id] >= (mb.daily_send_limit or 200):
                    print(f"  [Campaign] {mb.email_address} hit limit, skip")
                    continue

                personalized_subject = subject_template.replace("{{name}}", customer.name or "")\
                    .replace("{{company}}", customer.company or "").replace("{{country}}", customer.country or "")
                personalized_body = body_template.replace("{{name}}", customer.name or "Valued Partner")\
                    .replace("{{company}}", customer.company or "your company").replace("{{country}}", customer.country or "")

                if inline_images:
                    for idx, img_html in enumerate(inline_images, 1):
                        # Match both formats: {image_1} (campaign) and {{IMAGE_1}} (auto-crm template)
                        for ph in [f"{{image_{idx}}}", f"{{IMAGE_{idx}}}", f"{{{{image_{idx}}}}}", f"{{{{IMAGE_{idx}}}}}"]:
                            if ph in personalized_body:
                                personalized_body = personalized_body.replace(ph, img_html)
                    remaining = [img for idx, img in enumerate(inline_images, 1)
                                 if f"{{image_{idx}}}" not in body_template 
                                 and f"{{IMAGE_{idx}}}" not in body_template
                                 and f"{{{{image_{idx}}}}}" not in body_template
                                 and f"{{{{IMAGE_{idx}}}}}" not in body_template]
                    if remaining:
                        gal = '<div style="margin-top:20px;text-align:center;"><h3>Our Products</h3></div>'
                        personalized_body += gal + "".join(remaining)

                from_addr = f"{mb.name or 'Sales'} <{mb.email_address}>"
                success = await EmailService.send_email(
                    smtp_host=mb.smtp_host, smtp_port=mb.smtp_port,
                    smtp_user=mb.smtp_username, smtp_pass=mb.smtp_password_enc,
                    from_addr=from_addr, to_addr=customer.email,
                    subject=personalized_subject, body=personalized_body,
                )

                now = datetime.now(timezone.utc)
                log = EmailLog(
                    mailbox_id=mb.id, customer_id=customer.id, direction="out",
                    subject=personalized_subject,
                    body=f"[Campaign {campaign.id}] {personalized_body[:200]}",
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

                if i < len(customers) - 1:
                    delay = random.randint(delay_min, delay_max)
                    print(f"  [Campaign] {i+1}/{len(customers)} to {customer.email}. Wait {delay}s")
                    await asyncio.sleep(delay)

            # Update campaign status
            camp.status = "completed"
            camp.sent_count = sent_count
            camp.failed_count = failed_count
            await db.commit()
            print(f"[Campaign {campaign.id}] Done: {sent_count} sent, {failed_count} failed")

        except Exception as e:
            print(f"[Campaign {campaign.id}] Error: {e}")
            import traceback
            traceback.print_exc()
            try:
                camp.status = "failed"
                camp.error_message = str(e)[:200]
                await db.commit()
            except:
                pass

# ─── Inbox Management ──────────────────────────────────────────────

class InboxScanRequest(BaseModel):
    mailbox_id: str
    max_emails: int = 5  # Small default for local LLM speed

class InboxActionRequest(BaseModel):
    email_id: str  # The mail_message_id from IMAP
    mailbox_id: str
    action: str  # mark_customer_interested / create_customer / mark_read / delete
    customer_name: str = ""
    customer_email: str = ""

@router.post("/inbox/scan")
async def scan_inbox(data: InboxScanRequest, db: AsyncSession = Depends(get_db)):
    """Scan a mailbox's inbox, fetch unseen emails, AI analyze each."""
    result = await db.execute(select(Mailbox).where(Mailbox.id == data.mailbox_id))
    mailbox = result.scalar_one_or_none()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    if not mailbox.imap_host:
        raise HTTPException(status_code=400, detail="Mailbox has no IMAP configured")

    # Fetch emails from IMAP (with timeout)
    try:
        emails = await asyncio.wait_for(
            EmailService.check_inbox(
                imap_host=mailbox.imap_host, imap_port=mailbox.imap_port,
                imap_user=mailbox.imap_username, imap_pass=mailbox.imap_password_enc,
                use_ssl=mailbox.use_ssl,
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="IMAP connection timed out. Check your IMAP credentials.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IMAP connection failed: {str(e)[:100]}")

    # Update last_checked
    mailbox.last_checked = datetime.now(timezone.utc).isoformat()
    await db.commit()

    # AI analyze each email (with timeout per email)
    from backend.agents import TradeAgent
    agent = TradeAgent(system_prompt="You are an email analyst for a PP hollow board trading company.")

    analyzed = []
    for email_data in emails[-data.max_emails:]:
        try:
            classification = await asyncio.wait_for(
                EmailService.classify_email(email_data["subject"], email_data["body"]),
                timeout=20.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            classification = {"category": "general_inquiry", "summary": "Classification timeout", "urgency": "low", "product": "unknown"}
            print(f"  [Inbox] Classification timeout: {e}")

        # Generate handling suggestion (fast keyword-based fallback)
        category = classification.get("category", "general_inquiry")
        action_map = {
            "price_inquiry": ("reply_quote", "Price inquiry - send quotation"),
            "order_confirmation": ("mark_interested", "Order confirmation - mark as interested"),
            "complaint": ("manual_review", "Complaint - needs human review"),
            "negotiation": ("manual_review", "Negotiation - needs human review"),
            "spam": ("mark_spam", "Spam detected"),
        }
        suggested_action, suggestion_reason = action_map.get(category, ("manual_review", "General inquiry - review manually"))

        analyzed.append({
            "message_id": email_data["message_id"],
            "subject": email_data["subject"],
            "from": email_data["from"],
            "body": email_data["body"][:1000],
            "date": email_data["date"],
            "classification": classification,
            "suggested_action": suggested_action,
            "suggestion_reason": suggestion_reason,
        })

    return {
        "mailbox_id": data.mailbox_id,
        "mailbox_email": mailbox.email_address,
        "emails_found": len(emails),
        "emails_analyzed": len(analyzed),
        "emails": analyzed,
    }


@router.post("/inbox/action")
async def inbox_action(data: InboxActionRequest, db: AsyncSession = Depends(get_db)):
    """Execute an action on an inbox email."""
    if data.action == "mark_customer_interested":
        # Find customer by email or name
        if data.customer_email:
            result = await db.execute(
                select(Customer).where(Customer.email == data.customer_email)
            )
            customer = result.scalar_one_or_none()
            if customer:
                customer.status = "interested"
                await db.commit()
                return {"status": "ok", "action": "marked_interested", "customer_id": customer.id}
        return {"status": "error", "message": "Customer not found"}

    elif data.action == "create_customer":
        customer = Customer(
            name=data.customer_name or data.customer_email.split("@")[0] if data.customer_email else "Unknown",
            email=data.customer_email,
            source="email_inquiry",
            status="interested",
        )
        db.add(customer)
        await db.commit()
        return {"status": "ok", "action": "customer_created", "customer_id": customer.id}

    elif data.action == "mark_spam":
        # Log it as spam
        log = EmailLog(
            mailbox_id=data.mailbox_id,
            direction="in",
            subject=f"[SPAM] {data.email_id[:50]}",
            status="received",
        )
        db.add(log)
        await db.commit()
        return {"status": "ok", "action": "marked_spam"}

    return {"status": "ok", "action": data.action, "message": "Action noted"}
