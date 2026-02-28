"""
rss.py — Fetches and parses RSS feeds.
No LLM calls here — pure fetch, parse, dedup, store.
"""

import json
import logging
from datetime import datetime

import feedparser

from database import (
    insert_rss_item,
    is_fingerprint_seen,
    is_rss_item_seen,
    log_poll,
)
from fingerprint import make_fingerprint

logger = logging.getLogger(__name__)


def _parse_published(entry) -> str:
    if hasattr(entry, "published"):
        return entry.published
    if hasattr(entry, "updated"):
        return entry.updated
    return datetime.utcnow().isoformat()


def _get_guid(entry) -> str:
    if hasattr(entry, "id") and entry.id:
        return entry.id
    if hasattr(entry, "link") and entry.link:
        return entry.link
    return make_fingerprint(entry.get("title", ""), "")


def poll_feed(feed_config: dict) -> tuple[int, int]:
    name = feed_config["name"]
    url = feed_config["url"]
    error = None
    items_found = 0
    items_new = 0

    try:
        logger.info("Polling RSS: %s", name)
        parsed = feedparser.parse(url)

        if parsed.bozo and not parsed.entries:
            raise ValueError(f"Feed parse error: {parsed.bozo_exception}")

        entries = parsed.entries
        items_found = len(entries)

        for entry in entries:
            guid = _get_guid(entry)
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            summary = summary.strip()

            if is_rss_item_seen(guid):
                continue

            fingerprint = make_fingerprint(title, summary)
            if is_fingerprint_seen(fingerprint):
                logger.debug("Fingerprint match (dup): %s", title[:60])
                continue

            insert_rss_item({
                "source_name": feed_config["name"],
                "source_type": feed_config["source_type"],
                "credibility_tier": feed_config["credibility_tier"],
                "guid": guid,
                "fingerprint": fingerprint,
                "title": title,
                "url": entry.get("link", ""),
                "summary": summary[:2000],
                "published_at": _parse_published(entry),
                "topics": json.dumps(feed_config.get("topics", [])),
                "ingested_at": datetime.utcnow().isoformat(),
            })
            items_new += 1
            logger.debug("New item: %s", title[:80])

    except Exception as e:
        error = str(e)
        logger.error("Error polling %s: %s", name, e)

    finally:
        log_poll(name, "rss", items_found, items_new, error)

    return items_found, items_new


def poll_all_feeds(feeds: list[dict]):
    total_found = 0
    total_new = 0
    for feed in feeds:
        found, new = poll_feed(feed)
        total_found += found
        total_new += new
    logger.info("RSS cycle complete — %d found, %d new", total_found, total_new)
