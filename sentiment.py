"""
sentiment.py — Equity and commodity sentiment scoring engine.

Equity signal is a composite of:
  - News sentiment from AV items (40%)
  - Price momentum from daily time series (40%)
  - Earnings transcript sentiment, recency-decayed over 30 days (20%)

Commodity signal aggregates equity signals in that commodity bucket,
weighted by credibility tier, with exponential decay (half-life: 7 days).

Scores are stored daily in sentiment_history and equity_sentiment tables.
"""

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone

import requests

from database import (
    get_last_n_days_av_items,
    get_latest_transcript_sentiment,
    upsert_equity_sentiment,
    insert_sentiment_history,
    get_equity_sentiment_all,
)

logger = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# Signal label thresholds
SIGNAL_THRESHOLDS = [
    (0.5,  1.01,  "Strong Buy",  "#22c55e"),
    (0.15, 0.5,   "Buy",         "#86efac"),
    (-0.15, 0.15, "Neutral",     "#94a3b8"),
    (-0.5, -0.15, "Sell",        "#fca5a5"),
    (-1.01, -0.5, "Strong Sell", "#ef4444"),
]


def score_to_signal(score: float) -> tuple[str, str]:
    for low, high, label, color in SIGNAL_THRESHOLDS:
        if low <= score < high:
            return label, color
    return "Neutral", "#94a3b8"


def _fetch_price_momentum(ticker: str) -> float:
    """
    Fetch last 14 days of daily closes, return normalized momentum score -1 to 1.
    Uses: 7-day % change + position in 14-day range.
    """
    try:
        r = requests.get(AV_BASE, params={
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        series = data.get("Time Series (Daily)", {})
        closes = [float(v["4. close"]) for _, v in sorted(series.items(), reverse=True)[:14]]
        if len(closes) < 2:
            return 0.0
        current, oldest = closes[0], closes[-1]
        high, low = max(closes), min(closes)
        rng = high - low or 1
        change_pct = (current - oldest) / oldest * 100
        trend = max(-1.0, min(1.0, change_pct / 15))
        position = ((current - low) / rng) * 2 - 1
        return round(trend * 0.6 + position * 0.4, 3)
    except Exception as e:
        logger.warning("Price momentum fetch failed for %s: %s", ticker, e)
        return 0.0


def _aggregate_news_sentiment(ticker: str, days: int = 3) -> float:
    """Weighted average of AV news sentiment for ticker over last N days."""
    items = get_last_n_days_av_items(ticker, days)
    if not items:
        return 0.0
    now = datetime.now(timezone.utc)
    TIER_W = {1: 1.0, 2: 0.7, 3: 0.4}
    total_w, weighted_sum = 0.0, 0.0
    for item in items:
        score = item.get("overall_sentiment_score")
        if score is None:
            continue
        try:
            pub = datetime.fromisoformat(item["published_at"]).replace(tzinfo=timezone.utc)
            age_h = (now - pub).total_seconds() / 3600
        except Exception:
            age_h = 24
        recency_w = max(0.3, 1.0 - (age_h / 72))
        tier_w = TIER_W.get(item.get("credibility_tier", 2), 0.7)
        w = tier_w * recency_w
        weighted_sum += score * w
        total_w += w
    return round(weighted_sum / total_w, 3) if total_w > 0 else 0.0


def _transcript_boost(ticker: str) -> float:
    """
    Get most recent transcript sentiment, decayed over 30 days.
    Returns contribution score (already weighted at 20%).
    """
    result = get_latest_transcript_sentiment(ticker)
    if not result:
        return 0.0
    score, generated_at = result
    try:
        age_days = (datetime.utcnow() - datetime.fromisoformat(generated_at)).days
    except Exception:
        age_days = 30
    decay = math.exp(-age_days / 30)  # half-life ~21 days
    return round(score * decay, 3)


def calculate_equity_signal(ticker: str, credibility_tier: int = 1) -> dict:
    """Full composite signal for one equity."""
    news_score = _aggregate_news_sentiment(ticker)
    price_score = _fetch_price_momentum(ticker)
    transcript_score = _transcript_boost(ticker)

    # Weighted composite
    composite = (news_score * 0.40) + (price_score * 0.40) + (transcript_score * 0.20)
    composite = max(-1.0, min(1.0, composite))

    label, color = score_to_signal(composite)

    # 7-day trend: compare to score from 7 days ago
    trend = "→"  # default flat; updated if history exists

    return {
        "ticker": ticker,
        "composite_score": round(composite, 3),
        "news_score": news_score,
        "price_score": price_score,
        "transcript_score": transcript_score,
        "label": label,
        "color": color,
        "trend": trend,
        "calculated_at": datetime.utcnow().isoformat(),
    }


def update_all_equity_signals(sources: list[dict]):
    """
    Recalculate signal for every tracked equity and persist to DB.
    Called after each AV news poll cycle.
    """
    import time
    for source in sources:
        if source["query_type"] != "ticker":
            continue
        ticker = source["query_value"]
        try:
            signal = calculate_equity_signal(ticker, source.get("credibility_tier", 1))
            upsert_equity_sentiment({
                "ticker": ticker,
                "name": source["name"],
                "commodity": source.get("commodity", ""),
                "composite_score": signal["composite_score"],
                "news_score": signal["news_score"],
                "price_score": signal["price_score"],
                "transcript_score": signal["transcript_score"],
                "label": signal["label"],
                "color": signal["color"],
                "updated_at": signal["calculated_at"],
            })
            logger.debug("Signal updated: %s → %s (%.3f)", ticker, signal["label"], signal["composite_score"])
            time.sleep(1.0)  # AV rate limit courtesy pause
        except Exception as e:
            logger.error("Signal update failed for %s: %s", ticker, e)


def calculate_commodity_sentiment(commodity: str, sources: list[dict]) -> dict:
    """
    Aggregate equity signals for a commodity bucket into a single score.
    Uses exponential decay on stored daily history for a smoothed long-term view.
    """
    equity_signals = get_equity_sentiment_all()
    relevant = [
        s for s in equity_signals
        if s.get("commodity") == commodity
    ]
    if not relevant:
        return {"score": 0.0, "label": "No Data", "color": "#94a3b8", "equity_count": 0}

    # Weight by composite score freshness and credibility
    total_w, weighted_sum = 0.0, 0.0
    for eq in relevant:
        # Find credibility tier from sources config
        source = next((s for s in sources if s.get("query_value") == eq["ticker"]), None)
        tier_w = {1: 1.0, 2: 0.7, 3: 0.4}.get(source.get("credibility_tier", 2) if source else 2, 0.7)
        try:
            age_h = (datetime.utcnow() - datetime.fromisoformat(eq["updated_at"])).total_seconds() / 3600
        except Exception:
            age_h = 12
        recency_w = max(0.5, 1.0 - age_h / 48)
        w = tier_w * recency_w
        weighted_sum += eq["composite_score"] * w
        total_w += w

    score = round(weighted_sum / total_w, 3) if total_w > 0 else 0.0
    label, color = score_to_signal(score)

    # Store daily history
    insert_sentiment_history({
        "commodity": commodity,
        "score": score,
        "label": label,
        "equity_count": len(relevant),
        "recorded_at": datetime.utcnow().isoformat(),
    })

    return {
        "score": score,
        "label": label,
        "color": color,
        "equity_count": len(relevant),
    }


def get_top_3_watchlist(sources: list[dict]) -> list[dict]:
    """
    Rank all tracked equities by 'potential' — not just current signal,
    but momentum, news/price divergence, and earnings proximity.
    Returns top 3 with reasoning.
    """
    from database import get_earnings_watch_tickers
    earnings_watch = get_earnings_watch_tickers()
    equity_signals = get_equity_sentiment_all()

    ranked = []
    for eq in equity_signals:
        ticker = eq["ticker"]
        score = eq.get("composite_score", 0.0)
        news = eq.get("news_score", 0.0)
        price = eq.get("price_score", 0.0)

        # Divergence bonus: positive news but price hasn't moved (upside potential)
        divergence = max(0.0, news - price)

        # Earnings proximity bonus
        earnings_boost = 0.2 if ticker in earnings_watch else 0.0

        # Momentum: news score improving (proxy: news > composite)
        momentum = max(0.0, news - score)

        potential_score = score + (divergence * 0.3) + earnings_boost + (momentum * 0.2)

        # Only surface positive-leaning signals
        if score > -0.1:
            source = next((s for s in sources if s.get("query_value") == ticker), {})
            reason = _derive_reason(news, price, divergence, earnings_boost, ticker, earnings_watch)
            ranked.append({
                "ticker": ticker,
                "name": eq.get("name", ticker),
                "label": eq.get("label", "Neutral"),
                "color": eq.get("color", "#94a3b8"),
                "score": round(potential_score, 3),
                "composite_score": score,
                "reason": reason,
                "top_headline": "",  # populated by digest
            })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:3]


def _derive_reason(news: float, price: float, divergence: float,
                   earnings_boost: float, ticker: str, earnings_watch: list) -> str:
    if earnings_boost > 0:
        return f"Earnings catalyst approaching"
    if divergence > 0.25:
        return f"News sentiment ahead of price — potential upside not yet priced in"
    if news > 0.3 and price > 0.2:
        return f"Broad bullish momentum across news and price action"
    if news > 0.3:
        return f"Strong positive news flow"
    if price > 0.3:
        return f"Price momentum building"
    return f"Improving signal across multiple factors"
