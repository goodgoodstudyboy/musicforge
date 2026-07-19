# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field, replace as replace
from pathlib import Path as Path
from song_agent.domains.quality.candidate_scoring import score_provider_edit_candidate as score_provider_edit_candidate
from song_agent.domains.creation.edits import EditIntent as EditIntent, EditedSongPlanResult as EditedSongPlanResult, apply_edit_intent as apply_edit_intent, validate_edit_intent as validate_edit_intent
from song_agent.domains.studio.editor_audition import EditorAuditionManifest as EditorAuditionManifest
from song_agent.domains.creation.music_quality import attach_quality as attach_quality
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig
from song_agent.domains.creation.provider_edits import ProviderEditPatch as ProviderEditPatch, apply_provider_edit_patch as apply_provider_edit_patch, generate_provider_edit_candidates as generate_provider_edit_candidates, provider_patch_to_intents as provider_patch_to_intents
from song_agent.domains.studio.prompt_templates import PromptTemplate as PromptTemplate
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.quality.review_edits import build_review_edit as build_review_edit
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan
from song_agent.domains.studio.song_editor import song_plan_hash as song_plan_hash

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

ReviewCandidate = _make_deferred_global('ReviewCandidate')
ReviewTask = _make_deferred_global('ReviewTask')
_candidate_source = _make_deferred_global('_candidate_source')
_candidate_warnings = _make_deferred_global('_candidate_warnings')
_clamp = _make_deferred_global('_clamp')
_ensure_task_open_for_generation = _make_deferred_global('_ensure_task_open_for_generation')
_judge_summary_for_decision = _make_deferred_global('_judge_summary_for_decision')
_provider_candidate_source = _make_deferred_global('_provider_candidate_source')
_provider_snapshot_for_candidate = _make_deferred_global('_provider_snapshot_for_candidate')
_usage_int = _make_deferred_global('_usage_int')
_validator = _make_deferred_global('_validator')
apply_candidate_intents = _make_deferred_global('apply_candidate_intents')
candidate_intents_for_strategy = _make_deferred_global('candidate_intents_for_strategy')
candidate_summary = _make_deferred_global('candidate_summary')
ensure_task_current = _make_deferred_global('ensure_task_current')
intent = _make_deferred_global('intent')
item = _make_deferred_global('item')
op = _make_deferred_global('op')
score_review_candidate = _make_deferred_global('score_review_candidate')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReviewCandidate, ReviewTask, _candidate_source, _candidate_warnings, _clamp, _ensure_task_open_for_generation, _judge_summary_for_decision
    global _provider_candidate_source, _provider_snapshot_for_candidate, _usage_int, _validator, apply_candidate_intents, candidate_intents_for_strategy, candidate_summary, ensure_task_current
    global intent, item, op, score_review_candidate
    ReviewCandidate = namespace.get('ReviewCandidate', ReviewCandidate)
    ReviewTask = namespace.get('ReviewTask', ReviewTask)
    _candidate_source = namespace.get('_candidate_source', _candidate_source)
    _candidate_warnings = namespace.get('_candidate_warnings', _candidate_warnings)
    _clamp = namespace.get('_clamp', _clamp)
    _ensure_task_open_for_generation = namespace.get('_ensure_task_open_for_generation', _ensure_task_open_for_generation)
    _judge_summary_for_decision = namespace.get('_judge_summary_for_decision', _judge_summary_for_decision)
    _provider_candidate_source = namespace.get('_provider_candidate_source', _provider_candidate_source)
    _provider_snapshot_for_candidate = namespace.get('_provider_snapshot_for_candidate', _provider_snapshot_for_candidate)
    _usage_int = namespace.get('_usage_int', _usage_int)
    _validator = namespace.get('_validator', _validator)
    apply_candidate_intents = namespace.get('apply_candidate_intents', apply_candidate_intents)
    candidate_intents_for_strategy = namespace.get('candidate_intents_for_strategy', candidate_intents_for_strategy)
    candidate_summary = namespace.get('candidate_summary', candidate_summary)
    ensure_task_current = namespace.get('ensure_task_current', ensure_task_current)
    intent = namespace.get('intent', intent)
    item = namespace.get('item', item)
    op = namespace.get('op', op)
    score_review_candidate = namespace.get('score_review_candidate', score_review_candidate)
    _bind_deferred_defaults(namespace)


REVIEW_TASK_SCHEMA_VERSION = 1
REVIEW_CANDIDATE_SCHEMA_VERSION = 1
REVIEW_DECISION_REPORT_SCHEMA_VERSION = 1
TASK_STATUSES = {"open", "candidate_ready", "applied", "resolved", "needs_more_work", "archived", "stale"}
CANDIDATE_STATUSES = {"queued", "ready", "failed", "applied", "stale", "deleted"}
STRATEGIES = ("conservative", "balanced", "bold")
PROVIDER_STRATEGY = "provider"
TERMINAL_TASK_STATUSES = {"resolved", "archived", "stale", "needs_more_work"}
FIX_MARKERS = {"fix", "issue", "drop"}
PRESERVE_MARKERS = {"keep", "hook"}
_STORE_LOCKS: dict[str, threading.RLock] = {}




def build_local_review_candidates(task: ReviewTask, parent_plan: SongPlan, *, strategies: list[str] | None = None) -> list[tuple[ReviewCandidate, SongPlan | None, DomainDocument, DomainDocument]]:
    _ensure_task_open_for_generation(task)
    strategies = [str(item or "").strip() for item in (strategies or list(STRATEGIES))]
    strategies = [item for item in strategies if item in STRATEGIES]
    if not strategies:
        strategies = list(STRATEGIES)
    result: list[tuple[ReviewCandidate, SongPlan | None, DomainDocument]] = []
    seen: set[str] = set()
    for strategy in strategies[:4]:
        try:
            intents = candidate_intents_for_strategy(task, strategy)
            candidate_plan = apply_candidate_intents(parent_plan, intents).plan
            candidate_plan.validate()
            validator = _validator("passed")
            scores = score_review_candidate(task, candidate_plan, intents, strategy, parent_plan)
            candidate = ReviewCandidate.from_dict(
                {
                    "schema_version": REVIEW_CANDIDATE_SCHEMA_VERSION,
                    "candidate_id": "revcand-001",
                    "task_id": task.task_id,
                    "project_id": task.project_id,
                    "parent_version_id": task.parent_version_id,
                    "candidate_type": "local_review_intents",
                    "strategy": strategy,
                    "status": "ready",
                    "summary": candidate_summary(task, strategy, intents),
                    "source": _candidate_source(task),
                    "intents": [intent.to_dict() for intent in intents],
                    "validator": validator,
                    "scores": scores,
                    "warnings": _candidate_warnings(task, strategy),
                    "hashes": {"parent_plan_hash": task.hashes.get("parent_plan_hash") or song_plan_hash(parent_plan)},
                }
            )
            key = song_plan_hash(candidate_plan)
            if key in seen:
                continue
            seen.add(key)
            result.append((candidate, candidate_plan, validator, {"scores": scores, "summary": candidate.summary}))
        except Exception as exc:
            candidate = ReviewCandidate.from_dict(
                {
                    "schema_version": REVIEW_CANDIDATE_SCHEMA_VERSION,
                    "candidate_id": "revcand-001",
                    "task_id": task.task_id,
                    "project_id": task.project_id,
                    "parent_version_id": task.parent_version_id,
                    "candidate_type": "local_review_intents",
                    "strategy": strategy,
                    "status": "failed",
                    "summary": f"{strategy} candidate failed.",
                    "source": _candidate_source(task),
                    "validator": _validator("failed", errors=[str(exc)]),
                    "scores": {"combined": 0, "review_fit": 0, "target_precision": 0, "quality_delta": 0, "quality_overall": 0, "novelty": 0, "safety": 0},
                    "error": str(exc),
                    "hashes": {"parent_plan_hash": task.hashes.get("parent_plan_hash") or song_plan_hash(parent_plan)},
                }
            )
            result.append((candidate, None, candidate.validator, {"error": str(exc)}))
    return result

def build_provider_review_candidates(
    *,
    task: ReviewTask,
    parent_plan: SongPlan,
    template: PromptTemplate,
    config: ProviderConfig,
    candidate_count: int = 3,
    local_candidates: list[ReviewCandidate] | None = None,
    asset_references: list[DomainDocument] | None = None,
    reference_references: list[DomainDocument] | None = None,
    client: object | None = None,
) -> tuple[list[tuple[ReviewCandidate, SongPlan | None, DomainDocument, DomainDocument]], DomainDocument, str]:
    _ensure_task_open_for_generation(task)
    ensure_task_current(task, parent_plan)
    instruction = provider_review_candidate_instruction(task, local_candidates or [])
    patches, provider_snapshot = generate_provider_edit_candidates(
        parent_plan=parent_plan,
        instruction=instruction,
        template=template,
        config=config,
        candidate_count=candidate_count,
        asset_references=asset_references,
        reference_references=reference_references,
        client=client,
    )
    snapshot = _provider_snapshot_for_candidate(provider_snapshot)
    snapshot["operation"] = "provider_review_candidates"
    snapshot["provider_run_id"] = f"{task.task_id}:{template.template_id}:{now_iso()}"
    generated: list[tuple[ReviewCandidate, SongPlan | None, DomainDocument]] = []
    for index, patch in enumerate(patches, start=1):
        try:
            result = apply_provider_edit_patch(parent_plan, patch)
            result.plan.validate()
            intents = provider_patch_to_intents(patch, parent_plan)
            validator = _validator(
                "passed",
                warnings=[
                    "Provider candidate was converted to local EditIntent operations before scoring and storage.",
                    *list(result.warnings),
                ],
            )
            scores = score_provider_review_candidate(
                task=task,
                parent_plan=parent_plan,
                candidate_plan=result.plan,
                patch=patch,
                intents=intents,
                validator_status="passed",
            )
            warnings = sorted({str(item) for item in [*patch.warnings, *result.warnings, *scores.get("warnings", [])] if str(item)})
            candidate = ReviewCandidate.from_dict(
                {
                    "schema_version": REVIEW_CANDIDATE_SCHEMA_VERSION,
                    "candidate_id": "revcand-001",
                    "task_id": task.task_id,
                    "project_id": task.project_id,
                    "parent_version_id": task.parent_version_id,
                    "candidate_type": "provider_review_patch",
                    "strategy": PROVIDER_STRATEGY,
                    "status": "ready",
                    "summary": sanitize_sensitive_text(patch.summary)[:800],
                    "source": _provider_candidate_source(task, snapshot, template.template_id, index),
                    "intents": [intent.to_dict() for intent in intents],
                    "patch": patch.to_dict(),
                    "validator": validator,
                    "scores": scores,
                    "warnings": warnings,
                    "hashes": {"parent_plan_hash": task.hashes.get("parent_plan_hash") or song_plan_hash(parent_plan)},
                }
            )
            generated.append((candidate, result.plan, validator, {"scores": scores, "summary": candidate.summary, "provider_snapshot": snapshot}))
        except Exception as exc:
            validator = _validator("failed", errors=[str(exc)])
            scores = {"combined": 0, "review_fit": 0, "target_precision": 0, "quality_delta": 0, "quality_overall": 0, "novelty": 0, "safety": 0, "risk": 100, "warnings": ["provider_candidate_failed"]}
            candidate = ReviewCandidate.from_dict(
                {
                    "schema_version": REVIEW_CANDIDATE_SCHEMA_VERSION,
                    "candidate_id": "revcand-001",
                    "task_id": task.task_id,
                    "project_id": task.project_id,
                    "parent_version_id": task.parent_version_id,
                    "candidate_type": "provider_review_patch",
                    "strategy": PROVIDER_STRATEGY,
                    "status": "failed",
                    "summary": sanitize_sensitive_text(patch.summary if isinstance(patch, ProviderEditPatch) else "Provider review candidate failed.")[:800],
                    "source": _provider_candidate_source(task, snapshot, template.template_id, index),
                    "patch": patch.to_dict() if isinstance(patch, ProviderEditPatch) else None,
                    "validator": validator,
                    "scores": scores,
                    "warnings": ["Provider candidate failed local validation."],
                    "error": str(exc),
                    "hashes": {"parent_plan_hash": task.hashes.get("parent_plan_hash") or song_plan_hash(parent_plan)},
                }
            )
            generated.append((candidate, None, validator, {"error": str(exc), "provider_snapshot": snapshot}))
    return generated, snapshot, instruction

def provider_review_candidate_instruction(task: ReviewTask, local_candidates: list[ReviewCandidate] | None = None) -> str:
    local_items = []
    for candidate in (local_candidates or [])[:6]:
        local_items.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy": candidate.strategy,
                "status": candidate.status,
                "rank": candidate.rank,
                "score": candidate.scores.get("combined"),
                "summary": candidate.summary,
                "warnings": list(candidate.warnings[:4]),
            }
        )
    context = sanitize_metadata(
        {
            "review_task": {
                "task_id": task.task_id,
                "title": task.title,
                "summary": task.summary,
                "priority": task.priority,
                "target": {
                    "section_name": task.target.get("section_name"),
                    "track_name": task.target.get("track_name"),
                    "role": task.target.get("role"),
                    "marker_kind": task.target.get("marker_kind"),
                    "global_marker_beat": task.target.get("global_marker_beat"),
                },
                "review_snapshot": {
                    "status": task.review_snapshot.get("status"),
                    "rating": task.review_snapshot.get("rating"),
                    "favorite": task.review_snapshot.get("favorite"),
                    "notes_excerpt": task.review_snapshot.get("notes_excerpt"),
                    "tags": task.review_snapshot.get("tags") or [],
                    "marker_kinds": task.review_snapshot.get("marker_kinds") or [],
                    "markers": task.review_snapshot.get("markers") or [],
                },
            },
            "local_candidate_context": local_items,
            "rules": [
                "Return constrained ProviderEditPatch candidates only.",
                "Do not apply changes automatically.",
                "Treat keep and hook markers as preserve signals.",
                "Prefer targeted edits around the review task target.",
            ],
        }
    )
    return json.dumps(context, ensure_ascii=False, sort_keys=True)

def score_provider_review_candidate(
    *,
    task: ReviewTask,
    parent_plan: SongPlan,
    candidate_plan: SongPlan,
    patch: ProviderEditPatch,
    intents: list[EditIntent],
    validator_status: str = "passed",
) -> DomainDocument:
    base = score_provider_edit_candidate(parent_plan=parent_plan, candidate_plan=candidate_plan, patch=patch, validator_status=validator_status).to_dict()
    target_section = str(task.target.get("section_name") or "")
    target_track = str(task.target.get("track_name") or "")
    changed_sections = {intent.target.section_name for intent in intents if intent.target.section_name}
    changed_tracks = {intent.target.track_name for intent in intents if intent.target.track_name}
    edit_types = {intent.edit_type for intent in intents}
    confidence = int(base.get("patch_confidence") or 0)
    review_fit = 42 + round(confidence * 0.32)
    if "track_density" in edit_types and (target_track or task.target.get("role") in {"bass", "drums"}):
        review_fit += 18
    if "section_energy" in edit_types and target_section:
        review_fit += 14
    if {"set_section_chords", "rewrite_section_lyrics"} & {op.op for op in patch.operations}:
        review_fit += 8
    target_precision = 38
    if target_section and target_section in changed_sections:
        target_precision += 38
    if target_track and target_track in changed_tracks:
        target_precision += 28
    if len(changed_sections) <= 1:
        target_precision += 8
    if len(changed_tracks) <= 1:
        target_precision += 6
    quality_overall = int(base.get("quality_overall") or 0)
    parent_quality = parent_plan.quality.scores.overall if parent_plan.quality and parent_plan.quality.scores else 0
    quality_delta = quality_overall - parent_quality
    risk = 0
    if len(patch.operations) > 2:
        risk += (len(patch.operations) - 2) * 10
    if patch.warnings:
        risk += min(30, len(patch.warnings) * 12)
    if target_precision < 60:
        risk += 14
    if quality_overall < 60:
        risk += 18
    safety = _clamp(100 - risk, 0, 100)
    combined = round(
        0.34 * _clamp(review_fit, 0, 100)
        + 0.24 * _clamp(target_precision, 0, 100)
        + 0.18 * _clamp(quality_overall, 0, 100)
        + 0.12 * _clamp(confidence, 0, 100)
        + 0.12 * safety
    )
    warnings = [str(item) for item in base.get("warnings", []) if str(item)]
    if risk >= 40:
        warnings.append("provider_review_risk")
    return {
        **base,
        "combined": _clamp(combined, 0, 100),
        "review_fit": _clamp(review_fit, 0, 100),
        "target_precision": _clamp(target_precision, 0, 100),
        "quality_delta": quality_delta,
        "quality_overall": quality_overall,
        "safety": safety,
        "risk": _clamp(risk, 0, 100),
        "warnings": sorted(set(warnings)),
    }

def build_review_decision_report(
    *,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    parent_plan: SongPlan | None = None,
    now: str | None = None,
    notes: str = "",
    judge_report: DomainDocument | None = None,
) -> DomainDocument:
    if parent_plan is not None:
        ensure_task_current(task, parent_plan)
    parent_hash = task.hashes.get("parent_plan_hash") or (song_plan_hash(parent_plan) if parent_plan is not None else "")
    usable = [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]
    ranked = sorted(usable, key=lambda item: (item.rank or 9999, -int(item.scores.get("combined") or 0), item.candidate_id))
    recommended = ranked[0] if ranked else None
    judge_summary = _judge_summary_for_decision(judge_report)
    local_recommended_id = recommended.candidate_id if recommended else None
    judge_recommended_id = judge_summary.get("recommended_candidate_id")
    risk_flags = _decision_risk_flags(task, candidates, recommended)
    warnings: list[str] = []
    if judge_summary:
        if judge_recommended_id:
            warnings.append("Provider judge report is advisory; applying still requires manual confirmation.")
        if judge_recommended_id and local_recommended_id and judge_recommended_id != local_recommended_id:
            warnings.append("Provider judge recommendation differs from local ranking.")
            risk_flags.append("judge_local_recommendation_disagreement")
        if judge_summary.get("stale"):
            warnings.append("Provider judge report is stale.")
            risk_flags.append("stale_judge_report")
    report = {
        "schema_version": REVIEW_DECISION_REPORT_SCHEMA_VERSION,
        "task_id": task.task_id,
        "project_id": task.project_id,
        "parent_version_id": task.parent_version_id,
        "parent_song_plan_hash": parent_hash,
        "created_at": now or now_iso(),
        "candidate_count": len(candidates),
        "recommended_candidate_id": local_recommended_id,
        "local_recommended_candidate_id": local_recommended_id,
        "judge_recommended_candidate_id": judge_recommended_id,
        "recommendation_reason": _recommendation_reason(recommended, judge_summary=judge_summary) if recommended else "No ready candidate is available.",
        "requires_manual_apply": True,
        "ranking": [_decision_rank_entry(candidate, index + 1) for index, candidate in enumerate(ranked)],
        "source_breakdown": review_candidate_source_breakdown(candidates),
        "risk_flags": sorted(set(risk_flags)),
        "judge_summary": judge_summary,
        "warnings": warnings,
        "notes": sanitize_sensitive_text(notes)[:1000],
    }
    return sanitize_metadata(report)

def review_decision_summary(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict):
        return {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "task_id": report.get("task_id"),
            "recommended_candidate_id": report.get("recommended_candidate_id"),
            "local_recommended_candidate_id": report.get("local_recommended_candidate_id"),
            "judge_recommended_candidate_id": report.get("judge_recommended_candidate_id"),
            "candidate_count": report.get("candidate_count"),
            "requires_manual_apply": bool(report.get("requires_manual_apply", True)),
            "source_breakdown": _as_document(report.get("source_breakdown")),
            "risk_flags": _as_list(report.get("risk_flags")),
            "judge_summary": _as_document(report.get("judge_summary")),
            "warnings": _as_list(report.get("warnings")),
            "created_at": report.get("created_at"),
        }
    )

def review_candidate_source_breakdown(candidates: list[ReviewCandidate]) -> DomainDocument:
    provider = [candidate for candidate in candidates if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")]
    local = [candidate for candidate in candidates if candidate.candidate_type == "local_review_intents"]
    usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    models: set[str] = set()
    templates: set[str] = set()
    seen_usage_calls: set[tuple[str, str, str, str, int]] = set()
    for candidate in provider:
        source = candidate.source
        usage_data = _as_document(source.get("usage"))
        usage_key = (
            str(source.get("provider_run_id") or ""),
            str(source.get("request_id") or ""),
            str(source.get("template_id") or ""),
            str(source.get("model") or ""),
            _usage_int(usage_data, "total_tokens"),
        )
        if usage_key not in seen_usage_calls:
            seen_usage_calls.add(usage_key)
            for key in usage:
                usage[key] += _usage_int(usage_data, key)
        if source.get("model"):
            models.add(str(source.get("model")))
        if source.get("template_id"):
            templates.add(str(source.get("template_id")))
    return sanitize_metadata(
        {
            "local_candidate_count": len(local),
            "provider_candidate_count": len(provider),
            "ready_provider_candidate_count": len([candidate for candidate in provider if candidate.status == "ready"]),
            "failed_provider_candidate_count": len([candidate for candidate in provider if candidate.status == "failed"]),
            "provider_models": sorted(models),
            "provider_template_ids": sorted(templates),
            "provider_usage": usage,
        }
    )

def _decision_rank_entry(candidate: ReviewCandidate, rank: int) -> DomainDocument:
    scores = _as_document(candidate.scores)
    return sanitize_metadata(
        {
            "candidate_id": candidate.candidate_id,
            "candidate_type": candidate.candidate_type,
            "strategy": candidate.strategy,
            "source_type": candidate.source.get("source_type") if isinstance(candidate.source, dict) else "",
            "provider": bool(candidate.source.get("provider")) if isinstance(candidate.source, dict) else False,
            "rank": rank,
            "combined": int(scores.get("combined") or 0),
            "review_fit": int(scores.get("review_fit") or 0),
            "quality_overall": int(scores.get("quality_overall") or 0),
            "target_precision": int(scores.get("target_precision") or 0),
            "risk": int(scores.get("risk") or (100 - int(scores.get("safety") or 100))),
            "warnings": list(candidate.warnings[:8]),
            "summary": candidate.summary,
        }
    )

def _recommendation_reason(candidate: ReviewCandidate | None, *, judge_summary: DomainDocument | None = None) -> str:
    if candidate is None:
        return "No ready candidate is available."
    score = int(candidate.scores.get("combined") or 0)
    source = "provider" if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider") else candidate.strategy
    reason = f"Ranked first by combined review score ({score}) from {source} candidate {candidate.candidate_id}."
    if isinstance(judge_summary, dict) and judge_summary.get("recommended_candidate_id"):
        reason += f" Provider judge recommends {judge_summary.get('recommended_candidate_id')} as advisory context."
    return sanitize_sensitive_text(reason)[:500]

def _decision_risk_flags(task: ReviewTask, candidates: list[ReviewCandidate], recommended: ReviewCandidate | None) -> list[str]:
    flags: list[str] = []
    if recommended is None:
        flags.append("no_ready_candidate")
    if recommended and recommended.candidate_type == "provider_review_patch":
        flags.append("provider_candidate_requires_manual_apply")
    if any(int(candidate.scores.get("risk") or 0) >= 40 for candidate in candidates):
        flags.append("high_risk_candidate_present")
    if any(candidate.status == "failed" for candidate in candidates):
        flags.append("failed_candidate_present")
    if task.status in TERMINAL_TASK_STATUSES or task.status == "applied":
        flags.append(f"task_status_{task.status}")
    return sorted(set(flags))
