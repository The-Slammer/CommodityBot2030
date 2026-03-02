"""
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
    {"name": "Tim Dillon Show", "channel_id": "UC4woSp8ITBoYDmjkukhEhxg", "source_type": "style_reference", "credibility_tier": 1, "topics": ["macro", "commentary"], "post_window_utc": (0, 23), "style_reference": True, "poll_day": "sunday"},
]

ALPHAVANTAGE_SOURCES = [

    # =========================================================
    # OIL & GAS — XLE CONSTITUENTS (NYSE)
    # Ordered by XLE weight
    # =========================================================

    # Tier 1 — Mega caps
    {"name": "ExxonMobil (XOM)", "query_type": "ticker", "query_value": "XOM", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Chevron (CVX)", "query_type": "ticker", "query_value": "CVX", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "ConocoPhillips (COP)", "query_type": "ticker", "query_value": "COP", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Williams Companies (WMB)", "query_type": "ticker", "query_value": "WMB", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "SLB (SLB)", "query_type": "ticker", "query_value": "SLB", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "EOG Resources (EOG)", "query_type": "ticker", "query_value": "EOG", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Kinder Morgan (KMI)", "query_type": "ticker", "query_value": "KMI", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Baker Hughes (BKR)", "query_type": "ticker", "query_value": "BKR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Valero Energy (VLO)", "query_type": "ticker", "query_value": "VLO", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Phillips 66 (PSX)", "query_type": "ticker", "query_value": "PSX", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Marathon Petroleum (MPC)", "query_type": "ticker", "query_value": "MPC", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "ONEOK (OKE)", "query_type": "ticker", "query_value": "OKE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Targa Resources (TRGP)", "query_type": "ticker", "query_value": "TRGP", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "EQT Corp (EQT)", "query_type": "ticker", "query_value": "EQT", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Occidental Petroleum (OXY)", "query_type": "ticker", "query_value": "OXY", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Diamondback Energy (FANG)", "query_type": "ticker", "query_value": "FANG", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Halliburton (HAL)", "query_type": "ticker", "query_value": "HAL", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Devon Energy (DVN)", "query_type": "ticker", "query_value": "DVN", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Expand Energy (EXE)", "query_type": "ticker", "query_value": "EXE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Texas Pacific Land (TPL)", "query_type": "ticker", "query_value": "TPL", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Coterra Energy (CTRA)", "query_type": "ticker", "query_value": "CTRA", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "APA Corp (APA)", "query_type": "ticker", "query_value": "APA", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},

    # =========================================================
    # OIL & GAS — MICRO CAPS (NYSE-listed E&P)
    # =========================================================
    {"name": "Northern Oil and Gas (NOG)", "query_type": "ticker", "query_value": "NOG", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Comstock Resources (CRK)", "query_type": "ticker", "query_value": "CRK", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Tellurian (TELL)", "query_type": "ticker", "query_value": "TELL", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Genie Energy (GNE)", "query_type": "ticker", "query_value": "GNE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "W&T Offshore (WTI)", "query_type": "ticker", "query_value": "WTI", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Ring Energy (REI)", "query_type": "ticker", "query_value": "REI", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},


    # =========================================================
    # OIL & GAS — EXPANDED WATCHLIST (E&P, Royalties, Midstream)
    # =========================================================

    # Large/Mid-cap E&P additions
    {"name": "Ovintiv (OVV)", "query_type": "ticker", "query_value": "OVV", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Antero Resources (AR)", "query_type": "ticker", "query_value": "AR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Chord Energy (CHRD)", "query_type": "ticker", "query_value": "CHRD", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Matador Resources (MTDR)", "query_type": "ticker", "query_value": "MTDR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SM Energy (SM)", "query_type": "ticker", "query_value": "SM", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Murphy Oil (MUR)", "query_type": "ticker", "query_value": "MUR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Gulfport Energy (GPOR)", "query_type": "ticker", "query_value": "GPOR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Range Resources (RRC)", "query_type": "ticker", "query_value": "RRC", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "CNX Resources (CNX)", "query_type": "ticker", "query_value": "CNX", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Crescent Energy (CRGY)", "query_type": "ticker", "query_value": "CRGY", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Permian Resources (PR)", "query_type": "ticker", "query_value": "PR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Magnolia Oil & Gas (MGY)", "query_type": "ticker", "query_value": "MGY", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Talos Energy (TALO)", "query_type": "ticker", "query_value": "TALO", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Kosmos Energy (KOS)", "query_type": "ticker", "query_value": "KOS", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "SandRidge Energy (SD)", "query_type": "ticker", "query_value": "SD", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "California Resources (CRC)", "query_type": "ticker", "query_value": "CRC", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Viper Energy (VNOM)", "query_type": "ticker", "query_value": "VNOM", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Mach Natural Resources (MNR)", "query_type": "ticker", "query_value": "MNR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Infinity Natural Resources (INR)", "query_type": "ticker", "query_value": "INR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "BKV Corp (BKV)", "query_type": "ticker", "query_value": "BKV", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Venture Global (VG)", "query_type": "ticker", "query_value": "VG", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Amplify Energy (AMPY)", "query_type": "ticker", "query_value": "AMPY", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Sable Offshore (SOC)", "query_type": "ticker", "query_value": "SOC", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Diversified Energy (DEC)", "query_type": "ticker", "query_value": "DEC", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Gran Tierra Energy (GTE)", "query_type": "ticker", "query_value": "GTE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "VAALCO Energy (EGY)", "query_type": "ticker", "query_value": "EGY", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "HighPeak Energy (HPK)", "query_type": "ticker", "query_value": "HPK", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Vista Energy ADR (VIST)", "query_type": "ticker", "query_value": "VIST", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Baytex Energy (BTE)", "query_type": "ticker", "query_value": "BTE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Canadian Natural Resources (CNQ)", "query_type": "ticker", "query_value": "CNQ", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Woodside Energy (WDS)", "query_type": "ticker", "query_value": "WDS", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 1, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Tamboran Resources (TBN)", "query_type": "ticker", "query_value": "TBN", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["natural_gas", "company_event"], "track_earnings": True, "commodity": "natural_gas"},
    {"name": "Greenfire Resources (GFR)", "query_type": "ticker", "query_value": "GFR", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Granite Ridge Resources (GRNT)", "query_type": "ticker", "query_value": "GRNT", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Royalty & Income names
    {"name": "Black Stone Minerals (BSM)", "query_type": "ticker", "query_value": "BSM", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Dorchester Minerals (DMLP)", "query_type": "ticker", "query_value": "DMLP", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Landbridge Company (LB)", "query_type": "ticker", "query_value": "LB", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Cross Timbers Royalty (CRT)", "query_type": "ticker", "query_value": "CRT", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},

    # Smaller E&P
    {"name": "Prairie Operating (PROP)", "query_type": "ticker", "query_value": "PROP", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "TXO Partners (TXO)", "query_type": "ticker", "query_value": "TXO", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "natural_gas", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Evolution Petroleum (EPM)", "query_type": "ticker", "query_value": "EPM", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Riley Exploration Permian (REPX)", "query_type": "ticker", "query_value": "REPX", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},
    {"name": "Obsidian Energy (OBE)", "query_type": "ticker", "query_value": "OBE", "commodity_group": "oil_gas", "source_type": "equity_news", "credibility_tier": 2, "topics": ["oil", "company_event"], "track_earnings": True, "commodity": "oil"},

    # =========================================================
    # URANIUM — NYSE / NYSE American listed
    # Non-US listed (ASX, TSX, London) excluded — not in AV
    # =========================================================
    {"name": "Cameco (CCJ)", "query_type": "ticker", "query_value": "CCJ", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Uranium Energy Corp (UEC)", "query_type": "ticker", "query_value": "UEC", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Denison Mines (DNN)", "query_type": "ticker", "query_value": "DNN", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Energy Fuels (UUUU)", "query_type": "ticker", "query_value": "UUUU", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "NexGen Energy (NXE)", "query_type": "ticker", "query_value": "NXE", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 1, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "Ur-Energy (URG)", "query_type": "ticker", "query_value": "URG", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 2, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},
    {"name": "enCore Energy (EU)", "query_type": "ticker", "query_value": "EU", "commodity_group": "uranium", "source_type": "equity_news", "credibility_tier": 2, "topics": ["uranium", "company_event"], "track_earnings": True, "commodity": "uranium"},

    # Note: PDN, DYL, BMN, BOE (ASX), U-U (TSX), KAP (London/Kazakhstan),
    # CGN (HK), YCA (London) are not available via AlphaVantage.

    # =========================================================
    # TOPIC-BASED — broad market news
    # =========================================================
    {"name": "Energy Market News (Topic)", "query_type": "topic", "query_value": "energy_transportation", "commodity_group": "oil_gas", "source_type": "topic_news", "credibility_tier": 2, "topics": ["oil", "natural_gas"], "track_earnings": False, "commodity": None},
]

EARNINGS_TRACKED_TICKERS = [
    s["query_value"] for s in ALPHAVANTAGE_SOURCES
    if s.get("track_earnings") and s["query_type"] == "ticker"
]

TOPIC_TAXONOMY = ["oil", "natural_gas", "uranium", "nuclear", "macro", "company_event", "policy"]
