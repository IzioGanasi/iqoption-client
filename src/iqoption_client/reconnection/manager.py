from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager
    from ..connection.clock_sync import ClockSync
    from ..accounts.manager import AccountsManager

logger = logging.getLogger(__name__)


class ReconnectionManager:
    def __init__(
        self,
        ws: WebSocketManager,
        accounts: AccountsManager,
        clock_sync: ClockSync,
        *,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> None:
        self._ws = ws
        self._accounts = accounts
        self._clock_sync = clock_sync
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._attempt = 0
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._on_disconnect_callbacks: list[Callable] = []
        self._on_reconnect_callbacks: list[Callable] = []
        self._ssid: str = ""
        self._subscriptions: list[dict] = []

    @property
    def is_reconnecting(self) -> bool:
        return self._running

    def on_disconnect(self, callback: Callable) -> None:
        self._on_disconnect_callbacks.append(callback)

    def on_reconnect(self, callback: Callable) -> None:
        self._on_reconnect_callbacks.append(callback)

    def save_ssid(self, ssid: str) -> None:
        self._ssid = ssid

    def save_subscriptions(self, subscriptions: list[dict]) -> None:
        self._subscriptions = subscriptions

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._reconnect_task = asyncio.create_task(self._monitor_loop())

    def stop_monitoring(self) -> None:
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                if not self._ws.is_connected and self._attempt < self._max_attempts:
                    await self._attempt_reconnect()
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconnection monitor error: {e}")
                await asyncio.sleep(1.0)

    async def _attempt_reconnect(self) -> None:
        self._attempt += 1
        delay = min(
            self._base_delay * (2 ** (self._attempt - 1)),
            self._max_delay,
        )
        logger.info(
            f"Reconnection attempt {self._attempt}/{self._max_attempts} "
            f"in {delay:.1f}s"
        )

        for cb in self._on_disconnect_callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Disconnect callback error: {e}")

        await asyncio.sleep(delay)

        try:
            if not self._ssid:
                raise RuntimeError("No SSID available for reconnection")

            await self._ws.connect(self._ssid)
            self._attempt = 0
            logger.info("Reconnected successfully")

            await self._restore_subscriptions()

            for cb in self._on_reconnect_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error(f"Reconnect callback error: {e}")

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            if self._attempt >= self._max_attempts:
                logger.error("Max reconnection attempts reached")

    async def _restore_subscriptions(self) -> None:
        for sub in self._subscriptions:
            try:
                await self._ws.subscribe(
                    sub.get("name", ""),
                    sub.get("version", "1.0"),
                    params=sub.get("params"),
                )
                logger.debug(f"Restored subscription: {sub.get('name')}")
            except Exception as e:
                logger.error(f"Failed to restore subscription {sub.get('name')}: {e}")

    def reset(self) -> None:
        self._attempt = 0
