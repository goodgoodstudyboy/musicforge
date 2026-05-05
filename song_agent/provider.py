from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json


CONFIG_DIR = Path(".musicforge")
CONFIG_PATH = CONFIG_DIR / "provider.json"
SUPPORTED_WIRE_APIS = {"openai_chat_completions", "mock"}


class ProviderError(Exception):
    """Base class for provider-related failures."""


class ProviderConfigError(ProviderError):
    """Raised when provider configuration is incomplete or invalid."""


class ProviderRequestError(ProviderError):
    """Raised when a provider request cannot be completed."""


class ProviderResponseError(ProviderError):
    """Raised when a provider response is malformed or unsuccessful."""


class ProviderOutputError(ProviderError):
    """Raised when provider output cannot be used as a SongPlan."""


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str = ""
    wire_api: str = "openai_chat_completions"
    api_key: str = ""
    model: str = ""
    light_model: str = ""
    review_model: str = ""
    gateway_profile: str = ""
    reasoning_effort: str = ""
    service_tier: str = ""
    timeout_seconds: int = 60
    max_retries: int = 1
    max_output_tokens: int = 4000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        config = cls(
            base_url=str(data.get("base_url", "") or "").strip(),
            wire_api=str(data.get("wire_api", "openai_chat_completions") or "").strip(),
            api_key=str(data.get("api_key", "") or ""),
            model=str(data.get("model", "") or "").strip(),
            light_model=str(data.get("light_model", "") or "").strip(),
            review_model=str(data.get("review_model", "") or "").strip(),
            gateway_profile=str(data.get("gateway_profile", "") or "").strip(),
            reasoning_effort=str(data.get("reasoning_effort", "") or "").strip(),
            service_tier=str(data.get("service_tier", "") or "").strip(),
            timeout_seconds=int(data.get("timeout_seconds", 60) or 60),
            max_retries=int(data.get("max_retries", 1) or 0),
            max_output_tokens=int(data.get("max_output_tokens", 4000) or 4000),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.wire_api not in SUPPORTED_WIRE_APIS:
            raise ProviderConfigError(f"Unsupported provider wire_api: {self.wire_api}.")
        if self.timeout_seconds < 5 or self.timeout_seconds > 300:
            raise ProviderConfigError("timeout_seconds must be between 5 and 300.")
        if self.max_retries < 0 or self.max_retries > 5:
            raise ProviderConfigError("max_retries must be between 0 and 5.")
        if self.max_output_tokens < 256 or self.max_output_tokens > 16000:
            raise ProviderConfigError("max_output_tokens must be between 256 and 16000.")

    def validate_ready_for_provider(self) -> None:
        missing: list[str] = []
        if self.wire_api != "mock" and not self.base_url:
            missing.append("base_url")
        if self.wire_api != "mock" and not self.api_key:
            missing.append("api_key")
        if not self.model:
            missing.append("model")
        if missing:
            raise ProviderConfigError(
                f"Provider config is incomplete: {', '.join(missing)} is required."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_public_dict(self, sources: dict[str, str] | None = None) -> dict[str, Any]:
        data = {
            "base_url": self.base_url,
            "wire_api": self.wire_api,
            "api_key_set": bool(self.api_key),
            "api_key_masked": mask_api_key(self.api_key),
            "model": self.model,
            "light_model": self.light_model,
            "review_model": self.review_model,
            "gateway_profile": self.gateway_profile,
            "reasoning_effort": self.reasoning_effort,
            "service_tier": self.service_tier,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_output_tokens": self.max_output_tokens,
        }
        if sources is not None:
            data["sources"] = sources
        return data

    def to_snapshot(self, mode: str, captured_at: str) -> dict[str, Any]:
        return {
            "mode": mode,
            "base_url": self.base_url,
            "wire_api": self.wire_api,
            "model": self.model,
            "light_model": self.light_model,
            "review_model": self.review_model,
            "gateway_profile": self.gateway_profile,
            "reasoning_effort": self.reasoning_effort,
            "service_tier": self.service_tier,
            "api_key_set": bool(self.api_key),
            "api_key_masked": mask_api_key(self.api_key),
            "captured_at": captured_at,
        }


def load_provider_config(
    path: Path = CONFIG_PATH,
    env: dict[str, str] | None = None,
) -> tuple[ProviderConfig, dict[str, str]]:
    env_data = env if env is not None else os.environ
    data: dict[str, Any] = {}
    sources = {field: "default" for field in ProviderConfig.__dataclass_fields__}

    if path.exists():
        data.update(read_json(path))
        for field in data:
            if field in sources:
                sources[field] = "file"

    for field, env_name in _env_map().items():
        value = env_data.get(env_name)
        if value is not None:
            data[field] = value
            sources[field] = "env"

    return ProviderConfig.from_dict(data), sources


def save_provider_config(config: ProviderConfig, path: Path = CONFIG_PATH) -> Path:
    config.validate()
    return write_json(path, config.to_dict())


def save_provider_config_from_dict(data: dict[str, Any], path: Path = CONFIG_PATH) -> ProviderConfig:
    config = ProviderConfig.from_dict(data)
    save_provider_config(config, path)
    return config


def reset_provider_config(path: Path = CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def provider_configured(config: ProviderConfig) -> bool:
    return bool(config.model and (config.wire_api == "mock" or (config.base_url and config.api_key)))


def test_provider_config(config: ProviderConfig) -> dict[str, Any]:
    config.validate_ready_for_provider()
    if config.wire_api == "mock":
        from song_agent.providers.mock import MockProviderClient

        result = MockProviderClient().test()
    elif config.wire_api == "openai_chat_completions":
        from song_agent.providers.openai_compatible import OpenAICompatibleClient

        result = OpenAICompatibleClient().test(config)
    else:
        raise ProviderConfigError(f"Unsupported provider wire_api: {config.wire_api}.")
    return {
        "ok": True,
        "provider": {
            "wire_api": config.wire_api,
            "model": config.model,
            "base_url": config.base_url,
            "api_key_set": bool(config.api_key),
        },
        "message": result.get("message", "Provider test completed."),
    }


def mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}...{value[-4:]}"


def _env_map() -> dict[str, str]:
    return {
        "base_url": "MUSICFORGE_PROVIDER_BASE_URL",
        "wire_api": "MUSICFORGE_PROVIDER_WIRE_API",
        "api_key": "MUSICFORGE_API_KEY",
        "model": "MUSICFORGE_PROVIDER_MODEL",
        "light_model": "MUSICFORGE_PROVIDER_LIGHT_MODEL",
        "review_model": "MUSICFORGE_PROVIDER_REVIEW_MODEL",
        "timeout_seconds": "MUSICFORGE_PROVIDER_TIMEOUT_SECONDS",
        "max_retries": "MUSICFORGE_PROVIDER_MAX_RETRIES",
    }
