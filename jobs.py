"""
jobs.py — All scheduled jobs.

Schedule:
  RSS feeds       — every 15 minutes, 24/7
  AlphaVantage    — every 60 minutes, 24/7 (configurable)
  YouTube         — every 30 minutes, 24/7 (self-gated by posting window)
  Digest          — daily at 06:15 AM PST (14:15 UTC)
"""

import logging
import os
import threading

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import RSS_FEEDS, YOUTUBE_CHANNELS, ALPHAVANTAGE_SOURCES
from rss import poll_all_feeds
from youtube import poll_all_channels
from alphavantage import poll_all_sources
from digest import generate_digest
from web import start_web_server

logger = logging.getLogger(__name__)

AV_POLL_INTERVAL = int(os.getenv("AV_POLL_INTERVAL_MINUTES", "60"))


def run_rss_job():
    logger.info("=== RSS poll cycle starting ===")
    poll_all_feeds(RSS_FEEDS)


def run_alphavantage_job():
    logger.info("=== AlphaVantage poll cycle starting ===")
    poll_all_sources(ALPHAVANTAGE_SOURCES)


def run_youtube_job():
    logger.info("=== YouTube poll cycle starting ===")
    poll_all_channels(YOUTUBE_CHANNELS)


def run_digest_job():
    logger.info("=== Daily digest job starting ===")
    try:
        generate_digest()
    except Exception as e:
        logger.error("Digest generation failed: %s", e)


def start_scheduler():
    # Start Flask web server in a background thread
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

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

    # AlphaVantage: configurable, default 60 minutes
    scheduler.add_job(
        run_alphavantage_job,
        trigger=IntervalTrigger(minutes=AV_POLL_INTERVAL),
        id="alphavantage_poll",
        name="AlphaVantage News Polling",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # YouTube: every 30 minutes
    scheduler.add_job(
        run_youtube_job,
        trigger=IntervalTrigger(minutes=30),
        id="youtube_poll",
        name="YouTube Channel Polling",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # Digest: daily at 06:15 AM PST = 14:15 UTC
    scheduler.add_job(
        run_digest_job,
        trigger=CronTrigger(hour=14, minute=15, timezone="UTC"),
        id="digest_daily",
        name="Daily Energy Jerkoff Digest",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(
        "Scheduler started — RSS 15min | AV %dmin | YouTube 30min | Digest 06:15 PST daily",
        AV_POLL_INTERVAL,
    )
    scheduler.start()
