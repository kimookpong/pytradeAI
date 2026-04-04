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
        "BTCUSD": {
            "name": "Bitcoin Momentum",
            "enabled": True,
            "lot_size": 0.01,
            "sl_points": 800,  # Wider SL to reduce whipsaw (was 500)
            "tp_points": 1200,  # Realistic target (was 800)
            "min_profit": 50.0,
            "timeframe": "M5",
            "icon": "₿",
            "color": "#f7931a",
        },
        "XAUUSD": {
            "name": "Gold Scalper",
            "enabled": True,
            "lot_size": 0.05,
            "sl_points": 100,
            "tp_points": 150,
            "min_profit": 10.0,
            "timeframe": "M5",
            "icon": "⚜️",
            "color": "#ffd700",
        },
        "USDJPY": {
            "name": "Yen Trend Follower",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 30,
            "tp_points": 50,
            "min_profit": 5.0,
            "timeframe": "M5",
            "icon": "¥",
            "color": "#00d4aa",
        },
        "ETHUSD": {
            "name": "Ethereum Swing",
            "enabled": True,
            "lot_size": 0.1,
            "sl_points": 500,  # Wider SL to reduce whipsaw (was 300)
            "tp_points": 750,  # Realistic target (was 500)
            "min_profit": 30.0,
            "timeframe": "M5",
            "icon": "Ξ",
            "color": "#627eea",
        },
        "EURUSD": {
            "name": "Euro Breakout",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 20,
            "tp_points": 35,
            "min_profit": 8.0,
            "timeframe": "M5",
            "icon": "€",
            "color": "#4fc3f7",
        },
        "GBPUSD": {
            "name": "Cable Rider",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 25,
            "tp_points": 40,
            "min_profit": 10.0,
            "timeframe": "M5",
            "icon": "£",
            "color": "#ab47bc",
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
        self._trade_cooldown = 60  # seconds between trades per symbol
        self._sim_price_counter = 0

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
                if self.system_active and self.connector.is_connected():
                    await self._process_strategies()
                await asyncio.sleep(2)
            except Exception as e:
                print(f"⚠️ Trading loop error: {e}")
                await asyncio.sleep(5)

        print("⏹️ Trading engine loop stopped")

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

            # Update price history
            self._price_history[symbol].append(bid)
            if len(self._price_history[symbol]) > 200:
                self._price_history[symbol] = self._price_history[symbol][-200:]

            # Need at least 20 periods for indicators
            if len(self._price_history[symbol]) < 20:
                self._log("STRATEGY", f"Strategy {symbol}: Insufficient data ({len(self._price_history[symbol])}/20 bars)", detail={"symbol": symbol, "bars": len(self._price_history[symbol])})
                continue

            # Check cooldown
            now = time.time()
            cooldown_remaining = self._trade_cooldown - (now - self._last_trade_time.get(symbol, 0))
            if cooldown_remaining > 0:
                self._log("TRADE", f"Strategy {symbol}: Cooldown active ({cooldown_remaining:.0f}s remaining)", detail={"symbol": symbol, "cooldown": round(cooldown_remaining, 1)})
                continue

            # Generate signal
            signal = self._calculate_signal(symbol)

            if signal and signal != "HOLD":
                # Check if we already have a position in this symbol
                positions = self.connector.get_positions()
                has_position = any(p["symbol"] == symbol for p in positions)

                if not has_position:
                    # Place order
                    pip_value = self.connector.SYMBOLS.get(symbol, {}).get("pip_value", 0.01)
                    if signal == "BUY":
                        sl = round(bid - config["sl_points"] * pip_value, 5)
                        tp = round(ask + config["tp_points"] * pip_value, 5)
                    else:
                        sl = round(ask + config["sl_points"] * pip_value, 5)
                        tp = round(bid - config["tp_points"] * pip_value, 5)

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
                    else:
                        print(f"❌ Failed {signal} {symbol}: {result.message}")

                elif has_position:
                    # Check if we should close existing position
                    for pos in positions:
                        if pos["symbol"] == symbol:
                            # Close if signal is opposite
                            if (pos["type"] == "BUY" and signal == "SELL") or \
                               (pos["type"] == "SELL" and signal == "BUY"):
                                result = self.connector.close_position(pos["ticket"])
                                if result.success:
                                    self._last_trade_time[symbol] = now
                                    self._log(
                                        "TRADE",
                                        f"🔄 Close {symbol} #{pos['ticket']} | {config['name']}",
                                        f"Opposite signal {signal} — {result.message}",
                                    )
                                    print(f"🔄 Closed {symbol} position: {result.message}")

    def _calculate_signal(self, symbol: str) -> str:
        """
        Calculate trading signal using technical indicators with stricter confirmation.
        
        Key improvements:
        - More conservative RSI thresholds (shifted -5 points)
        - SELL requires MA confirmation (no solo Bollinger Band entries)
        - Symbol-specific rules for high-volatility pairs (ETHUSD, BTCUSD)
        - Require matching trend before entering
        """
        prices = self._price_history[symbol]

        # RSI (14 periods)
        rsi = self._calc_rsi(prices, 14)

        # Moving Averages
        ma_fast = sum(prices[-7:]) / 7
        ma_slow = sum(prices[-20:]) / 20

        # Bollinger Bands (20 periods, 2 std dev)
        ma_20 = sum(prices[-20:]) / 20
        std = (sum((p - ma_20) ** 2 for p in prices[-20:]) / 20) ** 0.5
        upper_band = ma_20 + 2 * std
        lower_band = ma_20 - 2 * std

        current_price = prices[-1]

        # Symbol-specific thresholds for high-volatility pairs
        is_high_vol = symbol in ["ETHUSD", "BTCUSD"]
        rsi_oversold = 20 if is_high_vol else 25  # Stricter for volatility
        rsi_weak_buy = 30 if is_high_vol else 35
        rsi_overbought = 80 if is_high_vol else 75  # Stricter for volatility
        rsi_weak_sell = 70 if is_high_vol else 65

        # Signal logic with stricter confirmation
        buy_signals = 0
        sell_signals = 0
        has_buy_trend = ma_fast > ma_slow  # Uptrend
        has_sell_trend = ma_fast < ma_slow  # Downtrend

        # RSI signals (more conservative thresholds)
        if rsi < rsi_oversold:
            buy_signals += 2
        elif rsi < rsi_weak_buy:
            buy_signals += 1
        
        if rsi > rsi_overbought:
            sell_signals += 2
        elif rsi > rsi_weak_sell:
            sell_signals += 1

        # MA crossover (confirms trend)
        if has_buy_trend:
            buy_signals += 1
        elif has_sell_trend:
            sell_signals += 1

        # Bollinger Band signals (with trend confirmation)
        if current_price <= lower_band:
            # Require uptrend or near-neutral
            if has_buy_trend or (not has_sell_trend):
                buy_signals += 2
            else:
                buy_signals += 1
        
        if current_price >= upper_band:
            # Require downtrend or near-neutral PLUS RSI > 60
            if (has_sell_trend or not has_buy_trend) and rsi > 60:
                sell_signals += 2
            else:
                sell_signals += 1

        # Log technical analysis for debugging
        self._log("TRADE", f"📊 Signal analysis {symbol}: RSI={rsi:.1f}, MA7={ma_fast:.5f}, MA20={ma_slow:.5f}, Price={current_price:.5f}, BB=[{lower_band:.5f},{upper_band:.5f}], Trend={'UP' if has_buy_trend else 'DOWN' if has_sell_trend else 'FLAT'}", detail={
            "symbol": symbol,
            "rsi": round(rsi, 1),
            "ma_fast": round(ma_fast, 5),
            "ma_slow": round(ma_slow, 5),
            "current_price": round(current_price, 5),
            "upper_band": round(upper_band, 5),
            "lower_band": round(lower_band, 5),
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
        })

        # **CRITICAL**: BUY requires confirmed uptrend + strong signal
        if buy_signals >= 3 and sell_signals < 2 and has_buy_trend:
            self._log("TRADE", f"🟢 BUY Signal {symbol}: buy_signals={buy_signals}, sell_signals={sell_signals}, uptrend=YES", detail={"symbol": symbol, "signal": "BUY", "buy_count": buy_signals, "sell_count": sell_signals})
            return "BUY"
        
        # **CRITICAL**: SELL requires confirmed downtrend + MA signal + strong RSI
        # Don't enter SELL on Bollinger Bands alone — too many false breakouts
        if sell_signals >= 3 and buy_signals < 2 and has_sell_trend and rsi > 60:
            self._log("TRADE", f"🔴 SELL Signal {symbol}: sell_signals={sell_signals}, buy_signals={buy_signals}, downtrend=YES, RSI={rsi:.1f}", detail={"symbol": symbol, "signal": "SELL", "buy_count": buy_signals, "sell_count": sell_signals, "rsi": round(rsi, 1)})
            return "SELL"

        return "HOLD"

    def get_trading_conditions(self, symbol: str) -> dict:
        """Get current trading conditions for a symbol - technical analysis + entry/exit rules."""
        prices = self._price_history.get(symbol, [])
        
        if len(prices) < 20:
            return {
                "symbol": symbol,
                "status": "insufficient_data",
                "message": f"Need 20 bars, have {len(prices)}",
            }

        # Technical indicators
        rsi = self._calc_rsi(prices, 14)
        ma_fast = sum(prices[-7:]) / 7
        ma_slow = sum(prices[-20:]) / 20
        
        ma_20 = sum(prices[-20:]) / 20
        std = (sum((p - ma_20) ** 2 for p in prices[-20:]) / 20) ** 0.5
        upper_band = ma_20 + 2 * std
        lower_band = ma_20 - 2 * std
        
        current_price = prices[-1]
        
        # Symbol-specific thresholds (same as in _calculate_signal)
        is_high_vol = symbol in ["ETHUSD", "BTCUSD"]
        rsi_oversold = 20 if is_high_vol else 25
        rsi_weak_buy = 30 if is_high_vol else 35
        rsi_overbought = 80 if is_high_vol else 75
        rsi_weak_sell = 70 if is_high_vol else 65
        
        # Trend direction
        has_buy_trend = ma_fast > ma_slow
        has_sell_trend = ma_fast < ma_slow
        
        # Count signals with new stricter logic
        buy_signals = 0
        sell_signals = 0
        buy_conditions = []
        sell_conditions = []
        
        # RSI analysis (more conservative thresholds)
        if rsi < rsi_oversold:
            buy_signals += 2
            buy_conditions.append(f"🔵 RSI = {rsi:.1f} (oversold)")
        elif rsi < rsi_weak_buy:
            buy_signals += 1
            buy_conditions.append(f"🔵 RSI = {rsi:.1f} (weak buy)")
        
        if rsi > rsi_overbought:
            sell_signals += 2
            sell_conditions.append(f"🔴 RSI = {rsi:.1f} (overbought)")
        elif rsi > rsi_weak_sell:
            sell_signals += 1
            sell_conditions.append(f"🔴 RSI = {rsi:.1f} (weak sell)")
        
        # MA crossover (trend confirmation)
        if has_buy_trend:
            buy_signals += 1
            buy_conditions.append(f"🔵 UPTREND: MA7 ({ma_fast:.5f}) > MA20 ({ma_slow:.5f})")
        elif has_sell_trend:
            sell_signals += 1
            sell_conditions.append(f"🔴 DOWNTREND: MA7 ({ma_fast:.5f}) < MA20 ({ma_slow:.5f})")
        else:
            buy_conditions.append(f"→ NEUTRAL: MA7 ≈ MA20")
        
        # Bollinger Bands (with trend confirmation requirement)
        if current_price <= lower_band:
            if has_buy_trend or (not has_sell_trend):
                buy_signals += 2
                buy_conditions.append(f"🔵 BREAKOUT: Price ({current_price:.5f}) ≤ Lower Band ({lower_band:.5f})")
            else:
                buy_signals += 1
                buy_conditions.append(f"🟡 BB Support: Price near Lower Band (weak signal)")
        
        if current_price >= upper_band:
            # CRITICAL: Require downtrend + strong RSI for SELL Bollinger Band signal
            if (has_sell_trend or not has_buy_trend) and rsi > 60:
                sell_signals += 2
                sell_conditions.append(f"🔴 BREAKOUT: Price ({current_price:.5f}) ≥ Upper Band ({upper_band:.5f})")
            else:
                sell_signals += 1
                sell_conditions.append(f"🟡 BB Resistance: Price near Upper Band (weak signal)")
        else:
            if not (current_price <= lower_band):
                buy_conditions.append(f"→ Price ({current_price:.5f}) within BB range")
        
        # Strategy settings
        cfg = self.STRATEGIES.get(symbol, {})
        
        # Apply New Stricter Logic to Trading Signal Display
        # BUY requires: 3+ signals + downtrend filtered + uptrend confirmation
        buy_triggered = buy_signals >= 3 and sell_signals < 2 and has_buy_trend
        
        # SELL requires: 3+ signals + uptrend filtered + downtrend confirmation + strong RSI
        sell_triggered = sell_signals >= 3 and buy_signals < 2 and has_sell_trend and rsi > 60
        
        return {
            "symbol": symbol,
            "status": "ready",
            "current_price": round(current_price, 5),
            "technical_indicators": {
                "rsi_14": round(rsi, 2),
                "ma_7": round(ma_fast, 5),
                "ma_20": round(ma_slow, 5),
                "bb_upper": round(upper_band, 5),
                "bb_lower": round(lower_band, 5),
                "bb_middle": round(ma_20, 5),
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
