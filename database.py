"""
db/database.py — SQLite schema and all read/write operations.
Single source of truth for persistence.
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
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rss_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name     TEXT NOT NULL,
                source_type     TEXT NOT NULL,
                credibility_tier INTEGER NOT NULL,
                guid            TEXT UNIQUE NOT NULL,   -- RSS guid or link, used for dedup
                fingerprint     TEXT NOT NULL,           -- Hash of title+summary for semantic dedup
                title           TEXT,
                url             TEXT,
                summary         TEXT,
                published_at    TEXT,
                topics          TEXT,                    -- JSON list e.g. ["oil","natural_gas"]
                ingested_at     TEXT NOT NULL,
                processed       INTEGER DEFAULT 0        -- 0=new, 1=triaged
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
                topics          TEXT,                    -- JSON list
                ingested_at     TEXT NOT NULL,
                processed       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS source_poll_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name     TEXT NOT NULL,
                source_type     TEXT NOT NULL,           -- 'rss' or 'youtube'
                polled_at       TEXT NOT NULL,
                items_found     INTEGER DEFAULT 0,
                items_new       INTEGER DEFAULT 0,
                error           TEXT                     -- NULL if successful
            );

            CREATE INDEX IF NOT EXISTS idx_rss_guid        ON rss_items(guid);
            CREATE INDEX IF NOT EXISTS idx_rss_fingerprint ON rss_items(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_rss_processed   ON rss_items(processed);
            CREATE INDEX IF NOT EXISTS idx_yt_video_id     ON youtube_items(video_id);
            CREATE INDEX IF NOT EXISTS idx_yt_processed    ON youtube_items(processed);
        """)
    logger.info("Database initialized at %s", DB_PATH)


# --- RSS ---

def is_rss_item_seen(guid: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM rss_items WHERE guid = ?", (guid,)
        ).fetchone()
        return row is not None


def is_fingerprint_seen(fingerprint: str) -> bool:
    """Catch near-duplicate items with the same content but different GUIDs."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM rss_items WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
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
            SELECT * FROM rss_items
            WHERE processed = 0
            ORDER BY ingested_at ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# --- YouTube ---

def is_video_seen(video_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM youtube_items WHERE video_id = ?", (video_id,)
        ).fetchone()
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
