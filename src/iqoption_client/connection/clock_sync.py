from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ClockSync:
    def __init__(self) -> None:
        self._server_time: int = 0
        self._local_at_sync: float = 0
        self._offset: int = 0
        self._synced = False
        self._task: asyncio.Task | None = None

    @property
    def server_time(self) -> int:
        if not self._synced:
            return int(time.time() * 1000)
        elapsed = (time.time() - self._local_at_sync) * 1000
        return int(self._server_time + elapsed)

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def is_synced(self) -> bool:
        return self._synced

    def update(self, server_timestamp: int) -> None:
        self._server_time = server_timestamp
        self._local_at_sync = time.time()
        local_ms = int(self._local_at_sync * 1000)
        self._offset = server_timestamp - local_ms
        self._synced = True
        logger.debug(f"Clock sync: server={server_timestamp}, offset={self._offset}ms")

    def server_time_to_local(self, server_ts: int) -> float:
        return (server_ts - self._offset) / 1000.0

    def local_to_server_time(self, local_ts: float) -> int:
        return int(local_ts * 1000) + self._offset
