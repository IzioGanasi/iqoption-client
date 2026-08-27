from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class HeartbeatManager:
    def __init__(self, interval: float = 30.0) -> None:
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._last_heartbeat: float = 0
        self._running = False

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                self._last_heartbeat = time.time()
                logger.debug(f"Heartbeat: {self._last_heartbeat}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
