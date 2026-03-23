"""
AI Insights Module
==================
R&D analytics — identifies weaknesses, strengths, and performance patterns.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional


class AIInsights:
    """Analyzes trading performance and provides actionable insights."""

    def __init__(self, connector):
        self.connector = connector

    def get_insights(self, days: int = 30) -> dict:
        """Get comprehensive R&D insights."""
        history = self.connector.get_history(days)

        if not history:
            return {
                "most_lost_symbol": {"symbol": "None!", "total_loss": 0},
                "weakest_action": {"action": "Perfect", "win_rate": 100},
                "total_loss_impact": 0,
                "win_rate": 0,
                "total_trades": 0,
                "symbol_breakdown": [],
                "action_breakdown": {"BUY": {"wins": 0, "losses": 0, "total_pnl": 0}, "SELL": {"wins": 0, "losses": 0, "total_pnl": 0}},
                "top_performer": {"symbol": "N/A", "total_profit": 0},
                "recent_streak": {"type": "none", "count": 0},
            }

        # ─── Symbol Analysis ───────────────────────────────
        symbol_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": 0})
        for deal in history:
            sym = deal["symbol"]
            symbol_stats[sym]["trades"] += 1
            symbol_stats[sym]["total_pnl"] += deal["profit"]
            if deal["profit"] >= 0:
                symbol_stats[sym]["wins"] += 1
            else:
                symbol_stats[sym]["losses"] += 1

        # Most Lost Symbol
        worst_symbol = "None!"
        worst_loss = 0.0
        for sym, stats in symbol_stats.items():
            losses_total = sum(d["profit"] for d in history if d["symbol"] == sym and d["profit"] < 0)
            if losses_total < worst_loss:
                worst_loss = losses_total
                worst_symbol = sym

        # Top Performer
        best_symbol = "N/A"
        best_profit = 0.0
        for sym, stats in symbol_stats.items():
            if stats["total_pnl"] > best_profit:
                best_profit = stats["total_pnl"]
                best_symbol = sym

        # ─── Action Analysis (BUY vs SELL) ─────────────────
        action_stats = {
            "BUY": {"wins": 0, "losses": 0, "total_pnl": 0.0},
            "SELL": {"wins": 0, "losses": 0, "total_pnl": 0.0},
        }
        for deal in history:
            action = deal["type"]
            if action in action_stats:
                action_stats[action]["total_pnl"] += deal["profit"]
                if deal["profit"] >= 0:
                    action_stats[action]["wins"] += 1
                else:
                    action_stats[action]["losses"] += 1

        # Weakest Action
        weakest_action = "Perfect"
        weakest_win_rate = 100.0
        for action, stats in action_stats.items():
            total = stats["wins"] + stats["losses"]
            if total > 0:
                wr = (stats["wins"] / total) * 100
                if wr < weakest_win_rate:
                    weakest_win_rate = wr
                    weakest_action = action

        # ─── Overall Stats ─────────────────────────────────
        total_trades = len(history)
        wins = sum(1 for d in history if d["profit"] >= 0)
        losses = sum(1 for d in history if d["profit"] < 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_loss = sum(d["profit"] for d in history if d["profit"] < 0)
        total_profit_all = sum(d["profit"] for d in history)

        # ─── Recent Streak ─────────────────────────────────
        streak_type = "none"
        streak_count = 0
        sorted_history = sorted(history, key=lambda x: x["time"], reverse=True)
        if sorted_history:
            first_result = "win" if sorted_history[0]["profit"] >= 0 else "loss"
            streak_type = first_result
            for deal in sorted_history:
                result = "win" if deal["profit"] >= 0 else "loss"
                if result == first_result:
                    streak_count += 1
                else:
                    break

        # ─── Symbol Breakdown ──────────────────────────────
        symbol_breakdown = []
        for sym, stats in symbol_stats.items():
            total = stats["wins"] + stats["losses"]
            wr = (stats["wins"] / total * 100) if total > 0 else 0
            symbol_breakdown.append({
                "symbol": sym,
                "trades": stats["trades"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate": round(wr, 1),
                "total_pnl": round(stats["total_pnl"], 2),
            })

        symbol_breakdown.sort(key=lambda x: x["total_pnl"], reverse=True)

        return {
            "most_lost_symbol": {"symbol": worst_symbol, "total_loss": round(worst_loss, 2)},
            "weakest_action": {"action": weakest_action, "win_rate": round(weakest_win_rate, 1)},
            "total_loss_impact": round(abs(total_loss), 2),
            "win_rate": round(win_rate, 1),
            "total_trades": total_trades,
            "total_profit": round(total_profit_all, 2),
            "symbol_breakdown": symbol_breakdown,
            "action_breakdown": {
                k: {
                    "wins": v["wins"],
                    "losses": v["losses"],
                    "total_pnl": round(v["total_pnl"], 2),
                }
                for k, v in action_stats.items()
            },
            "top_performer": {"symbol": best_symbol, "total_profit": round(best_profit, 2)},
            "recent_streak": {"type": streak_type, "count": streak_count},
        }

    def get_retrain_suggestions(self) -> list[str]:
        """Get AI model retrain suggestions based on performance."""
        insights = self.get_insights()
        suggestions = []

        # Check overall win rate
        if insights["win_rate"] < 50:
            suggestions.append("⚠️ Overall win rate below 50% — consider re-evaluating all strategies")

        # Check weakest action
        if insights["weakest_action"]["win_rate"] < 45:
            action = insights["weakest_action"]["action"]
            suggestions.append(f"🔧 {action} trades underperforming — adjust {action} entry conditions")

        # Check worst symbol
        if insights["most_lost_symbol"]["total_loss"] < -200:
            sym = insights["most_lost_symbol"]["symbol"]
            suggestions.append(f"🚫 Consider disabling {sym} — significant loss accumulation")

        # Check streak
        if insights["recent_streak"]["type"] == "loss" and insights["recent_streak"]["count"] >= 3:
            suggestions.append("⏸️ Losing streak detected — consider pausing auto-trade temporarily")

        # Check symbol breakdown for poorly performing symbols
        for sb in insights["symbol_breakdown"]:
            if sb["trades"] >= 5 and sb["win_rate"] < 40:
                suggestions.append(f"📉 {sb['symbol']} has {sb['win_rate']}% win rate over {sb['trades']} trades — needs optimization")

        if not suggestions:
            suggestions.append("✅ All strategies performing within acceptable parameters")

        return suggestions
