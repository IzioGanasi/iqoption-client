from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, ws: WebSocketManager) -> None:
        self._ws = ws

    async def get_history_positions(
        self, user_id: int, user_balance_id: int, limit: int = 50
    ) -> list[dict]:
        try:
            result = await self._ws.send_message(
                "portfolio.get-history-positions",
                "2.0",
                body={
                    "user_id": user_id,
                    "user_balance_id": user_balance_id,
                    "limit": limit,
                },
            )
            positions = result.get("msg", [])
            if isinstance(positions, list):
                return positions
            return []
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def get_positions(self, user_balance_id: int) -> list[dict]:
        try:
            result = await self._ws.send_message(
                "portfolio.get-positions",
                "1.0",
                body={"user_balance_id": user_balance_id},
            )
            positions = result.get("msg", [])
            if isinstance(positions, list):
                return positions
            return []
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
