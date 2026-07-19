from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import os as os
from dataclasses import asdict as asdict, dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.provider_contracts import ProviderConfig as ProviderConfig, ProviderConfigError as ProviderConfigError, ProviderEditResponse as ProviderEditResponse, ProviderError as ProviderError, ProviderOutputError as ProviderOutputError, ProviderRequestError as ProviderRequestError, ProviderResponseError as ProviderResponseError, SUPPORTED_WIRE_APIS as SUPPORTED_WIRE_APIS, mask_api_key as mask_api_key


CONFIG_DIR = Path(".musicforge")
CONFIG_PATH = CONFIG_DIR / "provider.json"
def load_provider_config(
    path: Path = CONFIG_PATH,
    env: dict[str, str] | None = None,
) -> tuple[ProviderConfig, dict[str, str]]:
    env_data = env if env is not None else os.environ
    data: ImplementationDocument = {}
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


def save_provider_config_from_dict(data: DomainDocument, path: Path = CONFIG_PATH) -> ProviderConfig:
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


def test_provider_config(config: ProviderConfig) -> DomainDocument:
    config.validate_ready_for_provider()
    if config.wire_api == "mock":
        from song_agent.domains.creation.providers.mock import MockProviderClient

        result = MockProviderClient().test()
    elif config.wire_api == "openai_chat_completions":
        from song_agent.domains.creation.providers.openai_compatible import OpenAICompatibleClient

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
