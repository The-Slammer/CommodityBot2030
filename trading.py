"""
trading.py — Paper trading decision engine.

Capital: $5,000 pool
Max positions: 5
Min position size: $500
Max position size: $2,000

Trading windows (ET):
  09:45 — Morning open (post-volatility settle)
  12:15 — Midday (shifted from 12:00 to avoid AV poll collision)
  15:30 — Pre-close

Trade types:
  momentum         — Strong Buy or Accelerating Buy on composite score
  swing_velocity   — Score accelerating rapidly over 48h, price not yet moved
  swing_divergence — Score strong but equity price has been flat/down

Entry criteria:
  Momentum:
    - Strong Buy (score >= 0.5) OR
    - Accelerating Buy: score >= 0.15 with score_delta >= 0.08 over last 2 recalcs
  Swing Velocity:
    - Score velocity (48h delta) >= 0.20 with current score >= 0.30
  Swing Divergence:
    - Composite score >= 0.40 + equity price flat or down over last 5 days

Exit criteria:
  - Score drops to Neutral (< 0.15) = hard exit, closes immediately
  - Score in Buy range but momentum_delta negative for 2 consecutive windows = soft exit
  - Displaced by stronger signal when slots full

Execution:
  - All entries and exits execute immediately at live GLOBAL_QUOTE price
  - No pending states — if AI approves, position opens/closes at current price
  - EOD settlement only updates current prices on open positions
"""

import json
import logging
import os
import time
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
    get_recent_eia_reports,
    get_recent_sec_filings,
    get_equity_score_velocity,
)

logger = logging.getLogger(__name__)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
AV_BASE    = "https://www.alphavantage.co/query"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
ET = ZoneInfo("America/New_York")

TOTAL_CAPITAL     = 5000.0
MAX_POSITIONS     = 5
MIN_POSITION_SIZE = 500.0
MAX_POSITION_SIZE = 2000.0

# Momentum entry thresholds
STRONG_BUY_FLOOR  = 0.50
ACCEL_BUY_FLOOR   = 0.15
ACCEL_DELTA_MIN   = 0.08

# Swing entry thresholds
SWING_VEL_DELTA   = 0.20   # 48h score acceleration to qualify as velocity swing
SWING_VEL_FLOOR   = 0.30   # minimum current score for velocity swing
SWING_DIV_FLOOR   = 0.40   # minimum score for divergence swing
SWING_DIV_MAX     = 8      # max divergence candidates to fetch price series for (API budget)

# Exit thresholds
NEUTRAL_HARD_EXIT = 0.15
SOFT_EXIT_CONSEC  = 2


# ---------------------------------------------------------------------------
# Market hours check
# ---------------------------------------------------------------------------

def _is_market_open() -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def _fetch_execution_price(ticker: str) -> float | None:
    """
    Fetch live GLOBAL_QUOTE price for immediate execution.
    Used at the moment a trade is approved — fills at this price, no pending queue.
    """
    try:
        r = requests.get(AV_BASE, params={
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.warning("AV rate limit on execution quote for %s", ticker)
            return None
        gq = data.get("Global Quote", {})
        price = gq.get("05. price")
        return float(price) if price else None
    except Exception as e:
        logger.warning("Execution price fetch failed for %s: %s", ticker, e)
        return None


def _fetch_price_series(ticker: str, days: int = 7) -> list:
    """
    Fetch daily price series for swing divergence check.
    Returns list of closing prices newest-first, or empty list on failure.
    """
    try:
        r = requests.get(AV_BASE, params={
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": ALPHAVANTAGE_API_KEY,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.warning("AV rate limit on price series for %s", ticker)
            return []
        series = data.get("Time Series (Daily)", {})
        sorted_dates = sorted(series.keys(), reverse=True)[:days]
        return [float(series[d]["4. close"]) for d in sorted_dates]
    except Exception as e:
        logger.warning("Price series fetch failed for %s: %s", ticker, e)
        return []


def _fetch_eod_prices(tickers: list) -> dict:
    """Fetch current prices for EOD position price updates."""
    prices = {}
    for ticker in tickers:
        price = _fetch_execution_price(ticker)
        if price:
            prices[ticker] = price
        time.sleep(1)
    return prices


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _get_score_delta(ticker: str) -> float:
    history = get_position_score_history(ticker, limit=2)
    if len(history) < 2:
        return 0.0
    return round(history[0]["score"] - history[1]["score"], 3)


def _is_momentum_candidate(signal: dict) -> tuple:
    score = signal.get("composite_score", 0)
    label = signal.get("label", "")
    delta = _get_score_delta(signal["ticker"])

    if label == "Strong Buy" and score >= STRONG_BUY_FLOOR:
        return True, "momentum", "Strong Buy"
    if label == "Buy" and score >= ACCEL_BUY_FLOOR and delta >= ACCEL_DELTA_MIN:
        return True, "momentum", f"Accelerating Buy (delta {delta:+.3f})"
    return False, "", ""


def _should_exit(position: dict, signal: dict | None) -> tuple:
    if signal is None:
        return True, "Signal lost"

    score = signal.get("composite_score", 0)
    label = signal.get("label", "")

    if score < NEUTRAL_HARD_EXIT:
        return True, f"Score hit Neutral floor ({score:.3f})"

    history = get_position_score_history(position["ticker"], limit=SOFT_EXIT_CONSEC + 1)
    if len(history) >= SOFT_EXIT_CONSEC:
        recent = [h["score"] for h in history[:SOFT_EXIT_CONSEC]]
        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            if label in ("Buy",) and score < 0.3:
                return True, f"Sustained deterioration ({', '.join(f'{s:.3f}' for s in recent)})"

    return False, ""


def _calculate_position_size(score: float, available_capital: float) -> float:
    if score >= 0.80:
        size = 1400 + (score - 0.80) / 0.20 * 600
    elif score >= 0.65:
        size = 900 + (score - 0.65) / 0.15 * 500
    elif score >= 0.50:
        size = 500 + (score - 0.50) / 0.15 * 400
    else:
        size = 500 + score * 400
    size = round(min(size, MAX_POSITION_SIZE, available_capital), 2)
    return max(size, MIN_POSITION_SIZE) if available_capital >= MIN_POSITION_SIZE else 0


def _combined_score(position: dict) -> float:
    signal_score  = position.get("current_composite", 0.0)
    entry_price   = position.get("entry_price", 1)
    current_price = position.get("current_price", entry_price)
    ret_pct = (current_price - entry_price) / entry_price if entry_price else 0
    return_component = max(-0.5, min(0.5, ret_pct))
    return round(signal_score * 0.6 + return_component * 0.4, 3)


# ---------------------------------------------------------------------------
# Swing trade detection
# ---------------------------------------------------------------------------

def _detect_swing_velocity_candidates(all_signals: dict, open_tickers: set) -> list:
    """
    Find tickers where the composite score has accelerated significantly
    over the last 48 hours while the equity hasn't necessarily moved yet.
    Uses score_snapshots table — no extra AV calls needed.
    """
    candidates = []
    for ticker, signal in all_signals.items():
        if ticker in open_tickers:
            continue
        score = signal.get("composite_score", 0)
        if score < SWING_VEL_FLOOR:
            continue
        velocity = get_equity_score_velocity(ticker)
        if velocity >= SWING_VEL_DELTA:
            candidates.append({
                "ticker": ticker,
                "signal": signal,
                "score": score,
                "velocity": velocity,
                "trade_type": "swing_velocity",
                "reason": f"Score velocity +{velocity:.3f} over 48h (current: {score:.3f})",
            })
            logger.info("Swing velocity candidate: %s | velocity: +%.3f | score: %.3f",
                        ticker, velocity, score)
    return candidates


def _detect_swing_divergence_candidates(all_signals: dict, open_tickers: set) -> list:
    """
    Find tickers with strong sentiment score but flat or declining equity price.
    Market hasn't priced in what the news is saying — classic lag opportunity.
    Fetches TIME_SERIES_DAILY for top candidates only (rate limit aware).
    2-second delay between calls.
    """
    # First pass: score filter — top candidates by score
    score_qualified = [
        (ticker, signal)
        for ticker, signal in all_signals.items()
        if ticker not in open_tickers
        and signal.get("composite_score", 0) >= SWING_DIV_FLOOR
    ]
    score_qualified.sort(key=lambda x: x[1].get("composite_score", 0), reverse=True)

    # Only fetch price series for top N to stay within API budget
    candidates = []
    for i, (ticker, signal) in enumerate(score_qualified[:SWING_DIV_MAX]):
        if i > 0:
            time.sleep(2)

        prices = _fetch_price_series(ticker, days=6)
        if not prices or len(prices) < 3:
            continue

        latest  = prices[0]
        oldest  = prices[-1]
        pct_chg = ((latest - oldest) / oldest) * 100 if oldest else 0

        # Divergence: score strong but price flat (< +1%) or down
        if pct_chg <= 1.0:
            score = signal.get("composite_score", 0)
            candidates.append({
                "ticker": ticker,
                "signal": signal,
                "score": score,
                "price_chg_pct": round(pct_chg, 2),
                "trade_type": "swing_divergence",
                "reason": (
                    f"Score {score:.3f} with price {pct_chg:+.1f}% over 5d "
                    f"(${oldest:.2f} → ${latest:.2f}) — sentiment/price divergence"
                ),
            })
            logger.info(
                "Swing divergence candidate: %s | score: %.3f | price chg: %+.1f%%",
                ticker, score, pct_chg
            )

    return candidates


# ---------------------------------------------------------------------------
# Market context builder
# ---------------------------------------------------------------------------

def _build_market_context() -> str:
    lines = []
    try:
        eia = get_recent_eia_reports(hours=48)
        if eia:
            lines.append("RECENT EIA DATA:")
            for r in eia[:3]:
                lines.append(
                    f"  {r.get('label','EIA')} | {r.get('report_type','')} | "
                    f"period {r.get('period','')} | value {r.get('value','')} "
                    f"{r.get('unit','')} (prev: {r.get('previous','')})"
                )
    except Exception:
        pass

    try:
        sec = get_recent_sec_filings(hours=48, high_priority_only=True)
        if sec:
            lines.append("RECENT SEC FILINGS (high priority):")
            for f in sec[:5]:
                labels = f.get("item_labels") or "[]"
                if isinstance(labels, str):
                    try: labels = json.loads(labels)
                    except: pass
                label_str = ", ".join(labels) if isinstance(labels, list) else str(labels)
                lines.append(
                    f"  {f.get('ticker','')} {f.get('filing_type','')} — "
                    f"{label_str} ({(f.get('filed_at') or '')[:10]})"
                )
    except Exception:
        pass

    return "\n".join(lines) if lines else "No recent EIA or SEC data in the last 48 hours."


# ---------------------------------------------------------------------------
# Sonnet decision layer
# ---------------------------------------------------------------------------

def _call_sonnet(prompt: str) -> str:
    try:
        r = requests.post(
            CLAUDE_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error("Sonnet call failed: %s", e)
        return ""


def _sonnet_entry_decision(candidates: list, open_positions: list,
                            available_capital: float, market_context: str) -> list:
    if not candidates:
        return []

    candidate_lines = []
    for c in candidates:
        sig = c["signal"]
        delta = _get_score_delta(sig["ticker"])
        history = get_position_score_history(sig["ticker"], limit=4)
        score_trail = " → ".join(f"{h['score']:.3f}" for h in reversed(history)) if history else "no history"

        extra = ""
        if c["trade_type"] == "swing_velocity":
            extra = f" | 48h velocity: +{c.get('velocity', 0):.3f}"
        elif c["trade_type"] == "swing_divergence":
            extra = f" | price 5d chg: {c.get('price_chg_pct', 0):+.1f}%"

        candidate_lines.append(
            f"  {sig['ticker']} ({sig.get('commodity','')}) | "
            f"trade_type: {c['trade_type']} | "
            f"composite: {sig.get('composite_score',0):.3f} | "
            f"label: {sig.get('label','')} | "
            f"news: {sig.get('news_score',0):.3f} | "
            f"price_momentum: {sig.get('price_score',0):.3f} | "
            f"delta: {delta:+.3f} | "
            f"score trail: {score_trail}{extra} | "
            f"rule reason: {c['reason']}"
        )

    open_lines = []
    for p in open_positions:
        entry   = p.get("entry_price") or 0
        current = p.get("current_price") or entry
        pnl_pct = round((current - entry) / entry * 100, 1) if entry else 0
        open_lines.append(
            f"  {p['ticker']} | size: ${p.get('position_size',0):.0f} | "
            f"type: {p.get('trade_type','momentum')} | "
            f"entry score: {p.get('entry_score',0):.3f} | "
            f"current signal: {p.get('current_composite',0):.3f} | "
            f"unrealised P&L: {pnl_pct:+.1f}%"
        )

    prompt = f"""You are the decision engine for CommodityBot, an automated energy and commodities paper trading system.

PORTFOLIO STATE:
  Available capital: ${available_capital:.0f} of $5,000 total
  Max positions: 5 | Min position: $500 | Max position: $2,000
  Open positions ({len(open_positions)}):
{chr(10).join(open_lines) if open_lines else '  None'}

ENTRY CANDIDATES (pre-filtered by rule engine):
{chr(10).join(candidate_lines)}

MARKET CONTEXT:
{market_context}

TRADE TYPES EXPLAINED:
  momentum         — Strong or accelerating sentiment signal. Standard directional trade.
  swing_velocity   — Sentiment score accelerating rapidly but price hasn't moved yet. Early entry on building conviction.
  swing_divergence — High sentiment score but equity price has been flat or declining. Market hasn't priced in the signal yet.

TASK:
Review each candidate and decide whether to approve or reject.
For swing trades, consider whether the divergence/velocity thesis is credible given market context.
For approved trades, specify position size ($500-$2,000).

Respond in this exact JSON format only, no other text:
{{
  "decisions": [
    {{
      "ticker": "XOM",
      "approved": true,
      "size": 1200,
      "reasoning": "One concise sentence explaining the decision."
    }}
  ]
}}"""

    response = _call_sonnet(prompt)
    if not response:
        logger.warning("Sonnet entry decision returned empty — falling back to rule-based")
        return candidates

    try:
        clean   = response.replace("```json", "").replace("```", "").strip()
        parsed  = json.loads(clean)
        decisions = {d["ticker"]: d for d in parsed.get("decisions", [])}

        approved = []
        for c in candidates:
            ticker   = c["ticker"]
            decision = decisions.get(ticker, {})
            if decision.get("approved", False):
                c["model_size"] = max(MIN_POSITION_SIZE,
                                      min(MAX_POSITION_SIZE, float(decision.get("size", 0))))
                c["model_reasoning"] = decision.get("reasoning", "Approved.")
                approved.append(c)
                logger.info("Sonnet APPROVED: %s | $%.0f | %s",
                            ticker, c["model_size"], c["model_reasoning"])
            else:
                logger.info("Sonnet REJECTED: %s | %s",
                            ticker, decision.get("reasoning", "No reason given."))
        return approved

    except Exception as e:
        logger.error("Sonnet entry parse failed: %s | raw: %s", e, response[:200])
        return candidates


def _sonnet_exit_decision(position: dict, signal: dict, market_context: str) -> tuple:
    ticker     = position["ticker"]
    history    = get_position_score_history(ticker, limit=5)
    score_trail = " → ".join(f"{h['score']:.3f}" for h in reversed(history)) if history else "no history"

    entry   = position.get("entry_price") or 0
    current = position.get("current_price") or entry
    pnl_pct = round((current - entry) / entry * 100, 1) if entry else 0
    days_held = 0
    try:
        opened    = datetime.fromisoformat(position.get("opened_at", ""))
        days_held = (datetime.utcnow() - opened).days
    except Exception:
        pass

    prompt = f"""You are the exit decision engine for CommodityBot.

POSITION:
  Ticker: {ticker} ({position.get('commodity','')})
  Trade type: {position.get('trade_type', 'momentum')}
  Entry score: {position.get('entry_score',0):.3f} | Entry label: {position.get('entry_label','')}
  Current composite score: {signal.get('composite_score',0):.3f} | Current label: {signal.get('label','')}
  Score trail (oldest → newest): {score_trail}
  News score: {signal.get('news_score',0):.3f} | Price momentum: {signal.get('price_score',0):.3f}
  Position size: ${position.get('position_size',0):.0f}
  Unrealised P&L: {pnl_pct:+.1f}%
  Days held: {days_held}

MARKET CONTEXT:
{market_context}

TASK:
Score is declining but above the hard Neutral floor (0.15). Close now or hold to next window?

Respond in this exact JSON format only:
{{
  "close": true,
  "reasoning": "One concise sentence."
}}"""

    response = _call_sonnet(prompt)
    if not response:
        return False, "Sonnet unavailable — holding"

    try:
        clean  = response.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return parsed.get("close", False), f"Sonnet: {parsed.get('reasoning', 'Model decision.')}"
    except Exception as e:
        logger.error("Sonnet exit parse failed: %s", e)
        return False, "Parse error — holding"


# ---------------------------------------------------------------------------
# Core decision engine
# ---------------------------------------------------------------------------

def run_trading_window(window_name: str):
    """
    Main trading logic. Called three times per market day.
    All decisions execute immediately — no pending states.
    """
    if not _is_market_open():
        logger.info("Trading window %s skipped — market closed", window_name)
        return

    logger.info("=== Trading window: %s ===", window_name)
    now_str = datetime.utcnow().isoformat()

    # 1. Snapshot current signals
    all_signals = {s["ticker"]: s for s in get_equity_sentiment_all()}
    for ticker, sig in all_signals.items():
        insert_score_snapshot({
            "ticker": ticker,
            "score": sig.get("composite_score", 0),
            "label": sig.get("label", ""),
            "window": window_name,
            "recorded_at": now_str,
        })

    # 2. Build market context once (shared for all model calls)
    market_context = _build_market_context()

    # 3. Evaluate exits on open positions
    open_positions = get_open_positions()
    closed_tickers = []

    for pos in open_positions:
        ticker = pos["ticker"]
        signal = all_signals.get(ticker)
        should_exit, reason = _should_exit(pos, signal)

        if should_exit:
            # Hard exit — get execution price immediately
            exit_price = _fetch_execution_price(ticker)
            _execute_close(pos, exit_price, reason, now_str)
            closed_tickers.append(ticker)
            logger.info("EXIT (hard): %s @ $%s — %s",
                        ticker, f"{exit_price:.2f}" if exit_price else "unknown", reason)
        elif signal and signal.get("composite_score", 1) < 0.35:
            # Borderline — ask Sonnet
            close_now, model_reason = _sonnet_exit_decision(pos, signal, market_context)
            if close_now:
                exit_price = _fetch_execution_price(ticker)
                _execute_close(pos, exit_price, model_reason, now_str)
                closed_tickers.append(ticker)
                logger.info("EXIT (model): %s @ $%s — %s",
                            ticker, f"{exit_price:.2f}" if exit_price else "unknown", model_reason)

    # Refresh open positions
    open_positions = [p for p in open_positions if p["ticker"] not in closed_tickers]
    open_tickers   = {p["ticker"] for p in open_positions}

    # 4. Portfolio state
    summary    = get_portfolio_summary()
    deployed   = summary.get("deployed_capital", 0.0)
    available  = TOTAL_CAPITAL - deployed
    open_count = len(open_positions)

    # 5. Collect all entry candidates across all three strategies
    all_candidates = []

    # Momentum candidates
    for ticker, signal in all_signals.items():
        if ticker in open_tickers:
            continue
        qualifies, trade_type, reason = _is_momentum_candidate(signal)
        if qualifies:
            all_candidates.append({
                "ticker": ticker,
                "signal": signal,
                "score":  signal.get("composite_score", 0),
                "trade_type": trade_type,
                "reason": reason,
            })

    # Swing velocity candidates (no extra API calls)
    velocity_candidates = _detect_swing_velocity_candidates(all_signals, open_tickers)
    for c in velocity_candidates:
        if not any(x["ticker"] == c["ticker"] for x in all_candidates):
            all_candidates.append(c)

    # Swing divergence candidates (TIME_SERIES_DAILY calls — rate limit aware)
    # Only run if we have available slots and capital
    if open_count < MAX_POSITIONS and available >= MIN_POSITION_SIZE:
        divergence_candidates = _detect_swing_divergence_candidates(all_signals, open_tickers)
        for c in divergence_candidates:
            if not any(x["ticker"] == c["ticker"] for x in all_candidates):
                all_candidates.append(c)

    all_candidates.sort(key=lambda x: x["score"], reverse=True)

    if not all_candidates:
        logger.info("No entry candidates this window")
        return

    # 6. Sonnet approves and sizes
    approved = _sonnet_entry_decision(all_candidates, open_positions, available, market_context)

    # 7. Execute approved entries immediately
    for candidate in approved:
        ticker = candidate["ticker"]
        score  = candidate["score"]

        if open_count >= MAX_POSITIONS:
            # Displacement check
            positions_with_combined = [(p, _combined_score(p)) for p in open_positions]
            weakest_pos, weakest_combined = min(positions_with_combined, key=lambda x: x[1])
            if score > weakest_combined + 0.05:
                exit_price = _fetch_execution_price(weakest_pos["ticker"])
                _execute_close(
                    weakest_pos, exit_price,
                    f"Displaced by {ticker} (score {score:.3f} vs {weakest_combined:.3f})",
                    now_str,
                )
                open_positions = [p for p in open_positions if p["id"] != weakest_pos["id"]]
                deployed  -= weakest_pos.get("position_size", 0)
                available += weakest_pos.get("position_size", 0)
                open_count -= 1
                logger.info("DISPLACE: %s evicted for %s", weakest_pos["ticker"], ticker)
            else:
                logger.info("No displacement warranted for %s", ticker)
                continue

        size = min(candidate.get("model_size",
                   _calculate_position_size(score, available)), available)
        if size < MIN_POSITION_SIZE:
            logger.info("Insufficient capital for %s (available: %.2f)", ticker, available)
            continue

        # Fetch live execution price
        entry_price = _fetch_execution_price(ticker)
        if not entry_price:
            logger.warning("Could not fetch execution price for %s — skipping", ticker)
            continue

        signal_data  = candidate["signal"]
        entry_reason = f"{candidate['reason']} | {candidate.get('model_reasoning', '')}"

        insert_position({
            "ticker":          ticker,
            "entry_reason":    entry_reason,
            "entry_score":     score,
            "entry_label":     signal_data.get("label", ""),
            "position_size":   size,
            "entry_price":     entry_price,
            "entry_window":    window_name,
            "opened_at":       now_str,
            "status":          "open",
            "current_composite": score,
            "commodity":       signal_data.get("commodity", ""),
        })
        open_count += 1
        deployed   += size
        available  -= size
        open_tickers.add(ticker)
        logger.info(
            "ENTRY EXECUTED: %s | $%.0f @ $%.2f | %s | %s",
            ticker, size, entry_price,
            candidate["trade_type"],
            candidate.get("model_reasoning", ""),
        )


def _execute_close(position: dict, exit_price: float | None, reason: str, closed_at: str):
    """
    Immediately close a position. Calculates P&L if price available.
    No pending state — position goes directly to closed.
    """
    pos_id      = position["id"]
    entry_price = position.get("entry_price") or 0
    size        = position.get("position_size", 0)

    if exit_price and entry_price:
        shares  = size / entry_price if entry_price else 0
        pnl     = round((exit_price - entry_price) * shares, 2)
        pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)
        update_position_price(
            pos_id,
            current_price=exit_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            status="closed",
        )
        logger.info(
            "CLOSE EXECUTED: %s @ $%.2f | P&L: $%.2f (%.2f%%)",
            position["ticker"], exit_price, pnl, pnl_pct,
        )
    else:
        # No price available — close at last known price
        update_position_price(pos_id, status="closed")
        logger.warning(
            "CLOSE EXECUTED (no price): %s — %s", position["ticker"], reason
        )

    close_position(pos_id, reason=reason, closed_at=closed_at)


# ---------------------------------------------------------------------------
# EOD settlement — price updates only
# ---------------------------------------------------------------------------

def run_eod_settlement():
    """
    Runs after 4 PM ET. Updates current prices and unrealised P&L on all
    open positions. No longer fills pending trades — those no longer exist.
    """
    logger.info("=== EOD Price Update ===")
    open_positions = get_open_positions()
    if not open_positions:
        logger.info("No open positions to update")
        return

    tickers = list({p["ticker"] for p in open_positions})
    prices  = _fetch_eod_prices(tickers)

    for pos in open_positions:
        ticker = pos["ticker"]
        price  = prices.get(ticker)
        if not price:
            logger.warning("No EOD price for %s — skipping update", ticker)
            continue

        entry_price = pos.get("entry_price") or price
        shares      = pos.get("position_size", 0) / entry_price if entry_price else 0
        unrealised  = round((price - entry_price) * shares, 2)
        unreal_pct  = round((price - entry_price) / entry_price * 100, 2) if entry_price else 0
        update_position_price(
            pos["id"],
            current_price=price,
            pnl=unrealised,
            pnl_pct=unreal_pct,
        )

    logger.info("EOD price update complete — %d positions updated", len(open_positions))
