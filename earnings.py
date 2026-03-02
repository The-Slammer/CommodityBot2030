"""
evening_digest.py — Daily 5:30 PM PST evening brief.

Takes the morning digest as a baseline, adds:
  - Price delta since morning open
  - Notable headlines from the day
  - Brief LLM narrative on what changed
"""

import json
import logging
import os
from datetime import datetime

import requests

from database import (
    get_latest_digest,
    get_last_24h_alphavantage_items,
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


def _fetch_current_prices() -> dict:
    prices = {}
    endpoints = {"oil": "WTI", "natural_gas": "NATURAL_GAS"}
    for key, fn in endpoints.items():
        try:
            r = requests.get(AV_BASE, params={
                "function": fn, "interval": "daily", "apikey": ALPHAVANTAGE_API_KEY
            }, timeout=15)
            data = r.json()
            latest = data.get("data", [{}])[0]
            prices[key] = float(latest.get("value", 0))
        except Exception:
            prices[key] = None
    # URNM for uranium
    try:
        r = requests.get(AV_BASE, params={
            "function": "GLOBAL_QUOTE", "symbol": "URNM", "apikey": ALPHAVANTAGE_API_KEY
        }, timeout=15)
        q = r.json().get("Global Quote", {})
        prices["uranium"] = float(q.get("05. price", 0))
    except Exception:
        prices["uranium"] = None
    return prices


def _get_todays_headlines(morning_generated_at: str) -> list:
    """Headlines ingested since the morning digest was generated."""
    from database import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT title, source_publisher, overall_sentiment_label, url
            FROM alphavantage_items
            WHERE ingested_at > ?
            ORDER BY ABS(overall_sentiment_score) DESC
            LIMIT 8
        """, (morning_generated_at,)).fetchall()
        return [dict(r) for r in rows]


def _generate_evening_narrative(morning_narrative: str, headlines: list,
                                 price_deltas: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return "Narrative unavailable."

    delta_text = "\n".join(
        f"  {k.replace('_', ' ').title()}: {'+' if v and v > 0 else ''}{v:.2f}% since morning"
        for k, v in price_deltas.items() if v is not None
    )
    headline_text = "\n".join(f"  - {h['title']} ({h['source_publisher']})" for h in headlines[:5])

    prompt = (
        "You are an energy markets analyst writing a brief end-of-day update. "
        "In 2 short paragraphs (100 words max total): summarize how today's price action "
        "compared to the morning outlook, and flag any notable headlines that moved the needle. "
        "Be direct and specific. No fluff. Don't repeat the morning narrative verbatim.\n\n"
        f"Morning outlook summary:\n{morning_narrative[:500]}\n\n"
        f"Price movement since morning:\n{delta_text}\n\n"
        f"Key headlines since morning:\n{headline_text}"
    )

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": "claude-sonnet-4-6", "max_tokens": 400,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        return r.json()["content"][0]["text"]
    except Exception as e:
        logger.error("Evening narrative failed: %s", e)
        return "Narrative generation failed."


def generate_evening_digest():
    logger.info("=== Evening digest generation starting ===")
    date_str = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
    morning = get_latest_digest()

    current_prices = _fetch_current_prices()
    headlines = _get_todays_headlines(morning["generated_at"] if morning else "")

    # Calculate price deltas vs morning
    price_deltas = {}
    if morning:
        try:
            morning_ps = json.loads(morning.get("price_sentiments", "{}"))
            for key in ["oil", "natural_gas", "uranium"]:
                morning_price = morning_ps.get(key, {}).get("current")
                current = current_prices.get(key)
                if morning_price and current and morning_price > 0:
                    price_deltas[key] = ((current - morning_price) / morning_price) * 100
                else:
                    price_deltas[key] = None
        except Exception:
            price_deltas = {k: None for k in ["oil", "natural_gas", "uranium"]}

    narrative = _generate_evening_narrative(
        morning.get("narrative", "") if morning else "",
        headlines,
        price_deltas,
    )

    narrative_html = "".join(
        f"<p>{p.strip()}</p>" for p in narrative.split("\n\n") if p.strip()
    )

    headlines_html = "".join(f"""
        <div class="headline-item">
            <a href="{h.get('url','#')}" target="_blank" rel="noopener">{h['title']}</a>
            <span class="pub">{h.get('source_publisher','')}
                <span class="sent-tag">{h.get('overall_sentiment_label','')}</span>
            </span>
        </div>""" for h in headlines)

    def delta_html(key, label, unit):
        d = price_deltas.get(key)
        p = current_prices.get(key)
        if d is None:
            return f'<div class="price-delta"><span class="label">{label}</span><span class="val">—</span></div>'
        color = "#22c55e" if d >= 0 else "#ef4444"
        sign = "+" if d >= 0 else ""
        return (f'<div class="price-delta">'
                f'<span class="label">{label}</span>'
                f'<span class="val">${p:.2f} {unit}</span>'
                f'<span class="chg" style="color:{color}">{sign}{d:.2f}% today</span>'
                f'</div>')

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
        .headline-item {{ padding:0.6rem 0; border-bottom:1px solid var(--border); }}
        .headline-item:last-child {{ border-bottom:none; }}
        .headline-item a {{ color:var(--dim); font-size:0.85rem; font-weight:300; text-decoration:none; display:block; }}
        .headline-item a:hover {{ color:var(--gold); }}
        .pub {{ font-family:'IBM Plex Mono',monospace; font-size:0.55rem; color:var(--muted); margin-top:0.2rem; display:flex; gap:0.5rem; align-items:center; }}
        .sent-tag {{ border:1px solid var(--border2); padding:0.1rem 0.35rem; color:var(--gold); font-size:0.55rem; }}
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

    <div class="section-label">Today's Key Headlines</div>
    <div>{headlines_html if headlines_html else '<p style="color:var(--muted);font-size:0.8rem">No new headlines since morning report.</p>'}</div>

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
    logger.info("=== Evening digest complete ===")
    return html
