"""APScheduler setup for background tasks."""
import traceback
from functools import wraps
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import sys
import io

# Force UTF-8 on Windows to avoid GBK encoding crashes
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

scheduler = AsyncIOScheduler()


def _safe_job(name: str):
    """Decorator: catch any exception in scheduled job, log it, never crash."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception:
                print(f"[Scheduler] {name} FAILED:\n{traceback.format_exc()}")
                return None
        return wrapper
    return decorator


def start_scheduler():
    """Register and start all scheduled jobs with error-catching wrappers."""
    # Daily blog post at 09:00 Beijing time (01:00 UTC)
    from backend.tasks.daily_blog import scheduled_blog_task
    scheduler.add_job(
        _safe_job("daily_blog")(scheduled_blog_task),
        CronTrigger(hour=1, minute=0),
        id="daily_blog",
        replace_existing=True,
    )

    # Check email sequences every 30 minutes
    from backend.tasks.email_sequences import scheduled_email_sequences
    scheduler.add_job(
        _safe_job("email_sequences")(scheduled_email_sequences),
        CronTrigger(minute="*/30"),
        id="email_sequences",
        replace_existing=True,
    )

    # Daily market scan at 08:00 Beijing time (00:00 UTC)
    from backend.tasks.market_scan import scheduled_market_scan
    scheduler.add_job(
        _safe_job("market_scan")(scheduled_market_scan),
        CronTrigger(hour=0, minute=0),
        id="market_scan",
        replace_existing=True,
    )

    # Campaign runner: run pending campaigns daily at 09:00 Beijing (01:00 UTC)
    from backend.routers.campaign import run_pending_campaigns
    scheduler.add_job(
        _safe_job("campaign_runner")(run_pending_campaigns),
        CronTrigger(hour=1, minute=0),
        id="campaign_runner",
        replace_existing=True,
    )

    # Auto-CRM: search every N minutes (IntervalTrigger, configured via interval_min)
    import json as _json
    _cfg_file = Path("auto-crm/data/email_config.json")
    _interval_minutes = 180  # default: every 3 hours
    if _cfg_file.exists():
        try:
            _cfg = _json.loads(_cfg_file.read_text(encoding="utf-8"))
            _interval_minutes = _cfg.get("interval_min", 180) or 180
        except:
            pass
    from backend.tasks.auto_crm_daily import scheduled_auto_crm_task
    scheduler.add_job(
        _safe_job("auto_crm")(scheduled_auto_crm_task),
        IntervalTrigger(minutes=_interval_minutes),
        id="auto_crm_daily",
        replace_existing=True,
    )

    # RED auto-publish: check every 30 minutes
    from backend.tasks.daily_red import generate_and_publish_red
    scheduler.add_job(
        _safe_job("daily_red")(generate_and_publish_red),
        CronTrigger(minute="*/30"),
        id="daily_red",
        replace_existing=True,
    )

    scheduler.start()
