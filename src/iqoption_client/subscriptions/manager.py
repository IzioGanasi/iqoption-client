from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.enums import InstrumentType

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class SubscriptionsManager:
    def __init__(self, ws: WebSocketManager) -> None:
        self._ws = ws
        self._active_subscriptions: set[str] = set()

    async def subscribe_portfolio(
        self,
        user_id: int,
        user_balance_id: int,
        instrument_type: InstrumentType,
    ) -> dict:
        sub_key = f"position-changed:{instrument_type.value}"
        if sub_key in self._active_subscriptions:
            return {"success": True}

        result = await self._ws.subscribe(
            "portfolio.position-changed",
            "3.0",
            params={
                "routingFilters": {
                    "user_id": user_id,
                    "user_balance_id": user_balance_id,
                    "instrument_type": instrument_type.value,
                }
            },
        )
        self._active_subscriptions.add(sub_key)
        logger.info(f"Subscribed to position-changed for {instrument_type.value}")
        return result

    async def subscribe_order(
        self,
        user_id: int,
        instrument_type: InstrumentType,
    ) -> dict:
        sub_key = f"order-changed:{instrument_type.value}"
        if sub_key in self._active_subscriptions:
            return {"success": True}

        result = await self._ws.subscribe(
            "portfolio.order-changed",
            "2.0",
            params={
                "routingFilters": {
                    "user_id": user_id,
                    "instrument_type": instrument_type.value,
                }
            },
        )
        self._active_subscriptions.add(sub_key)
        logger.info(f"Subscribed to order-changed for {instrument_type.value}")
        return result

    async def unsubscribe_all(self) -> None:
        self._active_subscriptions.clear()
