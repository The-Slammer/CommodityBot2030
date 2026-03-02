"""
config.py — All source definitions.
"""

import os

RSS_FEEDS = ["""
config.py — All source definitions.
"""

import os

RSS_FEEDS = [
    # Verified working feeds only
    {"name": "World Nuclear News", "url": "https://www.world-nuclear-news.org/rss", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["uranium", "nuclear"]},
    {"name": "Uranium Insider (Substack)", "url": os.getenv("URANIUM_INSIDER_FEED", "https://uraniuminsider.substack.com/feed"), "source_type": "newsletter", "credibility_tier": 2, "topics": ["uranium"]},
    {"name": "OilPrice.com", "url": "https://oilprice.com/rss/main", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
    {"name": "Energy Monitor", "url": "https://www.energymonitor.ai/feed", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "nuclear"]},
    {"name": "Rigzone", "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
    # Removed (broken): S&P Global, Reuters Energy, Platts, Natural Gas Intelligence, EIA News
]

YOUTUBE_CHANNELS = [
    {"name": "Macro Voices", "channel_id": "UCG7K2qx9bMpHBiAJTHSRrxg", "source_type": "podcast", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 16)},
    {"name": "Bloomberg Television", "channel_id": "UCIALMKvObZNtJ6AmdCLP7Lg", "source_type": "news_video", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (13, 22)},
    {"name": "Rule Investment Media", "channel_id": "UCLReD7YczIpNz-gDIVF1hdQ", "source_type": "research_interview", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 18), "research_tier": True},
    {"name": "David Lin Report", "channel_id": "UClBMLpP3UHXLmgEypMmXPuA", "source_type": "research_interview", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 20), "research_tier": True},
    {"name": "Gareth Soloway", "channel_id": "UCwTu6kD2igaLMpxswtcdxlg", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "macro"], "post_window_utc": (14, 18)},
    {"name": "Verified Investing", "channel_id": "UCZ-J2m1AUSLnifUEKam5_dA", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "macro"], "post_window_utc": (14, 18)},
    {"name": "Clem Chambers", "channel_id": "UCZrMDqkXFpsuD5fSqreih8g", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "macro"], "post_window_utc": (14, 18)},
    {"name": "Kitco News", "channel_id": "UC9ijza42jVR3T6b8bColgvg", "source_type": "news_video", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (13, 20)},
    {"name": "Bravos Research", "channel_id": "UCOHxDwCcOzBaLkeTazanwcw", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium"], "post_window_utc": (14, 18)},
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
    # OIL & GAS — EXPANDED WATCHLIST (E&P, Royalties, Midstream)
    # =========================================================

    # Large/Mid-cap E&P additions
    {"name": "Ovintiv (OVV)", "query_type": "ticker", "query_value": "OVV", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Antero Resources (AR)", "query_type": "ticker", "query_value": "AR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Chord Energy (CHRD)", "query_type": "ticker", "query_value": "CHRD", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Matador Resources (MTDR)", "query_type": "ticker", "query_value": "MTDR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SM Energy (SM)", "query_type": "ticker", "query_value": "SM", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Murphy Oil (MUR)", "query_type": "ticker", "query_value": "MUR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Gulfport Energy (GPOR)", "query_type": "ticker", "query_value": "GPOR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Range Resources (RRC)", "query_type": "ticker", "query_value": "RRC", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "CNX Resources (CNX)", "query_type": "ticker", "query_value": "CNX", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Crescent Energy (CRGY)", "query_type": "ticker", "query_value": "CRGY", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Permian Resources (PR)", "query_type": "ticker", "query_value": "PR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Magnolia Oil & Gas (MGY)", "query_type": "ticker", "query_value": "MGY", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Talos Energy (TALO)", "query_type": "ticker", "query_value": "TALO", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Kosmos Energy (KOS)", "query_type": "ticker", "query_value": "KOS", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SandRidge Energy (SD)", "query_type": "ticker", "query_value": "SD", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "California Resources (CRC)", "query_type": "ticker", "query_value": "CRC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Viper Energy (VNOM)", "query_type": "ticker", "query_value": "VNOM", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Mach Natural Resources (MNR)", "query_type": "ticker", "query_value": "MNR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Infinity Natural Resources (INR)", "query_type": "ticker", "query_value": "INR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "BKV Corp (BKV)", "query_type": "ticker", "query_value": "BKV", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Venture Global (VG)", "query_type": "ticker", "query_value": "VG", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Amplify Energy (AMPY)", "query_type": "ticker", "query_value": "AMPY", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Sable Offshore (SOC)", "query_type": "ticker", "query_value": "SOC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Diversified Energy (DEC)", "query_type": "ticker", "query_value": "DEC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Gran Tierra Energy (GTE)", "query_type": "ticker", "query_value": "GTE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "VAALCO Energy (EGY)", "query_type": "ticker", "query_value": "EGY", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "HighPeak Energy (HPK)", "query_type": "ticker", "query_value": "HPK", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Vista Energy ADR (VIST)", "query_type": "ticker", "query_value": "VIST", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Baytex Energy (BTE)", "query_type": "ticker", "query_value": "BTE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Canadian Natural Resources (CNQ)", "query_type": "ticker", "query_value": "CNQ", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Woodside Energy (WDS)", "query_type": "ticker", "query_value": "WDS", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Tamboran Resources (TBN)", "query_type": "ticker", "query_value": "TBN", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Greenfire Resources (GFR)", "query_type": "ticker", "query_value": "GFR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Granite Ridge Resources (GRNT)", "query_type": "ticker", "query_value": "GRNT", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Royalty & Income names
    {"name": "Black Stone Minerals (BSM)", "query_type": "ticker", "query_value": "BSM", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Dorchester Minerals (DMLP)", "query_type": "ticker", "query_value": "DMLP", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Landbridge Company (LB)", "query_type": "ticker", "query_value": "LB", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Cross Timbers Royalty (CRT)", "query_type": "ticker", "query_value": "CRT", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Smaller E&P
    {"name": "Prairie Operating (PROP)", "query_type": "ticker", "query_value": "PROP", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "TXO Partners (TXO)", "query_type": "ticker", "query_value": "TXO", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Evolution Petroleum (EPM)", "query_type": "ticker", "query_value": "EPM", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Riley Exploration Permian (REPX)", "query_type": "ticker", "query_value": "REPX", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Obsidian Energy (OBE)", "query_type": "ticker", "query_value": "OBE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

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
    # Verified working feeds only
    {"name": "World Nuclear News", "url": "https://www.world-nuclear-news.org/rss", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["uranium", "nuclear"]},
    {"name": "Uranium Insider (Substack)", "url": os.getenv("URANIUM_INSIDER_FEED", "https://uraniuminsider.substack.com/feed"), "source_type": "newsletter", "credibility_tier": 2, "topics": ["uranium"]},
    {"name": "OilPrice.com", "url": "https://oilprice.com/rss/main", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
    {"name": "Energy Monitor", "url": "https://www.energymonitor.ai/feed", "source_type": "news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "nuclear"]},
    {"name": "Rigzone", "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx", "source_type": "trade_publication", "credibility_tier": 2, "topics": ["oil", "natural_gas"]},
    # Removed (broken): S&P Global, Reuters Energy, Platts, Natural Gas Intelligence, EIA News
]

YOUTUBE_CHANNELS = [
    {"name": "Macro Voices", "channel_id": "UCG7K2qx9bMpHBiAJTHSRrxg", "source_type": "podcast", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 16)},
    {"name": "Bloomberg Television", "channel_id": "UCIALMKvObZNtJ6AmdCLP7Lg", "source_type": "news_video", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (13, 22)},
    {"name": "Rule Investment Media", "channel_id": "UCLReD7YczIpNz-gDIVF1hdQ", "source_type": "podcast", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (14, 18)},
    {"name": "Gareth Soloway", "channel_id": "UCwTu6kD2igaLMpxswtcdxlg", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "macro"], "post_window_utc": (14, 18)},
    {"name": "Verified Investing", "channel_id": "UCZ-J2m1AUSLnifUEKam5_dA", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "macro"], "post_window_utc": (14, 18)},
    {"name": "Clem Chambers", "channel_id": "UCZrMDqkXFpsuD5fSqreih8g", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "macro"], "post_window_utc": (14, 18)},
    {"name": "Kitco News", "channel_id": "UC9ijza42jVR3T6b8bColgvg", "source_type": "news_video", "credibility_tier": 1, "topics": ["oil", "natural_gas", "uranium", "macro"], "post_window_utc": (13, 20)},
    {"name": "Bravos Research", "channel_id": "UCOHxDwCcOzBaLkeTazanwcw", "source_type": "analyst", "credibility_tier": 2, "topics": ["oil", "natural_gas", "uranium"], "post_window_utc": (14, 18)},
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
    # OIL & GAS — EXPANDED WATCHLIST (E&P, Royalties, Midstream)
    # =========================================================

    # Large/Mid-cap E&P additions
    {"name": "Ovintiv (OVV)", "query_type": "ticker", "query_value": "OVV", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Antero Resources (AR)", "query_type": "ticker", "query_value": "AR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Chord Energy (CHRD)", "query_type": "ticker", "query_value": "CHRD", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Matador Resources (MTDR)", "query_type": "ticker", "query_value": "MTDR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SM Energy (SM)", "query_type": "ticker", "query_value": "SM", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Murphy Oil (MUR)", "query_type": "ticker", "query_value": "MUR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Gulfport Energy (GPOR)", "query_type": "ticker", "query_value": "GPOR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Range Resources (RRC)", "query_type": "ticker", "query_value": "RRC", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "CNX Resources (CNX)", "query_type": "ticker", "query_value": "CNX", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Crescent Energy (CRGY)", "query_type": "ticker", "query_value": "CRGY", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Permian Resources (PR)", "query_type": "ticker", "query_value": "PR", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Magnolia Oil & Gas (MGY)", "query_type": "ticker", "query_value": "MGY", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Talos Energy (TALO)", "query_type": "ticker", "query_value": "TALO", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Kosmos Energy (KOS)", "query_type": "ticker", "query_value": "KOS", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SandRidge Energy (SD)", "query_type": "ticker", "query_value": "SD", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "California Resources (CRC)", "query_type": "ticker", "query_value": "CRC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Viper Energy (VNOM)", "query_type": "ticker", "query_value": "VNOM", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Mach Natural Resources (MNR)", "query_type": "ticker", "query_value": "MNR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Infinity Natural Resources (INR)", "query_type": "ticker", "query_value": "INR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "BKV Corp (BKV)", "query_type": "ticker", "query_value": "BKV", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Venture Global (VG)", "query_type": "ticker", "query_value": "VG", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Amplify Energy (AMPY)", "query_type": "ticker", "query_value": "AMPY", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Sable Offshore (SOC)", "query_type": "ticker", "query_value": "SOC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Diversified Energy (DEC)", "query_type": "ticker", "query_value": "DEC", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Gran Tierra Energy (GTE)", "query_type": "ticker", "query_value": "GTE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "VAALCO Energy (EGY)", "query_type": "ticker", "query_value": "EGY", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "HighPeak Energy (HPK)", "query_type": "ticker", "query_value": "HPK", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Vista Energy ADR (VIST)", "query_type": "ticker", "query_value": "VIST", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Baytex Energy (BTE)", "query_type": "ticker", "query_value": "BTE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Canadian Natural Resources (CNQ)", "query_type": "ticker", "query_value": "CNQ", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Woodside Energy (WDS)", "query_type": "ticker", "query_value": "WDS", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Tamboran Resources (TBN)", "query_type": "ticker", "query_value": "TBN", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Greenfire Resources (GFR)", "query_type": "ticker", "query_value": "GFR", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Granite Ridge Resources (GRNT)", "query_type": "ticker", "query_value": "GRNT", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Royalty & Income names
    {"name": "Black Stone Minerals (BSM)", "query_type": "ticker", "query_value": "BSM", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Dorchester Minerals (DMLP)", "query_type": "ticker", "query_value": "DMLP", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Landbridge Company (LB)", "query_type": "ticker", "query_value": "LB", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Cross Timbers Royalty (CRT)", "query_type": "ticker", "query_value": "CRT", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Smaller E&P
    {"name": "Prairie Operating (PROP)", "query_type": "ticker", "query_value": "PROP", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "TXO Partners (TXO)", "query_type": "ticker", "query_value": "TXO", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Evolution Petroleum (EPM)", "query_type": "ticker", "query_value": "EPM", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Riley Exploration Permian (REPX)", "query_type": "ticker", "query_value": "REPX", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Obsidian Energy (OBE)", "query_type": "ticker", "query_value": "OBE", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

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
