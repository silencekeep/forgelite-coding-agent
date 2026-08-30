"""A tiny OpenAI-compatible HTTP client; no model or agent SDK is used."""

from __future__ import annotations

import json
import ipaddress
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen


class ModelRequestError(RuntimeError):
    """A request to the configured model endpoint could not be completed."""


@dataclass
class ChatCompletionsClient:
    api_key: str
    base_url: str
    model: str
    retries: int = 3
    timeout_seconds: int = 90

    def __post_init__(self) -> None:
        # A surprisingly common desktop setup exports HTTP(S)_PROXY globally.
        # Sending a loopback gateway request through that proxy either fails or
        # leaks a local endpoint name.  Local model gateways must be direct.
        self._bypass_proxy = _is_loopback_url(self.base_url)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error = "unknown failure"
        for attempt in range(self.retries + 1):
            request = Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "local-coding-agent/0.1",
                },
                method="POST",
            )
            try:
                with self._open(request) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
                if not isinstance(decoded, dict) or not decoded.get("choices"):
                    raise ModelRequestError("Model response contains no choices.")
                return decoded
            except HTTPError as exc:
                detail = _error_detail(exc)
                # Most 4xx failures are configuration or request errors, where a
                # retry only wastes time. 429 remains retryable.
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise ModelRequestError(f"Model HTTP {exc.code}: {detail}") from exc
                last_error = f"Model HTTP {exc.code}: {detail}"
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"Model connection/response error: {exc}"
            except ModelRequestError:
                raise
            if attempt < self.retries:
                time.sleep(1.5 * (2**attempt))
        raise ModelRequestError(f"Request failed after {self.retries + 1} attempts: {last_error}")

    def _open(self, request: Request):
        if self._bypass_proxy:
            return build_opener(ProxyHandler({})).open(request, timeout=self.timeout_seconds)
        return urlopen(request, timeout=self.timeout_seconds)


def _error_detail(error: HTTPError) -> str:
    try:
        raw = error.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            message = parsed.get("error", {}).get("message")
            if message:
                return str(message)[:500]
        return raw[:500]
    except Exception:
        return error.reason if isinstance(error.reason, str) else "request rejected"


def _is_loopback_url(url: str) -> bool:
    """Return true only for a genuine local endpoint, never arbitrary private IPs."""
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"
