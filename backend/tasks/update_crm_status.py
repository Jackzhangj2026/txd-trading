"""Update existing customers' status from auto-crm lead data."""

import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AUTO_CRM_DIR = Path(__file__).parent.parent.parent / "auto-crm"
LEADS_FILE = AUTO_CRM_DIR / "data" / "leads.json"


async def update_contacted_status(db: AsyncSession) -> dict:
    """Update existing customers' status based on auto-crm lead status."""
    from backend.models.customer import Customer

    if not LEADS_FILE.exists():
        return {"error": "leads.json not found"}

    leads = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    updated = 0
    not_found = 0

    for lead in leads:
        if lead.get("status") != "contacted":
            continue

        email = (lead.get("email") or "").strip().lower()
        if not email:
            continue

        # Find customer by email
        result = await db.execute(select(Customer).where(Customer.email == email))
        customer = result.scalar_one_or_none()
        if customer:
            if customer.status != "contacted":
                customer.status = "contacted"
                updated += 1
        else:
            # Try by company name
            company = lead.get("company", "")
            if company:
                result = await db.execute(
                    select(Customer).where(Customer.company.ilike(f"%{company[:50]}%"))
                )
                customer = result.scalar_one_or_none()
                if customer and customer.status != "contacted":
                    customer.status = "contacted"
                    updated += 1
                else:
                    not_found += 1
            else:
                not_found += 1

    await db.commit()
    return {"updated": updated, "not_found": not_found}
