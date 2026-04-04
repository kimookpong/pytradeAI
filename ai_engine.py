"""
AI Engine — Minimax / Gemini Integration
=========================================
Calls external AI APIs to analyze market conditions and generate
BUY / SELL / HOLD signals. When auto-trade is enabled for a symbol,
the engine will automatically execute the order via MT5Connector.
"""

import json
import time
import math
import asyncio
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


# ─── Settings persistence ───────────────────────────────────────

SETTINGS_FILE = Path(__file__).parent / "ai_settings.json"

DEFAULT_SETTINGS = {
    "provider": "minimax",          # "minimax" | "gemini"
    "minimax_api_key": "",
    "minimax_model": "MiniMax-Text-01",
    "gemini_api_key": "",
    "gemini_model": "gemini-1.5-flash",
    "auto_trade_enabled": False,    # master switch
    "analysis_interval": 60,       # seconds between analyses
    "symbols": {
        "EURUSD": {"auto_trade": False, "lot_size": 0.1, "sl_points": 20, "tp_points": 35, "max_trades": 1},
        "GBPUSD": {"auto_trade": False, "lot_size": 0.1, "sl_points": 25, "tp_points": 40, "max_trades": 1},
        "USDJPY": {"auto_trade": False, "lot_size": 0.1, "sl_points": 30, "tp_points": 50, "max_trades": 1},
        "XAUUSD": {"auto_trade": False, "lot_size": 0.05, "sl_points": 100, "tp_points": 150, "max_trades": 1},
        "BTCUSD": {"auto_trade": False, "lot_size": 0.01, "sl_points": 500, "tp_points": 800, "max_trades": 1},
        "ETHUSD": {"auto_trade": False, "lot_size": 0.01, "sl_points": 300, "tp_points": 500, "max_trades": 1},
    },
}


def load_ai_settings() -> dict:
    """Load AI settings from defaults (file-based persistence disabled - use localStorage)."""
    # Always return defaults - frontend manages persistence via localStorage
    return {k: v for k, v in DEFAULT_SETTINGS.items()}


def save_ai_settings(settings: dict):
    """Save AI settings (currently no-op - frontend manages persistence via localStorage)."""
    # Skip file writing - all persistence handled by frontend localStorage
    pass


# ─── AI Engine ──────────────────────────────────────────────────

class AIEngine:
    """Manages AI-driven market analysis and auto-trading."""

    def __init__(self, connector, log_callback=None):
        self.connector = connector
        self.settings = load_ai_settings()
        self._price_history: dict[str, list[float]] = {}
        self._last_analysis: dict[str, dict] = {}
        self._last_trade_time: dict[str, float] = {}
        self._analysis_log: list[dict] = []
        self._thinking_log: list[dict] = []  # Detailed AI reasoning log
        self._running = False
        self._cooldown = 120
        self._log = log_callback or (lambda *a, **kw: None)
        # Performance context cache: symbol -> (timestamp, stats_dict)
        self._perf_cache: dict[str, tuple[float, dict]] = {}
        self._on_thinking_update = None  # Callback for frontend broadcasts

    # ─── AI mode check (used by TradingEngine) ─────────────────

    def is_ai_active(self, symbol: str) -> bool:
        """Return True if AI auto-trade is currently enabled for this symbol."""
        return (
            self.settings.get("auto_trade_enabled", False) and
            self.settings["symbols"].get(symbol, {}).get("auto_trade", False)
        )

    def set_thinking_callback(self, callback):
        """Set callback for AI thinking updates (for WebSocket broadcasting)."""
        self._on_thinking_update = callback

    def _log_thinking(self, symbol: str, stage: str, data: dict):
        """Log AI thinking process for frontend display."""
        entry = {
            "timestamp": int(time.time()),
            "symbol": symbol,
            "stage": stage,
            "data": data,
        }
        self._thinking_log.append(entry)
        # Keep last 200 thinking entries
        if len(self._thinking_log) > 200:
            self._thinking_log = self._thinking_log[-200:]
        # Notify frontend via callback
        if self._on_thinking_update:
            self._on_thinking_update(entry)

    # ─── Public: settings ──────────────────────────────────────

    def get_settings(self) -> dict:
        """Return current settings (mask API keys partially)."""
        s = dict(self.settings)
        s["minimax_api_key_set"] = bool(s.get("minimax_api_key"))
        s["gemini_api_key_set"]  = bool(s.get("gemini_api_key"))
        return s

    def update_settings(self, updates: dict) -> dict:
        """Merge updates into settings and persist."""
        protected = {"symbols"}  # updated separately
        for k, v in updates.items():
            if k not in protected:
                self.settings[k] = v
        save_ai_settings(self.settings)
        return self.get_settings()

    def update_symbol_settings(self, symbol: str, updates: dict) -> dict:
        """Update per-symbol AI auto-trade config."""
        sym = symbol.upper()
        if sym not in self.settings["symbols"]:
            return {"error": f"Unknown symbol: {sym}"}
        self.settings["symbols"][sym].update(updates)
        save_ai_settings(self.settings)
        return {"symbol": sym, **self.settings["symbols"][sym]}

    def get_last_analysis(self, symbol: str = None) -> dict | list:
        if symbol:
            return self._last_analysis.get(symbol.upper(), {})
        return self._last_analysis

    def get_analysis_log(self) -> list:
        return list(reversed(self._analysis_log[-50:]))

    def get_thinking_log(self, limit: int = 100) -> list:
        """Get the AI thinking logs (for debugging/display)."""
        return list(reversed(self._thinking_log[-limit:]))

    def clear_thinking_log(self):
        """Clear thinking logs."""
        self._thinking_log.clear()

    # ─── Price data ────────────────────────────────────────────

    def record_price(self, symbol: str, bid: float):
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(bid)
        if len(self._price_history[symbol]) > 100:
            self._price_history[symbol] = self._price_history[symbol][-100:]

    # ─── Technical context ─────────────────────────────────────

    def _get_perf_context(self, symbol: str) -> dict:
        """
        Build a performance summary for the symbol from recent trade history.
        Results are cached for 2 minutes to avoid excessive MT5 calls.
        """
        now = time.time()
        cached = self._perf_cache.get(symbol)
        if cached and (now - cached[0]) < 120:
            self._log("AI", f"Performance context cache HIT for {symbol}", detail={"symbol": symbol, "cached": True, "stats": cached[1]})
            return cached[1]

        try:
            history = self.connector.get_history(14)
        except Exception as e:
            self._log("ERROR", f"Failed to query history for {symbol}: {e}", detail={"symbol": symbol, "error": str(e)})
            return {}

        sym_trades = [t for t in history if t.get("symbol") == symbol]
        if not sym_trades:
            self._log("AI", f"Performance context: No trades for {symbol} in last 14 days", detail={"symbol": symbol, "count": 0})
            self._perf_cache[symbol] = (now, {})
            return {}

        sym_trades.sort(key=lambda t: t.get("time", 0))
        wins   = [t for t in sym_trades if t.get("profit", 0) > 0]
        losses = [t for t in sym_trades if t.get("profit", 0) <= 0]
        net_pnl  = sum(t.get("profit", 0) for t in sym_trades)
        avg_win  = sum(t["profit"] for t in wins)   / len(wins)   if wins   else 0.0
        avg_loss = sum(t["profit"] for t in losses) / len(losses) if losses else 0.0
        win_rate = len(wins) / len(sym_trades) * 100 if sym_trades else 0.0

        last5 = sym_trades[-5:]
        last5_str = ", ".join(
            f"{'✓' if t.get('profit', 0) > 0 else '✗'} {t.get('type','?')} ${t.get('profit', 0):+.2f}"
            for t in last5
        )

        stats = {
            "total":    len(sym_trades),
            "wins":     len(wins),
            "losses":   len(losses),
            "win_rate": round(win_rate, 1),
            "net_pnl":  round(net_pnl, 2),
            "avg_win":  round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "last5":    last5_str,
        }
        self._log("AI", f"Performance context: {symbol} - {len(sym_trades)} trades, {len(wins)} wins ({win_rate:.0f}%), P/L ${net_pnl:+.2f}", detail={"symbol": symbol, **stats})
        self._perf_cache[symbol] = (now, stats)
        return stats

    def _build_market_context(self, symbol: str) -> dict:
        """Compute simple technical indicators from price history."""
        prices = self._price_history.get(symbol, [])
        if not prices:
            return {}

        last  = prices[-1]
        n     = len(prices)

        # SMA 5 / 20
        sma5  = sum(prices[-5:]) / min(n, 5)
        sma20 = sum(prices[-20:]) / min(n, 20)

        # RSI-14 (simplified)
        gains, losses = [], []
        for i in range(1, min(n, 15)):
            d = prices[-i] - prices[-i-1]
            (gains if d > 0 else losses).append(abs(d))
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 1e-9
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        # Volatility
        if n >= 2:
            returns = [(prices[i] / prices[i-1]) - 1 for i in range(max(1, n-20), n)]
            mean = sum(returns) / len(returns)
            vol = math.sqrt(sum((r - mean)**2 for r in returns) / len(returns)) * 100
        else:
            vol = 0.0

        # Trend
        if n >= 5:
            slope = (prices[-1] - prices[-5]) / prices[-5] * 100
        else:
            slope = 0.0

        price_data = self.connector.get_symbol_price(symbol)
        spread = price_data.get("spread", 0) if price_data else 0

        ctx = {
            "symbol": symbol,
            "last_price": round(last, 5),
            "sma5": round(sma5, 5),
            "sma20": round(sma20, 5),
            "rsi14": round(rsi, 1),
            "volatility_pct": round(vol, 4),
            "trend_5bar_pct": round(slope, 4),
            "spread": round(spread, 5),
            "bars_available": n,
        }
        self._log("AI", f"Market context for {symbol}: Price={ctx['last_price']}, RSI={ctx['rsi14']}, Vol={ctx['volatility_pct']}%, Trend={ctx['trend_5bar_pct']:+.2f}%", detail=ctx)
        return ctx

    def _build_prompt(self, symbol: str, ctx: dict) -> str:
        """Build the AI prompt for market analysis, including performance context."""
        sym_cfg = self.settings["symbols"].get(symbol, {})
        perf    = self._get_perf_context(symbol)

        if perf and perf.get("total", 0) > 0:
            perf_section = f"""
Recent trade performance ({symbol}, last 14 days):
- Trades: {perf['total']} | Wins: {perf['wins']} | Losses: {perf['losses']} | Win Rate: {perf['win_rate']}%
- Net P&L: ${perf['net_pnl']:+.2f} | Avg Win: +${perf['avg_win']:.2f} | Avg Loss: ${perf['avg_loss']:.2f}
- Last 5 results: {perf['last5']}
Use this data to adjust your signal — if win rate is low, prefer HOLD; if avg loss > avg win, tighten confidence threshold."""
        else:
            perf_section = "\nNo recent trade history available for this symbol yet."

        return f"""You are an expert forex/crypto trading analyst. Analyze the market data below and provide a trading signal that maximises profitability.

Symbol: {symbol}
Current Price: {ctx.get('last_price')}
SMA-5: {ctx.get('sma5')}  |  SMA-20: {ctx.get('sma20')}
RSI-14: {ctx.get('rsi14')}
Volatility (20-bar): {ctx.get('volatility_pct')}%
Trend (5-bar slope): {ctx.get('trend_5bar_pct')}%
Spread: {ctx.get('spread')}
Data bars available: {ctx.get('bars_available')}

Risk settings: SL={sym_cfg.get('sl_points', 0)} pts, TP={sym_cfg.get('tp_points', 0)} pts, Lot={sym_cfg.get('lot_size', 0.01)}
{perf_section}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0-100,
  "logic_name": "name of the strategy or logic used (e.g., RSI Reversal, Volatility Breakout, MA Crossover)",
  "reason": "brief explanation factoring the context",
  "key_level": <nearest significant price level as float>,
  "risk": "LOW" | "MEDIUM" | "HIGH"
}}"""

    # ─── AI API calls ──────────────────────────────────────────

    def _call_minimax(self, prompt: str) -> str:
        """Call MiniMax Text API and return the response text."""
        api_key = self.settings.get("minimax_api_key", "")
        model   = self.settings.get("minimax_model", "MiniMax-Text-01")
        if not api_key:
            raise ValueError("MiniMax API key not set")

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.2,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]

    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API and return the response text."""
        api_key = self.settings.get("gemini_api_key", "")
        model   = self.settings.get("gemini_model", "gemini-1.5-flash")
        if not api_key:
            raise ValueError("Gemini API key not set")

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
        }).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_ai_response(self, text: str) -> dict:
        """Parse JSON from AI response, tolerating markdown code fences."""
        text = text.strip()
        # Strip ```json ... ``` if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        # Find first { ... }
        start = text.find("{")
        end   = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]
        return json.loads(text)

    def analyze_symbol(self, symbol: str) -> dict:
        """
        Run AI analysis for a symbol.
        Returns analysis dict with signal, confidence, reason, risk.
        """
        # Stage 1: Market Context
        ctx = self._build_market_context(symbol)
        self._log_thinking(symbol, "market_analysis", ctx)
        
        if not ctx or ctx.get("bars_available", 0) < 5:
            result = {
                "symbol": symbol,
                "signal": "HOLD",
                "confidence": 0,
                "logic_name": "None",
                "reason": "Insufficient price data",
                "risk": "HIGH",
                "key_level": None,
                "context": ctx,
                "provider": "—",
                "timestamp": int(time.time()),
                "error": "not_enough_data",
            }
            self._log_thinking(symbol, "analysis_complete", {"error": "not_enough_data"})
            return result

        # Stage 2: Performance Context
        perf = self._get_perf_context(symbol)
        self._log_thinking(symbol, "performance_analysis", perf)

        # Stage 3: Prompt Building
        provider = self.settings.get("provider", "minimax")
        prompt   = self._build_prompt(symbol, ctx)
        self._log_thinking(symbol, "prompt_ready", {
            "provider": provider,
            "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt
        })

        # Stage 4: API Call & Response
        try:
            self._log_thinking(symbol, "calling_api", {"provider": provider})
            
            if provider == "gemini":
                raw = self._call_gemini(prompt)
            else:
                raw = self._call_minimax(prompt)

            self._log_thinking(symbol, "api_response", {"response_preview": raw[:150]})

            parsed = self._parse_ai_response(raw)
            result = {
                "symbol": symbol,
                "signal": parsed.get("signal", "HOLD").upper(),
                "confidence": int(parsed.get("confidence", 0)),
                "logic_name": parsed.get("logic_name", "Technical Analysis"),
                "reason": parsed.get("reason", ""),
                "risk": parsed.get("risk", "MEDIUM").upper(),
                "key_level": parsed.get("key_level"),
                "context": ctx,
                "provider": provider,
                "timestamp": int(time.time()),
                "error": None,
            }
            
            # Log decision
            self._log_thinking(symbol, "decision", {
                "signal": result["signal"],
                "confidence": result["confidence"],
                "risk": result["risk"],
                "logic_name": result["logic_name"],
                "reason": result["reason"],
            })
            
        except Exception as e:
            self._log_thinking(symbol, "api_error", {"error": str(e)[:100]})
            result = {
                "symbol": symbol,
                "signal": "HOLD",
                "confidence": 0,
                "logic_name": "Error Fallback",
                "reason": f"AI error: {str(e)[:80]}",
                "risk": "HIGH",
                "key_level": None,
                "context": ctx,
                "provider": provider,
                "timestamp": int(time.time()),
                "error": str(e)[:120],
            }

        self._last_analysis[symbol] = result
        self._analysis_log.append({**result, "context": None})  # no context in log
        if len(self._analysis_log) > 100:
            self._analysis_log = self._analysis_log[-100:]
        
        self._log_thinking(symbol, "analysis_complete", {"status": "success"})
        return result

    # ─── Auto-trade ────────────────────────────────────────────

    def maybe_auto_trade(self, symbol: str, analysis: dict) -> dict | None:
        """
        If auto-trade is enabled and analysis gives a strong enough signal,
        place an order automatically.
        Returns order result dict or None.
        """
        if not self.settings.get("auto_trade_enabled"):
            self._log_thinking(symbol, "auto_trade_check", {"status": "auto_trade_disabled"})
            return None

        sym_cfg = self.settings["symbols"].get(symbol, {})
        if not sym_cfg.get("auto_trade"):
            self._log_thinking(symbol, "auto_trade_check", {"status": "symbol_auto_trade_disabled"})
            return None

        signal     = analysis.get("signal", "HOLD")
        confidence = analysis.get("confidence", 0)
        risk       = analysis.get("risk", "HIGH")

        # Log trading decision process
        trade_check = {
            "signal": signal,
            "confidence": confidence,
            "risk": risk,
            "checks": {}
        }

        if signal == "HOLD":
            trade_check["checks"]["hold_signal"] = "REJECTED: signal is HOLD"
            self._log_thinking(symbol, "trade_decision", trade_check)
            return None
        
        trade_check["checks"]["hold_signal"] = "✓ BUY or SELL signal"

        if confidence < 60:
            trade_check["checks"]["confidence"] = f"REJECTED: {confidence}% < 60%"
            self._log_thinking(symbol, "trade_decision", trade_check)
            return None
        
        trade_check["checks"]["confidence"] = f"✓ {confidence}% >= 60%"

        if risk == "HIGH":
            trade_check["checks"]["risk"] = "REJECTED: risk level HIGH"
            self._log_thinking(symbol, "trade_decision", trade_check)
            return None
        
        trade_check["checks"]["risk"] = f"✓ risk level {risk}"

        # Cooldown check
        last = self._last_trade_time.get(symbol, 0)
        cooldown_remaining = self._cooldown - (time.time() - last)
        if cooldown_remaining > 0:
            trade_check["checks"]["cooldown"] = f"REJECTED: {int(cooldown_remaining)}s remaining"
            self._log_thinking(symbol, "trade_decision", trade_check)
            return None
        
        trade_check["checks"]["cooldown"] = "✓ cooldown expired"

        # Check max open trades per symbol
        positions = self.connector.get_positions() or []
        sym_positions = [p for p in positions if p.get("symbol") == symbol]
        max_trades = sym_cfg.get("max_trades", 1)
        if len(sym_positions) >= max_trades:
            trade_check["checks"]["max_trades"] = f"REJECTED: {len(sym_positions)}/{max_trades} max reached"
            self._log_thinking(symbol, "trade_decision", trade_check)
            return None
        
        trade_check["checks"]["max_trades"] = f"✓ {len(sym_positions)}/{max_trades} open"

        # Place order
        lot    = sym_cfg.get("lot_size", 0.01)
        sl_pts = sym_cfg.get("sl_points", 50)
        tp_pts = sym_cfg.get("tp_points", 80)

        trade_check["status"] = "EXECUTING"
        trade_check["order_params"] = {
            "symbol": symbol,
            "action": signal,
            "lot": lot,
            "sl_pts": sl_pts,
            "tp_pts": tp_pts
        }
        self._log_thinking(symbol, "trade_decision", trade_check)

        result = self.connector.place_order(
            symbol=symbol,
            order_type=signal,
            volume=lot,
            sl=float(sl_pts),
            tp=float(tp_pts),
            comment=f"AI:{analysis.get('provider','?')}:{confidence}%",
            timeframe="M5",
            min_profit=0.0,  # AI trades use default, no min_profit trigger
            sl_points=0.0,   # AI trades use default, no SL shifting
        )

        if result.success:
            self._last_trade_time[symbol] = time.time()
            self._log(
                "AI",
                f"✅ AI {signal} {symbol} | {analysis.get('provider','?')} {confidence}%",
                f"Ticket #{result.ticket} | Lot {lot} | Risk {analysis.get('risk','?')} | {analysis.get('reason','')[:80]}",
            )
            self._log_thinking(symbol, "trade_executed", {
                "ticket": result.ticket,
                "action": signal,
                "message": result.message
            })
            log_entry = {
                "type": "auto_trade",
                "symbol": symbol,
                "action": signal,
                "confidence": confidence,
                "ticket": result.ticket,
                "message": result.message,
                "timestamp": int(time.time()),
            }
            self._analysis_log.append(log_entry)
        else:
            self._log_thinking(symbol, "trade_failed", {
                "error": result.message
            })

        return {
            "success": result.success,
            "ticket": result.ticket,
            "message": result.message,
            "symbol": symbol,
            "action": signal,
        }

    # ─── Background loop ───────────────────────────────────────

    async def run_loop(self):
        """
        Background task: periodically analyze each symbol with auto_trade enabled
        and execute orders when signals are strong enough.
        """
        self._running = True
        while self._running:
            interval = self.settings.get("analysis_interval", 60)
            await asyncio.sleep(interval)

            if not self.settings.get("auto_trade_enabled"):
                continue

            for symbol, sym_cfg in self.settings["symbols"].items():
                if not sym_cfg.get("auto_trade"):
                    continue
                try:
                    # Record latest price
                    p = self.connector.get_symbol_price(symbol)
                    if p:
                        self.record_price(symbol, p["bid"])

                    analysis = self.analyze_symbol(symbol)
                    self.maybe_auto_trade(symbol, analysis)
                    await asyncio.sleep(1)   # small gap between symbol calls
                except Exception as e:
                    print(f"⚠️ AI loop error [{symbol}]: {e}")

    def stop(self):
        self._running = False
