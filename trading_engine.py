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
    """Core auto-trading engine with strategy management."""

    STRATEGIES = {
        "BTCUSD": {
            "name": "Bitcoin Momentum",
            "enabled": False,
            "lot_size": 0.01,
            "sl_points": 500,
            "tp_points": 800,
            "icon": "₿",
            "color": "#f7931a",
        },
        "XAUUSD": {
            "name": "Gold Scalper",
            "enabled": False,
            "lot_size": 0.05,
            "sl_points": 100,
            "tp_points": 150,
            "icon": "⚜️",
            "color": "#ffd700",
        },
        "USDJPY": {
            "name": "Yen Trend Follower",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 30,
            "tp_points": 50,
            "icon": "¥",
            "color": "#00d4aa",
        },
        "ETHUSD": {
            "name": "Ethereum Swing",
            "enabled": False,
            "lot_size": 0.01,
            "sl_points": 300,
            "tp_points": 500,
            "icon": "Ξ",
            "color": "#627eea",
        },
        "EURUSD": {
            "name": "Euro Breakout",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 20,
            "tp_points": 35,
            "icon": "€",
            "color": "#4fc3f7",
        },
        "GBPUSD": {
            "name": "Cable Rider",
            "enabled": False,
            "lot_size": 0.1,
            "sl_points": 25,
            "tp_points": 40,
            "icon": "£",
            "color": "#ab47bc",
        },
    }

    def __init__(self, connector):
        self.connector = connector
        self.system_active = False
        self.running = False
        self._price_history: dict[str, list[float]] = {s: [] for s in self.STRATEGIES}
        self._last_trade_time: dict[str, float] = {s: 0 for s in self.STRATEGIES}
        self._trade_cooldown = 60  # seconds between trades per symbol
        self._sim_price_counter = 0

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
                continue

            # Check cooldown
            now = time.time()
            if now - self._last_trade_time.get(symbol, 0) < self._trade_cooldown:
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
                    )

                    if result.success:
                        self._last_trade_time[symbol] = now
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
                                    print(f"🔄 Closed {symbol} position: {result.message}")

    def _calculate_signal(self, symbol: str) -> str:
        """Calculate trading signal using technical indicators."""
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

        # Signal logic
        buy_signals = 0
        sell_signals = 0

        # RSI signals
        if rsi < 30:
            buy_signals += 2
        elif rsi < 40:
            buy_signals += 1
        elif rsi > 70:
            sell_signals += 2
        elif rsi > 60:
            sell_signals += 1

        # MA crossover
        if ma_fast > ma_slow:
            buy_signals += 1
        elif ma_fast < ma_slow:
            sell_signals += 1

        # Bollinger Band signals
        if current_price <= lower_band:
            buy_signals += 2
        elif current_price >= upper_band:
            sell_signals += 2

        # Decision
        if buy_signals >= 3 and sell_signals < 2:
            return "BUY"
        elif sell_signals >= 3 and buy_signals < 2:
            return "SELL"

        return "HOLD"

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
