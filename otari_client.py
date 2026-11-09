"""Otari gateway client for Lingua's optional tutor layer.

Otari (by Mozilla AI) is an OpenAI-compatible LLM gateway: one hosted
endpoint in front of many providers, addressed with workspace-scoped
API keys (tokens starting ``otk_``). Lingua talks to it with nothing but
the Python standard library, in keeping with the plugin's zero
dependency rule.

Configuration, first hit wins per value:

1. Explicit arguments to :class:`OtariClient`.
2. Environment variables:
   - ``OTARI_API_KEY``  workspace token from otari.ai (starts ``otk_``)
   - ``OTARI_BASE_URL`` default ``https://api.otari.ai/api/v1``;
     EU-region keys must use ``https://eu.api.otari.ai/api/v1``
   - ``OTARI_MODEL``    provider/model id, e.g.
     ``openai/gpt-oss-20b``

Nothing in this module runs at import time and no request is made
unless a tutor tool is called with a key configured. Without a key the
client raises :class:`OtariNotConfigured` and the tutor tools turn that
into a short, helpful message; the offline Lingua tools never touch
this module's network path at all.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.otari.ai/api/v1"
EU_BASE_URL = "https://eu.api.otari.ai/api/v1"
# The model used in the Otari quickstart: an open-weight model served
# in provider/model form through the hosted gateway.
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_TIMEOUT = 30.0

MISSING_KEY_MESSAGE = (
    "Otari is not configured, so the tutor layer is off. To enable it: "
    "create a free account at https://otari.ai, create a workspace API "
    "key (it starts with otk_), and set the OTARI_API_KEY environment "
    "variable where Hermes runs. Lingua's offline tools (decks, SM-2 "
    "reviews, stats) keep working without a key."
)


class OtariError(Exception):
    """A gateway call failed; the message is safe to show the user."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class OtariNotConfigured(OtariError):
    """No API key is available, so no request was attempted."""


def _default_transport(url, headers, payload, timeout):
    """POST with urllib; returns (status, headers, body_bytes).

    Never raises for an HTTP error status: the caller maps statuses to
    friendly errors in one place. Network failures raise OtariError.
    """
    request = urllib.request.Request(
        url, data=payload, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()
    except urllib.error.URLError as exc:
        raise OtariError(f"Could not reach the Otari gateway: {exc.reason}") from exc
    except TimeoutError as exc:  # socket timeouts surface as TimeoutError
        raise OtariError(
            f"The Otari gateway did not answer within {timeout:.0f}s."
        ) from exc


def _error_message(status: int, body: bytes) -> str:
    """Turn a gateway error response into a specific, actionable line."""
    detail = ""
    if isinstance(body, bytes):
        body_text = body.decode("utf-8", errors="replace")
    elif isinstance(body, str):
        body_text = body
    else:  # a test double may hand back an already parsed value
        body_text = json.dumps(body)
    try:
        parsed = json.loads(body_text)
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif isinstance(error, str):
            detail = error
    except (ValueError, UnicodeDecodeError):
        detail = ""
    suffix = f" Gateway said: {detail}" if detail else ""
    if status in (401, 403):
        return (
            "Otari rejected the API key (HTTP "
            f"{status}). Check that OTARI_API_KEY holds a current "
            "workspace token from otari.ai (tokens start with otk_) and "
            f"that the key is allowed to use this model.{suffix}"
        )
    if status == 421:
        return (
            "Otari returned 421 Misdirected Request: this API key "
            "belongs to the EU region. Set OTARI_BASE_URL to "
            f"{EU_BASE_URL} and try again.{suffix}"
        )
    if status == 429:
        return (
            "Otari rate limited the request or the workspace budget "
            "ceiling was hit (HTTP 429). Wait a moment, check the "
            f"budget for this key in the Otari usage view, then retry.{suffix}"
        )
    if status == 404:
        return (
            "The Otari gateway returned 404. The model id may not be "
            "available to this workspace; check OTARI_MODEL against the "
            f"Models tab at otari.ai.{suffix}"
        )
    return f"Otari gateway error (HTTP {status}).{suffix}"


def _content_text(content) -> str:
    """Extract text from a chat completion message content value."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):  # content parts form
        parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        ]
        return "".join(parts).strip()
    return ""


class OtariClient:
    """Minimal OpenAI-compatible chat client pointed at Otari."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport=None,
    ):
        self.api_key = (
            api_key if api_key is not None
            else os.environ.get("OTARI_API_KEY", "")
        ).strip()
        self.base_url = (
            base_url if base_url is not None
            else os.environ.get("OTARI_BASE_URL", "") or DEFAULT_BASE_URL
        ).strip().rstrip("/")
        self.model = (
            model if model is not None
            else os.environ.get("OTARI_MODEL", "") or DEFAULT_MODEL
        ).strip()
        self.timeout = float(timeout)
        self._transport = transport or _default_transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages, model=None, temperature=0.7, max_tokens=None):
        """Send one chat completion; returns a plain dict.

        Returns ``{content, model, usage, raw}`` where ``content`` is
        the assistant's text. Raises OtariNotConfigured before any
        network use when no key is set, and OtariError for gateway,
        network, and malformed-response failures.
        """
        if not self.api_key:
            raise OtariNotConfigured(MISSING_KEY_MESSAGE)
        payload_dict = {
            "model": (model or self.model),
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload_dict["max_tokens"] = max_tokens
        payload = json.dumps(payload_dict).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        status, _resp_headers, body = self._transport(
            url, headers, payload, self.timeout
        )
        if status >= 400:
            raise OtariError(_error_message(status, body), status=status)
        try:
            raw = json.loads(body.decode("utf-8"))
            choice = raw["choices"][0]
            content = _content_text(choice["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise OtariError(
                "Otari returned a response Lingua could not parse."
            ) from exc
        if not content:
            raise OtariError("Otari returned an empty response.")
        return {
            "content": content,
            "model": raw.get("model") or payload_dict["model"],
            "usage": raw.get("usage") or {},
            "raw": raw,
        }

    def chat_text(self, messages, **kwargs) -> str:
        """Convenience wrapper: just the assistant's text."""
        return self.chat(messages, **kwargs)["content"]
