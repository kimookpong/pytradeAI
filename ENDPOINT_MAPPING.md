"""
Endpoint Mapping - Correct API paths for all test scripts
==========================================================

Based on actual server.py implementation.
Use this as reference when running tests.

PRICE DATA:

- GET /api/symbols → Returns all symbol prices {symbol: {bid, ask, spread, ...}}
- NOT: /api/price/{symbol}

ACCOUNT INFO:

- GET /api/account → Returns account balance, equity, margin info
- NOT: /api/account/info

POSITIONS:

- GET /api/positions → Returns open positions

TRADE EXECUTION:

- POST /api/trade/place → Place BUY/SELL order {symbol, order_type, volume, sl, tp, comment}
- POST /api/trade/close/{ticket} → Close position by ticket number
- NOT: /api/order/manual

TRADE HISTORY:

- GET /api/history → Returns trade history, optionally filtered by days
- Returns: list of trades [{"ticket": n, "symbol": "...", "type": "BUY", ...}]
- NOT: list directly in "data" wrapper

ANALYTICS:

- GET /api/analytics → Full analytics summary {total_trades, wins, losses, by_symbol, ...}
- Data is in response root, not in "data" wrapper

STRATEGY STATUS:

- GET /api/status → Get trading system status
- POST /api/system/toggle → Toggle trading system
- POST /api/strategy/toggle/{symbol} → Toggle strategy for specific symbol
- NOT: /api/strategy/status or /api/strategy/toggle

AI ANALYSIS:

- GET /api/ai/analysis → Get recent AI analyses
- POST /api/ai/analyze/{symbol} → Run AI analysis on symbol
- GET /api/insights → Get AI insights

WEBSOCKET:

- WS /ws/prices → Real-time price updates
- WS /ws/debug → Debug output stream

EXPORT:

- GET /api/log/export → Export system + AI logs as JSON
- GET /api/history/export → Export trade history as CSV
  """

CORRECT_ENDPOINTS = { # Price data
"get_all_prices": "/symbols", # Returns all symbol: {bid, ask, ...}

    # Account
    "get_account": "/account",  # Returns account info

    # Positions
    "get_positions": "/positions",  # Returns open positions

    # Trading
    "place_order": "/trade/place",  # POST: {symbol, order_type, volume, sl, tp}
    "close_order": "/trade/close",  # POST with /ticket

    # History & Analytics
    "get_history": "/history",  # GET with optional ?days=N - returns list directly
    "get_analytics": "/analytics",  # Returns analytics summary (NOT wrapped in "data")

    # Strategy Control
    "get_status": "/status",  # Trading system status
    "toggle_system": "/system/toggle",  # POST to toggle trading
    "toggle_strategy": "/strategy/toggle/{symbol}",  # POST

    # AI
    "get_insights": "/insights",  # GET AI insights
    "analyze_symbol": "/ai/analyze/{symbol}",  # POST AI analysis

    # Export
    "export_logs": "/log/export",  # GET JSON export
    "export_history": "/history/export",  # GET CSV export

}

RESPONSE_FORMATS = {
"/symbols": {
"format": "dict of symbol: {bid, ask, spread, time, ...}",
"note": "Not wrapped in 'data' key"
},
"/account": {
"format": "{balance, equity, margin, free_margin, leverage, ...}",
"note": "Not wrapped in 'data' key"
},
"/positions": {
"format": "[{ticket, symbol, type, volume, price_open, ...}]",
"note": "Returns list directly, not wrapped in 'data'"
},
"/history": {
"format": "[{ticket, symbol, type, volume, price_open, price_close, profit, ...}]",
"note": "Returns list directly, not wrapped in 'data' - FIX: some tests expect 'data' wrapper"
},
"/analytics": {
"format": "{total_trades, trades_won, trades_lost, win_rate_pct, total_profit, by_symbol, ...}",
"note": "Returns data directly, not wrapped in 'data' wrapper"
},
"/status": {
"format": "{enabled, symbol_status, ...}",
"note": "Not wrapped in 'data'"
},
"/trade/place": {
"format": "{success: bool, ticket: int, message: str}",
"note": "POST endpoint"
},
}
