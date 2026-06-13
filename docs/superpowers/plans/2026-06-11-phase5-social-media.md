# Phase 5: Social Media Operation System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build a social media content system — LLM generates platform-optimized content (LinkedIn, Twitter/X, YouTube, TikTok, RED, Douyin, WeChat), manages content calendar, provides admin for review/publish.

**Architecture:** ContentPiece model stores drafts per platform. ContentGenerator service uses TradeAgent to create platform-specific content from core topics. Content calendar/scheduler manages publishing queue. PlatformAccount model stores credentials.

**Tech Stack:** FastAPI, SQLAlchemy, TradeAgent (LiteLLM), Jinja2 templates

---

### Task 1: ContentPiece + PlatformAccount models + Content API

**Files:**
- Create: `E:\hollowsheet\backend\models\content_piece.py`
- Create: `E:\hollowsheet\backend\models\platform_account.py`
- Update: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\routers\content_media.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**
- [ ] Create ContentPiece model (title, content_type, platform, status, body, media_urls JSON, scheduled_at, published_at, source_blog_id)
- [ ] Create PlatformAccount model (platform, account_name, account_type, credentials encrypted, active)
- [ ] Update models __init__.py
- [ ] Create content_media.py router with: list queue, generate draft, update draft, schedule, list calendar, get metrics
- [ ] Register router in main.py
- [ ] Commit

### Task 2: Content generation service (10 platforms)

**Files:**
- Create: `E:\hollowsheet\backend\services\content_generator.py`

**Steps:**
- [ ] Create ContentGenerator with:
  - `generate_linkedin_post(topic)` — professional B2B post
  - `generate_twitter_thread(topic)` — short thread
  - `generate_youtube_script(topic)` — video script
  - `generate_pinterest_pin(topic)` — image post description
  - `generate_tiktok_script(topic)` — short video script
  - `generate_facebook_post(topic)` — social update
  - `generate_red_note(topic)` — 小红书种草笔记 (Chinese)
  - `generate_douyin_script(topic)` — 抖音口播脚本 (Chinese)
  - `generate_wechat_article(topic)` — 公众号文章 (Chinese)
  - `generate_wechat_moment(topic)` — 朋友圈文案 (Chinese)
  - `generate_all(topic)` — generate for all platforms at once
- [ ] Commit

### Task 3: Admin social media page

**Files:**
- Create: `E:\hollowsheet\backend\admin\templates\social.html`
- Update: `E:\hollowsheet\backend\admin\router.py`
- Update: `E:\hollowsheet\backend\admin\templates\base.html`

**Steps:**
- [ ] Create social.html — content calendar view, generate button, queue list
- [ ] Add `/admin/social` route
- [ ] Update sidebar
- [ ] Commit
