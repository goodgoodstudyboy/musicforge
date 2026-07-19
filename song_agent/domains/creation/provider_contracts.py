from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
from dataclasses import asdict, dataclass


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
class ProviderEditResponse:
    data: ImplementationDocument
    usage: ImplementationDocument | None = None
    request_id: str | None = None


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
    def from_dict(cls, data: DomainDocument) -> "ProviderConfig":
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

    def to_dict(self) -> DomainDocument:
        return asdict(self)

    def to_public_dict(self, sources: dict[str, str] | None = None) -> DomainDocument:
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

    def to_snapshot(self, mode: str, captured_at: str) -> DomainDocument:
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


def mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}...{value[-4:]}"
