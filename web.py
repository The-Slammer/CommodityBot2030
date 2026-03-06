"""
web.py — Flask server. Routes: /, /evening, /weekly, /stats, /health, /trigger
"""

import logging
import os
import threading
import json
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
_evening_running = False

from charts import charts_bp
app.register_blueprint(charts_bp)

from scanner import scanner_bp
app.register_blueprint(scanner_bp)

DEV_BANNER = """<div style="background:#0d0d0d;border-bottom:1px solid #1a1a1a;padding:0.3rem clamp(1.5rem,5vw,4rem);text-align:center">
<span style="font-family:'IBM Plex Mono',monospace;font-size:0.55rem;color:#444;letter-spacing:0.08em">
CommodityBot is under continuous development — features are regularly tuned, expanded, and added.
</span></div>"""

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

NAV_BAR = """<style>
.cb-nav{background:#0f0f0f;border-bottom:1px solid #222;padding:0.6rem clamp(1.5rem,5vw,4rem);display:flex;gap:2rem;align-items:center;flex-wrap:wrap;position:relative;z-index:100}
.cb-nav a,.cb-nav .dd-trigger{font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;cursor:pointer}
.cb-nav .brand{font-size:0.6rem;color:#c9a84c;letter-spacing:0.15em;text-transform:uppercase}
.cb-nav .ml-auto{margin-left:auto}
.dd{position:relative;display:inline-block}
.dd-trigger{background:none;border:none;padding:0;font-family:'IBM Plex Mono',monospace}
.dd-menu{visibility:hidden;opacity:0;pointer-events:none;position:absolute;top:100%;left:0;padding-top:6px;background:transparent;min-width:160px;z-index:200;transition:opacity 0.12s ease, visibility 0.12s ease;transition-delay:0s;}
.dd-menu-inner{background:#111;border:1px solid #222}
.dd-menu a{display:block;padding:0.5rem 1rem;font-family:'IBM Plex Mono',monospace;font-size:0.62rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;border-bottom:1px solid #1a1a1a}
.dd-menu a:last-child{border-bottom:none}
.dd-menu a:hover,.cb-nav a:hover,.dd-trigger:hover{color:#e8e2d6}
.dd:hover .dd-menu{visibility:visible;opacity:1;pointer-events:auto;transition-delay:0s,0s;}
.dd-menu{transition-delay:0s,200ms;}
</style>
<nav class="cb-nav">
  <span class="brand">CommodityBot</span>
  <div class="dd">
    <button class="dd-trigger">Words ▾</button>
    <div class="dd-menu">
      <a href="/">Morning Report</a>
      <a href="/evening">Evening Brief</a>
      <a href="/weekly">Weekly Wrap</a>
    </div>
  </div>
  <div class="dd">
    <button class="dd-trigger">Charts ▾</button>
    <div class="dd-menu">
      <a href="/charts/energy">Energy</a>
      <a href="/charts/gold-silver">Gold / Silver</a>
      <a href="/charts/copper">Copper</a>
      <a href="/charts/uranium">Uranium</a>
    </div>
  </div>
  <a href="/scanner">Scanner</a>
  <a href="/portfolio">Portfolio</a>
  <a href="/about">About</a>
  <a href="/data-health" class="ml-auto">Health</a>
  <a href="/stats">Stats →</a>
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
<h1>Morning Market <em>Breakdown</em></h1><p>{note}</p>
<p style="margin-top:1rem"><a href="/stats">View ingestion stats →</a></p>
</div></div></body></html>"""


def _inject_nav(html: str) -> str:
    return html.replace("<body>", f"<body>{DEV_BANNER}{NAV_BAR}", 1)


def _inject_disclaimer(html: str) -> str:
    return html.replace("</body>", f"{DISCLAIMER_FOOTER}</body>", 1)


def _build_price_ticker() -> str:
    try:
        from database import get_latest_commodity_price, get_commodity_price_series
        
        def ticker_item(symbol, label):
            latest = get_latest_commodity_price(symbol)
            if not latest:
                return (f'<span style="font-family:\'IBM Plex Mono\',monospace;'
                        f'font-size:0.6rem;color:#6b6560">{label} —</span>')
            
            price = latest["price"]
            polled = latest["polled_at"][:16].replace("T", " ")

            # Get 7d series for week-over-week
            series = get_commodity_price_series(symbol, days=8)
            wow_html = ""
            if series and len(series) >= 2:
                oldest = series[-1]["value"]
                chg = ((price - oldest) / oldest) * 100
                color = "#22c55e" if chg >= 0 else "#ef4444"
                arrow = "▲" if chg >= 0 else "▼"
                sign = "+" if chg >= 0 else ""
                wow_html = (
                    f'<span style="color:{color};margin-left:0.4rem;font-size:0.58rem">'
                    f'{arrow} {sign}{chg:.2f}% W/W</span>'
                    f'<span style="color:#2a2a2a;margin-left:0.35rem;font-size:0.55rem">'
                    f'(was ${oldest:.2f})</span>'
                )

            return (
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.6rem;'
                f'color:#9a9490;letter-spacing:0.05em">'
                f'<span style="color:#6b6560">{label}</span> '
                f'<span style="color:#e8e2d6">${price:.2f}</span>'
                f'{wow_html}'
                f'</span>'
            )

        # Brent shown display-only — not used in benchmarking or digest
        wti_latest   = get_latest_commodity_price("CRUDE_WTI")
        brent_latest = get_latest_commodity_price("CRUDE_BRENT")
        spread_html  = ""
        if wti_latest and brent_latest:
            spread = brent_latest["price"] - wti_latest["price"]
            sign   = "+" if spread >= 0 else ""
            spread_html = (
                f' <span style="color:#444;font-size:0.55rem">'
                f'B/W {sign}{spread:.2f}</span>'
            )

        items = "  ·  ".join([
            ticker_item("CRUDE_WTI",   "WTI OIL") + spread_html,
            ticker_item("CRUDE_BRENT", "BRENT"),
            ticker_item("NATURAL_GAS", "NAT GAS"),
            ticker_item("URNM",        "URANIUM"),
            ticker_item("GOLD",        "GOLD"),
            ticker_item("SILVER",      "SILVER"),
            ticker_item("COPPER",      "COPPER"),
        ])

        # Timestamp from latest WTI poll
        latest_wti = get_latest_commodity_price("CRUDE_WTI")
        ts = latest_wti["polled_at"][:16].replace("T", " ") + " UTC" if latest_wti else ""

        return (
            f'<div style="background:#0a0a0a;border-bottom:1px solid #1a1a1a;'
            f'padding:0.35rem clamp(1.5rem,5vw,4rem);display:flex;'
            f'align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">'
            f'<div style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">{items}</div>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.55rem;'
            f'color:#2a2a2a;letter-spacing:0.06em">as of {ts}</span>'
            f'</div>'
        )
    except Exception:
        return ""

        generated = digest.get("generated_at", "")[:16].replace("T", " ") + " UTC" if digest.get("generated_at") else ""

        items = "  ·  ".join([
            ticker_item("oil", "WTI", "$/bbl"),
            ticker_item("natural_gas", "NAT GAS", "$/MMBtu"),
            ticker_item("uranium", "URANIUM", "$/share"),
        ])

        return (
            f'<div style="background:#0a0a0a;border-bottom:1px solid #1a1a1a;'
            f'padding:0.35rem clamp(1.5rem,5vw,4rem);display:flex;'
            f'align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">'
            f'<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">{items}</div>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.55rem;'
            f'color:#3a3a3a;letter-spacing:0.06em">as of {generated}</span>'
            f'</div>'
        )
    except Exception:
        return ""


def _wrap(html: str) -> str:
    ticker = _build_price_ticker()
    html = _inject_disclaimer(_inject_nav(html))
    # Inject price ticker right after the opening <nav> tag closes
    html = html.replace("</nav>", f"</nav>{ticker}", 1)
    return html


@app.route("/")
def index():
    digest = get_latest_digest()
    if digest:
        return Response(_wrap(digest["html"]), mimetype="text/html")
    return Response(PLACEHOLDER("The Morning Market Breakdown", "Morning report publishes at 06:15 PST"), mimetype="text/html")


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


@app.route("/trigger/evening", methods=["POST"])
def trigger_evening():
    global _evening_running
    if _evening_running:
        return Response(_trigger_page(running=True, label="Evening brief"), mimetype="text/html")

    def run():
        global _evening_running
        _evening_running = True
        try:
            from evening_digest import generate_evening_digest
            generate_evening_digest()
        except Exception as e:
            logger.error("Manual evening trigger failed: %s", e)
        finally:
            _evening_running = False

    threading.Thread(target=run, daemon=True).start()
    return Response(_trigger_page(started=True, label="Evening brief"), mimetype="text/html")


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
  <form method="POST" action="/trigger/evening" onsubmit="this.querySelector('button').disabled=true;this.querySelector('button').textContent='Generating...'">
    <button class="btn" type="submit" style="background:#1a1a1a;border-color:#2a2a2a">🌙 Regenerate Evening Brief</button>
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


def _trigger_page(started=False, running=False, label="Morning report"):
    redirect_url = "/evening" if "vening" in label else "/"
    msg = f"A {label.lower()} is already running." if running else f"{label} started — redirecting in 35 seconds..."
    color = "#8a6f2e" if running else "#22c55e"
    refresh = f'<meta http-equiv="refresh" content="35;url={redirect_url}">' if started else ""
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


@app.route("/diag/av")
def diag_av():
    """Diagnostic endpoint — tests AV entitlement by fetching XOM quote and WTI price."""
    import requests, os
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "")
    base = "https://www.alphavantage.co/query"
    results = {}

    # Test 1: equity quote (should work on any plan)
    try:
        r = requests.get(base, params={"function": "GLOBAL_QUOTE", "symbol": "XOM", "apikey": api_key}, timeout=10)
        data = r.json()
        gq = data.get("Global Quote", {})
        results["equity_quote"] = {
            "status": "OK" if gq.get("05. price") else "EMPTY",
            "price": gq.get("05. price"),
            "note": data.get("Note") or data.get("Information") or "none",
        }
    except Exception as e:
        results["equity_quote"] = {"status": "ERROR", "error": str(e)}

    # Test 2: WTI commodity (requires premium)
    try:
        r = requests.get(base, params={"function": "WTI", "interval": "daily", "apikey": api_key}, timeout=10)
        data = r.json()
        entries = data.get("data", [])
        results["wti_commodity"] = {
            "status": "OK" if entries else "EMPTY",
            "latest": entries[0] if entries else None,
            "note": data.get("Note") or data.get("Information") or "none",
        }
    except Exception as e:
        results["wti_commodity"] = {"status": "ERROR", "error": str(e)}

    # Test 3: intraday (tests realtime/delayed entitlement)
    try:
        r = requests.get(base, params={
            "function": "TIME_SERIES_INTRADAY", "symbol": "XOM",
            "interval": "5min", "outputsize": "compact", "apikey": api_key
        }, timeout=10)
        data = r.json()
        series = data.get("Time Series (5min)", {})
        latest_ts = max(series.keys()) if series else None
        results["intraday"] = {
            "status": "OK" if series else "EMPTY",
            "latest_timestamp": latest_ts,
            "note": data.get("Note") or data.get("Information") or "none",
        }
    except Exception as e:
        results["intraday"] = {"status": "ERROR", "error": str(e)}

    results["checked_at"] = datetime.utcnow().isoformat() + "Z"

    html = f"""<!DOCTYPE html>
<html><head><title>AV Diagnostic</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px;padding:2rem}}
h1{{color:#c9a84c;font-size:0.9rem;letter-spacing:0.2em}}
.card{{background:#111;border:1px solid #222;padding:1rem;margin:0.75rem 0;max-width:700px}}
.card h2{{color:#c9a84c;font-size:0.7rem;letter-spacing:0.1em;margin:0 0 0.5rem}}
.ok{{color:#22c55e}}.empty{{color:#ef4444}}.error{{color:#ef4444}}
pre{{color:#9a9490;font-size:0.68rem;line-height:1.6;margin:0}}
</style></head><body>
<h1>ALPHAVANTAGE DIAGNOSTIC</h1>
<p style="color:#6b6560;font-size:0.65rem">{results["checked_at"]}</p>
"""
    for test, res in results.items():
        if test == "checked_at":
            continue
        status = res.get("status", "")
        color_class = "ok" if status == "OK" else "error"
        html += f'<div class="card"><h2>{test.upper()} — <span class="{color_class}">{status}</span></h2>'
        html += f'<pre>{json.dumps(res, indent=2)}</pre></div>'

    html += "</body></html>"
    return Response(html, mimetype="text/html")


@app.route("/about")
def about():
    return Response(_wrap("""<!DOCTYPE html>
<html><head><title>CommodityBot \u2014 About</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px}
.content{padding:3rem clamp(1.5rem,5vw,4rem);max-width:900px}
.hero{margin-bottom:3.5rem;padding-bottom:2.5rem;border-bottom:1px solid #1a1a1a}
.hero-label{font-size:0.58rem;color:#444;letter-spacing:0.25em;text-transform:uppercase;margin-bottom:1rem}
.hero-title{font-family:'Playfair Display',serif;font-size:clamp(2.2rem,5vw,3.2rem);color:#e8e2d6;line-height:1.15;margin-bottom:1.5rem}
.hero-title em{color:#c9a84c;font-style:italic}
.hero-body{font-size:0.82rem;color:#9a9490;line-height:2;max-width:720px}
.hero-body strong{color:#c9a84c;font-weight:500}
h2{font-size:0.62rem;color:#c9a84c;letter-spacing:0.25em;text-transform:uppercase;margin:3rem 0 1.25rem;padding-bottom:0.6rem;border-bottom:1px solid #1a1a1a}
p{color:#9a9490;line-height:1.9;margin:0 0 1.1rem;font-size:0.78rem}
p strong{color:#e8e2d6;font-weight:500}
.factor-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1px;margin:1.25rem 0 2rem}
.factor-card{background:#0e0e0e;border:1px solid #1a1a1a;padding:1.1rem 1.25rem}
.factor-card .fc-icon{font-size:1rem;margin-bottom:0.6rem}
.factor-card .fc-title{font-size:0.68rem;color:#e8e2d6;letter-spacing:0.08em;margin-bottom:0.5rem;text-transform:uppercase}
.factor-card .fc-body{font-size:0.65rem;color:#6b6560;line-height:1.7}
.source-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1px;margin:1.25rem 0 2rem}
.source-card{background:#0e0e0e;border:1px solid #1a1a1a;padding:1rem 1.1rem}
.source-card .sc-name{font-size:0.68rem;color:#c9a84c;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.4rem}
.source-card .sc-desc{font-size:0.63rem;color:#6b6560;line-height:1.6}
.dev-banner{background:#0e0e0e;border:1px solid #1e1e1e;padding:1.1rem 1.25rem;margin:2.5rem 0;display:flex;align-items:flex-start;gap:1rem}
.dev-dot{width:6px;height:6px;border-radius:50%;background:#22c55e;margin-top:0.35rem;flex-shrink:0;box-shadow:0 0 6px #22c55e}
.dev-text{font-size:0.68rem;color:#6b6560;line-height:1.7}
.dev-text strong{color:#e8e2d6}
.disclaimer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #1a1a1a;font-size:0.6rem;color:#333;line-height:1.8}
</style></head>
<body><div class="content">

<div class="hero">
  <div class="hero-label">About this system</div>
  <h1 class="hero-title">The world runs on<br><em>commodities.</em><br>We watch them so you don't have to.</h1>
  <p class="hero-body">
    Before the price at the pump changes, before your electricity bill spikes, before a mining stock breaks out or a refiner collapses \u2014 something moved in the commodity markets. A supply disruption. A government report. A geopolitical threshold crossed. <strong>CommodityBot exists to catch those signals as they happen</strong> and surface what matters to the people who need to understand why commodity prices move the way they do.
  </p>
</div>

<h2>Why Commodities Matter to Everyone</h2>

<p>Most people interact with commodity markets every single day without realizing it. The price of crude oil is embedded in the cost of every product that was manufactured, packaged, or shipped. Natural gas is the feedstock for fertilizer \u2014 which means it is inside the cost of food. Copper is in every wire in your home, every EV on the road, every data center running the AI systems reshaping the economy. Gold and silver are the world's oldest stores of value, and they still move in response to the same forces \u2014 currency debasement, geopolitical fear, real interest rates \u2014 that they always have.</p>

<p>When commodity prices are volatile, the effects ripple outward. Inflation rises. Energy companies expand or contract their drilling programs. Governments shift energy policy. Currencies of commodity-producing nations move. <strong>Understanding what drives commodity prices is understanding how the physical economy actually works</strong> \u2014 underneath the financial abstraction, underneath the headlines, at the level of barrels and BTUs and tonnes.</p>

<h2>What Moves Commodity Prices</h2>

<div class="factor-grid">
  <div class="factor-card">
    <div class="fc-icon">&#9889;</div>
    <div class="fc-title">Geopolitical Disruption</div>
    <div class="fc-body">Wars, sanctions, and chokepoint threats \u2014 the Strait of Hormuz, the Red Sea, Russia pipeline flows \u2014 can reprice global energy markets overnight. The gap between headline risk and actual supply impact is where the real trading signal lives.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#128202;</div>
    <div class="fc-title">Supply Decisions</div>
    <div class="fc-body">OPEC+ production quotas, US shale rig counts, LNG export capacity, and state-owned producer behavior collectively determine how much supply enters the market. A single OPEC communiqu\u00e9 can move WTI by dollars per barrel.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#128203;</div>
    <div class="fc-title">Inventory &amp; Government Data</div>
    <div class="fc-body">The EIA's weekly crude and natural gas storage reports are among the most market-moving scheduled data releases in energy. A larger-than-expected draw or build in inventories can immediately reprice front-month futures.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#128181;</div>
    <div class="fc-title">Dollar Strength</div>
    <div class="fc-body">Commodities are priced in US dollars globally. When the dollar strengthens, commodities become more expensive in local currencies, dampening demand. When the dollar weakens, commodities reprice higher even before physical demand changes.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#127758;</div>
    <div class="fc-title">Demand Shocks</div>
    <div class="fc-body">China's industrial cycle, AI datacenter buildout driving power and copper demand, EV adoption curves, and emerging market growth rates are the long-cycle demand forces that underpin commodity supercycles \u2014 or break them.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#128200;</div>
    <div class="fc-title">Capital Cycle Lag</div>
    <div class="fc-body">Years of underinvestment in upstream energy and mining infrastructure create supply deficits that take years to correct. The longest and most profitable commodity moves often come from reading where we are in the capital cycle \u2014 not the news cycle.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#127919;</div>
    <div class="fc-title">Speculative Positioning</div>
    <div class="fc-body">COT (Commitment of Traders) data reveals how leveraged money is positioned in commodity futures. Extreme crowding in either direction creates the conditions for violent reversals when the narrative shifts.</div>
  </div>
  <div class="factor-card">
    <div class="fc-icon">&#9889;</div>
    <div class="fc-title">Structural Demand Shifts</div>
    <div class="fc-body">The energy transition, nuclear renaissance, grid modernization, and defense spending cycles create decade-long tailwinds for specific commodities \u2014 uranium, copper, lithium \u2014 independent of short-term price noise.</div>
  </div>
</div>

<h2>What CommodityBot Does</h2>

<p>CommodityBot is a <strong>dynamic AI-powered intelligence system</strong> built to aggregate, synthesize, and surface the signals that move commodity markets. It runs continuously \u2014 pulling fresh data every hour across hundreds of sources \u2014 and applies a layered analysis pipeline to convert raw information into actionable market intelligence.</p>

<p>The system currently tracks commodity equities across oil &amp; gas E&amp;P, midstream, uranium, gold miners, silver miners, copper, and lithium. It monitors spot commodity prices for WTI crude, Brent crude, natural gas, gold, silver, and copper in real time. Every tracked equity receives a composite signal score updated hourly \u2014 blending news sentiment, price momentum, and earnings transcript analysis into a single directional read.</p>

<div class="source-grid">
  <div class="source-card">
    <div class="sc-name">Equity News &amp; Sentiment</div>
    <div class="sc-desc">Hourly news feed across all tracked tickers, scored and weighted by source credibility and recency</div>
  </div>
  <div class="source-card">
    <div class="sc-name">Government Reports</div>
    <div class="sc-desc">EIA weekly crude and natural gas storage data ingested on release day and factored into the intelligence pipeline</div>
  </div>
  <div class="source-card">
    <div class="sc-name">SEC Filings</div>
    <div class="sc-desc">Material corporate events \u2014 8-Ks, earnings releases, insider activity \u2014 monitored in real time across all tracked companies</div>
  </div>
  <div class="source-card">
    <div class="sc-name">Video &amp; Podcast Intelligence</div>
    <div class="sc-desc">Curated analyst interviews, institutional research channels, and macro voices \u2014 transcribed and analyzed for signal</div>
  </div>
  <div class="source-card">
    <div class="sc-name">Geopolitical Monitoring</div>
    <div class="sc-desc">Daily AI-generated briefs mapping global events to their specific commodity price implications</div>
  </div>
  <div class="source-card">
    <div class="sc-name">Commodity Price Feeds</div>
    <div class="sc-desc">Spot prices for seven commodities updated every 30 minutes, tracked with week-over-week context and spread analysis</div>
  </div>
</div>

<h2>The Intelligence Layer</h2>

<p>Raw data collection is table stakes. What CommodityBot adds is a two-stage AI synthesis pipeline \u2014 a fast Haiku model for initial classification, escalating to Claude Sonnet for the deeper analysis that ends up in the morning report, evening brief, and weekly wrap. The reports are written the way a thoughtful analyst would write them: identifying what is actually moving, what the contradictions are, and what deserves attention before it becomes consensus.</p>

<p>The nightly scanner runs a technical pass across the full equity universe \u2014 computing 30/60/90 day performance, 52-week positioning, volatility, sentiment velocity, and relative strength against Sprott benchmark ETFs. The paper trading engine runs three windows per market day, using the same signal stack to make autonomous position decisions and test whether the data has real predictive value.</p>

<h2>Under Continuous Development</h2>

<div class="dev-banner">
  <div class="dev-dot"></div>
  <div class="dev-text">
    <strong>CommodityBot is actively being built.</strong> New data sources, signal types, commodities, and analytical capabilities are added continuously. The system you see today is more capable than it was last month, and less capable than it will be next month. The goal is to keep expanding the coverage and sharpening the intelligence until it becomes the most useful commodity market tool available to individual investors and traders \u2014 built by someone who uses it themselves, tuned for the signals that actually matter.
  </div>
</div>

<div class="disclaimer">
  RESEARCH &amp; EDUCATIONAL PURPOSES ONLY. Nothing on this site constitutes financial advice, investment recommendations, or an offer to buy or sell any security or commodity. Commodity markets are highly volatile. Past signals do not guarantee future results. Always conduct your own due diligence before making investment decisions.
</div>

</div></body></html>"""), mimetype="text/html")


@app.route("/data-health")
def data_health():
    from database import get_conn, get_latest_commodity_price, get_commodity_price_series
    from datetime import datetime, timedelta
    import os as _os

    now = datetime.utcnow()

    # --- Commodity price health ---
    COMMODITY_CHECKS = [
        {"symbol": "CRUDE_WTI",   "label": "WTI Crude Oil",   "unit": "$/bbl",   "min": 30,  "max": 150, "stale_hours": 2},
        {"symbol": "CRUDE_BRENT", "label": "Brent Crude",     "unit": "$/bbl",   "min": 30,  "max": 150, "stale_hours": 2},
        {"symbol": "NATURAL_GAS", "label": "Natural Gas",     "unit": "$/MMBtu", "min": 0.5, "max": 30,  "stale_hours": 2},
        {"symbol": "URNM",        "label": "URNM (Uranium)",  "unit": "$/share", "min": 10,  "max": 200, "stale_hours": 2},
        {"symbol": "GOLD",        "label": "Gold",            "unit": "$/oz",    "min": 500, "max": 5000,"stale_hours": 2},
        {"symbol": "SILVER",      "label": "Silver",          "unit": "$/oz",    "min": 5,   "max": 500, "stale_hours": 2},
        {"symbol": "COPPER",      "label": "Copper",          "unit": "$/lb",    "min": 1,   "max": 20,  "stale_hours": 2},
    ]

    def age_str(ts_str):
        try:
            ts = datetime.fromisoformat(ts_str[:19])
            delta = now - ts
            h = int(delta.seconds // 3600 + delta.days * 24)
            m = int((delta.seconds % 3600) // 60)
            if delta.days > 0:
                return f"{delta.days}d {h % 24}h ago"
            elif h > 0:
                return f"{h}h {m}m ago"
            else:
                return f"{m}m ago"
        except Exception:
            return "unknown"

    commodity_rows = ""
    commodity_ok = 0
    commodity_warn = 0
    commodity_err = 0

    for check in COMMODITY_CHECKS:
        latest = get_latest_commodity_price(check["symbol"])
        if not latest:
            status = "MISSING"
            color  = "#ef4444"
            price_str = "—"
            age_label = "never polled"
            commodity_err += 1
        else:
            price = latest["price"]
            age   = age_str(latest["polled_at"])
            price_str = f"${price:.4f}"

            # Check staleness
            try:
                ts    = datetime.fromisoformat(latest["polled_at"][:19])
                delta = now - ts
                stale = delta > timedelta(hours=check["stale_hours"])
            except Exception:
                stale = True

            # Check range
            out_of_range = price < check["min"] or price > check["max"]

            if out_of_range:
                status = "OUT OF RANGE"
                color  = "#ef4444"
                age_label = age
                commodity_err += 1
            elif stale:
                status = "STALE"
                color  = "#f59e0b"
                age_label = age
                commodity_warn += 1
            else:
                status = "OK"
                color  = "#22c55e"
                age_label = age
                commodity_ok += 1

        series = get_commodity_price_series(check["symbol"], days=7)
        points = len(series) if series else 0
        oldest = series[-1]["date"][:10] if series else "—"

        commodity_rows += f"""
        <tr>
          <td class="label-cell">{check["label"]}</td>
          <td class="mono">{check["symbol"]}</td>
          <td class="mono price-cell">{price_str}</td>
          <td class="mono">{check["unit"]}</td>
          <td class="mono age-cell">{age_label}</td>
          <td class="mono">{points} pts (since {oldest})</td>
          <td><span class="badge" style="border-color:{color};color:{color}">{status}</span></td>
        </tr>"""

    # --- Equity sentiment health ---
    with get_conn() as conn:
        eq_rows = conn.execute("""
            SELECT ticker, composite_score, label, updated_at, commodity_group
            FROM equity_sentiment
            ORDER BY commodity_group, updated_at DESC
        """).fetchall()

    equity_rows = ""
    eq_ok = eq_stale = eq_missing = 0

    for row in eq_rows:
        try:
            ts    = datetime.fromisoformat(row["updated_at"][:19])
            delta = now - ts
            stale = delta > timedelta(hours=4)
            age   = age_str(row["updated_at"])
        except Exception:
            stale = True
            age   = "unknown"

        if stale:
            s_color = "#f59e0b"
            s_label = "STALE"
            eq_stale += 1
        else:
            s_color = "#22c55e"
            s_label = "OK"
            eq_ok += 1

        score = row["composite_score"]
        score_color = "#22c55e" if score >= 0.5 else "#f59e0b" if score >= 0.15 else "#ef4444"

        equity_rows += f"""
        <tr>
          <td class="mono" style="color:#e8e2d6">{row["ticker"]}</td>
          <td class="mono" style="color:{score_color}">{score:.3f}</td>
          <td class="mono">{row["label"]}</td>
          <td class="mono">{row["commodity_group"] or "—"}</td>
          <td class="mono age-cell">{age}</td>
          <td><span class="badge" style="border-color:{s_color};color:{s_color}">{s_label}</span></td>
        </tr>"""

    if not equity_rows:
        equity_rows = "<tr><td colspan='6' class='muted-cell'>No equity signals yet</td></tr>"
        eq_missing = 1

    # --- Scanner job health ---
    try:
        with get_conn() as conn:
            scanner_row = conn.execute("""
                SELECT computed_at FROM scanner_performance
                ORDER BY computed_at DESC LIMIT 1
            """).fetchone()
            scanner_perf_count = conn.execute(
                "SELECT COUNT(*) FROM scanner_performance"
            ).fetchone()[0]
            scanner_sig_count = conn.execute(
                "SELECT COUNT(*) FROM scanner_signals"
            ).fetchone()[0]
            basket_row = conn.execute("""
                SELECT computed_at FROM scanner_basket_flow
                ORDER BY computed_at DESC LIMIT 1
            """).fetchone()
    except Exception:
        scanner_row = None
        scanner_perf_count = 0
        scanner_sig_count = 0
        basket_row = None

    def scanner_age(row):
        if not row:
            return "never run", "#ef4444"
        a = age_str(row[0])
        try:
            delta = now - datetime.fromisoformat(row[0][:19])
            color = "#22c55e" if delta < timedelta(hours=26) else "#f59e0b"
        except Exception:
            color = "#444"
        return a, color

    scanner_age_str, scanner_color = scanner_age(scanner_row)
    basket_age_str,  basket_color  = scanner_age(basket_row)

    # --- Digest freshness ---
    with get_conn() as conn:
        morning_row = conn.execute(
            "SELECT generated_at FROM digests ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        evening_row = conn.execute(
            "SELECT generated_at FROM evening_digests ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()

    def digest_status(row, max_hours=26):
        if not row:
            return "never generated", "#ef4444", "MISSING"
        a = age_str(row[0])
        try:
            delta = now - datetime.fromisoformat(row[0][:19])
            ok = delta < timedelta(hours=max_hours)
        except Exception:
            ok = False
        color = "#22c55e" if ok else "#f59e0b"
        label = "OK" if ok else "STALE"
        return a, color, label

    m_age, m_color, m_label = digest_status(morning_row)
    e_age, e_color, e_label = digest_status(evening_row)

    summary_color = "#22c55e" if commodity_err == 0 and commodity_warn == 0 else "#f59e0b" if commodity_err == 0 else "#ef4444"
    summary_text  = "ALL SYSTEMS OK" if commodity_err == 0 and commodity_warn == 0 else f"{commodity_err} ERRORS · {commodity_warn} WARNINGS" if commodity_err > 0 else f"{commodity_warn} WARNINGS"

    return Response(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Health — CommodityBot</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px}}
.content{{padding:2rem clamp(1.5rem,5vw,4rem);max-width:1400px}}
h1{{color:#c9a84c;font-size:1.1rem;letter-spacing:0.2em;margin-bottom:0.25rem}}
h2{{color:#c9a84c;font-size:0.72rem;letter-spacing:0.15em;margin:2rem 0 0.75rem;border-bottom:1px solid #1e1e1e;padding-bottom:0.5rem;text-transform:uppercase}}
.summary-bar{{display:flex;align-items:center;gap:1rem;padding:0.75rem 1rem;border:1px solid #222;margin:1.25rem 0 2rem;background:#0e0e0e}}
.summary-dot{{width:8px;height:8px;border-radius:50%}}
.summary-text{{font-size:0.68rem;letter-spacing:0.15em;text-transform:uppercase;font-weight:500}}
.summary-ts{{font-size:0.58rem;color:#444;margin-left:auto}}
.status-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1px;margin-bottom:2rem}}
.status-card{{background:#0e0e0e;border:1px solid #1a1a1a;padding:1rem 1.1rem}}
.status-card .sc-label{{font-size:0.58rem;color:#555;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.4rem}}
.status-card .sc-value{{font-size:1.1rem;color:#e8e2d6;margin-bottom:0.2rem}}
.status-card .sc-sub{{font-size:0.58rem;color:#444}}
table{{width:100%;border-collapse:collapse;margin-bottom:2rem}}
th{{text-align:left;color:#444;font-size:0.6rem;letter-spacing:0.1em;padding:0.5rem 0.6rem;border-bottom:1px solid #1e1e1e;text-transform:uppercase}}
td{{padding:0.45rem 0.6rem;border-bottom:1px solid #111;color:#9a9490;font-size:0.65rem;vertical-align:middle}}
.mono{{font-family:'IBM Plex Mono',monospace}}
.label-cell{{color:#e8e2d6}}
.price-cell{{color:#c9a84c}}
.age-cell{{color:#6b6560}}
.muted-cell{{color:#333;padding:1rem}}
.badge{{font-size:0.58rem;letter-spacing:0.1em;padding:0.15rem 0.5rem;border:1px solid;text-transform:uppercase}}
a{{color:#c9a84c;text-decoration:none}}
.refresh{{font-size:0.6rem;color:#444;margin-top:0.5rem}}
</style>
</head>
<body>{NAV_BAR}
<div class="content">
  <h1>DATA HEALTH</h1>
  <div class="refresh">Auto-refresh: <a href="/data-health">Reload page</a> &nbsp;·&nbsp; as of {now.strftime("%Y-%m-%d %H:%M")} UTC</div>

  <div class="summary-bar">
    <div class="summary-dot" style="background:{summary_color}"></div>
    <span class="summary-text" style="color:{summary_color}">{summary_text}</span>
    <span class="summary-ts">Commodity prices: {commodity_ok} ok · {commodity_warn} stale · {commodity_err} errors</span>
  </div>

  <div class="status-grid">
    <div class="status-card">
      <div class="sc-label">Morning Digest</div>
      <div class="sc-value" style="font-size:0.85rem;color:{m_color}">{m_label}</div>
      <div class="sc-sub">{m_age}</div>
    </div>
    <div class="status-card">
      <div class="sc-label">Evening Brief</div>
      <div class="sc-value" style="font-size:0.85rem;color:{e_color}">{e_label}</div>
      <div class="sc-sub">{e_age}</div>
    </div>
    <div class="status-card">
      <div class="sc-label">Scanner Performance</div>
      <div class="sc-value" style="font-size:0.85rem;color:{scanner_color}">{scanner_perf_count} tickers</div>
      <div class="sc-sub">last run {scanner_age_str}</div>
    </div>
    <div class="status-card">
      <div class="sc-label">Basket Flow</div>
      <div class="sc-value" style="font-size:0.85rem;color:{basket_color}">computed</div>
      <div class="sc-sub">last run {basket_age_str}</div>
    </div>
    <div class="status-card">
      <div class="sc-label">Scanner Signals</div>
      <div class="sc-value">{scanner_sig_count}</div>
      <div class="sc-sub">flagged tickers</div>
    </div>
    <div class="status-card">
      <div class="sc-label">Equity Signals</div>
      <div class="sc-value">{eq_ok + eq_stale}</div>
      <div class="sc-sub">{eq_ok} fresh · {eq_stale} stale</div>
    </div>
  </div>

  <h2>Commodity Prices</h2>
  <table>
    <thead><tr>
      <th>Commodity</th><th>Symbol</th><th>Latest Price</th><th>Unit</th>
      <th>Age</th><th>History (7d)</th><th>Status</th>
    </tr></thead>
    <tbody>{commodity_rows}</tbody>
  </table>

  <h2>Equity Sentiment Signals</h2>
  <table>
    <thead><tr>
      <th>Ticker</th><th>Score</th><th>Label</th><th>Group</th><th>Age</th><th>Status</th>
    </tr></thead>
    <tbody>{equity_rows}</tbody>
  </table>

  <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #1a1a1a">
    <a href="/stats">← Back to Stats</a>
  </div>
</div>
</body>
</html>""", mimetype="text/html")


def start_web_server():
    port = int(os.getenv("PORT", "8080"))
    logger.info("Web server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
