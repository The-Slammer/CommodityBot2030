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


# ---------------------------------------------------------------------------
# New tables — added for sentiment engine, earnings, and report history
# ---------------------------------------------------------------------------

def init_new_tables():
    """Call this from init_db() to add new tables without dropping existing ones."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS equity_sentiment (
                ticker          TEXT PRIMARY KEY,
                name            TEXT,
                commodity       TEXT,
                composite_score REAL,
                news_score      REAL,
                price_score     REAL,
                transcript_score REAL,
                label           TEXT,
                color           TEXT,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS sentiment_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                commodity       TEXT NOT NULL,
                score           REAL,
                label           TEXT,
                equity_count    INTEGER,
                recorded_at     TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sh_commodity ON sentiment_history(commodity);
            CREATE INDEX IF NOT EXISTS idx_sh_recorded  ON sentiment_history(recorded_at);

            CREATE TABLE IF NOT EXISTS earnings_watch (
                ticker          TEXT PRIMARY KEY,
                report_date     TEXT,
                days_until      INTEGER,
                in_watch        INTEGER DEFAULT 0,
                fiscal_quarter  TEXT,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS earnings_transcripts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT NOT NULL,
                fiscal_quarter  TEXT NOT NULL,
                report_date     TEXT,
                transcript_raw  TEXT,
                summary         TEXT,
                sentiment_score REAL,
                generated_at    TEXT NOT NULL,
                UNIQUE(ticker, fiscal_quarter)
            );
            CREATE INDEX IF NOT EXISTS idx_et_ticker ON earnings_transcripts(ticker);

            CREATE TABLE IF NOT EXISTS evening_digests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str        TEXT NOT NULL,
                html            TEXT NOT NULL,
                narrative       TEXT,
                generated_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS weekly_digests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                week_str        TEXT NOT NULL,
                html            TEXT NOT NULL,
                narrative       TEXT,
                generated_at    TEXT NOT NULL
            );
        """)


# --- Equity sentiment ---

def upsert_equity_sentiment(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO equity_sentiment
                (ticker, name, commodity, composite_score, news_score, price_score,
                 transcript_score, label, color, updated_at)
            VALUES
                (:ticker, :name, :commodity, :composite_score, :news_score, :price_score,
                 :transcript_score, :label, :color, :updated_at)
            ON CONFLICT(ticker) DO UPDATE SET
                name=excluded.name, commodity=excluded.commodity,
                composite_score=excluded.composite_score, news_score=excluded.news_score,
                price_score=excluded.price_score, transcript_score=excluded.transcript_score,
                label=excluded.label, color=excluded.color, updated_at=excluded.updated_at
        """, data)


def get_equity_sentiment_all() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM equity_sentiment ORDER BY composite_score DESC
        """).fetchall()
        return [dict(r) for r in rows]


# --- Sentiment history ---

def insert_sentiment_history(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO sentiment_history (commodity, score, label, equity_count, recorded_at)
            VALUES (:commodity, :score, :label, :equity_count, :recorded_at)
        """, data)


def get_sentiment_history(commodity: str, days: int = 30) -> list:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM sentiment_history
            WHERE commodity = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
        """, (commodity, cutoff)).fetchall()
        return [dict(r) for r in rows]


# --- Earnings ---

def upsert_earnings_watch(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO earnings_watch
                (ticker, report_date, days_until, in_watch, fiscal_quarter, updated_at)
            VALUES
                (:ticker, :report_date, :days_until, :in_watch, :fiscal_quarter, :updated_at)
            ON CONFLICT(ticker) DO UPDATE SET
                report_date=excluded.report_date, days_until=excluded.days_until,
                in_watch=excluded.in_watch, fiscal_quarter=excluded.fiscal_quarter,
                updated_at=excluded.updated_at
        """, data)


def get_earnings_watch_tickers() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker FROM earnings_watch WHERE in_watch = 1
        """).fetchall()
        return [r[0] for r in rows]


def get_earnings_watch_rows() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM earnings_watch WHERE in_watch = 1
        """).fetchall()
        return [dict(r) for r in rows]


def insert_earnings_transcript(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO earnings_transcripts
                (ticker, fiscal_quarter, report_date, transcript_raw, summary, sentiment_score, generated_at)
            VALUES
                (:ticker, :fiscal_quarter, :report_date, :transcript_raw, :summary, :sentiment_score, :generated_at)
        """, data)


def is_transcript_stored(ticker: str, fiscal_quarter: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT 1 FROM earnings_transcripts WHERE ticker = ? AND fiscal_quarter = ?
        """, (ticker, fiscal_quarter)).fetchone()
        return row is not None


def get_latest_transcript_sentiment(ticker: str) -> tuple | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT sentiment_score, generated_at FROM earnings_transcripts
            WHERE ticker = ? ORDER BY generated_at DESC LIMIT 1
        """, (ticker,)).fetchone()
        return (row[0], row[1]) if row else None


def get_recent_transcripts(days: int = 7) -> list:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker, fiscal_quarter, report_date, summary, sentiment_score, generated_at
            FROM earnings_transcripts WHERE generated_at >= ?
            ORDER BY generated_at DESC
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]


# --- News queries ---

def get_last_n_days_av_items(ticker: str, days: int = 3) -> list:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM alphavantage_items
            WHERE query_value = ? AND ingested_at >= ?
            ORDER BY ingested_at DESC
        """, (ticker, cutoff)).fetchall()
        return [dict(r) for r in rows]


def get_last_24h_av_items_by_topic(topics: list) -> list:
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM alphavantage_items WHERE ingested_at >= ?
            ORDER BY ingested_at DESC
        """, (cutoff,)).fetchall()
        items = [dict(r) for r in rows]
        import json as _json
        return [
            i for i in items
            if any(t in _json.loads(i.get("topics", "[]")) for t in topics)
        ]


# --- Evening / weekly digests ---

def insert_evening_digest(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO evening_digests (date_str, html, narrative, generated_at)
            VALUES (:date_str, :html, :narrative, :generated_at)
        """, data)


def get_latest_evening_digest() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM evening_digests ORDER BY generated_at DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None


def insert_weekly_digest(data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO weekly_digests (week_str, html, narrative, generated_at)
            VALUES (:week_str, :html, :narrative, :generated_at)
        """, data)


def get_latest_weekly_digest() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM weekly_digests ORDER BY generated_at DESC LIMIT 1
        """).fetchone()
        return dict(row) if row else None


def get_week_digests(days: int = 7) -> list:
    """Get all morning digests from the past N days for weekly wrap."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT date_str, narrative, price_sentiments, news_sentiments, generated_at
            FROM digests WHERE generated_at >= ?
            ORDER BY generated_at ASC
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]
