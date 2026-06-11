"""APScheduler setup for background tasks."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.tasks.daily_blog import scheduled_blog_task
from backend.tasks.email_sequences import scheduled_email_sequences

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Register and start all scheduled jobs."""
    # Daily blog post at 09:00 Beijing time (01:00 UTC)
    scheduler.add_job(
        scheduled_blog_task,
        CronTrigger(hour=1, minute=0),  # UTC
        id="daily_blog",
        replace_existing=True,
    )

    # Check email sequences every 30 minutes
    scheduler.add_job(
        scheduled_email_sequences,
        CronTrigger(minute="*/30"),
        id="email_sequences",
        replace_existing=True,
    )

    scheduler.start()
