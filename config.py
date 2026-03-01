"""
config.py — All source definitions.
"""

import os

RSS_FEEDS = [
    {"name": "S&P Global Commodity Insights", "url": "https://www.spglobal.com/commodityinsights/rss", "source_type": "market_data", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium"]},
    {"name": "Reuters Energy", "url": "https://feeds.reuters.com/reuters/energyNews", "source_type": "news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium"]},
    {"name": "Platts Oil News", "url": "https://www.spglobal.com/platts/rss/oil", "source_type": "market_data", "credibility_tier": 1, "topics": ["oil"]},
    {"name": "World Nuclear News", "url": "https://www.world-nuclear-news.org/rss", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["uranium", "nuclear"]},
    {"name": "Uranium Insider (Substack)", "url": os.getenv("URANIUM_INSIDER_FEED", "https://uraniuminsider.substack.com/feed"), "source_type": "newsletter", "credibility_tier": 2, "topics": ["uranium"]},
    {"name": "OilPrice.com", "url": "https://oilprice.com/rss/main", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
    {"name": "Natural Gas Intelligence", "url": "https://www.naturalgasintel.com/rss", "source_type": "trade_publication", "credibility_tier": 1, "topics": ["natural_gas"]},
    {"name": "Energy Monitor", "url": "https://www.energymonitor.ai/feed", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "nuclear"]},
    {"name": "EIA News", "url": "https://www.eia.gov/rss/news.xml", "source_type": "government", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium"]},
    {"name": "Rigzone", "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
]

YOUTUBE_CHANNELS = [
    {"name": "Macro Voices", "channel_id": "UCG7K2qx9bMpHBiAJTHSRrxg", "source_type": "podcast", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 16)},
    {"name": "Energy News Beat", "channel_id": "UCaaa_replace_with_real_id", "source_type": "news_video", "credibility_tier": 2, "topics": ["oil", "natural_gas"], "post_window_utc": (13, 15)},
    {"name": "Uranium Royalties Channel", "channel_id": "UCbbb_replace_with_real_id", "source_type": "company_channel", "credibility_tier": 3, "topics": ["uranium"], "post_window_utc": (15, 17)},
]

ALPHAVANTAGE_SOURCES = [

    # =========================================================
    # OIL & GAS — XLE CONSTITUENTS (NYSE)
    # Ordered by XLE weight
    # =========================================================

    # Tier 1 — Mega caps
    {"name": "ExxonMobil (XOM)", "query_type": "ticker", "query_value": "XOM", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Chevron (CVX)", "query_type": "ticker", "query_value": "CVX", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "ConocoPhillips (COP)", "query_type": "ticker", "query_value": "COP", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Williams Companies (WMB)", "query_type": "ticker", "query_value": "WMB", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "SLB (SLB)", "query_type": "ticker", "query_value": "SLB", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "EOG Resources (EOG)", "query_type": "ticker", "query_value": "EOG", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Kinder Morgan (KMI)", "query_type": "ticker", "query_value": "KMI", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Baker Hughes (BKR)", "query_type": "ticker", "query_value": "BKR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Valero Energy (VLO)", "query_type": "ticker", "query_value": "VLO", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Phillips 66 (PSX)", "query_type": "ticker", "query_value": "PSX", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Marathon Petroleum (MPC)", "query_type": "ticker", "query_value": "MPC", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "ONEOK (OKE)", "query_type": "ticker", "query_value": "OKE", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Targa Resources (TRGP)", "query_type": "ticker", "query_value": "TRGP", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "EQT Corp (EQT)", "query_type": "ticker", "query_value": "EQT", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Occidental Petroleum (OXY)", "query_type": "ticker", "query_value": "OXY", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Diamondback Energy (FANG)", "query_type": "ticker", "query_value": "FANG", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Halliburton (HAL)", "query_type": "ticker", "query_value": "HAL", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Devon Energy (DVN)", "query_type": "ticker", "query_value": "DVN", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Expand Energy (EXE)", "query_type": "ticker", "query_value": "EXE", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Texas Pacific Land (TPL)", "query_type": "ticker", "query_value": "TPL", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Coterra Energy (CTRA)", "query_type": "ticker", "query_value": "CTRA", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "APA Corp (APA)", "query_type": "ticker", "query_value": "APA", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},

    # =========================================================
    # OIL & GAS — MICRO CAPS (NYSE-listed E&P)
    # =========================================================
    {"name": "Northern Oil and Gas (NOG)", "query_type": "ticker", "query_value": "NOG", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Comstock Resources (CRK)", "query_type": "ticker", "query_value": "CRK", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Tellurian (TELL)", "query_type": "ticker", "query_value": "TELL", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Genie Energy (GNE)", "query_type": "ticker", "query_value": "GNE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "W&T Offshore (WTI)", "query_type": "ticker", "query_value": "WTI", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Ring Energy (REI)", "query_type": "ticker", "query_value": "REI", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

    # =========================================================
    # URANIUM — NYSE / NYSE American listed
    # Non-US listed (ASX, TSX, London) excluded — not in AV
    # =========================================================
    {"name": "Cameco (CCJ)", "query_type": "ticker", "query_value": "CCJ", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Uranium Energy Corp (UEC)", "query_type": "ticker", "query_value": "UEC", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Denison Mines (DNN)", "query_type": "ticker", "query_value": "DNN", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Energy Fuels (UUUU)", "query_type": "ticker", "query_value": "UUUU", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "NexGen Energy (NXE)", "query_type": "ticker", "query_value": "NXE", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Ur-Energy (URG)", "query_type": "ticker", "query_value": "URG", "source_type": "equity_news", "credibility_tier": 2, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "enCore Energy (EU)", "query_type": "ticker", "query_value": "EU", "source_type": "equity_news", "credibility_tier": 2, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},

    # Note: PDN, DYL, BMN, BOE (ASX), U-U (TSX), KAP (London/Kazakhstan),
    # CGN (HK), YCA (London) are not available via AlphaVantage.

    # =========================================================
    # TOPIC-BASED — broad market news
    # =========================================================
    {"name": "Energy Market News (Topic)", "query_type": "topic", "query_value": "energy_transportation", "source_type": "topic_news", "credibility_tier": 2, "topics": ["oil", "natural_gas"], "track_earnings": False, "commodity": None},
]

EARNINGS_TRACKED_TICKERS = [
    s["query_value"] for s in ALPHAVANTAGE_SOURCES
    if s.get("track_earnings") and s["query_type"] == "ticker"
]

TOPIC_TAXONOMY = ["oil", "natural_gas", "uranium", "nuclear", "macro", "company_event", "policy"]
