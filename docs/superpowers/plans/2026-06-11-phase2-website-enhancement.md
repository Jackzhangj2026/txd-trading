# Phase 2: Website Enhancement & Content Maintenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add intelligent inquiry processing (LLM classification), inquiry+customer CRUD APIs, admin panel pages, and the content maintenance engine (blog generator, image processor).

**Architecture:** New API routes for inquiries and customers using existing models. LLM classification via TradeAgent base class from Phase 1. APScheduler for scheduled content tasks. Blog generator writes to existing `blog/` directory.

**Tech Stack:** FastAPI, SQLAlchemy, TradeAgent (LiteLLM), APScheduler, Jinja2 templates

---

### Task 1: Inquiry API routes

**Files:**
- Create: `E:\hollowsheet\backend\routers\inquiries.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**

- [ ] Create `routers/inquiries.py` with:
  - `POST /api/inquiries` — submit inquiry, auto-classify via LLM, create/update customer
  - `GET /api/inquiries` — list (filter by status/classification, paginated)
  - `GET /api/inquiries/{id}` — get detail
  - `PUT /api/inquiries/{id}` — update status/classification
  - Classification uses TradeAgent.classify() for "high/medium/low/spam"
- [ ] Register router in main.py
- [ ] Test: POST inquiry → check it auto-classifies and creates customer
- [ ] Commit

### Task 2: Customer API routes

**Files:**
- Create: `E:\hollowsheet\backend\routers\customers.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**

- [ ] Create `routers/customers.py` with:
  - `GET /api/customers` — list (filter by source/score/market, paginated, search)
  - `GET /api/customers/{id}` — get detail with inquiries
  - `PUT /api/customers/{id}` — update (score, market, notes)
  - `DELETE /api/customers/{id}` — soft delete
- [ ] Register router in main.py
- [ ] Test: create inquiry → customer auto-created → list customers
- [ ] Commit

### Task 3: Admin panel — Inquiries & Customers pages

**Files:**
- Create/Update: `E:\hollowsheet\backend\admin\templates\inquiries.html`
- Create/Update: `E:\hollowsheet\backend\admin\templates\customers.html`
- Update: `E:\hollowsheet\backend\admin\router.py`

**Steps:**

- [ ] Add inquiries list page to admin router (`/admin/inquiries`)
- [ ] Add customers list page to admin router (`/admin/customers`)
- [ ] Inquiries page: table with status badges, classification tags, click to detail
- [ ] Customers page: table with score badges, company+country, click to detail
- [ ] Update sidebar links to point to real pages
- [ ] Commit

### Task 4: Content Maintenance Engine — Blog Generator

**Files:**
- Create: `E:\hollowsheet\backend\services\blog_generator.py`
- Create: `E:\hollowsheet\backend\services\image_processor.py`
- Create: `E:\hollowsheet\backend\tasks\__init__.py`
- Create: `E:\hollowsheet\backend\tasks\daily_blog.py`
- Update: `E:\hollowsheet\backend\scheduler.py`

**Steps:**

- [ ] Create `services/blog_generator.py` with:
  - `BlogGenerator.generate_topic()` — LLM picks topic based on industry + recent inquiries
  - `BlogGenerator.generate_post(topic)` — LLM writes full HTML post
  - Saves to `blog/{slug}.html` and updates `blog/index.html`
- [ ] Create `services/image_processor.py`:
  - `scan_new_images()` — checks `images/products/` for unprocessed files
  - `generate_thumbnail()` — creates 400px thumbnails
  - `describe_image()` — LLM generates alt text and description
- [ ] Create `tasks/daily_blog.py` — APScheduler job calling blog_generator
- [ ] Create `scheduler.py` — APScheduler setup with job store
- [ ] Commit

### Task 5: Admin panel — Content management pages

**Files:**
- Create: `E:\hollowsheet\backend\admin\templates\content.html`
- Update: `E:\hollowsheet\backend\admin\router.py`

**Steps:**

- [ ] Add `/admin/content` page showing blog queue, generated posts, image scan results
- [ ] "Generate Now" button triggers blog generation
- [ ] List of existing blog posts (from `blog/index.html` JS data)
- [ ] Commit

---

## Verification

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Check:
- [ ] `POST /api/inquiries` with sample inquiry → auto-classified + customer created
- [ ] `GET /api/customers` → shows customer created by inquiry
- [ ] `GET /admin/inquiries` → rendered inquiry list
- [ ] `GET /admin/customers` → rendered customer list
- [ ] `GET /admin/content` → rendered content management page
