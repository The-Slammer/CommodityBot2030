"""
charts.py — Chart pages blueprint.
Routes: /charts/energy, /charts/gold-silver, /charts/copper, /charts/uranium
"""

import json
import logging
from flask import Blueprint, Response
from chart_data import get_all_timeframes

logger = logging.getLogger(__name__)
charts_bp = Blueprint("charts", __name__)

TIMEFRAME_LABELS = ["1M", "3M", "6M", "1Y"]

CHART_COLORS = {
    "WTI":         "#c9a84c",
    "NATURAL_GAS": "#60a5fa",
    "GOLD":        "#fbbf24",
    "SILVER":      "#94a3b8",
    "COPPER":      "#fb923c",
    "URNM":        "#34d399",
}

# Regular string — NOT an f-string — so JS braces don't need escaping
_JS_TEMPLATE = """
var rawData = __DATA__;
var colors  = __COLORS__;

function fmtDate(s) {
    var d = new Date(s + 'T00:00:00');
    return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
}

function buildChart(id, series, color) {
    var ctx = document.getElementById(id);
    if (!ctx || !series || !series.length) {
        var wrap = ctx ? ctx.parentElement : null;
        if (wrap) wrap.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:IBM Plex Mono,monospace;font-size:0.6rem;color:#333">No data yet</div>';
        return;
    }
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: series.map(function(p){ return fmtDate(p.date); }),
            datasets: [{
                data: series.map(function(p){ return p.value; }),
                borderColor: color,
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1a1a1a',
                    titleColor: '#9a9490',
                    bodyColor: '#e8e2d6',
                    borderColor: '#333',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: { color:'#555', font:{family:"IBM Plex Mono,monospace",size:9}, maxTicksLimit:6, maxRotation:0 },
                    grid: { color:'#1a1a1a' },
                    border: { color:'#222' }
                },
                y: {
                    position: 'right',
                    ticks: { color:'#555', font:{family:"IBM Plex Mono,monospace",size:9} },
                    grid: { color:'#1a1a1a' },
                    border: { color:'#222' }
                }
            }
        }
    });
}

Object.keys(rawData).forEach(function(symbol) {
    var tfs = rawData[symbol];
    var color = colors[symbol] || '#c9a84c';
    Object.keys(tfs).forEach(function(tf) {
        buildChart('chart-' + symbol + '-' + tf, tfs[tf], color);
    });
});
"""


def _build_page(page_title, commodities):
    chart_data = {c["symbol"]: get_all_timeframes(c["symbol"]) for c in commodities}
    js = _JS_TEMPLATE.replace("__DATA__", json.dumps(chart_data)).replace("__COLORS__", json.dumps(CHART_COLORS))

    sections_html = ""
    for c in commodities:
        cards = "".join(
            f'<div class="chart-card">'
            f'<div class="chart-tf-label">{tf}</div>'
            f'<div class="chart-wrap"><canvas id="chart-{c["symbol"]}-{tf}"></canvas></div>'
            f'</div>'
            for tf in TIMEFRAME_LABELS
        )
        sections_html += (
            f'<div class="commodity-block">'
            f'<h2 class="commodity-name">{c["label"]}</h2>'
            f'<div class="chart-grid">{cards}</div>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title} Charts — CommodityBot</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,900;1,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a0a;color:#e8e2d6;font-family:'IBM Plex Mono',monospace;min-height:100vh}}
.dev-banner{{background:#0d0d0d;border-bottom:1px solid #1a1a1a;padding:0.3rem clamp(1.5rem,5vw,4rem);text-align:center}}
.dev-banner span{{font-size:0.55rem;color:#444;letter-spacing:0.08em}}
.cb-nav{{background:#0f0f0f;border-bottom:1px solid #222;padding:0.6rem clamp(1.5rem,5vw,4rem);display:flex;gap:2rem;align-items:center;flex-wrap:wrap;position:relative;z-index:100}}
.cb-nav a,.cb-nav .dd-trigger{{font-size:0.65rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;cursor:pointer}}
.cb-nav .brand{{font-size:0.6rem;color:#c9a84c;letter-spacing:0.15em;text-transform:uppercase;font-weight:500}}
.cb-nav .ml-auto{{margin-left:auto}}
.dd{{position:relative;display:inline-block}}
.dd-trigger{{background:none;border:none;padding:0;font-family:'IBM Plex Mono',monospace}}
.dd-menu{{display:none;position:absolute;top:calc(100% + 6px);left:0;background:#111;border:1px solid #222;min-width:160px;z-index:200}}
.dd-menu a{{display:block;padding:0.5rem 1rem;font-size:0.62rem;color:#9a9490;text-decoration:none;letter-spacing:0.08em;border-bottom:1px solid #1a1a1a}}
.dd-menu a:last-child{{border-bottom:none}}
.dd-menu a:hover,.cb-nav a:hover,.dd-trigger:hover{{color:#e8e2d6}}
.dd:hover .dd-menu{{display:block}}
.price-strip{{background:#0a0a0a;border-bottom:1px solid #1a1a1a;padding:0.35rem clamp(1.5rem,5vw,4rem);font-size:0.6rem;color:#9a9490}}
.content{{max-width:1400px;margin:0 auto;padding:2rem clamp(1.5rem,5vw,4rem)}}
.page-title{{font-family:'Playfair Display',serif;font-size:1.8rem;color:#e8e2d6;margin-bottom:2rem}}
.page-title em{{color:#c9a84c;font-style:italic}}
.commodity-block{{margin-bottom:3.5rem}}
.commodity-name{{font-size:0.72rem;color:#c9a84c;letter-spacing:0.2em;text-transform:uppercase;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid #1e1e1e}}
.chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem}}
.chart-card{{background:#0e0e0e;border:1px solid #1e1e1e;padding:1rem}}
.chart-tf-label{{font-size:0.58rem;color:#444;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:0.6rem}}
.chart-wrap{{height:220px;position:relative}}
.disclaimer{{margin:2rem auto;padding:0 clamp(1.5rem,5vw,4rem)}}
.disclaimer-inner{{padding:0.85rem 1.1rem;border:1px solid #2a2a2a;font-size:0.58rem;color:#6b6560;line-height:1.7;letter-spacing:0.03em}}
@media(max-width:700px){{.chart-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="dev-banner"><span>CommodityBot is under continuous development — features are regularly tuned, expanded, and added.</span></div>
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
  <a href="/portfolio">Portfolio</a>
  <a href="/about">About</a>
  <a href="/stats" class="ml-auto">Stats →</a>
</nav>
<div class="content">
  <h1 class="page-title"><em>{page_title}</em></h1>
  {sections_html}
</div>
<div class="disclaimer">
  <div class="disclaimer-inner">
    <strong style="color:#9a9490">RESEARCH PURPOSES ONLY.</strong> CommodityBot is an automated research and data aggregation tool. Nothing published on this platform constitutes financial advice, investment advice, a trading recommendation, or a solicitation to buy or sell any security, commodity, or financial instrument. Always conduct your own due diligence and consult a licensed financial advisor before making any investment decisions.
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
{js}
</script>
</body>
</html>"""


@charts_bp.route("/charts/energy")
def charts_energy():
    return Response(_build_page("Energy", [
        {"symbol": "WTI",         "label": "Crude Oil (WTI)"},
        {"symbol": "NATURAL_GAS", "label": "Natural Gas (Henry Hub)"},
    ]), mimetype="text/html")


@charts_bp.route("/charts/gold-silver")
def charts_gold_silver():
    return Response(_build_page("Gold / Silver", [
        {"symbol": "GOLD",   "label": "Gold"},
        {"symbol": "SILVER", "label": "Silver"},
    ]), mimetype="text/html")


@charts_bp.route("/charts/copper")
def charts_copper():
    return Response(_build_page("Copper", [
        {"symbol": "COPPER", "label": "Copper"},
    ]), mimetype="text/html")


@charts_bp.route("/charts/uranium")
def charts_uranium():
    return Response(_build_page("Uranium", [
        {"symbol": "URNM", "label": "Uranium (URNM)"},
    ]), mimetype="text/html")
