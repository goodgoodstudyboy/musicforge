from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import os as os
import subprocess as subprocess
from dataclasses import asdict as asdict, dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any, Callable as Callable

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json


CONFIG_DIR = Path(".musicforge")
CONFIG_PATH = CONFIG_DIR / "renderer.json"
SUPPORTED_RENDERERS = {"fluidsynth"}
SUPPORTED_OUTPUT_FORMATS = {"wav"}


class RendererError(ValueError):
    """Base class for audio renderer failures."""


class RendererConfigError(RendererError):
    """Raised when renderer configuration is incomplete or invalid."""


class RendererExecutionError(RendererError):
    """Raised when renderer execution fails."""


@dataclass(frozen=True)
class RendererConfig:
    renderer_type: str = "fluidsynth"
    fluidsynth_path: str = "fluidsynth"
    soundfont_path: str = ""
    sample_rate: int = 44100
    output_format: str = "wav"
    gain: float = 0.6

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "RendererConfig":
        config = cls(
            renderer_type=str(data.get("renderer_type", "fluidsynth") or "").strip(),
            fluidsynth_path=str(data.get("fluidsynth_path", "fluidsynth") or "").strip(),
            soundfont_path=str(data.get("soundfont_path", "") or "").strip(),
            sample_rate=int(data.get("sample_rate", 44100) or 44100),
            output_format=str(data.get("output_format", "wav") or "").strip(),
            gain=float(data.get("gain", 0.6) if data.get("gain", None) not in {None, ""} else 0.6),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.renderer_type not in SUPPORTED_RENDERERS:
            raise RendererConfigError(f"Unsupported renderer_type: {self.renderer_type}.")
        if not self.fluidsynth_path:
            raise RendererConfigError("fluidsynth_path is required.")
        if self.sample_rate < 8000 or self.sample_rate > 192000:
            raise RendererConfigError("sample_rate must be between 8000 and 192000.")
        if self.output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise RendererConfigError("output_format must be wav.")
        if self.gain < 0.0 or self.gain > 10.0:
            raise RendererConfigError("gain must be between 0.0 and 10.0.")

    def validate_ready_for_render(self) -> None:
        self.validate()
        if not self.soundfont_path:
            raise RendererConfigError("soundfont_path is required.")
        if not Path(self.soundfont_path).exists():
            raise RendererConfigError("SoundFont file does not exist.")

    def to_dict(self) -> DomainDocument:
        return asdict(self)

    def to_public_dict(self, sources: dict[str, str] | None = None) -> DomainDocument:
        soundfont = Path(self.soundfont_path) if self.soundfont_path else None
        data = {
            "renderer_type": self.renderer_type,
            "fluidsynth_path": self.fluidsynth_path,
            "soundfont_path": self.soundfont_path,
            "soundfont_exists": bool(soundfont and soundfont.exists()),
            "soundfont_warning": soundfont_warning(self.soundfont_path),
            "sample_rate": self.sample_rate,
            "output_format": self.output_format,
            "gain": self.gain,
        }
        if sources is not None:
            data["sources"] = sources
        return data


Runner = Callable[..., Any]


def load_renderer_config(
    path: Path = CONFIG_PATH,
    env: dict[str, str] | None = None,
) -> tuple[RendererConfig, dict[str, str]]:
    env_data = env if env is not None else os.environ
    data: ImplementationDocument = {}
    sources = {field: "default" for field in RendererConfig.__dataclass_fields__}

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

    return RendererConfig.from_dict(data), sources


def save_renderer_config(config: RendererConfig, path: Path = CONFIG_PATH) -> Path:
    config.validate()
    return write_json(path, config.to_dict())


def save_renderer_config_from_dict(data: DomainDocument, path: Path = CONFIG_PATH) -> RendererConfig:
    config = RendererConfig.from_dict(data)
    save_renderer_config(config, path)
    return config


def reset_renderer_config(path: Path = CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def renderer_configured(config: RendererConfig) -> bool:
    return bool(
        config.renderer_type == "fluidsynth"
        and config.fluidsynth_path
        and config.soundfont_path
        and Path(config.soundfont_path).exists()
    )


def test_renderer_config(
    config: RendererConfig,
    *,
    runner: Runner | None = None,
    timeout_seconds: int = 10,
) -> DomainDocument:
    config.validate_ready_for_render()
    runner = runner or subprocess.run
    cmd = [config.fluidsynth_path, "--version"]
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=timeout_seconds, shell=False)
    except FileNotFoundError as exc:
        raise RendererExecutionError("FluidSynth executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RendererExecutionError("FluidSynth test timed out.") from exc
    except OSError as exc:
        raise RendererExecutionError(_short_error(str(exc))) from exc
    returncode = int(getattr(result, "returncode", 0) or 0)
    if returncode != 0:
        stderr = str(getattr(result, "stderr", "") or "")
        stdout = str(getattr(result, "stdout", "") or "")
        raise RendererExecutionError(_short_error(stderr or stdout or "FluidSynth test failed."))
    return {
        "ok": True,
        "renderer": {
            "renderer_type": config.renderer_type,
            "fluidsynth_path": config.fluidsynth_path,
            "soundfont_exists": Path(config.soundfont_path).exists(),
        },
        "message": "Renderer test completed.",
    }


def render_audio(
    midi_path: Path,
    wav_path: Path,
    config: RendererConfig,
    *,
    runner: Runner | None = None,
    timeout_seconds: int = 300,
) -> Path:
    config.validate_ready_for_render()
    if not midi_path.exists():
        raise RendererConfigError("MIDI file does not exist.")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    runner = runner or subprocess.run
    cmd = build_fluidsynth_command(midi_path, wav_path, config)
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=timeout_seconds, shell=False)
    except FileNotFoundError as exc:
        raise RendererExecutionError("FluidSynth executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RendererExecutionError("Audio render timed out.") from exc
    except OSError as exc:
        raise RendererExecutionError(_short_error(str(exc))) from exc
    returncode = int(getattr(result, "returncode", 0) or 0)
    if returncode != 0:
        stderr = str(getattr(result, "stderr", "") or "")
        stdout = str(getattr(result, "stdout", "") or "")
        raise RendererExecutionError(_short_error(stderr or stdout or "Audio render failed."))
    if not wav_path.exists():
        raise RendererExecutionError("Audio render did not create song.wav.")
    return wav_path


def build_fluidsynth_command(midi_path: Path, wav_path: Path, config: RendererConfig) -> list[str]:
    return [
        config.fluidsynth_path,
        "-ni",
        config.soundfont_path,
        str(midi_path),
        "-F",
        str(wav_path),
        "-r",
        str(config.sample_rate),
        "-g",
        str(config.gain),
    ]


def soundfont_warning(soundfont_path: str) -> str | None:
    if not soundfont_path:
        return None
    suffix = Path(soundfont_path).suffix.lower()
    if suffix and suffix not in {".sf2", ".sf3"}:
        return "SoundFont extension is not .sf2 or .sf3."
    return None


def _short_error(value: str, limit: int = 500) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value or "Audio renderer failed."
    return value[:limit].rstrip() + "..."


def _env_map() -> dict[str, str]:
    return {
        "renderer_type": "MUSICFORGE_RENDERER_TYPE",
        "fluidsynth_path": "MUSICFORGE_FLUIDSYNTH_PATH",
        "soundfont_path": "MUSICFORGE_SOUNDFONT_PATH",
        "sample_rate": "MUSICFORGE_AUDIO_SAMPLE_RATE",
        "gain": "MUSICFORGE_AUDIO_GAIN",
    }
