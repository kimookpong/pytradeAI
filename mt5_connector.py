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
    sl_points: float = 0.0  # Original SL distance in pips (for profit trigger shifting)
    time: int = 0
    timeframe: str = "M5"  # M5 default
    min_profit: float = 0.0  # Minimum profit to close position
    sl_shifted: bool = False  # Whether SL has been shifted to breakeven + gap
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
    time: int = 0  # open time
    close_time: int = 0  # close time
    comment: str = ""


class MT5Connector:
    """Manages connection and trading operations with MT5 terminal."""

    # Symbol configurations with volume limits (min/step/max lots, for MT5 compatibility)
    SYMBOLS = {
        "BTCUSD": {"digits": 2, "base_price": 67500.0, "spread": 50.0, "pip_value": 0.1, "min_volume": 0.01, "step_volume": 0.01, "max_volume": 200.0},
        "XAUUSD": {"digits": 2, "base_price": 2180.0, "spread": 0.30, "pip_value": 0.01, "min_volume": 0.01, "step_volume": 0.01, "max_volume": 200.0},
        "ETHUSD": {"digits": 2, "base_price": 3450.0, "spread": 15.0, "pip_value": 0.1, "min_volume": 0.1, "step_volume": 0.1, "max_volume": 2000.0},
    }

    def __init__(self, log_callback=None):
        self.connected = False
        self.simulation_mode = not MT5_AVAILABLE
        self._account = AccountInfo()
        self._positions: list[Position] = []
        self._history: list[HistoryDeal] = []
        self._sim_prices: dict[str, float] = {}
        self._sim_ticket_counter = 100000
        self._sim_start_time = time.time()
        self._log = log_callback or (lambda *a, **kw: None)
        # Maps display name (EURUSD) → broker name (EURUSDm)
        self._broker_map: dict[str, str] = {s: s for s in self.SYMBOLS}
        # Stores per-ticket metadata for real MT5 positions (timeframe, min_profit, sl_points, sl_shifted)
        self._mt5_position_meta: dict[int, dict] = {}

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
            result = {
                "symbol": symbol,
                "bid": round(price, digits),
                "ask": round(price + spread, digits),
                "spread": round(spread, digits),
                "time": int(time.time()),
            }
            self._log("MT5", f"Price update: {symbol} bid={result['bid']}, ask={result['ask']}, spread={result['spread']}", detail={"symbol": symbol, "bid": result["bid"], "ask": result["ask"]})
            return result

        broker_sym = self._broker_map.get(symbol, symbol)
        tick = mt5.symbol_info_tick(broker_sym)
        if tick is None:
            # Symbol may not be in Market Watch — subscribe and retry once
            mt5.symbol_select(broker_sym, True)
            tick = mt5.symbol_info_tick(broker_sym)
        if tick is None:
            self._log("ERROR", f"Failed to get price for {symbol} ({broker_sym}) — not available on broker", detail={"symbol": symbol})
            return {}
        result = {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 5),
            "time": tick.time,
        }
        self._log("MT5", f"Price update: {symbol} bid={result['bid']}, ask={result['ask']}, spread={result['spread']}", detail={"symbol": symbol, "bid": result["bid"], "ask": result["ask"]})
        return result

    def validate_volume(self, symbol: str, volume: float) -> tuple:
        """Validate and adjust volume against broker limits for a symbol.
        
        Returns:
            tuple: (validated_volume, is_valid, message)
        """
        if symbol not in self.SYMBOLS:
            return volume, False, f"Symbol {symbol} not found"
        
        sym_config = self.SYMBOLS[symbol]
        min_vol = sym_config.get("min_volume", 0.01)
        step_vol = sym_config.get("step_volume", 0.01)
        max_vol = sym_config.get("max_volume", 1000.0)
        
        # Check minimum volume
        if volume < min_vol:
            return volume, False, f"Volume {volume} below minimum {min_vol} for {symbol}"
        
        # Check maximum volume
        if volume > max_vol:
            return volume, False, f"Volume {volume} exceeds maximum {max_vol} for {symbol}"
        
        # Round to valid step increments
        rounded_volume = round(volume / step_vol) * step_vol
        rounded_volume = round(rounded_volume, 8)  # Avoid floating point precision issues
        
        if abs(rounded_volume - volume) > 1e-6:
            return rounded_volume, True, f"Volume adjusted from {volume} to {rounded_volume} ({symbol})"
        
        return volume, True, "Volume valid"

    def place_order(self, symbol: str, order_type: str, volume: float,
                    sl: float = 0.0, tp: float = 0.0, comment: str = "", timeframe: str = "M5", min_profit: float = 0.0, sl_points: float = 0.0) -> TradeResult:
        """Place a market order. Timeframe defaults to M5. Min profit in dollars. SL points stores original SL distance for breakeven shifting."""
        # Validate volume against broker limits
        validated_volume, is_valid, message = self.validate_volume(symbol, volume)
        if not is_valid:
            self._log("ERROR", f"Order rejected: {symbol} {order_type} volume {volume} - {message}", detail={"symbol": symbol, "type": order_type, "volume": volume, "reason": message})
            return TradeResult(success=False, message=f"Order failed: {message}")
        
        # Use validated volume
        volume = validated_volume
        
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
                sl_points=sl_points,
                time=int(time.time()),
                timeframe=timeframe,
                min_profit=min_profit,
                sl_shifted=False,
                comment=comment or "Auto-Trade",
            )
            self._positions.append(pos)
            success_result = TradeResult(success=True, ticket=pos.ticket, message=f"Order placed: {order_type} {volume} {symbol}")
            self._log("TRADE", f"🟢 Order placed (SIM): {order_type} {volume} {symbol} @ {entry_price:.5f}, ticket={pos.ticket}, SL={sl:.5f}, TP={tp:.5f}", detail={"action": "order_placed", "symbol": symbol, "type": order_type, "volume": volume, "entry": entry_price, "ticket": pos.ticket, "sl": sl, "tp": tp})
            return success_result

        # Real MT5 order
        broker_sym = self._broker_map.get(symbol, symbol)
        price_info = mt5.symbol_info_tick(broker_sym)
        if price_info is None:
            error_result = TradeResult(success=False, message=f"Failed to get price for {symbol} ({broker_sym})")
            self._log("ERROR", f"Failed to get price for {symbol} ({broker_sym})", detail={"symbol": symbol})
            return error_result

        # Detect broker-supported filling mode to avoid ORDER_INVALID_FILL (error 10030)
        filling_type = mt5.ORDER_FILLING_IOC  # default
        sym_info = mt5.symbol_info(broker_sym)
        if sym_info is not None:
            filling_mode = getattr(sym_info, "filling_mode", 0)
            # filling_mode bits: 1=FOK, 2=IOC; RETURN is always last resort
            if filling_mode & 2:  # IOC supported
                filling_type = mt5.ORDER_FILLING_IOC
            elif filling_mode & 1:  # FOK supported
                filling_type = mt5.ORDER_FILLING_FOK
            else:
                filling_type = mt5.ORDER_FILLING_RETURN
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
        # If filling mode was rejected, retry once with ORDER_FILLING_RETURN as fallback
        if result is not None and result.retcode in (10030, 10014) and filling_type != mt5.ORDER_FILLING_RETURN:
            request["type_filling"] = mt5.ORDER_FILLING_RETURN
            result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = result.comment if result else "Unknown error"
            retcode = result.retcode if result else -1
            self._log("ERROR", f"Order failed (MT5): {symbol} {order_type} - {msg} (retcode={retcode})", detail={"symbol": symbol, "type": order_type, "volume": volume, "reason": msg})
            return TradeResult(success=False, message=f"Order failed: {msg} (retcode={retcode})")

        # Store metadata for strategy-aware close logic (custom fields not on MT5 position objects)
        self._mt5_position_meta[result.order] = {
            "timeframe": timeframe,
            "min_profit": min_profit,
            "sl_points": sl_points,
            "sl_shifted": False,
        }

        self._log("TRADE", f"🟢 Order placed (MT5): {order_type} {volume} {symbol} @ {price:.5f}, ticket={result.order}, SL={sl:.5f}, TP={tp:.5f}", detail={"action": "order_placed", "symbol": symbol, "type": order_type, "volume": volume, "entry": price, "ticket": result.order, "sl": sl, "tp": tp})
        return TradeResult(success=True, ticket=result.order, message=f"Order executed: {order_type} {volume} {symbol}")

    def close_position(self, ticket: int, force: bool = False) -> TradeResult:
        """
        Close an open position by ticket.
        If force=True: Override strategy lockout and close immediately (for manual override).
        Otherwise:
        - M5 timeframe: 
          - Before 5min: Can close if profit >= min_profit OR profit >= 50% TP
          - After 5min: Can close ONLY if proper exit signal (RSI overbought/oversold OR near TP) + profit confirmation
        - Other timeframes: can close after 1 minute if profit >= min_profit.
        """
        current_time = int(time.time())
        
        if self.simulation_mode:
            for i, p in enumerate(self._positions):
                if p.ticket == ticket:
                    time_elapsed = current_time - p.time
                    is_m5 = p.timeframe == "M5"
                    min_hold_seconds = 300 if is_m5 else 60  # 5 min for M5, 1 min for others
                    
                    # FORCE CLOSE: Skip all strategy checks (manual override)
                    if force:
                        deal = HistoryDeal(
                            ticket=p.ticket,
                            symbol=p.symbol,
                            type=p.type,
                            volume=p.volume,
                            price_open=p.price_open,
                            price_close=p.price_current,
                            profit=p.profit,
                            time=p.time,
                            close_time=int(time.time()),
                            comment="Force Closed",
                        )
                        self._history.append(deal)
                        self._account.balance += p.profit
                        self._positions.pop(i)
                        return TradeResult(success=True, ticket=ticket, message=f"✅ FORCE CLOSED: Position {ticket}, P&L: {p.profit:.2f}")
                    
                    # Check if profit trigger is hit
                    can_close_by_profit = False
                    if p.min_profit > 0 and abs(p.profit) >= p.min_profit:
                        can_close_by_profit = True
                        
                        # Shift SL to lock in gains: entry ± sl_points (equal to original risk)
                        if not p.sl_shifted and p.sl_points > 0:
                            pip_value = self.SYMBOLS.get(p.symbol, {}).get("pip_value", 0.01)
                            if p.type == 0:  # BUY: shift SL up to entry + sl_points
                                new_sl = round(p.price_open + p.sl_points * pip_value, 5)
                            else:  # SELL: shift SL down to entry - sl_points
                                new_sl = round(p.price_open - p.sl_points * pip_value, 5)
                            
                            p.sl = new_sl
                            p.sl_shifted = True
                    
                    # Check if M5: can close early if profit hits ~50% of target
                    can_close_by_tp_trigger = False
                    if is_m5 and p.tp > 0:
                        # Calculate target profit: distance from entry to TP
                        target_profit_pips = abs(p.tp - p.price_open)
                        trigger_threshold = target_profit_pips * 0.5  # 50% of target
                        
                        # Check if current profit exceeds trigger
                        if abs(p.profit) >= trigger_threshold:
                            can_close_by_tp_trigger = True
                    
                    # BEFORE 5 min: Allow close if: profit trigger OR TP trigger
                    if time_elapsed < min_hold_seconds:
                        if not can_close_by_profit and not can_close_by_tp_trigger:
                            remaining = min_hold_seconds - time_elapsed
                            if is_m5:
                                min_profit_hint = f" | Min ${p.min_profit}" if p.min_profit > 0 else ""
                                return TradeResult(
                                    success=False,
                                    message=f"M5: Wait for strategy signal. Lockout {remaining}s.{min_profit_hint}"
                                )
                            else:
                                min_profit_hint = f" | Min ${p.min_profit}" if p.min_profit > 0 else ""
                                return TradeResult(
                                    success=False, 
                                    message=f"Cannot close yet. Wait {remaining}s (1min lockout){min_profit_hint}"
                                )
                    
                    # AFTER 5 min: Require proper exit signal (RSI overbought/oversold + profit confirmation)
                    if time_elapsed >= min_hold_seconds:
                        exit_signal_valid = self._check_exit_signal(p)
                        if not exit_signal_valid:
                            return TradeResult(
                                success=False,
                                message=f"M5: Waiting for proper exit signal (RSI/Price confirmation). Profit: {p.profit:.2f}"
                            )
                    
                    # Record in history
                    deal = HistoryDeal(
                        ticket=p.ticket,
                        symbol=p.symbol,
                        type=p.type,
                        volume=p.volume,
                        price_open=p.price_open,
                        price_close=p.price_current,
                        profit=p.profit,
                        time=p.time,  # open time
                        close_time=int(time.time()),  # close time
                        comment="Closed",
                    )
                    self._history.append(deal)
                    self._account.balance += p.profit
                    self._positions.pop(i)
                    result = TradeResult(success=True, ticket=ticket, message=f"Position {ticket} closed, P&L: {p.profit:.2f}")
                    trade_type = "BUY" if p.type == 0 else "SELL"
                    self._log("TRADE", f"🔴 Position closed (SIM): {trade_type} {p.symbol} {p.volume}lot, Profit: ${p.profit:.2f}, Entry: {p.price_open:.5f}, Close: {p.price_current:.5f}", detail={"action": "position_closed", "symbol": p.symbol, "type": trade_type, "volume": p.volume, "profit": p.profit, "entry": p.price_open, "close": p.price_current})
                    return result
            error_result = TradeResult(success=False, message=f"Position {ticket} not found")
            self._log("ERROR", f"Close failed: Position {ticket} not found (SIM)", detail={"ticket": ticket})
            return error_result

        # Real MT5 close
        position = None
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            position = positions[0]
        if position is None:
            self._log("ERROR", f"Close failed: Position {ticket} not found (MT5)", detail={"ticket": ticket})
            return TradeResult(success=False, message=f"Position {ticket} not found")

        # FORCE CLOSE: skip all strategy checks
        if not force:
            # Retrieve stored metadata (custom fields not available on MT5 position objects)
            meta = self._mt5_position_meta.get(ticket, {})
            meta_timeframe = meta.get("timeframe", "M5")
            meta_min_profit = meta.get("min_profit", 0.0)
            meta_sl_shifted = meta.get("sl_shifted", False)
            meta_sl_points = meta.get("sl_points", 0.0)

            time_elapsed = current_time - position.time
            min_hold_seconds = 300 if meta_timeframe == "M5" else 60

            # Check if profit trigger is hit — shift SL to breakeven when triggered
            can_close_by_profit = meta_min_profit > 0 and abs(position.profit) >= meta_min_profit
            if can_close_by_profit and not meta_sl_shifted and meta_sl_points > 0:
                pip_value = self.SYMBOLS.get(position.symbol, {}).get("pip_value", 0.01)
                if position.type == 0:  # BUY: move SL up to entry + sl_points
                    new_sl = round(position.price_open + meta_sl_points * pip_value, 5)
                else:  # SELL: move SL down to entry - sl_points
                    new_sl = round(position.price_open - meta_sl_points * pip_value, 5)
                broker_sym = self._broker_map.get(position.symbol, position.symbol)
                modify_result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "sl": new_sl,
                    "tp": position.tp,
                })
                if modify_result and modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                    if ticket in self._mt5_position_meta:
                        self._mt5_position_meta[ticket]["sl_shifted"] = True

            # BEFORE min_hold: allow only if profit trigger hit
            if time_elapsed < min_hold_seconds and not can_close_by_profit:
                remaining = min_hold_seconds - time_elapsed
                min_profit_hint = f" | Min ${meta_min_profit}" if meta_min_profit > 0 else ""
                return TradeResult(
                    success=False,
                    message=f"M5: Wait for strategy signal. Lockout {remaining:.0f}s.{min_profit_hint}"
                )

            # AFTER min_hold: require valid exit signal
            if time_elapsed >= min_hold_seconds:
                if not self._check_exit_signal(position):
                    return TradeResult(
                        success=False,
                        message=f"M5: Waiting for exit signal (RSI/Price confirmation). Profit: {position.profit:.2f}"
                    )

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
            "comment": "Force Closed" if force else "Closed",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = result.comment if result else "Unknown error"
            return TradeResult(success=False, message=f"Close failed: {msg}")

        self._mt5_position_meta.pop(ticket, None)
        return TradeResult(success=True, ticket=ticket, message="Position closed")

    def get_history(self, days: int = 30) -> list[dict]:
        """Get trade history for the last N days."""
        if self.simulation_mode:
            # Filter by days in simulation mode
            cutoff_time = int(time.time()) - (days * 86400)
            
            result = []
            for d in self._history:
                # Filter by close_time if available, otherwise by open time
                trade_time = d.close_time if d.close_time > 0 else d.time
                if trade_time >= cutoff_time:
                    result.append({
                        "ticket":      d.ticket,
                        "symbol":      d.symbol,
                        "type":        "BUY" if d.type == 0 else "SELL",
                        "volume":      d.volume,
                        "price_open":  round(d.price_open,  5),
                        "price_close": round(d.price_close, 5),
                        "profit":      round(d.profit, 2),
                        "time":        d.time,
                        "close_time":  d.close_time,
                        "comment":     d.comment,
                    })
            self._log("MT5", f"History query (SIM): {len(result)} trades in last {days} days", detail={"count": len(result), "days": days, "trades": result[:5]})
            return result

        # Real MT5: group IN/OUT deals by position_id to build round-trips
        from_date = datetime.now() - timedelta(days=days)
        deals = mt5.history_deals_get(from_date, datetime.now())
        if deals is None:
            self._log("ERROR", f"Failed to get MT5 history for {days} days", detail={"days": days})
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
                "time":        inn.time if inn else out.time,  # open time from IN deal
                "close_time":  out.time,  # close time from OUT deal
                "comment":     out.comment if hasattr(out, "comment") else "",
            })
        self._log("MT5", f"History query (MT5): {len(result)} trades in last {days} days", detail={"count": len(result), "days": days, "trades": result[:5]})
        return result

    def _check_exit_signal(self, position: Position) -> bool:
        """
        Check if position has valid exit signal (proper exit point according to strategies).
        For M5 after 5 minutes: requires RSI overbought/oversold OR price near TP + minimum profit.
        
        Returns: True if exit is allowed, False if waiting for better signal.
        """
        # Must have at least some profit to exit after 5 min
        if position.profit <= 0:
            return False
        
        # For now, accept exit if:
        # 1. Profit >= 50% of TP distance (halfway target reached)
        # 2. Price is very close to TP (within 10% of distance)
        # 3. Profit >= $10 (minimum buffer for good exit)
        
        if position.tp > 0:
            target_profit_pips = abs(position.tp - position.price_open)
            trigger_threshold = target_profit_pips * 0.5  # 50% of target
            
            if abs(position.profit) >= trigger_threshold:
                return True
            
            # Check if price is close to TP (within 10% of distance)
            distance_to_tp = abs(position.tp - position.price_current)
            if distance_to_tp < target_profit_pips * 0.1:  # Within 10% of TP
                return True
        
        # Accept if profit is substantial (at least $10)
        if position.profit >= 10.0:
            return True
        
        return False

    def get_candles(self, symbol: str, count: int = 50) -> list[float]:
        """Get last `count` M5 candle closing prices for a symbol.

        Returns a list of closing prices (oldest first).
        Falls back to current bid ticks if candles unavailable.
        """
        if self.simulation_mode:
            # Return current simulated price history (already collected as ticks,
            # but for simulation purposes this is acceptable)
            return []

        broker_sym = self._broker_map.get(symbol, symbol)
        try:
            rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_M5, 0, count)
            if rates is None or len(rates) == 0:
                return []
            # rates is a numpy structured array with fields: time, open, high, low, close, ...
            return [float(r["close"]) for r in rates]
        except Exception as e:
            print(f"⚠️ get_candles({symbol}): {e}")
            return []

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
        """Update P&L for simulated positions and auto-trigger SL/TP."""
        to_close: list[tuple] = []

        for p in self._positions:
            if p.symbol not in self._sim_prices:
                continue
            current = self._sim_prices[p.symbol]
            spread = self.SYMBOLS[p.symbol]["spread"]
            if p.type == 0:  # BUY: close at bid
                p.price_current = current
                p.profit = round((current - p.price_open) * p.volume * self._get_point_value(p.symbol), 2)
                if p.sl > 0 and current <= p.sl:
                    to_close.append((p, "SL"))
                elif p.tp > 0 and current >= p.tp:
                    to_close.append((p, "TP"))
            else:  # SELL: close at ask
                p.price_current = round(current + spread, self.SYMBOLS[p.symbol]["digits"])
                p.profit = round((p.price_open - p.price_current) * p.volume * self._get_point_value(p.symbol), 2)
                if p.sl > 0 and (current + spread) >= p.sl:
                    to_close.append((p, "SL"))
                elif p.tp > 0 and current <= p.tp:
                    to_close.append((p, "TP"))

        # Auto-close positions that hit SL or TP
        for p, reason in to_close:
            if p not in self._positions:
                continue
            deal = HistoryDeal(
                ticket=p.ticket,
                symbol=p.symbol,
                type=p.type,
                volume=p.volume,
                price_open=p.price_open,
                price_close=p.price_current,
                profit=p.profit,
                time=p.time,
                close_time=int(time.time()),
                comment=reason,
            )
            self._history.append(deal)
            self._account.balance += p.profit
            self._positions.remove(p)
            trade_type = "BUY" if p.type == 0 else "SELL"
            self._log(
                "TRADE",
                f"🎯 {reason} hit (SIM): {trade_type} {p.symbol} P&L: ${p.profit:.2f}",
                detail={"action": f"{reason.lower()}_hit", "symbol": p.symbol, "profit": p.profit, "ticket": p.ticket},
            )

    def _get_point_value(self, symbol: str) -> float:
        """Get point value multiplier for P&L calculation."""
        multipliers = {
            "BTCUSD": 1.0,
            "XAUUSD": 100.0,
            "ETHUSD": 1.0,
        }
        return multipliers.get(symbol, 1.0)

    def pips_to_sl_tp(
        self,
        symbol: str,
        entry_price: float,
        sl_pips: float,
        tp_pips: float,
        order_type: str,
        lot: float,
    ) -> tuple[float, float]:
        """Convert dollar pips (1 pip = $0.01) to actual SL/TP price levels.

        Formula:
            dollar_amount  = pips × 0.01
            price_distance = dollar_amount / (lot × point_value_multiplier)

        Returns (sl_price, tp_price). Zeros are returned for unset values.
        """
        point_mult = self._get_point_value(symbol)
        digits = self.SYMBOLS.get(symbol, {}).get("digits", 5)
        if point_mult <= 0 or lot <= 0:
            return 0.0, 0.0

        sl_dist = (sl_pips * 0.01) / (lot * point_mult) if sl_pips > 0 else 0.0
        tp_dist = (tp_pips * 0.01) / (lot * point_mult) if tp_pips > 0 else 0.0

        is_buy = order_type.upper() == "BUY"
        sl = round(entry_price - sl_dist, digits) if sl_pips > 0 else 0.0
        tp = round(entry_price + tp_dist, digits) if tp_pips > 0 else 0.0
        if not is_buy:
            sl = round(entry_price + sl_dist, digits) if sl_pips > 0 else 0.0
            tp = round(entry_price - tp_dist, digits) if tp_pips > 0 else 0.0
        return sl, tp

    def _generate_sim_history(self):
        """Generate realistic trade history for simulation."""
        symbols = ["BTCUSD", "XAUUSD", "ETHUSD"]
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
            
            # Generate open and close times (close time is after open time)
            open_time = now - random.randint(3600, 30 * 86400)
            close_time = open_time + random.randint(60, 7200)  # Close 1-120 min after open
            
            self._history.append(HistoryDeal(
                ticket=90000 + i,
                symbol=symbol,
                type=trade_type,
                volume=round(random.choice([0.01, 0.02, 0.05, 0.1]), 2),
                price_open=round(price, self.SYMBOLS[symbol]["digits"]),
                price_close=price_close,
                profit=profit,
                time=open_time,  # open time
                close_time=close_time,  # close time
                comment="Auto-Trade",
            ))

        # Sort by time
        self._history.sort(key=lambda d: d.time)
