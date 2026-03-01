"""
sec.py — SEC EDGAR 8-K filing monitor for tracked equities.

Uses EDGAR's free RSS feed per company CIK.
No API key required.

Flow:
  1. Maintain CIK map for all tracked tickers (fetched from EDGAR company search)
  2. Poll each company's EDGAR RSS feed every 60 min (same cycle as AV)
  3. Filter for 8-K, 10-Q, 10-K filings
  4. Fetch filing summary (Item descriptions from 8-K header)
  5. Store in sec_filings table
  6. Flag high-priority items (production updates, asset sales, guidance changes)
  7. Feeding into equity sentiment as a high-weight signal

8-K Item numbers we care about most:
  2.02 — Results of Operations (earnings release)
  7.01 — Regulation FD (guidance, investor day)
  8.01 — Other Events (material events)
  1.01 — Material Definitive Agreement (M&A, JV)
  2.01 — Completion of Acquisition/Disposition
"""

import json
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

from database import (
    insert_sec_filing,
    is_sec_filing_stored,
    get_recent_sec_filings,
    get_cik_for_ticker,
    upsert_cik,
)

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://www.sec.gov"
EDGAR_HEADERS = {
    "User-Agent": "CommodityBot research@commoditybot.ai",  # EDGAR requires user-agent
    "Accept-Encoding": "gzip, deflate",
}

# 8-K items we flag as high priority
HIGH_PRIORITY_ITEMS = {
    "1.01": "Material Agreement",
    "2.01": "Acquisition/Disposition",
    "2.02": "Earnings Release",
    "7.01": "Regulation FD / Guidance",
    "8.01": "Material Event",
}

# Hardcoded CIK map for our tracked tickers
# CIK = Central Index Key, EDGAR's company identifier
TICKER_CIK_MAP = {
    "XOM":  "0000034088",
    "CVX":  "0000093410",
    "COP":  "0001163165",
    "WMB":  "0000107263",
    "SLB":  "0000087347",
    "EOG":  "0000821189",
    "KMI":  "0001110805",
    "BKR":  "0001701605",
    "VLO":  "0001035002",
    "PSX":  "0001534992",
    "MPC":  "0001510295",
    "OKE":  "0001039684",
    "TRGP": "0001389170",
    "EQT":  "0000019617",
    "OXY":  "0000797468",
    "FANG": "0001539838",
    "HAL":  "0000045012",
    "DVN":  "0001090012",
    "EXE":  "0000895456",
    "TPL":  "0097476",
    "CTRA": "0000858470",
    "APA":  "0000006769",
    "NOG":  "0001104485",
    "CRK":  "0000023632",
    "TELL": "0001538822",
    "GNE":  "0001472468",
    "WTI":  "0000858655",
    "REI":  "0001581552",
    "CCJ":  "0000016160",
    "UEC":  "0001334978",
    "DNN":  "0000049600",
    "UUUU": "0000049600",
    "NXE":  "0001560327",
    "URG":  "0001375365",
    "EU":   "0001522767",
}


def _fetch_edgar_rss(cik: str, filing_type: str = "8-K") -> list:
    """
    Fetch EDGAR RSS feed for a company's recent filings.
    Returns list of filing dicts.
    """
    url = (
        f"{EDGAR_BASE}/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik}&type={filing_type}"
        f"&dateb=&owner=include&count=5&search_text=&output=atom"
    )
    try:
        r = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        filings = []
        for entry in entries:
            title = entry.findtext("atom:title", default="", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            updated = entry.findtext("atom:updated", default="", namespaces=ns)
            filing_id = entry.findtext("atom:id", default="", namespaces=ns)
            filings.append({
                "title": title,
                "url": link,
                "filed_at": updated[:10] if updated else "",
                "filing_id": filing_id,
            })
        return filings
    except Exception as e:
        logger.debug("EDGAR RSS fetch failed for CIK %s: %s", cik, e)
        return []


def _fetch_8k_items(filing_url: str) -> list:
    """
    Fetch the filing index page and extract 8-K item numbers.
    Returns list of item strings like ['2.02', '8.01'].
    """
    try:
        # Convert filing URL to index URL
        index_url = filing_url.replace("/Archives/edgar/data/", "/Archives/edgar/data/")
        r = requests.get(index_url, headers=EDGAR_HEADERS, timeout=15)
        r.raise_for_status()
        text = r.text

        items = []
        import re
        # Look for "Item X.XX" patterns in the filing header
        matches = re.findall(r"Item\s+(\d+\.\d+)", text, re.IGNORECASE)
        for m in matches:
            if m in HIGH_PRIORITY_ITEMS:
                items.append(m)
        return list(set(items))
    except Exception:
        return []


def _is_high_priority(items: list) -> bool:
    return any(item in HIGH_PRIORITY_ITEMS for item in items)


def poll_sec_filings(tickers: list[str]):
    """
    Poll EDGAR for recent 8-K, 10-Q, 10-K filings for all tracked tickers.
    Called on the same 60-min cycle as AlphaVantage.
    """
    cutoff = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    new_count = 0

    for ticker in tickers:
        cik = TICKER_CIK_MAP.get(ticker)
        if not cik:
            continue

        for filing_type in ["8-K", "10-Q"]:
            filings = _fetch_edgar_rss(cik, filing_type)
            for f in filings:
                if f["filed_at"] < cutoff:
                    continue
                if is_sec_filing_stored(f["filing_id"]):
                    continue

                # For 8-Ks, try to extract item numbers
                items = []
                priority = False
                if filing_type == "8-K" and f["url"]:
                    items = _fetch_8k_items(f["url"])
                    priority = _is_high_priority(items)

                item_labels = [
                    HIGH_PRIORITY_ITEMS.get(i, i) for i in items
                ]

                record = {
                    "ticker": ticker,
                    "cik": cik,
                    "filing_type": filing_type,
                    "filing_id": f["filing_id"],
                    "title": f["title"],
                    "url": f["url"],
                    "filed_at": f["filed_at"],
                    "items": json.dumps(items),
                    "item_labels": json.dumps(item_labels),
                    "high_priority": 1 if priority else 0,
                    "ingested_at": datetime.utcnow().isoformat(),
                }
                insert_sec_filing(record)
                new_count += 1

                if priority:
                    logger.info(
                        "HIGH PRIORITY 8-K: %s — %s (%s)",
                        ticker, ", ".join(item_labels), f["filed_at"]
                    )

    logger.info("SEC poll complete — %d new filings", new_count)


def get_todays_sec_filings(hours: int = 36) -> list:
    """Return recent high-priority SEC filings for digest injection."""
    return get_recent_sec_filings(hours=hours, high_priority_only=True)
