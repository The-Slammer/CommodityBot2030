"""
main.py — Entrypoint.
"""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    from database import init_db, init_new_tables
    from config import RSS_FEEDS, YOUTUBE_CHANNELS, ALPHAVANTAGE_SOURCES, EARNINGS_TRACKED_TICKERS
    from rss import poll_all_feeds
    from youtube import poll_all_channels
    from alphavantage import poll_all_sources
    from jobs import start_scheduler

    logger.info("CommodityBot starting up")

    # Core DB init — must succeed
    init_db()
    init_new_tables()

    # Optional table init — warn but continue if module not yet deployed
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

    # Initial ingestion polls
    logger.info("Running initial polls...")
    try:
        poll_all_feeds(RSS_FEEDS)
    except Exception as e:
        logger.error("Initial RSS poll failed: %s", e)

    try:
        poll_all_sources(ALPHAVANTAGE_SOURCES)
    except Exception as e:
        logger.error("Initial AV poll failed: %s", e)

    try:
        poll_all_channels(YOUTUBE_CHANNELS)
    except Exception as e:
        logger.error("Initial YouTube poll failed: %s", e)

    # Sentiment signals — non-critical for startup
    try:
        from sentiment import update_all_equity_signals
        update_all_equity_signals(ALPHAVANTAGE_SOURCES)
    except Exception as e:
        logger.error("Initial sentiment update failed: %s", e)

    # SEC filings — non-critical for startup
    try:
        from sec import poll_sec_filings
        poll_sec_filings(EARNINGS_TRACKED_TICKERS)
    except Exception as e:
        logger.error("Initial SEC poll failed: %s", e)

    # Always reaches here — start web + scheduler
    logger.info("Starting scheduler and web server...")
    start_scheduler()


if __name__ == "__main__":
    main()
