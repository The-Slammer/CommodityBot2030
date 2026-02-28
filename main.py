"""
main.py — Entrypoint. Initializes DB, runs an immediate first poll, then starts the scheduler.
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
    from db.database import init_db
    from config import RSS_FEEDS, YOUTUBE_CHANNELS
    from ingestion.rss import poll_all_feeds
    from ingestion.youtube import poll_all_channels
    from scheduler.jobs import start_scheduler

    logger.info("Energy Agent starting up")

    # Initialize DB schema
    init_db()

    # Run an immediate poll on startup so you don't wait 15 minutes for first data
    logger.info("Running initial poll...")
    poll_all_feeds(RSS_FEEDS)
    poll_all_channels(YOUTUBE_CHANNELS)

    # Hand off to scheduler — this blocks forever
    start_scheduler()


if __name__ == "__main__":
    main()
