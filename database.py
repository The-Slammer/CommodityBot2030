"""
database.py — SQLite schema and all read/write operations.
"""

import sqlite3
import logging
import os
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "energy_agent.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rss_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name     TEXT NOT NULL,
                source_type     TEXT NOT NULL,
                credibility_tier INTEGER NOT NULL,
                guid            TEXT UNIQUE NOT NULL,
                fingerprint     TEXT NOT NULL,
                title           TEXT,
                url             TEXT,
                summary         TEXT,
                published_at    TEXT,
                topics          TEXT,
                ingested_at     TEXT NOT NULL,
                processed       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS youtube_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name     TEXT NOT NULL,
                channel_id      TEXT NOT NULL,
                source_type     TEXT NOT NULL,
                credibility_tier INTEGER NOT NULL,
                video_id        TEXT UNIQUE NOT NULL,
                title           TEXT,
                published_at    TEXT,
                transcript_raw  TEXT,
                transcript_summary TEXT,
                topics          TEXT,
                ingested_at     TEXT NOT NULL,
                processed       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS alphavantage_items (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name             TEXT NOT NULL,
                query_type              TEXT NOT NULL,   -- 'ticker' or 'topic'
                query_value             TEXT NOT NULL,   -- e.g. 'XOM' or 'energy_transportation'
                source_type             TEXT NOT NULL,
                credibility_tier        INTEGER NOT NULL,
                url                     TEXT UNIQUE NOT NULL,  -- primary dedup key
                fingerprint             TEXT NOT NULL,
                title                   TEXT,
                summary                 TEXT,
                source_publisher        TEXT,            -- e.g. 'Reuters', 'Finviz'
                published_at            TEXT,
                overall_sentiment_score REAL,            -- AV pre-scored: -1.0 to 1.0
                overall_sentiment_label TEXT,            -- 'Bullish', 'Neutral', etc.
                ticker_sentiment        TEXT,            -- JSON: per-ticker scores
                av_topics               TEXT,            -- JSON: AV's own topic tags
                topics                  TEXT,            -- JSON: our taxonomy tags
                ingested_at             TEXT NOT NULL,
                processed               INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS source_poll_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name     TEXT NOT NULL,
                source_type     TEXT NOT NULL,           -- 'rss', 'youtube', 'alphavantage'
                polled_at       TEXT NOT NULL,
                items_found     INTEGER DEFAULT 0,
                items_new       INTEGER DEFAULT 0,
                error           TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_rss_guid            ON rss_items(guid);
            CREATE INDEX IF NOT EXISTS idx_rss_fingerprint     ON rss_items(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_rss_processed       ON rss_items(processed);
            CREATE INDEX IF NOT EXISTS idx_yt_video_id         ON youtube_items(video_id);
            CREATE INDEX IF NOT EXISTS idx_yt_processed        ON youtube_items(processed);
            CREATE INDEX IF NOT EXISTS idx_av_url              ON alphavantage_items(url);
            CREATE INDEX IF NOT EXISTS idx_av_fingerprint      ON alphavantage_items(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_av_processed        ON alphavantage_items(processed);
            CREATE INDEX IF NOT EXISTS idx_av_sentiment        ON alphavantage_items(overall_sentiment_score);
            CREATE INDEX IF NOT EXISTS idx_av_query_value      ON alphavantage_items(query_value);

            CREATE TABLE IF NOT EXISTS digests (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str            TEXT NOT NULL,
                html                TEXT NOT NULL,
                price_sentiments    TEXT,   -- JSON
                news_sentiments     TEXT,   -- JSON
                narrative           TEXT,
                generated_at        TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_digest_generated ON digests(generated_at);
        """)
    logger.info("Database initialized at %s", DB_PATH)


# --- RSS ---

def is_rss_item_seen(guid: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM rss_items WHERE guid = ?", (guid,)).fetchone()
        return row is not None


def is_fingerprint_seen(fingerprint: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM rss_items WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return row is not None


def insert_rss_item(item: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO rss_items
                (source_name, source_type, credibility_tier, guid, fingerprint,
                 title, url, summary, published_at, topics, ingested_at)
            VALUES
                (:source_name, :source_type, :credibility_tier, :guid, :fingerprint,
                 :title, :url, :summary, :published_at, :topics, :ingested_at)
        """, item)


def get_unprocessed_rss_items(limit: int = 100) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM rss_items WHERE processed = 0
            ORDER BY ingested_at ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# --- YouTube ---

def is_video_seen(video_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM youtube_items WHERE video_id = ?", (video_id,)).fetchone()
        return row is not None


def insert_youtube_item(item: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO youtube_items
                (source_name, channel_id, source_type, credibility_tier,
                 video_id, title, published_at, transcript_raw,
                 transcript_summary, topics, ingested_at)
            VALUES
                (:source_name, :channel_id, :source_type, :credibility_tier,
                 :video_id, :title, :published_at, :transcript_raw,
                 :transcript_summary, :topics, :ingested_at)
        """, item)


# --- AlphaVantage ---

def is_alphavantage_item_seen(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM alphavantage_items WHERE url = ?", (url,)
        ).fetchone()
        return row is not None


def insert_alphavantage_item(item: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO alphavantage_items
                (source_name, query_type, query_value, source_type, credibility_tier,
                 url, fingerprint, title, summary, source_publisher, published_at,
                 overall_sentiment_score, overall_sentiment_label, ticker_sentiment,
                 av_topics, topics, ingested_at)
            VALUES
                (:source_name, :query_type, :query_value, :source_type, :credibility_tier,
                 :url, :fingerprint, :title, :summary, :source_publisher, :published_at,
                 :overall_sentiment_score, :overall_sentiment_label, :ticker_sentiment,
                 :av_topics, :topics, :ingested_at)
        """, item)


def get_unprocessed_alphavantage_items(limit: int = 100) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM alphavantage_items WHERE processed = 0
            ORDER BY ingested_at ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# --- Poll log ---

def log_poll(source_name: str, source_type: str, items_found: int,
             items_new: int, error: str = None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO source_poll_log
                (source_name, source_type, polled_at, items_found, items_new, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_name, source_type, datetime.utcnow().isoformat(),
              items_found, items_new, error))


# --- Digest ---

def get_last_24h_alphavantage_items() -> list:
    """Return all AV items ingested in the last 24 hours for digest generation."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM alphavantage_items
            WHERE ingested_at >= ?
            ORDER BY ingested_at DESC
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]


def insert_digest(digest: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO digests
                (date_str, html, price_sentiments, news_sentiments, narrative, generated_at)
            VALUES
                (:date_str, :html, :price_sentiments, :news_sentiments, :narrative, :generated_at)
        """, digest)


def get_latest_digest() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM digests ORDER BY generated_at DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None
