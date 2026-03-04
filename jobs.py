"""
jobs.py — All scheduled jobs.

Schedule (UTC):
  RSS                  — every 15 min
  Commodity prices     — every 30 min
  AV oil_gas           — every 60 min, offset :00
  AV uranium           — every 60 min, offset :15
  AV precious_metals   — every 60 min, offset :30  (ready for gold/silver)
  AV copper            — every 60 min, offset :40  (ready for copper)
  AV lithium           — every 60 min, offset :50  (ready for lithium)
  SEC filings          — every 60 min, offset :05
  YouTube              — every 6 hours
  Style reference      — Sundays 18:00 UTC (Tim Dillon)
  Sentiment            — after each AV market group completes
  Earnings check       — daily 13:00 UTC (5 AM PST)
  Morning digest       — daily 14:15 UTC (6:15 AM PST)
  EIA Crude            — Wednesdays 15:35 UTC
  EIA Nat Gas          — Thursdays 15:35 UTC
  EIA Drilling         — 16th of month 16:00 UTC
  Transcript poll      — daily 21:00 + 23:00 UTC
  Evening digest       — daily 01:30 UTC (5:30 PM PST)
  Weekly wrap          — Saturdays 01:30 UTC (Friday 5:30 PM PST)
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
from commodity_prices import poll_commodity_prices
from geopolitics import generate_geopolitical_brief
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

try:
    from scanner import run_scanner_job
    _scanner_available = True
except ImportError as e:
    import logging; logging.getLogger(__name__).warning("scanner module unavailable: %s", e)
    _scanner_available = False
    def run_scanner_job(): pass

from web import start_web_server

logger = logging.getLogger(__name__)
AV_POLL_INTERVAL = int(os.getenv("AV_POLL_INTERVAL_MINUTES", "60"))


def run_rss_job():
    logger.info("=== RSS poll cycle ===")
    poll_all_feeds(RSS_FEEDS)


def _sources_for_group(group: str) -> list:
    return [s for s in ALPHAVANTAGE_SOURCES if s.get("commodity_group") == group]


def _run_av_group(group: str):
    sources = _sources_for_group(group)
    if not sources:
        logger.warning("No sources found for commodity_group=%s", group)
        return
    logger.info("=== AV poll: %s (%d sources) ===", group, len(sources))
    poll_all_sources(sources)
    update_all_equity_signals(sources)


def run_av_oil_gas():
    _run_av_group("oil_gas")


def run_av_uranium():
    _run_av_group("uranium")


def run_av_precious_metals():
    _run_av_group("precious_metals")


def run_av_copper():
    _run_av_group("copper")


def run_av_lithium():
    _run_av_group("lithium")


def run_sec_job():
    logger.info("=== SEC filings poll cycle ===")
    try:
        poll_sec_filings(EARNINGS_TRACKED_TICKERS)
    except Exception as e:
        logger.error("SEC poll failed: %s", e)


def run_youtube_job():
    logger.info("=== YouTube poll cycle ===")
    # Exclude style_reference channels — those run on their own schedule
    news_channels = [c for c in YOUTUBE_CHANNELS if not c.get("style_reference")]
    poll_all_channels(news_channels)


def run_style_reference_job():
    """Poll style_reference channels only — runs Sundays."""
    style_channels = [c for c in YOUTUBE_CHANNELS if c.get("style_reference")]
    if style_channels:
        logger.info("=== Style reference poll (Tim Dillon) ===")
        poll_all_channels(style_channels)


def run_morning_digest_job():
    logger.info("=== Morning digest job ===")
    try:
        check_earnings_calendar(EARNINGS_TRACKED_TICKERS)
        logger.info("Pre-digest commodity price refresh...")
        poll_commodity_prices()
    except Exception as e:
        logger.warning("Pre-digest price refresh failed (continuing): %s", e)
    try:
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
    scheduler.add_job(run_sec_job, CronTrigger(minute=5), id="sec_poll", misfire_grace_time=120)

    # AV market groups — staggered every 10-15 min to avoid rate limit bursts
    # Each group runs independently on a 60-min cycle at its offset
    scheduler.add_job(poll_commodity_prices, IntervalTrigger(minutes=30), id="commodity_prices", misfire_grace_time=120)
    scheduler.add_job(generate_geopolitical_brief, CronTrigger(hour=5, minute=0), id="geo_brief", misfire_grace_time=300)
    scheduler.add_job(run_av_oil_gas,         CronTrigger(minute=0),  id="av_oil_gas",         misfire_grace_time=120)
    scheduler.add_job(run_av_uranium,         CronTrigger(minute=15), id="av_uranium",          misfire_grace_time=120)
    scheduler.add_job(run_av_precious_metals, CronTrigger(minute=30), id="av_precious_metals",  misfire_grace_time=120)
    scheduler.add_job(run_av_copper,          CronTrigger(minute=40), id="av_copper",           misfire_grace_time=120)
    scheduler.add_job(run_av_lithium,         CronTrigger(minute=50), id="av_lithium",          misfire_grace_time=120)
    scheduler.add_job(run_youtube_job, IntervalTrigger(hours=6), id="yt_poll", misfire_grace_time=300)
    scheduler.add_job(run_style_reference_job, CronTrigger(day_of_week="sun", hour=18, minute=0), id="style_ref_poll", misfire_grace_time=3600)

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
    # 09:45 ET = 14:45 UTC  |  12:15 ET = 17:15 UTC (shifted from :00 to avoid AV oil_gas collision)
    # 15:30 ET = 20:30 UTC  |  EOD price update = 21:15 UTC (after 4 PM ET close)
    scheduler.add_job(run_trading_morning,  CronTrigger(hour=14, minute=45, day_of_week="mon-fri", timezone="UTC"), id="trade_morning",  misfire_grace_time=120)
    scheduler.add_job(run_trading_midday,   CronTrigger(hour=17, minute=15, day_of_week="mon-fri", timezone="UTC"), id="trade_midday",   misfire_grace_time=120)
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

    # Nightly scanner — 02:00 UTC (after markets close, before geo brief at 05:00)
    scheduler.add_job(run_scanner_job_wrapper, CronTrigger(hour=2, minute=0, timezone="UTC"), id="scanner_nightly", misfire_grace_time=600)

    logger.info(
        "Scheduler started — %d jobs registered | AV interval: %dmin",
        len(scheduler.get_jobs()), AV_POLL_INTERVAL
    )
    scheduler.start()


def run_scanner_job_wrapper():
    logger.info("=== Nightly scanner job ===")
    try:
        from database import init_scanner_tables
        init_scanner_tables()
        run_scanner_job()
    except Exception as e:
        logger.error("Scanner job failed: %s", e)
