from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.provider import ProviderConfig, ProviderOutputError
from song_agent.provider_edits import (
    ProviderEditPatch,
    apply_provider_edit_patch,
    create_provider_edit_preview,
    delete_provider_edit_preview,
    generate_provider_edit_candidates,
    generate_provider_edit_patch,
    preview_candidate_plan,
    preview_patch,
    preview_stale,
    read_provider_edit_preview,
    song_plan_hash,
)
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.schemas.song import SongRequest


def parent_plan():
    return deterministic_compose(
        SongRequest.from_dict(
            {
                "title": "Provider Edit Parent",
                "language": "English",
                "style": "synth pop",
                "theme": "provider edit",
            }
        )
    )


def test_provider_edit_patch_applies_without_mutating_parent() -> None:
    plan = parent_plan()
    before = plan.to_dict()
    patch = ProviderEditPatch.from_dict(
        {
            "schema_version": 1,
            "summary": "lift chorus",
            "operations": [
                {"op": "set_section_energy", "section_name": "chorus", "energy": 0.9},
                {"op": "set_section_chords", "section_name": "chorus", "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"]},
            ],
            "confidence": 0.8,
        }
    )

    result = apply_provider_edit_patch(plan, patch)

    assert plan.to_dict() == before
    assert result.plan.to_dict() != before
    assert result.summary["operation_count"] == 2
    chorus = next(section for section in result.plan.sections if section.name == "chorus")
    assert chorus.chords == ["Cmaj7", "Am7", "Fmaj7", "G7"]


def test_provider_edit_patch_rejects_unsafe_and_invalid_payloads() -> None:
    with pytest.raises(ValueError, match="Unsupported provider edit operation"):
        ProviderEditPatch.from_dict({"schema_version": 1, "summary": "bad", "operations": [{"op": "write_file"}]})
    with pytest.raises(ValueError, match="Unsupported chord names"):
        ProviderEditPatch.from_dict(
            {"schema_version": 1, "summary": "bad", "operations": [{"op": "set_section_chords", "section_name": "chorus", "chords": ["Hmaj7"]}]}
        )
    with pytest.raises(ValueError, match="secret"):
        ProviderEditPatch.from_dict(
            {"schema_version": 1, "summary": "bad", "operations": [{"op": "set_section_energy", "section_name": "chorus", "api_key": "sk-secret"}]}
        )


def test_mock_provider_generates_valid_edit_patch() -> None:
    plan = parent_plan()
    template = PromptTemplateStore().get_template("provider-edit-intent")

    patch, snapshot = generate_provider_edit_patch(
        parent_plan=plan,
        instruction="Make the final chorus more energetic but keep lyrics.",
        template=template,
        config=ProviderConfig(wire_api="mock", model="mock-main", api_key="sk-secret"),
    )

    assert patch.operations[0].op == "set_section_energy"
    assert snapshot["mode"] == "provider"
    assert snapshot["template_id"] == "provider-edit-intent"
    assert "sk-secret" not in str(snapshot)


def test_mock_provider_generates_multiple_edit_candidates() -> None:
    plan = parent_plan()
    template = PromptTemplateStore().get_template("provider-edit-candidates")

    patches, snapshot = generate_provider_edit_candidates(
        parent_plan=plan,
        instruction="Give me three stronger chorus options.",
        template=template,
        config=ProviderConfig(wire_api="mock", model="mock-main", api_key="sk-secret"),
        candidate_count=3,
    )

    assert len(patches) == 3
    assert {patch.summary for patch in patches} >= {"Lift chorus energy", "Brighten chorus harmony"}
    assert snapshot["operation"] == "provider_edit_candidates"
    assert snapshot["candidate_count"] == 3
    assert "sk-secret" not in str(snapshot)


def test_provider_edit_candidates_rejects_invalid_count() -> None:
    plan = parent_plan()
    template = PromptTemplateStore().get_template("provider-edit-candidates")

    with pytest.raises(ValueError, match="candidate_count"):
        generate_provider_edit_candidates(
            parent_plan=plan,
            instruction="too many",
            template=template,
            config=ProviderConfig(wire_api="mock", model="mock-main"),
            candidate_count=6,
        )


def test_invalid_mock_provider_patch_is_wrapped_as_provider_output_error() -> None:
    from song_agent.providers.mock import MockProviderClient

    plan = parent_plan()
    template = PromptTemplateStore().get_template("provider-edit-intent")
    with pytest.raises(ProviderOutputError):
        generate_provider_edit_patch(
            parent_plan=plan,
            instruction="bad",
            template=template,
            config=ProviderConfig(wire_api="mock", model="mock-main"),
            client=MockProviderClient(mode="invalid_schema"),
        )


def test_provider_edit_preview_files_are_safe_and_deletable(tmp_path: Path) -> None:
    plan = parent_plan()
    patch = ProviderEditPatch.from_dict(
        {
            "schema_version": 1,
            "summary": "lift chorus",
            "operations": [{"op": "set_section_energy", "section_name": "chorus", "energy": 0.9}],
        }
    )
    project_dir = tmp_path / ".musicforge" / "projects" / "preview-project"
    template = PromptTemplateStore().get_template("provider-edit-intent")

    preview = create_provider_edit_preview(
        project_dir=project_dir,
        project_id="preview-project",
        parent_version_id="v001",
        parent_job_id="parent-job",
        parent_plan=plan,
        instruction="lift chorus",
        template=template,
        patch=patch,
        now="2026-05-07T00:00:00Z",
    )

    assert preview.preview_id == "preview-001"
    assert preview.source["song_plan_sha256"] == song_plan_hash(plan)
    assert preview_stale(preview, plan) is False
    assert read_provider_edit_preview(project_dir, "preview-001").status == "ready"
    assert preview_candidate_plan(project_dir, "preview-001").title == plan.title
    assert preview_patch(project_dir, "preview-001").summary == "lift chorus"
    with pytest.raises(ValueError, match="Invalid preview id"):
        read_provider_edit_preview(project_dir, "../bad")

    delete_provider_edit_preview(project_dir, "preview-001")
    assert not (project_dir / "edit-previews" / "preview-001").exists()
