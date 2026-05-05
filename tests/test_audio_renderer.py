import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from song_agent.renderers.audio import (
    RendererConfig,
    RendererConfigError,
    RendererExecutionError,
    build_fluidsynth_command,
    load_renderer_config,
    render_audio,
    renderer_configured,
    save_renderer_config_from_dict,
    test_renderer_config as run_renderer_test,
)


def test_renderer_config_defaults() -> None:
    config = RendererConfig.from_dict({})

    assert config.renderer_type == "fluidsynth"
    assert config.fluidsynth_path == "fluidsynth"
    assert config.soundfont_path == ""
    assert config.sample_rate == 44100
    assert config.output_format == "wav"
    assert config.gain == 0.6
    assert renderer_configured(config) is False


def test_save_and_load_renderer_config(tmp_path: Path) -> None:
    soundfont = tmp_path / "soundfont.sf2"
    soundfont.write_bytes(b"sf2")
    path = tmp_path / ".musicforge" / "renderer.json"

    saved = save_renderer_config_from_dict(
        {
            "renderer_type": "fluidsynth",
            "fluidsynth_path": "C:\\Program Files\\FluidSynth\\bin\\fluidsynth.exe",
            "soundfont_path": str(soundfont),
            "sample_rate": 48000,
            "gain": 0.8,
        },
        path=path,
    )
    loaded, sources = load_renderer_config(path=path, env={})

    assert saved.soundfont_path == str(soundfont)
    assert loaded.fluidsynth_path.endswith("fluidsynth.exe")
    assert loaded.sample_rate == 48000
    assert loaded.gain == 0.8
    assert loaded.to_public_dict()["soundfont_exists"] is True
    assert sources["soundfont_path"] == "file"


def test_renderer_config_env_overrides_file(tmp_path: Path) -> None:
    file_soundfont = tmp_path / "file.sf2"
    env_soundfont = tmp_path / "env.sf3"
    file_soundfont.write_bytes(b"file")
    env_soundfont.write_bytes(b"env")
    path = tmp_path / "renderer.json"
    save_renderer_config_from_dict(
        {
            "soundfont_path": str(file_soundfont),
            "sample_rate": 44100,
            "gain": 0.5,
        },
        path=path,
    )

    config, sources = load_renderer_config(
        path=path,
        env={
            "MUSICFORGE_SOUNDFONT_PATH": str(env_soundfont),
            "MUSICFORGE_AUDIO_SAMPLE_RATE": "96000",
            "MUSICFORGE_AUDIO_GAIN": "1.2",
        },
    )

    assert config.soundfont_path == str(env_soundfont)
    assert config.sample_rate == 96000
    assert config.gain == 1.2
    assert sources["soundfont_path"] == "env"


def test_renderer_config_requires_soundfont() -> None:
    config = RendererConfig.from_dict({"soundfont_path": ""})

    with pytest.raises(RendererConfigError, match="soundfont_path is required"):
        config.validate_ready_for_render()


def test_renderer_test_rejects_missing_soundfont(tmp_path: Path) -> None:
    config = RendererConfig.from_dict({"soundfont_path": str(tmp_path / "missing.sf2")})

    with pytest.raises(RendererConfigError, match="SoundFont file does not exist"):
        run_renderer_test(config)


def test_render_audio_builds_fluidsynth_command(tmp_path: Path) -> None:
    midi = tmp_path / "song.mid"
    wav = tmp_path / "song.wav"
    sf2 = tmp_path / "font.sf2"
    midi.write_bytes(b"MThd")
    sf2.write_bytes(b"font")
    config = RendererConfig.from_dict(
        {
            "fluidsynth_path": "C:\\Program Files\\FluidSynth\\fluidsynth.exe",
            "soundfont_path": str(sf2),
            "sample_rate": 48000,
            "gain": 0.7,
        }
    )

    cmd = build_fluidsynth_command(midi, wav, config)

    assert cmd == [
        "C:\\Program Files\\FluidSynth\\fluidsynth.exe",
        "-ni",
        str(sf2),
        str(midi),
        "-F",
        str(wav),
        "-r",
        "48000",
        "-g",
        "0.7",
    ]


def test_render_audio_writes_wav_with_fake_runner(tmp_path: Path) -> None:
    midi = tmp_path / "song.mid"
    wav = tmp_path / "song.wav"
    sf2 = tmp_path / "font.sf2"
    midi.write_bytes(b"MThd")
    sf2.write_bytes(b"font")
    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        wav_path = Path(cmd[cmd.index("-F") + 1])
        wav_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    config = RendererConfig.from_dict({"soundfont_path": str(sf2)})

    output = render_audio(midi, wav, config, runner=fake_runner)

    assert output == wav
    assert wav.read_bytes().startswith(b"RIFF")
    assert calls[0][1]["shell"] is False
    assert "capture_output" in calls[0][1]


def test_render_audio_failure_raises_renderer_execution_error(tmp_path: Path) -> None:
    midi = tmp_path / "song.mid"
    wav = tmp_path / "song.wav"
    sf2 = tmp_path / "font.sf2"
    midi.write_bytes(b"MThd")
    sf2.write_bytes(b"font")

    def fake_runner(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="x" * 800)

    config = RendererConfig.from_dict({"soundfont_path": str(sf2)})

    with pytest.raises(RendererExecutionError) as exc:
        render_audio(midi, wav, config, runner=fake_runner)

    assert len(str(exc.value)) <= 503


def test_render_audio_does_not_use_shell_true(tmp_path: Path) -> None:
    midi = tmp_path / "song.mid"
    wav = tmp_path / "song.wav"
    sf2 = tmp_path / "font.sf2"
    midi.write_bytes(b"MThd")
    sf2.write_bytes(b"font")

    def fake_runner(cmd, **kwargs):
        assert isinstance(cmd, list)
        assert kwargs["shell"] is False
        wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    render_audio(midi, wav, RendererConfig.from_dict({"soundfont_path": str(sf2)}), runner=fake_runner)


def test_renderer_test_uses_list_args_and_no_shell(tmp_path: Path) -> None:
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"font")
    seen = {}

    def fake_runner(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["shell"] = kwargs["shell"]
        return SimpleNamespace(returncode=0, stdout="FluidSynth", stderr="")

    result = run_renderer_test(RendererConfig.from_dict({"soundfont_path": str(sf2)}), runner=fake_runner)

    assert result["ok"] is True
    assert seen["cmd"] == ["fluidsynth", "--version"]
    assert seen["shell"] is False


def test_renderer_test_maps_missing_binary(tmp_path: Path) -> None:
    sf2 = tmp_path / "font.sf2"
    sf2.write_bytes(b"font")

    def fake_runner(cmd, **kwargs):
        raise FileNotFoundError("missing")

    with pytest.raises(RendererExecutionError, match="FluidSynth executable was not found"):
        run_renderer_test(RendererConfig.from_dict({"soundfont_path": str(sf2)}), runner=fake_runner)


def test_render_audio_maps_timeout(tmp_path: Path) -> None:
    midi = tmp_path / "song.mid"
    wav = tmp_path / "song.wav"
    sf2 = tmp_path / "font.sf2"
    midi.write_bytes(b"MThd")
    sf2.write_bytes(b"font")

    def fake_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    with pytest.raises(RendererExecutionError, match="timed out"):
        render_audio(midi, wav, RendererConfig.from_dict({"soundfont_path": str(sf2)}), runner=fake_runner)
