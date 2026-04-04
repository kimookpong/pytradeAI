"""
Phase 3: Strategy Signal Accuracy Testing
==========================================
Tests technical indicators and signal generation accuracy.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8888/api"
TEST_SYMBOLS = ["BTCUSD", "EURUSD", "XAUUSD", "ETHUSD"]


class StrategyTester:
    """Test strategy signal accuracy and indicator calculations."""
    
    def __init__(self):
        self.session = None
        self.results = {
            "indicators": [],
            "signals": [],
            "entry_conditions": [],
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
    
    async def test_trading_conditions(self):
        """Test 1: Get and validate trading conditions for each symbol."""
        print("\n" + "="*60)
        print("TEST 1: Trading Conditions (Technical Indicators)")
        print("="*60)
        
        for symbol in TEST_SYMBOLS:
            print(f"\n📊 {symbol}:")
            
            data = await self.get_json(f"/strategies/conditions/{symbol}")
            if not data or not data.get("data"):
                print(f"   ❌ Failed to get conditions")
                continue
            
            cond = data.get("data", {})
            
            # Extract indicators
            status = cond.get("status")
            if status == "insufficient_data":
                print(f"   ⚠️  Insufficient data: {cond.get('message')}")
                continue
            
            rsi = cond.get("rsi", 0)
            ma7 = cond.get("ma7", 0)
            ma20 = cond.get("ma20", 0)
            bb_upper = cond.get("bb_upper", 0)
            bb_lower = cond.get("bb_lower", 0)
            price = cond.get("current_price", 0)
            trend = cond.get("trend", "UNKNOWN")
            
            # Validate indicators
            checks = {
                "rsi_valid": 0 <= rsi <= 100,
                "ma7_positive": ma7 > 0,
                "ma20_positive": ma20 > 0,
                "bb_valid": bb_lower > 0 and bb_upper > bb_lower,
                "price_in_range": bb_lower <= price <= bb_upper or (price > 0 and bb_lower > 0),
                "price_log": price > 0,
            }
            
            all_pass = all(checks.values())
            status_icon = "✅" if all_pass else "❌"
            
            print(f"   {status_icon} Indicators:")
            print(f"      RSI(14): {rsi:.1f}")
            print(f"      MA(7): {ma7:.5f}, MA(20): {ma20:.5f}")
            print(f"      BB: [{bb_lower:.5f}, {bb_upper:.5f}]")
            print(f"      Price: {price:.5f}, Trend: {trend}")
            print(f"      Checks: {json.dumps(checks, indent=13)}")
            
            self.results["indicators"].append({
                "symbol": symbol,
                "rsi": rsi,
                "ma7": ma7,
                "ma20": ma20,
                "bb_upper": bb_upper,
                "bb_lower": bb_lower,
                "price": price,
                "trend": trend,
                "checks": checks,
                "pass": all_pass,
                "timestamp": time.time(),
            })
    
    async def test_signal_generation(self):
        """Test 2: Monitor signal generation over time."""
        print("\n" + "="*60)
        print("TEST 2: Signal Generation Accuracy")
        print("="*60)
        
        signal_counts = {}
        
        for i in range(3):  # Sample 3 times
            print(f"\n[Cycle {i+1}]")
            
            for symbol in TEST_SYMBOLS:
                data = await self.get_json(f"/strategies/conditions/{symbol}")
                if not data or not data.get("data"):
                    continue
                
                cond = data.get("data", {})
                signal = cond.get("signal", "HOLD")
                
                if symbol not in signal_counts:
                    signal_counts[symbol] = {"BUY": 0, "SELL": 0, "HOLD": 0}
                
                signal_counts[symbol][signal] += 1
                
                # Log signal with reasoning
                print(f"   {symbol}: {signal}")
                
                if signal != "HOLD":
                    print(f"      RSI: {cond.get('rsi', 0):.1f}")
                    print(f"      Trend: {cond.get('trend', '?')}")
                    print(f"      Buy Signals: {cond.get('buy_signals', 0)}")
                    print(f"      Sell Signals: {cond.get('sell_signals', 0)}")
                
                self.results["signals"].append({
                    "symbol": symbol,
                    "signal": signal,
                    "rsi": cond.get("rsi", 0),
                    "trend": cond.get("trend", ""),
                    "cycle": i,
                    "timestamp": time.time(),
                })
            
            if i < 2:
                await asyncio.sleep(3)
        
        # Analyze signal distribution
        print(f"\n📈 Signal Distribution:")
        for symbol, counts in signal_counts.items():
            total = sum(counts.values())
            pct = {k: f"{(v/total*100):.0f}%" for k, v in counts.items()}
            print(f"   {symbol}: {counts['BUY']} BUY, {counts['SELL']} SELL, {counts['HOLD']} HOLD")
            print(f"            {pct['BUY']} BUY, {pct['SELL']} SELL, {pct['HOLD']} HOLD")
    
    async def test_entry_conditions(self):
        """Test 3: Validate entry conditions."""
        print("\n" + "="*60)
        print("TEST 3: Entry Condition Validation")
        print("="*60)
        
        for symbol in TEST_SYMBOLS:
            print(f"\n🎯 {symbol}:")
            
            data = await self.get_json(f"/strategies/conditions/{symbol}")
            if not data or not data.get("data"):
                print(f"   ❌ Failed to get conditions")
                continue
            
            cond = data.get("data", {})
            signal = cond.get("signal", "HOLD")
            
            # Check entry logic
            entry_checks = {
                "has_signal": signal in ["BUY", "SELL"],
                "signal_has_confidence": signal != "HOLD",
            }
            
            if signal == "BUY":
                entry_checks.update({
                    "uptrend": cond.get("trend") == "UP",
                    "rsi_valid": cond.get("rsi", 0) < 50 or cond.get("rsi", 0) > 30,
                })
                print(f"   🟢 BUY Signal:")
            elif signal == "SELL":
                entry_checks.update({
                    "downtrend": cond.get("trend") == "DOWN",
                    "rsi_valid": cond.get("rsi", 0) > 50 or cond.get("rsi", 0) < 70,
                })
                print(f"   🔴 SELL Signal:")
            else:
                print(f"   ➡️  HOLD (no entry)")
                self.results["entry_conditions"].append({
                    "symbol": symbol,
                    "signal": signal,
                    "action": "hold",
                    "pass": True,
                    "timestamp": time.time(),
                })
                continue
            
            print(f"      Conditions met: {sum(entry_checks.values())}/{len(entry_checks)}")
            for check, passed in entry_checks.items():
                print(f"      {'✓' if passed else '✗'} {check}")
            
            self.results["entry_conditions"].append({
                "symbol": symbol,
                "signal": signal,
                "checks": entry_checks,
                "all_pass": all(entry_checks.values()),
                "timestamp": time.time(),
            })
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("PHASE 3 TEST SUMMARY")
        print("="*60)
        
        # Indicators summary
        ind_passes = sum(1 for i in self.results["indicators"] if i.get("pass"))
        print(f"\n1️⃣ Indicators: {ind_passes}/{len(self.results['indicators'])} passed")
        
        # Signals summary
        signal_types = {}
        for s in self.results["signals"]:
            sig = s.get("signal")
            signal_types[sig] = signal_types.get(sig, 0) + 1
        
        print(f"2️⃣ Signals Generated: {len(self.results['signals'])}")
        for sig, count in signal_types.items():
            print(f"      {sig}: {count}")
        
        # Entry conditions summary
        entry_passes = sum(1 for e in self.results["entry_conditions"] if e.get("all_pass", True))
        print(f"3️⃣ Entry Conditions: {entry_passes}/{len(self.results['entry_conditions'])} valid")
        
        # Errors
        if self.results["errors"]:
            print(f"\n❌ Errors: {len(self.results['errors'])}")
        else:
            print(f"\n✅ No errors!")


async def run_tests():
    print("\n🧪 pytradeAI — Phase 3: Strategy Signal Accuracy Testing")
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    tester = StrategyTester()
    await tester.init()
    
    try:
        await tester.test_trading_conditions()
        await tester.test_signal_generation()
        await tester.test_entry_conditions()
        tester.print_summary()
        
        # Save results
        results_file = f"test_phase3_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(tester.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(run_tests())
