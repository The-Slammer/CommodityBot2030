"""
evening_digest.py — Standalone end-of-day intelligence summary.
Runs at 17:30 PST daily. Fully independent — does not require a morning digest.

Structure:
  1. Intraday price movement (earliest vs latest DB price per commodity)
  2. Top 1-2 developments (Haiku scans all day's headlines for significance)
  3. Sonnet close (what it means, what to watch tomorrow)
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta

from database import (
    get_conn,
    get_av_items_since,
    get_latest_geopolitical_brief,
    insert_evening_digest,
)

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Price movement
# ---------------------------------------------------------------------------

def _get_intraday_movement() -> dict:
    """
    Compare earliest and latest stored price for each commodity today.
    Returns dict keyed by symbol with open, close, change_pct, high, low.
    """
    symbols = ["WTI", "NATURAL_GAS", "URNM", "GOLD", "SILVER", "COPPER"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = {}

    with get_conn() as conn:
        for symbol in symbols:
            rows = conn.execute("""
                SELECT price, polled_at FROM commodity_prices
                WHERE symbol = ? AND DATE(polled_at) = ?
                ORDER BY polled_at ASC
            """, (symbol, today)).fetchall()

            if not rows or len(rows) < 2:
                # Fall back to yesterday comparison if only one reading today
                yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
                prev = conn.execute("""
                    SELECT price FROM commodity_prices
                    WHERE symbol = ? AND DATE(polled_at) = ?
                    ORDER BY polled_at DESC LIMIT 1
                """, (symbol, yesterday)).fetchone()

                if rows and prev:
                    price_open = prev["price"]
                    price_close = rows[-1]["price"]
                    prices = [price_open, price_close]
                else:
                    result[symbol] = None
                    continue
            else:
                prices = [r["price"] for r in rows]
                price_open = prices[0]
                price_close = prices[-1]

            change_pct = ((price_close - price_open) / price_open) * 100
            result[symbol] = {
                "open":       round(price_open, 4),
                "close":      round(price_close, 4),
                "high":       round(max(prices), 4),
                "low":        round(min(prices), 4),
                "change_pct": round(change_pct, 3),
                "direction":  "up" if change_pct >= 0 else "down",
            }

    return result


# ---------------------------------------------------------------------------
# Haiku significance filter
# ---------------------------------------------------------------------------

def _haiku_top_developments(headlines: list) -> list:
    """
    Haiku reviews today's headlines and returns the 1-2 most significant
    developments. Significance = material impact on commodity prices,
    not volume of coverage.
    """
    if not ANTHROPIC_API_KEY or not headlines:
        return []

    text = "\n".join(
        f"  [{i+1}] {h['title']} — {h['summary'][:200]} ({h['source']})"
        for i, h in enumerate(headlines[:100])
    )

    prompt = (
        "You are an energy and commodities market analyst reviewing today's news.\n\n"
        "From the headlines and summaries below, identify the 1 or 2 most significant "
        "developments that could materially affect commodity prices — oil, natural gas, "
        "uranium, gold, silver, or copper.\n\n"
        "Significance means: OPEC decisions, sanctions, supply disruptions, major earnings "
        "surprises, geopolitical escalation, central bank moves, large M&A, regulatory "
        "rulings. Ignore routine price updates, minor analyst upgrades, and promotional content.\n\n"
        "If nothing is genuinely significant today, return an empty developments array.\n\n"
        + text +
        "\n\nRespond ONLY in this exact JSON format, no preamble:\n"
        "{\n"
        '  "developments": [\n'
        '    {\n'
        '      "headline": "your reworded one-line headline",\n'
        '      "why_it_matters": "one sentence on the commodity price implication",\n'
        '      "commodities_affected": ["oil", "natural_gas"],\n'
        '      "direction": "bullish|bearish|neutral"\n'
        '    }\n'
        "  ]\n"
        "}"
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
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        text_out = r.json()["content"][0]["text"]
        clean = text_out.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        return data.get("developments", [])
    except Exception as e:
        logger.error("Haiku development extraction failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Sonnet narrative close
# ---------------------------------------------------------------------------

def _sonnet_close(price_movement: dict, developments: list, geo_brief: dict) -> str:
    """
    Sonnet writes a 2-paragraph end-of-day close synthesizing price movement
    and key developments into actionable context for tomorrow.
    """
    if not ANTHROPIC_API_KEY:
        return ""

    # Build price context
    price_lines = []
    labels = {
        "WTI": "Crude Oil (WTI)", "NATURAL_GAS": "Natural Gas",
        "URNM": "Uranium (URNM)", "GOLD": "Gold",
        "SILVER": "Silver", "COPPER": "Copper",
    }
    for symbol, data in price_movement.items():
        if not data:
            continue
        label = labels.get(symbol, symbol)
        sign = "+" if data["change_pct"] >= 0 else ""
        price_lines.append(
            f"  {label}: ${data['close']:.2f} ({sign}{data['change_pct']:.2f}% today, "
            f"range ${data['low']:.2f}–${data['high']:.2f})"
        )

    # Build developments context
    dev_lines = []
    for d in developments:
        dev_lines.append(
            f"  - {d['headline']} [{d['direction'].upper()}] — {d['why_it_matters']}"
        )

    geo_context = ""
    if geo_brief and geo_brief.get("summary"):
        geo_context = f"\n\nGeopolitical backdrop: {geo_brief['summary']}"

    prompt = (
        "You are writing the Daily Energy Close — a sharp, no-fluff end-of-day "
        "commodity markets summary for serious investors. "
        "Write exactly 2 paragraphs, 120-160 words total.\n\n"
        "Paragraph 1: Synthesize today's price movement across commodities. "
        "Which markets moved meaningfully and why. Highlight any divergences — "
        "if oil fell while gold rose, that contrast matters.\n\n"
        "Paragraph 2: What the key development(s) mean for tomorrow and the near term. "
        "End with the single most important thing to watch. "
        "Be direct. No bullet points. No fluff. Don't start with 'Today'.\n\n"
        "PRICE MOVEMENT TODAY:\n" + "\n".join(price_lines) +
        ("\n\nKEY DEVELOPMENTS:\n" + "\n".join(dev_lines) if dev_lines else "\n\nNo major developments identified today.") +
        geo_context
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
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        logger.error("Sonnet close generation failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _render_html(date_str: str, price_movement: dict, developments: list, narrative: str) -> str:
    labels = {
        "WTI": "Crude Oil (WTI)", "NATURAL_GAS": "Natural Gas (Henry Hub)",
        "URNM": "Uranium (URNM)", "GOLD": "Gold",
        "SILVER": "Silver", "COPPER": "Copper",
    }
    units = {
        "WTI": "$/bbl", "NATURAL_GAS": "$/MMBtu",
        "URNM": "$/share", "GOLD": "$/oz",
        "SILVER": "$/oz", "COPPER": "$/lb",
    }

    # Price cards
    price_cards = ""
    for symbol, data in price_movement.items():
        label = labels.get(symbol, symbol)
        unit = units.get(symbol, "")
        if not data:
            price_cards += (
                f'<div class="price-card">'
                f'<div class="pc-label">{label}</div>'
                f'<div class="pc-price">—</div>'
                f'</div>'
            )
            continue
        color = "#22c55e" if data["direction"] == "up" else "#ef4444"
        arrow = "▲" if data["direction"] == "up" else "▼"
        sign = "+" if data["change_pct"] >= 0 else ""
        price_cards += (
            f'<div class="price-card">'
            f'<div class="pc-label">{label}</div>'
            f'<div class="pc-price">${data["close"]:.2f} <span class="pc-unit">{unit}</span></div>'
            f'<div class="pc-chg" style="color:{color}">{arrow} {sign}{data["change_pct"]:.2f}% today</div>'
            f'<div class="pc-range">Range: ${data["low"]:.2f} – ${data["high"]:.2f}</div>'
            f'</div>'
        )

    # Development cards
    dev_cards = ""
    if developments:
        for d in developments:
            dir_color = {"bullish": "#22c55e", "bearish": "#ef4444"}.get(d["direction"], "#9a9490")
            commodities = ", ".join(d.get("commodities_affected", []))
            dev_cards += (
                f'<div class="dev-card">'
                f'<div class="dev-header">'
                f'<span class="dev-headline">{d["headline"]}</span>'
                f'<span class="dev-badge" style="color:{dir_color};border-color:{dir_color}">'
                f'{d["direction"].upper()}</span>'
                f'</div>'
                f'<div class="dev-why">{d["why_it_matters"]}</div>'
                f'<div class="dev-commodities">{commodities}</div>'
                f'</div>'
            )
    else:
        dev_cards = '<div class="quiet-day">No material developments identified today.</div>'

    # Narrative paragraphs
    narrative_html = ""
    if narrative:
        for para in narrative.strip().split("\n\n"):
            if para.strip():
                narrative_html += f'<p class="narrative-para">{para.strip()}</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Daily Energy Close — {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;min-height:100vh}}
.masthead{{text-align:center;padding:3rem clamp(1.5rem,5vw,4rem) 2rem;border-bottom:1px solid #1a1a1a}}
.edition{{font-size:0.6rem;color:#c9a84c;letter-spacing:0.25em;text-transform:uppercase;margin-bottom:1rem}}
.title{{font-family:'Playfair Display',serif;font-size:clamp(2rem,6vw,3.5rem);color:#e8e2d6;line-height:1.1;margin-bottom:0.75rem}}
.title em{{color:#c9a84c;font-style:italic}}
.subtitle{{font-family:'Playfair Display',serif;font-style:italic;font-size:0.9rem;color:#6b6560;margin-bottom:1.5rem}}
.dateline{{display:inline-block;border:1px solid #2a2a2a;font-size:0.6rem;color:#6b6560;letter-spacing:0.15em;padding:0.4rem 1rem;text-transform:uppercase}}
.content{{max-width:1100px;margin:0 auto;padding:2.5rem clamp(1.5rem,5vw,4rem)}}
.section-title{{font-size:0.62rem;color:#c9a84c;letter-spacing:0.2em;text-transform:uppercase;margin-bottom:1.25rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e1e}}
.price-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1px;background:#1a1a1a;border:1px solid #1a1a1a;margin-bottom:3rem}}
.price-card{{background:#0e0e0e;padding:1.25rem 1rem}}
.pc-label{{font-size:0.58rem;color:#6b6560;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.5rem}}
.pc-price{{font-size:1.3rem;color:#e8e2d6;margin-bottom:0.25rem}}
.pc-unit{{font-size:0.55rem;color:#444}}
.pc-chg{{font-size:0.7rem;margin-bottom:0.2rem}}
.pc-range{{font-size:0.58rem;color:#444;letter-spacing:0.04em}}
.dev-card{{border:1px solid #1e1e1e;padding:1.25rem;margin-bottom:1px;background:#0e0e0e}}
.dev-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:0.6rem}}
.dev-headline{{font-size:0.75rem;color:#e8e2d6;line-height:1.5;flex:1}}
.dev-badge{{font-size:0.55rem;letter-spacing:0.1em;border:1px solid;padding:0.15rem 0.5rem;white-space:nowrap;flex-shrink:0}}
.dev-why{{font-size:0.68rem;color:#9a9490;line-height:1.6;margin-bottom:0.4rem}}
.dev-commodities{{font-size:0.58rem;color:#444;letter-spacing:0.08em;text-transform:uppercase}}
.quiet-day{{font-size:0.68rem;color:#444;padding:1.5rem 0;letter-spacing:0.08em}}
.narrative-section{{margin-top:3rem}}
.narrative-para{{font-size:0.85rem;color:#9a9490;line-height:1.9;margin-bottom:1.25rem;max-width:720px}}
.developments-section{{margin-bottom:3rem}}
@media(max-width:600px){{.price-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="masthead">
  <div class="edition">Evening Edition</div>
  <h1 class="title">Daily <em>Energy</em> Close</h1>
  <div class="subtitle">End-of-day commodity intelligence</div>
  <div class="dateline">{date_str} · Published 17:30 PST</div>
</div>
<div class="content">
  <div class="section-title">Price Movement Today</div>
  <div class="price-grid">{price_cards}</div>

  <div class="developments-section">
    <div class="section-title">Key Developments</div>
    {dev_cards}
  </div>

  <div class="narrative-section">
    <div class="section-title">The Close</div>
    {narrative_html}
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_evening_digest():
    logger.info("=== Evening digest generation starting ===")

    date_str = datetime.utcnow().strftime("%B %-d, %Y")

    # 1. Intraday price movement
    price_movement = _get_intraday_movement()
    logger.info("Price movement computed for %d symbols", len(price_movement))

    # 2. Collect today's headlines
    midnight = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
    av_items = get_av_items_since(midnight)
    headlines = []
    seen = set()
    for item in av_items:
        title = (item.get("title") or "").strip()
        if title and title not in seen:
            seen.add(title)
            headlines.append({
                "title": title,
                "summary": item.get("summary") or "",
                "source": item.get("source_publisher") or item.get("source_name") or "",
            })
    logger.info("Collected %d unique headlines for today", len(headlines))

    # 3. Haiku filters for significance
    developments = _haiku_top_developments(headlines)
    logger.info("Haiku identified %d key developments", len(developments))

    # 4. Load geopolitical brief
    geo_brief = {}
    try:
        geo_brief = get_latest_geopolitical_brief() or {}
    except Exception as e:
        logger.warning("Could not load geo brief: %s", e)

    # 5. Sonnet close
    narrative = _sonnet_close(price_movement, developments, geo_brief)
    logger.info("Sonnet close generated (%d chars)", len(narrative))

    # 6. Render and save
    html = _render_html(date_str, price_movement, developments, narrative)
    save_evening_digest({
        "date_str": date_str,
        "html": html,
        "generated_at": datetime.utcnow().isoformat(),
    })

    logger.info("=== Evening digest complete ===")
