"""
web.py — Flask server serving the digest, stats, and manual trigger.
"""

import logging
import os
import threading
from datetime import datetime

from flask import Flask, Response, redirect

from database import get_latest_digest

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Track if a digest generation is currently running
_digest_running = False

PLACEHOLDER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>The Daily Energy Jerkoff</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
    <style>
        body { background:#0a0a0a; color:#6b6560; font-family:'IBM Plex Mono',monospace;
               display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
        .wrap { text-align:center; }
        h1 { font-family:'Playfair Display',serif; font-size:3rem; color:#e8e2d6; margin-bottom:1rem; }
        h1 em { font-style:italic; color:#c9a84c; }
        p { font-size:0.7rem; letter-spacing:0.15em; text-transform:uppercase; }
        a { color:#c9a84c; }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>The Daily <em>Energy</em> Jerkoff</h1>
        <p>First edition publishes at 06:15 PST</p>
        <p style="margin-top:1rem"><a href="/stats">View ingestion stats →</a></p>
    </div>
</body>
</html>"""


@app.route("/")
def index():
    digest = get_latest_digest()
    if digest:
        return Response(digest["html"], mimetype="text/html")
    return Response(PLACEHOLDER_HTML, mimetype="text/html")


@app.route("/health")
def health():
    digest = get_latest_digest()
    return {
        "status": "ok",
        "latest_digest": digest["date_str"] if digest else None,
        "generated_at": digest["generated_at"] if digest else None,
        "server_time_utc": datetime.utcnow().isoformat(),
    }


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
            logger.error("Manual digest trigger failed: %s", e)
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

        recent_polls = conn.execute("""
            SELECT source_name, source_type, items_found, items_new, error, polled_at
            FROM source_poll_log ORDER BY polled_at DESC LIMIT 30
        """).fetchall()

        recent_av = conn.execute("""
            SELECT title, source_publisher, overall_sentiment_label, published_at
            FROM alphavantage_items ORDER BY ingested_at DESC LIMIT 10
        """).fetchall()

    polls_html = "".join(f"""
        <tr>
            <td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td>
            <td style="color:{'#ef4444' if r[4] else '#22c55e'}">{r[4] or 'OK'}</td>
            <td>{r[5]}</td>
        </tr>""" for r in recent_polls)

    av_html = "".join(f"""
        <tr>
            <td>{r[0][:80] if r[0] else ''}</td><td>{r[1] or ''}</td>
            <td style="color:#c9a84c">{r[2] or ''}</td><td>{r[3] or ''}</td>
        </tr>""" for r in recent_av)

    running_banner = ""
    if _digest_running:
        running_banner = '<div class="running">⟳ Digest generation in progress...</div>'

    return Response(f"""<!DOCTYPE html>
<html><head>
<title>CommodityBot Stats</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  body {{ background:#0a0a0a; color:#e8e2d6; font-family:'IBM Plex Mono',monospace; padding:2rem; font-size:13px; }}
  h1 {{ color:#c9a84c; margin-bottom:0.5rem; font-size:1.2rem; letter-spacing:0.2em; }}
  h2 {{ color:#c9a84c; font-size:0.8rem; letter-spacing:0.15em; margin:2rem 0 0.75rem; border-bottom:1px solid #222; padding-bottom:0.5rem; }}
  .topbar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:2rem; flex-wrap:wrap; gap:1rem; }}
  .counts {{ display:flex; gap:1.5rem; flex-wrap:wrap; }}
  .count {{ background:#111; border:1px solid #222; padding:0.75rem 1.25rem; }}
  .count .n {{ font-size:1.8rem; color:#e8e2d6; }}
  .count .l {{ font-size:0.6rem; color:#6b6560; letter-spacing:0.1em; text-transform:uppercase; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; color:#6b6560; font-size:0.65rem; letter-spacing:0.1em; padding:0.4rem 0.5rem; border-bottom:1px solid #222; }}
  td {{ padding:0.4rem 0.5rem; border-bottom:1px solid #161616; color:#9a9490; font-size:0.7rem; max-width:400px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  a {{ color:#c9a84c; text-decoration:none; }}
  .trigger-form {{ display:inline; }}
  .btn {{ background:none; border:1px solid #c9a84c; color:#c9a84c; font-family:'IBM Plex Mono',monospace;
          font-size:0.7rem; letter-spacing:0.15em; text-transform:uppercase; padding:0.6rem 1.25rem;
          cursor:pointer; transition:all 0.2s; }}
  .btn:hover {{ background:#c9a84c; color:#0a0a0a; }}
  .btn:disabled {{ opacity:0.4; cursor:not-allowed; }}
  .running {{ background:#1a1500; border:1px solid #8a6f2e; color:#c9a84c; padding:0.75rem 1rem;
              font-size:0.7rem; letter-spacing:0.1em; margin-bottom:1.5rem; }}
</style>
</head><body>

<div class="topbar">
  <div>
    <h1>COMMODITYBOT — STATS</h1>
    <div style="font-size:0.6rem;color:#444;margin-top:0.25rem">next scheduled digest: 06:15 PST daily</div>
  </div>
  <form class="trigger-form" method="POST" action="/trigger"
        onsubmit="this.querySelector('button').disabled=true;this.querySelector('button').textContent='Generating...'">
    <button class="btn" type="submit">⚡ Generate Digest Now</button>
  </form>
</div>

{running_banner}

<div class="counts">
  <div class="count"><div class="n">{rss_count}</div><div class="l">RSS Items</div></div>
  <div class="count"><div class="n">{av_count}</div><div class="l">AV Items</div></div>
  <div class="count"><div class="n">{digest_count}</div><div class="l">Digests Generated</div></div>
</div>

<h2>RECENT POLL LOG</h2>
<table>
  <tr><th>SOURCE</th><th>TYPE</th><th>FOUND</th><th>NEW</th><th>STATUS</th><th>TIME</th></tr>
  {polls_html}
</table>

<h2>LATEST ALPHAVANTAGE ITEMS</h2>
<table>
  <tr><th>TITLE</th><th>PUBLISHER</th><th>SENTIMENT</th><th>PUBLISHED</th></tr>
  {av_html}
</table>

<p style="margin-top:2rem;color:#333;font-size:0.65rem;">
  <a href="/">← back to digest</a>
</p>
</body></html>""", mimetype="text/html")


def _trigger_page(started=False, running=False):
    if running:
        msg = "A digest is already being generated. Check back in a minute."
        color = "#8a6f2e"
    else:
        msg = "Digest generation started. It takes about 30 seconds. Redirecting to digest..."
        color = "#22c55e"

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Generating...</title>
{"<meta http-equiv='refresh' content='35;url=/'>" if started else ""}
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>
  body {{ background:#0a0a0a; color:#e8e2d6; font-family:'IBM Plex Mono',monospace;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; text-align:center; }}
  .msg {{ color:{color}; font-size:0.8rem; letter-spacing:0.1em; max-width:400px; line-height:1.8; }}
  a {{ color:#c9a84c; }}
</style>
</head><body>
  <div>
    <div class="msg">{msg}</div>
    <p style="margin-top:1.5rem;font-size:0.65rem;color:#444">
      <a href="/stats">← back to stats</a>
    </p>
  </div>
</body></html>"""


def start_web_server():
    port = int(os.getenv("PORT", "8080"))
    logger.info("Web server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
