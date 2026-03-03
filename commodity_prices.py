import logging, os, time
import requests
from database import insert_commodity_price, get_latest_commodity_price

logger = logging.getLogger(__name__)
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
AV_BASE = "https://www.alphavantage.co/query"

COMMODITY_SYMBOLS = [
    {"symbol": "WTI", "av_function": "WTI", "extra_params": {"interval": "daily"}, "response_type": "commodity"},
    {"symbol": "NATURAL_GAS", "av_function": "NATURAL_GAS", "extra_params": {"interval": "daily"}, "response_type": "commodity"},
    {"symbol": "URNM", "av_function": "GLOBAL_QUOTE", "extra_params": {"symbol": "URNM"}, "response_type": "quote"}
    {"symbol": "GOLD", "av_function": "GOLD", "extra_params": {"interval": "daily"}, "response_type": "commodity"},
    {"symbol": "SILVER", "av_function": "SILVER", "extra_params": {"interval": "daily"}, "response_type": "commodity"},
    {"symbol": "COPPER", "av_function": "COPPER", "extra_params": {"interval": "daily"}, "response_type": "commodity"},
]

def _fetch_price(config):
    try:
        params = {"function": config["av_function"], "apikey": ALPHAVANTAGE_API_KEY}
        params.update(config.get("extra_params", {}))
        r = requests.get(AV_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.warning("AV rate limit hit fetching %s", config["symbol"])
            return None
        if config["response_type"] == "commodity":
            val = data.get("data", [{}])[0].get("value", 0)
        else:
            val = data.get("Global Quote", {}).get("05. price", 0)
        price = float(val) if val else None
        return price if price and price > 0 else None
    except Exception as e:
        logger.error("Price fetch failed for %s: %s", config["symbol"], e)
        return None

def poll_commodity_prices():
    if not ALPHAVANTAGE_API_KEY:
        logger.warning("ALPHAVANTAGE_API_KEY not set")
        return
    logger.info("=== Commodity price poll starting ===")
    success, failed = 0, 0
    for i, config in enumerate(COMMODITY_SYMBOLS):
        if i > 0:
            time.sleep(15)
        symbol = config["symbol"]
        price = _fetch_price(config)
        if price:
            insert_commodity_price(symbol, price)
            logger.info("Price stored: %s = %.4f", symbol, price)
            success += 1
        else:
            last = get_latest_commodity_price(symbol)
            if last:
                logger.warning("Price fetch failed for %s -- last known: %.4f (from %s)", symbol, last["price"], last["polled_at"][:16])
            else:
                logger.warning("Price fetch failed for %s -- no historical price in DB", symbol)
            failed += 1
    logger.info("=== Commodity price poll complete: %d ok, %d failed ===", success, failed)
