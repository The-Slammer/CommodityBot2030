"""
chart_data.py — Historical price data layer for chart pages.
Fetches from AlphaVantage, caches in DB for 24 hours.
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta

from database import get_conn

logger = logging.getLogger(__name__)
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
AV_BASE = "https://www.alphavantage.co/query"

TIMEFRAMES = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}

AV_CONFIG = {
    "WTI":         {"function": "WTI",              "type": "commodity"},
    "NATURAL_GAS": {"function": "NATURAL_GAS",       "type": "commodity"},
    "GOLD":        {"function": "GOLD",              "type": "commodity"},
    "SILVER":      {"function": "SILVER",            "type": "commodity"},
    "COPPER":      {"function": "COPPER",            "type": "commodity"},
    "URNM":        {"function": "TIME_SERIES_DAILY", "type": "equity"},
}


def _get_cache(symbol):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT series, cached_at FROM chart_cache
            WHERE symbol = ? ORDER BY cached_at DESC LIMIT 1
        """, (symbol,)).fetchone()
        if not row:
            return None
        age = datetime.utcnow() - datetime.fromisoformat(row["cached_at"])
        if age > timedelta(hours=24):
            return None
        return json.loads(row["series"])


def _set_cache(symbol, series):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chart_cache (symbol, series, cached_at) VALUES (?, ?, ?)",
            (symbol, json.dumps(series), datetime.utcnow().isoformat())
        )


def _fetch_av(symbol):
    config = AV_CONFIG.get(symbol)
    if not config:
        return []
    params = {"apikey": ALPHAVANTAGE_API_KEY, "function": config["function"]}
    if config["type"] == "commodity":
        params["interval"] = "daily"
    else:
        params["symbol"] = symbol
        params["outputsize"] = "full"
    try:
        r = requests.get(AV_BASE, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.warning("AV rate limit on chart fetch for %s", symbol)
            return []
        if config["type"] == "commodity":
            return [
                {"date": p["date"], "value": float(p["value"])}
                for p in data.get("data", [])
                if p.get("value") and p["value"] != "."
            ]
        else:
            ts = data.get("Time Series (Daily)", {})
            return [
                {"date": d, "value": float(v["4. close"])}
                for d, v in sorted(ts.items(), reverse=True)
            ]
    except Exception as e:
        logger.error("AV chart fetch failed for %s: %s", symbol, e)
        return []


def get_chart_series(symbol, days):
    """Get price series for symbol over last N days. Cache-first, AV fallback."""
    series = _get_cache(symbol)
    if not series:
        series = _fetch_av(symbol)
        if series:
            _set_cache(symbol, series)
    if not series:
        return []
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    filtered = [p for p in series if p["date"] >= cutoff]
    return sorted(filtered, key=lambda x: x["date"])


def get_all_timeframes(symbol):
    """Return {1M: [...], 3M: [...], 6M: [...], 1Y: [...]} for a symbol."""
    return {label: get_chart_series(symbol, days) for label, days in TIMEFRAMES.items()}
