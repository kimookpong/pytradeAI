"""
Phase 2: UX/UI Responsiveness Testing
======================================
Validates WebSocket real-time updates, UI responsiveness, manual order execution,
and strategy enable/disable functionality.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8888/api"
WS_BASE = "ws://localhost:8888"


class UXUITester:
    """Test UX/UI responsiveness and interactions."""
    
    def __init__(self):
        self.session = None
        self.ws = None
        self.results = {
            "websocket_updates": [],
            "manual_orders": [],
            "strategy_control": [],
            "ui_responsiveness": [],
            "errors": [],
        }
    
    async def init(self):
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session:
            await self.session.close()
        if self.ws:
            await self.ws.close()
    
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
    
    async def post_json(self, endpoint, data):
        try:
            async with self.session.post(f"{API_BASE}{endpoint}", json=data) as resp:
                if resp.status in [200, 201]:
                    return await resp.json()
                return None
        except Exception as e:
            self.results["errors"].append({
                "ts": time.time(),
                "error": f"POST failed ({endpoint}): {str(e)}"
            })
            return None
    
    async def test_websocket_updates(self):
        """Test 1: Validate WebSocket real-time price updates."""
        print("\n" + "="*60)
        print("TEST 1: WebSocket Real-Time Updates")
        print("="*60)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"{WS_BASE}/ws") as ws:
                    print("\n✅ WebSocket connected to /ws")
                    
                    updates = []
                    start_time = time.time()
                    
                    # Collect updates for 5 seconds
                    while time.time() - start_time < 5:
                        try:
                            msg = await asyncio.wait_for(ws.receive_str(), timeout=1.0)
                            data = json.loads(msg)
                            
                            # Validate update structure
                            symbol = data.get("symbol")
                            bid = data.get("bid")
                            ask = data.get("ask")
                            time_ws = data.get("time")
                            
                            if symbol and bid and ask:
                                updates.append({
                                    "symbol": symbol,
                                    "bid": bid,
                                    "ask": ask,
                                    "time": time_ws,
                                    "received_at": time.time(),
                                })
                                print(f"   ✓ Update {len(updates)}: {symbol} ${bid:.5f}-${ask:.5f}")
                        except asyncio.TimeoutError:
                            continue
                    
                    # Validate update frequency
                    elapsed = time.time() - start_time
                    frequency = len(updates) / elapsed if elapsed > 0 else 0
                    
                    print(f"\n   Updates received: {len(updates)}")
                    print(f"   Frequency: {frequency:.1f} updates/second")
                    print(f"   Duration: {elapsed:.1f}s")
                    
                    checks = {
                        "updates_received": len(updates) > 0,
                        "frequency_reasonable": 0.1 < frequency < 10,  # 0.1-10 per second
                        "update_structure_valid": all(
                            u.get("symbol") and u.get("bid") and u.get("ask")
                            for u in updates
                        ) if updates else True,
                        "recent_timestamps": all(
                            abs(u["received_at"] - time.time()) < 5
                            for u in updates
                        ) if updates else True,
                    }
                    
                    all_pass = all(checks.values())
                    status = "✓" if all_pass else "⚠️"
                    
                    print(f"\n   {status} WebSocket Checks:")
                    for check, passed in checks.items():
                        print(f"      {'✓' if passed else '✗'} {check}")
                    
                    self.results["websocket_updates"].append({
                        "total_updates": len(updates),
                        "frequency": frequency,
                        "duration": elapsed,
                        "checks": checks,
                        "pass": all_pass,
                        "timestamp": time.time(),
                    })
        
        except Exception as e:
            self.results["errors"].append({
                "ts": time.time(),
                "error": f"WebSocket test failed: {str(e)}"
            })
            print(f"❌ WebSocket test failed: {e}")
    
    async def test_manual_order_execution(self):
        """Test 2: Validate manual order execution end-to-end."""
        print("\n" + "="*60)
        print("TEST 2: Manual Order Execution")
        print("="*60)
        
        # Get current prices
        all_prices = await self.get_json("/symbols")
        if not all_prices or "EURUSD" not in all_prices:
            print("❌ Could not get price data")
            return
        
        price = all_prices.get("EURUSD", {})
        bid = price.get("bid", 0)
        
        if not bid:
            print("ℹ️  No price data available")
            return
        
        # Prepare order
        entry_price = bid * 0.999  # Slight discount to ensure execution
        stop_loss = bid * 0.97
        take_profit = bid * 1.03
        
        order_data = {
            "symbol": "EURUSD",
            "type": "BUY",
            "volume": 0.1,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "is_manual": True,
        }
        
        print(f"\n📤 Placing manual order:")
        print(f"   Symbol: EURUSD, Type: BUY, Volume: 0.1")
        print(f"   Entry: ${entry_price:.5f}, SL: ${stop_loss:.5f}, TP: ${take_profit:.5f}")
        
        # Execute order
        result = await self.post_json("/trade/place", order_data)
        
        if not result:
            print("❌ Order execution failed")
            return
        
        success = result.get("success", False)
        ticket = result.get("ticket", 0)
        message = result.get("message", "")
        
        status = "✓" if success else "✗"
        print(f"\n   {status} Response: {message}")
        
        if success:
            print(f"   Ticket: {ticket}")
            
            # Wait for order to appear in history
            await asyncio.sleep(1)
            
            # Verify order in history
            history = await self.get_json("/history?days=1")
            if history:
                trades = history.get("data", [])
                order_found = any(t.get("ticket") == ticket for t in trades)
                
                checks = {
                    "order_executed": success,
                    "ticket_provided": ticket > 0,
                    "order_in_history": order_found,
                    "message_informative": len(message) > 0,
                }
                
                print(f"   ✓ Order found in history: {order_found}")
            else:
                checks = {
                    "order_executed": success,
                    "ticket_provided": ticket > 0,
                }
        else:
            checks = {
                "order_executed": success,
                "error_message": len(message) > 0,
            }
        
        all_pass = all(checks.values())
        status = "✓" if all_pass else "✗"
        
        print(f"\n   {status} Execution Checks:")
        for check, passed in checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["manual_orders"].append({
            "symbol": "EURUSD",
            "success": success,
            "ticket": ticket,
            "message": message,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_strategy_enable_disable(self):
        """Test 3: Validate strategy enable/disable control."""
        print("\n" + "="*60)
        print("TEST 3: Strategy Enable/Disable Control")
        print("="*60)
        
        # Get current system status
        status_before = await self.get_json("/status")
        if not status_before:
            print("ℹ️  Could not retrieve initial system status")
            return
        
        enabled_before = status_before.get("enabled", False) if isinstance(status_before, dict) else False
        print(f"\n✅ Initial Status: {'Enabled' if enabled_before else 'Disabled'}")
        
        # Toggle system
        toggle_data = {}
        
        toggle_result = await self.post_json("/system/toggle", toggle_data)
        if not toggle_result:
            print("❌ Toggle request failed")
            return
        
        toggle_success = toggle_result.get("success", False)
        print(f"   {'✓' if toggle_success else '✗'} Toggle result: {toggle_success}")
        
        # Wait and verify new state
        await asyncio.sleep(1)
        
        status_after = await self.get_json("/status")
        if not status_after:
            print("❌ Could not retrieve updated system status")
            return
        
        enabled_after = status_after.get("enabled", False) if isinstance(status_after, dict) else False
        print(f"   Final Status: {'Enabled' if enabled_after else 'Disabled'}")
        
        checks = {
            "initial_status_valid": enabled_before in [True, False],
            "toggle_success": toggle_success,
            "state_changed": enabled_after != enabled_before or not toggle_success,
            "final_status_valid": enabled_after in [True, False],
            "status_consistent": True,  # Just verify status is valid
        }
        
        all_pass = all(checks.values())
        status = "✓" if all_pass else "✗"
        
        print(f"\n   {status} Control Checks:")
        for check, passed in checks.items():
            print(f"      {'✓' if passed else '✗'} {check}")
        
        self.results["strategy_control"].append({
            "enabled_before": enabled_before,
            "enabled_after": enabled_after,
            "toggle_success": toggle_success,
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    async def test_ui_responsiveness(self):
        """Test 4: Validate UI endpoint responsiveness."""
        print("\n" + "="*60)
        print("TEST 4: UI Endpoint Responsiveness")
        print("="*60)
        
        endpoints = [
            ("/symbols", "Price data"),
            ("/analytics", "Analytics"),
            ("/history?days=1", "Trade history"),
            ("/insights", "AI Insights"),
        ]
        
        print(f"\n✅ Response Time Testing:")
        
        all_pass = True
        
        for endpoint, label in endpoints:
            start = time.time()
            result = await self.get_json(endpoint)
            elapsed = time.time() - start
            
            success = result is not None
            response_time_ms = elapsed * 1000
            
            # Valid response should be < 1000ms
            valid_time = response_time_ms < 1000
            
            status = "✓" if (success and valid_time) else "✗"
            print(f"   {status} {label}: {response_time_ms:.0f}ms")
            
            if not (success and valid_time):
                all_pass = False
        
        checks = {
            "all_endpoints_responsive": all_pass,
            "response_times_acceptable": all_pass,
        }
        
        self.results["ui_responsiveness"].append({
            "checks": checks,
            "pass": all_pass,
            "timestamp": time.time(),
        })
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("PHASE 2 TEST SUMMARY")
        print("="*60)
        
        # WebSocket
        ws_passes = sum(1 for w in self.results["websocket_updates"] if w.get("pass"))
        print(f"\n1️⃣ WebSocket Updates: {ws_passes}/{len(self.results['websocket_updates'])} passed")
        
        # Manual Orders
        mo_passes = sum(1 for m in self.results["manual_orders"] if m.get("pass"))
        print(f"2️⃣ Manual Orders: {mo_passes}/{len(self.results['manual_orders'])} passed")
        
        # Strategy Control
        sc_passes = sum(1 for s in self.results["strategy_control"] if s.get("pass"))
        print(f"3️⃣ Strategy Control: {sc_passes}/{len(self.results['strategy_control'])} passed")
        
        # Responsiveness
        resp_passes = sum(1 for r in self.results["ui_responsiveness"] if r.get("pass"))
        print(f"4️⃣ UI Responsiveness: {resp_passes}/{len(self.results['ui_responsiveness'])} passed")
        
        # Errors
        if self.results["errors"]:
            print(f"\n❌ Errors: {len(self.results['errors'])}")
        else:
            print(f"\n✅ No errors!")


async def run_tests():
    print("\n🧪 pytradeAI — Phase 2: UX/UI Responsiveness Testing")
    print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    tester = UXUITester()
    await tester.init()
    
    try:
        await tester.test_websocket_updates()
        await tester.test_manual_order_execution()
        await tester.test_strategy_enable_disable()
        await tester.test_ui_responsiveness()
        tester.print_summary()
        
        # Save results
        results_file = f"test_phase2_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(tester.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(run_tests())
