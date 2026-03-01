"""
web.py — Flask server. Routes: /, /evening, /weekly, /stats, /health, /trigger
"""

import logging
import os
import threading
from datetime import datetime

from flask import Flask, Response, redirect

from database import (
    get_latest_digest,
    get_latest_evening_digest,
    get_latest_weekly_digest,
    get_equity_sentiment_all,
)

logger = logging.getLogger(__name__)
app = Flask(__name__)
_digest_running = False

DISCLAIMER_FOOTER = """<div style="margin:2rem auto;max-width:900px;padding:0 clamp(1.5rem,5vw,4rem)">
<div style="padding:0.85rem 1.1rem;border:1px solid #2a2a2a;font-family:'IBM Plex Mono',monospace;
font-size:0.58rem;color:#6b6560;line-height:1.7;letter-spacing:0.03em">
<strong style="color:#9a9490">RESEARCH PURPOSES ONLY.</strong> CommodityBot is an automated 
research and data aggregation tool. Nothing published on this platform constitutes financial advice, 
investment advice, a trading recommendation, or a solicitation to buy or sell any security, 
commodity, or financial instrument. All content is generated algorithmically from publicly available 
data sources and is provided for informational purposes only. Always conduct your own due diligence 
and consult a licensed financial advisor before making any investment decisions. 
Past performance is not indicative of future results. CommodityBot and its operators 
assume no liability for actions taken based on this content.
</div></div>"""

NAV_BAR = """<nav style="background:#0f0f0f;border-bottom:1px solid #222;
padding:0.6rem clamp(1.5rem,5vw,4rem);display:flex;gap:2rem;align-items:center;flex-wrap:wrap">
<span style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:#c9a84c;
letter-spacing:0.15em;text-transform:uppercase">CommodityBot</span>
<a href="/" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;
text-decoration:none;letter-spacing:0.08em">Morning Report</a>
<a href="/evening" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;
text-decoration:none;letter-spacing:0.08em">Evening Brief</a>
<a href="/weekly" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;
text-decoration:none;letter-spacing:0.08em">Weekly Wrap</a>
<a href="/stats" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;
text-decoration:none;letter-spacing:0.08em;margin-left:auto">Stats →</a>
</nav>"""

PLACEHOLDER = lambda title, note: f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>body{{background:#0a0a0a;color:#6b6560;font-family:'IBM Plex Mono',monospace;
display:flex;flex-direction:column;min-height:100vh;margin:0}}
.wrap{{flex:1;display:flex;align-items:center;justify-content:center;text-align:center;padding:2rem}}
h1{{font-family:'Playfair Display',serif;font-size:2.5rem;color:#e8e2d6;margin-bottom:1rem}}
h1 em{{font-style:italic;color:#c9a84c}}p{{font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase}}
a{{color:#c9a84c}}</style></head>
<body>{NAV_BAR}<div class="wrap"><div>
<h1>The Daily <em>Energy</em> Jerkoff</h1><p>{note}</p>
<p style="margin-top:1rem"><a href="/stats">View ingestion stats →</a></p>
</div></div></body></html>"""


def _inject_nav(html: str) -> str:
    return html.replace("<body>", f"<body>{NAV_BAR}", 1)


def _inject_disclaimer(html: str) -> str:
    return html.replace("</body>", f"{DISCLAIMER_FOOTER}</body>", 1)


def _wrap(html: str) -> str:
    return _inject_disclaimer(_inject_nav(html))


@app.route("/")
def index():
    digest = get_latest_digest()
    if digest:
        return Response(_wrap(digest["html"]), mimetype="text/html")
    return Response(PLACEHOLDER("The Daily Energy Jerkoff", "Morning report publishes at 06:15 PST"), mimetype="text/html")


@app.route("/evening")
def evening():
    digest = get_latest_evening_digest()
    if digest:
        return Response(_wrap(digest["html"]), mimetype="text/html")
    return Response(PLACEHOLDER("Evening Brief", "Evening brief publishes at 17:30 PST"), mimetype="text/html")


@app.route("/weekly")
def weekly():
    digest = get_latest_weekly_digest()
    if digest:
        return Response(_wrap(digest["html"]), mimetype="text/html")
    return Response(PLACEHOLDER("Weekly Wrap", "Weekly wrap publishes Fridays at 17:30 PST"), mimetype="text/html")


@app.route("/health")
def health():
    digest = get_latest_digest()
    return {"status": "ok", "latest_digest": digest["date_str"] if digest else None,
            "server_time_utc": datetime.utcnow().isoformat()}


@app.route("/trigger", methods=["POST"])
def trigger():
    global _digest_running
    if _digest_running:
        return Response(_trigger_page(running=True), mimetype="text/html")

    def run():
        global _digest_running
        _digest_running = True
        try:
            from digest import generate_digest
            generate_digest()
        except Exception as e:
            logger.error("Manual trigger failed: %s", e)
        finally:
            _digest_running = False

    threading.Thread(target=run, daemon=True).start()
    return Response(_trigger_page(started=True), mimetype="text/html")


@app.route("/stats")
def stats():
    from database import get_conn
    with get_conn() as conn:
        rss_count = conn.execute("SELECT COUNT(*) FROM rss_items").fetchone()[0]
        av_count = conn.execute("SELECT COUNT(*) FROM alphavantage_items").fetchone()[0]
        digest_count = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
        rss_polls = conn.execute("""
            SELECT source_name, items_found, items_new, error, polled_at
            FROM source_poll_log WHERE source_type = 'rss'
            ORDER BY polled_at DESC LIMIT 20
        """).fetchall()
        av_polls = conn.execute("""
            SELECT source_name, items_found, items_new, error, polled_at
            FROM source_poll_log WHERE source_type = 'alphavantage'
            ORDER BY polled_at DESC LIMIT 40
        """).fetchall()

    equity_signals = get_equity_sentiment_all()

    def poll_rows(rows):
        result = []
        for r in rows:
            color = '#ef4444' if r[3] else '#22c55e'
            status = r[3] or 'OK'
            result.append(
                f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td>'
                f'<td style="color:{color}">{status}</td>'
                f'<td>{r[4]}</td></tr>'
            )
        return ''.join(result)

    rss_polls_html = poll_rows(rss_polls) or "<tr><td colspan='5' style='color:#6b6560'>No RSS polls logged yet</td></tr>"
    av_polls_html = poll_rows(av_polls) or "<tr><td colspan='5' style='color:#6b6560'>No AV polls logged yet</td></tr>"

    def signal_badge(label, color):
        return f'<span style="border:1px solid {color};color:{color};font-family:\'IBM Plex Mono\',monospace;font-size:0.6rem;letter-spacing:0.08em;padding:0.15rem 0.5rem">{label}</span>'

    equity_rows = "".join(f"""
        <tr>
            <td style="font-family:'IBM Plex Mono',monospace;color:#e8e2d6">{eq.get('ticker','')}</td>
            <td>{eq.get('name','')}</td>
            <td>{eq.get('commodity','')}</td>
            <td>{signal_badge(eq.get('label','—'), eq.get('color','#94a3b8'))}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">{eq.get('composite_score','—')}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:#6b6560;font-size:0.65rem">{eq.get('updated_at','')[:16]}</td>
        </tr>""" for eq in equity_signals) or "<tr><td colspan='6' style='color:#6b6560'>No signals yet — generates after first AV poll</td></tr>"

    running_banner = '<div style="background:#1a1500;border:1px solid #8a6f2e;color:#c9a84c;padding:0.75rem 1rem;font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;margin-bottom:1.5rem">⟳ Digest generation in progress...</div>' if _digest_running else ""

    return Response(f"""<!DOCTYPE html>
<html><head><title>CommodityBot Stats</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px;margin:0}}
.content{{padding:2rem clamp(1.5rem,5vw,4rem)}}
h1{{color:#c9a84c;font-size:1.1rem;letter-spacing:0.2em;margin-bottom:0.35rem}}
h2{{color:#c9a84c;font-size:0.75rem;letter-spacing:0.15em;margin:2rem 0 0.75rem;border-bottom:1px solid #222;padding-bottom:0.5rem}}
.counts{{display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:2rem}}
.count{{background:#111;border:1px solid #222;padding:0.75rem 1.25rem}}
.count .n{{font-size:1.8rem;color:#e8e2d6}}
.count .l{{font-size:0.6rem;color:#6b6560;letter-spacing:0.1em;text-transform:uppercase}}
.topbar{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.5rem;flex-wrap:wrap;gap:1rem}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;color:#6b6560;font-size:0.62rem;letter-spacing:0.1em;padding:0.4rem 0.4rem;border-bottom:1px solid #222;text-transform:uppercase}}
td{{padding:0.4rem 0.4rem;border-bottom:1px solid #161616;color:#9a9490;font-size:0.68rem;max-width:350px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.btn{{background:none;border:1px solid #c9a84c;color:#c9a84c;font-family:'IBM Plex Mono',monospace;font-size:0.7rem;letter-spacing:0.15em;text-transform:uppercase;padding:0.6rem 1.25rem;cursor:pointer;transition:all 0.2s}}
.btn:hover{{background:#c9a84c;color:#0a0a0a}}
a{{color:#c9a84c;text-decoration:none}}
</style></head>
<body>{NAV_BAR}
<div class="content">
<div class="topbar">
  <div><h1>COMMODITYBOT — STATS</h1>
  <div style="font-size:0.6rem;color:#444;margin-top:0.2rem">Morning 06:15 · Evening 17:30 · Weekly Fri 17:30 (all PST)</div></div>
  <form method="POST" action="/trigger" onsubmit="this.querySelector('button').disabled=true;this.querySelector('button').textContent='Generating...'">
    <button class="btn" type="submit">⚡ Generate Digest Now</button>
  </form>
</div>

{running_banner}

<div class="counts">
  <div class="count"><div class="n">{rss_count}</div><div class="l">RSS Items</div></div>
  <div class="count"><div class="n">{av_count}</div><div class="l">AV Items</div></div>
  <div class="count"><div class="n">{digest_count}</div><div class="l">Digests</div></div>
</div>

<h2>EQUITY SIGNALS</h2>
<table>
  <tr><th>Ticker</th><th>Name</th><th>Commodity</th><th>Signal</th><th>Score</th><th>Updated</th></tr>
  {equity_rows}
</table>

<h2>RSS FEEDS — LAST 20 POLLS PER FEED</h2>
<table>
  <tr><th>Source</th><th>Found</th><th>New</th><th>Status</th><th>Time</th></tr>
  {rss_polls_html}
</table>

<h2>ALPHAVANTAGE — LAST 40 POLLS</h2>
<table>
  <tr><th>Source</th><th>Found</th><th>New</th><th>Status</th><th>Time</th></tr>
  {av_polls_html}
</table>

<div style="margin-top:2rem;padding:0.85rem 1rem;border:1px solid #2a2a2a;font-size:0.58rem;color:#6b6560;line-height:1.7">
<strong style="color:#9a9490">RESEARCH PURPOSES ONLY.</strong> All signals are algorithmic and 
do not constitute financial advice. Not a recommendation to buy or sell any security.
</div>
</div></body></html>""", mimetype="text/html")


def _trigger_page(started=False, running=False):
    msg = "A digest is already running." if running else "Digest started — redirecting in 35 seconds..."
    color = "#8a6f2e" if running else "#22c55e"
    refresh = '<meta http-equiv="refresh" content="35;url=/">' if started else ""
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{refresh}
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}}
.msg{{color:{color};font-size:0.8rem;letter-spacing:0.1em;max-width:400px;line-height:1.8}}
a{{color:#c9a84c}}</style></head>
<body><div><div class="msg">{msg}</div>
<p style="margin-top:1.5rem;font-size:0.65rem;color:#444"><a href="/stats">← back to stats</a></p>
</div></body></html>"""


def start_web_server():
    port = int(os.getenv("PORT", "8080"))
    logger.info("Web server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
