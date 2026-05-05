import io
import json
import urllib.error

import pytest

from song_agent.provider import (
    ProviderConfig,
    ProviderOutputError,
    ProviderRequestError,
    ProviderResponseError,
)
from song_agent.providers.mock import MockProviderClient
from song_agent.providers.openai_compatible import OpenAICompatibleClient
from song_agent.quality import validate_song_plan
from song_agent.schemas.song import SongPlan, SongRequest


class FakeResponse:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.data


def request() -> SongRequest:
    return SongRequest(
        title="Provider Song",
        language="en",
        style="city pop",
        theme="rain",
        duration_seconds=60,
        tempo_bpm=92,
    )


def config() -> ProviderConfig:
    return ProviderConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-example-secret",
        model="example-main",
    )


def test_mock_provider_returns_valid_song_plan():
    data = MockProviderClient().generate_song_plan_json(
        request(),
        ProviderConfig(wire_api="mock", model="mock-main"),
    )

    plan = SongPlan.from_dict(data)
    validate_song_plan(plan)


def test_mock_provider_can_return_invalid_schema():
    data = MockProviderClient(mode="invalid_schema").generate_song_plan_json(
        request(),
        ProviderConfig(wire_api="mock", model="mock-main"),
    )

    with pytest.raises(ValueError):
        SongPlan.from_dict(data)


def test_openai_compatible_client_builds_request_without_logging_key():
    captured = {}
    song_plan = MockProviderClient().generate_song_plan_json(request(), ProviderConfig())
    response = {
        "choices": [
            {"message": {"content": json.dumps(song_plan)}},
        ]
    }

    def opener(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(json.dumps(response).encode("utf-8"))

    data = OpenAICompatibleClient(opener=opener).generate_song_plan_json(
        request(),
        config(),
        "Return JSON only.",
    )

    assert data["title"] == "Provider Song"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["timeout"] == 60
    assert captured["headers"]["Authorization"] == "Bearer sk-example-secret"
    assert "sk-example-secret" not in json.dumps(captured["body"])


def test_openai_compatible_client_handles_non_2xx():
    def opener(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url,
            500,
            "server error",
            hdrs={},
            fp=io.BytesIO(b"{\"error\":\"boom\"}"),
        )

    with pytest.raises(ProviderRequestError, match="HTTP 500"):
        OpenAICompatibleClient(opener=opener).test(config())


def test_openai_compatible_client_handles_invalid_json():
    def opener(req, timeout):
        return FakeResponse(b"not json")

    with pytest.raises(ProviderResponseError, match="not valid JSON"):
        OpenAICompatibleClient(opener=opener).test(config())


def test_provider_output_must_be_song_plan():
    with pytest.raises(ProviderOutputError):
        raise ProviderOutputError("Provider output did not match SongPlan.")
