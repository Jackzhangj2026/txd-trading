"""APScheduler setup for background tasks."""

from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Register and start all scheduled jobs."""
    # Daily blog post at 09:00 Beijing time (01:00 UTC)
    from backend.tasks.daily_blog import scheduled_blog_task
    scheduler.add_job(
        scheduled_blog_task,
        CronTrigger(hour=1, minute=0),  # UTC
        id="daily_blog",
        replace_existing=True,
    )

    # Check email sequences every 30 minutes
    from backend.tasks.email_sequences import scheduled_email_sequences
    scheduler.add_job(
        scheduled_email_sequences,
        CronTrigger(minute="*/30"),
        id="email_sequences",
        replace_existing=True,
    )

    # Daily market scan at 08:00 Beijing time (00:00 UTC)
    from backend.tasks.market_scan import scheduled_market_scan
    scheduler.add_job(
        scheduled_market_scan,
        CronTrigger(hour=0, minute=0),
        id="market_scan",
        replace_existing=True,
    )

    # Campaign runner: run pending campaigns daily at 09:00 Beijing (01:00 UTC)
    from backend.routers.campaign import run_pending_campaigns
    scheduler.add_job(
        run_pending_campaigns,
        CronTrigger(hour=1, minute=0),
        id="campaign_runner",
        replace_existing=True,
    )

    # Auto-CRM: send development emails at configured hour (Beijing time)
    import json as _json
    _cfg_file = Path("auto-crm/data/email_config.json")
    _schedule_hour = 10  # default
    if _cfg_file.exists():
        try:
            _cfg = _json.loads(_cfg_file.read_text(encoding="utf-8"))
            _schedule_hour = _cfg.get("schedule_hour", 10)
        except:
            pass
    # Convert Beijing hour to UTC
    _utc_hour = (_schedule_hour - 8) % 24
    from backend.tasks.auto_crm_daily import scheduled_auto_crm_task
    scheduler.add_job(
        scheduled_auto_crm_task,
        CronTrigger(hour=_utc_hour, minute=0),
        id="auto_crm_daily",
        replace_existing=True,
    )

    # RED auto-publish: check every 30 minutes, task reads settings + respects time
    from backend.tasks.daily_red import generate_and_publish_red
    scheduler.add_job(
        generate_and_publish_red,
        CronTrigger(minute="*/30"),
        id="daily_red",
        replace_existing=True,
    )

    scheduler.start()
