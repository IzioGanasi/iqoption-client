import asyncio
import unittest
from unittest.mock import AsyncMock

from iqoption_client.configuration import Config
from iqoption_client.connection.event_bus import EventBus
from iqoption_client.connection.websocket_manager import WebSocketManager


class WebSocketResponseRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_arriving_during_send_is_not_lost(self):
        bus = EventBus()
        manager = WebSocketManager(Config(), bus)

        async def respond_immediately(envelope):
            # Simulate a server response arriving before the send call returns.
            await bus.dispatch({
                "name": "authenticated",
                "request_id": envelope["request_id"],
                "msg": "session-123",
            })

        manager._ws_send = AsyncMock(side_effect=respond_immediately)

        result = await manager._send_and_wait_for_response(
            "auth-test",
            {"name": "authenticate", "request_id": "auth-test"},
            timeout=0.1,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "authenticated")
        self.assertEqual(result["msg"], "session-123")
        self.assertNotIn("auth-test", bus._pending)

    async def test_timeout_removes_pending_future(self):
        bus = EventBus()
        manager = WebSocketManager(Config(), bus)
        manager._ws_send = AsyncMock()

        with self.assertRaisesRegex(Exception, "Timeout waiting for response"):
            await manager._send_and_wait_for_response(
                "never-responds",
                {"name": "request", "request_id": "never-responds"},
                timeout=0.01,
            )

        self.assertNotIn("never-responds", bus._pending)


if __name__ == "__main__":
    unittest.main()
