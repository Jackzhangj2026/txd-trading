"""APScheduler setup for background tasks."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.tasks.daily_blog import scheduled_blog_task

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

    scheduler.start()
