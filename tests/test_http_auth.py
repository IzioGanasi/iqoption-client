import unittest
from unittest.mock import AsyncMock, Mock

from iqoption_client.configuration import Config
from iqoption_client.connection.http_auth import HTTPAuth
from iqoption_client.exceptions import AuthenticationError


class FakeResponse:
    def __init__(self, status, payload=None, json_error=None):
        self.status = status
        self._payload = payload
        self._json_error = json_error

    async def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeRequestContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class HTTPAuthTests(unittest.IsolatedAsyncioTestCase):
    def make_auth(self, response):
        auth = HTTPAuth(Config(email="test@example.invalid", password="not-a-real-password"))
        session = Mock()
        session.post.return_value = FakeRequestContext(response)
        auth._get_session = AsyncMock(return_value=session)
        return auth, session

    async def test_success_returns_required_session_fields(self):
        auth, session = self.make_auth(FakeResponse(200, {
            "code": "success",
            "ssid": "session-id",
            "token": "token-value",
            "user_id": 42,
        }))

        result = await auth.login()

        self.assertEqual(result["ssid"], "session-id")
        self.assertEqual(result["token"], "token-value")
        self.assertEqual(result["user_id"], 42)
        self.assertEqual(result["company_id"], 0)
        self.assertEqual(result["created_at"], 0)
        self.assertTrue(session.post.called)

    async def test_rejected_credentials_raise_authentication_error(self):
        auth, _ = self.make_auth(FakeResponse(401, {
            "code": "invalid_credentials",
            "message": "Invalid credentials",
        }))

        with self.assertRaisesRegex(AuthenticationError, "Invalid credentials"):
            await auth.login()

    async def test_malformed_json_raises_authentication_error(self):
        auth, _ = self.make_auth(FakeResponse(502, json_error=ValueError("bad json")))

        with self.assertRaisesRegex(AuthenticationError, "invalid JSON"):
            await auth.login()

    async def test_missing_required_field_raises_clear_error(self):
        auth, _ = self.make_auth(FakeResponse(200, {
            "code": "success",
            "ssid": "session-id",
            "token": "token-value",
        }))

        with self.assertRaisesRegex(AuthenticationError, "user_id"):
            await auth.login()

    async def test_non_object_json_is_rejected(self):
        auth, _ = self.make_auth(FakeResponse(200, ["unexpected", "list"]))

        with self.assertRaisesRegex(AuthenticationError, "unexpected response format"):
            await auth.login()


if __name__ == "__main__":
    unittest.main()
