"""
config.py — All source definitions live here.
Add/remove feeds and channels without touching any other file.
"""

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
        "url": "https://uraniuminsider.substack.com/feed",  # Replace with private feed URL
        "source_type": "newsletter",
        "credibility_tier": 2,
        "topics": ["uranium"],
    },
    # --- Company IR Feeds ---
    {
        "name": "Cameco Investor Relations",
        "url": "https://www.cameco.com/invest/rss",
        "source_type": "company_ir",
        "credibility_tier": 3,  # Promotional — weighted lower
        "topics": ["uranium"],
    },
    {
        "name": "ExxonMobil Newsroom",
        "url": "https://corporate.exxonmobil.com/rss/news",
        "source_type": "company_ir",
        "credibility_tier": 3,
        "topics": ["oil", "natural_gas"],
    },
    {
        "name": "Chevron Newsroom",
        "url": "https://www.chevron.com/rss/news",
        "source_type": "company_ir",
        "credibility_tier": 3,
        "topics": ["oil", "natural_gas"],
    },
    {
        "name": "ConocoPhillips News",
        "url": "https://www.conocophillips.com/rss/news",
        "source_type": "company_ir",
        "credibility_tier": 3,
        "topics": ["oil", "natural_gas"],
    },
    {
        "name": "Pioneer Natural Resources",
        "url": "https://www.pxd.com/rss/news",
        "source_type": "company_ir",
        "credibility_tier": 3,
        "topics": ["oil"],
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
        "name": "Gulf Intelligence",
        "channel_id": "https://www.youtube.com/channel/UCa7Xz4oHMke7m2xxq_K1lhg",
        "source_type": "news_video",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas", "uranium", "macro"],
        # Expected posting window in UTC (hour, 24hr)
        "post_window_utc": (14, 16),
    },
    {
        "name": "Rule Investment Media",
        "channel_id": "https://www.youtube.com/channel/UCLReD7YczIpNz-gDIVF1hdQ",
        "source_type": "news_video",
        "credibility_tier": 2,
        "topics": ["oil", "natural_gas"],
        "post_window_utc": (13, 15),
    },
    {
        "name": "Uranium Insider",
        "channel_id": "https://www.youtube.com/channel/UCDmY09g5tiR0ocNXvEnOddg",
        "source_type": "company_channel",
        "credibility_tier": 3,
        "topics": ["uranium"],
        "post_window_utc": (15, 17),
    },
]


# Topic taxonomy — items must map to at least one of these
TOPIC_TAXONOMY = [
    "oil",
    "natural_gas",
    "uranium",
    "nuclear",
    "macro",          # Macro factors: rates, dollar, geopolitics
    "company_event",  # Earnings, M&A, production updates
    "policy",         # Regulation, permitting, sanctions
]
