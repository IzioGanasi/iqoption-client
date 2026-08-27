from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self) -> None:
        self._ssid: str = ""
        self._token: str = ""
        self._user_id: int = 0
        self._company_id: int = 0
        self._created_at: int = 0
        self._connected_at: float = 0
        self._session_id: str = ""

    @property
    def ssid(self) -> str:
        return self._ssid

    @property
    def token(self) -> str:
        return self._token

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def age_seconds(self) -> float:
        if self._connected_at:
            return time.time() - self._connected_at
        return 0

    def set_credentials(
        self, ssid: str, token: str, user_id: int,
        company_id: int = 0, created_at: int = 0,
    ) -> None:
        self._ssid = ssid
        self._token = token
        self._user_id = user_id
        self._company_id = company_id
        self._created_at = created_at
        self._connected_at = time.time()

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id

    def clear(self) -> None:
        self._ssid = ""
        self._token = ""
        self._user_id = 0
        self._session_id = ""
        self._connected_at = 0

    @property
    def has_valid_ssid(self) -> bool:
        return bool(self._ssid)
