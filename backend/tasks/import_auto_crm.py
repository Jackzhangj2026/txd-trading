"""One-time import: migrate auto-crm data into the main backend."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

AUTO_CRM_DIR = Path(__file__).parent.parent.parent / "auto-crm"
IMAGE_TARGET_DIR = Path("generated_sites") / "auto-crm-images"


async def import_all(db: AsyncSession) -> dict:
    """Import all auto-crm data into the backend. Returns import stats."""
    from backend.models.customer import Customer
    from backend.models.email_log import EmailLog
    from backend.models.email_template import EmailTemplate
    from backend.models.mailbox import Mailbox
    from backend.services.lead_scoring import LeadScoringEngine

    results = {"customers_imported": 0, "customers_skipped": 0, "logs_imported": 0,
               "template_created": False, "mailbox_created": False, "images_copied": 0}

    # ─── 1. Import leads → customers ──────────────────────────────────
    leads_file = AUTO_CRM_DIR / "data" / "leads.json"
    if leads_file.exists():
        leads = json.loads(leads_file.read_text(encoding="utf-8"))
        existing_emails = set()
        existing_result = await db.execute(select(Customer.email))
        for row in existing_result.scalars().all():
            if row:
                existing_emails.add(row.lower().strip())

        for lead in leads:
            email = (lead.get("email") or "").strip().lower()
            if email and email in existing_emails:
                results["customers_skipped"] += 1
                continue

            company = lead.get("company", "")
            contact = lead.get("contact_person", "")
            country = lead.get("country", "")
            product = lead.get("product_interest", "")
            source = lead.get("source", "auto_crm")
            notes = lead.get("notes", "")
            status = lead.get("status", "new")
            stage = lead.get("stage", "new")

            # Combine notes
            combined_notes = notes
            if product:
                combined_notes = (combined_notes + " | " if combined_notes else "") + f"Product Interest: {product}"
            if status != "new" or stage != "new":
                combined_notes = (combined_notes + " | " if combined_notes else "") + f"CRM Status: {status}, Stage: {stage}"

            name = contact or company or email.split("@")[0] if email else ""
            score = LeadScoringEngine.calculate_score(
                company=company, email=email,
                country=country, intent_text=combined_notes,
                source=f"auto_crm_{source}",
            )

            # Determine customer status from auto-crm lead status
            crm_status = "lead"
            if lead.get("status") == "contacted":
                crm_status = "contacted"
            
            customer = Customer(
                name=name,
                email=email,
                company=company,
                country=country,
                source=f"auto_crm_{source}",
                status=crm_status,
                score=score,
                notes=combined_notes,
                tags=json.dumps(["imported_from_auto_crm"]),
            )
            db.add(customer)
            if email:
                existing_emails.add(email)
            results["customers_imported"] += 1

    # ─── 2. Import sent log → email_logs ──────────────────────────────
    sent_file = AUTO_CRM_DIR / "data" / "sent_log.json"
    if sent_file.exists():
        sent_log = json.loads(sent_file.read_text(encoding="utf-8"))
        existing_logs = set()
        existing_result = await db.execute(select(EmailLog.subject, EmailLog.sent_at))
        for row in existing_result.fetchall():
            existing_logs.add((row[0] or "", row[1] or ""))

        for entry in sent_log:
            to = entry.get("to", "")
            subject = entry.get("subject", "")
            time_str = entry.get("time", "")
            sent_status = entry.get("status", "sent")

            key = (subject, time_str)
            if key in existing_logs:
                continue

            log = EmailLog(
                direction="out",
                subject=subject,
                body=f"Imported from auto-crm. To: {to}",
                status=sent_status,
                sent_at=time_str,
            )
            db.add(log)
            existing_logs.add(key)
            results["logs_imported"] += 1

    # ─── 3. Import email template ─────────────────────────────────────
    template_file = AUTO_CRM_DIR / "templates" / "email_template.html"
    if template_file.exists():
        existing = await db.execute(
            select(EmailTemplate).where(EmailTemplate.name == "auto_crm_first_contact")
        )
        if not existing.scalar_one_or_none():
            template_html = template_file.read_text(encoding="utf-8")
            email_template = EmailTemplate(
                name="auto_crm_first_contact",
                category="cold",
                subject_template="Introduction from {{company_name}} - PP Hollow Board Supplier",
                body_template=template_html,
                variables=json.dumps(["CONTACT_NAME", "COMPANY_NAME", "IMAGE_1", "IMAGE_2", "IMAGE_3", "IMAGE_4"]),
            )
            db.add(email_template)
            results["template_created"] = True

    # ─── 4. Create mailbox entry for necata@163.com ───────────────────
    cfg_file = AUTO_CRM_DIR / "data" / "email_config.json"
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        existing = await db.execute(
            select(Mailbox).where(Mailbox.email_address == cfg.get("sender_email", ""))
        )
        if not existing.scalar_one_or_none() and cfg.get("sender_email"):
            mailbox = Mailbox(
                name="Auto CRM Sender",
                email_address=cfg.get("sender_email", ""),
                smtp_host=cfg.get("smtp_server", ""),
                smtp_port=cfg.get("smtp_port", 465),
                smtp_username=cfg.get("sender_email", ""),
                smtp_password_enc=cfg.get("smtp_password", ""),
                use_ssl=cfg.get("smtp_port", 465) == 465,
                daily_send_limit=cfg.get("daily_limit", 20),
            )
            db.add(mailbox)
            results["mailbox_created"] = True

    # ─── 5. Copy product images ───────────────────────────────────────
    img_dir = AUTO_CRM_DIR / "email_images"
    if img_dir.exists():
        IMAGE_TARGET_DIR.mkdir(parents=True, exist_ok=True)
        for img_file in img_dir.glob("*"):
            if img_file.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                target = IMAGE_TARGET_DIR / img_file.name
                if not target.exists():
                    shutil.copy2(img_file, target)
                    results["images_copied"] += 1

    await db.commit()
    return results
