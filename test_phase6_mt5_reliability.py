"""
Phase 6: MT5 Data Reliability Testing
======================================
Tests price accuracy, order execution, and trade history completeness.
Run this after starting the server to validate all data flows correctly.
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime, timedelta

# Configuration
API_BASE = "http://localhost:8888/api"
TEST_SYMBOLS = ["BTCUSD", "EURUSD", "XAUUSD"]
TEST_DURATION_SECONDS = 60  # Run tests for 1 minute
CYCLE_INTERVAL = 2  # Check every 2 seconds (matching WebSocket broadcast)


class MT5ReliabilityTester:
    """Test MT5 data reliability and order execution."""
    
    def __init__(self):
        self.session = None
        self.results = {
            "price_updates": [],
            "account_snapshots": [],
            "orders_placed": [],
            "positions_tracked": [],
            "history_queries": [],
            "errors": [],
        }
        self.test_start_time = None
        self.last_prices = {}
    
    async def init(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession()
        self.test_start_time = time.time()
    
    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    async def get_json(self, endpoint):
        """Fetch JSON from API endpoint."""
        try:
            async with self.session.get(f"{API_BASE}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = f"HTTP {resp.status} from {endpoint}"
                    self.results["errors"].append({"ts": time.time(), "error": error})
                    return None
        except Exception as e:
            error = f"Request failed ({endpoint}): {str(e)}"
            self.results["errors"].append({"ts": time.time(), "error": error})
            return None
    
    async def post_json(self, endpoint, payload):
        """POST JSON to API endpoint."""
        try:
            async with self.session.post(f"{API_BASE}{endpoint}", json=payload) as resp:
                if resp.status in [200, 201]:
                    return await resp.json()
                else:
                    error = f"HTTP {resp.status} from POST {endpoint}"
                    self.results["errors"].append({"ts": time.time(), "error": error})
                    return None
        except Exception as e:
            error = f"POST failed ({endpoint}): {str(e)}"
            self.results["errors"].append({"ts": time.time(), "error": error})
            return None
    
    async def test_price_accuracy(self):
        """Test 1: Validate price updates are accurate and realistic."""
        print("\n" + "="*60)
        print("TEST 1: Price Accuracy & Updates")
        print("="*60)
        
        all_prices = await self.get_json("/symbols")
        if not all_prices:
            print(f"❌ Failed to get prices")
            return
        
        for symbol in TEST_SYMBOLS:
            if symbol not in all_prices:
                print(f"❌ No price data for {symbol}")
                continue
            
            price = all_prices.get(symbol, {})
            bid = price.get("bid", 0)
            ask = price.get("ask", 0)
            spread = price.get("spread", 0)
            
            # Validation checks
            time_val = price.get("time", time.time())
            checks = {
                "bid_ask_valid": bid > 0 and ask > 0,
                "bid_less_than_ask": bid < ask,
                "spread_positive": spread >= 0,  # Spread can be 0
                "spread_matches": abs(spread - (ask - bid)) < 0.0001 if spread >= 0 else True,
                "time_recent": abs(time_val - time.time()) < 5,
            }
            
            all_pass = all(checks.values())
            status = "✅" if all_pass else "❌"
            
            print(f"\n{status} {symbol}:")
            print(f"   Bid: {bid:.5f}, Ask: {ask:.5f}, Spread: {spread:.5f}")
            
            self.results["price_updates"].append({
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "checks": checks,
                "pass": all_pass,
                "timestamp": time.time(),
            })
            
            self.last_prices[symbol] = {"bid": bid, "ask": ask}
    
    async def test_account_info(self):
        """Test 2: Validate account info accuracy and consistency."""
        print("\n" + "="*60)
        print("TEST 2: Account Info Accuracy")
        print("="*60)
        
        account = await self.get_json("/account")
        if not account:
            print("❌ Failed to get account info")
            return
        
        balance = account.get("balance", 0)
        equity = account.get("equity", 0)
        margin_used = account.get("margin", 0)
        free_margin = account.get("free_margin", 0)
        leverage = account.get("leverage", 100)
        
        # Validation checks
        checks = {
            "balance_positive": balance > 0,
            "equity_positive": equity > 0,
            "equity_gte_balance": equity >= balance,
            "margin_valid": margin_used >= 0,
            "free_margin_valid": free_margin >= 0,
            "equity_calc_valid": equity >= margin_used,
            "leverage_reasonable": 1 <= leverage <= 500,
        }
        
        all_pass = all(checks.values())
        status = "✅" if all_pass else "❌"
        
        print(f"\n{status} Account:")
        print(f"   Balance: ${balance:.2f}")
        print(f"   Equity: ${equity:.2f}")
        print(f"   Margin Used: ${margin_used:.2f}")
        print(f"   Free Margin: ${free_margin:.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Checks: {json.dumps({k: v for k, v in checks.items()}, indent=10)}")
        
        self.results["account_snapshots"].append({
            "balance": balance,
            "equity": equity,
            "margin": margin_used,
            "free_margin": free_margin,
            "leverage": leverage,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_order_execution(self):
        """Test 3: Place test orders and verify execution."""
        print("\n" + "="*60)
        print("TEST 3: Order Execution Reliability")
        print("="*60)
        
        # Place a small BUY order
        symbol = "EURUSD"
        payload = {
            "symbol": symbol,
            "order_type": "BUY",
            "volume": 0.01,
            "sl": 0,
            "tp": 0,
            "comment": "TEST_PHASE6_BUY"
        }
        
        print(f"\nPlacing test BUY order: {symbol} 0.01 lot")
        result = await self.post_json("/trade/place", payload)
        
        if result and result.get("success"):
            ticket = result.get("ticket")
            print(f"✅ Order executed: Ticket #{ticket}")
            
            self.results["orders_placed"].append({
                "symbol": symbol,
                "type": "BUY",
                "volume": 0.01,
                "ticket": ticket,
                "status": "placed",
                "timestamp": time.time(),
            })
            
            # Verify position appears immediately
            await asyncio.sleep(0.5)
            positions = await self.get_json("/positions")
            
            if positions and isinstance(positions, list):
                pos_list = positions
                matching_pos = [p for p in pos_list if p.get("symbol") == symbol and str(p.get("ticket")) == str(ticket)]
                
                if matching_pos:
                    pos = matching_pos[0]
                    print(f"✅ Position found immediately after order")
                    print(f"   Ticket: {pos.get('ticket')}")
                    print(f"   Entry: {pos.get('price_open'):.5f}")
                    print(f"   Current: {pos.get('price_current'):.5f}")
                    print(f"   P/L: ${pos.get('profit', 0):.2f}")
                else:
                    print(f"❌ Position not found in list after order")
            else:
                print(f"❌ Failed to fetch positions")
        else:
            print(f"❌ Order failed: {result.get('message', 'Unknown error') if result else 'No response'}")
    
    async def test_position_tracking(self):
        """Test 4: Monitor position P/L updates in real-time."""
        print("\n" + "="*60)
        print("TEST 4: Position Tracking & P/L Updates")
        print("="*60)
        
        positions = await self.get_json("/positions")
        
        if not positions or not isinstance(positions, list):
            print("ℹ️  No open positions to track")
            return
        
        pos_list = positions
        print(f"\nTracking {len(pos_list)} open position(s):")
        
        for pos in pos_list[:3]:  # Track first 3 positions
            ticket = pos.get("ticket")
            symbol = pos.get("symbol")
            pos_type = pos.get("type")
            volume = pos.get("volume")
            entry = pos.get("price_open")
            current = pos.get("price_current")
            pnl = pos.get("profit", 0)
            
            print(f"\n   Ticket #{ticket} ({pos_type} {symbol} {volume}lot):")
            print(f"   Entry: {entry:.5f}, Current: {current:.5f}")
            print(f"   P/L: ${pnl:.2f}")
            
            # Check P/L consistency
            if pos_type == "BUY":
                expected_pnl_direction = current > entry
            else:
                expected_pnl_direction = current < entry
            
            print(f"   P/L direction: {'✅ Correct' if expected_pnl_direction or pnl == 0 else '⚠️ Check manually'}")
            
            self.results["positions_tracked"].append({
                "ticket": ticket,
                "symbol": symbol,
                "type": pos_type,
                "volume": volume,
                "entry": entry,
                "current": current,
                "pnl": pnl,
                "pnl_consistency_check": expected_pnl_direction or pnl == 0,
                "timestamp": time.time(),
            })
    
    async def test_trade_history(self):
        """Test 5: Verify trade history completeness."""
        print("\n" + "="*60)
        print("TEST 5: Trade History Completeness")
        print("="*60)
        
        # Get history for last 1 day
        history = await self.get_json("/history?days=1")
        
        # Handle both list and dict responses
        trades = history if isinstance(history, list) else (history.get("data", []) if history else [])
        
        if not trades or len(trades) == 0:
            print("ℹ️  No trade history in last 1 day")
            self.results["history_queries"].append({
                "days": 1,
                "count": 0,
                "pass": True,
                "timestamp": time.time(),
            })
            return
        
        print(f"\n✅ Found {len(trades)} closed trades in last 1 day")
        
        # Validate each trade
        all_valid = True
        for trade in trades[:5]:  # Show first 5
            ticket = trade.get("ticket")
            symbol = trade.get("symbol")
            trade_type = trade.get("type")
            volume = trade.get("volume")
            open_price = trade.get("price_open")
            close_price = trade.get("price_close")
            profit = trade.get("profit")
            
            # Check completeness
            is_complete = all([
                ticket, symbol, trade_type, volume,
                open_price, close_price, profit is not None
            ])
            
            status = "✅" if is_complete else "❌"
            print(f"\n   {status} Ticket #{ticket}: {trade_type} {symbol} {volume}lot")
            print(f"      Entry: {open_price:.5f}, Close: {close_price:.5f}")
            print(f"      Profit: ${profit:.2f}")
            
            if not is_complete:
                all_valid = False
        
        self.results["history_queries"].append({
            "days": 1,
            "count": len(trades),
            "all_complete": all_valid,
            "pass": all_valid,
            "timestamp": time.time(),
        })
    
    async def test_continuous_monitoring(self):
        """Test 6: Continuous price monitoring with change detection."""
        print("\n" + "="*60)
        print(f"TEST 6: Continuous Monitoring ({TEST_DURATION_SECONDS}s)")
        print("="*60)
        
        cycles = int(TEST_DURATION_SECONDS / CYCLE_INTERVAL)
        price_changes = {sym: [] for sym in TEST_SYMBOLS}
        
        for cycle in range(cycles):
            elapsed = time.time() - self.test_start_time
            print(f"\n[Cycle {cycle+1}/{cycles}] Elapsed: {elapsed:.0f}s")
            
            all_prices = await self.get_json("/symbols")
            if not all_prices:
                continue
            
            for symbol in TEST_SYMBOLS:
                if symbol not in all_prices:
                    continue
                
                price_data = all_prices[symbol]
                bid = price_data.get("bid", 0)
                
                if symbol in self.last_prices:
                    prev_bid = self.last_prices[symbol]["bid"]
                    change = bid - prev_bid
                    change_pct = (change / prev_bid * 100) if prev_bid > 0 else 0
                    
                    price_changes[symbol].append({
                        "bid": bid,
                        "change": change,
                        "change_pct": change_pct,
                        "cycle": cycle,
                    })
                    
                    changed = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    print(f"   {symbol}: {bid:.5f} {changed} ({change_pct:+.4f}%)")
                else:
                    print(f"   {symbol}: {bid:.5f}")
                
                self.last_prices[symbol] = {"bid": bid}
            
            # Wait for next cycle
            if cycle < cycles - 1:
                await asyncio.sleep(CYCLE_INTERVAL)
        
        # Analyze price movement patterns
        print(f"\n📊 Price Movement Analysis:")
        for symbol, changes in price_changes.items():
            if not changes:
                continue
            
            total_moves = len(changes)
            moves_up = sum(1 for c in changes if c["change"] > 0)
            moves_down = sum(1 for c in changes if c["change"] < 0)
            moves_flat = total_moves - moves_up - moves_down
            
            avg_change = sum(abs(c["change"]) for c in changes) / total_moves if total_moves > 0 else 0
            healthy = moves_up > 0 and moves_down > 0 and avg_change > 0  # Price should move
            
            status = "✅" if healthy else "⚠️"
            print(f"\n   {status} {symbol}:")
            print(f"      Updates: {total_moves}, Up: {moves_up}, Down: {moves_down}, Flat: {moves_flat}")
            print(f"      Avg Change: {avg_change:.7f}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        # Price updates summary
        price_passes = sum(1 for p in self.results["price_updates"] if p.get("pass"))
        print(f"\n1️⃣ Price Updates: {price_passes}/{len(self.results['price_updates'])} passed")
        
        # Account summary
        account_passes = sum(1 for a in self.results["account_snapshots"] if a.get("pass"))
        print(f"2️⃣ Account Info: {account_passes}/{len(self.results['account_snapshots'])} passed")
        
        # Orders summary
        print(f"3️⃣ Orders Placed: {len(self.results['orders_placed'])}")
        
        # Positions summary
        print(f"4️⃣ Positions Tracked: {len(self.results['positions_tracked'])}")
        
        # History summary
        history_passes = sum(1 for h in self.results["history_queries"] if h.get("pass"))
        print(f"5️⃣ Trade History: {history_passes}/{len(self.results['history_queries'])} passed")
        
        # Errors summary
        if self.results["errors"]:
            print(f"\n❌ Errors Encountered: {len(self.results['errors'])}")
            for error in self.results["errors"][:5]:
                print(f"   - {error.get('error')}")
        else:
            print(f"\n✅ No errors encountered!")
        
        print("\n" + "="*60)


async def run_tests():
    """Run all tests."""
    print("\n🧪 pytradeAI — Phase 6: MT5 Data Reliability Testing")
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Server: http://localhost:8888")
    
    tester = MT5ReliabilityTester()
    await tester.init()
    
    try:
        # Run all tests
        await tester.test_price_accuracy()
        await tester.test_account_info()
        await tester.test_order_execution()
        await tester.test_position_tracking()
        await tester.test_trade_history()
        await tester.test_continuous_monitoring()
        
        # Print summary
        tester.print_summary()
        
        # Save results to file
        results_file = f"test_phase6_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(tester.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    print("\n⚠️  Make sure server is running: python -m uvicorn server:app --port 8888")
    print("Waiting 2 seconds before starting tests...\n")
    time.sleep(2)
    
    asyncio.run(run_tests())
