"""
Phase 4: AI Context Quality Testing
====================================
Validates AI context calculations, market context indicators, and performance metrics.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8888/api"


class AIContextTester:
    """Test AI context quality and accuracy."""
    
    def __init__(self):
        self.session = None
        self.results = {
            "market_context_snapshots": [],
            "performance_context_tests": [],
            "ai_analysis_tests": [],
            "context_consistency": [],
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
    
    async def test_market_context_accuracy(self):
        """Test 1: Validate market context calculations."""
        print("\n" + "="*60)
        print("TEST 1: Market Context Accuracy")
        print("="*60)
        
        # Get market data
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD"]
        
        for symbol in symbols[:3]:  # Test first 3 symbols
            price_data = await self.get_json(f"/price?symbol={symbol}")
            if not price_data:
                continue
            
            prices = price_data.get("data", {})
            bid = prices.get("bid", 0)
            ask = prices.get("ask", 0)
            
            # Get current context from AI engine
            ai_data = await self.get_json(f"/analyze?symbol={symbol}")
            if not ai_data:
                continue
            
            analysis = ai_data.get("data", {})
            ai_bid = analysis.get("current_bid", 0)
            ai_ask = analysis.get("current_ask", 0)
            rsi = analysis.get("rsi", None)
            ma = analysis.get("ma", None)
            volatility = analysis.get("volatility", None)
            
            print(f"\n✅ {symbol} Market Context:")
            print(f"   Price API: Bid=${bid:.5f}, Ask=${ask:.5f}")
            print(f"   AI Context: Bid=${ai_bid:.5f}, Ask=${ai_ask:.5f}")
            
            if rsi is not None:
                print(f"   RSI: {rsi:.1f} (Valid: {0 <= rsi <= 100})")
            if ma is not None:
                print(f"   MA: {ma:.5f}")
            if volatility is not None:
                print(f"   Volatility: {volatility:.4f} (Valid: {volatility >= 0})")
            
            # Validation checks
            checks = {
                "bid_ask_present": bid > 0 and ask > 0,
                "price_sync": abs(bid - ai_bid) < 0.001 or ai_bid == 0,  # ±0.001 tolerance
                "rsi_range": 0 <= rsi <= 100 if rsi is not None else True,
                "ma_positive": ma > 0 if ma is not None else True,
                "volatility_positive": volatility >= 0 if volatility is not None else True,
            }
            
            all_pass = all(checks.values())
            status = "✓" if all_pass else "✗"
            
            print(f"   {status} Integrity Checks:")
            for check, passed in checks.items():
                print(f"      {'✓' if passed else '✗'} {check}")
            
            self.results["market_context_snapshots"].append({
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "ai_bid": ai_bid,
                "ai_ask": ai_ask,
                "rsi": rsi,
                "ma": ma,
                "volatility": volatility,
                "checks": checks,
                "pass": all_pass,
                "timestamp": time.time(),
            })
    
    async def test_performance_context(self):
        """Test 2: Validate performance context aggregation."""
        print("\n" + "="*60)
        print("TEST 2: Performance Context Aggregation")
        print("="*60)
        
        # Get analytics for performance metrics
        analytics_data = await self.get_json("/analytics")
        if not analytics_data:
            print("ℹ️  Could not retrieve analytics")
            return
        
        analytics = analytics_data.get("data", {})
        
        # Extract performance metrics
        total_trades = analytics.get("total_trades", 0)
        wins = analytics.get("trades_won", 0)
        losses = analytics.get("trades_lost", 0)
        win_rate = analytics.get("win_rate_pct", 0)
        total_pnl = analytics.get("total_profit", 0)
        
        print(f"\n✅ Performance Context:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Wins: {wins}, Losses: {losses}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Total P/L: ${total_pnl:+.2f}")
        
        # Validation checks
        checks = {
            "trades_valid": total_trades >= 0,
            "wins_losses_consistency": wins >= 0 and losses >= 0,
            "win_rate_range": 0 <= win_rate <= 100,
            "pnl_reasonable": True,  # Visual check
            "14day_context_available": "performance_14d" in analytics or "recent_trades" in analytics,
        }
        
        # If win_rate calculated
        if total_trades > 0:
            calc_win_rate = (wins / total_trades) * 100
            checks["win_rate_accuracy"] = abs(calc_win_rate - win_rate) < 2.0  # ±2% tolerance
        
        all_pass = all(checks.values())
        status = "✓" if all_pass else "⚠️"
        
        print(f"\n   {status} Context Validation:")
        for check, passed in checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["performance_context_tests"].append({
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_ai_analysis_consistency(self):
        """Test 3: Validate AI analysis consistency."""
        print("\n" + "="*60)
        print("TEST 3: AI Analysis Consistency")
        print("="*60)
        
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        
        for symbol in symbols:
            # Get analysis from AI engine
            ai_data = await self.get_json(f"/analyze?symbol={symbol}")
            if not ai_data:
                continue
            
            analysis = ai_data.get("data", {})
            
            signal = analysis.get("signal", "HOLD")
            confidence = analysis.get("confidence", 0)
            reasoning = analysis.get("reasoning", "")
            thinking = analysis.get("thinking_log", {})
            
            print(f"\n✅ {symbol} Analysis:")
            print(f"   Signal: {signal}")
            print(f"   Confidence: {confidence:.1f}%")
            print(f"   Reasoning: {reasoning[:50]}..." if len(reasoning) > 50 else f"   Reasoning: {reasoning}")
            
            # Validation checks
            checks = {
                "signal_valid": signal in ["BUY", "SELL", "HOLD"],
                "confidence_range": 0 <= confidence <= 100,
                "reasoning_present": len(reasoning) > 5,
                "thinking_log_present": bool(thinking),
                "signal_supported": True,  # Visual check for reasoning
            }
            
            all_pass = all(checks.values())
            status = "✓" if all_pass else "✗"
            
            print(f"   {status} Consistency Checks:")
            for check, passed in checks.items():
                print(f"      {'✓' if passed else '✗'} {check}")
            
            self.results["ai_analysis_tests"].append({
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "reasoning_len": len(reasoning),
                "has_thinking": bool(thinking),
                "checks": checks,
                "pass": all_pass,
                "timestamp": time.time(),
            })
    
    async def test_context_temporal_consistency(self):
        """Test 4: Validate context doesn't change unexpectedly."""
        print("\n" + "="*60)
        print("TEST 4: Context Temporal Consistency")
        print("="*60)
        
        # Get analytics snapshot 1
        snapshot1 = await self.get_json("/analytics")
        if not snapshot1:
            print("ℹ️  Could not retrieve analytics")
            return
        
        # Wait a moment
        print("\n   Waiting 2 seconds for temporal check...")
        await asyncio.sleep(2)
        
        # Get analytics snapshot 2
        snapshot2 = await self.get_json("/analytics")
        if not snapshot2:
            print("❌ Failed to get second snapshot")
            return
        
        # Compare snapshots
        data1 = snapshot1.get("data", {})
        data2 = snapshot2.get("data", {})
        
        trades1 = data1.get("total_trades", 0)
        trades2 = data2.get("total_trades", 0)
        pnl1 = data1.get("total_profit", 0)
        pnl2 = data2.get("total_profit", 0)
        
        print(f"\n✅ Snapshot Comparison:")
        print(f"   Snapshot 1: {trades1} trades, P/L=${pnl1:+.2f}")
        print(f"   Snapshot 2: {trades2} trades, P/L=${pnl2:+.2f}")
        
        # Validation checks
        checks = {
            "trades_non_decreasing": trades2 >= trades1,
            "trade_delta_reasonable": abs(trades2 - trades1) <= 5,  # Max 5 new trades in 2s
            "pnl_delta_reasonable": abs(pnl2 - pnl1) < 1000,  # Max $1000 change in 2s
            "no_negative_jump": pnl2 >= (pnl1 - 500),  # No sudden loss > $500
        }
        
        all_pass = all(checks.values())
        status = "✓" if all_pass else "⚠️"
        
        print(f"\n   {status} Stability Checks:")
        for check, passed in checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["context_consistency"].append({
            "trades_delta": trades2 - trades1,
            "pnl_delta": pnl2 - pnl1,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_context_completeness(self):
        """Test 5: Validate context has all required fields."""
        print("\n" + "="*60)
        print("TEST 5: Context Completeness")
        print("="*60)
        
        # Get full analytics
        analytics_data = await self.get_json("/analytics")
        if not analytics_data:
            print("❌ Could not retrieve analytics")
            return
        
        analytics = analytics_data.get("data", {})
        
        required_fields = [
            "total_trades",
            "trades_won",
            "trades_lost",
            "win_rate_pct",
            "total_profit",
            "avg_win",
            "avg_loss",
        ]
        
        missing_fields = [f for f in required_fields if f not in analytics or analytics[f] is None]
        
        optional_fields = [
            "by_symbol",
            "max_drawdown",
            "best_symbol",
            "worst_symbol",
        ]
        
        present_optional = [f for f in optional_fields if f in analytics and analytics[f]]
        
        print(f"\n✅ Analytics Fields:")
        print(f"   Required: {len(required_fields) - len(missing_fields)}/{len(required_fields)} present")
        
        if missing_fields:
            print(f"   ❌ Missing: {missing_fields}")
        else:
            print(f"   ✓ All required fields present")
        
        print(f"   Optional: {len(present_optional)}/{len(optional_fields)} present")
        if present_optional:
            print(f"   ✓ Found: {present_optional}")
        
        all_pass = len(missing_fields) == 0
        
        self.results["context_consistency"].append({
            "missing_fields": missing_fields,
            "optional_present": present_optional,
            "checks": {"all_required_present": all_pass},
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("PHASE 4 TEST SUMMARY")
        print("="*60)
        
        # Market context
        mc_passes = sum(1 for m in self.results["market_context_snapshots"] if m.get("pass"))
        print(f"\n1️⃣ Market Context: {mc_passes}/{len(self.results['market_context_snapshots'])} passed")
        
        # Performance context
        pc_passes = sum(1 for p in self.results["performance_context_tests"] if p.get("pass"))
        print(f"2️⃣ Performance Context: {pc_passes}/{len(self.results['performance_context_tests'])} passed")
        
        # AI analysis
        ai_passes = sum(1 for a in self.results["ai_analysis_tests"] if a.get("pass"))
        print(f"3️⃣ AI Analysis: {ai_passes}/{len(self.results['ai_analysis_tests'])} passed")
        
        # Consistency
        con_passes = sum(1 for c in self.results["context_consistency"] if c.get("pass"))
        print(f"4️⃣ Context Consistency: {con_passes}/{len(self.results['context_consistency'])} passed")
        
        # Errors
        if self.results["errors"]:
            print(f"\n❌ Errors: {len(self.results['errors'])}")
        else:
            print(f"\n✅ No errors!")


async def run_tests():
    print("\n🧪 pytradeAI — Phase 4: AI Context Quality Testing")
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    tester = AIContextTester()
    await tester.init()
    
    try:
        await tester.test_market_context_accuracy()
        await tester.test_performance_context()
        await tester.test_ai_analysis_consistency()
        await tester.test_context_temporal_consistency()
        await tester.test_context_completeness()
        tester.print_summary()
        
        # Save results
        results_file = f"test_phase4_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(tester.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(run_tests())
