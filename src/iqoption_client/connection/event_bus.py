from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future] = {}
        self._listeners: dict[str, list[Callable]] = {}
        self._wildcard_listeners: list[Callable] = []

    def set_pending(self, request_id: str, future: asyncio.Future) -> None:
        self._pending[request_id] = future

    def remove_pending(self, request_id: str) -> None:
        self._pending.pop(request_id, None)

    def on(self, event_name: str, callback: Callable) -> None:
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def on_all(self, callback: Callable) -> None:
        self._wildcard_listeners.append(callback)

    def off(self, event_name: str, callback: Callable) -> None:
        if event_name in self._listeners:
            self._listeners[event_name] = [
                cb for cb in self._listeners[event_name] if cb != callback
            ]

    async def dispatch(self, message: dict) -> None:
        name = message.get("name", "")
        request_id = message.get("request_id")

        # Skip "result" ack messages
        if name == "result":
            logger.debug(f"ACK received for request_id={request_id}")
            return

        # Skip echo messages (name=sendMessage is the server echoing back our request)
        if name == "sendMessage":
            return

        # Handle actual data responses for pending futures
        if request_id and request_id in self._pending:
            future = self._pending.get(request_id)
            if future and not future.done():
                future.set_result({
                    "success": True,
                    "name": name,
                    "msg": message.get("msg"),
                    "status": message.get("status"),
                })
            return

        # Dispatch to named event listeners
        callbacks = self._listeners.get(name, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(message))
                else:
                    cb(message)
            except Exception as e:
                logger.error(f"Error in listener for {name}: {e}")

        for cb in self._wildcard_listeners:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(message))
                else:
                    cb(message)
            except Exception as e:
                logger.error(f"Error in wildcard listener: {e}")
