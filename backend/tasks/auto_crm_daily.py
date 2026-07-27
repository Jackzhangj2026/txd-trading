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
    # PP hollow board / core products
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
    # Gift box / rigid box packaging
    {"product": "gift box", "buyer": ["importer", "distributor", "wholesaler", "manufacturer"]},
    {"product": "rigid box", "buyer": ["importer", "supplier", "buyer"]},
    {"product": "luxury packaging box", "buyer": ["importer", "distributor", "wholesaler"]},
    {"product": "magnetic gift box", "buyer": ["importer", "procurement", "buyer"]},
    {"product": "custom gift box", "buyer": ["importer", "manufacturer", "distributor"]},
    # Carton / paper box packaging
    {"product": "carton box", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "paper box", "buyer": ["importer", "supplier", "distributor"]},
    {"product": "corrugated carton", "buyer": ["importer", "wholesaler", "procurement"]},
    {"product": "folding carton", "buyer": ["importer", "manufacturer", "buyer"]},
    {"product": "kraft paper box", "buyer": ["importer", "distributor", "wholesaler"]},
    # Fruit packaging
    {"product": "fruit box", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "fruit packaging", "buyer": ["importer", "manufacturer", "supplier"]},
    {"product": "apple box", "buyer": ["importer", "wholesaler", "procurement"]},
    {"product": "citrus packaging", "buyer": ["importer", "distributor", "buyer"]},
    {"product": "fresh fruit carton", "buyer": ["importer", "supplier", "wholesaler"]},
    # Agricultural / vegetable packaging
    {"product": "vegetable box", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "agricultural packaging", "buyer": ["importer", "manufacturer", "supplier"]},
    {"product": "produce box", "buyer": ["importer", "wholesaler", "distributor"]},
    {"product": "tomato box", "buyer": ["importer", "procurement", "buyer"]},
    {"product": "fresh produce carton", "buyer": ["importer", "supplier", "manufacturer"]},
    # Logistics / shipping packaging
    {"product": "logistics packaging", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "shipping box", "buyer": ["importer", "supplier", "procurement"]},
    {"product": "heavy duty box", "buyer": ["importer", "manufacturer", "buyer"]},
    {"product": "industrial packaging", "buyer": ["importer", "wholesaler", "distributor"]},
    {"product": "export packaging", "buyer": ["importer", "supplier", "buyer"]},
]

COUNTRIES = ["USA", "Germany", "UK", "France", "Italy", "Spain",
             "Netherlands", "Brazil", "Mexico", "UAE", "Saudi Arabia",
             "South Africa", "Australia", "Poland", "Turkey",
             "Canada", "Japan", "Singapore", "Thailand", "Vietnam",
             "Chile", "Argentina", "Russia", "Sweden", "Belgium"]


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
    return queries[:8]  # 8 queries per batch for wider coverage


async def step_search_new_leads(db: AsyncSession, max_save: int = 10) -> dict:
    """Search for new leads using MarketScanner, save at most max_save to customers table."""
    scanner = MarketScanner()
    day = datetime.now().day
    queries = generate_search_queries(day)
    print(f"  [Auto-CRM] Search: {len(queries)} queries for new leads (max save: {max_save})")

    all_results = []
    all_leads = []
    seen_companies = set()

    existing_result = await db.execute(select(Customer.email))
    existing_emails = {str(row[0]).lower().strip() for row in existing_result.fetchall() if row[0]}

    for query in queries:
        try:
            results = await asyncio.wait_for(
                scanner.google_search(query, num_results=6), timeout=30.0
            )
            all_results.extend(results)
        except asyncio.TimeoutError:
            print(f"    [Auto-CRM] Timeout for: {query[:40]}")
            continue
        except Exception as e:
            print(f"    [Auto-CRM] Search failed: {query[:40]}: {e}")
            continue

    # Parse companies directly from search result titles
    # 严格要求：每个线索必须有真实URL来源，过滤掉社交媒体和非企业网站
    import re as _re2
    _email_re2 = _re2.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', _re2.IGNORECASE)
    _NON_COMPANY_DOMAINS = (
        "google.com", "youtube.com", "facebook.com", "linkedin.com",
        "twitter.com", "instagram.com", "wikipedia.org", "bing.com",
        "baidu.com", "pinterest.com"
    )
    for result in all_results:
        title = (result.get("title") or "").strip()
        snippet = (result.get("snippet") or "").strip()
        url = (result.get("url") or "").strip()

        # 必须有真实URL来源 — 无URL或社交媒体链接的搜索结果不可信
        if not url or not url.startswith(("http://", "https://")):
            continue
        if any(skip in url.lower() for skip in _NON_COMPANY_DOMAINS):
            continue

        company = ""
        if " - " in title:
            company = title.split(" - ")[0].strip()
        elif title:
            words = title.split()
            company = " ".join(words[:min(3, len(words))])
        if not company or len(company) < 3 or company.lower() in ("results", "search", "the", ""):
            continue

        # Extract email from snippet
        email = ""
        email_matches = _email_re2.findall(snippet + " " + title)
        if email_matches:
            e = email_matches[0].strip().lower()
            if not e.endswith((".png",".jpg",".gif",".svg")):
                email = e

        # Extract website URL
        website = ""
        if url and not any(s in url.lower() for s in ("google.com","youtube.com","facebook.com","linkedin.com","twitter.com","instagram.com")):
            website = url.split("?")[0].rstrip("/")

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
            "source_text": snippet[:200], "email": email, "website": website,
        })

    saved = 0
    for lead in all_leads:
        if saved >= max_save:
            break
        company = (lead.get("company") or "").strip()
        country = (lead.get("country") or "").strip()
        email = (lead.get("email") or "").strip().lower()
        product = (lead.get("product_interest") or "").strip()

        if company.lower() in ("unknown", "") and not email:
            continue
        # 必须有真实网站URL作为企业存在的证据
        website = (lead.get("website") or "").strip()
        if not website:
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
            name=name, company=company, country=country, website=website,
            email=email, source="auto_crm_search", score=score, notes=notes,
        )
        db.add(customer)
        saved += 1

    if saved > 0:
        await db.flush()

    print(f"    [Auto-CRM] Search results: {len(queries)} queries, {len(all_results)} results, {saved} new leads")
    return {"queries": len(queries), "results": len(all_results), "leads_extracted": len(all_leads), "saved": saved}


async def get_leads_for_today(db: AsyncSession, target: int = 10) -> list[Customer]:
    """Select leads to contact today: prefer with email, include website-only for scraping."""
    # First: leads with email
    result = await db.execute(
        select(Customer).where(
            Customer.source.like("auto_crm%") | Customer.source.like("market_scan%"),
            Customer.status.notin_(["contacted", "interested"]),
            Customer.email != "",
        ).order_by(Customer.score.desc()).limit(target)
    )
    leads = list(result.scalars().all())

    # Fill remaining with leads that have website but no email (will be scraped)
    if len(leads) < target:
        web_result = await db.execute(
            select(Customer).where(
                Customer.source.like("auto_crm%") | Customer.source.like("market_scan%"),
                Customer.status.notin_(["contacted", "interested"]),
                Customer.email == "",
                Customer.website != "",
            ).order_by(Customer.score.desc()).limit(target - len(leads))
        )
        for c in web_result.scalars().all():
            if c.id not in {l.id for l in leads}:
                leads.append(c)
                if len(leads) >= target:
                    break

    # Still short: any non-contacted customer with email
    if len(leads) < target:
        more = await db.execute(
            select(Customer).where(
                Customer.status.notin_(["contacted", "interested"]),
                Customer.email != "",
            ).order_by(Customer.score.desc()).limit(target - len(leads))
        )
        for c in more.scalars().all():
            if c.id not in {l.id for l in leads}:
                leads.append(c)
                if len(leads) >= target:
                    break

    return leads[:target]


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


async def step_enrich_emails(db: AsyncSession, target: int = 5) -> list[Customer]:
    """Scrape websites of unenriched leads to find emails. Returns list of enriched customers."""
    import asyncio as aio2
    import httpx
    enriched_list = []
    enriched = 0

    enrich_result = await db.execute(
        select(Customer).where(
            (Customer.source.like("auto_crm%") | Customer.source.like("market_scan%")),
            Customer.status.notin_(["contacted", "interested"]),
            Customer.email == "",
            Customer.website != "",
        ).order_by(Customer.score.desc()).limit(target * 10)
    )
    candidates = list(enrich_result.scalars().all())
    print(f"  [Enrich] Scraping up to {len(candidates)} websites (target: {target})...")

    for customer in candidates:
        if enriched >= target:
            break
        try:
            website = customer.website.strip()
            if not website.startswith("http"):
                website = "https://" + website

            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                page_text = ""
                try:
                    resp = await aio2.wait_for(
                        client.get(website, headers={"User-Agent": "Mozilla/5.0"}),
                        timeout=6.0
                    )
                    if resp.status_code == 200:
                        page_text = resp.text[:50000]
                except Exception:
                    pass

                if not page_text or "@" not in page_text:
                    for suffix in ["/contact", "/about", "/kontakt", "/impressum"]:
                        try:
                            r2 = await aio2.wait_for(
                                client.get(website.rstrip("/") + suffix,
                                          headers={"User-Agent": "Mozilla/5.0"}),
                                timeout=5.0
                            )
                            if r2.status_code == 200 and "@" in r2.text:
                                page_text = r2.text[:30000]
                                break
                        except Exception:
                            pass

                if page_text and "@" in page_text:
                    import re as _re3
                    _email_re3 = _re3.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', _re3.IGNORECASE)
                    found = set()
                    for m in _email_re3.findall(page_text):
                        e = m.strip().lower()
                        if e and "@" in e and not e.endswith((".png",".jpg",".gif",".svg",".css",".js")):
                            found.add(e)
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
                        enriched_list.append(customer)
                        print(f"  [Enrich] [{enriched}/{target}] {customer.company} → {best}")
        except Exception:
            pass

    if enriched > 0:
        await db.commit()
    print(f"  [Enrich] Done: {enriched} emails found")
    return enriched_list


async def scheduled_auto_crm_task():
    """Daily auto-CRM: SEARCH -> SAVE -> SELECT FROM CUSTOMER DB -> SEND -> LOG.
    Recipients come from the existing customer list (with real email addresses).
    Hard cap: 5 emails per day. Simulates human sending with random delays.
    """
    import random as _random
    start = datetime.now()
    today_str = start.strftime("%Y-%m-%d")
    report = {"date": today_str, "search": {}, "email": {}}

    async with async_session() as db:
        try:
            # Daily limit — never send more than 5 per day
            DAILY_LIMIT = 5

            # Count emails already sent today (across all runs)
            today_prefix = today_str  # YYYY-MM-DD
            sent_today_result = await db.execute(
                select(EmailLog).where(
                    EmailLog.direction == "out",
                    EmailLog.status == "sent",
                    EmailLog.sent_at.like(f"{today_prefix}%"),
                )
            )
            sent_today = len(sent_today_result.scalars().all())
            remaining = max(0, DAILY_LIMIT - sent_today)

            print(f"[Auto-CRM] Starting at {start.isoformat()}, sent today: {sent_today}/{DAILY_LIMIT}, remaining: {remaining}")

            if remaining == 0:
                print("[Auto-CRM] Daily limit reached — skipping send")
                report["email"]["sent"] = 0
                report["email"]["skip_reason"] = "daily_limit_reached"
                _save_report(report)
                return report

            # Step 0: Search & save new leads (keeps the customer list growing)
            search_result = await step_search_new_leads(db, max_save=20)
            report["search"] = search_result

            # Step 1: Enrich emails for website-only leads (still useful)
            await step_enrich_emails(db, target=5)

            # Step 2: Get mailbox & template
            mailbox_result = await db.execute(
                select(Mailbox).where(Mailbox.active == True).order_by(Mailbox.created_at.desc())
            )
            mailbox = mailbox_result.scalar_one_or_none()
            if not mailbox:
                print("[Auto-CRM] No active mailbox")
                report["email"]["sent"] = 0
                report["email"]["skip_reason"] = "no_mailbox"
                await db.commit()
                _save_report(report)
                return report

            template_result = await db.execute(
                select(EmailTemplate).where(EmailTemplate.name == "cold_first_contact")
            )
            template = template_result.scalar_one_or_none()
            if not template:
                print("[Auto-CRM] No email template")
                report["email"]["sent"] = 0
                report["email"]["skip_reason"] = "no_template"
                await db.commit()
                _save_report(report)
                return report

            # Step 3: Select recipients from EXISTING customers with real emails.
            # Rule: new customers first (created_at DESC), and skip anyone emailed
            # within the last 15 days to avoid high-frequency repeat sending.
            fifteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
            # Customer emails that were sent to in the last 15 days (exclude these)
            recent_sent_result = await db.execute(
                select(EmailLog.customer_id).where(
                    EmailLog.direction == "out",
                    EmailLog.status == "sent",
                    EmailLog.sent_at >= fifteen_days_ago,
                    EmailLog.customer_id.isnot(None),
                )
            )
            recent_sent_ids = {row[0] for row in recent_sent_result.fetchall()}

            recipients_result = await db.execute(
                select(Customer).where(
                    Customer.status.notin_(["contacted", "interested"]),
                    Customer.email != "",
                    Customer.email.isnot(None),
                ).order_by(Customer.created_at.desc()).limit(remaining * 5)
            )
            all_candidates = list(recipients_result.scalars().all())

            # Filter out customers emailed within 15 days
            recipients = []
            for c in all_candidates:
                if c.id in recent_sent_ids:
                    continue
                recipients.append(c)
                if len(recipients) >= remaining:
                    break

            if not recipients:
                print("[Auto-CRM] No eligible customers with email — nothing to send")
                report["email"]["sent"] = 0
                report["email"]["skip_reason"] = "no_eligible_customers"
                await db.commit()
                _save_report(report)
                return report

            print(f"  [Auto-CRM] Selected {len(recipients)} recipients (newest first, 15-day cooldown applied; {len(all_candidates) - len(recipients)} skipped due to recent contact)")

            # Step 4: Send emails with human-like random delays (30-180 seconds between sends)
            sent_count = 0
            for idx, customer in enumerate(recipients):
                if sent_count >= remaining:
                    break
                if not customer.email:
                    continue

                # Random delay between emails (skip before the first send)
                if idx > 0:
                    delay = _random.randint(30, 180)
                    print(f"  [Auto-CRM] Human-like delay: waiting {delay}s before next send...")
                    await asyncio.sleep(delay)

                email_subject = (template.subject_template or "Introduction from TXD CO., LTD")
                email_subject = email_subject.replace("{{company_name}}", customer.company or "TXD CO., LTD")
                email_subject = email_subject.replace("{{CONTACT_NAME}}", customer.name or "Valued Partner")
                email_subject = email_subject.replace("{{company}}", customer.company or "TXD CO., LTD")
                email_subject = email_subject.replace("{{name}}", customer.name or "Valued Partner")
                email_subject = email_subject.replace("{{country}}", customer.country or "")

                print(f"  [Auto-CRM] Sending to {customer.email} ({customer.company or 'unknown'})...")
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
                    # Commit after each send so progress is saved even if interrupted
                    await db.commit()
                    print(f"  [Auto-CRM] ✓ Sent {sent_count}/{remaining} to {customer.email}")
                else:
                    print(f"  [Auto-CRM] ✗ Failed to send to {customer.email}")

            await db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            report["email"]["sent"] = sent_count
            report["email"]["daily_limit"] = DAILY_LIMIT
            report["email"]["sent_before_run"] = sent_today
            report["elapsed_seconds"] = round(elapsed, 1)
            print(f"  [Auto-CRM] Done: sent {sent_count}/{remaining} (today total {sent_today + sent_count}/{DAILY_LIMIT}), {elapsed:.0f}s")

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
