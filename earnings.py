"""
earnings.py — Earnings calendar monitoring and transcript pulling.

Flow:
  1. Daily check: fetch EARNINGS_CALENDAR for all tracked tickers via AV
  2. Flag any ticker with earnings within 48 hours as 'earnings_watch'
  3. After market close on earnings day: poll for transcript (retry hourly)
  4. On transcript arrival: summarize via LLM, store, boost sentiment weight

NOTE ON AV ENTITLEMENT:
  EARNINGS_CALENDAR    — available on all AV plans (CSV response)
  EARNINGS_CALL_TRANSCRIPT — requires AV premium endpoint
  If transcripts are consistently returning None, check AV plan entitlement.
  The /diag/earnings endpoint in web.py surfaces what's in the DB.
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
    Fetch upcoming earnings for all tracked tickers via AV EARNINGS_CALENDAR.
    Flag any within 48 hours as earnings_watch in DB.
    Called once daily before morning digest.

    AV returns CSV. If response is empty or malformed, logs loudly rather
    than silently returning — callers should see this in Railway logs.
    """
    logger.info("Checking earnings calendar for %d tickers", len(tickers))
    try:
        r = requests.get(AV_BASE, params={
            "function": "EARNINGS_CALENDAR",
            "horizon": "3month",
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()

        # AV rate limit or info message comes back as JSON even on CSV endpoint
        if r.headers.get("Content-Type", "").startswith("application/json"):
            data = r.json()
            note = data.get("Note") or data.get("Information") or str(data)
            logger.error("EARNINGS_CALENDAR returned JSON instead of CSV — AV limit or entitlement issue: %s", note)
            return

        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            logger.warning("EARNINGS_CALENDAR returned %d lines — may be empty or rate-limited. Raw: %s",
                           len(lines), r.text[:200])
            return

        headers = lines[0].split(",")
        now = datetime.utcnow()
        watch_window = now + timedelta(hours=48)
        matched = 0
        watch_count = 0

        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                row = dict(zip(headers, parts))
                ticker = row.get("symbol", "").strip()
                if ticker not in tickers:
                    continue
                matched += 1
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
                    watch_count += 1
                    logger.info("EARNINGS WATCH: %s reports on %s (%d days)",
                                ticker, report_date_str, days_until)

            except Exception as e:
                logger.debug("Earnings calendar parse error on line '%s': %s", line[:80], e)

        logger.info(
            "Earnings calendar complete — %d total lines, %d matched tracked tickers, %d in 48h watch",
            len(lines) - 1, matched, watch_count
        )

        if matched == 0:
            logger.warning(
                "EARNINGS_CALENDAR returned 0 matches for %d tracked tickers — "
                "verify AV key, tickers in config, and that the endpoint returned data",
                len(tickers)
            )

    except Exception as e:
        logger.error("Earnings calendar fetch failed: %s", e)


def _fetch_transcript(ticker: str, fiscal_quarter: str) -> str | None:
    """
    Fetch earnings call transcript from AV EARNINGS_CALL_TRANSCRIPT.
    Returns raw text or None.

    NOTE: This endpoint requires AV premium entitlement. If it consistently
    returns None, the plan does not include transcript access. Check /diag/av
    or contact AV support to confirm entitlement.
    """
    try:
        r = requests.get(AV_BASE, params={
            "function": "EARNINGS_CALL_TRANSCRIPT",
            "symbol": ticker,
            "quarter": fiscal_quarter,
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Check for rate limit or entitlement message
        note = data.get("Note") or data.get("Information")
        if note:
            logger.warning(
                "EARNINGS_CALL_TRANSCRIPT for %s returned API message (likely entitlement/rate limit): %s",
                ticker, note
            )
            return None

        transcript = data.get("transcript", "")
        if transcript and len(transcript) > 500:
            logger.info("Transcript fetched for %s %s (%d chars)", ticker, fiscal_quarter, len(transcript))
            return transcript

        # Log what came back so we can diagnose
        keys = list(data.keys())
        logger.warning(
            "EARNINGS_CALL_TRANSCRIPT for %s %s returned no usable transcript. "
            "Response keys: %s | transcript length: %d",
            ticker, fiscal_quarter, keys, len(transcript)
        )
        return None

    except Exception as e:
        logger.warning("Transcript fetch failed for %s %s: %s", ticker, fiscal_quarter, e)
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
    Called after market close on weekdays. Retries until transcript arrives.
    """
    from database import get_earnings_watch_rows
    watch_rows = get_earnings_watch_rows()

    if not watch_rows:
        logger.info("No tickers in earnings watch — skipping transcript poll")
        return

    logger.info("Polling transcripts for %d watch-list tickers", len(watch_rows))

    for row in watch_rows:
        ticker = row["ticker"]
        fiscal_quarter = row["fiscal_quarter"]
        report_date = row["report_date"]

        # Only attempt pull on or after report date
        try:
            rdate = datetime.strptime(report_date, "%Y-%m-%d")
            if datetime.utcnow() < rdate:
                logger.debug("Skipping %s — report date %s is in the future", ticker, report_date)
                continue
        except Exception:
            continue

        # Skip if already stored
        if is_transcript_stored(ticker, fiscal_quarter):
            logger.debug("Transcript already stored: %s %s", ticker, fiscal_quarter)
            continue

        logger.info("Attempting transcript pull: %s %s (report date: %s)",
                    ticker, fiscal_quarter, report_date)
        transcript = _fetch_transcript(ticker, fiscal_quarter)

        if not transcript:
            logger.info("Transcript not yet available for %s — will retry next window", ticker)
            continue

        summary, sentiment_score = _summarize_transcript(ticker, transcript)

        insert_earnings_transcript({
            "ticker": ticker,
            "fiscal_quarter": fiscal_quarter,
            "report_date": report_date,
            "transcript_raw": transcript[:50000],
            "summary": summary,
            "sentiment_score": sentiment_score,
            "generated_at": datetime.utcnow().isoformat(),
        })

        logger.info(
            "Transcript stored: %s %s — sentiment %.3f",
            ticker, fiscal_quarter, sentiment_score
        )
        time.sleep(2.0)  # AV rate limit pause between tickers


def get_earnings_diagnostics() -> dict:
    """
    Returns a diagnostic snapshot of earnings pipeline health.
    Called by /diag/earnings in web.py.
    """
    from database import get_earnings_watch_rows, get_recent_transcripts, get_conn
    import os as _os

    watch_rows  = get_earnings_watch_rows()
    transcripts = get_recent_transcripts(days=14)

    # Count all earnings_watch rows regardless of in_watch flag
    try:
        from database import get_conn
        with get_conn() as conn:
            all_watch = conn.execute(
                "SELECT ticker, report_date, days_until, in_watch, fiscal_quarter, updated_at "
                "FROM earnings_watch ORDER BY report_date ASC LIMIT 20"
            ).fetchall()
            all_watch = [dict(r) for r in all_watch]
    except Exception:
        all_watch = []

    return {
        "av_key_set":          bool(ALPHAVANTAGE_API_KEY),
        "anthropic_key_set":   bool(ANTHROPIC_API_KEY),
        "finnhub_key_set":     bool(os.getenv("FINNHUB_API_KEY", "")),
        "watch_list_active":   len(watch_rows),
        "all_watch_rows":      all_watch,
        "transcripts_14d":     len(transcripts),
        "recent_transcripts":  [
            {
                "ticker":          t["ticker"],
                "fiscal_quarter":  t["fiscal_quarter"],
                "report_date":     t["report_date"],
                "sentiment_score": t["sentiment_score"],
                "generated_at":    t["generated_at"],
            }
            for t in transcripts[:10]
        ],
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
