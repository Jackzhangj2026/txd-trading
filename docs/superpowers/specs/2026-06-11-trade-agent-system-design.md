# TXD Trade Agent System — Design Spec

**Date:** 2026-06-11
**Project:** TXD CO., LTD PP Hollow Board Trading Website
**Version:** 0.1.0 (draft)

---

## Overview

Build an intelligent agent system for international trade on top of the existing TXD CO., LTD static website (GitHub Pages). The system automates market intelligence, customer acquisition, email communication, website content maintenance, and social media operation across 10 platforms (overseas + China).

**Current product focus:** PP hollow sheet (polypropylene corrugated board — a packaging material). Future support for additional trade categories via extensible target market configuration.

**Technology stack:** Python FastAPI + PostgreSQL + LLM (user-selectable provider, default DeepSeek) + Docker deployment.

**Build order:** Phase 1 (infrastructure) → Phase 2 (website) → Phase 3 (email) → Phase 4 (intelligence/leads) → Phase 5 (social media).

---

## Phase 1: Infrastructure Layer

### Directory Structure

```
hollowsheet/
├── backend/                     ← New: Python backend
│   ├── main.py                  ← FastAPI entry point
│   ├── config.py                ← Configuration (env vars + .env)
│   ├── database.py              ← DB connection & session management
│   ├── models/                  ← SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py              ← Base (timestamps, UUID PK)
│   │   ├── product.py
│   │   ├── inquiry.py
│   │   ├── customer.py
│   │   ├── email_log.py
│   │   ├── email_template.py
│   │   ├── mailbox.py
│   │   ├── content.py
│   │   ├── market_intel.py
│   │   └── target_market.py
│   ├── schemas/                 ← Pydantic schemas
│   ├── routers/                 ← API routes
│   │   ├── products.py
│   │   ├── inquiries.py
│   │   ├── customers.py
│   │   ├── emails.py
│   │   ├── mailboxes.py
│   │   ├── content.py
│   │   ├── intel.py
│   │   ├── target_markets.py
│   │   └── agents.py            ← LLM agent endpoints
│   ├── services/                ← Business logic
│   │   ├── lead_scoring.py
│   │   ├── email_service.py
│   │   ├── blog_generator.py
│   │   ├── image_processor.py
│   │   ├── content_gen.py
│   │   ├── market_scanner.py
│   │   └── social_publisher.py
│   ├── agents/                  ← LLM agent definitions
│   │   ├── base_agent.py        ← Base class (tool calling, memory)
│   │   └── ...
│   ├── tasks/                   ← Scheduled task definitions
│   │   ├── daily_blog.py
│   │   ├── daily_market_scan.py
│   │   ├── weekly_images.py
│   │   └── monthly_reports.py
│   ├── scheduler.py             ← Task scheduler (APScheduler)
│   ├── migrations/              ← Alembic
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── admin/                       ← New: Admin panel (Jinja2 + HTMX)
│   ├── templates/
│   ├── static/
│   └── router.py
├── index.html                   ← Existing (keep, enhanced later)
├── blog/                        ← Existing
├── images/                      ← Existing
└── docker-compose.yml           ← New
```

### Core Components

#### 1. FastAPI Application

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TXD Trade Agent API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

app.include_router(products.router, prefix="/api/products")
app.include_router(inquiries.router, prefix="/api/inquiries")
app.include_router(emails.router, prefix="/api/emails")
app.include_router(mailboxes.router, prefix="/api/mailboxes")
app.include_router(customers.router, prefix="/api/customers")
app.include_router(content.router, prefix="/api/content")
app.include_router(intel.router, prefix="/api/intel")
app.include_router(target_markets.router, prefix="/api/target-markets")
app.include_router(agents.router, prefix="/api/agents")
```

#### 2. LLM Provider Abstraction

User selects a single global LLM provider via `.env`:

```env
# Switch LLM provider by changing this one line
ACTIVE_LLM=deepseek

# Available provider API keys (kept in env for flexibility)
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
```

Supported providers:
- DeepSeek (default, ¥1/¥2 per 1M tokens — most cost-effective)
- OpenAI (GPT-4o / GPT-4o-mini)
- Anthropic (Claude Sonnet)
- Google Gemini
- Alibaba Qwen
- Ollama (local, free)
- Any OpenAI-compatible API

```python
# backend/config.py
LLM_PROVIDERS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com"
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o",
    },
    # ...
}

# Agent uses the single active provider at init
class TradeAgent:
    def __init__(self):
        cfg = get_provider_config(settings.active_llm)
        self.client = LiteLLM(**cfg)
```

#### 3. Database Models (Initial)

- `Product` — id, name_zh, name_en, category, specs(JSON), images, active
- `Inquiry` — id, customer_id, product_id, message, status, source, classification
- `Customer` — id, name, email, company, country, source, score, notes, matched_market
- `EmailLog` — id, mailbox_id, customer_id, direction, subject, body, status, sent_at
- `EmailTemplate` — id, name, subject_template, body_template, category, variables(JSON)
- `Mailbox` — id, name, email_address, imap/smtp config, routing_rules(JSON), assigned_to
- `EmailSequence` — id, customer_id, template_id, status, scheduled_at, step
- `TargetMarket` — id, name, keywords(JSON), products(JSON), industries(JSON), customer_types(JSON), search_keywords(JSON), active, priority, scan_frequency
- `MarketKeyword` — id, keyword, source_type, language, active, last_scanned
- `MarketScan` — id, keyword_id, source_type, raw_data(JSON), leads_extracted
- `MarketReport` — id, report_type, title, summary(Text), data(JSON)
- `ContentPiece` — id, title, content_type, platform, status, body(Text), media_urls(JSON), scheduled_at
- `ContentMetrics` — id, content_id, platform, impressions, clicks, likes, comments, shares
- `PlatformAccount` — id, platform, account_name, account_type, credentials(encrypted), active

---

## Phase 2: Website Enhancement & Content Maintenance

### 2.1 Product Management API

| Method | Path | Function |
|--------|------|----------|
| GET | `/api/products` | List products (filter by category/search) |
| GET | `/api/products/{id}` | Product detail |
| POST | `/api/products` | Create product |
| PUT | `/api/products/{id}` | Update product |
| DELETE | `/api/products/{id}` | Delete product |

Products stored in PostgreSQL; frontend (`index.html`) fetches via JS `fetch()` for dynamic rendering.

### 2.2 Intelligent Inquiry Processing

```
User submits contact form
    │
    ▼
FastAPI receives
    ├── Validates input
    ├── LLM classifies: high-quality / needs-info / spam
    ├── Auto-creates/updates Customer record
    ├── Stores Inquiry with classification
    └── Sends auto-reply (template matched by classification)
```

LLM classification prompt:
```
system: You are an inquiry classifier for a PP hollow board trading company.
Classify: high=real purchase intent / medium=potential / low=spam or irrelevant
Extract: product interest, quantity, target market, urgency
```

### 2.3 Content Maintenance Engine

Scheduled tasks for automated site content management:

| Task | Frequency | Description |
|------|-----------|-------------|
| `daily_blog` | Daily 09:00 | Generate SEO blog post → `blog/{slug}.html` + update `blog/index.html` |
| `weekly_images` | Weekly Mon | Scan `images/products/` for new files, compress, generate thumbnails, LLM describes |
| `monthly_factory_media` | Monthly | Organize new factory photos/videos, update gallery |
| `on_demand_description` | On trigger | AI-generate product descriptions from images |

Blog generation enhancement over current GitHub Actions:
- Topic sourced from industry trends + customer inquiries (dynamic, not fixed 10-topic rotation)
- Multiple article structures adapted to topic
- Multi-language support (EN primary, ZH/ES optional)
- Auto-generate Schema.org JSON-LD structured data
- Select product images as article illustrations

### 2.4 Admin Panel (Jinja2 + HTMX)

```
/admin/
├── /dashboard        ← Overview: new inquiries, customers, pending tasks
├── /inquiries        ← Inquiry list (mark processed/unprocessed)
├── /customers        ← Customer list (source, score, market)
├── /products         ← Product CRUD with image upload
├── /content          ← Content calendar, blog queue
├── /mailboxes        ← Multi-mailbox configuration
├── /target-markets   ← Target market definitions
├── /intel            ← Market intelligence dashboard
├── /settings         ← LLM provider, email config, system settings
└── /reports          ← Generated reports
```

---

## Phase 3: Email Communication System

### 3.1 Multi-Mailbox Support

Manage multiple email inboxes from one system:

```python
class Mailbox(Base):
    id: UUID
    name: str                       # "General Inquiries", "Sales EU", "Support"
    email_address: str              # info@txd.com, sales@txd.com
    imap_server / smtp_server       # Connection config
    routing_rules: JSON             # Route rules per mailbox
    assigned_to: str                # Responsible person
    daily_send_limit: int = 200
```

Supported email services: QQ Mail, Alibaba Enterprise Email, Gmail, Outlook, custom IMAP/SMTP.

**Receive flow:** Poll all active mailboxes in parallel → LLM classify → route to auto-reply or manual follow-up.

**Send strategy:** Reply to same customer from the same mailbox (conversation continuity). New outreach selects mailbox by target market/region.

### 3.2 Email Template Engine (Jinja2)

Pre-built templates for trade scenarios:

| Stage | Template | Trigger |
|-------|----------|---------|
| Cold outreach | First contact | New lead |
| Quotation | Price response | Customer asks |
| Follow-up 1 | "Just checking in" | 3 days after quote |
| Follow-up 2 | New product/price update | 7 days |
| Follow-up 3 | Last chance | 14 days |
| Sample confirm | Sample tracking | Customer requests sample |
| Order confirm | Order details | Customer places order |
| Holiday | Season's greetings | Calendar-based |

Template variables: `{{customer.name}}`, `{{product.name_en}}`, `{{specs.thickness}}`, `{{price}}`, etc.

### 3.3 Intelligent Reply Classifier

LLM classifies incoming email intent:

```python
intent = llm.classify(("""
Classify this buyer email intent:
1. Price inquiry → extract product, specs, quantity
2. Negotiation → extract target price
3. Order confirmation → mark as order
4. Complaint → escalate to human
5. Spam → archive
6. Needs follow-up → explain why
""", email_body))
```

Classification drives auto-response strategy:
- Inquiry → send quotation template + log to CRM
- Negotiation → send negotiation template (with configurable floor price)
- Order → send confirmation + notify admin (WeChat/SMS)
- Complaint → flag for human + notify immediately
- Spam → silent archive

### 3.4 Email Sequence Orchestration

```
Lead enters system
    │
Day 0  ── Cold email ────────────── Company intro + product highlights
Day 3  ── Follow-up 1 ── no reply ─ "Just checking in"
Day 7  ── Follow-up 2 ── no reply ─ Case study / testimonial
Day 14 ── Follow-up 3 ── no reply ─ Special offer / new catalog
Day 30 ── Dormant ── no reply ──── Move to dormant pool (retry in 6 months)
                │
          Customer replied? ── Yes ── Switch to intelligent reply flow, pause sequence
```

### 3.5 Email API

| Method | Path | Function |
|--------|------|----------|
| GET | `/api/mailboxes` | List mailboxes |
| POST | `/api/mailboxes` | Add mailbox |
| PUT | `/api/mailboxes/{id}` | Edit mailbox |
| DELETE | `/api/mailboxes/{id}` | Delete mailbox |
| POST | `/api/mailboxes/{id}/test` | Test IMAP+SMTP connection |
| GET | `/api/emails/templates` | List templates |
| POST | `/api/emails/templates` | Create template |
| POST | `/api/emails/send` | Send email manually |
| POST | `/api/emails/sequences` | Create sequence for customer |
| GET | `/api/emails/log?customer_id=X` | Email history with customer |
| POST | `/api/emails/check` | Trigger inbox check |

---

## Phase 4: Market Intelligence & Lead Generation

### 4.1 Target Market Configuration (User-Defined)

Users define one or more target markets. All intelligence activities filter against these definitions.

```python
class TargetMarket(Base):
    id: UUID
    name: str                    # "Packaging", "Automotive Parts"
    active: bool = True
    keywords: JSON               # ["packaging", "corrugated", "中空板"]
    products: JSON               # ["PP hollow board", "plastic box"]
    industries: JSON             # ["logistics", "packaging materials"]
    customer_types: JSON         # ["importer", "distributor", "factory"]
    search_keywords: JSON        # Auto-generated search queries from LLM
    scan_frequency: str = "daily"
    priority: int = 5            # 1-10, affects lead scoring weight
```

**How it works across the intelligence pipeline:**

```
Target Market Set
    │
    ├──→ Drives search keywords for all data sources
    ├──→ LLM filters scraped data: "Does this match any target market?"
    ├──→ Lead scoring weighted by market match + priority
    └──→ Reports segmented by market
```

**Adding a new trade category:** Simply add a new Target Market (e.g., "Automotive Parts") → system automatically starts collecting relevant intelligence for it.

### 4.2 Data Sources & Collection

| Source | Method | Frequency |
|--------|--------|-----------|
| Google Search | Custom Search API / Playwright | Daily |
| Alibaba RFQ | Playwright scrape | Daily |
| Made-in-China | Playwright scrape | Daily |
| LinkedIn | Search + manual import | Weekly |
| Customs data | CSV/Excel import | On-demand |
| Google News | RSS + API | Daily |
| Competitors | Playwright | Weekly |

### 4.3 Lead Extraction & Scoring

**Extraction flow:**

```
Raw data (web text / search result)
    │
    ▼
LLM extracts structured info:
    company_name, website, contact_person, email, phone,
    country, product_interest, quantity_estimate, source
    │
    ▼
Check: belongs to which Target Market?
    │
    ▼
Deduplicate (same company+email → merge)
    │
    ▼
Store in Customer table
```

**Scoring model:**

| Factor | Max points |
|--------|-----------|
| Information completeness (email, phone, website) | 30 |
| Purchase intent signals ("urgent", "order", "quote") | 30 |
| Target market match | 30 |
| Data source quality (Alibaba RFQ > LinkedIn > Google) | 10 |
| **Total** | **100** |

| Score | Grade | Action |
|-------|-------|--------|
| 80-100 | 🔥 Hot | Manual follow-up immediately + high-priority email |
| 60-79 | 🔵 Warm | Auto send cold email, add to sequence |
| 30-59 | 🟡 Cold | Nurture sequence (weekly industry tips) |
| 0-29 | ⚪ Lead | Store in pool, monthly retry |

### 4.4 Market Intelligence Engine

- Raw material price tracking (PP resin from Chinese commodity sites)
- Competitor monitoring (pricing, new products from competitor websites)
- Target market trend analysis (Google Trends, industry reports)
- Trade policy changes (customs announcements, tariff updates)

### 4.5 Scheduled Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| `daily_market_scan` | Daily 08:00 | Search keywords, extract leads |
| `daily_news_digest` | Daily 09:00 | Industry news summary + trend analysis |
| `weekly_competitor_check` | Weekly Mon | Monitor competitor updates |
| `weekly_lead_report` | Weekly Mon | New leads summary + score distribution |
| `monthly_trend_report` | Monthly 1st | Market trend report |

### 4.6 Market Intelligence API

| Method | Path | Function |
|--------|------|----------|
| GET | `/api/target-markets` | List target markets |
| POST | `/api/target-markets` | Create target market |
| PUT | `/api/target-markets/{id}` | Update target market |
| GET | `/api/intel/keywords` | List monitoring keywords |
| POST | `/api/intel/keywords` | Add keyword |
| GET | `/api/intel/leads` | Leads list (filter by score/market) |
| POST | `/api/intel/scan` | Trigger manual scan |
| GET | `/api/intel/reports` | Reports list |

---

## Phase 5: Social Media Operation System

### 5.1 Platform Matrix

| Platform | Region | Content Type | Frequency | Publish Method |
|----------|--------|-------------|-----------|---------------|
| LinkedIn | Global (B2B) | Professional insights, case studies | 3x/week | API (auto) |
| Twitter/X | Global | Industry news, product highlights | Daily | API v2 (auto) |
| YouTube | Global | Factory tour, product demo | 1-2x/week | API OAuth (auto) |
| Pinterest | Global | Product catalog images | 5x/week | API (auto) |
| TikTok | Global | Short product/factory videos | Daily | Manual (generate script) |
| Facebook | Global | Company updates, customer stories | 3x/week | Graph API (auto) |
| **小红书 RED** | **China** | **Product use cases, factory stories** | **3-5x/week** | **Manual (system generates copy)** |
| **抖音 Douyin** | **China** | **Product showcase, factory daily** | **1-2x/day** | **Manual (system generates script)** |
| **微信 WeChat** | **China** | **Articles (公众号), moments (朋友圈)** | **2x/week + daily** | **Semi-auto (Official Account API)** |

### 5.2 Content Generation

LLM generates platform-optimized content from a single core topic:

```
One core article
    │
    ├── EN version
    │   ├── → LinkedIn professional post
    │   ├── → Twitter/X short threads
    │   ├── → YouTube video script
    │   ├── → Pinterest image posts
    │   └── → TikTok short video script
    │
    └── CN version
        ├── → WeChat public account article
        ├── → WeChat Moments short post
        ├── → 小红书 (RED)种草 note
        ├── → 抖音 (Douyin) script
        └── → Video content (cross-platform)
```

### 5.3 Content Calendar

```
        Mon         Tue         Wed         Thu         Fri
LinkedIn  Insight     —           Case study   —           —
Twitter   News        Product     News        Industry    Product
YouTube   —           —           —           —           Video
Pinterest Product Img Application Product Img Application Product Img
RED       —           Note        —           Note        —
Douyin    Video       —           Video       —           Video
WeChat    —           Article     —           Moments     —
```

### 5.4 Analytics & Optimization

- Cross-platform metrics aggregation (impressions, clicks, engagement)
- Content performance analysis
- AI-driven optimization suggestions

### 5.5 Content API

| Method | Path | Function |
|--------|------|----------|
| GET | `/api/content/queue` | Content queue (pending publish) |
| POST | `/api/content/generate` | LLM generate draft |
| PUT | `/api/content/{id}` | Edit draft |
| POST | `/api/content/{id}/publish` | Publish |
| POST | `/api/content/{id}/schedule` | Schedule |
| GET | `/api/content/calendar` | Content calendar view |
| GET | `/api/content/metrics` | Content performance data |

---

## Admin Panel (Cross-Phase)

A single admin panel built with Jinja2 + HTMX, covering all phases:

```
/admin/
├── Dashboard — overview KPIs
├── Customers — CRM, lead list, scoring
├── Inquiries — inquiry management
├── Emails
│   ├── Mailboxes — multi-email config
│   ├── Templates — email template editor
│   └── Sequences — sequence orchestration
├── Products — product CRUD
├── Content
│   ├── Blog — blog management + AI generation
│   ├── Social — social media queue & calendar
│   └── Media — image/video upload & management
├── Intel
│   ├── Target Markets — market definitions
│   ├── Leads — lead list & scoring
│   └── Reports — market intelligence reports
└── Settings — LLM provider, system config
```

---

## Deployment Architecture

### Development (Phase 1-2)

```
Local machine
├── FastAPI backend  →  http://localhost:8000
├── PostgreSQL       →  localhost:5432
├── Admin panel      →  http://localhost:8000/admin
└── GitHub Pages     →  existing (enhanced frontend calls local API)
```

### Production (future)

```
VPS / Docker
├── FastAPI (gunicorn + uvicorn)
├── PostgreSQL
├── Redis (optional, for task queue)
├── Nginx reverse proxy
└── GitHub Pages (frontend remains, calls VPS API)
```

### Alternative: Zero-VPS for Cost Saving

For maximum cost efficiency, use GitHub Actions as a cron runner:

```
GitHub Actions (scheduler)
    │
    ├── Python scripts run on schedule
    ├── Generate blog posts → commit to repo
    ├── Run market scans → store results in repo as JSON
    ├── Send scheduled emails via SMTP
    └── Generate social media content → commit for manual review
```

This eliminates VPS cost entirely at the cost of real-time responsiveness.

---

## Cost Summary

| Item | Development Phase | Production (VPS) | Zero-VPS Alternative |
|------|------------------|------------------|---------------------|
| Server | ¥0 (local) | ¥50-80/mo (VPS) | ¥0 (GitHub Actions) |
| LLM API | ¥10-20/mo | ¥10-20/mo | ¥10-20/mo |
| Domain | ¥0 (has) | ¥0 | ¥0 |
| Email | ¥0 (existing) | ¥0 | ¥0 |
| Storage | ¥0 (Git repo) | ¥0 | ¥0 |
| **Total** | **¥10-20/mo** | **¥60-100/mo** | **¥10-20/mo** |

---

## Expected Impact (6-month projection)

Based on conservative estimates for a PP hollow board trading company targeting overseas markets:

| Metric | Current | With System (6mo) |
|--------|---------|-------------------|
| Website daily visitors | 10-30 | 100-300 |
| Monthly inquiries | 5-15 | 30-80 |
| Monthly qualified leads | 2-5 | 15-30 |
| Social media followers | 0 | 500-2000 (cross-platform) |
| Blog articles | 10 (static) | 200+ (auto-generated) |
| Email outreach/month | 0 | 500-1000 |
| Cost per lead | — | ≈¥0.3-2 |

---

## Future Extensions

- Additional trade categories via new Target Market definitions
- Multi-language content (Spanish, Arabic for target markets)
- WhatsApp Business integration
- Order management system
- Supplier management / procurement module
- AI-powered price negotiation agent
- Customer portal (order tracking, history)

---

*This spec was generated through collaborative brainstorming. All sections have been reviewed for internal consistency, scope, and ambiguity before finalization.*
