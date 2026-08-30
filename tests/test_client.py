from __future__ import annotations

import unittest

from coding_agent.client import ChatCompletionsClient, _is_loopback_url


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
