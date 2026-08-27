from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.account import Account, Balance

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class AccountsManager:
    def __init__(self, ws: WebSocketManager) -> None:
        self._ws = ws
        self._account: Account | None = None

    @property
    def account(self) -> Account | None:
        return self._account

    @property
    def user_id(self) -> int:
        return self._account.user_id if self._account else 0

    @property
    def balance_id(self) -> int | None:
        if self._account:
            bal = self._account.active_balance
            if bal:
                return bal.id
        return None

    async def login(self, ssid: str, token: str, user_id: int, **kwargs) -> Account:
        self._account = Account(
            user_id=user_id,
            ssid=ssid,
            token=token,
            company_id=kwargs.get("company_id", 0),
            created_at=kwargs.get("created_at", 0),
        )
        return self._account

    async def get_profile(self) -> dict:
        result = await self._ws.send_message("core.get-profile", "1.0")
        data = result.get("msg", {})
        profile_result = data.get("result", {})
        if self._account and profile_result:
            self._account.user_id = profile_result.get("id", self._account.user_id)
        return profile_result

    async def get_balances(self) -> list[Balance]:
        result = await self._ws.send_message(
            "internal-billing.get-balances",
            "1.0",
            body={"types_ids": [1, 4, 2], "tournaments_statuses_ids": [3, 2]},
        )
        balances_data = result.get("msg", [])
        if isinstance(balances_data, list):
            balances = [Balance.from_dict(b) for b in balances_data]
            if self._account:
                self._account.balances = balances
            return balances
        return []

    async def select_account(self, account_type: str = "demo") -> bool:
        if not self._account:
            return False
        if account_type == "demo":
            bal = self._account.demo_balance
        else:
            bal = self._account.real_balance
        if bal:
            self._account.select_balance(bal.id)
            logger.info(f"Selected {account_type} balance: {bal.id} (${bal.amount:.2f})")
            return True
        return False
