"""
scanner.py — Nightly market scanner and curated signal page.

Nightly job (02:00 UTC):
  - Fetches TIME_SERIES_DAILY for all tracked tickers in rate-limit-safe batches
  - Batch size: 15 tickers / 20s pause = ~45 calls/min (safe under 75/min limit)
  - Designed for 300 tickers: full run takes ~7 minutes at safe rate
  - Checkpoints progress so crashes resume, not restart
  - Computes:
      * 30/60/90 day performance per ticker per commodity group
      * 52-week highs and lows
      * Volatility (avg daily range % over 30d)
      * Score velocity (uses existing score_snapshots)
      * Sentiment/price divergence
      * Sentiment reversals (Bearish → Bullish flip in 48h)
  - Stores curated signals in scanner_signals table
  - Stores performance tables in scanner_performance table

Page (/scanner):
  - Top: dynamic signals (only renders flagged tickers)
  - Bottom: always-present 30/60/90 day tables grouped by commodity
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests
from flask import Blueprint, Response

from database import get_conn, get_equity_score_velocity
from config import ALPHAVANTAGE_SOURCES, BASKET_BENCHMARKS

logger = logging.getLogger(__name__)
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
AV_BASE = "https://www.alphavantage.co/query"

scanner_bp = Blueprint("scanner", __name__)

# Rate limit config — safe for 300 tickers
BATCH_SIZE      = 15    # tickers per batch
BATCH_PAUSE_SEC = 20    # seconds between batches (~45 calls/min)
CALL_PAUSE_SEC  = 1     # seconds between individual calls within a batch

# Signal thresholds
VOLATILITY_HIGH_PCT   = 4.0   # avg daily range % to flag as high volatility
DIVERGENCE_SCORE_MIN  = 0.40  # min composite score for divergence flag
DIVERGENCE_PRICE_MAX  = 1.0   # max 5d price change % to qualify as divergence
VELOCITY_MIN          = 0.20  # min 48h score delta to flag
REVERSAL_DELTA_MIN    = 0.30  # min score swing to count as sentiment reversal
HIGH_52W_THRESHOLD    = 0.97  # price within 3% of 52w high
LOW_52W_THRESHOLD     = 1.03  # price within 3% of 52w low

# Commodity group display labels
GROUP_LABELS = {
    "oil_gas":          "Energy (Oil & Gas)",
    "uranium":          "Uranium",
    "gold_miners":      "Gold Miners",
    "silver_miners":    "Silver Miners",
    "precious_metals":  "Precious Metals",   # legacy fallback
    "copper":           "Copper",
    "lithium":          "Lithium",
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_checkpoint() -> dict:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT tickers_done, started_at FROM scanner_job_checkpoint
            ORDER BY started_at DESC LIMIT 1
        """).fetchone()
        if not row:
            return {"tickers_done": [], "started_at": None}
        try:
            return {
                "tickers_done": json.loads(row["tickers_done"]),
                "started_at":   row["started_at"],
            }
        except Exception:
            return {"tickers_done": [], "started_at": None}


def _save_checkpoint(tickers_done: list, started_at: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM scanner_job_checkpoint")
        conn.execute(
            "INSERT INTO scanner_job_checkpoint (tickers_done, started_at) VALUES (?, ?)",
            (json.dumps(tickers_done), started_at)
        )


def _save_price_cache(ticker: str, series: list):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO scanner_price_cache (ticker, series, cached_at)
            VALUES (?, ?, ?)
        """, (ticker, json.dumps(series), datetime.utcnow().isoformat()))


def _get_price_cache(ticker: str) -> list:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT series, cached_at FROM scanner_price_cache
            WHERE ticker = ? ORDER BY cached_at DESC LIMIT 1
        """, (ticker,)).fetchone()
        if not row:
            return []
        # Use cache if less than 23 hours old
        age = datetime.utcnow() - datetime.fromisoformat(row["cached_at"])
        if age > timedelta(hours=23):
            return []
        try:
            return json.loads(row["series"])
        except Exception:
            return []


def _save_signal(signal: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO scanner_signals
                (ticker, commodity_group, signal_type, label, value, detail, computed_at)
            VALUES
                (:ticker, :commodity_group, :signal_type, :label, :value, :detail, :computed_at)
        """, signal)


def _clear_signals():
    with get_conn() as conn:
        conn.execute("DELETE FROM scanner_signals")


def _save_performance(record: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO scanner_performance
                (ticker, commodity_group, pct_30d, pct_60d, pct_90d,
                 price_latest, price_30d, price_60d, price_90d,
                 high_52w, low_52w, computed_at)
            VALUES
                (:ticker, :commodity_group, :pct_30d, :pct_60d, :pct_90d,
                 :price_latest, :price_30d, :price_60d, :price_90d,
                 :high_52w, :low_52w, :computed_at)
        """, record)


def _clear_performance():
    with get_conn() as conn:
        conn.execute("DELETE FROM scanner_performance")


def _get_equity_sentiment(ticker: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT composite_score, label, news_score FROM equity_sentiment
            WHERE ticker = ? LIMIT 1
        """, (ticker,)).fetchone()
        return dict(row) if row else {}


def _get_previous_sentiment_label(ticker: str) -> str:
    """Returns the label from ~48 hours ago for reversal detection."""
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    with get_conn() as conn:
        row = conn.execute("""
            SELECT label FROM score_snapshots
            WHERE ticker = ? AND recorded_at <= ?
            ORDER BY recorded_at DESC LIMIT 1
        """, (ticker, cutoff)).fetchone()
        return row["label"] if row else ""


# ---------------------------------------------------------------------------
# AV price fetch
# ---------------------------------------------------------------------------

def _fetch_daily_series(ticker: str) -> list:
    """
    Fetch full TIME_SERIES_DAILY for a ticker.
    Returns list of {date, close} dicts sorted newest-first.
    """
    try:
        r = requests.get(AV_BASE, params={
            "function":   "TIME_SERIES_DAILY",
            "symbol":     ticker,
            "outputsize": "full",
            "apikey":     ALPHAVANTAGE_API_KEY,
        }, timeout=20)
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.warning("AV rate limit on scanner fetch for %s", ticker)
            return []
        series = data.get("Time Series (Daily)", {})
        if not series:
            return []
        return [
            {"date": d, "close": float(v["4. close"])}
            for d, v in sorted(series.items(), reverse=True)
        ]
    except Exception as e:
        logger.error("Scanner AV fetch failed for %s: %s", ticker, e)
        return []


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def _price_n_days_ago(series: list, days: int) -> float | None:
    """Return closing price from approximately N trading days ago."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    candidates = [p for p in series if p["date"] <= cutoff]
    return candidates[0]["close"] if candidates else None


def _compute_volatility(series: list, days: int = 30) -> float:
    """Average daily range % over last N days. Requires OHLC — approximated from close series."""
    closes = [p["close"] for p in series[:days + 1]]
    if len(closes) < 2:
        return 0.0
    daily_ranges = [
        abs(closes[i] - closes[i + 1]) / closes[i + 1] * 100
        for i in range(len(closes) - 1)
    ]
    return round(sum(daily_ranges) / len(daily_ranges), 3) if daily_ranges else 0.0


def _compute_metrics(ticker: str, series: list, commodity_group: str, now_str: str) -> dict | None:
    """Compute all performance and signal metrics for a ticker."""
    if not series or len(series) < 5:
        return None

    latest = series[0]["close"]
    closes = [p["close"] for p in series]
    high_52w = max(closes[:252]) if len(closes) >= 252 else max(closes)
    low_52w  = min(closes[:252]) if len(closes) >= 252 else min(closes)

    p30 = _price_n_days_ago(series, 30)
    p60 = _price_n_days_ago(series, 60)
    p90 = _price_n_days_ago(series, 90)

    pct_30d = round((latest - p30) / p30 * 100, 2) if p30 else None
    pct_60d = round((latest - p60) / p60 * 100, 2) if p60 else None
    pct_90d = round((latest - p90) / p90 * 100, 2) if p90 else None

    volatility = _compute_volatility(series, days=30)

    return {
        "ticker":          ticker,
        "commodity_group": commodity_group,
        "latest":          latest,
        "pct_30d":         pct_30d,
        "pct_60d":         pct_60d,
        "pct_90d":         pct_90d,
        "price_30d":       p30,
        "price_60d":       p60,
        "price_90d":       p90,
        "high_52w":        round(high_52w, 4),
        "low_52w":         round(low_52w, 4),
        "volatility_30d":  volatility,
    }


def _emit_signals(metrics: dict, sentiment: dict, velocity: float, now_str: str):
    """Evaluate metrics and emit curated signals to scanner_signals table."""
    ticker = metrics["ticker"]
    group  = metrics["commodity_group"]
    latest = metrics["latest"]

    # 52-week high proximity
    if metrics["high_52w"] and latest >= metrics["high_52w"] * HIGH_52W_THRESHOLD:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "52w_high",
            "label": "Near 52-Week High",
            "value": round(latest / metrics["high_52w"] * 100, 1),
            "detail": f"${latest:.2f} vs 52w high ${metrics['high_52w']:.2f}",
            "computed_at": now_str,
        })

    # 52-week low proximity
    if metrics["low_52w"] and latest <= metrics["low_52w"] * LOW_52W_THRESHOLD:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "52w_low",
            "label": "Near 52-Week Low",
            "value": round(latest / metrics["low_52w"] * 100, 1),
            "detail": f"${latest:.2f} vs 52w low ${metrics['low_52w']:.2f}",
            "computed_at": now_str,
        })

    # High volatility
    if metrics["volatility_30d"] >= VOLATILITY_HIGH_PCT:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "high_volatility",
            "label": "High Volatility",
            "value": metrics["volatility_30d"],
            "detail": f"Avg daily move {metrics['volatility_30d']:.1f}% over 30 days",
            "computed_at": now_str,
        })

    # Score velocity
    if velocity >= VELOCITY_MIN:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "score_velocity",
            "label": "Sentiment Accelerating",
            "value": round(velocity, 3),
            "detail": f"Score velocity +{velocity:.3f} over 48h",
            "computed_at": now_str,
        })

    # Sentiment / price divergence
    score = sentiment.get("composite_score", 0)
    pct_5d = metrics.get("pct_30d")  # use 30d as proxy when 5d not available
    if score >= DIVERGENCE_SCORE_MIN and pct_5d is not None and pct_5d <= DIVERGENCE_PRICE_MAX:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "divergence",
            "label": "Score/Price Divergence",
            "value": round(score, 3),
            "detail": f"Score {score:.3f} ({sentiment.get('label','')}) but price {pct_5d:+.1f}% (30d)",
            "computed_at": now_str,
        })

    # Sentiment reversal
    prev_label = _get_previous_sentiment_label(ticker)
    curr_label = sentiment.get("label", "")
    bearish_labels  = {"Bearish", "Strong Sell", "Sell"}
    bullish_labels  = {"Bullish", "Strong Buy", "Buy"}
    if prev_label in bearish_labels and curr_label in bullish_labels:
        _save_signal({
            "ticker": ticker, "commodity_group": group,
            "signal_type": "reversal",
            "label": "Sentiment Reversal",
            "value": score,
            "detail": f"Flipped from {prev_label} → {curr_label} in 48h",
            "computed_at": now_str,
        })


# ---------------------------------------------------------------------------
# Main nightly job
# ---------------------------------------------------------------------------

def run_scanner_job():
    """
    Nightly scanner job. Rate-limit safe for 300+ tickers.
    Checkpoints progress — safe to restart after crash.
    """
    logger.info("=== Scanner job starting ===")
    now_str = datetime.utcnow().isoformat()

    # Build full ticker list with commodity group
    tickers = [
        {"ticker": s["query_value"], "group": s["commodity_group"]}
        for s in ALPHAVANTAGE_SOURCES
        if s.get("query_type") == "ticker" and s.get("query_value")
    ]
    # Deduplicate
    seen = set()
    unique_tickers = []
    for t in tickers:
        if t["ticker"] not in seen:
            seen.add(t["ticker"])
            unique_tickers.append(t)

    logger.info("Scanner: %d unique tickers across %d groups",
                len(unique_tickers),
                len({t["group"] for t in unique_tickers}))

    # Check checkpoint — resume from where we left off if job crashed
    checkpoint   = _get_checkpoint()
    done_today   = checkpoint.get("tickers_done", [])
    started_at   = checkpoint.get("started_at", "")
    is_today     = started_at and started_at[:10] == now_str[:10]
    already_done = set(done_today) if is_today else set()

    if already_done:
        logger.info("Resuming from checkpoint — %d tickers already done", len(already_done))

    # Clear old results at start of fresh run
    if not already_done:
        _clear_signals()
        _clear_performance()
        _save_checkpoint([], now_str)

    all_metrics     = []
    all_price_cache = {}
    completed       = list(already_done)

    # Process in batches
    remaining = [t for t in unique_tickers if t["ticker"] not in already_done]
    batches    = [remaining[i:i + BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        logger.info("Scanner batch %d/%d (%d tickers)",
                    batch_idx + 1, len(batches), len(batch))

        for entry in batch:
            ticker = entry["ticker"]
            group  = entry["group"]

            # Use cache if fresh
            series = _get_price_cache(ticker)
            if not series:
                series = _fetch_daily_series(ticker)
                if series:
                    _save_price_cache(ticker, series)
                time.sleep(CALL_PAUSE_SEC)

            if series:
                all_price_cache[ticker] = series
                metrics = _compute_metrics(ticker, series, group, now_str)
                if metrics:
                    all_metrics.append(metrics)
                    # Save performance record
                    _save_performance({
                        "ticker":          ticker,
                        "commodity_group": group,
                        "pct_30d":         metrics["pct_30d"],
                        "pct_60d":         metrics["pct_60d"],
                        "pct_90d":         metrics["pct_90d"],
                        "price_latest":    metrics["latest"],
                        "price_30d":       metrics["price_30d"],
                        "price_60d":       metrics["price_60d"],
                        "price_90d":       metrics["price_90d"],
                        "high_52w":        metrics["high_52w"],
                        "low_52w":         metrics["low_52w"],
                        "computed_at":     now_str,
                    })
                    # Compute signals
                    sentiment = _get_equity_sentiment(ticker)
                    velocity  = get_equity_score_velocity(ticker)
                    _emit_signals(metrics, sentiment, velocity, now_str)

            completed.append(ticker)

        # Checkpoint after each batch
        _save_checkpoint(completed, now_str if not is_today else started_at)

        # Pause between batches (skip after last batch)
        if batch_idx < len(batches) - 1:
            logger.info("Batch %d complete — pausing %ds for rate limit",
                        batch_idx + 1, BATCH_PAUSE_SEC)
            time.sleep(BATCH_PAUSE_SEC)

    logger.info("=== Scanner job complete — %d tickers processed, %d performance records ===",
                len(completed), len(all_metrics))

    # Basket flow — uses already-cached price data, minimal extra API calls
    try:
        run_basket_flow_job(all_price_cache)
    except Exception as e:
        logger.error("Basket flow job failed: %s", e)


# ---------------------------------------------------------------------------
# Data read helpers for page
# ---------------------------------------------------------------------------

def _get_signals() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM scanner_signals ORDER BY signal_type, commodity_group, value DESC
        """).fetchall()
        return [dict(r) for r in rows]


def _get_performance_by_group() -> dict:
    """Returns {group: [sorted performance records]} for all groups."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM scanner_performance ORDER BY commodity_group, pct_30d DESC
        """).fetchall()
    result = {}
    for row in rows:
        g = row["commodity_group"]
        if g not in result:
            result[g] = []
        result[g].append(dict(row))
    return result


def _get_computed_at() -> str:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT computed_at FROM scanner_performance
            ORDER BY computed_at DESC LIMIT 1
        """).fetchone()
        return row["computed_at"][:16].replace("T", " ") + " UTC" if row else "Not yet computed"




# ---------------------------------------------------------------------------
# Basket flow computation
# ---------------------------------------------------------------------------

def _save_basket_flow(record: dict):
    with get_conn() as conn:
        conn.execute("DELETE FROM scanner_basket_flow WHERE commodity_group = ?",
                     (record["commodity_group"],))
        conn.execute("""
            INSERT INTO scanner_basket_flow
                (commodity_group, benchmark_ticker, etf_pct_5d, etf_pct_10d, etf_pct_30d,
                 etf_direction, leaders, laggards, catchup, computed_at)
            VALUES
                (:commodity_group, :benchmark_ticker, :etf_pct_5d, :etf_pct_10d, :etf_pct_30d,
                 :etf_direction, :leaders, :laggards, :catchup, :computed_at)
        """, record)


def _get_basket_flow() -> list:
    group_order = ["oil_gas", "uranium", "gold_miners", "silver_miners", "copper", "lithium"]
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM scanner_basket_flow ORDER BY computed_at DESC
        """).fetchall()
    results = {r["commodity_group"]: dict(r) for r in rows}
    ordered = []
    for g in group_order:
        if g in results:
            ordered.append(results[g])
    for g, r in results.items():
        if g not in group_order:
            ordered.append(r)
    return ordered


def _relative_strength(stock_series: list, etf_series: list, days: int) -> float | None:
    """
    Computes (stock_pct_change - etf_pct_change) over N days.
    Positive = stock outperforming ETF. Negative = underperforming.
    """
    s_latest = stock_series[0]["close"] if stock_series else None
    e_latest = etf_series[0]["close"] if etf_series else None
    s_old = _price_n_days_ago(stock_series, days)
    e_old = _price_n_days_ago(etf_series, days)
    if not all([s_latest, e_latest, s_old, e_old]):
        return None
    s_chg = (s_latest - s_old) / s_old * 100
    e_chg = (e_latest - e_old) / e_old * 100
    return round(s_chg - e_chg, 2)


def run_basket_flow_job(all_price_cache: dict):
    """
    Compute basket flow for each commodity group.
    Called after the main scanner job so ETF price data is already cached.
    all_price_cache: {ticker: series} dict built during main scanner run.
    """
    logger.info("=== Basket flow computation ===")
    now_str = datetime.utcnow().isoformat()

    # Build ticker → group map
    ticker_group = {}
    for s in ALPHAVANTAGE_SOURCES:
        if s.get("query_type") == "ticker" and s.get("query_value"):
            ticker_group[s["query_value"]] = s["commodity_group"]

    for group, benchmark in BASKET_BENCHMARKS.items():
        # Fetch or get cached ETF series
        etf_series = all_price_cache.get(benchmark)
        if not etf_series:
            logger.info("Fetching benchmark ETF: %s for group %s", benchmark, group)
            etf_series = _fetch_daily_series(benchmark)
            if etf_series:
                _save_price_cache(benchmark, etf_series)
                all_price_cache[benchmark] = etf_series
            time.sleep(CALL_PAUSE_SEC)

        if not etf_series:
            logger.warning("No price data for benchmark %s — skipping %s", benchmark, group)
            continue

        etf_latest = etf_series[0]["close"]
        etf_p5  = _price_n_days_ago(etf_series, 5)
        etf_p10 = _price_n_days_ago(etf_series, 10)
        etf_p30 = _price_n_days_ago(etf_series, 30)
        etf_pct_5d  = round((etf_latest - etf_p5)  / etf_p5  * 100, 2) if etf_p5  else None
        etf_pct_10d = round((etf_latest - etf_p10) / etf_p10 * 100, 2) if etf_p10 else None
        etf_pct_30d = round((etf_latest - etf_p30) / etf_p30 * 100, 2) if etf_p30 else None

        # ETF direction based on 5d move
        if etf_pct_5d is None:
            etf_direction = "neutral"
        elif etf_pct_5d >= 1.5:
            etf_direction = "inflow"
        elif etf_pct_5d <= -1.5:
            etf_direction = "outflow"
        else:
            etf_direction = "neutral"

        # Compute relative strength for all stocks in this group
        rs_scores = []
        group_tickers = [t for t, g in ticker_group.items() if g == group]

        for ticker in group_tickers:
            stock_series = all_price_cache.get(ticker)
            if not stock_series:
                continue
            rs_5d  = _relative_strength(stock_series, etf_series, 5)
            rs_10d = _relative_strength(stock_series, etf_series, 10)
            rs_30d = _relative_strength(stock_series, etf_series, 30)
            stock_pct_5d = None
            if stock_series:
                s_p5 = _price_n_days_ago(stock_series, 5)
                if s_p5:
                    stock_pct_5d = round((stock_series[0]["close"] - s_p5) / s_p5 * 100, 2)

            rs_scores.append({
                "ticker":      ticker,
                "rs_5d":       rs_5d,
                "rs_10d":      rs_10d,
                "rs_30d":      rs_30d,
                "stock_pct_5d": stock_pct_5d,
                "price":       round(stock_series[0]["close"], 2),
            })

        if not rs_scores:
            continue

        # Sort by 5d relative strength
        valid = [x for x in rs_scores if x["rs_5d"] is not None]
        valid.sort(key=lambda x: x["rs_5d"], reverse=True)

        # Leaders — outperforming ETF most (top 3, positive RS only)
        leaders = [x for x in valid[:5] if x["rs_5d"] > 0][:3]

        # Laggards — underperforming most (bottom 3, negative RS)
        laggards = [x for x in reversed(valid) if x["rs_5d"] < 0][:3]

        # Catch-up candidates — ETF moving up but stock hasn't moved yet
        # High RS on 30d but low on 5d = potential catch-up
        catchup = []
        if etf_direction == "inflow":
            catchup_candidates = [
                x for x in rs_scores
                if x.get("rs_30d") is not None and x.get("rs_5d") is not None
                and x["rs_30d"] > 5        # strong over 30d
                and x["rs_5d"] < 1         # but lagging this week
                and x not in laggards
            ]
            catchup_candidates.sort(key=lambda x: x.get("rs_30d", 0), reverse=True)
            catchup = catchup_candidates[:3]

        import json as _json
        _save_basket_flow({
            "commodity_group":  group,
            "benchmark_ticker": benchmark,
            "etf_pct_5d":       etf_pct_5d,
            "etf_pct_10d":      etf_pct_10d,
            "etf_pct_30d":      etf_pct_30d,
            "etf_direction":    etf_direction,
            "leaders":          _json.dumps(leaders),
            "laggards":         _json.dumps(laggards),
            "catchup":          _json.dumps(catchup),
            "computed_at":      now_str,
        })
        logger.info("Basket flow saved: %s | ETF %s 5d: %s%% | %d leaders %d laggards %d catchup",
                    group, benchmark,
                    f"{etf_pct_5d:+.1f}" if etf_pct_5d is not None else "n/a",
                    len(leaders), len(laggards), len(catchup))

    logger.info("=== Basket flow complete ===")

# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

SIGNAL_TYPE_CONFIG = {
    "52w_high":        {"icon": "⬆",  "color": "#22c55e", "group": "Momentum"},
    "52w_low":         {"icon": "⬇",  "color": "#ef4444", "group": "Momentum"},
    "high_volatility": {"icon": "⚡", "color": "#f59e0b", "group": "Volatility"},
    "score_velocity":  {"icon": "▲",  "color": "#60a5fa", "group": "Sentiment"},
    "divergence":      {"icon": "◈",  "color": "#c9a84c", "group": "Sentiment"},
    "reversal":        {"icon": "↺",  "color": "#a78bfa", "group": "Sentiment"},
}


def _render_signal_card(sig: dict) -> str:
    cfg   = SIGNAL_TYPE_CONFIG.get(sig["signal_type"], {"icon": "•", "color": "#9a9490", "group": ""})
    color = cfg["color"]
    return (
        f'<div class="sig-card" style="border-left:2px solid {color}">'
        f'<div class="sig-header">'
        f'<span class="sig-icon" style="color:{color}">{cfg["icon"]}</span>'
        f'<span class="sig-ticker">{sig["ticker"]}</span>'
        f'<span class="sig-label" style="color:{color}">{sig["label"]}</span>'
        f'<span class="sig-group">{GROUP_LABELS.get(sig["commodity_group"], sig["commodity_group"])}</span>'
        f'</div>'
        f'<div class="sig-detail">{sig["detail"]}</div>'
        f'</div>'
    )


def _pct_cell(pct: float | None) -> str:
    if pct is None:
        return '<td class="pct-cell muted">—</td>'
    color = "#22c55e" if pct >= 0 else "#ef4444"
    sign  = "+" if pct >= 0 else ""
    arrow = "▲" if pct >= 0 else "▼"
    return f'<td class="pct-cell" style="color:{color}">{arrow} {sign}{pct:.1f}%</td>'


def _render_performance_section(group: str, records: list) -> str:
    if not records:
        return ""

    # Sort for winners/losers
    valid_30 = [r for r in records if r.get("pct_30d") is not None]
    valid_30.sort(key=lambda x: x["pct_30d"], reverse=True)

    top3    = valid_30[:3]
    bottom3 = list(reversed(valid_30[-3:])) if len(valid_30) >= 3 else []

    def rows_html(recs, highlight_color):
        html = ""
        for r in recs:
            html += (
                f'<tr>'
                f'<td class="tk-cell" style="color:{highlight_color}">{r["ticker"]}</td>'
                f'<td class="price-cell">${r["price_latest"]:.2f}</td>'
                + _pct_cell(r.get("pct_30d"))
                + _pct_cell(r.get("pct_60d"))
                + _pct_cell(r.get("pct_90d"))
                + f'<td class="muted">${r["high_52w"]:.2f} / ${r["low_52w"]:.2f}</td>'
                f'</tr>'
            )
        return html

    return f"""
<div class="perf-block">
  <h2 class="group-title">{GROUP_LABELS.get(group, group)}</h2>
  <div class="perf-tables">
    <div class="perf-half">
      <div class="perf-label winners">▲ Top Performers</div>
      <table class="perf-table">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>30D</th><th>60D</th><th>90D</th><th>52W Hi / Lo</th>
        </tr></thead>
        <tbody>{rows_html(top3, '#22c55e')}</tbody>
      </table>
    </div>
    <div class="perf-half">
      <div class="perf-label losers">▼ Laggards</div>
      <table class="perf-table">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>30D</th><th>60D</th><th>90D</th><th>52W Hi / Lo</th>
        </tr></thead>
        <tbody>{rows_html(bottom3, '#ef4444')}</tbody>
      </table>
    </div>
  </div>
</div>"""


NAV = """<style>
.cb-nav{background:#0f0f0f;border-bottom:1px solid #222;padding:0.6rem clamp(1.5rem,5vw,4rem);display:flex;gap:2rem;align-items:center;flex-wrap:wrap;position:relative;z-index:100}
.cb-nav a,.cb-nav .dd-trigger{font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;cursor:pointer}
.cb-nav .brand{font-size:0.6rem;color:#c9a84c;letter-spacing:0.15em;text-transform:uppercase}
.cb-nav .ml-auto{margin-left:auto}
.dd{position:relative;display:inline-block}
.dd-trigger{background:none;border:none;padding:0;font-family:'IBM Plex Mono',monospace}
.dd-menu{visibility:hidden;opacity:0;pointer-events:none;position:absolute;top:100%;left:0;padding-top:6px;background:transparent;min-width:160px;z-index:200;transition:opacity 0.12s ease,visibility 0.12s ease;transition-delay:0s}
.dd-menu-inner{background:#111;border:1px solid #222}
.dd-menu a{display:block;padding:0.5rem 1rem;font-family:'IBM Plex Mono',monospace;font-size:0.62rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;border-bottom:1px solid #1a1a1a}
.dd-menu a:last-child{border-bottom:none}
.dd-menu a:hover,.cb-nav a:hover,.dd-trigger:hover{color:#e8e2d6}
.dd:hover .dd-menu{visibility:visible;opacity:1;pointer-events:auto;transition-delay:0s}
.dd-menu{transition-delay:0s,200ms}
</style>
<nav class="cb-nav">
  <span class="brand">CommodityBot</span>
  <div class="dd">
    <button class="dd-trigger">Words ▾</button>
    <div class="dd-menu"><div class="dd-menu-inner">
      <a href="/">Morning Report</a>
      <a href="/evening">Evening Brief</a>
      <a href="/weekly">Weekly Wrap</a>
    </div></div>
  </div>
  <div class="dd">
    <button class="dd-trigger">Charts ▾</button>
    <div class="dd-menu"><div class="dd-menu-inner">
      <a href="/charts/energy">Energy</a>
      <a href="/charts/gold-silver">Gold / Silver</a>
      <a href="/charts/copper">Copper</a>
      <a href="/charts/uranium">Uranium</a>
    </div></div>
  </div>
  <a href="/scanner">Scanner</a>
  <a href="/portfolio">Portfolio</a>
  <a href="/about">About</a>
  <a href="/data-health" class="ml-auto">Health</a>
  <a href="/stats">Stats →</a>
</nav>"""

DEV_BANNER = """<div style="background:#0d0d0d;border-bottom:1px solid #1a1a1a;padding:0.3rem clamp(1.5rem,5vw,4rem);text-align:center">
<span style="font-family:'IBM Plex Mono',monospace;font-size:0.55rem;color:#444;letter-spacing:0.08em">
CommodityBot is under continuous development — features are regularly tuned, expanded, and added.
</span></div>"""




def _render_basket_flow_section(flows: list) -> str:
    if not flows:
        return '<div class="no-signals">Basket flow data not yet computed.</div>'

    blocks = ""
    for flow in flows:
        group     = flow["commodity_group"]
        benchmark = flow["benchmark_ticker"]
        direction = flow.get("etf_direction", "neutral")
        pct_5d    = flow.get("etf_pct_5d")
        pct_10d   = flow.get("etf_pct_10d")
        pct_30d   = flow.get("etf_pct_30d")

        # Direction badge
        dir_color = {"inflow": "#22c55e", "outflow": "#ef4444", "neutral": "#6b6560"}[direction]
        dir_label = {"inflow": "▲ INFLOW", "outflow": "▼ OUTFLOW", "neutral": "— NEUTRAL"}[direction]

        def pct_span(v):
            if v is None: return '<span class="muted">—</span>'
            color = "#22c55e" if v >= 0 else "#ef4444"
            sign  = "+" if v >= 0 else ""
            return f'<span style="color:{color}">{sign}{v:.1f}%</span>'

        etf_line = (
            f'<div class="bf-etf">'
            f'<span class="bf-benchmark">{benchmark}</span>'
            f'<span class="bf-dir" style="color:{dir_color}">{dir_label}</span>'
            f'<span class="bf-perfs">'
            f'5D: {pct_span(pct_5d)} &nbsp; 10D: {pct_span(pct_10d)} &nbsp; 30D: {pct_span(pct_30d)}'
            f'</span>'
            f'</div>'
        )

        import json as _json

        def stock_rows(items_json, label_color):
            try:
                items = _json.loads(items_json) if isinstance(items_json, str) else (items_json or [])
            except Exception:
                items = []
            if not items:
                return '<div class="bf-empty">None flagged</div>'
            rows = ""
            for item in items:
                rs = item.get("rs_5d")
                sp = item.get("stock_pct_5d")
                rs_str = f'{rs:+.1f}%' if rs is not None else "—"
                sp_str = f'{sp:+.1f}%' if sp is not None else "—"
                rs_color = "#22c55e" if (rs or 0) >= 0 else "#ef4444"
                rows += (
                    f'<div class="bf-stock-row">'
                    f'<span class="bf-stk" style="color:{label_color}">{item["ticker"]}</span>'
                    f'<span class="bf-price">${item.get("price", 0):.2f}</span>'
                    f'<span class="bf-rs" style="color:{rs_color}">RS {rs_str}</span>'
                    f'<span class="muted">own {sp_str} 5d</span>'
                    f'</div>'
                )
            return rows

        leaders_html  = stock_rows(flow.get("leaders", "[]"),  "#22c55e")
        laggards_html = stock_rows(flow.get("laggards", "[]"), "#ef4444")
        catchup_html  = stock_rows(flow.get("catchup", "[]"),  "#f59e0b")

        catchup_block = ""
        if direction == "inflow":
            catchup_block = f"""
            <div class="bf-col">
              <div class="bf-col-title" style="color:#f59e0b">↗ Catch-Up Watch</div>
              {catchup_html}
            </div>"""

        blocks += f"""
<div class="bf-block">
  <div class="bf-header">
    <span class="bf-group-name">{GROUP_LABELS.get(group, group)}</span>
    {etf_line}
  </div>
  <div class="bf-cols">
    <div class="bf-col">
      <div class="bf-col-title" style="color:#22c55e">▲ Leaders</div>
      {leaders_html}
    </div>
    <div class="bf-col">
      <div class="bf-col-title" style="color:#ef4444">▼ Laggards</div>
      {laggards_html}
    </div>
    {catchup_block}
  </div>
</div>"""

    return blocks


def _build_page(signals: list, perf_by_group: dict, computed_at: str, basket_flows: list = None) -> str:
    # Group signals by type group
    signal_groups = {}
    for sig in signals:
        cfg   = SIGNAL_TYPE_CONFIG.get(sig["signal_type"], {"group": "Other"})
        label = cfg["group"]
        if label not in signal_groups:
            signal_groups[label] = []
        signal_groups[label].append(sig)

    signals_html = ""
    if signals:
        for group_label, group_sigs in signal_groups.items():
            cards = "".join(_render_signal_card(s) for s in group_sigs)
            signals_html += f'<div class="sig-group-block"><div class="sig-group-title">{group_label}</div>{cards}</div>'
    else:
        signals_html = '<div class="no-signals">No notable signals flagged in last scan. Check back after market close.</div>'

    # Performance sections — render in consistent order
    group_order = ["oil_gas", "uranium", "precious_metals", "copper", "lithium"]
    perf_html   = ""
    for group in group_order:
        if group in perf_by_group:
            perf_html += _render_performance_section(group, perf_by_group[group])
    # Any groups not in the order list
    for group, records in perf_by_group.items():
        if group not in group_order:
            perf_html += _render_performance_section(group, records)

    if not perf_html:
        perf_html = '<div class="no-signals">Performance data not yet computed. Scanner runs nightly at 02:00 UTC.</div>'

    basket_section = _render_basket_flow_section(basket_flows or [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scanner — CommodityBot</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;min-height:100vh}}
.content{{max-width:1400px;margin:0 auto;padding:2rem clamp(1.5rem,5vw,4rem)}}
.page-header{{margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:1rem}}
.page-title{{font-family:'Playfair Display',serif;font-size:2rem;color:#e8e2d6}}
.page-title em{{color:#c9a84c;font-style:italic}}
.computed-at{{font-size:0.58rem;color:#333;letter-spacing:0.08em}}
.section-divider{{font-size:0.62rem;color:#c9a84c;letter-spacing:0.2em;text-transform:uppercase;margin:2.5rem 0 1.25rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e1e}}

/* Basket flow */
.bf-block{background:#0e0e0e;border:1px solid #1e1e1e;padding:1.25rem;margin-bottom:1px}
.bf-header{display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid #1a1a1a}
.bf-group-name{font-size:0.68rem;color:#e8e2d6;letter-spacing:0.1em;text-transform:uppercase;min-width:120px}
.bf-etf{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.bf-benchmark{font-size:0.65rem;color:#c9a84c;letter-spacing:0.1em}
.bf-dir{font-size:0.6rem;letter-spacing:0.12em;font-weight:500}
.bf-perfs{font-size:0.6rem;color:#9a9490;letter-spacing:0.05em}
.bf-cols{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem}
.bf-col{padding:0}
.bf-col-title{font-size:0.58rem;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:0.5rem}
.bf-stock-row{display:flex;align-items:center;gap:0.6rem;padding:0.3rem 0;border-bottom:1px solid #111;flex-wrap:wrap}
.bf-stock-row:last-child{border-bottom:none}
.bf-stk{font-size:0.7rem;font-weight:500;min-width:3rem}
.bf-price{font-size:0.62rem;color:#9a9490}
.bf-rs{font-size:0.62rem;font-weight:500}
.bf-empty{font-size:0.6rem;color:#333;padding:0.5rem 0;letter-spacing:0.08em}

/* Signals */
.sig-group-block{{margin-bottom:2rem}}
.sig-group-title{{font-size:0.6rem;color:#555;letter-spacing:0.2em;text-transform:uppercase;margin-bottom:0.75rem}}
.sig-card{{background:#0e0e0e;border:1px solid #1e1e1e;padding:0.85rem 1rem 0.85rem 1.25rem;margin-bottom:1px}}
.sig-header{{display:flex;align-items:center;gap:0.75rem;margin-bottom:0.3rem;flex-wrap:wrap}}
.sig-icon{{font-size:0.8rem;width:1rem;text-align:center}}
.sig-ticker{{font-size:0.78rem;color:#e8e2d6;font-weight:500;min-width:3rem}}
.sig-label{{font-size:0.65rem;letter-spacing:0.08em}}
.sig-group{{font-size:0.55rem;color:#333;letter-spacing:0.1em;text-transform:uppercase;margin-left:auto}}
.sig-detail{{font-size:0.62rem;color:#6b6560;padding-left:1.75rem;line-height:1.5}}
.no-signals{{font-size:0.65rem;color:#333;padding:2rem 0;letter-spacing:0.08em}}
/* Performance tables */
.perf-block{{margin-bottom:3rem}}
.group-title{{font-size:0.72rem;color:#c9a84c;letter-spacing:0.2em;text-transform:uppercase;margin-bottom:1.25rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e1e}}
.perf-tables{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}
.perf-label{{font-size:0.58rem;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:0.6rem;padding:0.3rem 0}}
.perf-label.winners{{color:#22c55e}}
.perf-label.losers{{color:#ef4444}}
.perf-table{{width:100%;border-collapse:collapse;font-size:0.62rem}}
.perf-table th{{color:#444;letter-spacing:0.1em;text-transform:uppercase;font-weight:400;padding:0.4rem 0.5rem;border-bottom:1px solid #1a1a1a;text-align:left}}
.perf-table td{{padding:0.5rem 0.5rem;border-bottom:1px solid #111;vertical-align:middle}}
.perf-table tr:last-child td{{border-bottom:none}}
.tk-cell{{font-size:0.72rem;font-weight:500;letter-spacing:0.05em}}
.price-cell{{color:#9a9490}}
.pct-cell{{font-size:0.68rem;letter-spacing:0.03em}}
.muted{{color:#444;font-size:0.6rem}}
.disclaimer{{margin:3rem auto 0;padding:0 clamp(1.5rem,5vw,4rem) 2rem}}
.disclaimer-inner{{padding:0.85rem 1.1rem;border:1px solid #1e1e1e;font-size:0.58rem;color:#444;line-height:1.7;letter-spacing:0.03em}}
@media(max-width:800px){{.perf-tables{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
{DEV_BANNER}
{NAV}
<div class="content">
  <div class="page-header">
    <h1 class="page-title">Market <em>Scanner</em></h1>
    <span class="computed-at">Last computed: {computed_at}</span>
  </div>

  <div class="section-divider">Basket Flow — Relative Strength vs Benchmark ETF</div>
  {basket_section}

  <div class="section-divider">Notable Signals</div>
  {signals_html}

  <div class="section-divider">30 / 60 / 90 Day Performance</div>
  {perf_html}
</div>
<div class="disclaimer">
  <div class="disclaimer-inner">
    <strong style="color:#6b6560">RESEARCH PURPOSES ONLY.</strong>
    Scanner data is computed nightly from closing prices. Not real-time.
    Nothing on this page constitutes financial advice or a trading recommendation.
    Always conduct your own due diligence before making investment decisions.
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Flask route
# ---------------------------------------------------------------------------

@scanner_bp.route("/scanner")
def scanner_page():
    signals       = _get_signals()
    perf_by_group = _get_performance_by_group()
    computed_at   = _get_computed_at()
    basket_flows  = _get_basket_flow()
    return Response(_build_page(signals, perf_by_group, computed_at, basket_flows), mimetype="text/html")
