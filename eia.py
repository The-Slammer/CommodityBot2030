"""
eia.py — EIA structured data ingestion.

Polls three EIA API v2 endpoints on their release schedules:
  - Crude & Petroleum Inventories  (Wednesdays 10:30 AM EST)
  - Natural Gas Storage            (Thursdays 10:30 AM EST)
  - Drilling Productivity Report   (monthly, mid-month)

EIA API key is free at https://www.eia.gov/opendata/
Set env var: EIA_API_KEY

Data is stored in eia_reports table and surfaced in digest on release days
as a dedicated "Inventory" section with surprise indicator vs analyst consensus.
"""

import logging
import os
from datetime import datetime, timedelta

import requests

from database import insert_eia_report, get_latest_eia_report, get_recent_eia_reports

logger = logging.getLogger(__name__)

EIA_API_KEY = os.getenv("EIA_API_KEY", "")
EIA_BASE = "https://api.eia.gov/v2"


# ---------------------------------------------------------------------------
# Crude & Petroleum Inventories
# Series: PET.WCESTUS1.W  — US ending stocks of crude oil, weekly
# ---------------------------------------------------------------------------

def fetch_crude_inventories() -> dict | None:
    """
    Fetch latest weekly US crude oil inventory from EIA.
    Returns dict with value, previous, change, and surprise flag.
    """
    if not EIA_API_KEY:
        logger.warning("EIA_API_KEY not set — skipping crude inventory fetch")
        return None
    try:
        r = requests.get(
            f"{EIA_BASE}/petroleum/stoc/wstk/data/",
            params={
                "api_key": EIA_API_KEY,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[product][]": "EPC0",   # crude oil
                "facets[area][]": "NUS",        # national US
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 4,
                "offset": 0,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("response", {}).get("data", [])
        if len(data) < 2:
            return None

        latest = data[0]
        previous = data[1]
        current_val = float(latest["value"])       # millions of barrels
        prev_val = float(previous["value"])
        change = round(current_val - prev_val, 3)  # +/- million bbls

        result = {
            "report_type": "crude_inventory",
            "period": latest["period"],
            "value": current_val,
            "previous": prev_val,
            "change": change,
            "unit": "million barrels",
            "label": f"{'BUILD' if change > 0 else 'DRAW'} of {abs(change):.1f}M bbls",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        logger.info("Crude inventory: %s", result["label"])
        return result

    except Exception as e:
        logger.error("Crude inventory fetch failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Natural Gas Storage
# Series: NG.NW2_EPG0_SWO_R48_BCF.W — working gas in underground storage
# ---------------------------------------------------------------------------

def fetch_natgas_storage() -> dict | None:
    """Fetch latest weekly US natural gas storage from EIA."""
    if not EIA_API_KEY:
        logger.warning("EIA_API_KEY not set — skipping nat gas storage fetch")
        return None
    try:
        r = requests.get(
            f"{EIA_BASE}/natural-gas/stor/wkly/data/",
            params={
                "api_key": EIA_API_KEY,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[process][]": "SAB",     # working gas, total lower 48
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 4,
                "offset": 0,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("response", {}).get("data", [])
        if len(data) < 2:
            return None

        latest = data[0]
        previous = data[1]
        current_val = float(latest["value"])   # BCF
        prev_val = float(previous["value"])
        change = round(current_val - prev_val, 1)

        result = {
            "report_type": "natgas_storage",
            "period": latest["period"],
            "value": current_val,
            "previous": prev_val,
            "change": change,
            "unit": "BCF",
            "label": f"{'INJECTION' if change > 0 else 'WITHDRAWAL'} of {abs(change):.0f} BCF",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        logger.info("Nat gas storage: %s", result["label"])
        return result

    except Exception as e:
        logger.error("Nat gas storage fetch failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Drilling Productivity Report (monthly)
# Covers major US shale basins — Permian, Eagle Ford, Bakken, etc.
# ---------------------------------------------------------------------------

def fetch_drilling_productivity() -> dict | None:
    """Fetch latest DPR data — new well oil production per rig."""
    if not EIA_API_KEY:
        return None
    try:
        r = requests.get(
            f"{EIA_BASE}/petroleum/dpr/wells/data/",
            params={
                "api_key": EIA_API_KEY,
                "frequency": "monthly",
                "data[0]": "value",
                "facets[product][]": "oil",
                "facets[series][]": "drilled",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 2,
                "offset": 0,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("response", {}).get("data", [])
        if not data:
            return None

        latest = data[0]
        result = {
            "report_type": "drilling_productivity",
            "period": latest.get("period", ""),
            "value": float(latest.get("value", 0)),
            "previous": float(data[1].get("value", 0)) if len(data) > 1 else None,
            "change": None,
            "unit": "wells drilled",
            "label": f"Drilling productivity update — {latest.get('period','')}",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        if result["previous"]:
            result["change"] = round(result["value"] - result["previous"], 1)
        return result

    except Exception as e:
        logger.error("Drilling productivity fetch failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def poll_eia_crude():
    """Called Wednesdays at 15:30 UTC (10:30 AM EST)."""
    logger.info("=== EIA crude inventory poll ===")
    result = fetch_crude_inventories()
    if result:
        insert_eia_report(result)


def poll_eia_natgas():
    """Called Thursdays at 15:30 UTC (10:30 AM EST)."""
    logger.info("=== EIA nat gas storage poll ===")
    result = fetch_natgas_storage()
    if result:
        insert_eia_report(result)


def poll_eia_drilling():
    """Called monthly — 16th of each month at 16:00 UTC."""
    logger.info("=== EIA drilling productivity poll ===")
    result = fetch_drilling_productivity()
    if result:
        insert_eia_report(result)


def get_todays_eia_data() -> list:
    """
    Return any EIA reports published today or yesterday.
    Used by digest to add inventory section on release days.
    """
    return get_recent_eia_reports(hours=36)
