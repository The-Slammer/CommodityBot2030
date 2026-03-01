"""
weekly_digest.py — Friday 5:30 PM PST weekly wrap.

Synthesizes the week's morning digests, surfaces dominant themes,
price trends, and a forward-looking "watch next week" section
using Finnhub earnings calendar + hardcoded EIA schedule.
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


def _get_upcoming_earnings(tickers: list[str]) -> list[dict]:
    """Fetch next week's earnings dates from Finnhub if key available."""
    if not FINNHUB_API_KEY:
        return []
    try:
        from_date = datetime.utcnow().strftime("%Y-%m-%d")
        to_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": from_date, "to": to_date, "token": FINNHUB_API_KEY},
            timeout=15,
        )
        earnings = r.json().get("earningsCalendar", [])
        return [e for e in earnings if e.get("symbol") in tickers]
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


def _generate_weekly_narrative(week_digests: list, transcripts: list,
                                upcoming_earnings: list) -> str:
    if not ANTHROPIC_API_KEY:
        return "Narrative unavailable."

    # Summarize week's narratives
    week_summary = "\n\n".join(
        f"{d['date_str']}: {d.get('narrative','')[:300]}"
        for d in week_digests
    )

    transcript_summary = "\n".join(
        f"  {t['ticker']} ({t['report_date']}): {t.get('summary','')[:200]}"
        for t in transcripts
    ) or "  No earnings this week."

    earnings_next = "\n".join(
        f"  {e.get('symbol')} — {e.get('date','TBD')} (Est EPS: {e.get('epsEstimate','N/A')})"
        for e in upcoming_earnings[:5]
    ) or "  None identified via Finnhub."

    eia_note = _eia_report_note()

    prompt = (
        "You are a senior energy markets analyst writing a Friday weekly wrap for serious investors. "
        "Write 4 tight paragraphs:\n"
        "1. The 2-3 dominant themes that drove energy markets this week\n"
        "2. How oil, natural gas, and uranium performed — any surprises vs Monday's outlook\n"
        "3. Earnings and company-level developments worth noting\n"
        "4. What to watch next week — upcoming catalysts, earnings, and key data releases\n\n"
        "Be sharp and specific. No filler. Don't summarize each day individually.\n\n"
        f"Week's daily narratives:\n{week_summary}\n\n"
        f"Earnings call highlights this week:\n{transcript_summary}\n\n"
        f"Upcoming earnings next week:\n{earnings_next}\n\n"
        f"Scheduled data releases: {eia_note}"
    )

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": "claude-haiku-4-5", "max_tokens": 600,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        return r.json()["content"][0]["text"]
    except Exception as e:
        logger.error("Weekly narrative failed: %s", e)
        return "Narrative generation failed."


def generate_weekly_digest():
    logger.info("=== Weekly digest generation starting ===")
    now = datetime.utcnow()
    week_str = f"Week of {(now - timedelta(days=4)).strftime('%B %d')} – {now.strftime('%B %d, %Y')}"

    from config import EARNINGS_TRACKED_TICKERS
    week_digests = get_week_digests(days=7)
    transcripts = get_recent_transcripts(days=7)
    upcoming_earnings = _get_upcoming_earnings(EARNINGS_TRACKED_TICKERS)

    narrative = _generate_weekly_narrative(week_digests, transcripts, upcoming_earnings)
    narrative_html = "".join(
        f"<p>{p.strip()}</p>" for p in narrative.split("\n\n") if p.strip()
    )

    # Upcoming earnings table
    earnings_rows = "".join(
        f"<tr><td>{e.get('symbol','')}</td><td>{e.get('date','TBD')}</td>"
        f"<td>{e.get('epsEstimate','N/A')}</td></tr>"
        for e in upcoming_earnings[:8]
    ) or "<tr><td colspan='3' style='color:var(--muted)'>No earnings identified via Finnhub</td></tr>"

    eia_note = _eia_report_note()

    # Transcripts from this week
    transcript_cards = "".join(f"""
        <div class="transcript-card">
            <div class="tc-header">
                <span class="tc-ticker">{t['ticker']}</span>
                <span class="tc-date">{t['report_date']}</span>
                <span class="tc-score" style="color:{'#22c55e' if t['sentiment_score']>0 else '#ef4444'}">
                    {'▲' if t['sentiment_score']>0 else '▼'} {abs(t['sentiment_score']):.2f}
                </span>
            </div>
            <div class="tc-summary">{t.get('summary','')}</div>
        </div>""" for t in transcripts
    ) or "<p style='color:var(--muted);font-size:0.8rem'>No earnings calls this week.</p>"

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
        }}
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ background:var(--bg); color:var(--text); font-family:'Source Serif 4',serif; font-size:15px; line-height:1.7; }}
        header {{ border-bottom:1px solid var(--border); padding:0 clamp(1.5rem,5vw,4rem); }}
        .masthead {{ padding:2rem 0 1.5rem; text-align:center; }}
        .eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.3em; color:var(--gold); text-transform:uppercase; margin-bottom:0.75rem; }}
        h1 {{ font-family:'Playfair Display',serif; font-size:clamp(2rem,5vw,3.5rem); font-weight:900; line-height:1; }}
        h1 em {{ font-style:italic; color:var(--gold); }}
        .datestamp {{ display:inline-block; margin-top:1rem; font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); letter-spacing:0.15em; text-transform:uppercase; padding:0.3rem 0.75rem; border:1px solid var(--border2); }}
        main {{ max-width:1000px; margin:0 auto; padding:2.5rem clamp(1.5rem,5vw,4rem); }}
        .section-label {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; letter-spacing:0.25em; text-transform:uppercase; color:var(--gold); margin-bottom:1rem; display:flex; align-items:center; gap:0.75rem; }}
        .section-label::after {{ content:''; flex:1; height:1px; background:var(--border); }}
        .narrative {{ border:1px solid var(--border); border-left:3px solid var(--gold); background:var(--card); padding:1.75rem 2rem; margin-bottom:2.5rem; }}
        .narrative p {{ font-size:0.95rem; font-weight:300; margin-bottom:0.85rem; }}
        .narrative p:last-child {{ margin-bottom:0; }}
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
        .disclaimer {{ margin-top:2.5rem; padding:1rem 1.25rem; border:1px solid var(--border2); font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); line-height:1.6; }}
        .disclaimer strong {{ color:var(--dim); }}
        footer {{ border-top:1px solid var(--border); padding:1.5rem clamp(1.5rem,5vw,4rem); display:flex; justify-content:space-between; flex-wrap:wrap; gap:1rem; }}
        .footer-l {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--muted); }}
        a.back {{ font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:var(--gold); text-decoration:none; }}
        @media(max-width:600px) {{ .two-col {{ grid-template-columns:1fr; }} }}
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
    <div class="footer-l">THE DAILY ENERGY JERKOFF · WEEKLY WRAP<br>PUBLISHED FRIDAYS AT 17:30 PST</div>
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
