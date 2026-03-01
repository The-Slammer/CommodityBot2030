"""
main.py — Entrypoint.
Flask starts immediately on boot. Initial polls run in background thread.
"""

import logging
import os
import threading
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def run_initial_polls(rss_feeds, av_sources, yt_channels, tracked_tickers):
    """Run startup ingestion in background so Flask can start immediately."""
    logger.info("Background: starting initial polls...")

    try:
        from rss import poll_all_feeds
        poll_all_feeds(rss_feeds)
    except Exception as e:
        logger.error("Initial RSS poll failed: %s", e)

    try:
        from alphavantage import poll_all_sources
        poll_all_sources(av_sources)
    except Exception as e:
        logger.error("Initial AV poll failed: %s", e)

    try:
        from youtube import poll_all_channels
        poll_all_channels(yt_channels)
    except Exception as e:
        logger.error("Initial YouTube poll failed: %s", e)

    try:
        from sentiment import update_all_equity_signals
        update_all_equity_signals(av_sources)
    except Exception as e:
        logger.error("Initial sentiment update failed: %s", e)

    try:
        from sec import poll_sec_filings
        poll_sec_filings(tracked_tickers)
    except Exception as e:
        logger.error("Initial SEC poll failed: %s", e)

    logger.info("Background: initial polls complete")


def main():
    from database import init_db, init_new_tables
    from config import RSS_FEEDS, YOUTUBE_CHANNELS, ALPHAVANTAGE_SOURCES, EARNINGS_TRACKED_TICKERS
    from jobs import start_scheduler

    logger.info("CommodityBot starting up")

    # DB init — must complete before anything else
    init_db()
    init_new_tables()

    try:
        from database import init_eia_sec_tables
        init_eia_sec_tables()
    except Exception as e:
        logger.warning("init_eia_sec_tables skipped: %s", e)

    try:
        from database import init_trading_tables
        init_trading_tables()
    except Exception as e:
        logger.warning("init_trading_tables skipped: %s", e)

    # Kick off initial polls in background thread — don't block Flask startup
    poll_thread = threading.Thread(
        target=run_initial_polls,
        args=(RSS_FEEDS, ALPHAVANTAGE_SOURCES, YOUTUBE_CHANNELS, EARNINGS_TRACKED_TICKERS),
        daemon=True,
    )
    poll_thread.start()

    # Start Flask + scheduler immediately
    logger.info("Starting scheduler and web server...")
    start_scheduler()


if __name__ == "__main__":
    main()
