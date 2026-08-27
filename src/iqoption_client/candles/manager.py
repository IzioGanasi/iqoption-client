from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from ..models.candle import Candle

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class CandlesManager:
    def __init__(self, ws: WebSocketManager) -> None:
        self._ws = ws
        self._callbacks: list[Callable] = []

    def on_candle(self, callback: Callable) -> None:
        self._callbacks.append(callback)
        self._ws.on("candle-generated", self._handle_candle)

    def _handle_candle(self, msg: dict) -> None:
        inner = msg.get("msg", msg)
        candle = Candle.from_dict(inner if isinstance(inner, dict) else msg)
        for cb in self._callbacks:
            try:
                cb(candle)
            except Exception as e:
                logger.error(f"Candle callback error: {e}")

    async def subscribe(self, active_id: int, period: int = 60) -> dict:
        return await self._ws.subscribe(
            "candle-generated",
            params={"routingFilters": {"active_id": active_id, "size": period}},
        )

    async def unsubscribe(self, active_id: int, period: int = 60) -> dict:
        return await self._ws.unsubscribe(
            "candle-generated",
            params={"routingFilters": {"active_id": active_id, "size": period}},
        )

    async def get_history(
        self, active_id: int, period: int = 60, count: int = 100
    ) -> list[Candle]:
        """Fetch historical candles using get-candles (v2.0).

        The server returns up to 1000 candles, ordered oldest-first.
        We fetch all available and return the last `count` ones.
        """
        result = await self._ws.send_message(
            "get-candles",
            "2.0",
            body={
                "active_id": active_id,
                "size": period,
                "from_id": 0,
                "to_id": 999999999,
                "split_normalization": True,
                "only_closed": True,
            },
        )
        msg = result.get("msg", {})
        if isinstance(msg, dict):
            candles_data = msg.get("candles", [])
        elif isinstance(msg, list):
            candles_data = msg
        else:
            candles_data = []
        if isinstance(candles_data, list):
            all_candles = [Candle.from_dict(c) for c in candles_data if isinstance(c, dict)]
            return all_candles[-count:] if len(all_candles) > count else all_candles
        return []
