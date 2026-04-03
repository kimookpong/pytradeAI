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
from ai_engine import AIEngine, load_ai_settings, save_ai_settings


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

ACCOUNTS_FILE = Path(__file__).parent / "mt5_accounts.json"

def _load_accounts() -> list[dict]:
    if ACCOUNTS_FILE.exists():
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_accounts(accounts: list[dict]):
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2, ensure_ascii=False), encoding="utf-8")


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


# ─── Global Instances ───────────────────────────────────────────

connector = MT5Connector()
engine = TradingEngine(connector, log_callback=log_event)
smart = SmartLogic(connector)
insights = AIInsights(connector)
ai_engine = AIEngine(connector, log_callback=log_event)

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


@app.get("/api/log")
async def get_system_log():
    """Full system activity log (all categories)."""
    return {"log": list(_system_log)}


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
        result = connector.close_position(ticket)
        log_event("TRADE",
                  f"{'✅' if result.success else '❌'} Close position #{ticket}",
                  result.message)
        await ws.send_json({"type": "close_result", "success": result.success, "message": result.message})

    elif cmd == "place_order":
        symbol = msg.get("symbol", "").upper()
        order_type = msg.get("order_type", "BUY").upper()
        volume = float(msg.get("volume", 0.01))
        sl = float(msg.get("sl", 0.0))
        tp = float(msg.get("tp", 0.0))
        comment = msg.get("comment", "Manual")
        result = connector.place_order(symbol, order_type, volume, sl, tp, comment)
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
