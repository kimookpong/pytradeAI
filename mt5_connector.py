"""
MT5 Connector Module
====================
Handles connection to MetaTrader 5 terminal.
Falls back to simulation mode on macOS or when MT5 is unavailable.
"""

import random
import time
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

# Try to import MetaTrader5 (Windows only)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("⚠️  MetaTrader5 not available — running in SIMULATION mode")


@dataclass
class AccountInfo:
    balance: float = 6040.95
    equity: float = 6040.95
    margin: float = 0.0
    free_margin: float = 6040.95
    profit: float = 0.0
    leverage: int = 100
    currency: str = "USD"
    server: str = "Demo-Server"
    name: str = "Demo Account"


@dataclass
class Position:
    ticket: int = 0
    symbol: str = ""
    type: int = 0  # 0=BUY, 1=SELL
    volume: float = 0.01
    price_open: float = 0.0
    price_current: float = 0.0
    profit: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    time: int = 0
    comment: str = ""


@dataclass
class TradeResult:
    success: bool = False
    ticket: int = 0
    message: str = ""


@dataclass
class HistoryDeal:
    ticket: int = 0
    symbol: str = ""
    type: int = 0
    volume: float = 0.01
    price_open: float = 0.0
    price_close: float = 0.0
    profit: float = 0.0
    time: int = 0
    comment: str = ""


class MT5Connector:
    """Manages connection and trading operations with MT5 terminal."""

    # Symbol configurations
    SYMBOLS = {
        "BTCUSD": {"digits": 2, "base_price": 67500.0, "spread": 50.0, "pip_value": 1.0},
        "XAUUSD": {"digits": 2, "base_price": 2180.0, "spread": 0.30, "pip_value": 0.01},
        "USDJPY": {"digits": 3, "base_price": 151.500, "spread": 0.015, "pip_value": 0.001},
        "ETHUSD": {"digits": 2, "base_price": 3450.0, "spread": 15.0, "pip_value": 1.0},
        "EURUSD": {"digits": 5, "base_price": 1.08500, "spread": 0.00012, "pip_value": 0.00001},
        "GBPUSD": {"digits": 5, "base_price": 1.26800, "spread": 0.00015, "pip_value": 0.00001},
    }

    def __init__(self):
        self.connected = False
        self.simulation_mode = not MT5_AVAILABLE
        self._account = AccountInfo()
        self._positions: list[Position] = []
        self._history: list[HistoryDeal] = []
        self._sim_prices: dict[str, float] = {}
        self._sim_ticket_counter = 100000
        self._sim_start_time = time.time()
        # Maps display name (EURUSD) → broker name (EURUSDm)
        self._broker_map: dict[str, str] = {s: s for s in self.SYMBOLS}

        # Initialize simulated prices
        for symbol, config in self.SYMBOLS.items():
            self._sim_prices[symbol] = config["base_price"]

        # Generate some fake trade history
        self._generate_sim_history()

    def _detect_broker_symbols(self):
        """Auto-detect broker symbol names (e.g. EURUSDm instead of EURUSD)."""
        # Common suffix/prefix variants brokers use
        variants = ["", "m", ".", "pro", "stp", "ecn", "raw"]
        all_broker = {s.name for s in (mt5.symbols_get() or [])}
        for display_name in self.SYMBOLS:
            for suffix in variants:
                candidate = display_name + suffix
                if candidate in all_broker:
                    mt5.symbol_select(candidate, True)
                    self._broker_map[display_name] = candidate
                    break
            else:
                print(f"⚠️  Symbol not found on broker: {display_name}")
        mapped = [f"{k}→{v}" for k, v in self._broker_map.items() if k != v]
        if mapped:
            print(f"🔀 Symbol aliases: {', '.join(mapped)}")

    def connect(self, login: int = 0, password: str = "", server: str = "") -> bool:
        """Connect to MT5 terminal."""
        if self.simulation_mode:
            self.connected = True
            print("✅ Connected to MT5 (Simulation Mode)")
            return True

        if not mt5.initialize():
            print(f"❌ MT5 initialize failed: {mt5.last_error()}")
            return False

        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                print(f"❌ MT5 login failed: {mt5.last_error()}")
                return False

        # Auto-detect broker-specific symbol names
        self._detect_broker_symbols()

        self.connected = True
        print("✅ Connected to MT5 (Live)")
        return True

    def disconnect(self):
        """Disconnect from MT5."""
        if not self.simulation_mode and MT5_AVAILABLE:
            mt5.shutdown()
        self.connected = False
        print("🔌 Disconnected from MT5")

    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        return self.connected

    def get_account_info(self) -> dict:
        """Get account information."""
        if self.simulation_mode:
            # Update equity based on open positions
            total_profit = sum(p.profit for p in self._positions)
            self._account.equity = self._account.balance + total_profit
            self._account.profit = total_profit
            return {
                "balance": round(self._account.balance, 2),
                "equity": round(self._account.equity, 2),
                "margin": round(self._account.margin, 2),
                "free_margin": round(self._account.free_margin, 2),
                "profit": round(self._account.profit, 2),
                "leverage": self._account.leverage,
                "currency": self._account.currency,
                "server": self._account.server,
                "name": self._account.name,
            }

        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "leverage": info.leverage,
            "currency": info.currency,
            "server": info.server,
            "name": info.name,
        }

    def get_positions(self) -> list[dict]:
        """Get all open positions."""
        if self.simulation_mode:
            self._update_sim_prices()
            self._update_sim_positions()
            return [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == 0 else "SELL",
                    "volume": p.volume,
                    "price_open": round(p.price_open, self.SYMBOLS.get(p.symbol, {}).get("digits", 2)),
                    "price_current": round(p.price_current, self.SYMBOLS.get(p.symbol, {}).get("digits", 2)),
                    "profit": round(p.profit, 2),
                    "sl": round(p.sl, self.SYMBOLS.get(p.symbol, {}).get("digits", 2)),
                    "tp": round(p.tp, self.SYMBOLS.get(p.symbol, {}).get("digits", 2)),
                    "time": p.time,
                    "comment": p.comment,
                }
                for p in self._positions
            ]

        # Build reverse map: broker name → display name
        rev_map = {v: k for k, v in self._broker_map.items()}
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": rev_map.get(p.symbol, p.symbol),
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "profit": p.profit,
                "sl": p.sl,
                "tp": p.tp,
                "time": p.time,
                "comment": p.comment if hasattr(p, 'comment') else "",
            }
            for p in positions
        ]

    def get_symbol_price(self, symbol: str) -> dict:
        """Get current bid/ask price for a symbol."""
        if self.simulation_mode:
            self._update_sim_prices()
            price = self._sim_prices.get(symbol, 0)
            spread = self.SYMBOLS.get(symbol, {}).get("spread", 0)
            digits = self.SYMBOLS.get(symbol, {}).get("digits", 2)
            return {
                "symbol": symbol,
                "bid": round(price, digits),
                "ask": round(price + spread, digits),
                "spread": round(spread, digits),
                "time": int(time.time()),
            }

        broker_sym = self._broker_map.get(symbol, symbol)
        tick = mt5.symbol_info_tick(broker_sym)
        if tick is None:
            return {}
        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 5),
            "time": tick.time,
        }

    def place_order(self, symbol: str, order_type: str, volume: float,
                    sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeResult:
        """Place a market order."""
        if self.simulation_mode:
            self._update_sim_prices()
            price = self._sim_prices.get(symbol, 0)
            spread = self.SYMBOLS.get(symbol, {}).get("spread", 0)

            if order_type.upper() == "BUY":
                entry_price = price + spread  # buy at ask
                trade_type = 0
            else:
                entry_price = price  # sell at bid
                trade_type = 1

            self._sim_ticket_counter += 1
            pos = Position(
                ticket=self._sim_ticket_counter,
                symbol=symbol,
                type=trade_type,
                volume=volume,
                price_open=entry_price,
                price_current=entry_price,
                profit=0.0,
                sl=sl,
                tp=tp,
                time=int(time.time()),
                comment=comment or "Auto-Trade",
            )
            self._positions.append(pos)
            return TradeResult(success=True, ticket=pos.ticket, message=f"Order placed: {order_type} {volume} {symbol}")

        # Real MT5 order
        broker_sym = self._broker_map.get(symbol, symbol)
        price_info = mt5.symbol_info_tick(broker_sym)
        if price_info is None:
            return TradeResult(success=False, message=f"Failed to get price for {symbol} ({broker_sym})")

        filling_type = mt5.ORDER_FILLING_IOC
        if order_type.upper() == "BUY":
            action_type = mt5.ORDER_TYPE_BUY
            price = price_info.ask
        else:
            action_type = mt5.ORDER_TYPE_SELL
            price = price_info.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": broker_sym,
            "volume": volume,
            "type": action_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": comment or "Auto-Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }
        if sl > 0:
            request["sl"] = sl
        if tp > 0:
            request["tp"] = tp

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = result.comment if result else "Unknown error"
            return TradeResult(success=False, message=f"Order failed: {msg}")

        return TradeResult(success=True, ticket=result.order, message=f"Order executed: {order_type} {volume} {symbol}")

    def close_position(self, ticket: int) -> TradeResult:
        """Close an open position by ticket."""
        if self.simulation_mode:
            for i, p in enumerate(self._positions):
                if p.ticket == ticket:
                    # Record in history
                    deal = HistoryDeal(
                        ticket=p.ticket,
                        symbol=p.symbol,
                        type=p.type,
                        volume=p.volume,
                        price_open=p.price_open,
                        price_close=p.price_current,
                        profit=p.profit,
                        time=int(time.time()),
                        comment="Closed",
                    )
                    self._history.append(deal)
                    self._account.balance += p.profit
                    self._positions.pop(i)
                    return TradeResult(success=True, ticket=ticket, message=f"Position {ticket} closed, P&L: {p.profit:.2f}")
            return TradeResult(success=False, message=f"Position {ticket} not found")

        # Real MT5 close
        position = None
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            position = positions[0]
        if position is None:
            return TradeResult(success=False, message=f"Position {ticket} not found")

        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        price_info = mt5.symbol_info_tick(position.symbol)
        price = price_info.bid if position.type == 0 else price_info.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = result.comment if result else "Unknown error"
            return TradeResult(success=False, message=f"Close failed: {msg}")

        return TradeResult(success=True, ticket=ticket, message="Position closed")

    def get_history(self, days: int = 30) -> list[dict]:
        """Get trade history for the last N days."""
        if self.simulation_mode:
            return [
                {
                    "ticket":      d.ticket,
                    "symbol":      d.symbol,
                    "type":        "BUY" if d.type == 0 else "SELL",
                    "volume":      d.volume,
                    "price_open":  round(d.price_open,  5),
                    "price_close": round(d.price_close, 5),
                    "profit":      round(d.profit, 2),
                    "time":        d.time,
                    "comment":     d.comment,
                }
                for d in self._history
            ]

        # Real MT5: group IN/OUT deals by position_id to build round-trips
        from_date = datetime.now() - timedelta(days=days)
        deals = mt5.history_deals_get(from_date, datetime.now())
        if deals is None:
            return []
        rev_map = {v: k for k, v in self._broker_map.items()}

        # entry: 0=DEAL_ENTRY_IN, 1=DEAL_ENTRY_OUT
        by_pos: dict = {}
        for d in deals:
            if not d.symbol:
                continue
            pid = d.position_id
            if pid not in by_pos:
                by_pos[pid] = {"in": None, "out": None}
            entry = getattr(d, "entry", -1)
            if entry == 0:
                by_pos[pid]["in"] = d
            elif entry == 1:
                by_pos[pid]["out"] = d

        result = []
        for pid, pair in by_pos.items():
            out = pair["out"]
            inn = pair["in"]
            if out is None:
                continue  # position still open
            sym = rev_map.get(out.symbol, out.symbol)
            result.append({
                "ticket":      out.ticket,
                "symbol":      sym,
                "type":        "BUY" if getattr(inn, "type", 0) == 0 else "SELL",
                "volume":      out.volume,
                "price_open":  round(inn.price, 5) if inn else 0.0,
                "price_close": round(out.price, 5),
                "profit":      round(out.profit, 2),
                "time":        out.time,
                "comment":     out.comment if hasattr(out, "comment") else "",
            })
        return result

    # ─── Simulation Helpers ─────────────────────────────────────────

    def _update_sim_prices(self):
        """Update simulated prices with realistic random walk."""
        for symbol, config in self.SYMBOLS.items():
            base = config["base_price"]
            volatility = base * 0.0003  # 0.03% per tick
            change = random.gauss(0, volatility)
            # Add sinusoidal wave for trend patterns
            t = time.time() - self._sim_start_time
            wave = math.sin(t / 120) * volatility * 2
            self._sim_prices[symbol] = max(base * 0.95, min(base * 1.05, self._sim_prices[symbol] + change + wave * 0.1))

    def _update_sim_positions(self):
        """Update P&L for simulated positions."""
        for p in self._positions:
            if p.symbol in self._sim_prices:
                current = self._sim_prices[p.symbol]
                spread = self.SYMBOLS[p.symbol]["spread"]
                if p.type == 0:  # BUY
                    p.price_current = current
                    p.profit = round((current - p.price_open) * p.volume * self._get_point_value(p.symbol), 2)
                else:  # SELL
                    p.price_current = current + spread
                    p.profit = round((p.price_open - current - spread) * p.volume * self._get_point_value(p.symbol), 2)

    def _get_point_value(self, symbol: str) -> float:
        """Get point value multiplier for P&L calculation."""
        multipliers = {
            "BTCUSD": 1.0,
            "XAUUSD": 100.0,
            "USDJPY": 100.0 / 151.5,
            "ETHUSD": 1.0,
            "EURUSD": 100000.0,
            "GBPUSD": 100000.0,
        }
        return multipliers.get(symbol, 1.0)

    def _generate_sim_history(self):
        """Generate realistic trade history for simulation."""
        symbols = ["BTCUSD", "XAUUSD", "USDJPY", "ETHUSD", "EURUSD"]
        now = int(time.time())

        for i in range(56):
            symbol = random.choice(symbols)
            trade_type = random.randint(0, 1)
            base_price = self.SYMBOLS[symbol]["base_price"]
            price = base_price * random.uniform(0.98, 1.02)
            # Win rate ~67.9%
            if random.random() < 0.679:
                profit = round(random.uniform(5, 80), 2)
            else:
                profit = round(random.uniform(-80, -5), 2)

            # Simulate close price from open price ± profit direction
            price_close = round(price + (abs(profit) / 100.0) * (1 if profit > 0 else -1), self.SYMBOLS[symbol]["digits"])
            self._history.append(HistoryDeal(
                ticket=90000 + i,
                symbol=symbol,
                type=trade_type,
                volume=round(random.choice([0.01, 0.02, 0.05, 0.1]), 2),
                price_open=round(price, self.SYMBOLS[symbol]["digits"]),
                price_close=price_close,
                profit=profit,
                time=now - random.randint(3600, 30 * 86400),
                comment="Auto-Trade",
            ))

        # Sort by time
        self._history.sort(key=lambda d: d.time)
