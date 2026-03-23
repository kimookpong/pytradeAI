"""
Smart Logic Module
==================
Symbol screening and selection — finds the most advantageous symbols to trade.
"""

import math
from typing import Optional


class SmartLogic:
    """Analyzes and ranks symbols by trading advantage."""

    def __init__(self, connector):
        self.connector = connector
        self._price_snapshots: dict[str, list[float]] = {}

    def update_prices(self):
        """Capture current prices for all symbols."""
        for symbol in self.connector.SYMBOLS:
            price_data = self.connector.get_symbol_price(symbol)
            if price_data:
                if symbol not in self._price_snapshots:
                    self._price_snapshots[symbol] = []
                self._price_snapshots[symbol].append(price_data["bid"])
                # Keep last 500 snapshots
                if len(self._price_snapshots[symbol]) > 500:
                    self._price_snapshots[symbol] = self._price_snapshots[symbol][-500:]

    def get_symbol_rankings(self) -> list[dict]:
        """Rank all symbols by trading advantage score."""
        rankings = []
        for symbol in self.connector.SYMBOLS:
            score = self._calculate_advantage_score(symbol)
            rankings.append({
                "symbol": symbol,
                "score": round(score, 1),
                "volatility": round(self._calc_volatility(symbol), 4),
                "trend_strength": round(self._calc_trend_strength(symbol), 2),
                "spread_cost": round(self._calc_spread_cost(symbol), 4),
                "recommendation": self._get_recommendation(score),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings

    def get_best_symbol(self) -> Optional[dict]:
        """Get the symbol with highest advantage score."""
        rankings = self.get_symbol_rankings()
        return rankings[0] if rankings else None

    def _calculate_advantage_score(self, symbol: str) -> float:
        """
        Calculate composite advantage score (0–100).
        Higher = better to trade right now.
        """
        volatility = self._calc_volatility(symbol)
        trend = self._calc_trend_strength(symbol)
        spread = self._calc_spread_cost(symbol)

        # Normalize components
        vol_score = min(volatility * 10000, 40)  # Volatility is good (up to 40 pts)
        trend_score = trend * 30  # Strong trend up to 30 pts
        spread_score = max(0, 30 - spread * 100000)  # Low spread up to 30 pts

        return vol_score + trend_score + spread_score

    def _calc_volatility(self, symbol: str) -> float:
        """Calculate price volatility (standard deviation of returns)."""
        prices = self._price_snapshots.get(symbol, [])
        if len(prices) < 10:
            return 0.0

        returns = [(prices[i] / prices[i - 1]) - 1 for i in range(1, len(prices))]
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance)

    def _calc_trend_strength(self, symbol: str) -> float:
        """Calculate trend strength using linear regression slope."""
        prices = self._price_snapshots.get(symbol, [])
        if len(prices) < 10:
            return 0.0

        n = len(prices)
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n

        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        # Normalize by price to get relative trend
        return abs(slope / y_mean) * 100

    def _calc_spread_cost(self, symbol: str) -> float:
        """Get spread cost relative to price."""
        price_data = self.connector.get_symbol_price(symbol)
        if not price_data or price_data["bid"] == 0:
            return float("inf")
        return price_data["spread"] / price_data["bid"]

    def _get_recommendation(self, score: float) -> str:
        """Get human-readable recommendation from score."""
        if score >= 70:
            return "🟢 Strong Advantage"
        elif score >= 50:
            return "🟡 Moderate"
        elif score >= 30:
            return "🟠 Weak"
        else:
            return "🔴 Avoid"
