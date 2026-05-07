from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from song_agent.provider import (
    ProviderConfig,
    ProviderEditResponse,
    ProviderRequestError,
    ProviderResponseError,
)
from song_agent.schemas.song import SongRequest
from song_agent.schemas.song import SongPlan


UrlOpen = Callable[..., Any]


@dataclass
class OpenAICompatibleClient:
    opener: UrlOpen = urllib.request.urlopen

    def test(self, config: ProviderConfig) -> dict[str, Any]:
        config.validate_ready_for_provider()
        response = self._request(
            config,
            [
                {"role": "system", "content": "Return a JSON object only."},
                {"role": "user", "content": "{\"ok\": true}"},
            ],
            max_tokens=32,
        )
        return {"ok": True, "response_keys": sorted(response.keys())}

    def generate_song_plan_json(
        self,
        request: SongRequest,
        config: ProviderConfig,
        prompt: str,
    ) -> dict[str, Any]:
        config.validate_ready_for_provider()
        response = self._request(
            config,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(request.to_dict(), ensure_ascii=False)},
            ],
            max_tokens=config.max_output_tokens,
        )
        content = _extract_content(response)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("Provider response content was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("Provider response content must be a JSON object.")
        return data

    def generate_node_json(
        self,
        node_name: str,
        node_input: dict[str, Any],
        config: ProviderConfig,
        prompt: str,
    ) -> dict[str, Any]:
        config.validate_ready_for_provider()
        response = self._request(
            config,
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"node": node_name, "input": node_input},
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=config.max_output_tokens,
        )
        content = _extract_content(response)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("Provider node response content was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("Provider node response content must be a JSON object.")
        return data

    def generate_edit_patch_json(
        self,
        parent_plan: SongPlan,
        instruction: str,
        config: ProviderConfig,
        prompt: str,
    ) -> dict[str, Any]:
        config.validate_ready_for_provider()
        response = self._request(
            config,
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": instruction,
                            "song_plan": parent_plan.to_dict(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=min(config.max_output_tokens, 4000),
        )
        content = _extract_content(response)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("Provider edit response content was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("Provider edit response content must be a JSON object.")
        return ProviderEditResponse(
            data=data,
            usage=_usage_dict(response.get("usage")),
            request_id=_request_id(response),
        )

    def generate_edit_candidates_json(
        self,
        parent_plan: SongPlan,
        instruction: str,
        config: ProviderConfig,
        candidate_count: int,
        prompt: str,
    ) -> ProviderEditResponse:
        config.validate_ready_for_provider()
        response = self._request(
            config,
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": instruction,
                            "candidate_count": candidate_count,
                            "song_plan": parent_plan.to_dict(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=min(config.max_output_tokens, 8000),
        )
        content = _extract_content(response)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("Provider edit candidate response content was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("Provider edit candidate response content must be a JSON object.")
        return ProviderEditResponse(
            data=data,
            usage=_usage_dict(response.get("usage")),
            request_id=_request_id(response),
        )

    def _request(
        self,
        config: ProviderConfig,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
    ) -> dict[str, Any]:
        url = _join_url(config.base_url, "chat/completions")
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if config.reasoning_effort:
            payload["reasoning_effort"] = config.reasoning_effort
        if config.service_tier:
            payload["service_tier"] = config.service_tier

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            safe_body = _sanitize_provider_error(raw, config)
            raise ProviderRequestError(
                f"Provider request failed with HTTP {exc.code}: {_shorten(safe_body)}"
            ) from exc
        except OSError as exc:
            safe_error = _sanitize_provider_error(str(exc), config)
            raise ProviderRequestError(f"Provider request failed: {safe_error}") from exc

        if status < 200 or status >= 300:
            raise ProviderRequestError(f"Provider request failed with HTTP {status}.")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("Provider response was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("Provider response must be a JSON object.")
        return data


def _extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderResponseError("Provider response is missing choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderResponseError("Provider response choice must be an object.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ProviderResponseError("Provider response choice is missing message.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderResponseError("Provider response message content is empty.")
    return content


def _usage_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _request_id(response: dict[str, Any]) -> str | None:
    for key in ("id", "request_id"):
        value = response.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _shorten(value: str, limit: int = 300) -> str:
    return value if len(value) <= limit else value[:limit] + "..."


def _sanitize_provider_error(value: str, config: ProviderConfig | None = None) -> str:
    redacted = value
    if config is not None and config.api_key:
        redacted = redacted.replace(config.api_key, "[redacted]")
    patterns = [
        r'(?i)("(?:api[_-]?key|access[_-]?token|authorization)"\s*:\s*")([^"]+)(")',
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"'}]+",
        r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,\"'}]+",
        r"(?i)(access[_-]?token\s*[:=]\s*)[^\s,\"'}]+",
        r"(?i)(bearer\s+)[^\s\"'}]+",
        r"sk-[A-Za-z0-9_\-]{8,}",
    ]
    for pattern in patterns:
        redacted = re.sub(pattern, _redact_match, redacted)
    return redacted


def _redact_match(match: re.Match[str]) -> str:
    if match.lastindex == 3:
        return match.group(1) + "[redacted]" + match.group(3)
    if match.lastindex:
        return match.group(1) + "[redacted]"
    return "[redacted]"
