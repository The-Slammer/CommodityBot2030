"""
trading.py — Paper trading decision engine.

Capital: $5,000 pool
Max positions: 5
Min position size: $500
Position sizing: conviction-weighted by composite score + momentum

Trading windows (ET):
  09:45 — Morning open (post-volatility settle)
  12:00 — Midday
  15:30 — Pre-close

Entry criteria:
  - Strong Buy (score >= 0.5) OR
  - Accelerating Buy: score >= 0.15 with score_delta >= 0.08 over last 2 recalcs

Exit criteria:
  - Score drops to Neutral (< 0.15) = hard exit
  - Score in Buy range but momentum_delta negative for 2 consecutive windows = soft exit
  - Displaced by stronger signal when slots full (weakest position by combined_score evicted)

Displacement:
  combined_score = current_composite * 0.6 + unrealised_return_pct * 0.4
  (positions with strong P&L buffer are protected from easy displacement)

Settlement: EOD closing price via AlphaVantage TIME_SERIES_DAILY
"""

import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from database import (
    get_equity_sentiment_all,
    get_open_positions,
    insert_position,
    close_position,
    get_position_score_history,
    insert_score_snapshot,
    get_portfolio_summary,
    update_position_price,
    get_closed_trades,
)

logger = logging.getLogger(__name__)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
AV_BASE = "https://www.alphavantage.co/query"
ET = ZoneInfo("America/New_York")

TOTAL_CAPITAL       = 5000.0
MAX_POSITIONS       = 5
MIN_POSITION_SIZE   = 500.0
MAX_POSITION_SIZE   = 2000.0

# Entry thresholds
STRONG_BUY_FLOOR    = 0.50   # Strong Buy entry
ACCEL_BUY_FLOOR     = 0.15   # Buy floor for accelerating entry
ACCEL_DELTA_MIN     = 0.08   # Minimum score improvement between recalcs to qualify

# Exit thresholds
NEUTRAL_HARD_EXIT   = 0.15   # Hard exit floor — at or below this, close
SOFT_EXIT_CONSEC    = 2      # Consecutive declining windows triggers soft exit


# ---------------------------------------------------------------------------
# Market hours check
# ---------------------------------------------------------------------------

def _is_market_open() -> bool:
    """Basic check — Mon-Fri, 9:30 AM to 4:00 PM ET. Ignores holidays."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def _fetch_current_price(ticker: str) -> float | None:
    """Fetch latest daily close from AV (real-time on premium tier)."""
    try:
        r = requests.get(AV_BASE, params={
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()
        series = r.json().get("Time Series (Daily)", {})
        if not series:
            return None
        latest_date = sorted(series.keys(), reverse=True)[0]
        return float(series[latest_date]["4. close"])
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", ticker, e)
        return None


def _fetch_eod_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch EOD closing prices for a list of tickers."""
    prices = {}
    for ticker in tickers:
        price = _fetch_current_price(ticker)
        if price:
            prices[ticker] = price
    return prices


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _get_score_delta(ticker: str) -> float:
    """
    Compare current composite score to the previous snapshot.
    Returns positive if accelerating, negative if deteriorating.
    """
    history = get_position_score_history(ticker, limit=2)
    if len(history) < 2:
        return 0.0
    return round(history[0]["score"] - history[1]["score"], 3)


def _is_entry_candidate(signal: dict) -> tuple[bool, str]:
    """
    Returns (qualifies, reason) for entry evaluation.
    Strong Buy always qualifies.
    Accelerating Buy qualifies if delta >= ACCEL_DELTA_MIN.
    """
    score = signal.get("composite_score", 0)
    label = signal.get("label", "")
    delta = _get_score_delta(signal["ticker"])

    if label == "Strong Buy" and score >= STRONG_BUY_FLOOR:
        return True, "Strong Buy"
    if label == "Buy" and score >= ACCEL_BUY_FLOOR and delta >= ACCEL_DELTA_MIN:
        return True, f"Accelerating Buy (Δ{delta:+.3f})"
    return False, ""


def _should_exit(position: dict, signal: dict | None) -> tuple[bool, str]:
    """
    Returns (should_exit, reason).
    Hard exit at Neutral floor.
    Soft exit on 2 consecutive declining windows with negative momentum.
    """
    if signal is None:
        return True, "Signal lost"

    score = signal.get("composite_score", 0)
    label = signal.get("label", "")

    # Hard exit
    if score < NEUTRAL_HARD_EXIT:
        return True, f"Score hit Neutral floor ({score:.3f})"

    # Check consecutive declines
    history = get_position_score_history(position["ticker"], limit=SOFT_EXIT_CONSEC + 1)
    if len(history) >= SOFT_EXIT_CONSEC:
        recent = [h["score"] for h in history[:SOFT_EXIT_CONSEC]]
        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            # All recent snapshots declining
            if label in ("Buy",) and score < 0.3:
                return True, f"Sustained deterioration ({', '.join(f'{s:.3f}' for s in recent)})"

    return False, ""


def _calculate_position_size(score: float, available_capital: float) -> float:
    """
    Conviction-weighted sizing.
    Score 0.50-0.65 → $500-900
    Score 0.65-0.80 → $900-1400
    Score 0.80-1.00 → $1400-2000
    Capped by available capital and MAX_POSITION_SIZE.
    """
    if score >= 0.80:
        size = 1400 + (score - 0.80) / 0.20 * 600   # scales to $2000
    elif score >= 0.65:
        size = 900 + (score - 0.65) / 0.15 * 500
    elif score >= 0.50:
        size = 500 + (score - 0.50) / 0.15 * 400
    else:
        # Accelerating Buy — modest size
        size = 500 + score * 400
    size = round(min(size, MAX_POSITION_SIZE, available_capital), 2)
    return max(size, MIN_POSITION_SIZE) if available_capital >= MIN_POSITION_SIZE else 0


def _combined_score(position: dict) -> float:
    """
    Displacement score: signal strength + P&L buffer.
    Higher = more protected from displacement.
    """
    signal_score = position.get("current_composite", 0.0)
    entry_price  = position.get("entry_price", 1)
    current_price = position.get("current_price", entry_price)
    ret_pct = (current_price - entry_price) / entry_price if entry_price else 0
    # Normalize return: +20% return = +0.2 boost, -20% = -0.2 drag
    return_component = max(-0.5, min(0.5, ret_pct))
    return round(signal_score * 0.6 + return_component * 0.4, 3)


# ---------------------------------------------------------------------------
# Core decision engine
# ---------------------------------------------------------------------------

def run_trading_window(window_name: str):
    """
    Main trading logic. Called three times per market day.
    1. Snapshot current scores
    2. Evaluate exits on open positions
    3. Evaluate new entries
    4. Handle displacement if slots full
    """
    if not _is_market_open():
        logger.info("Trading window %s skipped — market closed", window_name)
        return

    logger.info("=== Trading window: %s ===", window_name)
    now_str = datetime.utcnow().isoformat()

    # --- 1. Snapshot all current signals ---
    all_signals = {s["ticker"]: s for s in get_equity_sentiment_all()}
    for ticker, sig in all_signals.items():
        insert_score_snapshot({
            "ticker": ticker,
            "score": sig.get("composite_score", 0),
            "label": sig.get("label", ""),
            "window": window_name,
            "recorded_at": now_str,
        })

    # --- 2. Evaluate exits ---
    open_positions = get_open_positions()
    closed_tickers = []

    for pos in open_positions:
        ticker = pos["ticker"]
        signal = all_signals.get(ticker)
        should_exit, reason = _should_exit(pos, signal)
        if should_exit:
            close_position(pos["id"], reason=reason, closed_at=now_str)
            closed_tickers.append(ticker)
            logger.info("EXIT queued: %s — %s", ticker, reason)

    # Refresh open positions after exits
    open_positions = [p for p in open_positions if p["ticker"] not in closed_tickers]

    # --- 3. Get portfolio state ---
    summary = get_portfolio_summary()
    deployed = summary.get("deployed_capital", 0.0)
    available = TOTAL_CAPITAL - deployed
    open_count = len(open_positions)
    open_tickers = {p["ticker"] for p in open_positions}

    # --- 4. Find entry candidates ---
    candidates = []
    for ticker, signal in all_signals.items():
        if ticker in open_tickers:
            continue
        qualifies, reason = _is_entry_candidate(signal)
        if qualifies:
            candidates.append({
                "ticker": ticker,
                "signal": signal,
                "reason": reason,
                "score": signal.get("composite_score", 0),
            })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    for candidate in candidates:
        ticker = candidate["ticker"]
        score  = candidate["score"]

        if open_count >= MAX_POSITIONS:
            # Check displacement — find weakest open position
            positions_with_combined = [
                (p, _combined_score(p)) for p in open_positions
            ]
            weakest_pos, weakest_combined = min(
                positions_with_combined, key=lambda x: x[1]
            )
            new_combined = score  # new entry has no P&L yet
            if new_combined > weakest_combined + 0.05:  # meaningful improvement
                close_position(
                    weakest_pos["id"],
                    reason=f"Displaced by stronger signal: {ticker} (score {score:.3f} vs {weakest_combined:.3f})",
                    closed_at=now_str,
                )
                open_positions = [p for p in open_positions if p["id"] != weakest_pos["id"]]
                deployed -= weakest_pos.get("position_size", 0)
                available += weakest_pos.get("position_size", 0)
                open_count -= 1
                logger.info("DISPLACE: %s evicted for %s", weakest_pos["ticker"], ticker)
            else:
                logger.info("No displacement warranted for %s — existing positions stronger", ticker)
                continue

        size = _calculate_position_size(score, available)
        if size < MIN_POSITION_SIZE:
            logger.info("Insufficient capital for %s (available: %.2f)", ticker, available)
            continue

        signal_data = candidate["signal"]
        position_record = {
            "ticker": ticker,
            "entry_reason": candidate["reason"],
            "entry_score": score,
            "entry_label": signal_data.get("label", ""),
            "position_size": size,
            "entry_price": None,    # filled at EOD settlement
            "entry_window": window_name,
            "opened_at": now_str,
            "status": "pending_open",
            "current_composite": score,
            "commodity": signal_data.get("commodity", ""),
        }
        insert_position(position_record)
        open_count += 1
        deployed += size
        available -= size
        open_tickers.add(ticker)
        logger.info(
            "ENTRY queued: %s | %s | $%.0f | score %.3f",
            ticker, candidate["reason"], size, score
        )


# ---------------------------------------------------------------------------
# EOD settlement
# ---------------------------------------------------------------------------

def run_eod_settlement():
    """
    Runs after 4 PM ET close.
    1. Fetch closing prices for all positions
    2. Fill pending_open entries with entry price
    3. Close pending_close positions with exit price
    4. Update current price on all open positions
    5. Log P&L
    """
    if not _is_market_open() and datetime.now(ET).hour < 16:
        logger.info("EOD settlement skipped — outside settlement window")
        return

    logger.info("=== EOD Settlement ===")
    all_positions = get_open_positions(include_pending=True)
    tickers = list({p["ticker"] for p in all_positions})
    prices = _fetch_eod_prices(tickers)

    settled_opens = 0
    settled_closes = 0

    for pos in all_positions:
        ticker  = pos["ticker"]
        price   = prices.get(ticker)
        if not price:
            logger.warning("No EOD price for %s — settlement deferred", ticker)
            continue

        status = pos.get("status", "")

        if status == "pending_open":
            update_position_price(pos["id"], entry_price=price, current_price=price, status="open")
            settled_opens += 1
            logger.info("SETTLED OPEN: %s @ $%.2f", ticker, price)

        elif status == "pending_close":
            entry_price   = pos.get("entry_price") or price
            position_size = pos.get("position_size", 0)
            shares        = position_size / entry_price if entry_price else 0
            pnl           = round((price - entry_price) * shares, 2)
            pnl_pct       = round((price - entry_price) / entry_price * 100, 2) if entry_price else 0
            update_position_price(
                pos["id"],
                current_price=price,
                exit_price=price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                status="closed",
            )
            settled_closes += 1
            logger.info(
                "SETTLED CLOSE: %s @ $%.2f | P&L: $%.2f (%.2f%%)",
                ticker, price, pnl, pnl_pct
            )

        elif status == "open":
            # Just update current price for unrealised P&L display
            entry_price   = pos.get("entry_price") or price
            shares        = pos.get("position_size", 0) / entry_price if entry_price else 0
            unrealised    = round((price - entry_price) * shares, 2)
            unrealised_pct = round((price - entry_price) / entry_price * 100, 2) if entry_price else 0
            update_position_price(
                pos["id"],
                current_price=price,
                pnl=unrealised,
                pnl_pct=unrealised_pct,
            )

    logger.info(
        "EOD settlement complete — %d opens filled, %d closes settled",
        settled_opens, settled_closes
    )
