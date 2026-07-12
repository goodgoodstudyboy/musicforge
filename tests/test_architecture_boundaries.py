from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from song_agent.application.audio_campaigns.release_coverage import audio_campaign_release_track_coverage
from song_agent.application.generation.service import generate_request as application_generate_request
from song_agent.application.jobs.model import JobState as ApplicationJobState
from song_agent.architecture_guardrails import (
    _dynamic_internal_import_target,
    _new_cycles,
    build_architecture_snapshot,
    evaluate_architecture,
)
from song_agent.cli import generate_request as cli_generate_request
from song_agent.server import JobState as ServerJobState


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_boundaries_match_baseline() -> None:
    report = evaluate_architecture(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["blockers"] == []
    assert report["snapshot"]["boundary_violations"] == []


def test_production_import_cycles_do_not_include_interfaces() -> None:
    snapshot = build_architecture_snapshot(ROOT)
    interface_modules = {"song_agent.cli", "song_agent.server", "song_agent.webui"}

    assert all(interface_modules.isdisjoint(cycle) for cycle in snapshot["cycles"])
    assert snapshot["dynamic_internal_imports"] == []


def test_cycle_ratchet_allows_legacy_cycles_to_shrink_but_not_merge() -> None:
    allowed = [["domain.a", "domain.b", "domain.c"], ["domain.x", "domain.y"]]

    assert _new_cycles(allowed, [["domain.a", "domain.b"]]) == []
    assert _new_cycles(allowed, [["domain.a", "domain.x"]]) == [["domain.a", "domain.x"]]


def test_dynamic_internal_import_detection_cannot_be_used_to_hide_dependency() -> None:
    builtin_call = ast.parse('__import__("song_agent.server")').body[0].value
    importlib_call = ast.parse('importlib.import_module("song_agent.cli")').body[0].value
    stdlib_call = ast.parse('__import__("hashlib")').body[0].value

    assert _dynamic_internal_import_target(builtin_call) == "song_agent.server"
    assert _dynamic_internal_import_target(importlib_call) == "song_agent.cli"
    assert _dynamic_internal_import_target(stdlib_call) is None


def test_compatibility_exports_forward_to_application_layer() -> None:
    assert ServerJobState is ApplicationJobState
    assert cli_generate_request is application_generate_request


def test_release_audio_coverage_service_preserves_track_identity_semantics() -> None:
    tracks = [
        SimpleNamespace(
            disc_number=1,
            track_number=1,
            track_id="track-001",
            title="Current Track",
            project_id="project-001",
            version_id="version-001",
            final_export_hash="a" * 64,
        ),
        SimpleNamespace(
            disc_number=1,
            track_number=2,
            track_id="track-002",
            title="Missing Track",
            project_id="project-002",
            version_id="version-002",
            final_export_hash="b" * 64,
        ),
    ]
    case_index = {
        "cases": [
            {
                "project_id": "project-001",
                "version_id": "version-001",
                "final_export_hash": "a" * 64,
            }
        ]
    }

    result = audio_campaign_release_track_coverage(tracks, case_index)

    assert result["status"] == "failed"
    assert result["matched_track_count"] == 1
    assert result["track_count"] == 2
    assert [row["track_id"] for row in result["missing_tracks"]] == ["track-002"]
