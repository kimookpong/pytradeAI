"""
pytradeAI — FastAPI Server
===========================
Main server with REST API + WebSocket for real-time browser dashboard.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from mt5_connector import MT5Connector
from trading_engine import TradingEngine
from smart_logic import SmartLogic
from ai_insights import AIInsights


# ─── Global Instances ───────────────────────────────────────────

connector = MT5Connector()
engine = TradingEngine(connector)
smart = SmartLogic(connector)
insights = AIInsights(connector)

# Connected WebSocket clients
ws_clients: set[WebSocket] = set()


# ─── Lifespan ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    connector.connect()
    asyncio.create_task(engine.run_loop())
    asyncio.create_task(broadcast_loop())
    print("=" * 50)
    print("🤖 pytradeAI started")
    print(f"📡 Mode: {'SIMULATION' if connector.simulation_mode else 'LIVE'}")
    print("🌐 Dashboard: http://localhost:8888")
    print("=" * 50)
    yield
    # Shutdown
    engine.stop()
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
    return {"system_active": active}


@app.post("/api/strategy/toggle/{symbol}")
async def toggle_strategy(symbol: str):
    result = engine.toggle_strategy(symbol.upper())
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


# ─── WebSocket ──────────────────────────────────────────────────

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
        await ws.send_json({"type": "system_toggle", "active": active})

    elif cmd == "toggle_strategy":
        symbol = msg.get("symbol", "")
        result = engine.toggle_strategy(symbol.upper())
        await ws.send_json({"type": "strategy_toggle", **result})

    elif cmd == "close_position":
        ticket = msg.get("ticket", 0)
        result = connector.close_position(ticket)
        await ws.send_json({"type": "close_result", "success": result.success, "message": result.message})


def build_realtime_payload() -> dict:
    """Build the real-time data payload for WebSocket clients."""
    smart.update_prices()
    account = connector.get_account_info()
    positions = connector.get_positions()
    strategies = engine.get_strategies()
    status = engine.get_system_status()
    ai = insights.get_insights()

    return {
        "type": "realtime",
        "timestamp": int(time.time()),
        "account": account,
        "positions": positions,
        "strategies": strategies,
        "status": status,
        "insights": {
            "most_lost_symbol": ai["most_lost_symbol"],
            "weakest_action": ai["weakest_action"],
            "total_loss_impact": ai["total_loss_impact"],
            "win_rate": ai["win_rate"],
            "total_trades": ai["total_trades"],
        },
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
