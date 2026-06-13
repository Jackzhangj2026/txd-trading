# Phase 3: Email Communication System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-mailbox email system with template engine, intelligent reply classification, email sequence orchestration, and admin management pages.

**Architecture:** SQLAlchemy models for mailboxes/templates/logs/sequences, smtplib+imaplib for email transport, TradeAgent for LLM classification of incoming emails, APScheduler for polling and sequence dispatch.

**Tech Stack:** FastAPI, SQLAlchemy, TradeAgent, smtplib, imaplib, email (stdlib), Jinja2, APScheduler

---

### Task 1: Mailbox model + CRUD API

**Files:**
- Create: `E:\hollowsheet\backend\models\mailbox.py`
- Update: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\routers\mailboxes.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**

- [ ] Create `models/mailbox.py` with Mailbox model (name, email_address, imap_host/port/username/password_enc, smtp_host/port/username/password_enc, use_ssl, routing_rules as JSON, assigned_to, daily_send_limit, active, last_checked)
- [ ] Update models `__init__.py` to export Mailbox
- [ ] Create `routers/mailboxes.py` with CRUD + test endpoint
- [ ] Register router in main.py
- [ ] Commit

### Task 2: Email template model + API + EmailLog model

**Files:**
- Create: `E:\hollowsheet\backend\models\email_template.py`
- Create: `E:\hollowsheet\backend\models\email_log.py`
- Create: `E:\hollowsheet\backend\models\email_sequence.py`
- Update: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\routers\emails.py`
- Update: `E:\hollowsheet\backend\main.py`

**Steps:**

- [ ] Create `models/email_template.py` (name, subject_template, body_template, category, variables as JSON, active)
- [ ] Create `models/email_log.py` (mailbox_id FK, customer_id FK, direction: in/out, subject, body, status, sent_at)
- [ ] Create `models/email_sequence.py` (customer_id FK, template_id FK, status: pending/sent/replied/completed, scheduled_at, sent_at, step_number)
- [ ] Update models `__init__.py`
- [ ] Create `routers/emails.py` with: list/create templates, list email log by customer, send email endpoint
- [ ] Register router in main.py
- [ ] Commit

### Task 3: Email service — send + receive

**Files:**
- Create: `E:\hollowsheet\backend\services\email_service.py`
- Update: `E:\hollowsheet\backend\routers\emails.py` (add test+check endpoints)

**Steps:**

- [ ] Create `services/email_service.py` with:
  - `EmailService.send_email(mailbox_id, to, subject, body)` — SMTP send
  - `EmailService.check_inbox(mailbox_id)` — IMAP fetch recent unread
  - `EmailService.classify_and_route(email)` — LLM classify intent → auto-reply or flag
- [ ] Update emails router: add POST test connection, POST check inbox
- [ ] Test with keyword fallback (no real email needed)
- [ ] Commit

### Task 4: Email sequence orchestration

**Files:**
- Create: `E:\hollowsheet\backend\services\sequence_service.py`
- Create: `E:\hollowsheet\backend\tasks\email_sequences.py`
- Update: `E:\hollowsheet\backend\scheduler.py`

**Steps:**

- [ ] Create `services/sequence_service.py` with:
  - `SequenceService.create_sequence(customer_id, template_ids)` — create follow-up sequence
  - `SequenceService.process_due_sequences()` — check for sequences due to send
  - `SequenceService.handle_reply(customer_id)` — pause sequence on customer reply
- [ ] Create `tasks/email_sequences.py` — scheduled task to process due sequences
- [ ] Update scheduler.py to add sequence processing job
- [ ] Commit

### Task 5: Admin email management pages

**Files:**
- Create: `E:\hollowsheet\backend\admin\templates\email.html`
- Update: `E:\hollowsheet\backend\admin\router.py`

**Steps:**

- [ ] Create email management admin page with:
  - Mailbox list (name, address, status, last checked)
  - Template list (name, category, preview)
  - Email log for a customer (read-only)
- [ ] Update sidebar link in base.html (remove "COMING SOON" from Emails)
- [ ] Commit

---

## Verification

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Check:
- [ ] `GET /api/mailboxes` → empty list
- [ ] `POST /api/email-templates` → creates template
- [ ] `GET /api/email-templates` → lists templates
- [ ] `GET /admin/emails` → rendered email management page
