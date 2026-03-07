@app.route("/diag/earnings")
def diag_earnings():
    """Diagnostic endpoint — surfaces earnings pipeline health."""
    try:
        from earnings import get_earnings_diagnostics
        data = get_earnings_diagnostics()
    except Exception as e:
        return {"error": str(e)}, 500

    def status_color(ok):
        return "#22c55e" if ok else "#ef4444"

    watch_rows_html = "".join(f"""
        <tr>
            <td style="color:#e8e2d6;font-family:'IBM Plex Mono',monospace">{r['ticker']}</td>
            <td>{r['report_date']}</td>
            <td>{r['days_until']}</td>
            <td style="color:{'#22c55e' if r['in_watch'] else '#6b6560'}">{'YES' if r['in_watch'] else 'no'}</td>
            <td>{r['fiscal_quarter']}</td>
            <td style="color:#6b6560;font-size:0.6rem">{(r['updated_at'] or '')[:16]}</td>
        </tr>""" for r in data.get("all_watch_rows", [])
    ) or "<tr><td colspan='6' style='color:#6b6560'>No earnings watch rows — calendar may not have run yet</td></tr>"

    transcript_rows_html = "".join(f"""
        <tr>
            <td style="color:#e8e2d6;font-family:'IBM Plex Mono',monospace">{t['ticker']}</td>
            <td>{t['fiscal_quarter']}</td>
            <td>{t['report_date']}</td>
            <td style="color:{'#22c55e' if (t['sentiment_score'] or 0) > 0 else '#ef4444'}">{t['sentiment_score']:.3f}</td>
            <td style="color:#6b6560;font-size:0.6rem">{(t['generated_at'] or '')[:16]}</td>
        </tr>""" for t in data.get("recent_transcripts", [])
    ) or "<tr><td colspan='5' style='color:#6b6560'>No transcripts stored — check AV entitlement for EARNINGS_CALL_TRANSCRIPT</td></tr>"

    def key_badge(ok):
        c = "#22c55e" if ok else "#ef4444"
        label = "SET" if ok else "MISSING"
        return f'<span style="border:1px solid {c};color:{c};font-family:IBM Plex Mono,monospace;font-size:0.6rem;padding:0.15rem 0.5rem">{label}</span>'

    return Response(f"""<!DOCTYPE html>
<html><head><title>Earnings Diagnostic</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;font-size:13px;padding:2rem}}
h1{{color:#c9a84c;font-size:0.9rem;letter-spacing:0.2em;margin-bottom:1.5rem}}
h2{{color:#c9a84c;font-size:0.72rem;letter-spacing:0.15em;margin:2rem 0 0.75rem;border-bottom:1px solid #222;padding-bottom:0.4rem}}
.keys{{display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:2rem}}
.key-card{{background:#111;border:1px solid #222;padding:0.75rem 1.25rem}}
.key-card .kl{{font-size:0.58rem;color:#6b6560;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.4rem}}
table{{width:100%;border-collapse:collapse;max-width:900px;margin-bottom:1rem}}
th{{text-align:left;color:#444;font-size:0.6rem;letter-spacing:0.1em;padding:0.4rem;border-bottom:1px solid #222;text-transform:uppercase}}
td{{padding:0.4rem;border-bottom:1px solid #111;color:#9a9490;font-size:0.65rem}}
a{{color:#c9a84c;text-decoration:none}}
</style></head>
<body>
<h1>EARNINGS PIPELINE DIAGNOSTIC</h1>
<p style="color:#6b6560;font-size:0.65rem;margin-bottom:1.5rem">{data['checked_at']}</p>

<div class="keys">
    <div class="key-card"><div class="kl">AlphaVantage Key</div>{key_badge(data['av_key_set'])}</div>
    <div class="key-card"><div class="kl">Anthropic Key</div>{key_badge(data['anthropic_key_set'])}</div>
    <div class="key-card"><div class="kl">Finnhub Key</div>{key_badge(data['finnhub_key_set'])}</div>
    <div class="key-card"><div class="kl">Active Watch</div><div style="font-size:1.2rem;color:#e8e2d6">{data['watch_list_active']}</div></div>
    <div class="key-card"><div class="kl">Transcripts (14d)</div><div style="font-size:1.2rem;color:#e8e2d6">{data['transcripts_14d']}</div></div>
</div>

<h2>EARNINGS WATCH TABLE</h2>
<table>
    <tr><th>Ticker</th><th>Report Date</th><th>Days Until</th><th>In Watch</th><th>Fiscal Quarter</th><th>Updated</th></tr>
    {watch_rows_html}
</table>

<h2>RECENT TRANSCRIPTS (14d)</h2>
<table>
    <tr><th>Ticker</th><th>Quarter</th><th>Report Date</th><th>Sentiment</th><th>Stored At</th></tr>
    {transcript_rows_html}
</table>

<p style="margin-top:1.5rem;font-size:0.62rem;color:#444">
    If watch table is empty: earnings calendar job has not run or AV returned no matches.<br>
    If transcripts are empty: AV EARNINGS_CALL_TRANSCRIPT likely requires premium entitlement — check /diag/av.
</p>
<p style="margin-top:0.75rem"><a href="/stats">← Back to Stats</a></p>
</body></html>""", mimetype="text/html")
