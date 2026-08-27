from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class EventsManager:
    def __init__(self, ws: WebSocketManager) -> None:
        self._ws = ws
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event_name: str, callback: Callable) -> None:
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(callback)
        self._ws.on(event_name, callback)

    def off(self, event_name: str, callback: Callable) -> None:
        if event_name in self._handlers:
            self._handlers[event_name] = [
                cb for cb in self._handlers[event_name] if cb != callback
            ]
        self._ws.off(event_name, callback)
