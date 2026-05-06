from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.music_quality import analyze_song_quality
from song_agent.projectio import read_json, write_json
from song_agent.schemas.song import SongPlan
from song_agent.stems import read_stem_manifest, stem_manifest_stale


GATE_STATUSES = {"passed", "warning", "failed", "missing_plan", "error"}


@dataclass
class QualityGateConfig:
    min_overall: int = 75
    min_structure: int = 65
    min_melody: int = 65
    min_harmony: int = 60
    min_arrangement: int = 60
    allow_warnings: bool = True
    max_warnings: int = 5
    require_audio: bool = False
    require_stems: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityGateConfig":
        return cls(
            min_overall=_score(data.get("min_overall", 75), "min_overall"),
            min_structure=_score(data.get("min_structure", 65), "min_structure"),
            min_melody=_score(data.get("min_melody", 65), "min_melody"),
            min_harmony=_score(data.get("min_harmony", 60), "min_harmony"),
            min_arrangement=_score(data.get("min_arrangement", 60), "min_arrangement"),
            allow_warnings=bool(data.get("allow_warnings", True)),
            max_warnings=max(0, int(data.get("max_warnings", 5) or 0)),
            require_audio=bool(data.get("require_audio", False)),
            require_stems=bool(data.get("require_stems", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_overall": self.min_overall,
            "min_structure": self.min_structure,
            "min_melody": self.min_melody,
            "min_harmony": self.min_harmony,
            "min_arrangement": self.min_arrangement,
            "allow_warnings": self.allow_warnings,
            "max_warnings": self.max_warnings,
            "require_audio": self.require_audio,
            "require_stems": self.require_stems,
        }


@dataclass
class QualityGateResult:
    status: str
    score: int | None
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evaluated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "checks": self.checks,
            "warnings": self.warnings,
            "evaluated_at": self.evaluated_at,
        }


def load_quality_gate_config(project_dir: Path) -> QualityGateConfig:
    path = project_dir / "quality-gate.json"
    if not path.exists():
        return QualityGateConfig()
    return QualityGateConfig.from_dict(read_json(path))


def save_quality_gate_config(project_dir: Path, config: QualityGateConfig) -> QualityGateConfig:
    write_json(project_dir / "quality-gate.json", config.to_dict())
    return config


def evaluate_quality_gate(run_dir: Path, config: QualityGateConfig, *, now: str) -> QualityGateResult:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    plan_path = run_dir / "data" / "song-plan.json"
    if not plan_path.exists():
        return QualityGateResult(
            status="missing_plan",
            score=None,
            checks=[_check("song_plan", False, "song-plan.json is missing.")],
            warnings=[],
            evaluated_at=now,
        )
    checks.append(_check("song_plan", True, "song-plan.json exists."))

    try:
        plan = SongPlan.from_dict(read_json(plan_path))
        quality = plan.quality or analyze_song_quality(plan)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return QualityGateResult(
            status="error",
            score=None,
            checks=[*checks, _check("song_plan_parse", False, str(exc))],
            warnings=[],
            evaluated_at=now,
        )

    scores = quality.scores or analyze_song_quality(plan).scores
    score_checks = [
        ("overall", scores.overall, config.min_overall),
        ("structure", scores.structure, config.min_structure),
        ("melody", scores.melody, config.min_melody),
        ("harmony", scores.harmony, config.min_harmony),
        ("arrangement", scores.arrangement, config.min_arrangement),
    ]
    for name, value, minimum in score_checks:
        checks.append(_check(f"score_{name}", value >= minimum, f"{name} {value} >= {minimum}", value=value, minimum=minimum))

    warnings.extend(list(quality.warnings or []))
    warning_count_ok = len(warnings) <= config.max_warnings
    checks.append(
        _check(
            "warning_count",
            warning_count_ok,
            f"{len(warnings)} warnings <= {config.max_warnings}",
            required=False,
            value=len(warnings),
            maximum=config.max_warnings,
        )
    )

    audio_path = run_dir / "renders" / "song.wav"
    if config.require_audio:
        checks.append(_check("audio", audio_path.exists(), "song.wav exists."))

    if config.require_stems:
        manifest = read_stem_manifest(run_dir)
        stems_ok = manifest is not None and not stem_manifest_stale(manifest, plan)
        checks.append(_check("stems", stems_ok, "stem manifest exists and matches song-plan.json."))

    failed_required = any(not check["passed"] for check in checks if check["required"])
    if failed_required:
        status = "failed"
    elif not config.allow_warnings and warnings:
        status = "failed"
    elif not warning_count_ok:
        status = "warning"
    else:
        status = "passed"

    return QualityGateResult(
        status=status,
        score=scores.overall,
        checks=checks,
        warnings=warnings,
        evaluated_at=now,
    )


def _check(name: str, passed: bool, message: str, *, required: bool = True, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "required": required,
        "message": message,
        **extra,
    }


def _score(value: Any, field_name: str) -> int:
    score = int(value)
    if score < 0 or score > 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")
    return score
