from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from ..models.enums import OptionType, Direction, OPTION_TYPE_IDS
from ..models.option import Option
from ..models.position import Position, DigitalPosition
from ..exceptions import TradingError

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager
    from ..connection.clock_sync import ClockSync
    from ..assets.manager import AssetsManager
    from ..accounts.manager import AccountsManager

logger = logging.getLogger(__name__)


class TradingManager:
    def __init__(
        self, ws: WebSocketManager, clock_sync: ClockSync,
        assets: AssetsManager, accounts: AccountsManager,
    ) -> None:
        self._ws = ws
        self._clock_sync = clock_sync
        self._assets = assets
        self._accounts = accounts
        self._pending_options: dict[int, asyncio.Future] = {}
        self._pending_digital: dict[int, asyncio.Future] = {}
        self._position_callbacks: list = []

    def on_position_changed(self, callback) -> None:
        self._position_callbacks.append(callback)
        self._ws.on("position-changed", self._handle_position_changed)

    def _handle_position_changed(self, msg: dict) -> None:
        raw_event = msg.get("raw_event", {})
        for key, data in raw_event.items():
            if "binary_options_option_changed" in key:
                pos = Position.from_event(data)
                # Only resolve future on terminal states to avoid race condition:
                # "opened" event resolves future, then win/loose arrives before
                # the new future is registered in the while loop.
                if pos.option_id in self._pending_options:
                    if pos.result in ("win", "loose", "tie"):
                        future = self._pending_options[pos.option_id]
                        if not future.done():
                            future.set_result(pos)
                for cb in self._position_callbacks:
                    try:
                        cb(pos)
                    except Exception as e:
                        logger.error(f"Position callback error: {e}")
            elif "digital_options_position_changed" in key:
                pos = DigitalPosition.from_event(data)
                # Only resolve future on terminal state (closed)
                if pos.id in self._pending_digital:
                    if pos.status == "closed":
                        future = self._pending_digital[pos.id]
                        if not future.done():
                            future.set_result(pos)
                for cb in self._position_callbacks:
                    try:
                        cb(pos)
                    except Exception as e:
                        logger.error(f"Position callback error: {e}")

    def _calculate_expired_blitz(self, expiration_size: int) -> int:
        server_time = self._clock_sync.server_time // 1000
        return server_time + expiration_size

    def _calculate_expired_from_period(self, active, option_type_name: str) -> int:
        """Calculate expired as nearest future candle close.
        
        Uses start_time from init data but falls back to epoch alignment
        if the start_time is too stale (produces expired too far in the future).
        """
        if not active or not active.option:
            raise TradingError(f"Invalid active for {option_type_name}")
        exp_time = active.option.exp_time
        start_time = active.option.start_time
        deadtime = active.deadtime
        if exp_time <= 0:
            raise TradingError(f"Invalid exp_time: {exp_time}")

        server_time = self._clock_sync.server_time // 1000

        # Primary: use start_time from init data
        elapsed = server_time - start_time
        if elapsed < 0:
            expired = start_time + exp_time
        else:
            periods = elapsed // exp_time
            expired = start_time + (periods + 1) * exp_time

        # Ensure deadtime
        while expired - server_time < deadtime:
            expired += exp_time

        # If expired is too far in the future (> 3 * exp_time), start_time is stale
        # Fall back to epoch-aligned boundaries
        if expired - server_time > 3 * exp_time:
            expired = ((server_time // exp_time) + 1) * exp_time
            while expired - server_time < deadtime:
                expired += exp_time

        return expired

    def _get_balance_id(self) -> int:
        bal_id = self._accounts.balance_id
        if bal_id:
            return bal_id
        raise TradingError("No balance selected.")

    async def open_binary_option(
        self, active_id: int, direction: Direction, amount: float,
        option_type: OptionType, expiration_size: int | None = None,
        profit_percent: int | None = None,
    ) -> Option:
        active = self._assets.get_active(active_id, option_type)
        if not active:
            raise TradingError(f"Active {active_id} not found for {option_type.value}")

        server_time_sec = self._clock_sync.server_time // 1000
        if not active.is_open(server_time_sec):
            raise TradingError(
                f"Active {active_id} not open "
                f"(suspended={active.is_suspended}, enabled={active.enabled})"
            )

        if profit_percent is None:
            profit_percent = self._assets.get_profit_percent(active_id, option_type)

        value = int(amount * 1_000_000)

        body = {
            "user_balance_id": self._get_balance_id(),
            "active_id": active_id,
            "option_type_id": OPTION_TYPE_IDS[option_type],
            "direction": direction.value,
            "refund_value": 0,
            "price": amount,
            "value": value,
            "profit_percent": profit_percent,
        }

        if option_type == OptionType.BLITZ:
            exp_size = expiration_size or (
                active.option.default_expiration if active.option else 30
            )
            body["expiration_size"] = exp_size
            body["expired"] = self._calculate_expired_blitz(exp_size)
        elif option_type == OptionType.TURBO:
            body["expired"] = self._calculate_expired_from_period(active, "turbo")
        elif option_type == OptionType.BINARY:
            body["expired"] = self._calculate_expired_from_period(active, "binary")

        logger.info(
            f"Opening {option_type.value} {direction.value} on {active_id}: "
            f"amount={amount}, expired={body.get('expired')}, "
            f"expiration_size={body.get('expiration_size', 'N/A')}, "
            f"profit_percent={profit_percent}"
        )

        result = await self._ws.send_message(
            "binary-options.open-option", "2.0", body=body
        )
        name = result.get("name", "")
        msg = result.get("msg", {})

        if name == "option" and isinstance(msg, dict) and "id" in msg:
            option = Option.from_open_response(msg, option_type)
            logger.info(f"Option opened: id={option.id}, exp={option.exp}")
            return option
        else:
            error_msg = msg.get("message", str(msg)) if isinstance(msg, dict) else str(msg)
            raise TradingError(
                f"Failed to open {option_type.value}: {error_msg} "
                f"(status={result.get('status')})"
            )

    async def open_digital_option(
        self, asset_id: int, direction: Direction, amount: str = "1",
        instrument_id: str | None = None, instrument_index: int | None = None,
    ) -> dict:
        if instrument_id is None or instrument_index is None:
            raise TradingError("instrument_id and instrument_index required.")

        body = {
            "user_balance_id": self._get_balance_id(),
            "instrument_id": instrument_id,
            "amount": amount,
            "instrument_index": instrument_index,
            "asset_id": asset_id,
        }

        result = await self._ws.send_message(
            "digital-options.place-digital-option", "3.0", body=body
        )
        name = result.get("name", "")
        msg = result.get("msg", {})

        if name == "digital-option-placed" and isinstance(msg, dict):
            option_id = msg.get("id", 0)
            if option_id:
                return {"id": option_id, "status": "placed"}

        error_msg = msg.get("message", str(msg)) if isinstance(msg, dict) else str(msg)
        raise TradingError(
            f"Failed to place digital: {error_msg} (status={result.get('status')})"
        )

    async def wait_for_binary_result(
        self, option_id: int, timeout: float = 300.0
    ) -> Position:
        deadline = time.monotonic() + timeout
        future = asyncio.get_event_loop().create_future()
        self._pending_options[option_id] = future
        try:
            remaining = deadline - time.monotonic()
            result = await asyncio.wait_for(future, timeout=max(remaining, 0.1))
            if isinstance(result, Position):
                return result
            raise TradingError(f"Unexpected result type: {type(result)}")
        except asyncio.TimeoutError:
            raise TradingError(f"Timeout waiting for result of option {option_id}")
        finally:
            self._pending_options.pop(option_id, None)

    async def wait_for_digital_result(
        self, digital_id: int, timeout: float = 300.0
    ) -> DigitalPosition:
        deadline = time.monotonic() + timeout
        future = asyncio.get_event_loop().create_future()
        self._pending_digital[digital_id] = future
        try:
            remaining = deadline - time.monotonic()
            result = await asyncio.wait_for(future, timeout=max(remaining, 0.1))
            if isinstance(result, DigitalPosition):
                return result
            raise TradingError(f"Unexpected result type: {type(result)}")
        except asyncio.TimeoutError:
            raise TradingError(f"Timeout waiting for digital result {digital_id}")
        finally:
            self._pending_digital.pop(digital_id, None)
