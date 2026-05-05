import pytest

from song_agent.agent.provider_pipeline import generate_provider_song_plan, load_provider_prompt
from song_agent.provider import ProviderConfig, ProviderOutputError
from song_agent.providers.mock import MockProviderClient
from song_agent.schemas.song import SongRequest


def request() -> SongRequest:
    return SongRequest(
        title="Provider Pipeline Song",
        language="en",
        style="city pop",
        theme="provider pipeline",
        duration_seconds=60,
        tempo_bpm=92,
    )


def test_provider_pipeline_uses_mock_and_returns_valid_song_plan():
    plan = generate_provider_song_plan(
        request(),
        ProviderConfig(wire_api="mock", model="mock-main"),
    )

    assert plan.title == "Provider Pipeline Song"
    assert {track.name for track in plan.tracks} == {"melody", "chords", "bass", "drums"}


def test_provider_pipeline_rejects_invalid_schema():
    with pytest.raises(ProviderOutputError, match="Provider output did not match SongPlan"):
        generate_provider_song_plan(
            request(),
            ProviderConfig(wire_api="mock", model="mock-main"),
            client=MockProviderClient(mode="invalid_schema"),
        )


def test_provider_prompt_requires_strict_json():
    prompt = load_provider_prompt()

    assert "Return only one JSON object" in prompt
    assert "Do not output Markdown" in prompt
    assert '"tracks"' in prompt
