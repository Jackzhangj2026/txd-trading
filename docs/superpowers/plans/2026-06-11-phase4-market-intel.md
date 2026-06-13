# Phase 4: Market Intelligence & Lead Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build target market configuration, market intelligence scanning (Google/Alibaba/RSS), LLM-based lead extraction and scoring, and admin management pages.

**Architecture:** TargetMarket model drives search keywords for all data sources. Scanner services collect raw data, LLM extracts structured leads with market matching. Lead scoring engine scores 0-100. Results feed into existing Customer table.

**Tech Stack:** FastAPI, SQLAlchemy, TradeAgent (LiteLLM), httpx/aiohttp for web fetching, APScheduler

---

### Task 1: TargetMarket model + CRUD API + AI keyword generation

**Files:**
- Create: `E:\hollowsheet\backend\models\target_market.py`
- Update: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\routers\target_markets.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**
- [ ] Create TargetMarket model (name, keywords, products, industries, customer_types, search_keywords, active, priority, scan_frequency)
- [ ] Create CRUD API with list/create/update/delete + AI keyword generation endpoint
- [ ] Register router in main.py
- [ ] Commit

### Task 2: Market scanner service (Google + RSS + Alibaba)

**Files:**
- Create: `E:\hollowsheet\backend\services\market_scanner.py`
- Update: `E:\hollowsheet\backend\routers\target_markets.py` (add scan endpoint)

**Steps:**
- [ ] Create MarketScanner with:
  - `google_search(keywords)` — fetch Google search results
  - `fetch_rss(keywords)` — fetch Google News RSS
  - `extract_leads(text)` — LLM extract company/email/country/interest
  - `match_market(lead_text, markets)` — LLM determine which target market
- [ ] Add POST `/api/target-markets/{id}/scan` endpoint
- [ ] Commit

### Task 3: Lead scoring service

**Files:**
- Create: `E:\hollowsheet\backend\services\lead_scoring.py`
- Update: `E:\hollowsheet\backend\routers\target_markets.py` (add leads listing)

**Steps:**
- [ ] Create lead_scoring.py with scoring engine (completeness 30pts, intent 30pts, market match 30pts, source quality 10pts)
- [ ] Add POST `/api/target-markets/{id}/leads` endpoint
- [ ] Add GET `/api/target-markets/{id}/leads` endpoint (list leads for a market)
- [ ] Commit

### Task 4: Scheduled market scanning

**Files:**
- Create: `E:\hollowsheet\backend\tasks\market_scan.py`
- Update: `E:\hollowsheet\backend\scheduler.py`

**Steps:**
- [ ] Create market_scan.py — scheduled task that scans all active markets
- [ ] Update scheduler.py to add daily market scan job
- [ ] Commit

### Task 5: Admin pages for target markets + leads

**Files:**
- Create: `E:\hollowsheet\backend\admin\templates\markets.html`
- Update: `E:\hollowsheet\backend\admin\router.py`
- Update: `E:\hollowsheet\backend\admin\templates\base.html`

**Steps:**
- [ ] Create markets.html — list target markets, show leads per market, trigger scan
- [ ] Add `/admin/markets` route
- [ ] Update sidebar to make Target Markets active
- [ ] Commit
