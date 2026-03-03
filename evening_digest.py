"""
evening_digest.py — Daily 5:30 PM PST evening brief.

Two-stage intelligence pipeline:
  Stage 1 (Haiku) — scores all news since morning, decides what is materially
                     significant enough to surface. Looks for: earnings surprises,
                     guidance changes, M&A, production updates, regulatory events,
                     analyst rating changes, or anything that would shift a company's
                     buy/sell score.
  Stage 2 (Sonnet) — receives price deltas, Haiku's filtered company developments,
                     and the morning narrative. Writes the evening brief narrative
                     and synthesizes cross-company themes if present.
"""

import json
import logging
import os
from datetime import datetime

import requests

from database import (
    get_latest_digest,
    get_av_items_since,
    insert_evening_digest,
)

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
AV_BASE = "https://www.alphavantage.co/query"

DISCLAIMER = """
<div class="disclaimer">
    <strong>Research purposes only.</strong> CommodityBot is an automated research tool.
    Nothing published here constitutes financial advice, a solicitation, or a recommendation
    to buy or sell any security or commodity. Always consult a licensed financial advisor
    before making investment decisions. Past performance is not indicative of future results.
</div>"""


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def _fetch_current_prices() -> dict:
    import time
    prices = {}
    endpoints = {"oil": "WTI", "natural_gas": "NATURAL_GAS"}
    for key, fn in endpoints.items():
        try:
            r = requests.get(AV_BASE, params={
                "function": fn, "interval": "daily", "apikey": ALPHAVANTAGE_API_KEY
            }, timeout=15)
            data = r.json()
            latest = data.get("data", [{}])[0]
            prices[key] = float(latest.get("value", 0)) or None
        except Exception:
            prices[key] = None
        time.sleep(12)
    try:
        r = requests.get(AV_BASE, params={
            "function": "GLOBAL_QUOTE", "symbol": "URNM", "apikey": ALPHAVANTAGE_API_KEY
        }, timeout=15)
        q = r.json().get("Global Quote", {})
        prices["uranium"] = float(q.get("05. price", 0)) or None
    except Exception:
        prices["uranium"] = None
    return prices


# ---------------------------------------------------------------------------
# Stage 1 — Haiku: score and filter news since morning
# ---------------------------------------------------------------------------

def _group_news_by_ticker(items: list) -> dict:
    """Group AV items by their query_value (ticker), keep top 3 per ticker by sentiment magnitude."""
    grouped = {}
    for item in items:
        ticker = item.get("query_value", "UNKNOWN")
        if ticker not in grouped:
            grouped[ticker] = []
        grouped[ticker].append(item)
    # Sort each ticker's news by abs sentiment, keep top 3
    for ticker in grouped:
        grouped[ticker] = sorted(
            grouped[ticker],
            key=lambda x: abs(x.get("overall_sentiment_score") or 0),
            reverse=True
        )[:3]
    return grouped


def _haiku_score_company_news(ticker: str, news_items: list) -> dict | None:
    """
    Haiku evaluates a single company's news batch and decides if anything
    is materially significant — i.e. would change the buy/sell outlook.
    Returns a dict with: ticker, material (bool), signal_impact (bullish/bearish/neutral),
    headline (best headline), summary (1 sentence), or None on failure.
    """
    if not ANTHROPIC_API_KEY or not news_items:
        return None

    news_text = "\n".join(
        f"  - [{item.get('overall_sentiment_label','?')}] {item.get('title','')} "
        f"({item.get('source_publisher','')})"
        for item in news_items
    )

    prompt = f"""You are evaluating news for {ticker} to decide if anything is materially significant for energy investors.

NEWS ITEMS:
{news_text}

TASK:
Decide if any of these stories represent a material development — something that would meaningfully shift the buy/sell outlook for {ticker}. Material events include: earnings surprises, guidance changes, production updates, M&A activity, analyst rating changes, regulatory decisions, contract wins/losses, management changes, or significant operational events.

Routine press releases, minor partnerships, and generic sector commentary are NOT material.

Respond ONLY in this exact JSON format, no other text:
{{
  "material": true,
  "signal_impact": "bullish",
  "headline": "The single most important headline in your own words",
  "summary": "One sentence explaining why this matters for the stock."
}}

If nothing is material, respond:
{{
  "material": false,
  "signal_impact": "neutral",
  "headline": "",
  "summary": ""
}}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
        clean = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        if parsed.get("material"):
            parsed["ticker"] = ticker
            return parsed
        return None
    except Exception as e:
        logger.warning("Haiku news scoring failed for %s: %s", ticker, e)
        return None


def _score_all_company_news(since_timestamp: str) -> list:
    """
    Pull all news since morning, group by ticker, run Haiku on each group.
    Returns list of material developments sorted by impact.
    """
    import time
    items = get_av_items_since(since_timestamp)
    if not items:
        logger.info("No new AV items since morning")
        return []

    grouped = _group_news_by_ticker(items)
    logger.info("Scoring company news — %d tickers with new items since morning", len(grouped))

    material = []
    for i, (ticker, news) in enumerate(grouped.items()):
        if i > 0:
            time.sleep(2)  # pace Haiku calls
        result = _haiku_score_company_news(ticker, news)
        if result:
            material.append(result)
            logger.info("Material development — %s: %s", ticker, result.get("signal_impact"))

    # Sort: bearish first (most actionable), then bullish, then neutral
    order = {"bearish": 0, "bullish": 1, "neutral": 2}
    material.sort(key=lambda x: order.get(x.get("signal_impact", "neutral"), 2))
    return material


# ---------------------------------------------------------------------------
# Stage 2 — Sonnet: write the evening narrative
# ---------------------------------------------------------------------------

def _generate_evening_narrative(morning_narrative: str, price_deltas: dict,
                                  developments: list) -> str:
    if not ANTHROPIC_API_KEY:
        return "Narrative unavailable."

    delta_text = "\n".join(
        f"  {k.replace('_', ' ').title()}: {'+' if v and v > 0 else ''}{v:.2f}% since morning"
        for k, v in price_deltas.items() if v is not None
    ) or "  Price delta data unavailable."

    if developments:
        dev_text = "\n".join(
            f"  {d['ticker']} [{d['signal_impact'].upper()}]: {d['headline']} — {d['summary']}"
            for d in developments
        )
    else:
        dev_text = "  No material company-level developments identified today."

    prompt = (
        "You are an energy markets analyst writing a concise end-of-day brief for serious investors. "
        "Write 2-3 paragraphs (150 words max total):\n"
        "1. How today's price action played out vs the morning outlook — be specific about moves\n"
        "2. Company-level developments that matter — focus only on what Haiku flagged as material, "
        "explain the significance briefly. If nothing material, say so in one line and move on.\n"
        "3. One forward-looking sentence: what does today set up for tomorrow.\n\n"
        "Be direct. No fluff. Don't repeat headlines verbatim — synthesize them.\n\n"
        f"Morning outlook:\n{morning_narrative[:600]}\n\n"
        f"Price movement today:\n{delta_text}\n\n"
        f"Material company developments (Haiku-filtered):\n{dev_text}"
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
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        logger.error("Evening narrative failed: %s", e)
        return "Narrative generation failed."


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

def _impact_color(impact: str) -> str:
    return {"bullish": "#22c55e", "bearish": "#ef4444"}.get(impact, "#94a3b8")


def _impact_label(impact: str) -> str:
    return {"bullish": "BULLISH", "bearish": "BEARISH"}.get(impact, "NEUTRAL")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def generate_evening_digest():
    logger.info("=== Evening digest generation starting ===")
    date_str = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
    morning = get_latest_digest()
    morning_generated_at = morning["generated_at"] if morning else ""

    # Fetch prices
    current_prices = _fetch_current_prices()

    # Calculate price deltas vs morning
    price_deltas = {}
    if morning:
        try:
            morning_ps = json.loads(morning.get("price_sentiments", "{}"))
            for key in ["oil", "natural_gas", "uranium"]:
                morning_price = morning_ps.get(key, {}).get("current")
                current = current_prices.get(key)
                if morning_price and current and morning_price > 0:
                    price_deltas[key] = round(((current - morning_price) / morning_price) * 100, 2)
                else:
                    price_deltas[key] = None
        except Exception:
            price_deltas = {k: None for k in ["oil", "natural_gas", "uranium"]}

    # Stage 1: Haiku scores company news
    developments = _score_all_company_news(morning_generated_at)
    logger.info("Haiku identified %d material developments", len(developments))

    # Stage 2: Sonnet writes narrative
    narrative = _generate_evening_narrative(
        morning.get("narrative", "") if morning else "",
        price_deltas,
        developments,
    )

    # --- HTML ---
    narrative_html = "".join(
        f"<p>{p.strip()}</p>" for p in narrative.split("\n\n") if p.strip()
    )

    def delta_html(key, label, unit):
        d = price_deltas.get(key)
        p = current_prices.get(key)
        if p is None:
            return (f'<div class="price-delta">'
                    f'<span class="label">{label}</span>'
                    f'<span class="val">—</span></div>')
        if d is None:
            # Have current price but no morning baseline — show price without delta
            return (f'<div class="price-delta">'
                    f'<span class="label">{label}</span>'
                    f'<span class="val">${p:.2f} {unit}</span>'
                    f'<span class="chg" style="color:#6b6560">delta unavailable</span>'
                    f'</div>')
        color = "#22c55e" if d >= 0 else "#ef4444"
        sign = "+" if d >= 0 else ""
        return (f'<div class="price-delta">'
                f'<span class="label">{label}</span>'
                f'<span class="val">${p:.2f} {unit}</span>'
                f'<span class="chg" style="color:{color}">{sign}{d:.2f}% today</span>'
                f'</div>')

    if developments:
        dev_cards = "".join(f"""
        <div class="dev-card">
            <div class="dev-header">
                <span class="dev-ticker">{d['ticker']}</span>
                <span class="dev-tag" style="border-color:{_impact_color(d['signal_impact'])};color:{_impact_color(d['signal_impact'])}">{_impact_label(d['signal_impact'])}</span>
            </div>
            <div class="dev-headline">{d['headline']}</div>
            <div class="dev-summary">{d['summary']}</div>
        </div>""" for d in developments)
    else:
        dev_cards = '<p style="color:var(--muted);font-size:0.8rem;font-style:italic">No material company-level developments identified today.</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evening Brief — {date_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;1,8..60,300&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg:#0a0a0a; --card:#111; --border:#222; --border2:#2a2a2a;
            --gold:#c9a84c; --text:#e8e2d6; --muted:#6b6560; --dim:#9a9490;
        }}
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ background:var(--bg); color:var(--text); font-family:'Source Serif 4',serif; font-size:15px; line-height:1.7; }}
        header {{ border-bottom:1px solid var(--border); padding:0 clamp(1.5rem,5vw,4rem); }}
        .masthead {{ padding:2rem 0 1.5rem; text-align:center; }}
        .eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.3em; color:var(--gold); text-transform:uppercase; margin-bottom:0.75rem; }}
        h1 {{ font-family:'Playfair Display',serif; font-size:clamp(2rem,5vw,3.5rem); font-weight:900; line-height:1; }}
        h1 em {{ font-style:italic; color:var(--gold); }}
        .sub {{ margin-top:0.75rem; font-size:0.8rem; font-style:italic; color:var(--muted); }}
        .datestamp {{ display:inline-block; margin-top:1rem; font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); letter-spacing:0.15em; text-transform:uppercase; padding:0.3rem 0.75rem; border:1px solid var(--border2); }}
        main {{ max-width:900px; margin:0 auto; padding:2.5rem clamp(1.5rem,5vw,4rem); }}
        .section-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.25em; text-transform:uppercase; color:var(--gold); margin-bottom:1rem; display:flex; align-items:center; gap:0.75rem; }}
        .section-label::after {{ content:''; flex:1; height:1px; background:var(--border); }}
        .prices {{ display:flex; gap:1px; background:var(--border); margin-bottom:2.5rem; }}
        .price-delta {{ flex:1; background:var(--card); padding:1rem 1.25rem; }}
        .price-delta .label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); letter-spacing:0.1em; text-transform:uppercase; display:block; margin-bottom:0.35rem; }}
        .price-delta .val {{ font-family:'IBM Plex Mono',monospace; font-size:1.1rem; display:block; }}
        .price-delta .chg {{ font-family:'IBM Plex Mono',monospace; font-size:0.7rem; display:block; margin-top:0.2rem; }}
        .brief {{ border:1px solid var(--border); border-left:3px solid var(--gold); background:var(--card); padding:1.75rem 2rem; margin-bottom:2.5rem; }}
        .brief p {{ font-size:0.95rem; font-weight:300; margin-bottom:0.75rem; }}
        .brief p:last-child {{ margin-bottom:0; }}
        .dev-card {{ background:var(--card); border:1px solid var(--border); padding:1rem 1.25rem; margin-bottom:0.75rem; }}
        .dev-header {{ display:flex; align-items:center; gap:0.75rem; margin-bottom:0.4rem; }}
        .dev-ticker {{ font-family:'IBM Plex Mono',monospace; font-size:0.8rem; color:var(--text); font-weight:500; }}
        .dev-tag {{ font-family:'IBM Plex Mono',monospace; font-size:0.55rem; letter-spacing:0.08em; padding:0.15rem 0.5rem; border:1px solid; }}
        .dev-headline {{ font-size:0.88rem; font-weight:300; color:var(--text); margin-bottom:0.3rem; }}
        .dev-summary {{ font-family:'IBM Plex Mono',monospace; font-size:0.62rem; color:var(--dim); line-height:1.5; }}
        .disclaimer {{ margin-top:2.5rem; padding:1rem 1.25rem; border:1px solid var(--border2); font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); line-height:1.6; letter-spacing:0.03em; }}
        .disclaimer strong {{ color:var(--dim); }}
        footer {{ border-top:1px solid var(--border); padding:1.5rem clamp(1.5rem,5vw,4rem); display:flex; justify-content:space-between; flex-wrap:wrap; gap:1rem; }}
        .footer-l {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); }}
        a.back {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--gold); text-decoration:none; }}
    </style>
</head>
<body>
<header>
    <div class="masthead">
        <div class="eyebrow">Evening Brief</div>
        <h1>Daily <em>Energy</em> Close</h1>
        <div class="sub">End-of-day update · CommodityBot Research</div>
        <div class="datestamp">{date_str} · Published 17:30 PST</div>
    </div>
</header>
<main>
    <div class="section-label">Price Movement Today</div>
    <div class="prices">
        {delta_html('oil', 'Crude Oil WTI', '$/bbl')}
        {delta_html('natural_gas', 'Natural Gas', '$/MMBtu')}
        {delta_html('uranium', 'Uranium (URNM)', '$/share')}
    </div>

    <div class="section-label">Evening Analysis</div>
    <div class="brief">{narrative_html}</div>

    <div class="section-label">Company Developments</div>
    <div class="developments">{dev_cards}</div>

    {DISCLAIMER}
</main>
<footer>
    <div class="footer-l">THE DAILY ENERGY JERKOFF · EVENING BRIEF<br>PUBLISHED DAILY AT 17:30 PST</div>
    <a class="back" href="/">← Morning Report</a>
</footer>
</body>
</html>"""

    insert_evening_digest({
        "date_str": date_str,
        "html": html,
        "narrative": narrative,
        "generated_at": datetime.utcnow().isoformat(),
    })
    logger.info("=== Evening digest complete — %d material developments surfaced ===", len(developments))
    return html
