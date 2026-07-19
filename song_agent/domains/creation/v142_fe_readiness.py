# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from song_agent.domains.studio.project_quality import QualityGateResult as QualityGateResult
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stems import read_stem_manifest as read_stem_manifest, stem_audio_path as stem_audio_path, stem_manifest_stale as stem_manifest_stale, stem_midi_path as stem_midi_path

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

_context_pack_export_summary = _make_deferred_global('_context_pack_export_summary')
_drop_empty = _make_deferred_global('_drop_empty')
_ensure_within = _make_deferred_global('_ensure_within')
_reference_ref_export_summary = _make_deferred_global('_reference_ref_export_summary')
_safe_reference_id = _make_deferred_global('_safe_reference_id')
_sanitize_asset_metadata = _make_deferred_global('_sanitize_asset_metadata')
item = _make_deferred_global('item')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global _context_pack_export_summary, _drop_empty, _ensure_within, _reference_ref_export_summary, _safe_reference_id, _sanitize_asset_metadata, item
    global key
    _context_pack_export_summary = namespace.get('_context_pack_export_summary', _context_pack_export_summary)
    _drop_empty = namespace.get('_drop_empty', _drop_empty)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _reference_ref_export_summary = namespace.get('_reference_ref_export_summary', _reference_ref_export_summary)
    _safe_reference_id = namespace.get('_safe_reference_id', _safe_reference_id)
    _sanitize_asset_metadata = namespace.get('_sanitize_asset_metadata', _sanitize_asset_metadata)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


BLOCKED_ASSET_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "token",
}




def _write_reference_ref_summaries(
    *,
    run_dir: Path,
    export_dir: Path,
    version_id: str,
    project_export: DomainDocument | None,
    files: list[DomainDocument],
    enabled: bool,
) -> list[DomainDocument]:
    if not enabled:
        files.append({"kind": "reference_refs", "path": "references", "exists": False, "required": False, "skipped": "disabled"})
        return []
    refs = _final_version_reference_refs(run_dir, version_id, project_export)
    if not refs:
        files.append({"kind": "reference_refs", "path": "references", "exists": False, "required": False})
        return []
    refs_dir = export_dir / "references"
    _ensure_within(export_dir, refs_dir)
    refs_dir.mkdir(parents=True, exist_ok=True)
    written: list[DomainDocument] = []
    for ref in refs:
        reference_id = _safe_reference_id(str(ref.get("reference_id") or ""))
        summary = _reference_ref_export_summary(ref)
        target = refs_dir / f"{reference_id}.json"
        _ensure_within(export_dir, target)
        write_json(target, summary)
        record = {"kind": "reference_ref", "path": f"references/{reference_id}.json", "exists": True, "required": False, "size_bytes": target.stat().st_size}
        files.append(record)
        written.append(summary)
    return written

def _final_version_reference_refs(run_dir: Path, version_id: str, project_export: DomainDocument | None) -> list[DomainDocument]:
    refs_by_id: dict[str, DomainDocument] = {}
    snapshot_path = run_dir / "data" / "reference-refs.json"
    if snapshot_path.exists():
        _ensure_within(run_dir, snapshot_path)
        try:
            snapshot = read_json(snapshot_path)
        except (OSError, ValueError, TypeError):
            snapshot = {}
        for ref in snapshot.get("reference_refs", []) if isinstance(snapshot, dict) else []:
            if isinstance(ref, dict) and ref.get("reference_id"):
                refs_by_id[str(ref["reference_id"])] = _reference_ref_export_summary({**ref, "used_by_versions": [version_id]})
    if isinstance(project_export, dict):
        for ref in project_export.get("reference_refs", []):
            if not isinstance(ref, dict) or not ref.get("reference_id"):
                continue
            used_by_versions = _as_list(ref.get("used_by_versions"))
            if version_id not in used_by_versions and not ref.get("linked_to_project"):
                continue
            reference_id = str(ref["reference_id"])
            refs_by_id.setdefault(reference_id, _reference_ref_export_summary(ref))
    return [refs_by_id[key] for key in sorted(refs_by_id)]

def _final_version_context_pack(run_dir: Path, version_id: str, project_export: DomainDocument | None) -> DomainDocument:
    snapshot_path = run_dir / "data" / "context-pack.json"
    if snapshot_path.exists():
        _ensure_within(run_dir, snapshot_path)
        try:
            snapshot = read_json(snapshot_path)
        except (OSError, ValueError, TypeError):
            snapshot = {}
        if isinstance(snapshot, dict) and snapshot.get("pack_id"):
            return _context_pack_export_summary({**snapshot, "used_by_versions": [version_id]})
    if isinstance(project_export, dict):
        for pack in project_export.get("context_packs", []):
            if not isinstance(pack, dict) or not pack.get("pack_id"):
                continue
            used_by_versions = _as_list(pack.get("used_by_versions"))
            if version_id in used_by_versions:
                return _context_pack_export_summary(pack)
    return {}

def _final_version_edit_metadata(run_dir: Path, version_id: str, project_export: DomainDocument | None) -> DomainDocument:
    path = run_dir / "data" / "edit-metadata.json"
    if path.exists():
        try:
            return _edit_metadata_export_summary(read_json(path))
        except (OSError, ValueError, TypeError):
            pass
    if isinstance(project_export, dict):
        for version in project_export.get("versions", []):
            if isinstance(version, dict) and version.get("version_id") == version_id and isinstance(version.get("edit"), dict):
                return _edit_metadata_export_summary(version["edit"])
    return {}

def _edit_metadata_export_summary(metadata: DomainDocument) -> DomainDocument:
    summary = {
        "edit_source": metadata.get("edit_source"),
        "edit_type": metadata.get("edit_type"),
        "preview_id": metadata.get("preview_id"),
        "operation_count": metadata.get("operation_count"),
        "changed_sections": metadata.get("changed_sections") or [],
        "changed_tracks": metadata.get("changed_tracks") or [],
        "clip_inserts": metadata.get("clip_inserts") or [],
        "template_inserts": metadata.get("template_inserts") or [],
        "audition_summary": _as_document(metadata.get("audition_summary")),
        "review_edit": _as_document(metadata.get("review_edit")),
        "review_summary": _as_document(metadata.get("review_summary")),
        "review_task": _as_document(metadata.get("review_task")),
        "review_candidate": _as_document(metadata.get("review_candidate")),
        "review_candidate_source": _as_document(metadata.get("review_candidate_source")),
        "review_provider_patch": _as_document(metadata.get("review_provider_patch")),
        "review_decision": _as_document(metadata.get("review_decision")),
        "review_sprint": _as_document(metadata.get("review_sprint")),
        "review_sprint_recommendation": _as_document(metadata.get("review_sprint_recommendation")),
        "review_sprint_action_queue": _as_document(metadata.get("review_sprint_action_queue")),
        "review_judge": _as_document(metadata.get("review_judge")),
        "summary": _as_document(metadata.get("summary")),
        "structure": _as_document(metadata.get("structure")),
        "warnings": metadata.get("warnings") or [],
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_review_sprint_summary(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict):
        return {}
    try:
        from song_agent.domains.quality.review_sprints import review_sprint_project_rollup

        sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
        if not sprints:
            return {}
        return _drop_empty(_sanitize_asset_metadata(review_sprint_project_rollup(sprints)))
    except (OSError, ValueError, TypeError):
        return {}

def _final_review_sprint_recommendations(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict):
        return {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    summaries = [sprint.get("recommendation_summary", {}) for sprint in sprints if isinstance(sprint.get("recommendation_summary"), dict)]
    if not summaries:
        return {}
    latest = summaries[0]
    summary = {
        "latest_sprint_id": sprints[0].get("sprint_id") if sprints else None,
        "next_action": latest.get("next_action"),
        "ready_to_close": bool(latest.get("ready_to_close", False)),
        "open_recommendation_count": sum(int(item.get("open_recommendation_count") or 0) for item in summaries),
        "context_recommendation_count": sum(int(item.get("context_recommendation_count") or 0) for item in summaries),
        "top_recommendation": _as_document(latest.get("top_recommendation")),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_review_sprint_action_queues(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict):
        return {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    summaries = [sprint.get("action_queue_summary", {}) for sprint in sprints if isinstance(sprint.get("action_queue_summary"), dict)]
    if not summaries:
        return {}
    latest = summaries[0]
    summary = {
        "latest_sprint_id": sprints[0].get("sprint_id") if sprints else None,
        "latest_queue_id": latest.get("latest_queue_id"),
        "queue_count": sum(int(item.get("queue_count") or 0) for item in summaries),
        "completed_action_count": sum(int(item.get("completed_action_count") or 0) for item in summaries),
        "manual_required_count": sum(int(item.get("manual_required_count") or 0) for item in summaries),
        "failed_action_count": sum(int(item.get("failed_action_count") or 0) for item in summaries),
        "latest_status": latest.get("latest_status"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_review_metrics(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict):
        return {}
    project_summary = _as_document(project_export.get("review_metrics_summary"))
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    sprint_summaries = []
    for sprint in sprints:
        metrics_summary = sprint.get("metrics_summary", {})
        if not isinstance(metrics_summary, dict):
            continue
        if not metrics_summary.get("sprint_id") and sprint.get("sprint_id"):
            metrics_summary = {**metrics_summary, "sprint_id": sprint.get("sprint_id")}
        sprint_summaries.append(metrics_summary)
    latest_sprint_id = str(project_summary.get("latest_sprint_id") or "")
    latest = next((summary for summary in sprint_summaries if str(summary.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest is None:
        latest = sprint_summaries[0] if sprint_summaries else {}
    summary = {
        "latest_readiness": project_summary.get("latest_readiness") or latest.get("readiness"),
        "latest_sprint_id": latest_sprint_id or latest.get("sprint_id"),
        "sprint_count": project_summary.get("sprint_count") or len(sprints),
        "active_sprint_count": project_summary.get("active_sprint_count"),
        "completion_rate": latest.get("completion_rate"),
        "quality_delta": latest.get("quality_delta"),
        "provider_tokens": project_summary.get("total_provider_tokens") if project_summary else latest.get("provider_tokens"),
        "total_candidate_count": project_summary.get("total_candidate_count"),
        "total_applied_candidate_count": project_summary.get("total_applied_candidate_count"),
        "warnings": _as_list(latest.get("warnings")),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_review_judge(project_export: DomainDocument | None, edit_metadata: DomainDocument | None = None) -> DomainDocument:
    edit_judge = edit_metadata.get("review_judge") if isinstance(edit_metadata, dict) and isinstance(edit_metadata.get("review_judge"), dict) else {}
    project_summary = project_export.get("review_metrics_summary") if isinstance(project_export, dict) and isinstance(project_export.get("review_metrics_summary"), dict) else {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)] if isinstance(project_export, dict) else []
    judge_summaries = []
    for sprint in sprints:
        judge_summary = sprint.get("judge_summary", {})
        if not isinstance(judge_summary, dict):
            continue
        if not judge_summary.get("sprint_id") and sprint.get("sprint_id"):
            judge_summary = {**judge_summary, "sprint_id": sprint.get("sprint_id")}
        judge_summaries.append(judge_summary)
    latest_sprint_id = str(_as_document(project_summary).get("latest_sprint_id") or "")
    latest = next((summary for summary in judge_summaries if str(summary.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest is None:
        latest = judge_summaries[0] if judge_summaries else {}
    summary = {
        "latest_sprint_id": latest_sprint_id or latest.get("sprint_id"),
        "judged_task_count": sum(int(item.get("judged_task_count") or 0) for item in judge_summaries),
        "stale_judge_count": sum(int(item.get("stale_judge_count") or 0) for item in judge_summaries),
        "judge_provider_tokens": sum(int(item.get("judge_provider_tokens") or 0) for item in judge_summaries),
        "high_risk_candidate_count": sum(int(item.get("high_risk_candidate_count") or 0) for item in judge_summaries),
        "applied_matches_judge": _as_document(edit_judge).get("applied_matches_judge"),
        "manual_review_required": True if judge_summaries or edit_judge else None,
        "judge_recommended_candidate_id": _as_document(edit_judge).get("judge_recommended_candidate_id"),
        "top_overall": _as_document(edit_judge).get("top_overall"),
        "confidence": _as_document(edit_judge).get("confidence"),
        "judge_stale_at_apply": _as_document(edit_judge).get("judge_stale_at_apply"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_review_sprint_closeout(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict):
        return {}
    project_summary = _as_document(project_export.get("review_metrics_summary"))
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    if not sprints:
        return {}
    latest_sprint_id = str(project_summary.get("latest_sprint_id") or "")
    latest_sprint = next((sprint for sprint in sprints if str(sprint.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest_sprint is None:
        latest_sprint = sprints[0]
        latest_sprint_id = str(latest_sprint.get("sprint_id") or "")
    closeout_summaries = [sprint.get("closeout_summary", {}) for sprint in sprints if isinstance(sprint.get("closeout_summary"), dict)]
    signoff_summaries = [sprint.get("signoff_summary", {}) for sprint in sprints if isinstance(sprint.get("signoff_summary"), dict)]
    latest_closeout = _as_document(latest_sprint.get("closeout_summary"))
    latest_signoff = _as_document(latest_sprint.get("signoff_summary"))
    summary = {
        "latest_sprint_id": latest_sprint_id or None,
        "closed_sprint_count": len([sprint for sprint in sprints if sprint.get("status") == "closed"]),
        "signed_sprint_count": len([item for item in signoff_summaries if item.get("status") == "signed"]),
        "forced_close_count": len([item for item in signoff_summaries if item.get("forced")]) or len([item for item in closeout_summaries if item.get("forced")]),
        "latest_closeout_status": latest_closeout.get("status"),
        "latest_closeout_readiness": latest_closeout.get("readiness"),
        "blocker_count": latest_closeout.get("blocker_count"),
        "warning_count": latest_closeout.get("warning_count"),
        "selected_version_id": latest_signoff.get("selected_version_id") or latest_closeout.get("recommended_final_version_id"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))

def _final_delivery_qa(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("delivery_qa_summary"), dict):
        return {}
    summary = project_export["delivery_qa_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "readiness": summary.get("readiness"),
                "handoff_allowed": summary.get("handoff_allowed"),
                "artifact_count": summary.get("artifact_count"),
                "blocker_count": summary.get("blocker_count"),
                "warning_count": summary.get("warning_count"),
                "final_version_id": summary.get("final_version_id"),
                "zip_sha256": summary.get("zip_sha256"),
                "zip_matches_manifest": summary.get("zip_matches_manifest"),
            }
        )
    )

def _final_acceptance_fix_sprint(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_sprint_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_sprint_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "fix_sprint_id": summary.get("fix_sprint_id"),
                "item_count": summary.get("item_count"),
                "open_item_count": summary.get("open_item_count"),
                "linked_review_task_count": summary.get("linked_review_task_count"),
                "completed_review_task_count": summary.get("completed_review_task_count"),
                "recheck_suite_id": summary.get("recheck_suite_id"),
                "delta_status": summary.get("delta_status"),
                "closeout_status": summary.get("closeout_status"),
            }
        )
    )

def _final_acceptance_fix_plan(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_plan_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_plan_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "plan_id": summary.get("plan_id"),
                "planned_item_count": summary.get("planned_item_count"),
                "high_priority_count": summary.get("high_priority_count"),
                "kb_match_count": summary.get("kb_match_count"),
                "risk_warning_count": summary.get("risk_warning_count"),
                "created_fix_sprint_id": summary.get("created_fix_sprint_id"),
                "stale": summary.get("stale"),
            }
        )
    )

def _final_acceptance_fix_plan_review(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_plan_review_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_plan_review_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "readiness": summary.get("readiness"),
                "review_id": summary.get("review_id"),
                "plan_id": summary.get("plan_id"),
                "fix_sprint_id": summary.get("fix_sprint_id"),
                "plan_effectiveness_score": summary.get("plan_effectiveness_score"),
                "ranking_alignment_score": summary.get("ranking_alignment_score"),
                "kb_evidence_helpfulness": summary.get("kb_evidence_helpfulness"),
                "stale": summary.get("stale"),
            }
        )
    )

def _final_acceptance_kb(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_kb_summary"), dict):
        return {}
    summary = project_export["acceptance_kb_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "report_id": summary.get("report_id"),
                "entry_count": summary.get("entry_count"),
                "effective_count": summary.get("effective_count"),
                "ineffective_count": summary.get("ineffective_count"),
                "average_effectiveness_score": summary.get("average_effectiveness_score"),
                "top_recurring_issues": _as_list(summary.get("top_recurring_issues")),
                "warning_count": summary.get("warning_count"),
                "stale": summary.get("stale"),
            }
        )
    )

def _final_planning_rule_simulation(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_simulation_summary"), dict):
        return {}
    summary = project_export["planning_rule_simulation_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "simulation_id": summary.get("simulation_id"),
                "ruleset_id": summary.get("ruleset_id"),
                "review_count": summary.get("review_count"),
                "item_count": summary.get("item_count"),
                "alignment_delta": summary.get("alignment_delta"),
                "recommendation": summary.get("recommendation"),
                "stale": summary.get("stale"),
            }
        )
    )

def _final_planning_rule_governance(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_governance_summary"), dict):
        return {}
    summary = project_export["planning_rule_governance_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "active_version_id": summary.get("active_version_id"),
                "ruleset_id": summary.get("ruleset_id"),
                "promotion_id": summary.get("promotion_id"),
                "simulation_id": summary.get("simulation_id"),
                "recommendation": summary.get("recommendation"),
                "alignment_delta": summary.get("alignment_delta"),
                "stale": summary.get("stale"),
                "evidence_stale": summary.get("evidence_stale"),
            }
        )
    )

def _final_planning_rule_impact(project_export: DomainDocument | None) -> DomainDocument:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_impact_summary"), dict):
        return {}
    summary = project_export["planning_rule_impact_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "report_id": summary.get("report_id"),
                "active_version_id": summary.get("active_version_id"),
                "observed_plan_count": summary.get("observed_plan_count"),
                "observed_review_count": summary.get("observed_review_count"),
                "manual_review_count": summary.get("manual_review_count"),
                "synthetic_review_count": summary.get("synthetic_review_count"),
                "effectiveness_delta": summary.get("effectiveness_delta"),
                "ranking_alignment_delta": summary.get("ranking_alignment_delta"),
                "recommendation": summary.get("recommendation"),
                "rollback_recommended": summary.get("rollback_recommended"),
                "stale": summary.get("stale"),
            }
        )
    )
