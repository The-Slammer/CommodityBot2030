"""
digest.py — Generates the Morning Market Breakdown.

Flow:
  1. Fetch 7-day price data for WTI, Natural Gas, URNM (uranium proxy)
  2. Calculate price sentiment per commodity
  3. Pull last 24hrs of AlphaVantage news from DB, aggregate news sentiment
  4. One LLM call (Sonnet + web_search tool) → narrative synthesis
  5. Render HTML and store in digests table
"""

import json
import logging
import os
import statistics
from datetime import datetime, timedelta, timezone

import requests
import time

from database import (
    get_last_24h_alphavantage_items,
    insert_digest,
)

try:
    from eia import get_todays_eia_data
    from sec import get_todays_sec_filings
except ImportError:
    get_todays_eia_data = lambda: []
    get_todays_sec_filings = lambda: []

logger = logging.getLogger(__name__)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AV_BASE = "https://www.alphavantage.co/query"

COMMODITIES = {
    "oil": {
        "label": "WTI Crude Oil",
        "unit": "$/bbl",
        "ticker": "WTI",
        "av_function": "WTI",
        "news_tickers": ["XOM", "CVX", "COP", "OXY", "EOG"],
        "news_topics": ["oil"],
    },
    "natural_gas": {
        "label": "Natural Gas (Henry Hub)",
        "unit": "$/MMBtu",
        "ticker": "NATGAS",
        "av_function": "NATURAL_GAS",
        "news_tickers": [],
        "news_topics": ["natural_gas"],
    },
    "uranium": {
        "label": "Uranium (URNM)",
        "unit": "$/share",
        "ticker": "URNM",
        "av_function": None,          # Use equity time series instead
        "news_tickers": ["URNM", "CCJ", "UEC", "DNN"],
        "news_topics": ["uranium", "nuclear"],
    },
}


# ---------------------------------------------------------------------------
# Price data fetching
# ---------------------------------------------------------------------------

def _fetch_commodity_price_series(av_function: str) -> list[dict]:
    """Fetch daily price series for WTI or NATURAL_GAS from AV."""
    params = {
        "function": av_function,
        "interval": "daily",
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    r = requests.get(AV_BASE, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "Note" in data or "Information" in data:
        raise RuntimeError(f"AV API limit hit for {av_function}")
    raw = data.get("data", [])
    return raw[:7]


def _fetch_equity_price_series(ticker: str) -> list[dict]:
    """Fetch daily price series for an equity (used for URNM uranium proxy)."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    r = requests.get(AV_BASE, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "Note" in data or "Information" in data:
        raise RuntimeError(f"AV API limit hit for {ticker}")
    series = data.get("Time Series (Daily)", {})
    results = []
    for date, values in sorted(series.items(), reverse=True)[:7]:
        results.append({"date": date, "value": float(values["4. close"])})
    return results


def fetch_price_data() -> dict:
    """
    Primary: read from commodity_prices DB table (populated every 30 min by commodity_prices.py).
    Fallback: live AV call if DB has no data for a symbol.
    """
    from database import get_commodity_price_series, get_latest_commodity_price

    SYMBOL_MAP = {
        "oil": "CRUDE_WTI",
        "natural_gas": "NATURAL_GAS",
        "uranium": "URNM",
    }

    prices = {}
    for key, config in COMMODITIES.items():
        symbol = SYMBOL_MAP.get(key)

        if symbol:
            series = get_commodity_price_series(symbol, days=7)
            if series:
                prices[key] = series
                try:
                    latest_ts = series[0].get("date") or ""
                    if len(latest_ts) > 10:
                        age = datetime.utcnow() - datetime.fromisoformat(latest_ts[:19])
                        if age > timedelta(hours=2):
                            logger.warning(
                                "Stale price data for %s — latest point is %dh %dm old",
                                key, int(age.seconds // 3600), int((age.seconds % 3600) // 60)
                            )
                except Exception:
                    pass
                logger.info("Price data for %s loaded from DB (%d points)", key, len(series))
                continue

        logger.warning("No DB price data for %s — falling back to live AV fetch", key)
        try:
            if config["av_function"]:
                raw = _fetch_commodity_price_series(config["av_function"])
                prices[key] = [{"date": item["date"], "value": float(item["value"])} for item in raw]
            else:
                prices[key] = _fetch_equity_price_series(config["ticker"])
            logger.info("Live AV fallback succeeded for %s (%d points)", key, len(prices[key]))
        except Exception as e:
            logger.error("Live AV fallback also failed for %s: %s", key, e)
            last = get_latest_commodity_price(symbol) if symbol else None
            if last:
                prices[key] = [{"date": last["polled_at"][:10], "value": last["price"]}]
                logger.warning("Using single last-known price for %s: %.4f", key, last["price"])
            else:
                prices[key] = []

    return prices


# ---------------------------------------------------------------------------
# Price sentiment calculation
# ---------------------------------------------------------------------------

SENTIMENT_LABELS = {
    (0.6, 1.01):   ("Strongly Bullish", "#22c55e"),
    (0.2, 0.6):    ("Bullish",          "#86efac"),
    (-0.2, 0.2):   ("Neutral",          "#94a3b8"),
    (-0.6, -0.2):  ("Bearish",          "#fca5a5"),
    (-1.01, -0.6): ("Strongly Bearish", "#ef4444"),
}


def _score_to_label(score: float) -> tuple[str, str]:
    for (low, high), (label, color) in SENTIMENT_LABELS.items():
        if low <= score < high:
            return label, color
    return "Neutral", "#94a3b8"


def calculate_price_sentiment(series: list[dict]) -> dict:
    """
    Given a daily price series (newest first), compute sentiment.
    Returns data_points count so the narrative prompt knows what it's working with.
    """
    if not series or len(series) < 2:
        return {
            "current": series[0]["value"] if series else None,
            "change_pct": None,
            "score": 0.0,
            "label": "Insufficient Data",
            "color": "#94a3b8",
            "high": series[0]["value"] if series else None,
            "low": series[0]["value"] if series else None,
            "series": series or [],
            "data_points": len(series),
        }

    values = [p["value"] for p in series]
    current = values[0]
    oldest = values[-1]
    high = max(values)
    low = min(values)
    rng = high - low if high != low else 1

    change_pct = ((current - oldest) / oldest) * 100
    position = (current - low) / rng
    trend_score = max(-1.0, min(1.0, change_pct / 10))
    position_score = (position * 2) - 1
    score = (trend_score * 0.6) + (position_score * 0.4)
    score = max(-1.0, min(1.0, score))

    label, color = _score_to_label(score)

    return {
        "current": round(current, 2),
        "change_pct": round(change_pct, 2),
        "score": round(score, 3),
        "label": label,
        "color": color,
        "high": round(high, 2),
        "low": round(low, 2),
        "series": [{"date": p["date"], "value": p["value"]} for p in series],
        "data_points": len(series),
    }


# ---------------------------------------------------------------------------
# News sentiment aggregation
# ---------------------------------------------------------------------------

def aggregate_news_sentiment(items: list[dict], commodity_config: dict) -> dict:
    """
    Filter last 24h AV items relevant to a commodity, compute weighted sentiment.
    Weights: credibility_tier_1 = 1.0, tier_2 = 0.7, tier_3 = 0.4
    Recency weight: items in last 6hrs = 1.0, 6-12hrs = 0.8, 12-24hrs = 0.6
    """
    TIER_WEIGHTS = {1: 1.0, 2: 0.7, 3: 0.4}
    now = datetime.now(timezone.utc)

    relevant = []
    for item in items:
        item_topics = json.loads(item.get("topics", "[]"))
        item_query = item.get("query_value", "")
        matches_topic = any(t in commodity_config["news_topics"] for t in item_topics)
        matches_ticker = item_query in commodity_config["news_tickers"]

        if not (matches_topic or matches_ticker):
            continue

        score = item.get("overall_sentiment_score")
        if score is None:
            continue

        try:
            published = datetime.fromisoformat(item["published_at"]).replace(tzinfo=timezone.utc)
            age_hours = (now - published).total_seconds() / 3600
        except Exception:
            age_hours = 12

        if age_hours <= 6:
            recency_w = 1.0
        elif age_hours <= 12:
            recency_w = 0.8
        else:
            recency_w = 0.6

        tier_w = TIER_WEIGHTS.get(item.get("credibility_tier", 2), 0.7)
        weight = tier_w * recency_w

        relevant.append({
            "title": item["title"],
            "score": score,
            "label": item.get("overall_sentiment_label", ""),
            "publisher": item.get("source_publisher", ""),
            "published_at": item.get("published_at", ""),
            "weight": weight,
            "url": item.get("url", ""),
        })

    if not relevant:
        return {
            "score": 0.0, "label": "No Data", "color": "#94a3b8",
            "article_count": 0, "top_headlines": []
        }

    total_weight = sum(a["weight"] for a in relevant)
    weighted_score = sum(a["score"] * a["weight"] for a in relevant) / total_weight
    weighted_score = max(-1.0, min(1.0, weighted_score))

    label, color = _score_to_label(weighted_score)

    top = sorted(relevant, key=lambda x: abs(x["score"]) * x["weight"], reverse=True)[:3]

    return {
        "score": round(weighted_score, 3),
        "label": label,
        "color": color,
        "article_count": len(relevant),
        "top_headlines": [
            {"title": a["title"], "publisher": a["publisher"],
             "label": a["label"], "url": a["url"]}
            for a in top
        ],
    }


# ---------------------------------------------------------------------------
# LLM narrative synthesis
# ---------------------------------------------------------------------------

def generate_narrative(price_sentiments: dict, news_sentiments: dict,
                        price_data: dict, eia_data: list = None,
                        sec_filings: list = None) -> str:
    """
    Sonnet LLM call with web_search tool enabled.

    Sonnet receives three explicit search tasks in priority order:
      1. Price verification — mandatory every run, corrects stale AV data
      2. Overnight macro context — dollar, Fed, China demand, OPEC
      3. Commodity-specific catalyst — conditional on sentiment divergence,
         includes geopolitical angle (disruptions, sanctions, chokepoints)

    Price context is conditionally built based on available data points to
    prevent the model from fabricating week-over-week claims it can't support.
    """
    if not ANTHROPIC_API_KEY:
        return "Narrative generation unavailable — ANTHROPIC_API_KEY not set."

    # Build per-commodity context blocks with data quality signals
    context = []
    divergence_flags = []

    for key, config in COMMODITIES.items():
        ps = price_sentiments.get(key, {})
        ns = news_sentiments.get(key, {})
        data_points = ps.get("data_points", 0)
        current = ps.get("current")
        change_pct = ps.get("change_pct")

        # Price line — only claim what the data supports
        if data_points >= 7 and change_pct is not None:
            price_line = (
                f"${current} | 7-day change: {change_pct:+.2f}% "
                f"| Price sentiment: {ps.get('label')}"
            )
        elif data_points >= 2 and change_pct is not None:
            price_line = (
                f"${current} | {data_points}-day change: {change_pct:+.2f}% "
                f"| Price sentiment: {ps.get('label')} "
                f"[NOTE: only {data_points} days of history — do not reference week-over-week]"
            )
        elif current is not None:
            price_line = (
                f"${current} | Price sentiment: {ps.get('label')} "
                f"[NOTE: single data point — report spot price only, no directional claims]"
            )
        else:
            price_line = "Price data unavailable — use web search to find current price"

        context.append(
            f"{config['label']}:\n"
            f"  Price: {price_line}\n"
            f"  News sentiment: {ns.get('label')} ({ns.get('article_count', 0)} articles)\n"
            f"  Top headlines: {'; '.join(h['title'] for h in ns.get('top_headlines', []))}"
        )

        # Flag divergences for the conditional search task
        price_score = ps.get("score", 0)
        news_score = ns.get("score", 0)
        if ns.get("article_count", 0) > 0 and abs(price_score - news_score) > 0.4:
            direction = (
                "price bearish / news bullish" if news_score > price_score
                else "price bullish / news bearish"
            )
            divergence_flags.append(f"{config['label']} ({direction})")

    divergence_note = (
        "DIVERGENCES DETECTED — run commodity-specific catalyst search for: "
        + ", ".join(divergence_flags)
        if divergence_flags
        else "No major sentiment divergences detected — skip commodity-specific catalyst search "
             "unless a headline above suggests an obvious unexplained move"
    )

    # EIA context
    eia_context = ""
    if eia_data:
        for r in eia_data:
            rtype = r.get("report_type", "").replace("_", " ").title()
            eia_context += f"\n  EIA {rtype}: {r.get('label','')} (period: {r.get('period','')})"

    # SEC context
    sec_context = ""
    if sec_filings:
        import json as _json
        for f in (sec_filings or [])[:5]:
            labels = _json.loads(f.get("item_labels", "[]"))
            label_str = ", ".join(labels) if labels else f.get("title", "")[:60]
            sec_context += f"\n  {f.get('ticker','')} {f.get('filing_type','')}: {label_str} ({f.get('filed_at','')})"

    # Geopolitical context from overnight brief
    geo_context = ""
    try:
        from database import get_latest_geopolitical_brief
        geo = get_latest_geopolitical_brief()
        if geo and geo.get("summary"):
            geo_context = geo["summary"]
            impacts = json.loads(geo.get("commodity_impacts", "{}"))
            if impacts:
                geo_context += "\n  Oil: " + impacts.get("oil", "")
                geo_context += "\n  Natural Gas: " + impacts.get("natural_gas", "")
                geo_context += "\n  Uranium: " + impacts.get("uranium", "")
    except Exception as e:
        logger.warning("Could not load geopolitical brief: %s", e)

    prompt = (
        "You are a sharp, opinionated energy markets analyst writing the Morning Market Breakdown — "
        "a no-BS morning briefing for serious energy investors.\n\n"

        "BEFORE WRITING, complete these web searches in order:\n\n"

        "SEARCH TASK 1 — PRICE VERIFICATION (mandatory, every run):\n"
        "Search current spot prices for WTI crude front month, natural gas front month, and URNM. "
        "Compare against the AV prices in the market data below. "
        "If live prices differ materially from what's below, use the live price in your narrative "
        "and note that internal data may be delayed.\n\n"

        "SEARCH TASK 2 — OVERNIGHT MACRO CONTEXT (mandatory, every run):\n"
        "Search for: US dollar index direction today, any Fed speaker commentary in the last 12 hours, "
        "China industrial demand or PMI signals, OPEC+ production news. "
        "Weave anything market-moving into the narrative — skip anything routine.\n\n"

        "SEARCH TASK 3 — COMMODITY CATALYST (conditional):\n"
        f"{divergence_note}\n"
        "For each flagged commodity, search for the specific catalyst driving the divergence. "
        "Extend the search to geopolitical developments that could explain the move: "
        "supply disruptions near production regions, new sanctions, conflict escalation, "
        "chokepoint threats (Strait of Hormuz, Red Sea, Russian pipeline flows, Kazakh export routes). "
        "Also check whether any geopolitical context from the overnight brief below has developed "
        "further overnight. Do not search for general energy news — the headlines below cover that.\n\n"

        "After completing searches, write a concise 3-paragraph narrative (150-200 words total):\n"
        "  Paragraph 1: What the price action is telling us across oil, natural gas, and uranium. "
        "Use verified live prices if they differ from the data below.\n"
        "  Paragraph 2: How news sentiment aligns or diverges from price action. "
        "Name the specific catalyst if found. Weave in geopolitical pressure that is amplifying "
        "or contradicting the move — do not list geopolitical events separately.\n"
        "  Paragraph 3: The one thing readers should be watching today and why.\n\n"

        "Style: direct, precise, no fluff. No 'Good morning'. Flowing paragraphs only, no bullets. "
        "Only reference week-over-week performance if 7-day price data is explicitly marked available below. "
        "If price history is limited, reference spot price and current direction only.\n\n"

        "MARKET DATA:\n" + "\n\n".join(context) +
        ("\n\nEIA INVENTORY DATA (released today):" + eia_context if eia_context else "") +
        ("\n\nSEC MATERIAL FILINGS (last 36h):" + sec_context if sec_context else "") +
        ("\n\nGEOPOLITICAL CONTEXT (from overnight brief):\n" + geo_context if geo_context else "")
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
                "model": "claude-sonnet-4-6",
                "max_tokens": 1500,
                "tools": [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                    }
                ],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        response_data = r.json()

        # Extract text blocks — response may contain tool_use and tool_result blocks interleaved
        text_blocks = [
            block["text"]
            for block in response_data.get("content", [])
            if block.get("type") == "text"
        ]
        narrative = "\n\n".join(text_blocks).strip()
        if not narrative:
            logger.warning("Sonnet returned no text blocks — check tool use response structure")
            return "Narrative generation produced no output — check logs."
        return narrative

    except Exception as e:
        logger.error("LLM narrative failed: %s", e)
        return "Narrative generation failed — check logs."


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_html(
    date_str: str,
    price_sentiments: dict,
    news_sentiments: dict,
    narrative: str,
    price_data: dict,
) -> str:
    """Render the full digest HTML page."""

    def sentiment_badge(label: str, color: str) -> str:
        return f'<span class="badge" style="color:{color};border-color:{color}">{label}</span>'

    def spark_data(series: list[dict]) -> str:
        if not series:
            return "[]"
        return json.dumps([p["value"] for p in reversed(series)])

    commodity_blocks = ""
    for key, config in COMMODITIES.items():
        ps = price_sentiments.get(key, {})
        ns = news_sentiments.get(key, {})
        headlines_html = ""
        for h in ns.get("top_headlines", []):
            headlines_html += f"""
            <div class="headline">
                <a href="{h['url']}" target="_blank" rel="noopener">{h['title']}</a>
                <span class="pub">{h['publisher']}</span>
            </div>"""

        change_pct = ps.get("change_pct")
        change_class = "positive" if change_pct and change_pct > 0 else "negative" if change_pct and change_pct < 0 else ""
        change_sign = "+" if change_pct and change_pct > 0 else ""
        change_display = f"{change_sign}{change_pct}% (7d)" if change_pct is not None else "—"

        commodity_blocks += f"""
        <div class="commodity-card">
            <div class="commodity-header">
                <div class="commodity-title">
                    <span class="commodity-label">{config['label']}</span>
                    <span class="commodity-unit">{config['unit']}</span>
                </div>
                <div class="commodity-price">
                    <span class="price-current">${ps.get('current', '—')}</span>
                    <span class="price-change {change_class}">{change_display}</span>
                </div>
            </div>

            <canvas class="sparkline" data-values='{spark_data(ps.get("series", []))}' width="100%" height="60"></canvas>

            <div class="sentiment-row">
                <div class="sentiment-block">
                    <div class="sentiment-label-text">PRICE SENTIMENT</div>
                    {sentiment_badge(ps.get('label', 'N/A'), ps.get('color', '#94a3b8'))}
                    <div class="sentiment-range">7d range: ${ps.get('low', '—')} – ${ps.get('high', '—')}</div>
                </div>
                <div class="sentiment-divider"></div>
                <div class="sentiment-block">
                    <div class="sentiment-label-text">NEWS SENTIMENT</div>
                    {sentiment_badge(ns.get('label', 'N/A'), ns.get('color', '#94a3b8'))}
                    <div class="sentiment-range">{ns.get('article_count', 0)} articles analyzed</div>
                </div>
            </div>

            <div class="headlines-section">
                <div class="headlines-title">KEY HEADLINES</div>
                {headlines_html if headlines_html else '<div class="headline no-headlines">No headlines in last 24h</div>'}
            </div>
        </div>"""

    narrative_html = "".join(
        f"<p>{para.strip()}</p>"
        for para in narrative.split("\n\n")
        if para.strip()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Market Breakdown — {date_str}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg:         #0a0a0a;
            --bg-card:    #111111;
            --bg-card-2:  #161616;
            --border:     #222222;
            --border-2:   #2a2a2a;
            --gold:       #c9a84c;
            --gold-dim:   #8a6f2e;
            --text:       #e8e2d6;
            --text-muted: #6b6560;
            --text-dim:   #9a9490;
            --red:        #ef4444;
            --green:      #22c55e;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 15px;
            line-height: 1.7;
            min-height: 100vh;
        }}

        header {{
            border-bottom: 1px solid var(--border);
            padding: 0 clamp(1.5rem, 5vw, 4rem);
        }}

        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.25rem 0 1rem;
            border-bottom: 1px solid var(--border);
        }}

        .header-meta {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.65rem;
            color: var(--text-muted);
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .header-ticker {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.65rem;
            color: var(--gold-dim);
            letter-spacing: 0.08em;
        }}

        .masthead {{
            padding: 2.5rem 0 2rem;
            text-align: center;
            position: relative;
        }}

        .masthead-eyebrow {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            letter-spacing: 0.3em;
            color: var(--gold);
            text-transform: uppercase;
            margin-bottom: 1rem;
        }}

        .masthead h1 {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(2.8rem, 7vw, 5.5rem);
            font-weight: 900;
            line-height: 0.95;
            letter-spacing: -0.02em;
            color: var(--text);
        }}

        .masthead h1 em {{
            font-style: italic;
            color: var(--gold);
        }}

        .masthead-sub {{
            margin-top: 1rem;
            font-family: 'Source Serif 4', serif;
            font-size: 0.875rem;
            font-weight: 300;
            font-style: italic;
            color: var(--text-muted);
            letter-spacing: 0.04em;
        }}

        .masthead-date {{
            margin-top: 1.5rem;
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.62rem;
            color: var(--text-muted);
            letter-spacing: 0.15em;
            text-transform: uppercase;
            padding: 0.35rem 1rem;
            border: 1px solid var(--border-2);
        }}

        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem clamp(1.5rem, 5vw, 4rem);
        }}

        .section-label {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: var(--gold);
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .section-label::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }}

        .analyst-note {{
            margin-bottom: 3.5rem;
            padding: 2rem 2.5rem;
            border: 1px solid var(--border);
            border-left: 3px solid var(--gold);
            background: var(--bg-card);
            position: relative;
        }}

        .analyst-note::before {{
            content: '❝';
            position: absolute;
            top: 1rem;
            right: 1.5rem;
            font-size: 3rem;
            color: var(--border-2);
            font-family: Georgia, serif;
            line-height: 1;
        }}

        .analyst-note p {{
            font-size: 0.975rem;
            color: var(--text);
            font-weight: 300;
            margin-bottom: 1rem;
        }}

        .analyst-note p:last-child {{ margin-bottom: 0; }}

        .analyst-byline {{
            margin-top: 1.25rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: var(--text-muted);
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}

        .commodity-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1.5px;
            background: var(--border);
            margin-bottom: 3.5rem;
        }}

        .commodity-card {{
            background: var(--bg-card);
            padding: 1.75rem;
            animation: fadeUp 0.5s ease both;
        }}

        .commodity-card:nth-child(2) {{ animation-delay: 0.1s; }}
        .commodity-card:nth-child(3) {{ animation-delay: 0.2s; }}

        @keyframes fadeUp {{
            from {{ opacity: 0; transform: translateY(12px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
        }}

        .commodity-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1.25rem;
        }}

        .commodity-label {{
            font-family: 'Playfair Display', serif;
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text);
            display: block;
        }}

        .commodity-unit {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: var(--text-muted);
            letter-spacing: 0.1em;
        }}

        .price-current {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 1.4rem;
            font-weight: 500;
            color: var(--text);
            display: block;
            text-align: right;
        }}

        .price-change {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.7rem;
            display: block;
            text-align: right;
            margin-top: 0.2rem;
        }}

        .price-change.positive {{ color: var(--green); }}
        .price-change.negative {{ color: var(--red); }}

        .sparkline {{
            width: 100%;
            height: 60px;
            margin: 0.75rem 0 1.25rem;
            display: block;
        }}

        .sentiment-row {{
            display: flex;
            align-items: stretch;
            gap: 0;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}

        .sentiment-block {{
            flex: 1;
            padding: 0.875rem 1rem;
        }}

        .sentiment-divider {{
            width: 1px;
            background: var(--border);
        }}

        .sentiment-label-text {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.55rem;
            letter-spacing: 0.15em;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }}

        .badge {{
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.65rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            padding: 0.2rem 0.5rem;
            border: 1px solid;
            margin-bottom: 0.35rem;
        }}

        .sentiment-range {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.58rem;
            color: var(--text-muted);
        }}

        .headlines-section {{
            border-top: 1px solid var(--border);
            padding-top: 1rem;
        }}

        .headlines-title {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.55rem;
            letter-spacing: 0.2em;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }}

        .headline {{
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border);
        }}

        .headline:last-child {{ border-bottom: none; }}

        .headline a {{
            display: block;
            color: var(--text-dim);
            text-decoration: none;
            font-size: 0.8rem;
            font-family: 'Source Serif 4', serif;
            font-weight: 300;
            line-height: 1.4;
            transition: color 0.15s;
        }}

        .headline a:hover {{ color: var(--gold); }}

        .headline .pub {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.55rem;
            color: var(--text-muted);
            margin-top: 0.2rem;
            display: block;
        }}

        .no-headlines {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.65rem;
            color: var(--text-muted);
            font-style: italic;
        }}

        footer {{
            border-top: 1px solid var(--border);
            padding: 2rem clamp(1.5rem, 5vw, 4rem);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .footer-left {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: var(--text-muted);
            letter-spacing: 0.08em;
        }}

        .footer-disclaimer {{
            font-family: 'Source Serif 4', serif;
            font-size: 0.7rem;
            font-style: italic;
            color: var(--text-muted);
            max-width: 500px;
            text-align: right;
        }}

        ::-webkit-scrollbar {{ width: 4px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border-2); }}
    </style>
</head>
<body>

<header>
    <div class="header-top">
        <span class="header-meta">Energy Intelligence Briefing</span>
        <span class="header-ticker">WTI · NATGAS · URANIUM · URNM · XOM · CVX · COP</span>
    </div>
    <div class="masthead">
        <div class="masthead-eyebrow">Morning Edition</div>
        <h1>Morning Market <em>Breakdown</em></h1>
        <div class="masthead-sub">Unfiltered energy markets intelligence for serious investors</div>
        <div class="masthead-date">{date_str} · Published 06:15 PST</div>
    </div>
</header>

<main>

    <div class="section-label">Analyst Briefing</div>
    <div class="analyst-note">
        {narrative_html}
        <div class="analyst-byline">Generated {date_str} · Based on 24h market data and news ingestion</div>
    </div>

    <div class="section-label">Market Dashboard</div>
    <div class="commodity-grid">
        {commodity_blocks}
    </div>

</main>

<footer>
    <div class="footer-left">
        MORNING MARKET BREAKDOWN<br>
        PUBLISHED DAILY AT 06:15 PST
    </div>
    <div class="footer-disclaimer">
        For informational purposes only. Not financial advice.
        All data sourced from public market feeds. Past performance is not indicative of future results.
    </div>
</footer>

<script>
document.querySelectorAll('.sparkline').forEach(canvas => {{
    const values = JSON.parse(canvas.dataset.values || '[]');
    if (!values.length) return;

    const ctx = canvas.getContext('2d');
    const W = canvas.offsetWidth || 300;
    const H = 60;
    canvas.width = W;
    canvas.height = H;

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 6;

    const x = (i) => pad + (i / (values.length - 1)) * (W - pad * 2);
    const y = (v) => H - pad - ((v - min) / range) * (H - pad * 2);

    const grad = ctx.createLinearGradient(0, 0, 0, H);
    const isUp = values[values.length - 1] >= values[0];
    const base = isUp ? 'rgba(34,197,94,' : 'rgba(239,68,68,';
    grad.addColorStop(0, base + '0.15)');
    grad.addColorStop(1, base + '0)');

    ctx.beginPath();
    ctx.moveTo(x(0), y(values[0]));
    values.forEach((v, i) => {{ if (i > 0) ctx.lineTo(x(i), y(v)); }});
    ctx.lineTo(x(values.length - 1), H);
    ctx.lineTo(x(0), H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(x(0), y(values[0]));
    values.forEach((v, i) => {{ if (i > 0) ctx.lineTo(x(i), y(v)); }});
    ctx.strokeStyle = isUp ? '#22c55e' : '#ef4444';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    const last = values.length - 1;
    ctx.beginPath();
    ctx.arc(x(last), y(values[last]), 3, 0, Math.PI * 2);
    ctx.fillStyle = isUp ? '#22c55e' : '#ef4444';
    ctx.fill();
}});
</script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def generate_digest():
    """Full digest generation pipeline. Called by the scheduler at 6:15AM PST."""
    logger.info("=== Digest generation starting ===")
    date_str = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")

    # 1. Fetch price data
    price_data = fetch_price_data()

    # 2. Calculate price sentiments
    price_sentiments = {
        key: calculate_price_sentiment(series)
        for key, series in price_data.items()
    }

    # 3. Pull last 24h news from DB
    news_items = get_last_24h_alphavantage_items()

    # 4. Aggregate news sentiment per commodity
    news_sentiments = {
        key: aggregate_news_sentiment(news_items, config)
        for key, config in COMMODITIES.items()
    }

    # 5. Fetch EIA and SEC data
    try:
        eia_data = get_todays_eia_data()
    except Exception:
        eia_data = []
    try:
        sec_filings = get_todays_sec_filings()
    except Exception:
        sec_filings = []

    # 6. LLM narrative (Sonnet + web search)
    narrative = generate_narrative(
        price_sentiments, news_sentiments, price_data,
        eia_data=eia_data, sec_filings=sec_filings
    )

    # 7. Render HTML
    html = render_html(date_str, price_sentiments, news_sentiments, narrative, price_data)

    # 8. Store in DB
    insert_digest({
        "date_str": date_str,
        "html": html,
        "price_sentiments": json.dumps(price_sentiments),
        "news_sentiments": json.dumps(news_sentiments),
        "narrative": narrative,
        "generated_at": datetime.utcnow().isoformat(),
    })

    logger.info("=== Digest generation complete for %s ===", date_str)
    return html
