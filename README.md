<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/MetaTrader5-4A90D9?style=for-the-badge&logo=metatrader5&logoColor=white" />
  <img src="https://img.shields.io/badge/WebSocket-010101?style=for-the-badge&logo=socketdotio&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<h1 align="center">🤖 pytradeAI</h1>

<p align="center">
  <strong>Automated trading system connected to MetaTrader 5 with a real-time browser dashboard.</strong><br>
  Built with Python · FastAPI · WebSocket · Vanilla JS
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#dashboard">Dashboard</a> •
  <a href="#api-reference">API</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| ⚡ **Auto-Trade** | Runs automated strategies on MT5 24/7 with RSI, Moving Averages & Bollinger Bands |
| 🧠 **Smart Logic** | Screens and ranks currency pairs & gold by volatility, trend strength, and spread cost |
| 🧬 **AI Insights** | Real-time analysis of strengths, weaknesses, most-lost symbols & weakest actions |
| 📊 **Live Dashboard** | Premium dark-themed browser UI with WebSocket updates every 2 seconds |
| 🔄 **Multi-Symbol** | Supports BTCUSD, XAUUSD (Gold), USDJPY, ETHUSD, EURUSD, GBPUSD |
| 🛡️ **Risk Management** | Configurable stop-loss, take-profit, and max position sizing per strategy |
| 🧪 **Simulation Mode** | Full demo mode for development & testing without MT5 (works on macOS/Linux) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser Dashboard                         │
│              (HTML / CSS / JavaScript)                        │
│                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│   │ Account  │  │ Win Rate │  │Strategies│  │  Positions  │ │
│   │ Balance  │  │ (30 Day) │  │  ON/OFF  │  │   Table     │ │
│   └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket + REST API
┌─────────────────────▼───────────────────────────────────────┐
│                  FastAPI Server (:8888)                       │
│                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ MT5 Connector│  │Trading Engine│  │   Smart Logic     │  │
│   │  (+ Sim Mode)│  │ (Auto-Trade) │  │ (Symbol Ranking)  │  │
│   └──────┬───────┘  └──────────────┘  └──────────────────┘  │
│          │           ┌──────────────┐                        │
│          │           │  AI Insights │                        │
│          │           │  (R&D / Perf)│                        │
│          │           └──────────────┘                        │
└──────────┼──────────────────────────────────────────────────┘
           │
┌──────────▼──────────┐
│   MetaTrader 5      │
│   Terminal (Windows) │
└─────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- MetaTrader 5 terminal *(Windows only, optional — simulation mode available)*

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/pytradeAI.git
cd pytradeAI

# Install dependencies
pip install -r requirements.txt

# Start the server
python server.py
```

### Open Dashboard

Navigate to **http://localhost:8888** in your browser.

> **Note:** On macOS/Linux, the system runs in **Simulation Mode** with realistic demo data. On Windows with MT5 installed, it connects to the live terminal automatically.

---

## Dashboard

### Overview

The dashboard provides a real-time view of your trading system:

- **Account Balance** — Live balance with P&L tracking
- **Win Rate (30 Days)** — Overall strategy performance
- **Active Strategies** — Toggle individual symbols ON/OFF
- **R&D Insights** — AI-powered weakness detection
  - Most Lost Symbol
  - Weakest Action (BUY vs SELL)
  - Total Loss Impact
- **Live Open Positions** — Real-time floating P&L with close buttons

### Controls

| Action | Method |
|--------|--------|
| Toggle System ON/OFF | Click **SYSTEM ON/OFF** button or press `Space` |
| Toggle Strategy | Click any strategy in the grid |
| Close Position | Click **Close** button on position row |
| Retrain AI | Click **Retrain AI Models** button |
| Close Modals | Press `Escape` |

---

## Project Structure

```
mt5-bot/
├── server.py              # FastAPI server (REST + WebSocket)
├── mt5_connector.py       # MT5 connection manager + simulation
├── trading_engine.py      # Auto-trading strategies (RSI/MA/BB)
├── smart_logic.py         # Symbol screening & ranking
├── ai_insights.py         # Performance analytics & suggestions
├── requirements.txt       # Python dependencies
├── README.md
└── static/
    ├── index.html         # Dashboard HTML
    ├── styles.css         # Premium dark theme
    └── app.js             # WebSocket client & UI logic
```

---

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/account` | Account balance, equity, margin |
| `GET` | `/api/positions` | Open positions list |
| `GET` | `/api/history?days=30` | Closed trade history |
| `GET` | `/api/strategies` | All strategies with status |
| `GET` | `/api/status` | System status overview |
| `POST` | `/api/system/toggle` | Toggle system ON/OFF |
| `POST` | `/api/strategy/toggle/{symbol}` | Toggle strategy for symbol |
| `GET` | `/api/insights?days=30` | AI performance insights |
| `GET` | `/api/insights/retrain` | Retrain suggestions |
| `GET` | `/api/rankings` | Symbol advantage rankings |

### WebSocket

Connect to `ws://localhost:8888/ws` for real-time data streaming.

**Incoming messages** (server → client):

```json
{
  "type": "realtime",
  "timestamp": 1711180800,
  "account": { "balance": 6040.95, "equity": 6055.20 },
  "positions": [...],
  "strategies": [...],
  "insights": { "win_rate": 67.9, "most_lost_symbol": {...} }
}
```

**Outgoing commands** (client → server):

```json
{ "command": "toggle_system" }
{ "command": "toggle_strategy", "symbol": "XAUUSD" }
{ "command": "close_position", "ticket": 100001 }
```

---

## Trading Strategies

Each symbol runs an independent strategy combining three indicators:

| Indicator | Signal | Weight |
|-----------|--------|--------|
| **RSI (14)** | RSI < 30 = BUY, RSI > 70 = SELL | 2 points |
| **MA Crossover** | Fast MA (7) > Slow MA (20) = BUY | 1 point |
| **Bollinger Bands** | Price ≤ Lower Band = BUY, ≥ Upper = SELL | 2 points |

A trade is executed when **BUY signals ≥ 3** or **SELL signals ≥ 3**, with the opposite direction scoring below 2.

---

## Deployment

### Option 1: Windows VPS (Recommended)

For 24/7 live trading, deploy on a Windows VPS with MT5 terminal:

```bash
# On Windows VPS
pip install -r requirements.txt
pip install MetaTrader5

# Edit server.py to set MT5 login credentials
python server.py
```

Access the dashboard remotely via `http://your-vps-ip:8888`.

### Option 2: Development on macOS/Linux

The system runs in simulation mode automatically — perfect for development, backtesting, and UI iteration.

```bash
python server.py
# → Simulation mode activated
# → Dashboard at http://localhost:8888
```

---

## Configuration

### MT5 Connection

To connect to a live MT5 account, modify the `connector.connect()` call in `server.py`:

```python
connector.connect(
    login=12345678,
    password="your_password",
    server="YourBroker-Server"
)
```

### Strategy Parameters

Adjust lot sizes, stop-loss, and take-profit in `trading_engine.py`:

```python
STRATEGIES = {
    "XAUUSD": {
        "lot_size": 0.05,     # Position size
        "sl_points": 100,     # Stop-loss in points
        "tp_points": 150,     # Take-profit in points
    },
    ...
}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI, Uvicorn |
| Frontend | HTML5, CSS3 (custom dark theme), Vanilla JavaScript |
| Real-time | WebSocket (native) |
| Data | Pandas, NumPy |
| Trading | MetaTrader5 Python API |
| Font | [Inter](https://fonts.google.com/specimen/Inter) (Google Fonts) |

---

## License

This project is licensed under the MIT License.

---

<p align="center">
  <sub>Built with ❤️ for algorithmic traders</sub>
</p>
