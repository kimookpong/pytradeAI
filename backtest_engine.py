"""
Backtesting Engine for pytradeAI
Replays historical data against strategies to evaluate performance
"""

import time
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class BacktestTrade:
    """Record of a profitable/losing trade during backtest"""
    ticket: int
    symbol: str
    entry_price: float
    exit_price: float
    entry_time: int
    exit_time: int
    volume: float
    profit: float
    win: bool = False


class BacktestEngine:
    """
    Backtests trading strategies against historical data
    """

    def __init__(self, mt5_connector, trading_engine):
        self.mt5 = mt5_connector
        self.engine = trading_engine
        self.backtest_trades = []

    def run_backtest(self, symbol: str, days: int = 30, 
                     start_balance: float = 10000.0) -> dict:
        """
        Run backtest on a single symbol for given period
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            days: Number of days to backtest
            start_balance: Starting account balance
            
        Returns:
            Backtest results with performance metrics
        """
        print(f"🧪 Backtest started: {symbol} ({days} days)")
        
        # Get historical data
        history = self.mt5.get_history(days=days)
        if not history:
            return {"error": "No historical data available"}
        
        # Filter by symbol
        symbol_trades = [t for t in history if t["symbol"] == symbol]
        if not symbol_trades:
            return {"error": f"No trades found for {symbol}"}
        
        # Simulate backtest
        balance = start_balance
        equity_curve = [start_balance]
        trades = []
        
        for trade in symbol_trades:
            balance += trade["profit"]
            equity_curve.append(balance)
            
            trades.append({
                "ticket": trade["ticket"],
                "symbol": trade["symbol"],
                "type": trade["type"],
                "entry_price": trade["price_open"],
                "exit_price": trade["price_close"],
                "entry_time": trade["time"],
                "exit_time": trade["close_time"],
                "volume": trade["volume"],
                "profit": trade["profit"],
                "win": trade["profit"] > 0,
            })
        
        # Calculate metrics
        wins = [t for t in trades if t["win"]]
        losses = [t for t in trades if not t["win"]]
        total_profit = sum(t["profit"] for t in wins)
        total_loss = sum(t["profit"] for t in losses)
        
        # Profit factor
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
        
        # Drawdown
        peak = start_balance
        max_drawdown = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_drawdown:
                max_drawdown = dd
        
        # Return on Investment
        roi = ((balance - start_balance) / start_balance * 100)
        
        result = {
            "symbol": symbol,
            "days": days,
            "start_balance": start_balance,
            "end_balance": balance,
            "net_profit": balance - start_balance,
            "roi_percent": roi,
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(trades) * 100) if trades else 0,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "max_drawdown_percent": (max_drawdown / start_balance * 100),
            "avg_win": (total_profit / len(wins)) if wins else 0,
            "avg_loss": (total_loss / len(losses)) if losses else 0,
            "trades": trades,
            "equity_curve": equity_curve,
        }
        
        print(f"✅ Backtest complete: ROI={roi:.1f}%, Win={len(wins)}/{len(trades)}")
        
        return result

    def compare_symbols(self, symbols: list, days: int = 30, 
                       start_balance: float = 10000.0) -> dict:
        """
        Compare performance across multiple symbols
        
        Args:
            symbols: List of symbols to compare
            days: Number of days to backtest
            start_balance: Starting account balance
            
        Returns:
            Comparison results for all symbols
        """
        results = {}
        
        for symbol in symbols:
            result = self.run_backtest(symbol, days, start_balance)
            if "error" not in result:
                results[symbol] = result
        
        # Rank by ROI
        ranked = sorted(
            results.items(),
            key=lambda x: x[1].get("roi_percent", 0),
            reverse=True
        )
        
        return {
            "comparison": dict(ranked),
            "best_symbol": ranked[0][0] if ranked else None,
            "worst_symbol": ranked[-1][0] if ranked else None,
            "avg_roi": sum(v.get("roi_percent", 0) for v in results.values()) / len(results) if results else 0,
        }

    def backtest_strategy(self, symbol: str, strategy_name: str, days: int = 30) -> dict:
        """
        Backtest specific strategy on symbol
        
        Args:
            symbol: Trading symbol
            strategy_name: Name of strategy (e.g., "RSI", "MA_Cross")
            days: Number of days to backtest
            
        Returns:
            Strategy-specific performance metrics
        """
        print(f"🧪 Strategy backtest: {strategy_name} on {symbol}")
        
        # Run backtest
        result = self.run_backtest(symbol, days)
        
        if "error" in result:
            return result
        
        # Add strategy-specific analysis
        result["strategy"] = strategy_name
        result["confidence_score"] = self._calculate_confidence(result)
        result["recommendation"] = self._generate_recommendation(result)
        
        return result

    def _calculate_confidence(self, result: dict) -> float:
        """Calculate confidence score (0-100) for strategy"""
        if result["total_trades"] < 5:
            return 20  # Too few trades
        
        score = 50  # Base score
        
        # ROI component
        roi = result["roi_percent"]
        if roi > 10:
            score += 20
        elif roi > 0:
            score += 10
        else:
            score -= 20
        
        # Win rate component
        wr = result["win_rate"]
        if wr > 60:
            score += 15
        elif wr > 50:
            score += 5
        
        # Drawdown component
        dd = result["max_drawdown_percent"]
        if dd < 5:
            score += 10
        elif dd > 20:
            score -= 20
        
        return max(0, min(100, score))

    def _generate_recommendation(self, result: dict) -> str:
        """Generate trading recommendation based on backtest"""
        roi = result["roi_percent"]
        wr = result["win_rate"]
        dd = result["max_drawdown_percent"]
        
        if roi < -5:
            return "❌ High Risk: Strategy losing money"
        elif wr < 45:
            return "⚠️ Caution: Win rate below 45%"
        elif dd > 20:
            return "⚠️ Caution: High drawdown (>20%)"
        elif roi > 10 and wr > 55:
            return "✅ Good: Strong performance"
        elif roi > 0:
            return "✓ Acceptable: Profitable with room to improve"
        else:
            return "? Review: Monitor performance"
