"""
alphavantage.py — Fetches news and sentiment data from AlphaVantage NEWS_SENTIMENT API.
Handles both ticker-specific queries (XOM, CVX) and topic-based queries (energy_transportation).
Deduplicates by URL before storing. Sentiment scores are stored with each item — no LLM needed.
"""

import json
import logging
import os
import time
from datetime import datetime

import requests

from database import (
    insert_alphavantage_item,
    is_alphavantage_item_seen,
    log_poll,
)
from fingerprint import make_fingerprint

logger = logging.getLogger(__name__)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

# Items to fetch per source per call. Keep conservative to limit noise.
ITEMS_PER_SOURCE = 20


def _fetch_news(query_type: str, query_value: str) -> list[dict]:
    """
    Call the AlphaVantage NEWS_SENTIMENT endpoint.
    Returns a list of raw article dicts or empty list on failure.
    """
    if not ALPHAVANTAGE_API_KEY:
        raise EnvironmentError("ALPHAVANTAGE_API_KEY not set")

    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": ALPHAVANTAGE_API_KEY,
        "limit": ITEMS_PER_SOURCE,
        "sort": "LATEST",
    }

    if query_type == "ticker":
        params["tickers"] = query_value
    elif query_type == "topic":
        params["topics"] = query_value
    else:
        raise ValueError(f"Unknown query_type: {query_type}")

    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    # AlphaVantage returns an error note in the JSON for bad keys / rate limits
    if "Note" in data:
        raise RuntimeError(f"AlphaVantage API note: {data['Note']}")
    if "Information" in data:
        raise RuntimeError(f"AlphaVantage API info: {data['Information']}")

    return data.get("feed", [])


def _parse_av_timestamp(ts: str) -> str:
    """Convert AV timestamp format (20260228T044358) to ISO."""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S").isoformat()
    except Exception:
        return ts


def poll_source(source_config: dict) -> tuple[int, int]:
    """
    Fetch news for a single AlphaVantage source config entry.
    Returns (items_found, items_new).
    """
    name = source_config["name"]
    query_type = source_config["query_type"]
    query_value = source_config["query_value"]
    error = None
    items_found = 0
    items_new = 0

    try:
        logger.info("Polling AlphaVantage: %s", name)
        articles = _fetch_news(query_type, query_value)
        items_found = len(articles)

        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "").strip()
            summary = article.get("summary", "").strip()

            if not url:
                continue

            # Dedup by URL first (cheapest check)
            if is_alphavantage_item_seen(url):
                continue

            # Secondary dedup by content fingerprint
            fingerprint = make_fingerprint(title, summary)

            # Extract ticker sentiments as JSON
            ticker_sentiment = json.dumps(article.get("ticker_sentiment", []))

            # Extract topic tags from AV's own topic classification
            av_topics = [t["topic"] for t in article.get("topics", [])]

            insert_alphavantage_item({
                "source_name": name,
                "query_type": query_type,
                "query_value": query_value,
                "source_type": source_config["source_type"],
                "credibility_tier": source_config["credibility_tier"],
                "url": url,
                "fingerprint": fingerprint,
                "title": title,
                "summary": summary[:2000],
                "source_publisher": article.get("source", ""),
                "published_at": _parse_av_timestamp(article.get("time_published", "")),
                "overall_sentiment_score": article.get("overall_sentiment_score"),
                "overall_sentiment_label": article.get("overall_sentiment_label", ""),
                "ticker_sentiment": ticker_sentiment,
                "av_topics": json.dumps(av_topics),
                "topics": json.dumps(source_config.get("topics", [])),
                "ingested_at": datetime.utcnow().isoformat(),
            })
            items_new += 1
            logger.debug("New AV item [%s]: %s", name, title[:80])

    except Exception as e:
        error = str(e)
        logger.error("Error polling AlphaVantage %s: %s", name, e)

    finally:
        log_poll(name, "alphavantage", items_found, items_new, error)

    return items_found, items_new


def poll_all_sources(sources: list[dict]):
    """
    Poll all configured AlphaVantage sources.
    Chunks requests into batches of 60 per minute to stay safely
    under the 75/min rate limit regardless of how many tickers are tracked.
    """
    CHUNK_SIZE   = 60   # requests per chunk
    CHUNK_WINDOW = 62   # seconds to wait after each chunk (full minute + 2s buffer)
    CALL_DELAY   = 0.5  # seconds between individual calls within a chunk

    total_found  = 0
    total_new    = 0
    chunk_start  = time.time()

    for i, source in enumerate(sources):
        found, new = poll_source(source)
        total_found += found
        total_new   += new

        # After every 60 requests, ensure a full minute has elapsed
        if (i + 1) % CHUNK_SIZE == 0 and i < len(sources) - 1:
            elapsed = time.time() - chunk_start
            wait = max(0, CHUNK_WINDOW - elapsed)
            if wait > 0:
                logger.info(
                    "AV rate limit pause — %d requests sent, waiting %.1fs before next chunk",
                    i + 1, wait
                )
                time.sleep(wait)
            chunk_start = time.time()
        elif i < len(sources) - 1:
            time.sleep(CALL_DELAY)

    logger.info(
        "AlphaVantage cycle complete — %d found, %d new",
        total_found, total_new
    )
