"""
jobs.py — All scheduled jobs.

Schedule (UTC):
  RSS             — every 15 min
  AlphaVantage    — every 60 min
  SEC filings     — every 60 min (same cycle as AV)
  YouTube         — every 30 min
  Sentiment       — after every AV poll
  Earnings check  — daily 13:00 UTC (5 AM PST)
  Morning digest  — daily 14:15 UTC (6:15 AM PST)
  EIA Crude       — Wednesdays 15:30 UTC (10:30 AM EST)
  EIA Nat Gas     — Thursdays 15:30 UTC (10:30 AM EST)
  EIA Drilling    — 16th of month 16:00 UTC
  Transcript poll — daily 21:00 + 23:00 UTC
  Evening digest  — daily 01:30 UTC (5:30 PM PST)
  Weekly wrap     — Saturdays 01:30 UTC (Friday 5:30 PM PST)
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
try:
    from eia import poll_eia_crude, poll_eia_natgas, poll_eia_drilling
    _eia_available = True
except ImportError as e:
    import logging; logging.getLogger(__name__).warning("eia module unavailable: %s", e)
    _eia_available = False
    def poll_eia_crude(): pass
    def poll_eia_natgas(): pass
    def poll_eia_drilling(): pass

try:
    from sec import poll_sec_filings
    _sec_available = True
except ImportError as e:
    import logging; logging.getLogger(__name__).warning("sec module unavailable: %s", e)
    _sec_available = False
    def poll_sec_filings(tickers): pass

try:
    from trading import run_trading_window, run_eod_settlement
    _trading_available = True
except ImportError as e:
    import logging; logging.getLogger(__name__).warning("trading module unavailable: %s", e)
    _trading_available = False
    def run_trading_window(window): pass
    def run_eod_settlement(): pass
from web import start_web_server

logger = logging.getLogger(__name__)
AV_POLL_INTERVAL = int(os.getenv("AV_POLL_INTERVAL_MINUTES", "60"))


def run_rss_job():
    logger.info("=== RSS poll cycle ===")
    poll_all_feeds(RSS_FEEDS)


def run_alphavantage_job():
    logger.info("=== AlphaVantage poll cycle ===")
    poll_all_sources(ALPHAVANTAGE_SOURCES)
    update_all_equity_signals(ALPHAVANTAGE_SOURCES)


def run_sec_job():
    logger.info("=== SEC filings poll cycle ===")
    try:
        poll_sec_filings(EARNINGS_TRACKED_TICKERS)
    except Exception as e:
        logger.error("SEC poll failed: %s", e)


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


def run_eia_crude_job():
    logger.info("=== EIA crude inventory job ===")
    try:
        poll_eia_crude()
    except Exception as e:
        logger.error("EIA crude job failed: %s", e)


def run_eia_natgas_job():
    logger.info("=== EIA nat gas storage job ===")
    try:
        poll_eia_natgas()
    except Exception as e:
        logger.error("EIA nat gas job failed: %s", e)


def run_eia_drilling_job():
    logger.info("=== EIA drilling productivity job ===")
    try:
        poll_eia_drilling()
    except Exception as e:
        logger.error("EIA drilling job failed: %s", e)


def run_trading_morning():
    try:
        run_trading_window("morning_open")
    except Exception as e:
        logger.error("Trading window morning failed: %s", e)


def run_trading_midday():
    try:
        run_trading_window("midday")
    except Exception as e:
        logger.error("Trading window midday failed: %s", e)


def run_trading_preclose():
    try:
        run_trading_window("pre_close")
    except Exception as e:
        logger.error("Trading window pre-close failed: %s", e)


def run_eod_settlement_job():
    try:
        run_eod_settlement()
    except Exception as e:
        logger.error("EOD settlement failed: %s", e)


def start_scheduler():
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    scheduler = BlockingScheduler(timezone="UTC")

    # Continuous ingestion
    scheduler.add_job(run_rss_job, IntervalTrigger(minutes=15), id="rss_poll", misfire_grace_time=60)
    scheduler.add_job(run_alphavantage_job, IntervalTrigger(minutes=AV_POLL_INTERVAL), id="av_poll", misfire_grace_time=120)
    scheduler.add_job(run_sec_job, IntervalTrigger(minutes=AV_POLL_INTERVAL), id="sec_poll", misfire_grace_time=120)
    scheduler.add_job(run_youtube_job, IntervalTrigger(minutes=30), id="yt_poll", misfire_grace_time=60)

    # Daily reports (PST)
    scheduler.add_job(run_morning_digest_job, CronTrigger(hour=14, minute=15, timezone="UTC"), id="morning_digest", misfire_grace_time=300)
    scheduler.add_job(run_evening_digest_job, CronTrigger(hour=1, minute=30, timezone="UTC"), id="evening_digest", misfire_grace_time=300)

    # Weekly wrap — Friday 5:30 PM PST = Saturday 01:30 UTC
    scheduler.add_job(run_weekly_digest_job, CronTrigger(day_of_week="sat", hour=1, minute=30, timezone="UTC"), id="weekly_digest", misfire_grace_time=300)

    # EIA release schedules (EST = UTC-5)
    scheduler.add_job(run_eia_crude_job, CronTrigger(day_of_week="wed", hour=15, minute=35, timezone="UTC"), id="eia_crude", misfire_grace_time=300)
    scheduler.add_job(run_eia_natgas_job, CronTrigger(day_of_week="thu", hour=15, minute=35, timezone="UTC"), id="eia_natgas", misfire_grace_time=300)
    scheduler.add_job(run_eia_drilling_job, CronTrigger(day=16, hour=16, minute=0, timezone="UTC"), id="eia_drilling", misfire_grace_time=600)

    # Paper trading windows (ET times converted to UTC)
    # 09:45 ET = 14:45 UTC  |  12:00 ET = 17:00 UTC  |  15:30 ET = 20:30 UTC
    # EOD settlement = 21:15 UTC (after 4 PM ET close)
    scheduler.add_job(run_trading_morning,  CronTrigger(hour=14, minute=45, day_of_week="mon-fri", timezone="UTC"), id="trade_morning",  misfire_grace_time=120)
    scheduler.add_job(run_trading_midday,   CronTrigger(hour=17, minute=0,  day_of_week="mon-fri", timezone="UTC"), id="trade_midday",   misfire_grace_time=120)
    scheduler.add_job(run_trading_preclose, CronTrigger(hour=20, minute=30, day_of_week="mon-fri", timezone="UTC"), id="trade_preclose", misfire_grace_time=120)
    scheduler.add_job(run_eod_settlement_job, CronTrigger(hour=21, minute=15, day_of_week="mon-fri", timezone="UTC"), id="eod_settlement", misfire_grace_time=300)

    # Earnings transcript polling (after market close)
    scheduler.add_job(run_transcript_poll_job, CronTrigger(hour=21, minute=0, timezone="UTC"), id="transcript_poll", misfire_grace_time=300)
    scheduler.add_job(run_transcript_poll_job, CronTrigger(hour=23, minute=0, timezone="UTC"), id="transcript_poll_2", misfire_grace_time=300)

    # Earnings calendar check (morning, before digest)
    scheduler.add_job(
        lambda: check_earnings_calendar(EARNINGS_TRACKED_TICKERS),
        CronTrigger(hour=13, minute=0, timezone="UTC"),
        id="earnings_check",
        misfire_grace_time=300
    )

    logger.info(
        "Scheduler started — %d jobs registered | AV interval: %dmin",
        len(scheduler.get_jobs()), AV_POLL_INTERVAL
    )
    scheduler.start()
