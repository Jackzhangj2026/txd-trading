"""Daily auto-CRM task: SEARCH lead find leads -> SAVE -> SEND email -> LOG."""
import json, asyncio
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
from backend.services.market_scanner import MarketScanner

REPORT_FILE = Path("generated_sites") / "auto_crm_report.json"

# --- Search Topics (from auto-crm/lead_search.py) ---

SEARCH_TOPICS = [
    {"product": "PP hollow sheet", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "corrugated plastic sheet", "buyer": ["importer", "distributor", "wholesaler"]},
    {"product": "PP hollow board", "buyer": ["manufacturer", "importer", "procurement"]},
    {"product": "plastic packaging sheet", "buyer": ["importer", "buyer", "distributor"]},
    {"product": "fluted plastic sheet", "buyer": ["importer", "wholesaler"]},
    {"product": "polypropylene twinwall sheet", "buyer": ["importer", "distributor"]},
    {"product": "plastic box manufacturer", "buyer": ["importer", "wholesaler", "buyer"]},
    {"product": "reusable plastic container", "buyer": ["importer", "distributor"]},
    {"product": "ESD packaging material", "buyer": ["importer", "procurement"]},
    {"product": "plastic corrugated box", "buyer": ["importer", "wholesaler", "buyer"]},
]

COUNTRIES = ["USA", "Germany", "UK", "France", "Italy", "Spain",
             "Netherlands", "Brazil", "Mexico", "UAE", "Saudi Arabia",
             "South Africa", "Australia", "Poland", "Turkey"]


def generate_search_queries(day_of_month: int = None) -> list[str]:
    """Generate targeted search queries (product x buyer x country)."""
    if day_of_month is None:
        day_of_month = datetime.now().day
    queries = []
    topic = SEARCH_TOPICS[day_of_month % len(SEARCH_TOPICS)]
    product = topic["product"]
    for buyer in topic["buyer"][:2]:
        queries.append(f'"{product}" {buyer} email contact')
        queries.append(f'"{product}" {buyer} company')
    for i in range(3):
        c = COUNTRIES[(day_of_month + i) % len(COUNTRIES)]
        queries.append(f'"{product}" importer {c}')
        queries.append(f'"{product}" distributor {c} buying')
    for b2b in ["alibaba.com", "europages.com", "tradeindia.com"]:
        queries.append(f'site:{b2b} "{product}" buy request')
    queries.append(f'"{product}" procurement manager linkedin')
    return queries[:4]  # Keep small for local LLM speed


async def step_search_new_leads(db: AsyncSession) -> dict:
    """Search for new leads using MarketScanner, save to customers table."""
    scanner = MarketScanner()
    day = datetime.now().day
    queries = generate_search_queries(day)
    print(f"  [Auto-CRM] Search: {len(queries)} queries for new leads")

    all_results = []
    all_leads = []
    seen_companies = set()

    existing_result = await db.execute(select(Customer.email))
    existing_emails = {str(row[0]).lower().strip() for row in existing_result.fetchall() if row[0]}

    for query in queries:
        try:
            results = await asyncio.wait_for(
                scanner.google_search(query, num_results=4), timeout=30.0
            )
            all_results.extend(results)
        except asyncio.TimeoutError:
            print(f"    [Auto-CRM] Timeout for: {query[:40]}")
            continue
        except Exception as e:
            print(f"    [Auto-CRM] Search failed: {query[:40]}: {e}")
            continue

    # Parse companies directly from search result titles
    for result in all_results:
        title = (result.get("title") or "").strip()
        snippet = (result.get("snippet") or "").strip()
        company = ""
        if " - " in title:
            company = title.split(" - ")[0].strip()
        elif title:
            words = title.split()
            company = " ".join(words[:min(3, len(words))])
        if not company or company.lower() in ("results", "search", "the", ""):
            continue

        country_keywords = {"USA":"USA", "Germany":"Germany", "UK":"UK", "United Kingdom":"UK",
                           "France":"France", "Italy":"Italy", "Spain":"Spain", "India":"India",
                           "China":"China", "UAE":"UAE", "Brazil":"Brazil", "Australia":"Australia"}
        country = ""
        snippet_lower = (snippet + " " + title).lower()
        for cname, code in country_keywords.items():
            if cname.lower() in snippet_lower:
                country = code
                break

        query_used = result.get("query", "")
        product = query_used.split('"')[1] if '"' in query_used else query_used[:60]
        all_leads.append({
            "company": company, "country": country,
            "product_interest": product, "confidence": 0.5,
            "source_text": snippet[:200], "email": "",
        })

    saved = 0
    for lead in all_leads:
        company = (lead.get("company") or "").strip()
        country = (lead.get("country") or "").strip()
        email = (lead.get("email") or "").strip().lower()
        product = (lead.get("product_interest") or "").strip()

        if company.lower() in ("unknown", "") and not email:
            continue
        dedup_key = email if email else company.lower()
        if dedup_key in seen_companies:
            continue
        if email and email in existing_emails:
            continue

        seen_companies.add(dedup_key)
        if email:
            existing_emails.add(email)

        name = company or email.split("@")[0] if email else "Unknown"
        source_text = lead.get("source_text", "")
        notes = f"Auto-search: {product}" if product else ""
        if source_text:
            notes = (notes + " | " if notes else "") + source_text

        score = LeadScoringEngine.calculate_score(
            company=company, email=email, country=country,
            intent_text=notes or "", source="auto_crm_search",
        )
        customer = Customer(
            name=name, company=company, country=country,
            email=email, source="auto_crm_search", score=score, notes=notes,
        )
        db.add(customer)
        saved += 1

    if saved > 0:
        await db.flush()

    print(f"    [Auto-CRM] Search results: {len(queries)} queries, {len(all_results)} results, {saved} new leads")
    return {"queries": len(queries), "results": len(all_results), "leads_extracted": len(all_leads), "saved": saved}


async def get_leads_for_today(db: AsyncSession, target: int = 10) -> list[Customer]:
    """Select leads to contact today: combine new + followup."""
    new_result = await db.execute(
        select(Customer).where(
            Customer.source.like("auto_crm%"),
            Customer.email != "",
        ).order_by(Customer.score.desc()).limit(target)
    )
    new_leads = []
    for c in new_result.scalars().all():
        if c.status not in ("contacted", "interested"):
            new_leads.append(c)

    if len(new_leads) < target:
        more_result = await db.execute(
            select(Customer).where(Customer.email != "").order_by(Customer.score.desc()).limit(target * 2)
        )
        for c in more_result.scalars().all():
            if c.status not in ("contacted", "interested") and c.id not in {nl.id for nl in new_leads}:
                new_leads.append(c)
                if len(new_leads) >= target:
                    break

    followup_result = await db.execute(
        select(Customer).where(
            Customer.status == "contacted", Customer.email != "",
        ).order_by(Customer.updated_at.asc()).limit(target)
    )
    followup_leads = list(followup_result.scalars().all())

    half = target // 2
    selected = new_leads[:half]
    selected.extend(followup_leads[:target - len(selected)])
    return selected


async def send_development_email(customer: Customer, mailbox: Mailbox, template: EmailTemplate) -> bool:
    from_addr = f"{mailbox.name or 'Sales'} <{mailbox.email_address}>"
    subject = (template.subject_template or "Introduction from TXD CO., LTD")
    # Subject — support all template variable variants
    subject = subject.replace("{{name}}", customer.name or "Valued Partner")
    subject = subject.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")
    subject = subject.replace("{{company}}", customer.company or "TXD CO., LTD")
    subject = subject.replace("{{company_name}}", customer.company or "TXD CO., LTD")
    subject = subject.replace("{{COMPANY_NAME}}", customer.company or "TXD CO., LTD")
    subject = subject.replace("{{country}}", customer.country or "")
    body = template.body_template or ""
    # Body — support all template variable variants
    body = body.replace("{{name}}", customer.name or "Valued Partner")
    body = body.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")
    body = body.replace("{{company}}", customer.company or "your company")
    body = body.replace("{{company_name}}", customer.company or "your company")
    body = body.replace("{{COMPANY_NAME}}", customer.company or "your company")
    body = body.replace("{{country}}", customer.country or "")
    # Embed factory images into image placeholders
    import base64, random
    from pathlib import Path as _Path
    _img_dir = _Path(__file__).parent.parent.parent / "factory image"
    if _img_dir.exists():
        _images = sorted([f for f in _img_dir.iterdir() if f.suffix.lower() in (".jpg",".jpeg",".png",".gif") and not f.name.startswith(".")])
        if _images:
            _selected = random.sample(_images, min(4, len(_images)))
            for _i, _ip in enumerate(_selected, 1):
                _ext = _ip.suffix.lower()
                _mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif"}
                _mt = _mime.get(_ext.lstrip("."), "image/jpeg")
                _b64 = base64.b64encode(_ip.read_bytes()).decode()
                _tag = f'<img src="data:{_mt};base64,{_b64}" alt="Product" style="max-width:100%;border-radius:4px;margin:10px 0;">'
                for _ph in [f"{{{{IMAGE_{_i}}}}}", f"{{IMAGE_{_i}}}", f"{{{{image_{_i}}}}}", f"{{image_{_i}}}"]:
                    if _ph in body:
                        body = body.replace(_ph, _tag)
    try:
        success = await EmailService.send_email(
            smtp_host=mailbox.smtp_host, smtp_port=mailbox.smtp_port,
            smtp_user=mailbox.smtp_username, smtp_pass=mailbox.smtp_password_enc,
            from_addr=from_addr, to_addr=customer.email,
            subject=subject, body=body,
        )
        return True
    except Exception as e:
        print(f"  [Auto-CRM] Send failed to {customer.email}: {e}")
        return False


async def scheduled_auto_crm_task():
    """Daily auto-CRM: SEARCH -> SAVE -> SELECT -> SEND -> LOG."""
    start = datetime.now()
    print(f"[Auto-CRM] Starting daily run at {start.isoformat()}")
    report = {"date": start.strftime("%Y-%m-%d"), "search": {}, "email": {}}

    async with async_session() as db:
        try:
            # Step 0: Search for new leads
            search_result = await step_search_new_leads(db)
            report["search"] = search_result

            # Step 1: Get leads to contact
            leads = await get_leads_for_today(db, target=10)
            print(f"  [Auto-CRM] Selected {len(leads)} leads for today")
            report["email"]["leads_selected"] = len(leads)

            if not leads:
                print("[Auto-CRM] No leads to contact, skipping send")
                await db.commit()
                report["email"]["sent"] = 0
                _save_report(report)
                return report

            # Step 2: Get mailbox & template
            mailbox_result = await db.execute(
                select(Mailbox).where(Mailbox.active == True).order_by(Mailbox.created_at.desc())
            )
            mailbox = mailbox_result.scalar_one_or_none()
            template_result = await db.execute(
                select(EmailTemplate).where(EmailTemplate.name == "auto_crm_first_contact")
            )
            template = template_result.scalar_one_or_none()

            if not mailbox:
                print("[Auto-CRM] No active mailbox configured")
                report["email"]["sent"] = 0
                await db.commit()
                _save_report(report)
                return report
            if not template:
                print("[Auto-CRM] No email template found")
                report["email"]["sent"] = 0
                await db.commit()
                _save_report(report)
                return report

            # Step 3: Enrich customers without email by scraping websites
            enriched = 0
            import asyncio as aio
            import httpx
            for customer in leads:
                if customer.email or not customer.website:
                    continue
                try:
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        resp = await aio.wait_for(
                            client.get(customer.website, headers={"User-Agent": "Mozilla/5.0"}),
                            timeout=8.0
                        )
                        if resp.status_code == 200:
                            import re as _re
                            _email_re = _re.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', _re.IGNORECASE)
                            found = set()
                            for m in _email_re.findall(resp.text[:50000]):
                                email = m.strip().lower()
                                if email and "@" in email and not email.endswith((".png",".jpg",".gif",".svg",".css",".js")):
                                    found.add(email)
                            if found:
                                from backend.services.email_intel import is_role_account
                                best = None
                                for e in found:
                                    if not is_role_account(e):
                                        best = e; break
                                if not best:
                                    best = next(iter(found))
                                customer.email = best
                                enriched += 1
                                print(f"  [Auto-CRM] Found email for {customer.company}: {best}")
                except (aio.TimeoutError, Exception):
                    pass
            if enriched > 0:
                await db.commit()
                report["email"]["enriched_from_website"] = enriched
                print(f"  [Auto-CRM] Enriched {enriched} customers with emails from websites")

            # Step 4: Send emails
            sent_count = 0
            for customer in leads:
                if not customer.email:
                    continue
                # Calculate subject once per customer
                email_subject = (template.subject_template or "Introduction from TXD CO., LTD")
                email_subject = email_subject.replace("{{company_name}}", customer.company or "TXD CO., LTD")
                email_subject = email_subject.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")

                success = await send_development_email(customer, mailbox, template)
                if success:
                    sent_count += 1
                    customer.status = "contacted"
                    customer.score = LeadScoringEngine.calculate_score(
                        company=customer.company or "", email=customer.email or "",
                        phone=customer.phone or "", country=customer.country or "",
                        intent_text=customer.notes or "", source=customer.source or "auto_crm",
                    )
                    log = EmailLog(
                        mailbox_id=mailbox.id, customer_id=customer.id, direction="out",
                        subject=email_subject, body=f"Auto-CRM to {customer.email}",
                        status="sent", sent_at=datetime.now(timezone.utc).isoformat(),
                    )
                    db.add(log)

            await db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            report["email"]["sent"] = sent_count
            report["elapsed_seconds"] = round(elapsed, 1)
            print(f"  [Auto-CRM] Done: sent {sent_count}, searched {search_result['saved']} new leads, {elapsed:.0f}s")

            # Sync auto-crm lead statuses into customers
            from pathlib import Path as _Path
            leads_file = _Path(__file__).parent.parent.parent / "auto-crm" / "data" / "leads.json"
            if leads_file.exists():
                try:
                    all_leads = json.loads(leads_file.read_text(encoding="utf-8"))
                    synced = 0
                    for lead in all_leads:
                        if lead.get("status") != "contacted":
                            continue
                        email = (lead.get("email") or "").strip().lower()
                        if not email:
                            continue
                        r = await db.execute(select(Customer).where(Customer.email == email))
                        c = r.scalar_one_or_none()
                        if c and c.status != "contacted":
                            c.status = "contacted"
                            synced += 1
                    if synced > 0:
                        await db.commit()
                        print(f"  [Auto-CRM] Synced {synced} customer statuses to contacted")
                except Exception as e:
                    print(f"  [Auto-CRM] Status sync error: {e}")

        except Exception as e:
            print(f"[Auto-CRM] Error: {e}")
            import traceback
            traceback.print_exc()
            report["error"] = str(e)

    _save_report(report)
    return report


def _save_report(report: dict):
    reports = []
    if REPORT_FILE.exists():
        try:
            reports = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            reports = []
    reports.append(report)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(reports[-90:], indent=2, ensure_ascii=False), encoding="utf-8")
