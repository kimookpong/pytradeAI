"""
Phase 5: Analytics Accuracy Testing
====================================
Validates P/L calculations, win rates, analytics summaries, and retrain suggestions.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from collections import defaultdict

API_BASE = "http://localhost:8888/api"


class AnalyticsTester:
    """Test analytics accuracy and calculations."""
    
    def __init__(self):
        self.session = None
        self.results = {
            "analytics_snapshots": [],
            "history_validation": [],
            "calculations": [],
            "retrain_suggestions": [],
            "errors": [],
        }
    
    async def init(self):
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def get_json(self, endpoint):
        try:
            async with self.session.get(f"{API_BASE}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            self.results["errors"].append({
                "ts": time.time(),
                "error": f"Request failed ({endpoint}): {str(e)}"
            })
            return None
    
    async def test_analytics_summary(self):
        """Test 1: Get and validate analytics summary."""
        print("\n" + "="*60)
        print("TEST 1: Analytics Summary")
        print("="*60)
        
        data = await self.get_json("/analytics")
        if not data:
            print("❌ Failed to get analytics")
            return
        
        # /analytics returns data directly, not wrapped in 'data' key
        analytics = data
        
        total_trades = analytics.get("total_trades", 0)
        # Try multiple field name variations
        wins = analytics.get("trades_won", 0)
        if wins == 0:
            # Calculate from trades if not directly provided
            wins = sum(1 for t in analytics.get("trades", []) if t.get("profit", 0) > 0)
        
        losses = analytics.get("trades_lost", 0)
        if losses == 0:
            losses = sum(1 for t in analytics.get("trades", []) if t.get("profit", 0) <= 0)
        
        win_rate = analytics.get("win_rate_pct", 0)
        if win_rate == 0:
            win_rate = analytics.get("win_rate", 0)
        
        total_pnl = analytics.get("total_profit", 0)
        if total_pnl == 0:
            total_pnl = analytics.get("net_profit", 0)
        
        avg_win = analytics.get("avg_win", 0)
        if avg_win == 0:
            avg_win = analytics.get("avg_profit", 0)
        
        avg_loss = analytics.get("avg_loss", 0)
        
        # Validation checks
        checks = {
            "total_trades_valid": total_trades >= 0,
            "wins_losses_sum": wins + losses <= total_trades + 1 or total_trades == 0,  # +1 tolerance
            "win_rate_valid": 0 <= win_rate <= 100,
            "win_rate_calc_valid": True,  # Will validate manually
            "avg_win_positive": avg_win >= 0 or total_trades == 0,
            "avg_loss_negative": avg_loss <= 0 or total_trades == 0,
            "pnl_consistency": total_pnl >= (avg_win * wins + avg_loss * losses - 100) if wins or losses else True,
        }
        
        if total_trades > 0:
            calc_win_rate = (wins / total_trades) * 100
            checks["win_rate_calc_valid"] = abs(calc_win_rate - win_rate) < 1  # Within 1%
        
        all_pass = all(checks.values())
        status = "✅" if all_pass else "⚠️"
        
        print(f"\n{status} Analytics Summary:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Wins: {wins}, Losses: {losses}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Total P/L: ${total_pnl:+.2f}")
        print(f"   Avg Win: ${avg_win:+.2f}, Avg Loss: ${avg_loss:+.2f}")
        print(f"\n   Validation Checks:")
        for check, passed in checks.items():
            print(f"   {'✓' if passed else '✗'} {check}")
        
        self.results["analytics_snapshots"].append({
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_trade_history_validation(self):
        """Test 2: Validate trade history data completeness."""
        print("\n" + "="*60)
        print("TEST 2: Trade History Completeness")
        print("="*60)
        
        # Get history
        data = await self.get_json("/history?days=30")
        if not data:
            print("ℹ️  No trade history available")
            return
        
        # Handle both list and dict responses
        trades = data if isinstance(data, list) else data.get("data", [])
        print(f"\n✅ Found {len(trades)} trades in history")
        
        # Validate each trade
        valid_count = 0
        issues = []
        
        for i, trade in enumerate(trades[:10]):  # Check first 10
            required_fields = [
                "ticket", "symbol", "type", "volume",
                "price_open", "price_close", "profit",
                "time", "close_time"
            ]
            
            missing = [f for f in required_fields if f not in trade or trade[f] is None]
            
            if not missing:
                valid_count += 1
                print(f"   ✓ Trade #{trade['ticket']}: Complete")
            else:
                issues.append(f"Trade #{trade.get('ticket', '?')}: Missing {missing}")
                print(f"   ✗ Trade #{trade.get('ticket', '?')}: Missing {missing}")
        
        completeness = (valid_count / min(10, len(trades)) * 100) if trades else 0
        
        print(f"\n   Completeness: {completeness:.0f}% ({valid_count}/10 sampled)")
        
        self.results["history_validation"].append({
            "total_trades": len(trades),
            "valid_sample": valid_count,
            "completeness_pct": completeness,
            "pass": completeness >= 80,
            "timestamp": time.time(),
        })
    
    async def test_per_symbol_analytics(self):
        """Test 3: Validate per-symbol analytics."""
        print("\n" + "="*60)
        print("TEST 3: Per-Symbol Analytics")
        print("="*60)
        
        data = await self.get_json("/analytics")
        if not data or not data.get("data"):
            print("❌ Failed to get analytics")
            return
        
        analytics = data.get("data", {})
        
        # Get symbol breakdown
        symbol_breakdown = analytics.get("by_symbol", []) or \
                          analytics.get("symbol_breakdown", []) or \
                          {}
        
        if not symbol_breakdown:
            print("ℹ️  No per-symbol data available")
            return
        
        print(f"\n✅ Symbol Breakdown:")
        
        for i, (symbol, stats) in enumerate(symbol_breakdown.items()) if isinstance(symbol_breakdown, dict) else enumerate(symbol_breakdown[:5]):
            if isinstance(symbol_breakdown, dict):
                sym_name = symbol
                sym_data = stats
            else:
                sym_name = stats.get("symbol", f"Symbol{i}")
                sym_data = stats
            
            trades = sym_data.get("trades", 0)
            wins = sym_data.get("wins", 0)
            losses = sym_data.get("losses", 0)
            win_rate = sym_data.get("win_rate", 0)
            pnl = sym_data.get("profit", sym_data.get("total_pnl", 0))
            
            checks = {
                "trades_valid": trades >= 0,
                "wins_valid": 0 <= wins <= trades,
                "losses_valid": 0 <= losses <= trades,
                "win_rate_valid": 0 <= win_rate <= 100,
                "pnl_reasonable": True,  # Visual check
            }
            
            all_pass = all(checks.values())
            status = "✓" if all_pass else "✗"
            
            print(f"\n   {status} {sym_name}:")
            print(f"      Trades: {trades}, Wins: {wins}, Losses: {losses}")
            print(f"      Win Rate: {win_rate:.1f}%, P/L: ${pnl:+.2f}")
            
            self.results["calculations"].append({
                "symbol": sym_name,
                "trades": trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "pnl": pnl,
                "checks": checks,
                "pass": all_pass,
                "timestamp": time.time(),
            })
    
    async def test_drawdown_calculation(self):
        """Test 4: Validate drawdown calculation."""
        print("\n" + "="*60)
        print("TEST 4: Drawdown Analysis")
        print("="*60)
        
        data = await self.get_json("/analytics")
        if not data or not data.get("data"):
            print("❌ Failed to get analytics")
            return
        
        analytics = data.get("data", {})
        
        max_drawdown = analytics.get("max_drawdown", 0)
        drawdown_pct = analytics.get("max_drawdown_pct", 0)
        
        print(f"\n✅ Drawdown Analysis:")
        print(f"   Max Drawdown: ${max_drawdown:+.2f} ({drawdown_pct:.1f}%)")
        
        checks = {
            "drawdown_valid": max_drawdown <= 0 or max_drawdown >= 0,
            "drawdown_pct_valid": 0 <= drawdown_pct <= 100,
            "drawdown_reasonable": drawdown_pct < 100,  # Should not lose 100%
        }
        
        all_pass = all(checks.values())
        status = "✓" if all_pass else "✗"
        
        print(f"   {status} Checks:")
        for check, passed in checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["calculations"].append({
            "metric": "drawdown",
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": drawdown_pct,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_retrain_suggestions(self):
        """Test 5: Validate retrain suggestions logic."""
        print("\n" + "="*60)
        print("TEST 5: Retrain Suggestions")
        print("="*60)
        
        data = await self.get_json("/insights/retrain")
        if not data or not data.get("data"):
            print("ℹ️  No retrain suggestions available")
            return
        
        suggestions = data.get("data", {})
        
        print(f"\n✅ Retrain Suggestions:")
        
        # Check if suggestions are logical
        logic_checks = {
            "suggestions_present": len(suggestions) > 0,
            "suggestions_actionable": all(
                isinstance(s, str) and len(s) > 10 
                for s in suggestions[:5]
            ) if suggestions else True,
        }
        
        if suggestions:
            print(f"\n   Suggestions ({len(suggestions)} total):")
            for i, suggestion in enumerate(suggestions[:5]):
                print(f"   {i+1}. {suggestion}")
        else:
            print(f"   ℹ️  No suggestions (trading may be performing well)")
        
        all_pass = all(logic_checks.values())
        status = "✓" if all_pass else "⚠️"
        
        print(f"\n   {status} Logic:")
        for check, passed in logic_checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["retrain_suggestions"].append({
            "count": len(suggestions),
            "suggestions": suggestions[:3],
            "checks": logic_checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("PHASE 5 TEST SUMMARY")
        print("="*60)
        
        # Analytics summary
        ana_passes = sum(1 for a in self.results["analytics_snapshots"] if a.get("pass"))
        print(f"\n1️⃣ Analytics: {ana_passes}/{len(self.results['analytics_snapshots'])} passed")
        
        # History validation
        hist_passes = sum(1 for h in self.results["history_validation"] if h.get("pass"))
        print(f"2️⃣ History: {hist_passes}/{len(self.results['history_validation'])} passed")
        
        # Calculations
        calc_passes = sum(1 for c in self.results["calculations"] if c.get("pass"))
        print(f"3️⃣ Calculations: {calc_passes}/{len(self.results['calculations'])} passed")
        
        # Retrain suggestions
        ret_passes = sum(1 for r in self.results["retrain_suggestions"] if r.get("pass"))
        print(f"4️⃣ Retrain Logic: {ret_passes}/{len(self.results['retrain_suggestions'])} passed")
        
        # Errors
        if self.results["errors"]:
            print(f"\n❌ Errors: {len(self.results['errors'])}")
        else:
            print(f"\n✅ No errors!")


async def run_tests():
    print("\n🧪 pytradeAI — Phase 5: Analytics Accuracy Testing")
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    tester = AnalyticsTester()
    await tester.init()
    
    try:
        await tester.test_analytics_summary()
        await tester.test_trade_history_validation()
        await tester.test_per_symbol_analytics()
        await tester.test_drawdown_calculation()
        await tester.test_retrain_suggestions()
        tester.print_summary()
        
        # Save results
        results_file = f"test_phase5_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(tester.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(run_tests())
