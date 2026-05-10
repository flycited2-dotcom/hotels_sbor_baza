import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import (
    DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE,
    WEEKLY_REPORT_WEEKDAY, WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE,
)
from services import db, excel, notifier

logger = logging.getLogger(__name__)


async def daily_job(bot):
    logger.info("Running daily digest job")
    try:
        leads = await db.get_leads_today()
        filepath = excel.generate_daily_report(leads) if leads else None
        await notifier.send_daily_digest(bot, leads, filepath)
    except Exception as e:
        logger.error(f"Daily job error: {e}")


async def weekly_job(bot):
    logger.info("Running weekly master job")
    try:
        all_leads = await db.get_all_leads()
        total = len(all_leads)

        # Count leads added this week (last 7 days)
        from datetime import date, timedelta
        week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_leads = [l for l in all_leads if l.get("created_at", "") >= week_ago]
        week_count = len(week_leads)

        filepath = excel.generate_master_report(all_leads) if all_leads else None
        await notifier.send_weekly_master(bot, total, week_count, filepath)
    except Exception as e:
        logger.error(f"Weekly job error: {e}")


def setup_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Simferopol")

    scheduler.add_job(
        daily_job,
        CronTrigger(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MINUTE),
        args=[bot],
        id="daily_digest",
        replace_existing=True,
    )

    scheduler.add_job(
        weekly_job,
        CronTrigger(day_of_week=WEEKLY_REPORT_WEEKDAY, hour=WEEKLY_REPORT_HOUR, minute=WEEKLY_REPORT_MINUTE),
        args=[bot],
        id="weekly_master",
        replace_existing=True,
    )

    return scheduler
