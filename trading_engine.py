"""
Trading Engine
==============
Auto-trading logic with multi-symbol strategy support.
Uses technical indicators (RSI, MA, Bollinger Bands) for entry/exit signals.
"""

import time
import math
import random
import asyncio
from datetime import datetime
from typing import Optional


class TradingEngine:
    """Core auto-trading engine with strategy management.
    Timeframe: M5 (5-minute) bars for all technical analysis and order entry/exit.
    """

    STRATEGIES = {
        # sl_points / tp_points are in DOLLAR PIPS  (1 pip = $0.01).
        # e.g. sl_points=100 → max loss $1.00  |  tp_points=200 → target $2.00
        "BTCUSD": {
            "name": "Bitcoin Momentum",
            "enabled": True,
            "lot_size": 0.01,
            "sl_points": 200,  # $2.00 risk  (200 dollar-pips × $0.01)
            "tp_points": 200,  # $2.00 target  → net ~$1.96 after commission
            "min_profit": 1.0,
            "timeframe": "M5",
            "icon": "₿",
            "color": "#f7931a",
            "commission": 2.0,  # USD per lot per side — Exness Raw Spread
        },
        "XAUUSD": {
            "name": "Gold Scalper",
            "enabled": True,
            "lot_size": 0.01,
            "sl_points": 200,  # $2.00 risk
            "tp_points": 200,  # $2.00 target  → net ~$1.93 after commission
            "min_profit": 1.0,
            "timeframe": "M5",
            "icon": "⚜️",
            "color": "#ffd700",
            "commission": 3.5,  # USD per lot per side — Exness Raw Spread
        },
        "ETHUSD": {
            "name": "Ethereum Swing",
            "enabled": True,
            "lot_size": 0.1,   # min safe volume — broker rejects < 0.1 and no partial close < 0.1
            "sl_points": 100,  # $1.00 risk  (kept tight due to crypto volatility at 0.1 lot)
            "tp_points": 200,  # $2.00 target  → net ~$1.98 after commission
            "min_profit": 1.0,
            "timeframe": "M5",
            "icon": "Ξ",
            "color": "#627eea",
            "commission": 0.5,  # USD per lot per side — Exness Raw Spread
        },
    }

    def __init__(self, connector, log_callback=None):
        self.connector = connector
        self.system_active = False
        self.running = False
        self._log = log_callback or (lambda *a, **kw: None)
        self._ai_active_fn = None   # set after AI engine is created
        self._price_history: dict[str, list[float]] = {s: [] for s in self.STRATEGIES}
        self._last_trade_time: dict[str, float] = {s: 0 for s in self.STRATEGIES}
        self._spread_history: dict[str, list[float]] = {s: [] for s in self.STRATEGIES}
        self._trade_cooldown = 300  # 5 min (1 full M5 bar) between trades per symbol
        self._sim_price_counter = 0
        # ── Risk management state ──────────────────────────────
        self._symbol_paused_until: dict[str, float] = {}  # symbol → epoch when pause expires
        self._max_daily_loss: float = -30.0   # halt new entries if today’s P&L ≤ this
        self._max_trades_per_day: int = 50    # max trades per symbol per day
        self._telegram = None
        self._risk_notified: set = set()  # dedup risk alert keys so we don't flood Telegram

    def set_telegram(self, telegram) -> None:
        """Inject TelegramNotifier so the engine can send trade/risk alerts."""
        self._telegram = telegram
    def set_ai_mode_fn(self, fn):
        """Set a callable(symbol) -> bool that returns True when AI is trading that symbol."""
        self._ai_active_fn = fn

    def toggle_system(self) -> bool:
        """Toggle the entire trading system ON/OFF."""
        self.system_active = not self.system_active
        return self.system_active

    def toggle_strategy(self, symbol: str) -> dict:
        """Toggle a specific strategy ON/OFF."""
        if symbol in self.STRATEGIES:
            self.STRATEGIES[symbol]["enabled"] = not self.STRATEGIES[symbol]["enabled"]
            return {
                "symbol": symbol,
                "enabled": self.STRATEGIES[symbol]["enabled"],
                "name": self.STRATEGIES[symbol]["name"],
            }
        return {"error": f"Unknown symbol: {symbol}"}

    def update_strategy_settings(self, symbol: str,
                                  lot_size: float = None,
                                  sl_points: int = None,
                                  tp_points: int = None,
                                  cooldown: int = None,
                                  enabled: bool = None) -> dict:
        """Update AI/strategy settings for a specific symbol."""
        if symbol not in self.STRATEGIES:
            return {"error": f"Unknown symbol: {symbol}"}
        cfg = self.STRATEGIES[symbol]
        if lot_size is not None:
            cfg["lot_size"] = round(float(lot_size), 2)
        if sl_points is not None:
            cfg["sl_points"] = int(sl_points)
        if tp_points is not None:
            cfg["tp_points"] = int(tp_points)
        if enabled is not None:
            cfg["enabled"] = bool(enabled)
        if cooldown is not None:
            self._trade_cooldown = int(cooldown)
        return {
            "symbol": symbol,
            "name": cfg["name"],
            "enabled": cfg["enabled"],
            "lot_size": cfg["lot_size"],
            "sl_points": cfg["sl_points"],
            "tp_points": cfg["tp_points"],
            "cooldown": self._trade_cooldown,
        }

    def get_strategies(self) -> list[dict]:
        """Get all strategies with their status."""
        return [
            {
                "symbol": symbol,
                "name": config["name"],
                "enabled": config["enabled"],
                "lot_size": config["lot_size"],
                "icon": config["icon"],
                "color": config["color"],
                "min_profit": config["min_profit"],
            }
            for symbol, config in self.STRATEGIES.items()
        ]

    def get_system_status(self) -> dict:
        """Get overall system status."""
        active_count = sum(1 for s in self.STRATEGIES.values() if s["enabled"])
        return {
            "system_active": self.system_active,
            "mt5_connected": self.connector.is_connected(),
            "active_strategies": active_count,
            "total_strategies": len(self.STRATEGIES),
            "simulation_mode": self.connector.simulation_mode,
        }

    async def run_loop(self):
        """Main trading loop — runs in background."""
        self.running = True
        print("🚀 Trading engine loop started")

        while self.running:
            try:
                if self.connector.is_connected():
                    # Always collect price history (needed for conditions display even when system is off)
                    self._collect_prices()
                    if self.system_active:
                        await self._process_strategies()
                await asyncio.sleep(2)
            except Exception as e:
                print(f"⚠️ Trading loop error: {e}")
                await asyncio.sleep(5)

        print("⏹️ Trading engine loop stopped")

    def _collect_prices(self):
        """Collect M5 candle closes for all symbols into history (always runs, not system-gated).

        When MT5 returns real candles we replace the history entirely so indicators
        are computed on genuine M5 OHLC data.  In simulation/fallback mode we keep
        the existing tick-sampling approach as an approximation.
        """
        for symbol in self.STRATEGIES:
            # Try real M5 candles first (live MT5 only)
            candles = self.connector.get_candles(symbol, count=100)
            if candles:
                # Full replacement — real candle closes are authoritative
                self._price_history[symbol] = candles
                continue

            # Fallback: append current bid tick (simulation or candle fetch failed)
            price_data = self.connector.get_symbol_price(symbol)
            if not price_data:
                continue
            bid = price_data["bid"]
            self._price_history[symbol].append(bid)
            if len(self._price_history[symbol]) > 200:
                self._price_history[symbol] = self._price_history[symbol][-200:]

    def stop(self):
        """Stop the trading loop."""
        self.running = False

    async def _process_strategies(self):
        """Process all enabled strategies."""
        for symbol, config in self.STRATEGIES.items():
            if not config["enabled"]:
                continue

            # Skip if AI engine is actively trading this symbol
            if self._ai_active_fn and self._ai_active_fn(symbol):
                continue

            # Get current price
            price_data = self.connector.get_symbol_price(symbol)
            if not price_data:
                continue

            bid = price_data["bid"]
            ask = price_data["ask"]

            # Trading hours — XAUUSD: 07:00-15:00 UTC (14:00-22:00 GMT+7), weekdays only; crypto: 24/7
            if not self._is_trading_hours(symbol):
                continue

            # Need enough bars for MA55 (crypto) or MA30 (XAUUSD)
            min_bars = 56 if symbol in ("BTCUSD", "ETHUSD") else 31
            if len(self._price_history[symbol]) < min_bars:
                self._log("STRATEGY", f"Strategy {symbol}: Insufficient data ({len(self._price_history[symbol])}/{min_bars} bars)", detail={"symbol": symbol, "bars": len(self._price_history[symbol])})
                continue

            # Check cooldown
            now = time.time()

            # ── RISK MANAGEMENT ────────────────────────────────────────────────
            # 1. Symbol-level pause after too many consecutive losses
            pause_until = self._symbol_paused_until.get(symbol, 0)
            if now < pause_until:
                self._log("RISK", f"⏸ {symbol}: paused after consecutive losses ({(pause_until - now) / 60:.0f}min left)", detail={"symbol": symbol, "pause_remaining": round(pause_until - now)})
                continue

            # 2. Daily drawdown circuit breaker (halts ALL symbols for the day)
            daily_pnl = self._get_daily_pnl()
            if daily_pnl <= self._max_daily_loss:
                self._log("RISK", f"🛑 Daily loss limit reached (${daily_pnl:.2f} ≤ ${self._max_daily_loss:.2f}) — halting new entries", detail={"daily_pnl": round(daily_pnl, 2), "limit": self._max_daily_loss})
                daily_key = f"daily_loss_{datetime.now().date()}"
                if self._telegram and daily_key not in self._risk_notified:
                    self._risk_notified.add(daily_key)
                    asyncio.create_task(self._telegram.notify_risk_alert(
                        f"🛑 Daily loss limit reached\n"
                        f"P&L today: <b>${daily_pnl:.2f}</b> (limit: ${self._max_daily_loss:.2f})\n"
                        f"No new entries will be opened for the rest of today."
                    ))
                return  # Stop processing all symbols this cycle

            # 3. Max trades per day per symbol
            today_count = self._get_today_trade_count(symbol)
            if today_count >= self._max_trades_per_day:
                self._log("RISK", f"⛔ {symbol}: max daily trades reached ({today_count}/{self._max_trades_per_day})", detail={"symbol": symbol, "today_count": today_count, "limit": self._max_trades_per_day})
                continue

            # 4. Consecutive loss limits (Exness risk rules: 2→15 min cooldown, 3→rest of day)
            consecutive_losses = self._get_consecutive_losses(symbol)
            if consecutive_losses >= 3:
                end_of_day = datetime.now().replace(hour=23, minute=59, second=59).timestamp()
                self._symbol_paused_until[symbol] = end_of_day
                self._log("RISK", f"🚨 {symbol}: {consecutive_losses} consecutive losses — paused for rest of day", detail={"symbol": symbol, "consecutive_losses": consecutive_losses})
                pause_key = f"pause_{symbol}_{datetime.now().date()}"
                if self._telegram and pause_key not in self._risk_notified:
                    self._risk_notified.add(pause_key)
                    asyncio.create_task(self._telegram.notify_risk_alert(
                        f"🚨 <b>{symbol}</b>: {consecutive_losses} consecutive losses\n"
                        f"Auto-trading paused for the <b>rest of today</b>."
                    ))
                continue
            effective_cooldown = 900 if consecutive_losses == 2 else self._trade_cooldown  # 15 min after 2 losses

            cooldown_remaining = effective_cooldown - (now - self._last_trade_time.get(symbol, 0))
            if cooldown_remaining > 0:
                self._log("TRADE", f"Strategy {symbol}: Cooldown active ({cooldown_remaining:.0f}s remaining)", detail={"symbol": symbol, "cooldown": round(cooldown_remaining, 1)})
                continue

            # Spread check — reject if current spread > 1.5× rolling average
            if not self._is_spread_ok(symbol, price_data):
                self._log("RISK", f"📶 {symbol}: spread too wide — skipped", detail={"symbol": symbol})
                continue

            # Generate signal
            signal = self._calculate_signal(symbol)

            if signal and signal != "HOLD":
                # Check if we already have a position in this symbol
                positions = self.connector.get_positions()
                has_position = any(p["symbol"] == symbol for p in positions)

                if not has_position:
                    # Place order — SL/TP converted from dollar pips (1 pip = $0.01)
                    entry = ask if signal == "BUY" else bid
                    sl, tp = self.connector.pips_to_sl_tp(
                        symbol, entry,
                        config["sl_points"], config["tp_points"],
                        signal, config["lot_size"],
                    )

                    result = self.connector.place_order(
                        symbol=symbol,
                        order_type=signal,
                        volume=config["lot_size"],
                        sl=sl,
                        tp=tp,
                        comment=f"AI-{config['name'][:10]}",
                        timeframe="M5",
                        min_profit=config["min_profit"],
                        sl_points=config["sl_points"],
                    )

                    if result.success:
                        self._last_trade_time[symbol] = now
                        self._log(
                            "TRADE",
                            f"✅ {signal} {symbol} | {config['name']}",
                            f"Ticket #{result.ticket} | Lot {config['lot_size']} | SL {sl:.5f} | TP {tp:.5f}",
                        )
                        print(f"📈 {signal} {symbol} @ {bid:.5f} | SL: {sl:.5f} | TP: {tp:.5f}")
                        if self._telegram:
                            asyncio.create_task(self._telegram.notify_order_open(
                                symbol=symbol, order_type=signal,
                                volume=config["lot_size"], entry=entry,
                                sl=sl, tp=tp, ticket=result.ticket,
                                comment=f"AI-{config['name'][:15]}",
                            ))
                    else:
                        print(f"❌ Failed {signal} {symbol}: {result.message}")

                elif has_position:
                    # Check if we should close existing position on opposite signal.
                    # Only close a strategy-opened position when ALL of:
                    #   1. Opposite signal fired
                    #   2. Position has been held at least `min_hold_seconds`
                    #   3. Position is currently profitable (don't lock in a loss)
                    # Note: use force=False so MT5Connector's SL/TP lockout rules also apply.
                    MIN_HOLD_STRATEGY_CLOSE = 300  # 5 minutes
                    for pos in positions:
                        if pos["symbol"] == symbol:
                            is_opposite = (
                                (pos["type"] == "BUY" and signal == "SELL") or
                                (pos["type"] == "SELL" and signal == "BUY")
                            )
                            if not is_opposite:
                                continue
                            held_seconds = now - pos.get("time", now)
                            is_profitable = pos.get("profit", 0) > 0
                            if held_seconds < MIN_HOLD_STRATEGY_CLOSE:
                                remaining = MIN_HOLD_STRATEGY_CLOSE - held_seconds
                                self._log("TRADE", f"⏳ {symbol}: opposite signal but min-hold not reached ({remaining:.0f}s left) — letting SL/TP manage", detail={"symbol": symbol, "held": round(held_seconds), "remaining": round(remaining)})
                                continue
                            if not is_profitable:
                                self._log("TRADE", f"⏸ {symbol}: opposite signal but position at loss (${pos['profit']:.2f}) — waiting for SL/TP", detail={"symbol": symbol, "profit": pos["profit"]})
                                continue
                            result = self.connector.close_position(pos["ticket"], force=False)
                            if result.success:
                                self._last_trade_time[symbol] = now
                                self._log(
                                    "TRADE",
                                    f"🔄 Close {symbol} #{pos['ticket']} | {config['name']}",
                                    f"Opposite signal {signal} after {held_seconds:.0f}s hold — {result.message}",
                                )
                                print(f"🔄 Closed {symbol} position: {result.message}")
                                if self._telegram:
                                    asyncio.create_task(self._telegram.notify_order_close(
                                        symbol=pos["symbol"], order_type=pos["type"],
                                        volume=pos["volume"], entry=pos["price_open"],
                                        close_price=pos.get("price_current", pos["price_open"]),
                                        profit=pos["profit"], ticket=pos["ticket"],
                                        comment=f"AI Signal {signal}",
                                    ))
                            else:
                                self._log("TRADE", f"⏸ {symbol}: close blocked — {result.message}", detail={"symbol": symbol, "reason": result.message})

    def _get_consecutive_losses(self, symbol: str) -> int:
        """Count consecutive losing trades for a symbol (most recent first)."""
        try:
            history = self.connector.get_history(1)
        except Exception:
            return 0
        sym_trades = [t for t in history if t.get("symbol") == symbol]
        sym_trades.sort(key=lambda t: t.get("close_time", t.get("time", 0)), reverse=True)
        count = 0
        for trade in sym_trades[:10]:
            if trade.get("profit", 0) <= 0:
                count += 1
            else:
                break
        return count

    def _get_daily_pnl(self) -> float:
        """Sum of closed-trade P&L since UTC midnight today."""
        try:
            history = self.connector.get_history(1)
        except Exception:
            return 0.0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return sum(
            t.get("profit", 0)
            for t in history
            if t.get("close_time", t.get("time", 0)) >= today_start
        )

    def _get_today_trade_count(self, symbol: str) -> int:
        """Count trades opened for a symbol since UTC midnight today."""
        try:
            history = self.connector.get_history(1)
        except Exception:
            return 0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return sum(
            1 for t in history
            if t.get("symbol") == symbol and t.get("time", 0) >= today_start
        )

    def _is_trading_hours(self, symbol: str) -> bool:
        """Trading hour filters (all times UTC):
        XAUUSD: 07:00-15:00 UTC (14:00-22:00 GMT+7), weekdays only — London+NY overlap.
        BTCUSD/ETHUSD: 02:00-09:00 UTC (09:00-16:00 GMT+7) and 13:00-19:00 UTC (20:00-02:00 GMT+7)
                        — avoids Asia early-morning low-liquidity window."""
        now = datetime.utcnow()
        h = now.hour
        if symbol == "XAUUSD":
            if now.weekday() >= 5:   # Saturday=5, Sunday=6
                return False
            return 7 <= h < 15
        else:  # BTCUSD, ETHUSD
            return (2 <= h < 9) or (13 <= h < 19)

    def _is_spread_ok(self, symbol: str, price_data: dict) -> bool:
        """Reject entry if current spread > 1.5× rolling average of last 50 readings."""
        current_spread = price_data["ask"] - price_data["bid"]
        history = self._spread_history[symbol]
        history.append(current_spread)
        if len(history) > 50:
            del history[:-50]
        if len(history) < 5:
            return True   # not enough history yet — allow
        avg_spread = sum(history[:-1]) / max(len(history) - 1, 1)
        if avg_spread <= 0:
            return True
        return current_spread <= avg_spread * 1.5

    def _calculate_signal(self, symbol: str) -> str:
        """
        Calculate trading signal.

        XAUUSD: MA10/MA30 — Gold responds well to shorter-period trend signals.
        BTCUSD/ETHUSD: MA21/MA55 — Longer periods filter crypto noise.

        Entry rules:
        - BUY only when price is ABOVE MA_slow (in long-term uptrend)
        - SELL only when price is BELOW MA_slow (in long-term downtrend)
        - BB bounce signals count ONLY with confirmed trend direction
        - Requires 2-bar consecutive close confirmation before firing
        - Minimum score 4 (of 7) with opposing score ≤ 1
        """
        prices = self._price_history[symbol]

        # Symbol-specific MA periods (Exness-tuned)
        if symbol == "XAUUSD":
            fast_period, slow_period = 10, 30
        else:  # BTCUSD, ETHUSD
            fast_period, slow_period = 21, 55
        is_crypto = symbol in ["ETHUSD", "BTCUSD"]

        if len(prices) < slow_period + 1:
            return "HOLD"

        # Moving Averages (trend direction gate)
        ma_fast = sum(prices[-fast_period:]) / fast_period
        ma_slow = sum(prices[-slow_period:]) / slow_period

        # RSI (14 periods)
        rsi = self._calc_rsi(prices, 14)

        # Bollinger Bands (20 periods; 2.2σ for XAUUSD, 2.0σ for crypto)
        bb_period = 20
        bb_sigma = 2.2 if symbol == "XAUUSD" else 2.0
        ma_bb = sum(prices[-bb_period:]) / bb_period
        std = (sum((p - ma_bb) ** 2 for p in prices[-bb_period:]) / bb_period) ** 0.5
        upper_band = ma_bb + bb_sigma * std
        lower_band = ma_bb - bb_sigma * std

        current_price = prices[-1]

        # Hard trend direction filter
        has_buy_trend = ma_fast > ma_slow
        has_sell_trend = ma_fast < ma_slow

        # RSI thresholds — tuned per symbol for Exness conditions
        if is_crypto:
            rsi_oversold  = 25   # was 20 (too easy to trigger in prolonged downtrend)
            rsi_weak_buy  = 35
            rsi_overbought = 72  # was 80 (rarely hit, so SELL was never triggered)
            rsi_weak_sell  = 62
        else:  # XAUUSD
            rsi_oversold  = 30
            rsi_weak_buy  = 38   # per spec scoring table: ≤ 38 for XAUUSD
            rsi_overbought = 65
            rsi_weak_sell  = 58

        buy_signals  = 0
        sell_signals = 0

        # 1. RSI signal
        if rsi <= rsi_oversold:
            buy_signals += 2
        elif rsi <= rsi_weak_buy:
            buy_signals += 1

        if rsi >= rsi_overbought:
            sell_signals += 2
        elif rsi >= rsi_weak_sell:
            sell_signals += 1

        # 2. MA trend confirmation
        if has_buy_trend:
            buy_signals += 1
        elif has_sell_trend:
            sell_signals += 1

        # 3. Bollinger Bands — ONLY with confirmed trend (removes counter-trend BB noise)
        if current_price <= lower_band and has_buy_trend:
            buy_signals += 2   # oversold bounce inside uptrend
        if current_price >= upper_band and has_sell_trend:
            sell_signals += 2  # overbought fade inside downtrend

        # 4. Two-bar consecutive close confirmation (reduces whipsaws)
        if len(prices) >= 3:
            if prices[-1] > prices[-2] > prices[-3]:
                buy_signals += 1
            elif prices[-1] < prices[-2] < prices[-3]:
                sell_signals += 1

        # 5. Momentum filter — penalise counter-trend entries
        if len(prices) >= 5:
            last5 = prices[-5:]
            bearish_bars = sum(1 for i in range(1, 5) if last5[i] < last5[i - 1])
            bullish_bars = sum(1 for i in range(1, 5) if last5[i] > last5[i - 1])
            if bearish_bars >= 4:
                buy_signals = max(0, buy_signals - 1)
                self._log("RISK", f"📉 {symbol}: 4/4 bars bearish — BUY penalised to {buy_signals}", detail={"symbol": symbol, "bearish_bars": bearish_bars, "buy_signals": buy_signals})
            if bullish_bars >= 4:
                sell_signals = max(0, sell_signals - 1)
                self._log("RISK", f"📈 {symbol}: 4/4 bars bullish — SELL penalised to {sell_signals}", detail={"symbol": symbol, "bullish_bars": bullish_bars, "sell_signals": sell_signals})

        # ADX(14) — filter out ranging markets; require trend strength ≥ 20
        adx = self._calc_adx(prices)
        adx_trending = adx >= 20.0

        self._log("TRADE", f"📊 {symbol}: RSI={rsi:.1f} MA{fast_period}={ma_fast:.5f} MA{slow_period}={ma_slow:.5f} ADX={adx:.1f} trend={'UP' if has_buy_trend else 'DOWN' if has_sell_trend else 'FLAT'} buy={buy_signals} sell={sell_signals}", detail={
            "symbol": symbol, "rsi": round(rsi, 1),
            "ma_fast": round(ma_fast, 5), "ma_slow": round(ma_slow, 5),
            "adx": round(adx, 1),
            "current_price": round(current_price, 5),
            "upper_band": round(upper_band, 5), "lower_band": round(lower_band, 5),
            "buy_signals": buy_signals, "sell_signals": sell_signals,
        })

        if not adx_trending:
            self._log("RISK", f"➡️ {symbol}: ADX={adx:.1f} < 20 — sideways market, no entry", detail={"symbol": symbol, "adx": round(adx, 1)})
            return "HOLD"

        # DECISION — score ≥ 4 (of 7), opposing ≤ 1, trend + ADX must match
        if buy_signals >= 4 and sell_signals <= 1 and has_buy_trend:
            self._log("TRADE", f"🟢 BUY {symbol} b={buy_signals} s={sell_signals} ADX={adx:.1f} uptrend=YES", detail={"symbol": symbol, "signal": "BUY", "buy_count": buy_signals, "sell_count": sell_signals, "adx": round(adx, 1)})
            return "BUY"

        if sell_signals >= 4 and buy_signals <= 1 and has_sell_trend:
            self._log("TRADE", f"🔴 SELL {symbol} b={buy_signals} s={sell_signals} ADX={adx:.1f} downtrend=YES RSI={rsi:.1f}", detail={"symbol": symbol, "signal": "SELL", "buy_count": buy_signals, "sell_count": sell_signals, "rsi": round(rsi, 1), "adx": round(adx, 1)})
            return "SELL"

        return "HOLD"

    def get_trading_conditions(self, symbol: str) -> dict:
        """Get current trading conditions for a symbol - technical analysis + entry/exit rules."""
        prices = self._price_history.get(symbol, [])
        
        min_bars = 56 if symbol in ("BTCUSD", "ETHUSD") else 31
        if len(prices) < min_bars:
            return {
                "symbol": symbol,
                "status": "insufficient_data",
                "message": f"Need {min_bars} bars, have {len(prices)}",
            }

        # Symbol-specific MA periods (must match _calculate_signal)
        if symbol == "XAUUSD":
            fast_period, slow_period = 10, 30
        else:  # BTCUSD, ETHUSD
            fast_period, slow_period = 21, 55
        is_crypto = symbol in ["ETHUSD", "BTCUSD"]
        bb_sigma = 2.2 if symbol == "XAUUSD" else 2.0

        # Technical indicators
        rsi = self._calc_rsi(prices, 14)
        adx = self._calc_adx(prices)
        ma_fast = sum(prices[-fast_period:]) / fast_period
        ma_slow = sum(prices[-slow_period:]) / slow_period

        bb_period = 20
        ma_bb = sum(prices[-bb_period:]) / bb_period
        std = (sum((p - ma_bb) ** 2 for p in prices[-bb_period:]) / bb_period) ** 0.5
        upper_band = ma_bb + bb_sigma * std
        lower_band = ma_bb - bb_sigma * std

        current_price = prices[-1]

        # RSI thresholds (must match _calculate_signal)
        if is_crypto:
            rsi_oversold  = 25
            rsi_weak_buy  = 35
            rsi_overbought = 72
            rsi_weak_sell  = 62
        else:  # XAUUSD
            rsi_oversold  = 30
            rsi_weak_buy  = 38   # per spec scoring table: ≤ 38 for XAUUSD
            rsi_overbought = 65
            rsi_weak_sell  = 58

        # Trend direction
        has_buy_trend  = ma_fast > ma_slow
        has_sell_trend = ma_fast < ma_slow

        # Count signals (same logic as _calculate_signal)
        buy_signals  = 0
        sell_signals = 0
        buy_conditions  = []
        sell_conditions = []

        # RSI
        if rsi <= rsi_oversold:
            buy_signals += 2
            buy_conditions.append(f"🔵 RSI = {rsi:.1f} (oversold ≤ {rsi_oversold})")
        elif rsi <= rsi_weak_buy:
            buy_signals += 1
            buy_conditions.append(f"🔵 RSI = {rsi:.1f} (weak buy ≤ {rsi_weak_buy})")

        if rsi >= rsi_overbought:
            sell_signals += 2
            sell_conditions.append(f"🔴 RSI = {rsi:.1f} (overbought ≥ {rsi_overbought})")
        elif rsi >= rsi_weak_sell:
            sell_signals += 1
            sell_conditions.append(f"🔴 RSI = {rsi:.1f} (weak sell ≥ {rsi_weak_sell})")

        # MA trend
        ma_label = f"MA{fast_period}/MA{slow_period}"
        if has_buy_trend:
            buy_signals += 1
            buy_conditions.append(f"🔵 UPTREND: {ma_label} ({ma_fast:.5f} > {ma_slow:.5f})")
        elif has_sell_trend:
            sell_signals += 1
            sell_conditions.append(f"🔴 DOWNTREND: {ma_label} ({ma_fast:.5f} < {ma_slow:.5f})")
        else:
            buy_conditions.append(f"→ NEUTRAL: {ma_label} flat")

        # Bollinger Bands — only with confirmed trend
        if current_price <= lower_band:
            if has_buy_trend:
                buy_signals += 2
                buy_conditions.append(f"🔵 BB OVERSOLD: Price ≤ Lower Band ({lower_band:.5f}) + uptrend")
            else:
                buy_conditions.append(f"⚠️ BB Lower touched but no uptrend — BUY blocked")

        if current_price >= upper_band:
            if has_sell_trend:
                sell_signals += 2
                sell_conditions.append(f"🔴 BB OVERBOUGHT: Price ≥ Upper Band ({upper_band:.5f}) + downtrend")
            else:
                sell_conditions.append(f"⚠️ BB Upper touched but no downtrend — SELL blocked")

        if not (current_price <= lower_band or current_price >= upper_band):
            buy_conditions.append(f"→ Price ({current_price:.5f}) within BB range")

        # 2-bar consecutive close confirmation
        if len(prices) >= 3:
            if prices[-1] > prices[-2] > prices[-3]:
                buy_signals += 1
                buy_conditions.append(f"🔵 2-bar up confirmation")
            elif prices[-1] < prices[-2] < prices[-3]:
                sell_signals += 1
                sell_conditions.append(f"🔴 2-bar down confirmation")

        # 5. Momentum filter — penalise counter-trend entries (mirrors _calculate_signal)
        if len(prices) >= 5:
            last5 = prices[-5:]
            bearish_bars = sum(1 for i in range(1, 5) if last5[i] < last5[i - 1])
            bullish_bars = sum(1 for i in range(1, 5) if last5[i] > last5[i - 1])
            if bearish_bars >= 4:
                buy_signals = max(0, buy_signals - 1)
                buy_conditions.append(f"⚠️ Momentum penalty: {bearish_bars}/4 bars bearish → BUY-1")
            if bullish_bars >= 4:
                sell_signals = max(0, sell_signals - 1)
                sell_conditions.append(f"⚠️ Momentum penalty: {bullish_bars}/4 bars bullish → SELL-1")

        # ADX gate — must be ≥ 20 for any entry
        adx_trending = adx >= 20.0
        adx_label = f"ADX={adx:.1f}"
        if adx_trending:
            buy_conditions.append(f"🔵 {adx_label} ≥ 20 (trending)")
            sell_conditions.append(f"🔴 {adx_label} ≥ 20 (trending)")
        else:
            buy_conditions.append(f"🚫 {adx_label} < 20 — sideways market, entry BLOCKED")
            sell_conditions.append(f"🚫 {adx_label} < 20 — sideways market, entry BLOCKED")

        # Strategy settings
        cfg = self.STRATEGIES.get(symbol, {})

        # Trigger flags (matches _calculate_signal decision gates — score ≥ 4, opposing ≤ 1, ADX ≥ 20)
        adx_trending = adx >= 20.0
        buy_triggered  = buy_signals >= 4 and sell_signals <= 1 and has_buy_trend and adx_trending
        sell_triggered = sell_signals >= 4 and buy_signals <= 1 and has_sell_trend and adx_trending
        
        # Last 40 prices for sparkline (enough for visual trend, keeps payload small)
        sparkline = [round(p, 5) for p in prices[-40:]]

        return {
            "symbol": symbol,
            "status": "ready",
            "current_price": round(current_price, 5),
            "price_history": sparkline,
            "bb_upper": round(upper_band, 5),
            "bb_lower": round(lower_band, 5),
            "ma_fast": round(ma_fast, 5),
            "technical_indicators": {
                "rsi_14": round(rsi, 2),
                "adx_14": round(adx, 1),
                "adx_trending": adx_trending,
                "ma_7": round(ma_fast, 5),
                "ma_20": round(ma_slow, 5),
                "ma_fast_period": fast_period,
                "ma_slow_period": slow_period,
                "bb_upper": round(upper_band, 5),
                "bb_lower": round(lower_band, 5),
                "bb_middle": round(ma_bb, 5),
                "bb_sigma": bb_sigma,
            },
            "buy_signal": {
                "score": buy_signals,
                "triggered": buy_triggered,
                "conditions": buy_conditions,
            },
            "sell_signal": {
                "score": sell_signals,
                "triggered": sell_triggered,
                "conditions": sell_conditions,
            },
            "entry_exit": {
                "cooldown_seconds": self._trade_cooldown,
                "lot_size": cfg.get("lot_size", 0.01),
                "stop_loss_points": cfg.get("sl_points", 0),
                "take_profit_points": cfg.get("tp_points", 0),
                "position_exists": any(p["symbol"] == symbol for p in self.connector.get_positions()),
            }
        }

    def _calc_rsi(self, prices: list[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(-period, 0)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]

        avg_gain = sum(gains) / period if gains else 0.001
        avg_loss = sum(losses) / period if losses else 0.001

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calc_adx(self, prices: list[float], period: int = 14) -> float:
        """Simplified ADX from close-only data (no OHLC in history buffer).

        Uses consecutive close-to-close differences as a proxy for True Range
        and Directional Movement, then applies Wilder's smoothing.
        Returns 0-100.  Default 25.0 when data is insufficient (passes the ≥20 gate).
        """
        if len(prices) < period * 2 + 2:
            return 25.0  # assume trending during warmup — let other gates filter

        plus_dm: list[float] = []
        minus_dm: list[float] = []
        tr_list: list[float] = []

        for i in range(1, len(prices)):
            up   = prices[i] - prices[i - 1]
            down = prices[i - 1] - prices[i]
            plus_dm.append(up   if up > down and up > 0   else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            tr_list.append(abs(prices[i] - prices[i - 1]))

        def _wilder_smooth(data: list[float], n: int) -> list[float]:
            if len(data) < n:
                return []
            smoothed = [sum(data[:n]) / n]
            for val in data[n:]:
                smoothed.append((smoothed[-1] * (n - 1) + val) / n)
            return smoothed

        atr     = _wilder_smooth(tr_list,   period)
        pdi_raw = _wilder_smooth(plus_dm,   period)
        mdi_raw = _wilder_smooth(minus_dm,  period)

        if not atr:
            return 25.0

        dx_list: list[float] = []
        for atr_v, pdi_v, mdi_v in zip(atr, pdi_raw, mdi_raw):
            if atr_v <= 0:
                continue
            di_plus  = pdi_v / atr_v * 100
            di_minus = mdi_v / atr_v * 100
            di_sum   = di_plus + di_minus
            dx_list.append(abs(di_plus - di_minus) / di_sum * 100 if di_sum > 0 else 0.0)

        if len(dx_list) < period:
            return 25.0

        return sum(dx_list[-period:]) / period
