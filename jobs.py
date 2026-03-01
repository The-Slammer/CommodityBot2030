"""
jobs.py — All scheduled jobs.

Schedule (all UTC):
  RSS             — every 15 min
  AlphaVantage    — every 60 min (configurable)
  YouTube         — every 30 min
  Sentiment       — after every AV poll
  Earnings check  — daily at 13:00 UTC (5 AM PST)
  Transcript poll — daily at 21:00–23:00 UTC (after market close)
  Morning digest  — daily at 14:15 UTC (6:15 AM PST)
  Evening digest  — daily at 01:30 UTC (5:30 PM PST prev day)
  Weekly wrap     — Saturdays at 01:30 UTC (Friday 5:30 PM PST)
"""

import logging
import os
import threading

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import RSS_FEEDS, YOUTUBE_CHANNELS, ALPHAVANTAGE_SOURCES, EARNINGS_TRACKED_TICKERS
from rss import poll_all_feeds
from youtube import poll_all_channels
from alphavantage import poll_all_sources
from digest import generate_digest
from evening_digest import generate_evening_digest
from weekly_digest import generate_weekly_digest
from sentiment import update_all_equity_signals
from earnings import check_earnings_calendar, poll_transcripts_for_watch_list
from web import start_web_server

logger = logging.getLogger(__name__)
AV_POLL_INTERVAL = int(os.getenv("AV_POLL_INTERVAL_MINUTES", "60"))


def run_rss_job():
    logger.info("=== RSS poll cycle ===")
    poll_all_feeds(RSS_FEEDS)


def run_alphavantage_job():
    logger.info("=== AlphaVantage poll cycle ===")
    poll_all_sources(ALPHAVANTAGE_SOURCES)
    # Update equity signals after every news poll
    update_all_equity_signals(ALPHAVANTAGE_SOURCES)


def run_youtube_job():
    logger.info("=== YouTube poll cycle ===")
    poll_all_channels(YOUTUBE_CHANNELS)


def run_morning_digest_job():
    logger.info("=== Morning digest job ===")
    try:
        check_earnings_calendar(EARNINGS_TRACKED_TICKERS)
        generate_digest()
    except Exception as e:
        logger.error("Morning digest failed: %s", e)


def run_evening_digest_job():
    logger.info("=== Evening digest job ===")
    try:
        generate_evening_digest()
    except Exception as e:
        logger.error("Evening digest failed: %s", e)


def run_weekly_digest_job():
    logger.info("=== Weekly digest job ===")
    try:
        generate_weekly_digest()
    except Exception as e:
        logger.error("Weekly digest failed: %s", e)


def run_transcript_poll_job():
    logger.info("=== Transcript poll job ===")
    try:
        poll_transcripts_for_watch_list()
    except Exception as e:
        logger.error("Transcript poll failed: %s", e)


def start_scheduler():
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(run_rss_job, IntervalTrigger(minutes=15), id="rss_poll", misfire_grace_time=60)
    scheduler.add_job(run_alphavantage_job, IntervalTrigger(minutes=AV_POLL_INTERVAL), id="av_poll", misfire_grace_time=120)
    scheduler.add_job(run_youtube_job, IntervalTrigger(minutes=30), id="yt_poll", misfire_grace_time=60)

    # Morning digest — 06:15 AM PST = 14:15 UTC
    scheduler.add_job(run_morning_digest_job, CronTrigger(hour=14, minute=15, timezone="UTC"), id="morning_digest", misfire_grace_time=300)

    # Evening digest — 05:30 PM PST = 01:30 UTC next day
    scheduler.add_job(run_evening_digest_job, CronTrigger(hour=1, minute=30, timezone="UTC"), id="evening_digest", misfire_grace_time=300)

    # Weekly wrap — Friday 05:30 PM PST = Saturday 01:30 UTC
    scheduler.add_job(run_weekly_digest_job, CronTrigger(day_of_week="sat", hour=1, minute=30, timezone="UTC"), id="weekly_digest", misfire_grace_time=300)

    # Transcript poll — after market close, 21:00 UTC = 1 PM PST (transcripts post throughout afternoon)
    scheduler.add_job(run_transcript_poll_job, CronTrigger(hour=21, minute=0, timezone="UTC"), id="transcript_poll", misfire_grace_time=300)
    scheduler.add_job(run_transcript_poll_job, CronTrigger(hour=23, minute=0, timezone="UTC"), id="transcript_poll_2", misfire_grace_time=300)

    logger.info(
        "Scheduler started — RSS 15min | AV %dmin | Morning 06:15 PST | Evening 17:30 PST | Weekly Fri 17:30 PST",
        AV_POLL_INTERVAL,
    )
    scheduler.start()
