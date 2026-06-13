"""Daily auto-CRM task — search leads, send development emails, log results."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.customer import Customer
from backend.models.email_log import EmailLog
from backend.models.mailbox import Mailbox
from backend.models.email_template import EmailTemplate
from backend.services.lead_scoring import LeadScoringEngine
from backend.services.email_service import EmailService

REPORT_FILE = Path(__file__).parent.parent / "generated_sites" / "auto_crm_report.json"

# ─── Lead selection logic (replicates auto-crm's get_leads_for_today) ─────

async def get_leads_for_today(db: AsyncSession, target: int = 10) -> list[Customer]:
    """Select leads to contact today: ~50% new + ~50% followup."""
    now = datetime.now(timezone.utc)

    # New leads (never contacted) — prefer auto_crm source, then highest score
    new_result = await db.execute(
        select(Customer).where(
            Customer.source.like("auto_crm%"),
            Customer.notes.notlike("%CRM Status: contacted%"),
            Customer.email != "",
        ).order_by(Customer.score.desc()).limit(target)
    )
    new_leads = list(new_result.scalars().all())

    # If not enough auto_crm leads, get any high-score leads
    if len(new_leads) < target:
        more_result = await db.execute(
            select(Customer).where(
                Customer.source.notlike("auto_crm%"),
                Customer.notes.notlike("%CRM Status: contacted%"),
                Customer.email != "",
            ).order_by(Customer.score.desc()).limit(target - len(new_leads))
        )
        new_leads.extend(more_result.scalars().all())

    # Followup leads — contacted > 25 days ago
    thirty_days_ago = (now - timedelta(days=25)).isoformat()
    followup_result = await db.execute(
        select(Customer).where(
            Customer.notes.like("%CRM Status: contacted%"),
            Customer.email != "",
        ).order_by(Customer.updated_at.asc()).limit(target)
    )
    followup_leads = list(followup_result.scalars().all())

    # Mix: prioritize new leads, fill with followups
    half = target // 2
    selected = new_leads[:half]
    selected.extend(followup_leads[:target - len(selected)])
    return selected


async def send_development_email(customer: Customer, mailbox: Mailbox,
                                  template: EmailTemplate) -> bool:
    """Send a single development email using the backend's email service."""
    from_addr = f"{mailbox.name or 'Sales'} <{mailbox.email_address}>"

    # Build subject and body from template
    subject = (template.subject_template or "Introduction from TXD CO., LTD")
    subject = subject.replace("{{company_name}}", customer.company or "TXD CO., LTD")
    subject = subject.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")

    body = template.body_template or ""
    body = body.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")
    body = body.replace("{{COMPANY_NAME}}", customer.company or "your company")

    # Replace image placeholders with empty (no embedded images via SMTP)
    for i in range(1, 5):
        body = body.replace(f"{{{{IMAGE_{i}}}}}", "")

    try:
        success = await EmailService.send_email(
            smtp_host=mailbox.smtp_host,
            smtp_port=mailbox.smtp_port,
            smtp_user=mailbox.smtp_username,
            smtp_pass=mailbox.smtp_password_enc,
            from_addr=from_addr,
            to_addr=customer.email,
            subject=subject,
            body=body,
        )
        return True
    except Exception as e:
        print(f"  ❌ Failed to send to {customer.email}: {e}")
        return False


async def scheduled_auto_crm_task():
    """Daily auto-CRM task — called by APScheduler."""
    print(f"[Auto-CRM] Starting daily run at {datetime.now().isoformat()}")

    async with async_session() as db:
        try:
            # 1. Get today's leads
            leads = await get_leads_for_today(db, target=10)
            print(f"[Auto-CRM] Selected {len(leads)} leads for today")

            if not leads:
                print("[Auto-CRM] No leads to contact, skipping")
                return

            # 2. Get mailbox and template
            mailbox_result = await db.execute(
                select(Mailbox).where(Mailbox.email_address.like("%necata%"))
            )
            mailbox = mailbox_result.scalar_one_or_none()

            if not mailbox:
                mailbox_result = await db.execute(
                    select(Mailbox).where(Mailbox.active == True)
                )
                mailbox = mailbox_result.scalar_one_or_none()

            template_result = await db.execute(
                select(EmailTemplate).where(EmailTemplate.name == "auto_crm_first_contact")
            )
            template = template_result.scalar_one_or_none()

            if not mailbox:
                print("[Auto-CRM] No mailbox configured, skipping send")
                return
            if not template:
                print("[Auto-CRM] No auto_crm_first_contact template found, skipping send")
                return

            # 3. Send emails
            sent_count = 0
            for customer in leads:
                if not customer.email:
                    continue
                success = await send_development_email(customer, mailbox, template)
                if success:
                    sent_count += 1

                    # Update customer notes to mark as contacted
                    contact_note = f"CRM Status: contacted, Stage: followup1, Contacted: {datetime.now().strftime('%Y-%m-%d')}"
                    if customer.notes:
                        customer.notes = customer.notes + " | " + contact_note
                    else:
                        customer.notes = contact_note

                    # Re-score
                    customer.score = LeadScoringEngine.calculate_score(
                        company=customer.company or "",
                        email=customer.email or "",
                        phone=customer.phone or "",
                        country=customer.country or "",
                        intent_text=customer.notes or "",
                        source=customer.source or "auto_crm",
                    )

                    # Create email log
                    log = EmailLog(
                        mailbox_id=mailbox.id,
                        customer_id=customer.id,
                        direction="out",
                        subject=(template.subject_template or "").replace("{{company_name}}", customer.company or "TXD CO., LTD"),
                        body=f"Auto-CRM development email to {customer.email}",
                        status="sent",
                        sent_at=datetime.now(timezone.utc).isoformat(),
                    )
                    db.add(log)

            await db.commit()

            # 4. Save report
            report = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "leads_selected": len(leads),
                "emails_sent": sent_count,
                "status": "completed",
            }
            reports = []
            if REPORT_FILE.exists():
                try:
                    reports = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, Exception):
                    reports = []
            reports.append(report)
            REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
            REPORT_FILE.write_text(json.dumps(reports[-90:], indent=2, ensure_ascii=False), encoding="utf-8")

            print(f"[Auto-CRM] Done: sent {sent_count} emails, selected {len(leads)} leads")

        except Exception as e:
            print(f"[Auto-CRM] Error: {e}")
            import traceback
            traceback.print_exc()
