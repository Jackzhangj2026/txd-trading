"""Auto-CRM import API — trigger data migration from auto-crm to backend."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db

router = APIRouter(prefix="/api/auto-crm", tags=["auto-crm"])


@router.post("/import")
async def import_auto_crm_data(db: AsyncSession = Depends(get_db)):
    """Import all auto-crm data into the backend."""
    from backend.tasks.import_auto_crm import import_all
    results = await import_all(db)
    return {
        "status": "ok",
        "message": f"Imported {results['customers_imported']} customers, "
                   f"{results['logs_imported']} email logs, "
                   f"{'template created, ' if results['template_created'] else ''}"
                   f"{'mailbox created, ' if results['mailbox_created'] else ''}"
                   f"{results['images_copied']} images",
        **results,
    }


@router.get("/stats")
async def get_auto_crm_stats(db: AsyncSession = Depends(get_db)):
    """Get auto-crm integration stats."""
    from backend.models.customer import Customer
    from backend.models.email_log import EmailLog
    from sqlalchemy import select, func

    auto_crm_count = await db.execute(
        select(func.count()).select_from(
            select(Customer).where(Customer.source.like("auto_crm%")).subquery()
        )
    )
    total_logs = await db.execute(select(func.count()).select_from(select(EmailLog).subquery()))

    return {
        "auto_crm_customers": auto_crm_count.scalar() or 0,
        "total_email_logs": total_logs.scalar() or 0,
    }


@router.post("/mark-sent-contacted")
async def mark_sent_contacted(db: AsyncSession = Depends(get_db)):
    """Mark customers as contacted if they have auto-crm sent logs."""
    from backend.tasks.update_crm_status import update_contacted_status
    result = await update_contacted_status(db)
    return result


@router.post("/run-daily")
async def run_auto_crm_daily():
    """Trigger the daily auto-crm task manually."""
    from backend.tasks.auto_crm_daily import scheduled_auto_crm_task
    try:
        report = await scheduled_auto_crm_task()
        msg = f"Searched {report.get('search', {}).get('queries', 0)} queries, found {report.get('search', {}).get('saved', 0)} new leads, sent {report.get('email', {}).get('sent', 0)} emails"
        return {
            "status": "ok",
            "message": msg,
            "detail": {
                "search_queries": report.get("search", {}).get("queries", 0),
                "search_saved": report.get("search", {}).get("saved", 0),
                "email_sent": report.get("email", {}).get("sent", 0),
                "email_leads": report.get("email", {}).get("leads_selected", 0),
                "elapsed": f"{report.get('elapsed_seconds', 0)}s" if report.get("elapsed_seconds") else "",
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/reports")
async def get_auto_crm_reports():
    """Get the auto-crm report history."""
    from pathlib import Path
    report_file = Path("generated_sites") / "auto_crm_report.json"
    if report_file.exists():
        import json
        reports = json.loads(report_file.read_text(encoding="utf-8"))
        return reports
    return []


@router.get("/today-sends")
async def get_today_sends(db: AsyncSession = Depends(get_db)):
    """Get today's sent emails with recipient details."""
    from backend.models.email_log import EmailLog
    from backend.models.customer import Customer
    from sqlalchemy import select, desc
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await db.execute(
        select(EmailLog).where(
            EmailLog.direction == "out",
            EmailLog.sent_at >= today,
        ).order_by(desc(EmailLog.sent_at)).limit(50)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        customer_name = ""
        customer_company = ""
        if log.customer_id:
            cust = await db.execute(select(Customer).where(Customer.id == log.customer_id))
            c = cust.scalar_one_or_none()
            if c:
                customer_name = c.name or c.email or ""
                customer_company = c.company or ""

        items.append({
            "id": log.id,
            "time": log.sent_at or "",
            "subject": log.subject or "",
            "status": log.status or "sent",
            "customer_name": customer_name,
            "customer_company": customer_company,
        })

    # Also get total count
    count_result = await db.execute(
        select(EmailLog).where(EmailLog.direction == "out", EmailLog.sent_at >= today)
    )
    total = len(count_result.scalars().all()) if count_result else len(items)

    return {"items": items, "total": total}


@router.get("/schedule")
async def get_schedule():
    """Get the auto-crm schedule time."""
    from pathlib import Path
    import json
    cfg_file = Path("auto-crm/data/email_config.json")
    default = {"schedule_hour": 10}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            return {"schedule_hour": cfg.get("schedule_hour", 10)}
        except:
            pass
    return default


@router.post("/schedule")
async def set_schedule(data: dict):
    """Set the auto-crm schedule time (Beijing hour, 0-23)."""
    from pathlib import Path
    import json
    hour = int(data.get("schedule_hour", 10))
    hour = max(0, min(23, hour))
    cfg_file = Path("auto-crm/data/email_config.json")
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except:
            pass
    cfg["schedule_hour"] = hour
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"status": "ok", "schedule_hour": hour}


# ─── Email target config ──────────────────────────────────────

@router.get("/email-target")
async def get_email_target():
    """Get emails_per_run setting (default 5)."""
    from pathlib import Path
    import json
    cfg_file = Path("auto-crm/data/email_config.json")
    default = {"emails_per_run": 5}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            return {"emails_per_run": cfg.get("emails_per_run", 5)}
        except:
            pass
    return default


@router.post("/email-target")
async def set_email_target(data: dict):
    """Set emails_per_run (1-50)."""
    from pathlib import Path
    import json
    count = int(data.get("emails_per_run", 5))
    count = max(1, min(50, count))
    cfg_file = Path("auto-crm/data/email_config.json")
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except:
            pass
    cfg["emails_per_run"] = count
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"status": "ok", "emails_per_run": count}
