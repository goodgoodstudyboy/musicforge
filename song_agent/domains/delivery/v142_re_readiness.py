# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsStore as AcceptanceAnalyticsStore, AnalyticsScope as AnalyticsScope, write_acceptance_analytics_summary as write_acceptance_analytics_summary
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixSprintStore as AcceptanceFixSprintStore, write_acceptance_fix_sprints_summary as write_acceptance_fix_sprints_summary
from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlanningStore as AcceptanceFixPlanningStore, write_acceptance_fix_plan_summary as write_acceptance_fix_plan_summary
from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore as AcceptanceFixPlanReviewStore, write_acceptance_fix_plan_review_summary as write_acceptance_fix_plan_review_summary
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseStore as AcceptanceKnowledgeBaseStore, write_acceptance_kb_summary as write_acceptance_kb_summary
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationStore as PlanningRuleSimulationStore, write_planning_simulation_summary as write_planning_simulation_summary
from song_agent.domains.creation.planning_rule_governance import PlanningRuleGovernanceStore as PlanningRuleGovernanceStore, write_planning_rule_governance_summary as write_planning_rule_governance_summary
from song_agent.domains.creation.planning_rule_impact import PlanningRuleImpactStore as PlanningRuleImpactStore, write_planning_rule_impact_summary as write_planning_rule_impact_summary
from song_agent.domains.studio.projectio import slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio import read_release_audio_qa as read_release_audio_qa, release_audio_summary as release_audio_summary
from song_agent.domains.quality.audio_review_evidence import export_audio_reviews as export_audio_reviews
from song_agent.domains.quality.audio_revision import export_audio_revisions as export_audio_revisions
from song_agent.domains.quality.mastering_qa import export_mastering as export_mastering, selected_mastering_track_sources as selected_mastering_track_sources
from song_agent.domains.quality.audio_encoding import export_encoded_audio_summary as export_encoded_audio_summary
from song_agent.domains.creation.encoded_audio_acceptance import export_encoded_audio_acceptance as export_encoded_audio_acceptance
from song_agent.domains.delivery.format_decisions import FormatDecisionStore as FormatDecisionStore
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore as RightsClearanceStore
from song_agent.domains.delivery.release_metadata import attach_metadata_export_to_manifest as attach_metadata_export_to_manifest, export_release_metadata_files as export_release_metadata_files, metadata_qa_allows_export as metadata_qa_allows_export, read_release_metadata as read_release_metadata, read_release_metadata_qa as read_release_metadata_qa, release_metadata_source_hash as release_metadata_source_hash
from song_agent.domains.delivery.release_qa import release_qa_allows_export as release_qa_allows_export, release_qa_summary as release_qa_summary, release_source_hash as release_source_hash
from song_agent.domains.delivery.release_export_manifest import RELEASE_EXPORT_BLOCKED_KEYS as RELEASE_EXPORT_BLOCKED_KEYS, read_release_export_manifest as read_release_export_manifest
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseDocument as ReleaseDocument, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

ReleaseExportError = _make_deferred_global('ReleaseExportError')
key = _make_deferred_global('key')
part = _make_deferred_global('part')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseExportError, key, part, value
    ReleaseExportError = namespace.get('ReleaseExportError', ReleaseExportError)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


RELEASE_EXPORT_SCHEMA_VERSION = 1
CORE_COPY_FILES = {"manifest.json", "README.txt", "project-export.json", "song-plan.json", "song.mid"}
OPTIONAL_COPY_FILES = {"song.wav", "audio-artifact.json", "quality-report.json", "validator-report.json", "run-summary.json", "mix-state.json", "mix-patch.json"}
OPTIONAL_COPY_PREFIXES = ("stems/", "assets/", "references/")
SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}




def _release_signoff_hash_payload(signoff_public: DomainDocument) -> DomainDocument:
    return {key: value for key, value in signoff_public.items() if key not in SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}

def _release_acceptance_analytics_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        analytics_store = AcceptanceAnalyticsStore(release_store=release_store, project_store=release_store.project_store)
        report = analytics_store.refresh(AnalyticsScope.from_values(scope_type="release", release_id=release_id))
    except Exception:
        summary = {"status": "missing", "readiness_status": "missing"}
        write_json(export_dir / "acceptance-analytics-summary.json", summary)
        return summary
    return write_acceptance_analytics_summary(export_dir / "acceptance-analytics-summary.json", report)

def _release_acceptance_fix_sprint_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = AcceptanceFixSprintStore(project_store=release_store.project_store)
        return write_acceptance_fix_sprints_summary(export_dir / "acceptance-fix-sprints-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "acceptance-fix-sprints-summary.json", summary)
        return summary

def _release_acceptance_fix_plan_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = AcceptanceFixPlanningStore(project_store=release_store.project_store)
        return write_acceptance_fix_plan_summary(export_dir / "acceptance-fix-plan-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "acceptance-fix-plan-summary.json", summary)
        return summary

def _release_acceptance_fix_plan_review_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = AcceptanceFixPlanReviewStore(project_store=release_store.project_store)
        return write_acceptance_fix_plan_review_summary(export_dir / "acceptance-fix-plan-review-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "acceptance-fix-plan-review-summary.json", summary)
        return summary

def _release_acceptance_kb_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = AcceptanceKnowledgeBaseStore(project_store=release_store.project_store)
        return write_acceptance_kb_summary(export_dir / "acceptance-kb-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "acceptance-kb-summary.json", summary)
        return summary

def _release_planning_rule_simulation_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = PlanningRuleSimulationStore(project_store=release_store.project_store)
        return write_planning_simulation_summary(export_dir / "planning-rule-simulation-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "planning-rule-simulation-summary.json", summary)
        return summary

def _release_planning_rule_governance_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = PlanningRuleGovernanceStore(project_store=release_store.project_store)
        return write_planning_rule_governance_summary(export_dir / "planning-rule-governance-summary.json", store)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "planning-rule-governance-summary.json", summary)
        return summary

def _release_planning_rule_impact_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        store = PlanningRuleImpactStore(project_store=release_store.project_store)
        return write_planning_rule_impact_summary(export_dir / "planning-rule-impact-summary.json", store, release_id=release_id)
    except Exception:
        summary = {"status": "missing"}
        write_json(export_dir / "planning-rule-impact-summary.json", summary)
        return summary

def _release_audio_qa_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    report = read_release_audio_qa(release_store, release_id, default={})
    summary = release_audio_summary(report)
    write_json(export_dir / "audio-summary.json", summary)
    return summary

def _release_audio_reviews_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return export_audio_reviews(release_store, release_id, export_dir, project_store=release_store.project_store)
    except Exception:
        summary = {"status": "missing", "track_count": 0, "manual_accepted_track_count": 0, "missing_track_ids": []}
        target = export_dir / "audio-reviews"
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "summary.json", summary)
        return summary

def _release_audio_revisions_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return export_audio_revisions(release_store, release_id, export_dir, project_store=release_store.project_store)
    except Exception:
        summary = {"status": "missing", "session_count": 0, "open_issue_count": 0}
        target = export_dir / "audio-revisions"
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "summary.json", summary)
        return summary

def _release_mastering_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return export_mastering(release_store, release_id, export_dir, project_store=release_store.project_store)
    except Exception:
        summary = {"status": "missing", "track_count": 0}
        target = export_dir / "mastering"
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "summary.json", summary)
        return summary

def _release_encoded_audio_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return export_encoded_audio_summary(release_store, release_id, export_dir)
    except Exception:
        summary = {"status": "missing", "profile_count": 0}
        write_json(export_dir / "encoded-audio-summary.json", summary)
        return summary

def _release_encoded_audio_acceptance_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return export_encoded_audio_acceptance(release_store, release_id, export_dir, project_store=release_store.project_store)
    except Exception:
        summary = {"status": "missing", "required_profiles": [], "track_count": 0}
        write_json(export_dir / "encoded-audio-acceptance-summary.json", summary)
        return summary

def _release_format_decision_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return FormatDecisionStore(release_store, project_store=release_store.project_store).export_release(release_id, export_dir)
    except Exception:
        summary = {"status": "missing", "session_id": None}
        target = export_dir / "format-decision"
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "decision-report.json", summary)
        return summary

def _release_rights_clearance_summary(release_store: ReleaseStore, release_id: str, export_dir: Path) -> DomainDocument:
    try:
        return RightsClearanceStore(release_store).export_release(release_id, export_dir)
    except Exception:
        summary = {"status": "missing", "summary_path": "rights/summary.json", "track_count": 0}
        target = export_dir / "rights"
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "summary.json", summary)
        return summary

def _validate_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or normalized.startswith("/") or normalized.startswith("\\") or normalized.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise ValueError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseExportError("Refusing to operate outside release export boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
