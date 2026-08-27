from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import websockets
from websockets.asyncio.client import connect

from ..configuration import Config
from ..models.messages import make_request_id, make_local_time
from .event_bus import EventBus
from ..exceptions import WebSocketError

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self, config: Config, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = asyncio.Event()
        self._receive_task: Optional[asyncio.Task] = None
        self._ssid: str = ""
        self._client_session_id: str = ""
        self._request_counter = 0
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def client_session_id(self) -> str:
        return self._client_session_id

    async def connect(self, ssid: str) -> str:
        self._ssid = ssid
        self._connected.clear()

        extra_headers = {
            "Origin": "https://iqoption.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        }

        try:
            self._ws = await connect(
                self._config.ws_url,
                additional_headers=extra_headers,
                ping_interval=None,
                close_timeout=5,
                max_size=2**24,  # 16MB to handle large init data
            )
        except Exception as e:
            raise WebSocketError(f"Failed to connect: {e}")

        self._receive_task = asyncio.create_task(self._receive_loop())

        # Authenticate
        client_session_id = await self._authenticate()
        self._connected.set()
        return client_session_id

    async def _authenticate(self) -> str:
        request_id = make_request_id("auth")
        msg = {
            "name": "authenticate",
            "request_id": request_id,
            "local_time": make_local_time(),
            "msg": {
                "ssid": self._ssid,
                "protocol": 3,
                "session_id": "",
                "client_session_id": "",
            },
        }
        await self._ws_send(msg)

        # Wait for "authenticated" response (not a result ack)
        result = await self._wait_for_response(request_id, timeout=10.0)
        if not result.get("success"):
            raise WebSocketError("Authentication failed")

        self._client_session_id = result.get("msg", "")

        # Send setOptions - only gets a "result" ack, no data response
        await self._ws_send({
            "name": "setOptions",
            "request_id": make_request_id("opts"),
            "local_time": make_local_time(),
            "msg": {"sendResults": True},
        })
        await asyncio.sleep(0.1)

        return self._client_session_id

    async def disconnect(self) -> None:
        self._connected.clear()
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _ws_send(self, data: dict) -> None:
        if not self._ws:
            raise WebSocketError("WebSocket not connected")
        raw = json.dumps(data)
        logger.debug(f"WS SEND: {raw[:200]}")
        await self._ws.send(raw)

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    message = json.loads(raw)
                    await self._event_bus.dispatch(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {raw[:100]}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket closed: {e}")
            self._connected.clear()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            self._connected.clear()

    async def _wait_for_response(
        self, request_id: str, timeout: float = 10.0
    ) -> dict:
        future = asyncio.get_event_loop().create_future()
        self._event_bus.set_pending(request_id, future)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._event_bus.remove_pending(request_id)
            raise WebSocketError(f"Timeout waiting for response to {request_id}")
        finally:
            self._event_bus.remove_pending(request_id)

    async def send_message(
        self,
        name: str,
        version: str,
        body: dict | None = None,
        timeout: float = 15.0,
    ) -> dict:
        request_id = str(self._request_counter)
        self._request_counter += 1

        msg_content: dict = {"name": name, "version": version}
        if body:
            msg_content["body"] = body

        envelope = {
            "name": "sendMessage",
            "request_id": request_id,
            "local_time": make_local_time(),
            "msg": msg_content,
        }

        await self._ws_send(envelope)
        result = await self._wait_for_response(request_id, timeout=timeout)
        return result

    async def subscribe(
        self,
        name: str,
        version: str = "1.0",
        params: dict | None = None,
    ) -> dict:
        # Subscriptions only get a "result" ack - fire and forget
        request_id = f"s_{self._request_counter}"
        self._request_counter += 1

        msg_content: dict = {"name": name, "version": version}
        if params:
            msg_content["params"] = params

        envelope = {
            "name": "subscribeMessage",
            "request_id": request_id,
            "local_time": make_local_time(),
            "msg": msg_content,
        }

        await self._ws_send(envelope)
        await asyncio.sleep(0.05)
        return {"success": True, "request_id": request_id}

    async def unsubscribe(
        self,
        name: str,
        version: str = "1.0",
        params: dict | None = None,
    ) -> dict:
        request_id = f"u_{self._request_counter}"
        self._request_counter += 1

        msg_content: dict = {"name": name, "version": version}
        if params:
            msg_content["params"] = params

        envelope = {
            "name": "unsubscribeMessage",
            "request_id": request_id,
            "local_time": make_local_time(),
            "msg": msg_content,
        }

        await self._ws_send(envelope)
        await asyncio.sleep(0.05)
        return {"success": True}

    def on(self, event_name: str, callback) -> None:
        self._event_bus.on(event_name, callback)

    def off(self, event_name: str, callback) -> None:
        self._event_bus.off(event_name, callback)
