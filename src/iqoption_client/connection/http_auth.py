from __future__ import annotations

import ssl
import aiohttp
import logging
from typing import Optional

from ..configuration import Config
from ..exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class HTTPAuth:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def login(self) -> dict:
        session = await self._get_session()
        payload = {
            "identifier": self._config.email,
            "password": self._config.password,
        }
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://iqoption.com",
            "Referer": "https://iqoption.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        }
        try:
            async with session.post(
                self._config.login_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
            ) as resp:
                data = await resp.json()
                logger.debug(f"Login response: status={resp.status}")
                if resp.status != 200 or data.get("code") != "success":
                    raise AuthenticationError(
                        f"Login failed: {data.get('message', data.get('code', 'unknown'))}"
                    )
                return {
                    "ssid": data["ssid"],
                    "token": data["token"],
                    "user_id": data["user_id"],
                    "company_id": data.get("company_id", 0),
                    "created_at": data.get("created_at", 0),
                }
        except aiohttp.ClientError as e:
            raise AuthenticationError(f"HTTP error during login: {e}")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
