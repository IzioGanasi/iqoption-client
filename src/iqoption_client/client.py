from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from .configuration import Config
from .connection.event_bus import EventBus
from .connection.websocket_manager import WebSocketManager
from .connection.http_auth import HTTPAuth
from .connection.heartbeat import HeartbeatManager
from .connection.clock_sync import ClockSync
from .accounts.manager import AccountsManager
from .assets.manager import AssetsManager
from .candles.manager import CandlesManager
from .subscriptions.manager import SubscriptionsManager
from .history.manager import HistoryManager
from .events.manager import EventsManager
from .trading.manager import TradingManager
from .reconnection.manager import ReconnectionManager
from .session.manager import SessionManager
from .connection_manager.manager import ConnectionManager, ConnectionState
from .operations.manager import OperationsManager
from .logging import CredentialFilter
from .logging import setup_logging
from .models.enums import OptionType, Direction, InstrumentType
from .models.option import Option
from .models.position import Position, DigitalPosition

logger = logging.getLogger(__name__)


class IQOptionClient:
    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()
        setup_logging(
            level=self._config.log_level,
            mask_credentials=True,
        )

        self._event_bus = EventBus()
        self._ws = WebSocketManager(self._config, self._event_bus)
        self._http = HTTPAuth(self._config)
        self._heartbeat = HeartbeatManager(self._config.heartbeat_interval)
        self._clock_sync = ClockSync()
        self._accounts = AccountsManager(self._ws)
        self._assets = AssetsManager(self._ws, self._clock_sync)
        self._candles = CandlesManager(self._ws)
        self._subscriptions = SubscriptionsManager(self._ws)
        self._history = HistoryManager(self._ws)
        self._events = EventsManager(self._ws)
        self._trading = TradingManager(
            self._ws, self._clock_sync, self._assets, self._accounts
        )
        self._reconnection = ReconnectionManager(
            self._ws, self._accounts, self._clock_sync,
            max_attempts=self._config.max_reconnect_attempts,
            base_delay=self._config.reconnect_delay,
        )
        self._session = SessionManager()
        self._conn_manager = ConnectionManager()
        self._operations = OperationsManager()

        self._connected = False
        self._time_sync_task: asyncio.Task | None = None

    @property
    def user_id(self) -> int:
        return self._accounts.user_id

    @property
    def balance_id(self) -> int | None:
        return self._accounts.balance_id

    @property
    def server_time(self) -> int:
        return self._clock_sync.server_time

    @property
    def clock_offset(self) -> int:
        return self._clock_sync.offset

    @property
    def assets(self) -> AssetsManager:
        return self._assets

    @property
    def candles(self) -> CandlesManager:
        return self._candles

    @property
    def accounts(self) -> AccountsManager:
        return self._accounts

    @property
    def subscriptions(self) -> SubscriptionsManager:
        return self._subscriptions

    @property
    def history(self) -> HistoryManager:
        return self._history

    @property
    def events(self) -> EventsManager:
        return self._events

    @property
    def trading(self) -> TradingManager:
        return self._trading

    @property
    def reconnection(self) -> ReconnectionManager:
        return self._reconnection

    @property
    def session(self) -> SessionManager:
        return self._session

    @property
    def connection_manager(self) -> ConnectionManager:
        return self._conn_manager

    @property
    def operations(self) -> OperationsManager:
        return self._operations

    async def connect(self) -> None:
        logger.info("Connecting to IQ Option...")

        login_data = await self._http.login()
        ssid = login_data["ssid"]
        token = login_data["token"]
        user_id = login_data["user_id"]

        await self._accounts.login(
            ssid, token, user_id,
            company_id=login_data.get("company_id", 0),
            created_at=login_data.get("created_at", 0),
        )
        logger.info(f"Login successful, user_id={user_id}")

        await self._ws.connect(ssid)
        logger.info("WebSocket connected")

        # Start listening for timeSync
        self._event_bus.on("timeSync", self._on_time_sync)
        self._time_sync_task = asyncio.create_task(self._receive_time_sync())

        # Start heartbeat
        self._heartbeat.start()

        # Get profile to confirm user_id
        profile = await self._accounts.get_profile()
        if profile:
            self._accounts._account.user_id = profile.get("id", user_id)
            logger.info(f"Profile loaded, user_id={self._accounts.user_id}")

        # Load balances
        await self._accounts.get_balances()
        await self._accounts.select_account(self._config.account_type)

        # Load assets
        await self._assets.load_initialization_data()
        await self._assets.load_trading_params()

        # Store session info
        self._session.set_credentials(
            ssid, token, user_id,
            company_id=login_data.get("company_id", 0),
            created_at=login_data.get("created_at", 0),
        )
        self._session.set_session_id(self._ws.client_session_id)

        # Start reconnection monitoring
        self._reconnection.save_ssid(ssid)
        self._reconnection.start_monitoring()

        self._conn_manager.set_state(ConnectionState.CONNECTED)
        self._connected = True
        logger.info("Connected and initialized")

    async def disconnect(self) -> None:
        self._connected = False
        self._reconnection.stop_monitoring()
        self._heartbeat.stop()
        if self._time_sync_task:
            self._time_sync_task.cancel()
            try:
                await self._time_sync_task
            except asyncio.CancelledError:
                pass
        await self._ws.disconnect()
        await self._http.close()
        self._conn_manager.set_state(ConnectionState.DISCONNECTED, "manual")
        self._session.clear()
        logger.info("Disconnected")

    async def _receive_time_sync(self) -> None:
        while self._connected:
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break

    def _on_time_sync(self, msg) -> None:
        if isinstance(msg, (int, float)):
            self._clock_sync.update(int(msg))
        elif isinstance(msg, dict):
            ts = msg.get("msg", 0)
            if ts:
                self._clock_sync.update(int(ts))

    # --- Trading shortcuts ---

    async def place_call(
        self,
        active_id: int,
        amount: float,
        option_type: OptionType,
        expiration_size: int | None = None,
        profit_percent: int | None = None,
    ) -> Option:
        return await self._trading.open_binary_option(
            active_id, Direction.CALL, amount, option_type,
            expiration_size=expiration_size,
            profit_percent=profit_percent,
        )

    async def place_put(
        self,
        active_id: int,
        amount: float,
        option_type: OptionType,
        expiration_size: int | None = None,
        profit_percent: int | None = None,
    ) -> Option:
        return await self._trading.open_binary_option(
            active_id, Direction.PUT, amount, option_type,
            expiration_size=expiration_size,
            profit_percent=profit_percent,
        )

    async def wait_for_binary_result(
        self, option_id: int, timeout: float = 300.0
    ) -> Position:
        return await self._trading.wait_for_binary_result(option_id, timeout)

    async def wait_for_digital_result(
        self, digital_id: int, timeout: float = 300.0
    ) -> DigitalPosition:
        return await self._trading.wait_for_digital_result(digital_id, timeout)

    async def subscribe_positions(
        self, instrument_type: InstrumentType
    ) -> dict:
        user_id = self._accounts.user_id
        bal_id = self._accounts.balance_id
        if not user_id or not bal_id:
            from .exceptions import TradingError
            raise TradingError("Must connect and select account first")
        return await self._subscriptions.subscribe_portfolio(
            user_id, bal_id, instrument_type
        )

    def on_position_changed(self, callback: Callable) -> None:
        self._trading.on_position_changed(callback)

    def on(self, event_name: str, callback: Callable) -> None:
        self._events.on(event_name, callback)
