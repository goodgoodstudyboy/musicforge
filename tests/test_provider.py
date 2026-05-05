import pytest

from song_agent.provider import (
    CONFIG_PATH,
    ProviderConfig,
    ProviderConfigError,
    load_provider_config,
    mask_api_key,
    provider_configured,
    reset_provider_config,
    save_provider_config,
)


def test_provider_config_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config, sources = load_provider_config()

    assert config == ProviderConfig()
    assert sources["base_url"] == "default"
    assert provider_configured(config) is False


def test_provider_config_save_and_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = ProviderConfig(
        base_url="https://api.example.com/v1",
        wire_api="openai_chat_completions",
        api_key="sk-example-secret",
        model="example-main",
    )

    save_provider_config(config)
    loaded, sources = load_provider_config()

    assert (tmp_path / CONFIG_PATH).exists()
    assert loaded == config
    assert sources["model"] == "file"


@pytest.mark.parametrize(
    ("value", "masked"),
    [
        ("", ""),
        ("short", "***"),
        ("sk-example-secret", "sk-...cret"),
    ],
)
def test_provider_config_masks_api_key(value, masked):
    assert mask_api_key(value) == masked


def test_provider_config_public_dict_never_includes_plain_key():
    config = ProviderConfig(api_key="sk-example-secret", model="mock-main", wire_api="mock")

    public = config.to_public_dict()

    assert "api_key" not in public
    assert public["api_key_set"] is True
    assert public["api_key_masked"] == "sk-...cret"


def test_provider_config_env_overrides_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_provider_config(
        ProviderConfig(
            base_url="https://file.example.com/v1",
            api_key="file-secret",
            model="file-model",
        )
    )

    loaded, sources = load_provider_config(
        env={
            "MUSICFORGE_PROVIDER_BASE_URL": "https://env.example.com/v1",
            "MUSICFORGE_API_KEY": "env-secret",
            "MUSICFORGE_PROVIDER_MODEL": "env-model",
            "MUSICFORGE_PROVIDER_TIMEOUT_SECONDS": "45",
        }
    )

    assert loaded.base_url == "https://env.example.com/v1"
    assert loaded.api_key == "env-secret"
    assert loaded.model == "env-model"
    assert loaded.timeout_seconds == 45
    assert sources["base_url"] == "env"
    assert sources["api_key"] == "env"


def test_provider_config_rejects_invalid_timeout():
    with pytest.raises(ProviderConfigError, match="timeout_seconds"):
        ProviderConfig.from_dict({"timeout_seconds": 4})


def test_provider_config_rejects_unknown_wire_api():
    with pytest.raises(ProviderConfigError, match="Unsupported provider wire_api"):
        ProviderConfig.from_dict({"wire_api": "unknown"})


def test_provider_config_requires_model_for_provider_jobs():
    config = ProviderConfig(base_url="https://api.example.com/v1", api_key="secret")

    with pytest.raises(ProviderConfigError, match="model"):
        config.validate_ready_for_provider()


def test_provider_reset_removes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_provider_config(ProviderConfig(wire_api="mock", model="mock-main"))

    removed = reset_provider_config()

    assert removed is True
    assert not (tmp_path / CONFIG_PATH).exists()
