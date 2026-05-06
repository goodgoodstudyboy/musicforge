from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from song_agent.agent.pipeline import deterministic_compose
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate, load_quality_gate_config, save_quality_gate_config
from song_agent.projectio import write_json
from song_agent.stems import read_stem_manifest, render_stem_midis
from song_agent.schemas.song import QualityScores, SongQualityMeta, SongRequest


def request() -> SongRequest:
    return SongRequest.from_dict(
        {
            "title": "Gate Song",
            "language": "English",
            "style": "synth pop",
            "theme": "quality gate",
        }
    )


def write_plan(run_dir: Path, *, score: int = 88, warnings: list[str] | None = None) -> None:
    plan = deterministic_compose(request())
    quality = SongQualityMeta(
        summary="test quality",
        scores=QualityScores(
            overall=score,
            structure=score,
            melody=score,
            harmony=score,
            arrangement=score,
            lyric_fit=score,
        ),
        warnings=warnings or [],
    )
    plan = replace(plan, quality=quality)
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    (run_dir / "renders").mkdir(parents=True, exist_ok=True)
    (run_dir / "renders" / "song.mid").write_bytes(b"MThd")


def test_quality_gate_passes_good_song_plan(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=88)

    result = evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-06T00:00:00Z")

    assert result.status == "passed"
    assert result.score == 88
    assert all(check["passed"] for check in result.checks if check["required"])


def test_quality_gate_fails_low_scores(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=40)

    result = evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-06T00:00:00Z")

    assert result.status == "failed"
    assert result.score == 40
    assert any(check["name"] == "score_overall" and not check["passed"] for check in result.checks)


def test_quality_gate_reports_missing_plan(tmp_path: Path) -> None:
    result = evaluate_quality_gate(tmp_path / "missing", QualityGateConfig(), now="2026-05-06T00:00:00Z")

    assert result.status == "missing_plan"
    assert result.score is None


def test_quality_gate_warning_count_can_warn_or_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=90, warnings=["one", "two"])

    warning = evaluate_quality_gate(
        run_dir,
        QualityGateConfig(max_warnings=1, allow_warnings=True),
        now="2026-05-06T00:00:00Z",
    )
    failed = evaluate_quality_gate(
        run_dir,
        QualityGateConfig(max_warnings=5, allow_warnings=False),
        now="2026-05-06T00:00:00Z",
    )

    assert warning.status == "warning"
    assert failed.status == "failed"


def test_quality_gate_can_require_audio(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=90)
    missing_audio = evaluate_quality_gate(run_dir, QualityGateConfig(require_audio=True), now="2026-05-06T00:00:00Z")
    (run_dir / "renders" / "song.wav").write_bytes(b"RIFF")
    with_audio = evaluate_quality_gate(run_dir, QualityGateConfig(require_audio=True), now="2026-05-06T00:00:00Z")

    assert missing_audio.status == "failed"
    assert with_audio.status == "passed"


def test_quality_gate_require_stems_checks_manifest_and_midi_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=90)
    plan = deterministic_compose(request())
    quality = SongQualityMeta(
        summary="test quality",
        scores=QualityScores(overall=90, structure=90, melody=90, harmony=90, arrangement=90, lyric_fit=90),
    )
    plan = replace(plan, quality=quality)
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())

    missing_manifest = evaluate_quality_gate(run_dir, QualityGateConfig(require_stems=True), now="2026-05-06T00:00:00Z")
    render_stem_midis(plan, run_dir, "job-1", now="2026-05-06T00:00:00Z")
    with_stems = evaluate_quality_gate(run_dir, QualityGateConfig(require_stems=True), now="2026-05-06T00:00:00Z")
    manifest = read_stem_manifest(run_dir)
    assert manifest is not None
    midi_path = run_dir / next(stem.midi_path for stem in manifest.stems if stem.note_count > 0)
    midi_path.unlink()
    missing_midi = evaluate_quality_gate(run_dir, QualityGateConfig(require_stems=True), now="2026-05-06T00:00:00Z")

    assert missing_manifest.status == "failed"
    assert with_stems.status == "passed"
    assert missing_midi.status == "failed"
    stems_check = next(check for check in missing_midi.checks if check["name"] == "stems")
    assert stems_check["passed"] is False
    assert any(not stem["passed"] and "missing" in stem["message"] for stem in stems_check["stems"])


def test_quality_gate_require_stems_rejects_manifest_paths_outside_stems_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_plan(run_dir, score=90)
    plan = deterministic_compose(request())
    quality = SongQualityMeta(
        summary="test quality",
        scores=QualityScores(overall=90, structure=90, melody=90, harmony=90, arrangement=90, lyric_fit=90),
    )
    plan = replace(plan, quality=quality)
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    render_stem_midis(plan, run_dir, "job-1", now="2026-05-06T00:00:00Z")
    manifest = read_stem_manifest(run_dir)
    assert manifest is not None
    data = manifest.to_dict()
    data["stems"][0]["midi_path"] = "data/provider-snapshot.json"
    write_json(run_dir / "stems" / "manifest.json", data)

    result = evaluate_quality_gate(run_dir, QualityGateConfig(require_stems=True), now="2026-05-06T00:00:00Z")

    assert result.status == "failed"
    stems_check = next(check for check in result.checks if check["name"] == "stems")
    assert stems_check["passed"] is False
    assert any("outside the job stems directory" in stem["message"] for stem in stems_check["stems"])


def test_quality_gate_config_round_trips(tmp_path: Path) -> None:
    config = save_quality_gate_config(tmp_path, QualityGateConfig(min_overall=80, require_audio=True))
    loaded = load_quality_gate_config(tmp_path)

    assert config.min_overall == 80
    assert loaded.min_overall == 80
    assert loaded.require_audio is True
