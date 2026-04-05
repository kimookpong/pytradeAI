"""
Telegram Notifier
=================
Sends real-time trade and strategy notifications to a Telegram chat.
Uses only the standard library (urllib) — no extra dependencies required.
"""

import json
import asyncio
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime


CONFIG_FILE = Path(__file__).parent / "telegram_config.json"

_DEFAULT_CONFIG = {
    "enabled": False,
    "bot_token": "",
    "chat_id": "",
    "notify_open": True,
    "notify_close": True,
    "notify_strategy": True,
    "notify_risk": True,
}


class TelegramNotifier:
    """Send Telegram messages via the Bot API."""

    def __init__(self):
        self._config: dict = dict(_DEFAULT_CONFIG)
        self._load()

    # ─── Config ────────────────────────────────────────────────

    def _load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self._config = {**_DEFAULT_CONFIG, **saved}
        except FileNotFoundError:
            self._config = dict(_DEFAULT_CONFIG)
        except Exception as e:
            print(f"[Telegram] Warning: could not load config: {e}")
            self._config = dict(_DEFAULT_CONFIG)

    def _save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"[Telegram] Warning: could not save config: {e}")

    def get_settings(self) -> dict:
        """Return config with token masked for frontend display."""
        token = self._config.get("bot_token", "")
        return {
            **self._config,
            "bot_token": f"{token[:8]}...{token[-4:]}" if len(token) > 12 else ("(set)" if token else ""),
            "has_token": bool(token),
        }

    def update_settings(self, data: dict) -> dict:
        """Update and persist config. Only overwrites keys that are present."""
        allowed = set(_DEFAULT_CONFIG.keys())
        for k, v in data.items():
            if k in allowed:
                self._config[k] = v
        self._save()
        return self.get_settings()

    # ─── Core sender ───────────────────────────────────────────

    async def _send(self, text: str) -> tuple[bool, str]:
        """Send a message. Returns (success, message)."""
        token = self._config.get("bot_token", "").strip()
        chat_id = self._config.get("chat_id", "").strip()

        if not token or not chat_id:
            return False, "Bot token or Chat ID not configured"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }).encode("utf-8")

        def _do_request():
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    if body.get("ok"):
                        return True, "OK"
                    return False, body.get("description", "Unknown error")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                try:
                    detail = json.loads(body).get("description", body)
                except Exception:
                    detail = body[:200]
                return False, f"HTTP {e.code}: {detail}"
            except Exception as ex:
                return False, str(ex)

        # Run blocking I/O in thread pool so we don't block the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_request)

    async def send_raw(self, text: str) -> tuple[bool, str]:
        """Send arbitrary text (for test messages)."""
        return await self._send(text)

    # ─── Notification helpers ───────────────────────────────────

    async def notify_order_open(self, symbol: str, order_type: str,
                                 volume: float, entry: float,
                                 sl: float, tp: float, ticket: int,
                                 comment: str = ""):
        if not self._config.get("enabled") or not self._config.get("notify_open"):
            return
        emoji = "🟢" if order_type.upper() == "BUY" else "🔴"
        sl_str = f"{sl:.5f}" if sl else "—"
        tp_str = f"{tp:.5f}" if tp else "—"
        text = (
            f"{emoji} <b>Order Opened</b>\n"
            f"📌 {symbol}  |  {order_type.upper()}  |  {volume} lot\n"
            f"💰 Entry: <code>{entry:.5f}</code>\n"
            f"🛡 SL: <code>{sl_str}</code>  |  🎯 TP: <code>{tp_str}</code>\n"
            f"🎫 Ticket: #{ticket}"
            + (f"\n💬 {comment}" if comment else "")
            + f"\n🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        ok, msg = await self._send(text)
        if not ok:
            print(f"[Telegram] notify_order_open failed: {msg}")

    async def notify_order_close(self, symbol: str, order_type: str,
                                  volume: float, entry: float,
                                  close_price: float, profit: float,
                                  ticket: int, comment: str = ""):
        if not self._config.get("enabled") or not self._config.get("notify_close"):
            return
        emoji = "✅" if profit >= 0 else "❌"
        pnl_sign = "+" if profit >= 0 else ""
        text = (
            f"{emoji} <b>Order Closed</b>\n"
            f"📌 {symbol}  |  {order_type.upper()}  |  {volume} lot\n"
            f"📈 Entry: <code>{entry:.5f}</code>  →  Close: <code>{close_price:.5f}</code>\n"
            f"💵 P&amp;L: <b>{pnl_sign}{profit:.2f} USD</b>\n"
            f"🎫 Ticket: #{ticket}"
            + (f"\n💬 {comment}" if comment else "")
            + f"\n🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        ok, msg = await self._send(text)
        if not ok:
            print(f"[Telegram] notify_order_close failed: {msg}")

    async def notify_strategy_change(self, action: str, detail: str = ""):
        if not self._config.get("enabled") or not self._config.get("notify_strategy"):
            return
        text = (
            f"⚙️ <b>Strategy Changed</b>\n"
            f"🔧 {action}"
            + (f"\n📝 {detail}" if detail else "")
            + f"\n🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        ok, msg = await self._send(text)
        if not ok:
            print(f"[Telegram] notify_strategy_change failed: {msg}")

    async def notify_risk_alert(self, message: str):
        if not self._config.get("enabled") or not self._config.get("notify_risk"):
            return
        text = (
            f"⚠️ <b>Risk Alert</b>\n"
            f"{message}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        ok, msg = await self._send(text)
        if not ok:
            print(f"[Telegram] notify_risk_alert failed: {msg}")
