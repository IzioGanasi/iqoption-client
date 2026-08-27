from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ConnectionState:
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class ConnectionManager:
    def __init__(self) -> None:
        self._state = ConnectionState.DISCONNECTED
        self._state_callbacks: list[Callable] = []
        self._connected_at: float = 0
        self._last_activity: float = 0
        self._disconnect_reason: str = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @property
    def uptime(self) -> float:
        if self._connected_at and self._state == ConnectionState.CONNECTED:
            return time.time() - self._connected_at
        return 0

    @property
    def last_activity_age(self) -> float:
        if self._last_activity:
            return time.time() - self._last_activity
        return 0

    def set_state(self, state: str, reason: str = "") -> None:
        old = self._state
        self._state = state
        if state == ConnectionState.CONNECTED:
            self._connected_at = time.time()
        if reason:
            self._disconnect_reason = reason
        logger.debug(f"Connection state: {old} → {state}" + (f" ({reason})" if reason else ""))
        for cb in self._state_callbacks:
            try:
                cb(old, state, reason)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def on_state_change(self, callback: Callable) -> None:
        self._state_callbacks.append(callback)

    def touch(self) -> None:
        self._last_activity = time.time()

    def to_dict(self) -> dict:
        return {
            "state": self._state,
            "uptime": self.uptime,
            "last_activity_age": self.last_activity_age,
            "disconnect_reason": self._disconnect_reason,
        }
