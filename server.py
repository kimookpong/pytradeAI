"""
pytradeAI — FastAPI Server
===========================
Main server with REST API + WebSocket for real-time browser dashboard.
"""

import asyncio
import collections
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from mt5_connector import MT5Connector
from trading_engine import TradingEngine
from smart_logic import SmartLogic
from ai_insights import AIInsights
from ai_engine import AIEngine
from backtest_engine import BacktestEngine


# ─── Request Models ─────────────────────────────────────────────

class MT5ConnectRequest(BaseModel):
    login: int = 0
    password: str = ""
    server: str = ""

class PlaceOrderRequest(BaseModel):
    symbol: str
    order_type: str   # "BUY" or "SELL"
    volume: float = 0.01
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""

class AISettingsRequest(BaseModel):
    symbol: str
    lot_size: Optional[float] = None
    sl_points: Optional[int] = None
    tp_points: Optional[int] = None
    cooldown: Optional[int] = None
    enabled: Optional[bool] = None

class AIProviderRequest(BaseModel):
    provider: Optional[str] = None          # "minimax" | "gemini"
    minimax_api_key: Optional[str] = None
    minimax_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    auto_trade_enabled: Optional[bool] = None
    analysis_interval: Optional[int] = None

class AISymbolSettingsRequest(BaseModel):
    symbol: str
    auto_trade: Optional[bool] = None
    lot_size: Optional[float] = None
    sl_points: Optional[int] = None
    tp_points: Optional[int] = None
    max_trades: Optional[int] = None

class SaveAccountRequest(BaseModel):
    name: str           # label e.g. "Demo ICMarkets"
    login: int = 0
    password: str = ""
    server: str = ""
    auto_connect: bool = False   # reconnect on startup


# ─── Saved Accounts Storage ─────────────────────────────────────
# All persistent data managed by frontend localStorage
# Backend maintains in-memory cache only for current session

# In-memory accounts storage (session-only, no file persistence)
_saved_accounts: list[dict] = []

def _load_accounts() -> list[dict]:
    """Load accounts from in-memory storage (frontend will provide via API)."""
    return list(_saved_accounts)

def _save_accounts(accounts: list[dict]):
    """Save accounts to in-memory storage only (no file writes)."""
    global _saved_accounts
    _saved_accounts = list(accounts)


# ─── System Log ──────────────────────────────────────────────────

_system_log: collections.deque = collections.deque(maxlen=500)

CATEGORY_ICONS = {
    "TRADE":    "💰",
    "SYSTEM":   "⚙️",
    "STRATEGY": "📡",
    "AI":       "🤖",
    "MT5":      "🔌",
    "ERROR":    "❌",
    "INFO":     "ℹ️",
}

def log_event(category: str, message: str, detail: str = ""):
    entry = {
        "ts":       datetime.now().strftime("%H:%M:%S"),
        "date":     datetime.now().strftime("%Y-%m-%d"),
        "category": category.upper(),
        "message":  message,
        "detail":   detail,
        "icon":     CATEGORY_ICONS.get(category.upper(), "•"),
    }
    _system_log.appendleft(entry)
    return entry


def broadcast_ai_thinking(thinking_entry: dict):
    """Callback to broadcast AI thinking logs to all connected WebSocket clients."""
    async def send_broadcast():
        for ws in list(ws_clients):
            try:
                await ws.send_json({
                    "type": "ai_thinking",
                    **thinking_entry
                })
            except Exception:
                pass
    
    # Schedule broadcast on event loop if available
    try:
        asyncio.create_task(send_broadcast())
    except RuntimeError:
        pass  # No event loop running


# ─── Global Instances ───────────────────────────────────────────

connector = MT5Connector(log_callback=log_event)
engine = TradingEngine(connector, log_callback=log_event)
smart = SmartLogic(connector)
insights = AIInsights(connector, log_callback=log_event)
ai_engine = AIEngine(connector, log_callback=log_event)
backtest = BacktestEngine(connector, engine)

# When AI is trading a symbol, skip the built-in strategy for that symbol
engine.set_ai_mode_fn(ai_engine.is_ai_active)

# Connected WebSocket clients
ws_clients: set[WebSocket] = set()


# ─── Lifespan ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — try auto-connect with saved default account
    accounts = _load_accounts()
    default = next((a for a in accounts if a.get("auto_connect")), None)
    if default and not connector.simulation_mode:
        print(f"🔑 Auto-connecting saved account: {default['name']}")
        connector.connect(login=default["login"], password=default["password"], server=default["server"])
        log_event("MT5", f"Auto-connected: {default['name']} ({default.get('server','')})")
    else:
        connector.connect()
        log_event("MT5", f"Connected ({'Simulation' if connector.simulation_mode else 'Live'} mode)")
    
    # Set up AI thinking callback for WebSocket broadcasts
    ai_engine.set_thinking_callback(broadcast_ai_thinking)
    
    asyncio.create_task(engine.run_loop())
    asyncio.create_task(ai_engine.run_loop())
    asyncio.create_task(broadcast_loop())
    print("=" * 50)
    print("🤖 pytradeAI started")
    print(f"📡 Mode: {'SIMULATION' if connector.simulation_mode else 'LIVE'}")
    print("🌐 Dashboard: http://localhost:8888")
    print("=" * 50)
    yield
    # Shutdown
    engine.stop()
    ai_engine.stop()
    connector.disconnect()
    print("🛑 Server shutdown")


app = FastAPI(title="pytradeAI", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Static Files ──────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse(str(static_dir / "index.html"))


# ─── REST API Endpoints ────────────────────────────────────────

@app.get("/api/account")
async def get_account():
    return connector.get_account_info()


@app.get("/api/positions")
async def get_positions():
    return connector.get_positions()


@app.get("/api/history")
async def get_history(days: int = 30):
    return connector.get_history(days)


@app.get("/api/strategies")
async def get_strategies():
    return engine.get_strategies()


@app.get("/api/strategies/{symbol}/conditions")
async def get_trading_conditions(symbol: str):
    """Get detailed trading conditions for a symbol (technical indicators + signals)."""
    conditions = engine.get_trading_conditions(symbol.upper())
    return conditions


@app.get("/api/status")
async def get_status():
    return engine.get_system_status()


@app.post("/api/system/toggle")
async def toggle_system():
    active = engine.toggle_system()
    log_event("SYSTEM", f"System {'activated' if active else 'paused'}")
    return {"system_active": active}


@app.post("/api/strategy/toggle/{symbol}")
async def toggle_strategy(symbol: str):
    result = engine.toggle_strategy(symbol.upper())
    state = "ON" if result.get("enabled") else "OFF"
    log_event("STRATEGY", f"{symbol.upper()} strategy turned {state}")
    return result


@app.get("/api/insights")
async def get_insights(days: int = 30):
    return insights.get_insights(days)


@app.get("/api/insights/retrain")
async def get_retrain_suggestions():
    return {"suggestions": insights.get_retrain_suggestions()}


@app.get("/api/rankings")
async def get_rankings():
    smart.update_prices()
    return smart.get_symbol_rankings()


@app.post("/api/analytics/import-test-trades")
async def import_test_trades():
    """
    DEBUG ENDPOINT: Import 50 sample trades for testing analytics.
    Populate mt5_connector._history with test data.
    """
    try:
        import random
        from datetime import timedelta
        from mt5_connector import HistoryDeal
        
        now = int(time.time())
        symbols = ["BTCUSD", "XAUUSD", "ETHUSD", "EURUSD", "GBPUSD"]
        strategies = ["Strategy-A", "Strategy-B", "Strategy-C"]
        
        # Clear existing history
        mt5_connector._history.clear()
        print(f"🗑️  Cleared history")
        
        # Generate 50 test trades
        for i in range(50):
            symbol = random.choice(symbols)
            trade_type = random.randint(0, 1)
            strategy = random.choice(strategies)
            
            # Win rate ~65%
            if random.random() < 0.65:
                profit = round(random.uniform(5, 150), 2)
            else:
                profit = round(random.uniform(-150, -5), 2)
            
            open_time = now - random.randint(86400, 30 * 86400)
            close_time = open_time + random.randint(600, 7200)
            
            trade = HistoryDeal(
                ticket=10000 + i,
                symbol=symbol,
                type=trade_type,
                volume=round(random.choice([0.01, 0.02, 0.05, 0.1]), 2),
                price_open=random.uniform(1.0, 100.0),
                price_close=random.uniform(1.0, 100.0),
                profit=profit,
                time=open_time,
                close_time=close_time,
                comment=f"Auto-Trade ({strategy})"
            )
            mt5_connector._history.append(trade)
        
        print(f"✅ Imported {len(mt5_connector._history)} test trades")
        
        return {
            "success": True,
            "message": f"Imported 50 test trades into mt5_connector._history",
            "count": len(mt5_connector._history),
            "sample": {
                "total_trades": 50,
                "win_rate": "~65%",
                "symbols": symbols,
                "strategies": strategies,
            }
        }
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"❌ Import test trades error: {error_msg}")
        print(error_trace)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": error_msg,
                "trace": error_trace[:300]
            }
        )


@app.get("/api/analytics")
async def get_analytics(days: int = 30):
    """
    Get comprehensive trading analytics for Performance Dashboard:
    - Win rate & trade statistics
    - P&L by symbol & strategy
    - Drawdown analysis
    - Return metrics
    """
    try:
        # Validate days parameter
        if days < 1 or days > 365:
            days = 30
        
        history = connector.get_history(days=days)
        print(f"📊 Analytics: Found {len(history)} trades in last {days} days")
        
        if not history:
            print("⚠️ No history data")
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "by_symbol": {},
                "by_strategy": {},
                "drawdown": 0.0,
                "daily_pnl": [],
                "trades": [],
            }

        # Calculate statistics
        wins = [t for t in history if t["profit"] > 0]
        losses = [t for t in history if t["profit"] < 0]
        total_profit = sum(t["profit"] for t in wins)
        total_loss = sum(t["profit"] for t in losses)  # negative values
        
        win_count = len(wins)
        loss_count = len(losses)
        total_count = len(history)
        win_rate = (win_count / total_count * 100) if total_count > 0 else 0.0
        
        print(f"✅ Stats: wins={win_count}, losses={loss_count}, rate={win_rate:.1f}%")

        # By symbol
        by_symbol = {}
        for trade in history:
            sym = trade["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {"trades": 0, "wins": 0, "profit": 0.0, "pnl_list": []}
            by_symbol[sym]["trades"] += 1
            by_symbol[sym]["pnl_list"].append(trade["profit"])
            if trade["profit"] > 0:
                by_symbol[sym]["wins"] += 1
            by_symbol[sym]["profit"] += trade["profit"]

        # By strategy (infer from comment or use symbol as proxy)
        by_strategy = {}
        for trade in history:
            # Extract strategy name from comment (e.g., "Auto-Trade (Strategy-A)" -> "Strategy-A")
            comment = trade.get("comment", "") or trade.get("comment", "Manual")
            if "Strategy-" in comment:
                # Extract strategy name like "Strategy-A" from comment
                import re
                match = re.search(r'Strategy-[A-Z]', comment)
                strat = match.group(0) if match else "Manual"
            else:
                strat = "Manual"
            
            if strat not in by_strategy:
                by_strategy[strat] = {"trades": 0, "wins": 0, "profit": 0.0}
            by_strategy[strat]["trades"] += 1
            if trade["profit"] > 0:
                by_strategy[strat]["wins"] += 1
            by_strategy[strat]["profit"] += trade["profit"]

        # Daily P&L for chart
        daily_pnl = {}
        for trade in history:
            day = datetime.fromtimestamp(trade["time"]).strftime("%Y-%m-%d")
            if day not in daily_pnl:
                daily_pnl[day] = 0.0
            daily_pnl[day] += trade["profit"]
        
        daily_pnl_list = [{"date": k, "profit": v} for k, v in sorted(daily_pnl.items())]

        # Drawdown: peak-to-trough decline
        cumulative = [0]
        for trade in sorted(history, key=lambda t: t["time"]):
            cumulative.append(cumulative[-1] + trade["profit"])
        
        peak = cumulative[0] if cumulative else 0
        max_drawdown = 0
        for val in cumulative:
            if val > peak:
                peak = val
            drawdown = peak - val
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "total_trades": total_count,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_profit": round(total_profit + total_loss, 2),
            "avg_profit": round(total_profit / win_count, 2) if win_count > 0 else 0.0,
            "avg_loss": round(total_loss / loss_count, 2) if loss_count > 0 else 0.0,
            "largest_win": round(max(wins, key=lambda x: x["profit"])["profit"], 2) if wins else 0.0,
            "largest_loss": round(min(losses, key=lambda x: x["profit"])["profit"], 2) if losses else 0.0,
            "by_symbol": {
                sym: {
                    "trades": stats["trades"],
                    "wins": stats["wins"],
                    "win_rate": round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] > 0 else 0,
                    "profit": round(stats["profit"], 2),
                    "avg_trade": round(stats["profit"] / stats["trades"], 2) if stats["trades"] > 0 else 0,
                }
                for sym, stats in by_symbol.items()
            },
            "by_strategy": {
                strat: {
                    "trades": stats["trades"],
                    "wins": stats["wins"],
                    "win_rate": round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] > 0 else 0,
                    "profit": round(stats["profit"], 2),
                }
                for strat, stats in by_strategy.items()
            },
            "drawdown": round(max_drawdown, 2),
            "daily_pnl": daily_pnl_list,
            "trades": history,  # Include individual trade records for detail view
        }
    
    except Exception as e:
        # Return error as JSON instead of exception page
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"❌ Analytics error: {error_msg}")
        print(error_trace)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to load analytics",
                "message": error_msg,
                "trace": error_trace[:500],  # Limit trace length
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "by_symbol": {},
                "by_strategy": {},
                "drawdown": 0.0,
                "daily_pnl": [],
                "trades": [],
            }
        )


@app.get("/api/analytics/history")
async def get_analytics_history(limit: int = 30):
    """
    Get historical analytics snapshots.
    Returns aggregated analytics by day for trend analysis.
    """
    history = mt5_connector.get_history(days=90)
    if not history:
        return {"snapshots": []}

    # Group by date
    by_date = {}
    for trade in history:
        day = datetime.fromtimestamp(trade["time"]).strftime("%Y-%m-%d")
        if day not in by_date:
            by_date[day] = []
        by_date[day].append(trade)

    # Calculate daily snapshots
    snapshots = []
    for day in sorted(by_date.keys())[-limit:]:
        trades = by_date[day]
        wins = len([t for t in trades if t["profit"] > 0])
        total = len(trades)
        profit = sum(t["profit"] for t in trades)

        snapshots.append({
            "date": day,
            "trades": total,
            "wins": wins,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "profit": round(profit, 2),
        })

    return {"snapshots": snapshots}


# ─── Backtesting ───────────────────────────────────────────────

@app.get("/api/backtest/run")
async def run_backtest(symbol: str = "BTCUSD", days: int = 30):
    """
    Run backtest on a single symbol
    
    Query params:
    - symbol: Trading symbol (e.g., "BTCUSD")
    - days: Number of days to backtest (1-365)
    """
    try:
        if symbol.upper() not in connector.SYMBOLS:
            return {"error": f"Unknown symbol: {symbol}"}
        
        result = backtest.run_backtest(symbol.upper(), days)
        
        # Log backtest
        log_event("BACKTEST", 
                 f"Backtest {symbol}: ROI={result.get('roi_percent', 0):.1f}%, "
                 f"WinRate={result.get('win_rate', 0):.0f}%")
        
        return result
    except Exception as e:
        print(f"❌ Backtest error: {str(e)}")
        return {"error": str(e)}


@app.get("/api/backtest/compare")
async def compare_backtests(symbols: str = "BTCUSD,EURUSD", days: int = 30):
    """
    Compare backtest performance across multiple symbols
    
    Query params:
    - symbols: Comma-separated symbols (e.g., "BTCUSD,XAUUSD,EURUSD")
    - days: Number of days to backtest
    """
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        # Filter valid symbols
        valid_symbols = [s for s in symbol_list if s in connector.SYMBOLS]
        
        if not valid_symbols:
            return {"error": "No valid symbols provided"}
        
        result = backtest.compare_symbols(valid_symbols, days)
        
        log_event("BACKTEST", f"Comparison: {len(valid_symbols)} symbols over {days} days")
        
        return result
    except Exception as e:
        print(f"❌ Comparison error: {str(e)}")
        return {"error": str(e)}


@app.get("/api/backtest/strategy")
async def backtest_strategy(symbol: str = "BTCUSD", strategy: str = "RSI", days: int = 30):
    """
    Backtest specific strategy on symbol
    
    Query params:
    - symbol: Trading symbol
    - strategy: Strategy name (RSI, MA_Cross, etc.)
    - days: Number of days to backtest
    """
    try:
        if symbol.upper() not in connector.SYMBOLS:
            return {"error": f"Unknown symbol: {symbol}"}
        
        result = backtest.backtest_strategy(symbol.upper(), strategy, days)
        
        log_event("BACKTEST", f"Strategy {strategy} on {symbol}: {result.get('recommendation', '')}")
        
        return result
    except Exception as e:
        print(f"❌ Strategy backtest error: {str(e)}")
        return {"error": str(e)}


# ─── MT5 Connection ────────────────────────────────────────────

@app.post("/api/mt5/connect")
async def mt5_connect(req: MT5ConnectRequest):
    """Connect to MT5 with credentials (or reconnect in simulation).
    Pass password='__use_saved__' to look up saved password by login+server."""
    login    = req.login
    password = req.password
    server   = req.server

    # If frontend passes sentinel, resolve from saved accounts
    if password == "__use_saved__":
        accounts = _load_accounts()
        match = next(
            (a for a in accounts if a.get("login") == login and a.get("server") == server),
            None,
        )
        if match:
            password = match.get("password", "")
        else:
            raise HTTPException(status_code=400, detail="Saved password not found — please re-enter password")

    ok = connector.connect(login=login, password=password, server=server)
    if not ok:
        log_event("MT5", f"Connection failed to {server or 'terminal'}", f"login={login}")
        raise HTTPException(status_code=400, detail="MT5 connection failed")
    mode = "Simulation" if connector.simulation_mode else "Live"
    log_event("MT5", f"Connected ({mode})", f"login={login} server={server}")
    return {
        "connected": connector.connected,
        "simulation_mode": connector.simulation_mode,
        "server": server or "Simulation",
    }


@app.post("/api/mt5/disconnect")
async def mt5_disconnect():
    """Disconnect from MT5."""
    engine.stop()
    connector.disconnect()
    log_event("MT5", "Disconnected from MT5")
    return {"connected": False}


# ─── Saved Accounts ───────────────────────────────────────────

@app.get("/api/mt5/saved-accounts")
async def get_saved_accounts():
    """List all saved MT5 accounts (passwords masked)."""
    accounts = _load_accounts()
    return [
        {
            "name": a["name"],
            "login": a.get("login", 0),
            "server": a.get("server", ""),
            "auto_connect": a.get("auto_connect", False),
            # never expose password to frontend
            "has_password": bool(a.get("password", "")),
        }
        for a in accounts
    ]

@app.post("/api/mt5/save-account")
async def save_account(req: SaveAccountRequest):
    """Save (add or update) an MT5 account."""
    accounts = _load_accounts()
    # If auto_connect, unset all others first
    if req.auto_connect:
        for a in accounts:
            a["auto_connect"] = False
    # Update existing or append
    existing = next((a for a in accounts if a["name"] == req.name), None)
    entry = {
        "name": req.name,
        "login": req.login,
        "password": req.password,
        "server": req.server,
        "auto_connect": req.auto_connect,
    }
    if existing:
        accounts[accounts.index(existing)] = entry
    else:
        accounts.append(entry)
    _save_accounts(accounts)
    return {"saved": True, "name": req.name, "auto_connect": req.auto_connect}

@app.delete("/api/mt5/saved-accounts/{name}")
async def delete_saved_account(name: str):
    """Delete a saved MT5 account by name."""
    accounts = _load_accounts()
    before = len(accounts)
    accounts = [a for a in accounts if a["name"] != name]
    if len(accounts) == before:
        raise HTTPException(status_code=404, detail=f"Account '{name}' not found")
    _save_accounts(accounts)
    return {"deleted": True, "name": name}

@app.post("/api/mt5/set-default/{name}")
async def set_default_account(name: str):
    """Mark an account as auto-connect default."""
    accounts = _load_accounts()
    found = False
    for a in accounts:
        a["auto_connect"] = (a["name"] == name)
        if a["name"] == name:
            found = True
    if not found:
        raise HTTPException(status_code=404, detail=f"Account '{name}' not found")
    _save_accounts(accounts)
    return {"default": name}


# ─── Live Symbol Prices ────────────────────────────────────────

@app.get("/api/symbols")
async def get_symbol_prices():
    """Get current bid/ask prices for all symbols."""
    result = {}
    for symbol in connector.SYMBOLS:
        price = connector.get_symbol_price(symbol)
        if price:
            result[symbol] = price
    return result


# ─── Manual Trading ────────────────────────────────────────────

@app.post("/api/trade/place")
async def place_trade(req: PlaceOrderRequest):
    """Place a manual market order."""
    result = connector.place_order(
        symbol=req.symbol.upper(),
        order_type=req.order_type.upper(),
        volume=req.volume,
        sl=req.sl,
        tp=req.tp,
        comment=req.comment or "Manual",
        timeframe="M5",
    )
    log_event("TRADE",
              f"{'✅' if result.success else '❌'} Manual {req.order_type.upper()} {req.volume} {req.symbol.upper()}",
              result.message)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"success": True, "ticket": result.ticket, "message": result.message}


@app.post("/api/trade/close/{ticket}")
async def close_trade(ticket: int):
    """Close a position by ticket."""
    result = connector.close_position(ticket)
    log_event("TRADE",
              f"{'✅' if result.success else '❌'} Close position #{ticket}",
              result.message)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"success": True, "message": result.message}


# ─── AI Settings ───────────────────────────────────────────────

@app.get("/api/ai/settings")
async def get_ai_settings():
    """Get full AI/strategy configuration for all symbols."""
    settings = []
    for symbol, cfg in engine.STRATEGIES.items():
        settings.append({
            "symbol": symbol,
            "name": cfg["name"],
            "enabled": cfg["enabled"],
            "lot_size": cfg["lot_size"],
            "sl_points": cfg["sl_points"],
            "tp_points": cfg["tp_points"],
            "cooldown": engine._trade_cooldown,
            "icon": cfg["icon"],
            "color": cfg["color"],
        })
    return settings


@app.post("/api/ai/settings")
async def update_ai_settings(req: AISettingsRequest):
    """Update AI/strategy settings for a symbol."""
    symbol = req.symbol.upper()
    result = engine.update_strategy_settings(
        symbol=symbol,
        lot_size=req.lot_size,
        sl_points=req.sl_points,
        tp_points=req.tp_points,
        cooldown=req.cooldown,
        enabled=req.enabled,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ─── AI Engine (Minimax / Gemini) ──────────────────────────────────

@app.get("/api/ai/provider")
async def get_ai_provider_settings():
    """Get AI provider config (API keys partially masked)."""
    return ai_engine.get_settings()


@app.post("/api/ai/provider")
async def update_ai_provider(req: AIProviderRequest):
    """Update AI provider settings."""
    updates = req.model_dump(exclude_none=True)
    return ai_engine.update_settings(updates)


@app.post("/api/ai/symbol")
async def update_ai_symbol(req: AISymbolSettingsRequest):
    """Update per-symbol AI auto-trade config."""
    updates = req.model_dump(exclude_none=True, exclude={"symbol"})
    return ai_engine.update_symbol_settings(req.symbol, updates)


@app.post("/api/ai/analyze/{symbol}")
async def analyze_symbol(symbol: str):
    """Trigger immediate AI analysis for one symbol."""
    sym = symbol.upper()
    p = connector.get_symbol_price(sym)
    if p:
        ai_engine.record_price(sym, p["bid"])
    return ai_engine.analyze_symbol(sym)


@app.get("/api/ai/analysis")
async def get_all_analysis():
    """Latest AI analysis for all symbols."""
    return ai_engine.get_last_analysis()


@app.get("/api/ai/log")
async def get_ai_log():
    """AI activity log."""
    return {"log": ai_engine.get_analysis_log()}


@app.get("/api/ai/thinking")
async def get_ai_thinking(limit: int = 100):
    """Get AI thinking process logs (for debugging/display)."""
    return {"thinking_log": ai_engine.get_thinking_log(limit)}


@app.post("/api/ai/thinking/clear")
async def clear_ai_thinking():
    """Clear AI thinking logs."""
    ai_engine.clear_thinking_log()
    log_event("AI", "Thinking logs cleared")
    return {"status": "cleared"}


@app.get("/api/log")
async def get_system_log():
    """Full system activity log (all categories)."""
    return {"log": list(_system_log)}


@app.get("/api/log/export")
async def export_system_log():
    """Export system log as JSON file for download."""
    import json as json_module
    from datetime import datetime
    
    log_data = {
        "exported_at": datetime.now().isoformat(),
        "total_entries": len(_system_log),
        "logs": list(_system_log),
        "ai_thinking_logs": ai_engine._thinking_log[-100:] if ai_engine else [],
    }
    
    filename = f"pytradeAI_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=log_data,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/history/export")
async def export_trade_history():
    """Export trade history as CSV file for download."""
    from datetime import datetime
    
    history = connector.get_history(days=365)  # Last 365 days
    
    if not history:
        return {"error": "No trade history available"}
    
    # Build CSV content
    csv_lines = ["Ticket,Symbol,Type,Volume,PriceOpen,PriceClose,Profit,OpenTime,CloseTime,Comment"]
    for trade in history:
        line = f"{trade.get('ticket','')},{trade.get('symbol','')},{trade.get('type','')},{trade.get('volume','')},{trade.get('price_open','')},{trade.get('price_close','')},{trade.get('profit','')},{trade.get('time','')},{trade.get('close_time','')},{trade.get('comment','')}"
        csv_lines.append(line)
    
    csv_content = "\n".join(csv_lines)
    filename = f"pytradeAI_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return {
        "filename": filename,
        "count": len(history),
        "csv": csv_content
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    print(f"🔗 WebSocket client connected ({len(ws_clients)} total)")

    try:
        while True:
            # Listen for commands from frontend
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                msg = json.loads(data)
                await handle_ws_command(ws, msg)
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            # Send real-time data
            payload = build_realtime_payload()
            await ws.send_json(payload)
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"⚠️ WebSocket error: {e}")
    finally:
        ws_clients.discard(ws)
        print(f"🔌 WebSocket client disconnected ({len(ws_clients)} remaining)")


async def handle_ws_command(ws: WebSocket, msg: dict):
    """Handle commands from WebSocket clients."""
    cmd = msg.get("command")

    if cmd == "toggle_system":
        active = engine.toggle_system()
        log_event("SYSTEM", f"System {'activated' if active else 'paused'}", "via WebSocket")
        await ws.send_json({"type": "system_toggle", "active": active})

    elif cmd == "toggle_strategy":
        symbol = msg.get("symbol", "")
        result = engine.toggle_strategy(symbol.upper())
        log_event("STRATEGY",
                  f"Strategy {symbol.upper()} {'enabled ✅' if result.get('enabled') else 'disabled ⏸️'}",
                  "via WebSocket")
        await ws.send_json({"type": "strategy_toggle", **result})

    elif cmd == "close_position":
        ticket = msg.get("ticket", 0)
        force = msg.get("force", False)
        result = connector.close_position(ticket, force=force)
        log_event("TRADE",
                  f"{'✅' if result.success else '❌'} Close position #{ticket}" + (f" (FORCE)" if force else ""),
                  result.message)
        await ws.send_json({"type": "close_result", "success": result.success, "message": result.message})

    elif cmd == "place_order":
        symbol = msg.get("symbol", "").upper()
        order_type = msg.get("order_type", "BUY").upper()
        volume = float(msg.get("volume", 0.01))
        sl = float(msg.get("sl", 0.0))
        tp = float(msg.get("tp", 0.0))
        comment = msg.get("comment", "Manual")
        timeframe = msg.get("timeframe", "M5")
        result = connector.place_order(symbol, order_type, volume, sl, tp, comment, timeframe)
        log_event("TRADE",
                  f"{'✅' if result.success else '❌'} Manual {order_type} {volume} {symbol}",
                  result.message)
        await ws.send_json({"type": "order_result", "success": result.success,
                            "ticket": result.ticket, "message": result.message})

    elif cmd == "update_ai_settings":
        symbol = msg.get("symbol", "").upper()
        result = engine.update_strategy_settings(
            symbol=symbol,
            lot_size=msg.get("lot_size"),
            sl_points=msg.get("sl_points"),
            tp_points=msg.get("tp_points"),
            cooldown=msg.get("cooldown"),
            enabled=msg.get("enabled"),
        )
        await ws.send_json({"type": "ai_settings_updated", **result})

    elif cmd == "mt5_connect":
        login = int(msg.get("login", 0))
        password = msg.get("password", "")
        server = msg.get("server", "")
        ok = connector.connect(login=login, password=password, server=server)
        await ws.send_json({"type": "mt5_connect_result", "success": ok,
                            "simulation_mode": connector.simulation_mode,
                            "connected": connector.connected})


def build_realtime_payload() -> dict:
    """Build the real-time data payload for WebSocket clients."""
    smart.update_prices()
    account = connector.get_account_info()
    positions = connector.get_positions()
    strategies = engine.get_strategies()
    status = engine.get_system_status()
    ai = insights.get_insights()

    # Live prices for all symbols
    prices = {}
    for symbol in connector.SYMBOLS:
        p = connector.get_symbol_price(symbol)
        if p:
            prices[symbol] = p

    return {
        "type": "realtime",
        "timestamp": int(time.time()),
        "account": account,
        "positions": positions,
        "strategies": strategies,
        "status": status,
        "prices": prices,
        "insights": {
            "most_lost_symbol": ai["most_lost_symbol"],
            "weakest_action": ai["weakest_action"],
            "total_loss_impact": ai["total_loss_impact"],
            "win_rate": ai["win_rate"],
            "total_trades": ai["total_trades"],
        },
        "ai_analysis": ai_engine.get_last_analysis(),
        "ai_auto_trade": ai_engine.settings.get("auto_trade_enabled", False),
        "ai_thinking_count": len(ai_engine.get_thinking_log(1)),  # Quick indicator
    }


async def broadcast_loop():
    """Broadcast real-time data to all connected clients."""
    global ws_clients
    while True:
        await asyncio.sleep(2)
        if not ws_clients:
            continue

        payload = build_realtime_payload()
        dead = set()
        for ws in ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)

        ws_clients -= dead


# ─── Main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")
