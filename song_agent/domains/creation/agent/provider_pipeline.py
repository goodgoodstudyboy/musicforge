from __future__ import annotations

from pathlib import Path
from typing import Any

from song_agent.domains.creation.provider import ProviderConfig, ProviderConfigError, ProviderOutputError
from song_agent.domains.creation.providers.mock import MockProviderClient
from song_agent.domains.creation.providers.openai_compatible import OpenAICompatibleClient
from song_agent.domains.creation.music_quality import attach_quality
from song_agent.application.legacy_dependencies.quality import validate_song_plan
from song_agent.domains.creation.schemas.song import SongPlan, SongRequest


PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "provider_song_plan.md"


def generate_provider_song_plan(
    request: SongRequest,
    config: ProviderConfig,
    client: Any | None = None,
) -> SongPlan:
    config.validate_ready_for_provider()
    client = client or _client_for_config(config)
    try:
        if config.wire_api == "mock":
            data = client.generate_song_plan_json(request, config)
        else:
            data = client.generate_song_plan_json(request, config, load_provider_prompt())
        if not isinstance(data, dict):
            raise ProviderOutputError("Provider output must be a JSON object.")
        plan = SongPlan.from_dict(data)
        validate_song_plan(plan)
        return attach_quality(plan) if plan.quality is None else plan
    except ProviderOutputError:
        raise
    except ValueError as exc:
        raise ProviderOutputError(f"Provider output did not match SongPlan: {exc}") from exc


def load_provider_prompt(path: Path = PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")


def _client_for_config(config: ProviderConfig) -> Any:
    if config.wire_api == "mock":
        return MockProviderClient()
    if config.wire_api == "openai_chat_completions":
        return OpenAICompatibleClient()
    raise ProviderConfigError(f"Unsupported provider wire_api: {config.wire_api}.")
