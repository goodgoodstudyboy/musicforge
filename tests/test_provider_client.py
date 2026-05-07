import io
import json
import urllib.error

import pytest

from song_agent.provider import (
    ProviderConfig,
    ProviderEditResponse,
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
    assert plan.quality is not None
    assert plan.quality.scores is not None


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


def test_openai_compatible_client_generates_edit_patch_json():
    captured = {}
    parent = SongPlan.from_dict(MockProviderClient().generate_song_plan_json(request(), ProviderConfig()))
    response = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": 1,
                            "summary": "lift chorus",
                            "operations": [{"op": "set_section_energy", "section_name": "chorus", "energy": 0.9}],
                            "confidence": 0.8,
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }

    def opener(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(json.dumps(response).encode("utf-8"))

    data = OpenAICompatibleClient(opener=opener).generate_edit_patch_json(
        parent,
        "lift chorus",
        config(),
        "Return patch JSON.",
    )

    assert isinstance(data, ProviderEditResponse)
    assert data.data["operations"][0]["op"] == "set_section_energy"
    assert data.usage == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert data.request_id == "chatcmpl-test"
    assert captured["body"]["messages"][0]["content"] == "Return patch JSON."
    assert "sk-example-secret" not in json.dumps(captured["body"])


def test_openai_compatible_client_generates_edit_candidates_json():
    captured = {}
    parent = SongPlan.from_dict(MockProviderClient().generate_song_plan_json(request(), ProviderConfig()))
    response = {
        "id": "chatcmpl-candidates",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": 1,
                            "candidates": [
                                {
                                    "schema_version": 1,
                                    "summary": "one",
                                    "operations": [{"op": "set_section_energy", "section_name": "chorus", "energy": 0.8}],
                                    "confidence": 0.8,
                                },
                                {
                                    "schema_version": 1,
                                    "summary": "two",
                                    "operations": [{"op": "set_track_density", "track_name": "drums", "strength": 8}],
                                    "confidence": 0.7,
                                },
                            ],
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 21, "completion_tokens": 13, "total_tokens": 34},
    }

    def opener(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(json.dumps(response).encode("utf-8"))

    data = OpenAICompatibleClient(opener=opener).generate_edit_candidates_json(
        parent,
        "give options",
        config(),
        candidate_count=2,
        prompt="Return candidates.",
    )

    assert isinstance(data, ProviderEditResponse)
    assert len(data.data["candidates"]) == 2
    assert data.usage == {"prompt_tokens": 21, "completion_tokens": 13, "total_tokens": 34}
    assert data.request_id == "chatcmpl-candidates"
    assert captured["body"]["messages"][0]["content"] == "Return candidates."
    assert captured["body"]["messages"][1]["content"].find("candidate_count") >= 0
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


def test_openai_compatible_client_redacts_secret_from_http_error_body():
    secret = "sk-example-secret"

    def opener(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url,
            400,
            "bad request",
            hdrs={},
            fp=io.BytesIO(
                json.dumps(
                    {
                        "error": "request echoed",
                        "authorization": f"Bearer {secret}",
                        "api_key": secret,
                        "access_token": "token-value",
                    }
                ).encode("utf-8")
            ),
        )

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient(opener=opener).test(config())

    message = str(exc_info.value)
    assert secret not in message
    assert "token-value" not in message
    assert "[redacted]" in message


def test_openai_compatible_client_redacts_secret_from_os_error():
    secret = "sk-example-secret"

    def opener(req, timeout):
        raise OSError(f"connection failed with Authorization: Bearer {secret}")

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient(opener=opener).test(config())

    assert secret not in str(exc_info.value)
    assert "[redacted]" in str(exc_info.value)


def test_openai_compatible_client_handles_invalid_json():
    def opener(req, timeout):
        return FakeResponse(b"not json")

    with pytest.raises(ProviderResponseError, match="not valid JSON"):
        OpenAICompatibleClient(opener=opener).test(config())


def test_provider_output_must_be_song_plan():
    with pytest.raises(ProviderOutputError):
        raise ProviderOutputError("Provider output did not match SongPlan.")
