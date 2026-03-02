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
try:
    from database import get_open_positions, get_closed_trades, get_portfolio_summary
    _trading_db_available = True
except ImportError:
    _trading_db_available = False
    def get_open_positions(**kw): return []
    def get_closed_trades(**kw): return []
    def get_portfolio_summary(): return {"total_capital":5000,"deployed_capital":0,"available_capital":5000,"open_positions":0,"total_trades":0,"total_pnl":0,"win_rate":0,"wins":0}

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
<a href="/portfolio" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em">Portfolio</a>
<a href="/about" style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em">About</a>
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
    import os as _os
    db_path = _os.getenv("DB_PATH", "/data/energy_agent.db")
    try:
        db_bytes = _os.path.getsize(db_path)
        db_size = f"{db_bytes / 1_048_576:.1f} MB" if db_bytes >= 1_048_576 else f"{db_bytes / 1024:.0f} KB"
    except Exception:
        db_size = "unknown"

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
  <div class="count"><div class="n">{db_size}</div><div class="l">Database Size</div></div>
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



@app.route("/portfolio")
def portfolio():
    summary = get_portfolio_summary()
    open_pos = get_open_positions(include_pending=True)
    closed = get_closed_trades(limit=50)

    total_capital   = summary["total_capital"]
    deployed        = summary["deployed_capital"]
    available       = summary["available_capital"]
    open_count      = summary["open_positions"]
    total_trades    = summary["total_trades"]
    total_pnl       = summary["total_pnl"]
    win_rate        = summary["win_rate"]
    wins            = summary["wins"]

    def pnl_color(v):
        if v is None: return "#9a9490"
        return "#22c55e" if float(v) >= 0 else "#ef4444"

    def pnl_fmt(v, prefix="$"):
        if v is None: return "—"
        return f"{prefix}{float(v):+.2f}" if prefix == "$" else f"{float(v):+.2f}%"

    def status_badge(s):
        colors = {
            "open": "#22c55e",
            "pending_open": "#c9a84c",
            "pending_close": "#fca5a5",
            "closed": "#6b6560",
        }
        c = colors.get(s, "#9a9490")
        label_text = s.upper().replace("_", " ")
        return (f'<span style="border:1px solid {c};color:{c};font-family:IBM Plex Mono,monospace;'
                f'font-size:0.58rem;padding:0.1rem 0.4rem;letter-spacing:0.06em">{label_text}</span>')

    # Open positions table
    if open_pos:
        open_rows = "".join(f"""
            <tr>
                <td style="font-family:'IBM Plex Mono',monospace;color:#e8e2d6;font-weight:bold">{p["ticker"]}</td>
                <td style="color:#9a9490">{p.get("commodity","")}</td>
                <td>{status_badge(p.get("status",""))}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${p.get("position_size",0):.0f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${p.get("entry_price") or 0:.2f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${p.get("current_price") or 0:.2f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:{pnl_color(p.get("pnl"))}">{pnl_fmt(p.get("pnl"))}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:{pnl_color(p.get("pnl_pct"))}">{pnl_fmt(p.get("pnl_pct"), "")}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#c9a84c;font-size:0.65rem">{p.get("entry_score",0):.3f}</td>
                <td style="color:#6b6560;font-size:0.62rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{p.get("entry_reason","")}</td>
            </tr>""" for p in open_pos)
    else:
        open_rows = "<tr><td colspan='10' style='color:#6b6560;text-align:center;padding:1.5rem'>No open positions — trading windows run at 09:45, 12:00, 15:30 ET</td></tr>"

    # Closed trades table
    if closed:
        closed_rows = "".join(f"""
            <tr>
                <td style="font-family:'IBM Plex Mono',monospace;color:#e8e2d6">{t["ticker"]}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${t.get("entry_price") or 0:.2f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${t.get("exit_price") or 0:.2f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:#9a9490">${t.get("position_size",0):.0f}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:{pnl_color(t.get("pnl"))}">{pnl_fmt(t.get("pnl"))}</td>
                <td style="font-family:'IBM Plex Mono',monospace;color:{pnl_color(t.get("pnl_pct"))}">{pnl_fmt(t.get("pnl_pct"), "")}</td>
                <td style="color:#6b6560;font-size:0.62rem">{(t.get("opened_at") or "")[:10]}</td>
                <td style="color:#6b6560;font-size:0.62rem">{(t.get("closed_at") or "")[:10]}</td>
                <td style="color:#9a9490;font-size:0.62rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{t.get("exit_reason","")}</td>
            </tr>""" for t in closed)
    else:
        closed_rows = "<tr><td colspan='9' style='color:#6b6560;text-align:center;padding:1.5rem'>No closed trades yet</td></tr>"

    deployed_pct = round(deployed / total_capital * 100, 1)
    pnl_color_total = "#22c55e" if total_pnl >= 0 else "#ef4444"

    return Response(_wrap(f"""<!DOCTYPE html>
<html><head><title>CommodityBot — Portfolio</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px;margin:0}}
.content{{padding:2rem clamp(1.5rem,5vw,4rem)}}
h1{{color:#c9a84c;font-size:1.1rem;letter-spacing:0.2em;margin-bottom:0.25rem}}
h2{{color:#c9a84c;font-size:0.75rem;letter-spacing:0.15em;margin:2rem 0 0.75rem;border-bottom:1px solid #222;padding-bottom:0.5rem}}
.stats-row{{display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:2rem}}
.stat{{background:#111;border:1px solid #222;padding:0.75rem 1.25rem;min-width:120px}}
.stat .n{{font-size:1.6rem;color:#e8e2d6;font-weight:500}}
.stat .l{{font-size:0.58rem;color:#6b6560;letter-spacing:0.1em;text-transform:uppercase;margin-top:0.15rem}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;color:#6b6560;font-size:0.6rem;letter-spacing:0.1em;padding:0.4rem;border-bottom:1px solid #222;text-transform:uppercase}}
td{{padding:0.4rem;border-bottom:1px solid #161616;color:#9a9490;font-size:0.68rem;vertical-align:middle}}
.bar-bg{{background:#1a1a1a;height:4px;border-radius:2px;margin-top:0.5rem}}
.bar-fill{{background:#c9a84c;height:4px;border-radius:2px}}
a{{color:#c9a84c;text-decoration:none}}
</style></head>
<body><div class="content">
<h1>PAPER TRADING — PORTFOLIO</h1>
<div style="font-size:0.6rem;color:#444;margin-bottom:1.5rem">
  Automated signal-driven paper trades · $5,000 capital pool · Windows: 09:45 / 12:00 / 15:30 ET · EOD settlement
</div>

<div class="stats-row">
  <div class="stat"><div class="n">${total_capital:,.0f}</div><div class="l">Total Capital</div></div>
  <div class="stat"><div class="n" style="color:#c9a84c">${deployed:,.0f}</div><div class="l">Deployed ({deployed_pct}%)</div>
    <div class="bar-bg"><div class="bar-fill" style="width:{deployed_pct}%"></div></div>
  </div>
  <div class="stat"><div class="n">${available:,.0f}</div><div class="l">Available</div></div>
  <div class="stat"><div class="n">{open_count}</div><div class="l">Open Positions</div></div>
  <div class="stat"><div class="n" style="color:{pnl_color_total}">{pnl_fmt(total_pnl)}</div><div class="l">Total P&amp;L</div></div>
  <div class="stat"><div class="n">{win_rate}%</div><div class="l">Win Rate ({wins}/{total_trades})</div></div>
</div>

<h2>OPEN POSITIONS</h2>
<table>
  <tr>
    <th>Ticker</th><th>Sector</th><th>Status</th><th>Size</th>
    <th>Entry $</th><th>Current $</th><th>P&amp;L $</th><th>P&amp;L %</th>
    <th>Signal</th><th>Entry Reason</th>
  </tr>
  {open_rows}
</table>

<h2>TRADE HISTORY</h2>
<table>
  <tr>
    <th>Ticker</th><th>Entry $</th><th>Exit $</th><th>Size</th>
    <th>P&amp;L $</th><th>P&amp;L %</th><th>Opened</th><th>Closed</th><th>Exit Reason</th>
  </tr>
  {closed_rows}
</table>

</div></body></html>"""), mimetype="text/html")


@app.route("/about")
def about():
    return Response(_wrap("""<!DOCTYPE html>
<html><head><title>CommodityBot — About</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px;margin:0}
.content{padding:2rem clamp(1.5rem,5vw,4rem);max-width:860px}
h1{color:#c9a84c;font-size:1.1rem;letter-spacing:0.2em;margin-bottom:0.25rem}
h2{color:#c9a84c;font-size:0.75rem;letter-spacing:0.15em;margin:2.5rem 0 0.75rem;border-bottom:1px solid #222;padding-bottom:0.5rem}
p{color:#9a9490;line-height:1.8;margin:0 0 1rem;font-size:0.75rem}
.tag{display:inline-block;border:1px solid #2a2a2a;color:#6b6560;font-size:0.58rem;padding:0.1rem 0.5rem;margin:0.2rem 0.2rem 0.2rem 0;letter-spacing:0.06em}
.tag.highlight{border-color:#8a6f2e;color:#c9a84c}
.source-row{display:flex;flex-wrap:wrap;gap:0.5rem;margin:0.75rem 0 1.25rem}
.source-card{background:#111;border:1px solid #1e1e1e;padding:0.65rem 0.9rem;min-width:160px;flex:1}
.source-card .s-name{color:#e8e2d6;font-size:0.7rem;margin-bottom:0.2rem}
.source-card .s-desc{color:#6b6560;font-size:0.6rem;line-height:1.5}
ul{color:#9a9490;font-size:0.75rem;line-height:1.9;padding-left:1.2rem;margin:0 0 1rem}
li{margin-bottom:0.1rem}
.subtitle{color:#6b6560;font-size:0.62rem;letter-spacing:0.08em;margin-bottom:2rem}
</style></head>
<body><div class="content">

<h1>COMMODITYBOT</h1>
<div class="subtitle">AUTOMATED ENERGY MARKETS INTELLIGENCE SYSTEM</div>

<p>CommodityBot is a personal research and paper trading system built to monitor energy markets around the clock. It ingests data from dozens of sources, scores equities across oil, natural gas, and uranium sectors, and uses that signal to make autonomous paper trading decisions — testing whether the data it collects actually translates into edge.</p>

<p>It started as an experiment in building a system that thinks like an energy analyst: always watching, always updating, never sleeping. It runs 24/7 on a cloud server and publishes a morning report, evening brief, and weekly wrap — each written by the AI engine using everything it learned that day.</p>

<h2>WHAT IT WATCHES</h2>

<p>The system tracks 79 energy equities across oil & gas E&P, midstream, refining, oilfield services, royalty trusts, and uranium miners. Every hour it pulls fresh news and price data for each name, scores the sentiment, and updates a composite signal that blends news, price momentum, and earnings transcript analysis.</p>

<div class="source-row">
  <div class="source-card"><div class="s-name">Market Intelligence</div><div class="s-desc">Real-time news sentiment & price data across all tracked equities, updated hourly</div></div>
  <div class="source-card"><div class="s-name">Government Data</div><div class="s-desc">Official US energy inventory and production reports on scheduled release cycles</div></div>
  <div class="source-card"><div class="s-name">Regulatory Filings</div><div class="s-desc">Material corporate events monitored in real time as they hit public record</div></div>
  <div class="source-card"><div class="s-name">Video & Podcast</div><div class="s-desc">Long-form interviews and analysis from a curated set of institutional and independent voices</div></div>
  <div class="source-card"><div class="s-name">News Feeds</div><div class="s-desc">Sector-specific publications covering oil, natural gas, and uranium markets</div></div>
</div>

<h2>THE PAPER TRADING ENGINE</h2>

<p>CommodityBot runs a $5,000 paper trading portfolio — real signals, simulated money. The goal is straightforward: find out whether the data it collects actually has predictive value, or whether it's just noise with a good-looking dashboard.</p>

<p>The engine runs three times per day during market hours — 9:45 AM, 12:00 PM, and 3:30 PM ET. At each window it looks for equities crossing into Strong Buy territory or showing strong accelerating momentum, then passes those candidates to Claude Sonnet for a final judgment call. Sonnet reviews the full signal picture — score history, news context, EIA data, any recent SEC filings, and the current portfolio — and decides whether to open a position and how much to size it.</p>

<p>Positions are settled at end-of-day closing prices. Exits are signal-driven: a position closes when the score deteriorates toward neutral, or when Sonnet determines the thesis has broken down. If a stronger opportunity arrives when all five slots are full, the weakest existing position can be displaced.</p>

<p>The portfolio page tracks open positions, unrealised P&L, and the full closed trade history with win rate over time.</p>

<h2>THE REPORTS</h2>

<p>Every morning at 6:15 AM PST, CommodityBot publishes a morning digest — a narrative summary of overnight developments, top-ranked equities, and anything notable from EIA or SEC filings. An evening brief follows at 5:30 PM, and a weekly wrap publishes every Friday evening synthesising the week's themes.</p>

<p>All three reports are written by Claude Sonnet using everything the system collected that day. The goal is something closer to a thoughtful analyst note than a data dump.</p>

</div></body></html>"""), mimetype="text/html")


def start_web_server():
    port = int(os.getenv("PORT", "8080"))
    logger.info("Web server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
