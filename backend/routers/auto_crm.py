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


@router.post("/run-daily")
async def run_auto_crm_daily():
    """Trigger the daily auto-crm task manually."""
    from backend.tasks.auto_crm_daily import scheduled_auto_crm_task
    try:
        await scheduled_auto_crm_task()
        return {"status": "ok", "message": "Daily auto-crm task completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
