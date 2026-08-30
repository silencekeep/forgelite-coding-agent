from __future__ import annotations

import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from coding_agent.client import ChatCompletionsClient, ModelRequestError, _is_loopback_url


class JsonResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body


class LocalGatewayTests(unittest.TestCase):
    def test_only_loopback_urls_bypass_proxy(self) -> None:
        self.assertTrue(_is_loopback_url("http://127.0.0.1:13000/v1"))
        self.assertTrue(_is_loopback_url("http://localhost:13000/v1"))
        self.assertTrue(_is_loopback_url("http://[::1]:13000/v1"))
        self.assertFalse(_is_loopback_url("https://api.openai.com/v1"))
        self.assertFalse(_is_loopback_url("http://192.168.1.5/v1"))

    def test_client_marks_loopback_gateway_for_direct_connection(self) -> None:
        local = ChatCompletionsClient("unused", "http://127.0.0.1:13000/v1", "test")
        remote = ChatCompletionsClient("unused", "https://example.com/v1", "test")
        self.assertTrue(local._bypass_proxy)
        self.assertFalse(remote._bypass_proxy)

    def test_rate_limit_is_retried_then_succeeds(self) -> None:
        client = ChatCompletionsClient("unused", "https://example.com/v1", "test", retries=1)
        rate_limit = HTTPError(
            "https://example.com/v1/chat/completions",
            429,
            "rate limited",
            {},
            io.BytesIO(b'{"error":{"message":"slow down"}}'),
        )
        success = JsonResponse(b'{"choices":[{"message":{"content":"done"}}]}')
        with patch.object(client, "_open", side_effect=[rate_limit, success]) as opened:
            with patch("coding_agent.client.time.sleep") as sleep:
                response = client.complete([], [])
        self.assertEqual(response["choices"][0]["message"]["content"], "done")
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once()

    def test_non_retryable_client_error_fails_immediately(self) -> None:
        client = ChatCompletionsClient("unused", "https://example.com/v1", "test", retries=3)
        bad_request = HTTPError(
            "https://example.com/v1/chat/completions",
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":{"message":"invalid model"}}'),
        )
        with patch.object(client, "_open", side_effect=bad_request) as opened:
            with patch("coding_agent.client.time.sleep") as sleep:
                with self.assertRaisesRegex(ModelRequestError, "invalid model"):
                    client.complete([], [])
        opened.assert_called_once()
        sleep.assert_not_called()
