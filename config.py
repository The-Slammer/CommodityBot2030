"""
config.py — All source definitions live here.
Add/remove feeds and channels without touching any other file.

Company IR feeds have been removed — those companies are now
queried directly via AlphaVantage NEWS_SENTIMENT for better
coverage and pre-scored sentiment data.
"""

import os

RSS_FEEDS = [
    # --- Market & Data Sources ---
    {
        "name": "S&P Global Commodity Insights",
        "url": "https://www.spglobal.com/commodityinsights/rss",
        "source_type": "market_data",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "uranium"],
    },
    {
        "name": "Reuters Energy",
        "url": "https://feeds.reuters.com/reuters/energyNews",
        "source_type": "news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "uranium"],
    },
    {
        "name": "Platts Oil News",
        "url": "https://www.spglobal.com/platts/rss/oil",
        "source_type": "market_data",
        "credibility_tier": 1,
        "topics": ["oil"],
    },
    # --- Uranium / Nuclear Specific ---
    {
        "name": "World Nuclear News",
        "url": "https://www.world-nuclear-news.org/rss",
        "source_type": "trade_publication",
        "credibility_tier": 2,
        "topics": ["uranium", "nuclear"],
    },
    {
        "name": "Uranium Insider (Substack)",
        "url": os.getenv("URANIUM_INSIDER_FEED", "https://uraniuminsider.substack.com/feed"),
        "source_type": "newsletter",
        "credibility_tier": 2,
        "topics": ["uranium"],
    },
    # --- General Energy News ---
    {
        "name": "OilPrice.com",
        "url": "https://oilprice.com/rss/main",
        "source_type": "news",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas"],
    },
    {
        "name": "Natural Gas Intelligence",
        "url": "https://www.naturalgasintel.com/rss",
        "source_type": "trade_publication",
        "credibility_tier": 1,
        "topics": ["natural_gas"],
    },
    {
        "name": "Energy Monitor",
        "url": "https://www.energymonitor.ai/feed",
        "source_type": "news",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas", "uranium", "nuclear"],
    },
    {
        "name": "EIA News",
        "url": "https://www.eia.gov/rss/news.xml",
        "source_type": "government",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "uranium"],
    },
    {
        "name": "Rigzone",
        "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
        "source_type": "trade_publication",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas"],
    },
]


YOUTUBE_CHANNELS = [
    {
        "name": "Macro Voices",
        "channel_id": "UCG7K2qx9bMpHBiAJTHSRrxg",
        "source_type": "podcast",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas", "uranium", "macro"],
        "post_window_utc": (14, 16),
    },
    {
        "name": "Energy News Beat",
        "channel_id": "UCaaa_replace_with_real_id",
        "source_type": "news_video",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas"],
        "post_window_utc": (13, 15),
    },
    {
        "name": "Uranium Royalties Channel",
        "channel_id": "UCbbb_replace_with_real_id",
        "source_type": "company_channel",
        "credibility_tier": 3,
        "topics": ["uranium"],
        "post_window_utc": (15, 17),
    },
]


# ---------------------------------------------------------------------------
# AlphaVantage NEWS_SENTIMENT sources
# ---------------------------------------------------------------------------
# Two query types:
#   ticker  — news for a specific equity (XOM, CVX, etc.)
#   topic   — broad topic-based news feed
#
# Each entry = 1 API call per poll cycle.
# AV free tier: 25 calls/day. Premium: much higher.
# At 30-min polling with 11 sources = ~528 calls/day — needs premium.
# To stay on free tier, increase poll interval to 6hrs in jobs.py
# or reduce source count.
# ---------------------------------------------------------------------------

ALPHAVANTAGE_SOURCES = [
    # --- Major Oil & Gas Equities ---
    {
        "name": "ExxonMobil (XOM)",
        "query_type": "ticker",
        "query_value": "XOM",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "company_event"],
    },
    {
        "name": "Chevron (CVX)",
        "query_type": "ticker",
        "query_value": "CVX",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "company_event"],
    },
    {
        "name": "ConocoPhillips (COP)",
        "query_type": "ticker",
        "query_value": "COP",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "company_event"],
    },
    {
        "name": "Occidental Petroleum (OXY)",
        "query_type": "ticker",
        "query_value": "OXY",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "company_event"],
    },
    {
        "name": "EOG Resources (EOG)",
        "query_type": "ticker",
        "query_value": "EOG",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["oil", "natural_gas", "company_event"],
    },
    # --- Uranium Equities ---
    {
        "name": "Cameco (CCJ)",
        "query_type": "ticker",
        "query_value": "CCJ",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["uranium", "company_event"],
    },
    {
        "name": "Uranium Energy Corp (UEC)",
        "query_type": "ticker",
        "query_value": "UEC",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["uranium", "company_event"],
    },
    {
        "name": "Denison Mines (DNN)",
        "query_type": "ticker",
        "query_value": "DNN",
        "source_type": "equity_news",
        "credibility_tier": 1,
        "topics": ["uranium", "company_event"],
    },
    {
        "name": "W&T Offshore (WTI)",
        "query_type": "ticker",
        "query_value": "WTI",
        "source_type": "equity_news",
        "credibility_tier": 2,
        "topics": ["oil", "company_event"],
    },
    {
        "name": "Ring Energy (REI)",
        "query_type": "ticker",
        "query_value": "REI",
        "source_type": "equity_news",
        "credibility_tier": 2,
        "topics": ["oil", "company_event"],
    },
    # --- Topic-Based Commodity News ---
    {
        "name": "Energy Market News (Topic)",
        "query_type": "topic",
        "query_value": "energy_transportation",
        "source_type": "topic_news",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas"],
    },
]


# Topic taxonomy — items must map to at least one of these
TOPIC_TAXONOMY = [
    "oil",
    "natural_gas",
    "uranium",
    "nuclear",
    "macro",
    "company_event",
    "policy",
]
