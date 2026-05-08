"""Alert delivery — Telegram Bot API.

Usage:
    alerts = AlertSender(settings)
    await alerts.send("⚠️ HALT triggered: max daily loss exceeded")

The Telegram Bot API is a plain HTTPS POST — no heavy SDK needed.
Token and chat_id come from environment variables / Kubernetes secrets.

If TELEGRAM_ENABLED=false (default in paper mode), all methods are no-ops
so alerts never fire in development unless explicitly enabled.
"""

from __future__ import annotations

import httpx

from risk_monitor.config import Settings
from risk_monitor.logging_setup import get_logger

log = get_logger(__name__)

_TELEGRAM_BASE = "https://api.telegram.org"


class AlertSender:
    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.telegram_enabled
        self._token = settings.telegram_token
        self._chat_id = settings.telegram_chat_id
        self._mode = settings.ibkr_mode

    async def send(self, text: str) -> None:
        """Send a plain-text Telegram message. Silently swallows errors."""
        if not self._enabled:
            log.info("alert.suppressed_telegram_disabled", message=text)
            return
        if not self._token or not self._chat_id:
            log.warning("alert.no_telegram_credentials")
            return

        url = f"{_TELEGRAM_BASE}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            log.info("alert.telegram_sent")
        except Exception as exc:
            # Never let an alert failure crash the monitor
            log.error("alert.telegram_failed", error=str(exc))

    async def halt(self, reason: str) -> None:
        mode_tag = f"[{self._mode.upper()}]"
        await self.send(
            f"🛑 <b>TRADING HALT {mode_tag}</b>\n\n"
            f"<b>Reason:</b> {reason}\n\n"
            f"All strategy pods have been scaled to 0.\n"
            f"Manual intervention required to resume."
        )

    async def adapter_disconnected(self, reason: str) -> None:
        mode_tag = f"[{self._mode.upper()}]"
        await self.send(
            f"⚠️ <b>IBKR CONNECTION LOST {mode_tag}</b>\n\n"
            f"<b>Details:</b> {reason}\n\n"
            f"The adapter lost contact with IB Gateway.\n"
            f"Strategies are paused until reconnected."
        )

    async def adapter_reconnected(self) -> None:
        mode_tag = f"[{self._mode.upper()}]"
        await self.send(
            f"✅ <b>IBKR RECONNECTED {mode_tag}</b>\n\n"
            f"Connection to IB Gateway restored."
        )

    async def heartbeat_timeout(self, seconds_since: float) -> None:
        mode_tag = f"[{self._mode.upper()}]"
        await self.send(
            f"⚠️ <b>ADAPTER HEARTBEAT TIMEOUT {mode_tag}</b>\n\n"
            f"No heartbeat received for <b>{seconds_since:.0f}s</b>.\n"
            f"The adapter pod may be down."
        )
