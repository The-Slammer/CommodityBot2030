"""
web.py — Minimal Flask server that serves the latest digest.
Railway will expose this on whatever port is set in the PORT env var.
"""

import logging
import os
from datetime import datetime

from flask import Flask, Response

from database import get_latest_digest

logger = logging.getLogger(__name__)

app = Flask(__name__)

PLACEHOLDER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Daily Energy Jerkoff</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
    <style>
        body { background:#0a0a0a; color:#6b6560; font-family:'IBM Plex Mono',monospace;
               display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
        .wrap { text-align:center; }
        h1 { font-family:'Playfair Display',serif; font-size:3rem; color:#e8e2d6; margin-bottom:1rem; }
        h1 em { font-style:italic; color:#c9a84c; }
        p { font-size:0.7rem; letter-spacing:0.15em; text-transform:uppercase; }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>The Daily <em>Energy</em> Jerkoff</h1>
        <p>First edition publishes at 06:15 PST</p>
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


def start_web_server():
    port = int(os.getenv("PORT", "8080"))
    logger.info("Web server starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
