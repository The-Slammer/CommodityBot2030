"""
scheduler/jobs.py — Defines and registers all polling jobs.
RSS runs every 15 minutes. YouTube runs every 30 minutes but
the channel module self-gates based on each channel's posting window.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import RSS_FEEDS, YOUTUBE_CHANNELS
from ingestion.rss import poll_all_feeds
from ingestion.youtube import poll_all_channels

logger = logging.getLogger(__name__)


def run_rss_job():
    logger.info("=== RSS poll cycle starting ===")
    poll_all_feeds(RSS_FEEDS)


def run_youtube_job():
    logger.info("=== YouTube poll cycle starting ===")
    poll_all_channels(YOUTUBE_CHANNELS)


def start_scheduler():
    scheduler = BlockingScheduler(timezone="UTC")

    # RSS: every 15 minutes
    scheduler.add_job(
        run_rss_job,
        trigger=IntervalTrigger(minutes=15),
        id="rss_poll",
        name="RSS Feed Polling",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # YouTube: every 30 minutes (channels self-gate by posting window)
    scheduler.add_job(
        run_youtube_job,
        trigger=IntervalTrigger(minutes=30),
        id="youtube_poll",
        name="YouTube Channel Polling",
        replace_existing=True,
        misfire_grace_time=60,
    )

    logger.info("Scheduler started — RSS every 15min, YouTube every 30min")
    scheduler.start()
