"""
earnings.py — Earnings calendar monitoring and transcript pulling.

Flow:
  1. Daily check: fetch EARNINGS_CALENDAR for all tracked tickers
  2. Flag any ticker with earnings within 48 hours as 'earnings_watch'
  3. After market close on earnings day: poll for transcript (retry hourly)
  4. On transcript arrival: summarize via LLM, store, boost sentiment weight
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests

from database import (
    upsert_earnings_watch,
    get_earnings_watch_tickers,
    insert_earnings_transcript,
    is_transcript_stored,
)

logger = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def check_earnings_calendar(tickers: list[str]):
    """
    Fetch upcoming earnings for all tracked tickers.
    Flag any within 48 hours as earnings_watch in DB.
    Called once daily at startup of morning digest cycle.
    """
    logger.info("Checking earnings calendar for %d tickers", len(tickers))
    try:
        r = requests.get(AV_BASE, params={
            "function": "EARNINGS_CALENDAR",
            "horizon": "3month",
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()

        # AV returns CSV for this endpoint
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return

        headers = lines[0].split(",")
        now = datetime.utcnow()
        watch_window = now + timedelta(hours=48)

        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                row = dict(zip(headers, parts))
                ticker = row.get("symbol", "").strip()
                if ticker not in tickers:
                    continue
                report_date_str = row.get("reportDate", "").strip()
                if not report_date_str:
                    continue
                report_date = datetime.strptime(report_date_str, "%Y-%m-%d")
                days_until = (report_date - now).days
                in_watch = report_date <= watch_window

                upsert_earnings_watch({
                    "ticker": ticker,
                    "report_date": report_date_str,
                    "days_until": days_until,
                    "in_watch": 1 if in_watch else 0,
                    "fiscal_quarter": row.get("fiscalDateEnding", "").strip(),
                    "updated_at": now.isoformat(),
                })

                if in_watch:
                    logger.info("EARNINGS WATCH: %s reports on %s", ticker, report_date_str)
            except Exception as e:
                logger.debug("Earnings calendar parse error: %s", e)

    except Exception as e:
        logger.error("Earnings calendar fetch failed: %s", e)


def _fetch_transcript(ticker: str, fiscal_quarter: str) -> str | None:
    """Fetch earnings call transcript from AV. Returns raw text or None."""
    try:
        r = requests.get(AV_BASE, params={
            "function": "EARNINGS_CALL_TRANSCRIPT",
            "symbol": ticker,
            "quarter": fiscal_quarter,
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=30)
        r.raise_for_status()
        data = r.json()
        transcript = data.get("transcript", "")
        if transcript and len(transcript) > 500:
            return transcript
        return None
    except Exception as e:
        logger.warning("Transcript fetch failed for %s: %s", ticker, e)
        return None


def _summarize_transcript(ticker: str, transcript: str) -> tuple[str, float]:
    """
    LLM call to summarize transcript for energy investors.
    Returns (summary_text, sentiment_score -1 to 1).
    """
    if not ANTHROPIC_API_KEY:
        return "Transcript summary unavailable.", 0.0

    prompt = (
        f"You are an energy sector analyst. Summarize this {ticker} earnings call transcript "
        f"for energy investors in 3-4 sentences. Focus on: production guidance, capex plans, "
        f"commodity price assumptions, any M&A or asset sale language, and management tone. "
        f"Then on a new line output exactly: SENTIMENT_SCORE: <float between -1.0 and 1.0> "
        f"where -1 is very bearish, 0 is neutral, 1 is very bullish.\n\n"
        f"Transcript (first 4000 chars):\n{transcript[:4000]}"
    )

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]

        # Extract sentiment score
        score = 0.0
        for line in text.split("\n"):
            if "SENTIMENT_SCORE:" in line:
                try:
                    score = float(line.split(":")[1].strip())
                    score = max(-1.0, min(1.0, score))
                except Exception:
                    pass

        summary = text.replace(f"SENTIMENT_SCORE: {score}", "").strip()
        return summary, score

    except Exception as e:
        logger.error("Transcript summarization failed for %s: %s", ticker, e)
        return "Summary generation failed.", 0.0


def poll_transcripts_for_watch_list():
    """
    Check all earnings_watch tickers and attempt transcript pull.
    Called hourly after 4 PM UTC (market close). Retries until transcript arrives.
    """
    from database import get_earnings_watch_rows
    watch_rows = get_earnings_watch_rows()

    for row in watch_rows:
        ticker = row["ticker"]
        fiscal_quarter = row["fiscal_quarter"]
        report_date = row["report_date"]

        # Only attempt pull on or after report date
        try:
            rdate = datetime.strptime(report_date, "%Y-%m-%d")
            if datetime.utcnow() < rdate:
                continue
        except Exception:
            continue

        # Skip if already stored
        if is_transcript_stored(ticker, fiscal_quarter):
            logger.debug("Transcript already stored: %s %s", ticker, fiscal_quarter)
            continue

        logger.info("Attempting transcript pull: %s %s", ticker, fiscal_quarter)
        transcript = _fetch_transcript(ticker, fiscal_quarter)

        if not transcript:
            logger.info("Transcript not yet available: %s", ticker)
            continue

        summary, sentiment_score = _summarize_transcript(ticker, transcript)

        insert_earnings_transcript({
            "ticker": ticker,
            "fiscal_quarter": fiscal_quarter,
            "report_date": report_date,
            "transcript_raw": transcript[:50000],  # cap storage
            "summary": summary,
            "sentiment_score": sentiment_score,
            "generated_at": datetime.utcnow().isoformat(),
        })

        logger.info(
            "Transcript stored: %s %s — sentiment %.3f",
            ticker, fiscal_quarter, sentiment_score
        )
        time.sleep(2.0)  # AV rate limit pause between tickers
