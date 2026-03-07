"""
weekly_digest.py — Friday 5:30 PM PST weekly wrap.

Synthesizes the week's morning digests, surfaces dominant themes,
price trends, and a forward-looking "watch next week" section.

Narrative uses Sonnet + web search to verify prices and surface any
week-end developments not captured in the daily pipeline.
"""

import json
import logging
import os
from datetime import datetime, timedelta

import requests

from database import (
    get_week_digests,
    get_recent_transcripts,
    insert_weekly_digest,
    get_commodity_price_series,
    get_latest_commodity_price,
)

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

DISCLAIMER = """
<div class="disclaimer">
    <strong>Research purposes only.</strong> CommodityBot is an automated research tool.
    Nothing published here constitutes financial advice, a solicitation, or a recommendation
    to buy or sell any security or commodity. Always consult a licensed financial advisor
    before making investment decisions. Past performance is not indicative of future results.
</div>"""

# DB symbol map for price lookups
PRICE_SYMBOLS = {
    "WTI Crude Oil":       "CRUDE_WTI",
    "Natural Gas":         "NATURAL_GAS",
    "Uranium (URNM)":      "URNM",
    "Gold":                "GOLD",
    "Silver":              "SILVER",
    "Copper":              "COPPER",
}


def _get_upcoming_earnings(tickers: list[str]) -> list[dict]:
    """Fetch next week's earnings dates from Finnhub if key available."""
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set — upcoming earnings will be empty")
        return []
    try:
        from_date = datetime.utcnow().strftime("%Y-%m-%d")
        to_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": from_date, "to": to_date, "token": FINNHUB_API_KEY},
            timeout=15,
        )
        r.raise_for_status()
        earnings = r.json().get("earningsCalendar", [])
        matched = [e for e in earnings if e.get("symbol") in tickers]
        logger.info("Finnhub earnings: %d matched of %d returned", len(matched), len(earnings))
        return matched
    except Exception as e:
        logger.warning("Finnhub earnings fetch failed: %s", e)
        return []


def _eia_report_note() -> str:
    """EIA petroleum status report drops every Wednesday at 10:30 AM EST."""
    next_wednesday = datetime.utcnow()
    days_ahead = (2 - next_wednesday.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_wednesday += timedelta(days=days_ahead)
    return f"EIA Weekly Petroleum Status Report — {next_wednesday.strftime('%A, %B %d')} at 10:30 AM EST"


def _build_price_context() -> str:
    """
    Pull 7-day price series from DB for all tracked commodities.
    Returns a formatted string for the narrative prompt, with
    explicit data quality flags so the model knows what it can claim.
    """
    lines = []
    for label, symbol in PRICE_SYMBOLS.items():
        try:
            series = get_commodity_price_series(symbol, days=7)
            latest = get_latest_commodity_price(symbol)

            if not series and not latest:
                lines.append(f"{label}: No price data in DB — use web search")
                continue

            if latest:
                current = latest["price"]
                age = latest["polled_at"][:16].replace("T", " ")
            else:
                current = series[0]["value"]
                age = series[0]["date"]

            if series and len(series) >= 2:
                oldest = series[-1]["value"]
                chg = ((current - oldest) / oldest) * 100
                high = max(p["value"] for p in series)
                low  = min(p["value"] for p in series)
                lines.append(
                    f"{label}: ${current:.2f} | 7d change: {chg:+.2f}% "
                    f"| Range: ${low:.2f}–${high:.2f} | As of: {age}"
                )
            elif series and len(series) == 1:
                lines.append(
                    f"{label}: ${current:.2f} | Only 1 data point — "
                    f"use web search to verify and find weekly change | As of: {age}"
                )
            else:
                lines.append(
                    f"{label}: ${current:.2f} (latest known, no series) — "
                    f"use web search to verify | As of: {age}"
                )
        except Exception as e:
            logger.warning("Price context build failed for %s: %s", symbol, e)
            lines.append(f"{label}: DB error — use web search")

    return "\n".join(lines)


def _generate_weekly_narrative(week_digests: list, transcripts: list,
                                upcoming_earnings: list, price_context: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Narrative unavailable."

    # Full daily narratives — not truncated, the weekly needs real context
    week_summary = "\n\n".join(
        f"=== {d['date_str']} ===\n{d.get('narrative', '(no narrative)').strip()}"
        for d in week_digests
    ) or "No daily digests available for this week."

    transcript_summary = "\n".join(
        f"  {t['ticker']} ({t['report_date']}): {t.get('summary', '').strip()}"
        for t in transcripts
    ) or "  No earnings transcripts this week."

    earnings_next = "\n".join(
        f"  {e.get('symbol')} — {e.get('date', 'TBD')} (Est EPS: {e.get('epsEstimate', 'N/A')})"
        for e in upcoming_earnings[:5]
    ) or "  None identified (Finnhub key may not be set)."

    eia_note = _eia_report_note()

    prompt = (
        "You are a senior energy markets analyst writing a Friday weekly wrap for serious investors.\n\n"

        "BEFORE WRITING, complete these web searches:\n\n"

        "SEARCH TASK 1 — PRICE VERIFICATION (mandatory):\n"
        "Verify current week-ending spot prices for WTI crude, natural gas front month, and URNM. "
        "For any commodity below marked as having limited or no DB data, search for the full "
        "week's price range. Use live prices in your narrative — do not rely solely on DB data "
        "if it appears stale or incomplete.\n\n"

        "SEARCH TASK 2 — WEEK-END MACRO CONTEXT (mandatory):\n"
        "Search for: any significant energy market developments from the past 48 hours, "
        "OPEC+ weekend news, dollar index weekly close, and whether any geopolitical situation "
        "escalated or de-escalated this week that affected commodity prices.\n\n"

        "SEARCH TASK 3 — FORWARD CATALYSTS (mandatory):\n"
        "Search for key energy market catalysts for next week: scheduled OPEC meetings, "
        "Fed events, China data releases, or any developing geopolitical situations "
        "that traders will be watching. Supplement the earnings and EIA schedule below.\n\n"

        "After completing searches, write 4 tight paragraphs:\n"
        "  1. The 2-3 dominant themes that drove energy markets this week\n"
        "  2. How oil, natural gas, and uranium performed — use verified prices, "
        "cite the weekly range, flag any surprises\n"
        "  3. Earnings and company-level developments worth noting\n"
        "  4. What to watch next week — upcoming catalysts, earnings, key data releases, "
        "and any geopolitical situations that remain live\n\n"

        "Be sharp and specific. No filler. Don't summarize each day individually. "
        "No bullets — flowing paragraphs only.\n\n"

        f"COMMODITY PRICES (from internal DB — verify with web search):\n{price_context}\n\n"
        f"WEEK'S DAILY NARRATIVES:\n{week_summary}\n\n"
        f"EARNINGS CALL HIGHLIGHTS THIS WEEK:\n{transcript_summary}\n\n"
        f"UPCOMING EARNINGS NEXT WEEK:\n{earnings_next}\n\n"
        f"SCHEDULED DATA RELEASES: {eia_note}"
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

        # Extract text blocks — response may contain tool_use/tool_result blocks interleaved
        text_blocks = [
            block["text"]
            for block in response_data.get("content", [])
            if block.get("type") == "text"
        ]
        narrative = "\n\n".join(text_blocks).strip()
        if not narrative:
            logger.warning("Sonnet returned no text blocks for weekly narrative")
            return "Narrative generation produced no output — check logs."
        return narrative

    except Exception as e:
        logger.error("Weekly narrative failed: %s", e)
        return "Narrative generation failed — check logs."


def generate_weekly_digest():
    logger.info("=== Weekly digest generation starting ===")
    now = datetime.utcnow()
    week_str = f"Week of {(now - timedelta(days=4)).strftime('%B %d')} – {now.strftime('%B %d, %Y')}"

    from config import EARNINGS_TRACKED_TICKERS
    week_digests      = get_week_digests(days=7)
    transcripts       = get_recent_transcripts(days=7)
    upcoming_earnings = _get_upcoming_earnings(EARNINGS_TRACKED_TICKERS)
    price_context     = _build_price_context()

    logger.info(
        "Weekly digest inputs: %d daily digests, %d transcripts, %d upcoming earnings",
        len(week_digests), len(transcripts), len(upcoming_earnings)
    )

    narrative = _generate_weekly_narrative(
        week_digests, transcripts, upcoming_earnings, price_context
    )
    narrative_html = "".join(
        f"<p>{p.strip()}</p>" for p in narrative.split("\n\n") if p.strip()
    )

    # Upcoming earnings table
    earnings_rows = "".join(
        f"<tr><td>{e.get('symbol','')}</td><td>{e.get('date','TBD')}</td>"
        f"<td>{e.get('epsEstimate','N/A')}</td></tr>"
        for e in upcoming_earnings[:8]
    ) or "<tr><td colspan='3' style='color:var(--muted)'>No earnings data — check FINNHUB_API_KEY</td></tr>"

    eia_note = _eia_report_note()

    # Transcript cards from this week
    transcript_cards = "".join(f"""
        <div class="transcript-card">
            <div class="tc-header">
                <span class="tc-ticker">{t['ticker']}</span>
                <span class="tc-date">{t['report_date']}</span>
                <span class="tc-score" style="color:{'#22c55e' if (t['sentiment_score'] or 0)>0 else '#ef4444'}">
                    {'▲' if (t['sentiment_score'] or 0)>0 else '▼'} {abs(t['sentiment_score'] or 0):.2f}
                </span>
            </div>
            <div class="tc-summary">{t.get('summary','')}</div>
        </div>""" for t in transcripts
    ) or "<p style='color:var(--muted);font-size:0.8rem'>No earnings calls this week.</p>"

    # Price summary cards for the sidebar
    price_cards = ""
    for label, symbol in PRICE_SYMBOLS.items():
        try:
            series  = get_commodity_price_series(symbol, days=7)
            latest  = get_latest_commodity_price(symbol)
            if not latest:
                continue
            current = latest["price"]
            if series and len(series) >= 2:
                oldest  = series[-1]["value"]
                chg     = ((current - oldest) / oldest) * 100
                chg_color = "#22c55e" if chg >= 0 else "#ef4444"
                chg_str = f'<span style="color:{chg_color}">{chg:+.2f}%</span>'
            else:
                chg_str = '<span style="color:#6b6560">—</span>'
            price_cards += f"""
            <div class="price-row">
                <span class="pr-label">{label}</span>
                <span class="pr-price">${current:.2f}</span>
                <span class="pr-chg">{chg_str}</span>
            </div>"""
        except Exception:
            continue

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Wrap — {week_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;1,8..60,300&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg:#0a0a0a; --card:#111; --border:#222; --border2:#2a2a2a;
            --gold:#c9a84c; --text:#e8e2d6; --muted:#6b6560; --dim:#9a9490;
            --green:#22c55e; --red:#ef4444;
        }}
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ background:var(--bg); color:var(--text); font-family:'Source Serif 4',serif; font-size:15px; line-height:1.7; }}
        header {{ border-bottom:1px solid var(--border); padding:0 clamp(1.5rem,5vw,4rem); }}
        .masthead {{ padding:2rem 0 1.5rem; text-align:center; }}
        .eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.3em; color:var(--gold); text-transform:uppercase; margin-bottom:0.75rem; }}
        h1 {{ font-family:'Playfair Display',serif; font-size:clamp(2rem,5vw,3.5rem); font-weight:900; line-height:1; }}
        h1 em {{ font-style:italic; color:var(--gold); }}
        .datestamp {{ display:inline-block; margin-top:1rem; font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); letter-spacing:0.15em; text-transform:uppercase; padding:0.3rem 0.75rem; border:1px solid var(--border2); }}
        main {{ max-width:1100px; margin:0 auto; padding:2.5rem clamp(1.5rem,5vw,4rem); }}
        .section-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.25em; text-transform:uppercase; color:var(--gold); margin-bottom:1rem; display:flex; align-items:center; gap:0.75rem; }}
        .section-label::after {{ content:''; flex:1; height:1px; background:var(--border); }}
        .narrative {{ border:1px solid var(--border); border-left:3px solid var(--gold); background:var(--card); padding:1.75rem 2rem; margin-bottom:2.5rem; }}
        .narrative p {{ font-size:0.95rem; font-weight:300; margin-bottom:0.85rem; }}
        .narrative p:last-child {{ margin-bottom:0; }}
        .three-col {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:1.5px; background:var(--border); margin-bottom:2.5rem; }}
        .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:1.5px; background:var(--border); margin-bottom:2.5rem; }}
        .col-block {{ background:var(--card); padding:1.5rem; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); letter-spacing:0.1em; text-transform:uppercase; padding:0.4rem 0; border-bottom:1px solid var(--border); text-align:left; }}
        td {{ font-family:'IBM Plex Mono',monospace; font-size:0.7rem; color:var(--dim); padding:0.45rem 0; border-bottom:1px solid var(--border2); }}
        .eia-note {{ font-family:'IBM Plex Mono',monospace; font-size:0.7rem; color:var(--gold); padding:0.75rem; border:1px solid var(--border2); margin-top:0.75rem; }}
        .transcript-card {{ border:1px solid var(--border); padding:1rem 1.25rem; margin-bottom:0.75rem; }}
        .tc-header {{ display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem; }}
        .tc-ticker {{ font-family:'IBM Plex Mono',monospace; font-size:0.8rem; color:var(--text); font-weight:500; }}
        .tc-date {{ font-family:'IBM Plex Mono',monospace; font-size:0.65rem; color:var(--muted); }}
        .tc-score {{ font-family:'IBM Plex Mono',monospace; font-size:0.7rem; margin-left:auto; }}
        .tc-summary {{ font-size:0.82rem; font-weight:300; color:var(--dim); line-height:1.6; }}
        .price-row {{ display:flex; align-items:center; padding:0.5rem 0; border-bottom:1px solid var(--border2); gap:0.75rem; }}
        .price-row:last-child {{ border-bottom:none; }}
        .pr-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.65rem; color:var(--dim); flex:1; }}
        .pr-price {{ font-family:'IBM Plex Mono',monospace; font-size:0.75rem; color:var(--text); }}
        .pr-chg {{ font-family:'IBM Plex Mono',monospace; font-size:0.65rem; min-width:60px; text-align:right; }}
        .disclaimer {{ margin-top:2.5rem; padding:1rem 1.25rem; border:1px solid var(--border2); font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); line-height:1.6; }}
        .disclaimer strong {{ color:var(--dim); }}
        footer {{ border-top:1px solid var(--border); padding:1.5rem clamp(1.5rem,5vw,4rem); display:flex; justify-content:space-between; flex-wrap:wrap; gap:1rem; }}
        .footer-l {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); }}
        a.back {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--gold); text-decoration:none; }}
        @media(max-width:700px) {{ .three-col,.two-col {{ grid-template-columns:1fr; }} }}
    </style>
</head>
<body>
<header>
    <div class="masthead">
        <div class="eyebrow">Friday Weekly Wrap</div>
        <h1>The <em>Energy</em> Week in Review</h1>
        <div class="datestamp">{week_str} · Published 17:30 PST</div>
    </div>
</header>
<main>
    <div class="section-label">Weekly Analysis</div>
    <div class="narrative">{narrative_html}</div>

    <div class="section-label">Week-End Prices</div>
    <div style="background:var(--card);border:1px solid var(--border);padding:1.25rem 1.5rem;margin-bottom:2.5rem">
        {price_cards or '<p style="color:var(--muted);font-size:0.75rem;font-family:IBM Plex Mono,monospace">No price data available</p>'}
    </div>

    <div class="two-col">
        <div class="col-block">
            <div class="section-label">Earnings Next Week</div>
            <table>
                <tr><th>Ticker</th><th>Date</th><th>EPS Est.</th></tr>
                {earnings_rows}
            </table>
            <div class="eia-note">📊 {eia_note}</div>
        </div>
        <div class="col-block">
            <div class="section-label">This Week's Earnings Calls</div>
            {transcript_cards}
        </div>
    </div>

    {DISCLAIMER}
</main>
<footer>
    <div class="footer-l">MORNING MARKET BREAKDOWN · WEEKLY WRAP<br>PUBLISHED FRIDAYS AT 17:30 PST</div>
    <a class="back" href="/">← Morning Report</a>
</footer>
</body>
</html>"""

    insert_weekly_digest({
        "week_str": week_str,
        "html": html,
        "narrative": narrative,
        "generated_at": now.isoformat(),
    })
    logger.info("=== Weekly digest complete ===")
    return html
