"""Email campaign API — send with persistence, stop, resume across restart."""

import asyncio
import base64
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db, async_session
from backend.models.campaign import Campaign
from backend.models.customer import Customer
from backend.models.email_log import EmailLog
from backend.models.mailbox import Mailbox
from backend.models.email_template import EmailTemplate
from backend.services.email_service import EmailService

router = APIRouter(prefix="/api/campaign", tags=["campaign"])
FACTORY_IMG_DIR = settings.factory_image_dir

# ─── Running task tracker for stop/resume ──────────────────────────

_running_campaigns: dict[str, asyncio.Event] = {}  # campaign_id -> stop event


async def _load_and_resume_campaigns():
    """On startup, resume pending campaigns that haven't run today."""
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.status.in_(["running", "pending"]))
        )
        campaigns = result.scalars().all()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resumed = 0
        for camp in campaigns:
            if camp.status == "running":
                # Was interrupted — reset to pending
                camp.status = "pending"
            if camp.last_run_date == today:
                # Already ran today, skip
                continue
            print(f"[Campaign] Resuming campaign {camp.id} ({camp.subject_preview[:40]})")
            asyncio.create_task(_run_campaign(camp.id))
            resumed += 1
        if campaigns:
            await db.commit()
        if resumed:
            print(f"[Campaign] Resumed {resumed} campaigns")

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
    max_emails: int = 20  # total customers to select
    daily_limit: int = 20  # max emails per day, 0 = no limit
    human_delay_min: int = 30
    human_delay_max: int = 180
    image_filenames: list[str] = []

@router.post("/send")
async def send_campaign(data: CampaignRequest, db: AsyncSession = Depends(get_db)):
    """Save campaign to DB and start sending.

    Deduplication: skips customers already sent by any campaign,
    and contacted customers (unless a specific status filter is set).
    """
    # ── 1. Collect all customers ever sent by any campaign ──
    # Build exclusion set from all campaigns' sent_customer_ids + customer_ids
    all_campaigns = (await db.execute(select(Campaign))).scalars().all()
    exclude_ids: set[str] = set()
    for c in all_campaigns:
        if c.status not in ("completed", "stopped", "failed"):
            # For active campaigns, exclude ALL their customers (prevent overlap)
            cids = json.loads(c.customer_ids or "[]")
            exclude_ids.update(cids)
        # Always exclude customers already sent by any campaign
        sids = json.loads(c.sent_customer_ids or "[]")
        exclude_ids.update(sids)

    # ── 2. Collect customers ──
    if data.customer_ids:
        # Batch fetch all customers at once (avoids N+1)
        valid_ids = [cid for cid in data.customer_ids if cid not in exclude_ids]
        if valid_ids:
            result = await db.execute(
                select(Customer).where(Customer.id.in_(valid_ids), Customer.email != "")
            )
            customers = [c for c in result.scalars().all()]
        else:
            customers = []
    else:
        filters = data.customer_filters
        query = select(Customer).where(Customer.email != "")
        # Default: exclude already-contacted customers (unless user picks a specific status)
        if not filters.get("status"):
            query = query.where(Customer.status != "contacted")
        if filters.get("status"):
            query = query.where(Customer.status == filters["status"])
        if filters.get("source"):
            query = query.where(Customer.source.like(f"%{filters['source']}%"))
        if filters.get("score_min") is not None:
            query = query.where(Customer.score >= filters["score_min"])
        query = query.order_by(Customer.score.desc()).limit(data.max_emails * 2)  # fetch extra to compensate for excludes
        result = await db.execute(query)
        all_customers = list(result.scalars().all())
        customers = [c for c in all_customers if c.id not in exclude_ids]

    if not customers:
        raise HTTPException(status_code=400, detail="No customers found matching criteria (all already sent or contacted)")
    customers = customers[:data.max_emails]

    # 2. Build content
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
        raise HTTPException(status_code=400, detail="Subject and body required")

    # 3. Save campaign to DB with full config
    customer_ids = [c.id for c in customers]
    campaign = Campaign(
        mailbox_ids=json.dumps(list(set(data.mailbox_ids))),
        customer_count=len(customers),
        subject_preview=subject[:200],
        status="pending",
        delay_min=data.human_delay_min,
        delay_max=data.human_delay_max,
        image_filenames=json.dumps(data.image_filenames),
        daily_limit=data.daily_limit,
        subject_template=subject,
        body_template=body,
        customer_ids=json.dumps(customer_ids),
        sent_customer_ids="[]",
        current_email_index=0,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    # 4. Start sending
    asyncio.create_task(_run_campaign(campaign.id))
    await db.commit()

    return {
        "campaign_id": campaign.id,
        "total_target": len(customers),
        "status": "running",
        "message": f"Campaign started: {len(customers)} emails",
    }

# ─── Campaign Stop ─────────────────────────────────────────────────

@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Stop a running or pending campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Campaign is {camp.status}, not running/pending")

    # Signal stop if running
    if campaign_id in _running_campaigns:
        _running_campaigns[campaign_id].set()
        asyncio.create_task(_cleanup_tracker(campaign_id))

    camp.status = "stopped"
    camp.completed_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    return {"status": "ok", "message": f"Campaign stopped (was {camp.status})"}


@router.get("/{campaign_id}/progress")
async def get_campaign_progress(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get live campaign progress."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    elapsed = ""
    if camp.started_at:
        try:
            start = datetime.fromisoformat(camp.started_at)
            elapsed_sec = (datetime.now(timezone.utc) - start).total_seconds()
            elapsed = f"{int(elapsed_sec // 60)}m {int(elapsed_sec % 60)}s"
        except:
            pass

    return {
        "id": camp.id,
        "status": camp.status,
        "sent_count": camp.sent_count,
        "failed_count": camp.failed_count,
        "customer_count": camp.customer_count,
        "current_email_index": camp.current_email_index,
        "daily_limit": camp.daily_limit,
        "last_run_date": camp.last_run_date,
        "started_at": camp.started_at,
        "completed_at": camp.completed_at,
        "elapsed": elapsed,
        "error_message": camp.error_message,
    }


@router.get("/{campaign_id}/recipients")
async def get_campaign_recipients(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get recipient list with send status for a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    all_cids = json.loads(camp.customer_ids or "[]")
    sent_ids = set(json.loads(camp.sent_customer_ids or "[]"))

    # Batch fetch all customers at once
    cust_result = await db.execute(select(Customer).where(Customer.id.in_(all_cids)))
    customers_map = {c.id: c for c in cust_result.scalars().all()}

    # Batch fetch relevant email logs
    log_result = await db.execute(
        select(EmailLog).where(
            EmailLog.customer_id.in_(all_cids),
            EmailLog.direction == "out",
            EmailLog.subject.like(f"%Campaign {campaign_id}%"),
        ).order_by(EmailLog.sent_at.desc())
    )
    logs_map = {}
    for log in log_result.scalars().all():
        if log.customer_id not in logs_map:
            logs_map[log.customer_id] = log

    recipients = []
    for cid in all_cids:
        c = customers_map.get(cid)
        log = logs_map.get(cid)
        recipients.append({
            "customer_id": cid,
            "name": c.name if c else "",
            "company": c.company if c else "",
            "email": c.email if c else "",
            "country": c.country if c else "",
            "sent": cid in sent_ids,
            "sent_at": log.sent_at if log else "",
            "status": log.status if log else ("sent" if cid in sent_ids else "pending"),
        })

    return {
        "campaign_id": campaign_id,
        "total": len(all_cids),
        "sent_count": camp.sent_count,
        "recipients": recipients,
    }


# ─── Campaign History ──────────────────────────────────────────────

@router.get("/history")
async def get_campaign_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(50)
    )
    campaigns = result.scalars().all()
    items = []
    for c in campaigns:
        elapsed = ""
        if c.started_at and c.completed_at:
            try:
                s = datetime.fromisoformat(c.started_at)
                e = datetime.fromisoformat(c.completed_at)
                sec = (e - s).total_seconds()
                elapsed = f"{int(sec // 60)}m {int(sec % 60)}s"
            except:
                pass
        elif c.started_at and c.status == "running":
            try:
                s = datetime.fromisoformat(c.started_at)
                sec = (datetime.now(timezone.utc) - s).total_seconds()
                elapsed = f"{int(sec // 60)}m {int(sec % 60)}s (running)"
            except:
                pass

        items.append({
            "id": c.id,
            "campaign_name": c.campaign_name,
            "customer_count": c.customer_count,
            "subject_preview": c.subject_preview,
            "status": c.status,
            "sent_count": c.sent_count,
            "failed_count": c.failed_count,
            "current_email_index": c.current_email_index,
            "error_message": c.error_message,
            "started_at": c.started_at,
            "completed_at": c.completed_at,
            "elapsed": elapsed,
            "created_at": str(c.created_at) if c.created_at else "",
        })
    return {"items": items, "total": len(items)}

# ─── Campaign Runner ───────────────────────────────────────────────

async def _run_campaign(campaign_id: str):
    """Run campaign batch — respects daily_limit, survives restarts.

    Sends up to `daily_limit` emails per run. If more customers remain,
    stays in "pending" status for the next day's scheduler to pick up.
    Safe to call multiple times per day — skips if already ran today.
    """
    stop_event = asyncio.Event()
    _running_campaigns[campaign_id] = stop_event
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with async_session() as db:
        try:
            # Load campaign
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            camp = result.scalar_one_or_none()
            if not camp:
                return

            # Skip if already ran today (from scheduler + lifespan race)
            if camp.last_run_date == today_str and camp.status == "pending":
                print(f"[Campaign {campaign_id}] Already ran today, skipping")
                return

            # Load mailboxes
            mailbox_ids = json.loads(camp.mailbox_ids or "[]")
            mailboxes = []
            for mid in mailbox_ids:
                r = await db.execute(select(Mailbox).where(Mailbox.id == mid, Mailbox.active == True))
                mb = r.scalar_one_or_none()
                if mb:
                    mailboxes.append(mb)
            if not mailboxes:
                camp.status = "failed"
                camp.error_message = "No valid active mailboxes"
                await db.commit()
                return

            # Load customers
            customer_ids = json.loads(camp.customer_ids or "[]")
            sent_ids = set(json.loads(camp.sent_customer_ids or "[]"))

            # ── Cross-campaign dedup: also skip customers sent by ANY other campaign ──
            all_camps = (await db.execute(
                select(Campaign).where(Campaign.id != campaign_id)
            )).scalars().all()
            for oc in all_camps:
                sent_ids.update(json.loads(oc.sent_customer_ids or "[]"))

            # Batch fetch customers
            r = await db.execute(
                select(Customer).where(Customer.id.in_(list(customer_ids)), Customer.email != "")
            )
            customers = r.scalars().all()

            # Pre-load images
            inline_images = []
            image_filenames = json.loads(camp.image_filenames or "[]")
            if image_filenames:
                for fname in image_filenames:
                    img_path = FACTORY_IMG_DIR / fname
                    if img_path.exists():
                        ext = img_path.suffix.lower()
                        mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif","webp":"image/webp"}
                        mt = mime.get(ext.lstrip("."), "image/jpeg")
                        b64 = base64.b64encode(img_path.read_bytes()).decode()
                        inline_images.append(f'<img src="data:{mt};base64,{b64}" alt="" style="max-width:100%;border-radius:4px;margin:10px 0;">')

            # Mark running
            camp.status = "running"
            camp.started_at = camp.started_at or datetime.now(timezone.utc).isoformat()
            await db.commit()

            subject_template = camp.subject_template or ""
            body_template = camp.body_template or ""
            daily_limit = camp.daily_limit or 20
            mailbox_idx = 0
            sent_today = 0
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_counts = {m.id: 0 for m in mailboxes}

            # Count today's sends per mailbox (for mailbox-level limits)
            for mb in mailboxes:
                count_result = await db.execute(
                    select(sa_func.count()).select_from(
                        select(EmailLog).where(
                            EmailLog.mailbox_id == mb.id,
                            EmailLog.sent_at >= today_start.isoformat()
                        ).subquery()
                    )
                )
                today_counts[mb.id] = count_result.scalar() or 0

            for i, customer in enumerate(customers):
                # Check stop signal
                if stop_event.is_set():
                    print(f"[Campaign {campaign_id}] Stopped by user")
                    camp.status = "stopped"
                    camp.completed_at = datetime.now(timezone.utc).isoformat()
                    await db.commit()
                    return

                # Check daily campaign limit
                if daily_limit > 0 and sent_today >= daily_limit:
                    print(f"[Campaign {campaign_id}] Daily limit reached ({daily_limit}), pausing")
                    break

                if customer.id in sent_ids:
                    continue
                if not customer.email:
                    continue

                # Check mailbox daily limit
                mb = mailboxes[mailbox_idx % len(mailboxes)]
                mailbox_idx += 1
                if today_counts[mb.id] >= (mb.daily_send_limit or 200):
                    continue

                # Personalize — support all template variable variants
                p_subj = subject_template.replace("{{name}}", customer.name or "")\
                    .replace("{{CONTACT_NAME}}", customer.name or "")\
                    .replace("{{company}}", customer.company or "")\
                    .replace("{{company_name}}", customer.company or "")\
                    .replace("{{COMPANY_NAME}}", customer.company or "")\
                    .replace("{{country}}", customer.country or "")
                p_body = body_template.replace("{{name}}", customer.name or "Valued Partner")\
                    .replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")\
                    .replace("{{company}}", customer.company or "your company")\
                    .replace("{{company_name}}", customer.company or "your company")\
                    .replace("{{COMPANY_NAME}}", customer.company or "your company")\
                    .replace("{{country}}", customer.country or "")

                if inline_images:
                    for idx, img_html in enumerate(inline_images, 1):
                        for ph in [f"{{image_{idx}}}", f"{{IMAGE_{idx}}}", f"{{{{image_{idx}}}}}", f"{{{{IMAGE_{idx}}}}}"]:
                            if ph in p_body:
                                p_body = p_body.replace(ph, img_html)
                    remaining = [img for idx, img in enumerate(inline_images, 1)
                                 if f"{{image_{idx}}}" not in body_template and f"{{IMAGE_{idx}}}" not in body_template
                                 and f"{{{{image_{idx}}}}}" not in body_template and f"{{{{IMAGE_{idx}}}}}" not in body_template]
                    if remaining:
                        p_body += '<div style="margin-top:20px;text-align:center;"><h3>Our Products</h3></div>' + "".join(remaining)

                from_addr = f"{mb.name or 'Sales'} <{mb.email_address}>"
                success = await EmailService.send_email(
                    smtp_host=mb.smtp_host, smtp_port=mb.smtp_port,
                    smtp_user=mb.smtp_username, smtp_pass=mb.smtp_password_enc,
                    from_addr=from_addr, to_addr=customer.email,
                    subject=p_subj, body=p_body,
                )

                now = datetime.now(timezone.utc)
                log = EmailLog(
                    mailbox_id=mb.id, customer_id=customer.id, direction="out",
                    subject=p_subj, body=f"[Campaign {campaign_id}] {p_body[:200]}",
                    status="sent" if success else "failed",
                    sent_at=now.isoformat(),
                )
                db.add(log)
                today_counts[mb.id] += 1
                sent_today += 1

                if success:
                    camp.sent_count += 1
                    customer.status = "contacted"
                else:
                    camp.failed_count += 1

                sent_ids.add(customer.id)
                camp.sent_customer_ids = json.dumps(list(sent_ids))
                camp.current_email_index = i + 1
                await db.commit()

                if not stop_event.is_set() and sent_today < daily_limit:
                    delay = random.randint(camp.delay_min, camp.delay_max)
                    print(f"[Campaign {campaign_id}] {camp.sent_count}/{camp.customer_count} sent. Waiting {delay}s...")
                    for _ in range(delay):
                        if stop_event.is_set():
                            camp.status = "stopped"
                            camp.completed_at = datetime.now(timezone.utc).isoformat()
                            await db.commit()
                            return
                        await asyncio.sleep(1)

            # Determine final status
            remaining = len([c for c in customers if c.id not in sent_ids and c.email])
            if remaining == 0:
                camp.status = "completed"
                camp.completed_at = datetime.now(timezone.utc).isoformat()
                print(f"[Campaign {campaign_id}] Completed: {camp.sent_count} sent")
            else:
                camp.status = "pending"
                camp.last_run_date = today_str
                print(f"[Campaign {campaign_id}] Paused: {camp.sent_count} sent, {remaining} remaining (next run tomorrow)")

            await db.commit()

        except Exception as e:
            print(f"[Campaign {campaign_id}] Error: {e}")
            import traceback
            traceback.print_exc()
            try:
                camp.status = "failed"
                camp.error_message = str(e)[:200]
                camp.completed_at = datetime.now(timezone.utc).isoformat()
                await db.commit()
            except:
                pass
        finally:
            _running_campaigns.pop(campaign_id, None)


@router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Resume a paused/stopped campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in ("pending", "stopped"):
        raise HTTPException(status_code=400, detail=f"Campaign is {camp.status}")
    camp.status = "pending"
    await db.commit()
    asyncio.create_task(_run_campaign(campaign_id))
    return {"status": "ok", "message": "Campaign resumed"}


async def run_pending_campaigns():
    """Called by scheduler daily — run all pending campaigns that haven't run today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with async_session() as db:
        result = await db.execute(
            select(Campaign).where(
                Campaign.status == "pending",
                Campaign.last_run_date != today,
            )
        )
        campaigns = result.scalars().all()
    for camp in campaigns:
        print(f"[Scheduler] Running campaign {camp.id}")
        asyncio.create_task(_run_campaign(camp.id))
    if campaigns:
        print(f"[Scheduler] Started {len(campaigns)} campaigns")
    return len(campaigns)


async def _cleanup_tracker(campaign_id: str):
    await asyncio.sleep(30)
    _running_campaigns.pop(campaign_id, None)

# ─── Inbox Management ──────────────────────────────────────────────

class InboxScanRequest(BaseModel):
    mailbox_id: str
    max_emails: int = 5

class InboxActionRequest(BaseModel):
    email_id: str
    mailbox_id: str
    action: str
    customer_name: str = ""
    customer_email: str = ""

@router.post("/inbox/scan")
async def scan_inbox(data: InboxScanRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == data.mailbox_id))
    mailbox = result.scalar_one_or_none()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if not mailbox.imap_host:
        raise HTTPException(status_code=400, detail="Mailbox has no IMAP configured")

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
        raise HTTPException(status_code=504, detail="IMAP connection timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IMAP failed: {str(e)[:200]}")

    mailbox.last_checked = datetime.now(timezone.utc).isoformat()
    await db.commit()

    error_emails = [e for e in emails if e.get("error")]
    real_emails = [e for e in emails if not e.get("error")]
    if error_emails:
        return {"error": True, "message": error_emails[0].get("message", "IMAP error")}

    analyzed = []
    for email_data in real_emails[-data.max_emails:]:
        try:
            classification = await asyncio.wait_for(
                EmailService.classify_email(email_data["subject"], email_data["body"]),
                timeout=20.0
            )
        except (asyncio.TimeoutError, Exception):
            classification = {"category": "general_inquiry", "summary": "Classification timeout", "urgency": "low", "product": "unknown"}

        category = classification.get("category", "general_inquiry")
        action_map = {
            "price_inquiry": ("reply_quote", "Price inquiry - send quotation"),
            "order_confirmation": ("mark_interested", "Order confirmation - mark as interested"),
            "complaint": ("manual_review", "Complaint - needs human review"),
            "negotiation": ("manual_review", "Negotiation - needs human review"),
            "spam": ("mark_spam", "Spam detected"),
        }
        suggested_action, suggestion_reason = action_map.get(category, ("manual_review", "General inquiry - review"))

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
    if data.action == "mark_customer_interested":
        if data.customer_email:
            result = await db.execute(select(Customer).where(Customer.email == data.customer_email))
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
        log = EmailLog(
            mailbox_id=data.mailbox_id, direction="in",
            subject=f"[SPAM] {data.email_id[:50]}", status="received",
        )
        db.add(log)
        await db.commit()
        return {"status": "ok", "action": "marked_spam"}
    return {"status": "ok", "action": data.action, "message": "Action noted"}
