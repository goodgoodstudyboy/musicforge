from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import json as json
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, score_song_plan as score_song_plan
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stems import read_stem_manifest as read_stem_manifest, stem_manifest_stale as stem_manifest_stale, stem_midi_path as stem_midi_path


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
    def from_dict(cls, data: DomainDocument) -> "QualityGateConfig":
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

    def to_dict(self) -> DomainDocument:
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
    checks: list[ImplementationDocument] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evaluated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    checks: list[ImplementationDocument] = []
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

    scores = quality.scores or score_song_plan(plan)
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
        if manifest is None:
            checks.append(_check("stems", False, "stem manifest exists and matches song-plan.json."))
        elif stem_manifest_stale(manifest, plan):
            checks.append(_check("stems", False, "stem manifest exists and matches song-plan.json."))
        else:
            stem_checks = _stem_midi_checks(run_dir, manifest, plan)
            checks.append(
                _check(
                    "stems",
                    all(check["passed"] for check in stem_checks),
                    "stem MIDI files exist and stay inside the job stems directory.",
                    stems=stem_checks,
                )
            )

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


def _check(name: str, passed: bool, message: str, *, required: bool = True, **extra: Any) -> ImplementationDocument:
    return {
        "name": name,
        "passed": passed,
        "required": required,
        "message": message,
        **extra,
    }


def _stem_midi_checks(run_dir: Path, manifest: Any, plan: SongPlan) -> list[ImplementationDocument]:
    expected_note_tracks = [
        {"track_name": track.name, "note_count": len(track.notes)}
        for track in plan.tracks
        if track.notes
    ]
    manifest_note_stems = [
        {"track_name": stem.track_name, "note_count": stem.note_count}
        for stem in manifest.stems
        if stem.note_count > 0
    ]
    coverage_passed = sorted(expected_note_tracks, key=_stem_track_key) == sorted(manifest_note_stems, key=_stem_track_key)
    checks: list[ImplementationDocument] = [
        {
            "stem_id": "__manifest_coverage__",
            "passed": coverage_passed,
            "path": "stems/manifest.json",
            "message": (
                f"stem manifest has {len(manifest_note_stems)} note-bearing stems "
                f"for {len(expected_note_tracks)} note-bearing SongPlan tracks."
            ),
            "expected_note_tracks": expected_note_tracks,
            "manifest_note_stems": manifest_note_stems,
        }
    ]
    for stem in manifest.stems:
        if stem.note_count <= 0:
            checks.append(
                {
                    "stem_id": stem.stem_id,
                    "passed": True,
                    "path": stem.midi_path,
                    "message": "Track has no notes; stem MIDI is not required.",
                }
            )
            continue
        try:
            path = stem_midi_path(run_dir, manifest, stem.stem_id)
            exists = path.exists()
            checks.append(
                {
                    "stem_id": stem.stem_id,
                    "passed": exists,
                    "path": stem.midi_path,
                    "message": "stem MIDI exists." if exists else "stem MIDI is missing.",
                }
            )
        except (FileNotFoundError, ValueError) as exc:
            checks.append(
                {
                    "stem_id": stem.stem_id,
                    "passed": False,
                    "path": stem.midi_path,
                    "message": str(exc),
                }
            )
    return checks


def _stem_track_key(item: ImplementationDocument) -> tuple[str, int]:
    return (str(item["track_name"]), int(item["note_count"]))


def _score(value: Any, field_name: str) -> int:
    score = int(value)
    if score < 0 or score > 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")
    return score
