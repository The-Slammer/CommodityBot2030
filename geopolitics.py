"""
geopolitics.py — Nightly geopolitical brief generator.

Runs at 05:00 UTC (75 min before morning digest). Scans last 24h of ingested
news for geopolitical signals relevant to commodity prices, synthesizes them
into a structured brief stored in the DB. The morning digest injects this
brief into the Sonnet prompt as standing context.
"""

import json
import logging
import os
import requests
from datetime import datetime

from database import (
    get_av_items_since,
    get_last_24h_rss_items,
    insert_geopolitical_brief,
    get_latest_geopolitical_brief,
)

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def _collect_candidate_headlines(hours: int = 24) -> list:
    """Pull last N hours of AV and RSS items as headline candidates."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    av_items = get_av_items_since(cutoff)
    rss_items = get_last_24h_rss_items()

    candidates = []

    for item in av_items:
        title = item.get("title", "").strip()
        if title:
            candidates.append({
                "title": title,
                "source": item.get("source_publisher", ""),
                "sentiment": item.get("overall_sentiment_label", ""),
            })

    for item in rss_items:
        title = item.get("title", "").strip()
        if title:
            candidates.append({
                "title": title,
                "source": item.get("source_name", ""),
                "sentiment": "",
            })

    # Deduplicate by title
    seen = set()
    unique = []
    for c in candidates:
        if c["title"] not in seen:
            seen.add(c["title"])
            unique.append(c)

    return unique[:150]  # cap at 150 to stay within Haiku context


def _haiku_extract_geopolitical_signals(candidates: list) -> dict:
    """
    Haiku scans headlines and extracts geopolitical signals relevant to commodities.
    Returns structured dict with signals list and per-commodity impact assessments.
    """
    if not ANTHROPIC_API_KEY or not candidates:
        return {}

    headlines_text = "\n".join(
        f"  - {c['title']} ({c['source']})"
        for c in candidates
    )

    prompt = (
        "You are a geopolitical risk analyst specializing in commodity markets. "
        "Review these headlines from the last 24 hours and identify any geopolitical "
        "developments that could materially affect oil, natural gas, or uranium prices.\n\n"
        "Look specifically for:\n"
        "- OPEC+ production decisions, quotas, or member disagreements\n"
        "- Sanctions on energy-producing nations (Russia, Iran, Venezuela, others)\n"
        "- Conflict or instability near key chokepoints (Strait of Hormuz, Suez Canal, "
        "Bab-el-Mandeb, Black Sea, Strait of Malacca)\n"
        "- Pipeline attacks, infrastructure sabotage, or forced shutdowns\n"
        "- Strategic petroleum reserve releases or emergency stockpile actions\n"
        "- Diplomatic breakthroughs or breakdowns affecting energy trade\n"
        "- Sanctions relief or new sanctions affecting uranium supply\n"
        "- Extreme weather or natural disasters threatening production regions\n\n"
        "HEADLINES:\n" + headlines_text + "\n\n"
        "Respond ONLY in this exact JSON format, no other text:\n"
        "{\n"
        '  "signals_found": true,\n'
        '  "signals": [\n'
        '    {"headline": "brief description", "category": "opec|sanctions|conflict|infrastructure|diplomatic|weather|other", "commodity_relevance": ["oil","natural_gas","uranium"], "direction": "bullish|bearish|neutral", "severity": "high|medium|low"}\n'
        "  ],\n"
        '  "summary": "3-5 sentence synthesis of the geopolitical picture and what it means for commodity prices",\n'
        '  "commodity_impacts": {\n'
        '    "oil": "one sentence on geopolitical pressure on oil prices",\n'
        '    "natural_gas": "one sentence on geopolitical pressure on nat gas",\n'
        '    "uranium": "one sentence on geopolitical pressure on uranium"\n'
        "  }\n"
        "}\n\n"
        "If no meaningful geopolitical signals exist, set signals_found to false, "
        "signals to empty array, and write brief neutral assessments."
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
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        logger.error("Haiku geopolitical extraction failed: %s", e)
        return {}


def generate_geopolitical_brief():
    """
    Main entry point. Collects headlines, runs Haiku extraction,
    stores structured brief in DB.
    """
    logger.info("=== Geopolitical brief generation starting ===")

    candidates = _collect_candidate_headlines(hours=24)
    logger.info("Collected %d candidate headlines", len(candidates))

    if not candidates:
        logger.warning("No headlines available — skipping geopolitical brief")
        return

    result = _haiku_extract_geopolitical_signals(candidates)

    if not result:
        logger.warning("Haiku extraction returned empty — storing blank brief")
        result = {
            "signals_found": False,
            "signals": [],
            "summary": "No geopolitical data available.",
            "commodity_impacts": {
                "oil": "No geopolitical signals identified.",
                "natural_gas": "No geopolitical signals identified.",
                "uranium": "No geopolitical signals identified.",
            }
        }

    signals_found = result.get("signals_found", False)
    signal_count = len(result.get("signals", []))

    insert_geopolitical_brief({
        "date_str": datetime.utcnow().strftime("%Y-%m-%d"),
        "signals_found": 1 if signals_found else 0,
        "signal_count": signal_count,
        "signals": json.dumps(result.get("signals", [])),
        "summary": result.get("summary", ""),
        "commodity_impacts": json.dumps(result.get("commodity_impacts", {})),
        "generated_at": datetime.utcnow().isoformat(),
    })

    logger.info(
        "=== Geopolitical brief complete — signals_found: %s, count: %d ===",
        signals_found, signal_count
    )
