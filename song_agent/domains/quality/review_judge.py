from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import hashlib as hashlib
import json as json
from typing import Any as Any

from song_agent.domains.studio.prompt_templates import PromptTemplate as PromptTemplate, render_prompt_template as render_prompt_template
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig, ProviderConfigError as ProviderConfigError, ProviderEditResponse as ProviderEditResponse, ProviderOutputError as ProviderOutputError
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import ReviewCandidate as ReviewCandidate, ReviewTask as ReviewTask, validate_review_candidate_id as validate_review_candidate_id
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.studio.song_editor import song_plan_hash as song_plan_hash


REVIEW_JUDGE_SCHEMA_VERSION = 1
REVIEW_JUDGE_TEMPLATE_ID = "provider-review-judge"
JUDGE_STATUSES = {"not_started", "completed", "failed", "stale", "unavailable"}
JUDGE_SCORE_FIELDS = ("overall", "review_fit", "target_precision", "musicality", "novelty", "risk")


class ReviewJudgeError(ValueError):
    pass


def build_review_judge_prompt_payload(
    *,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    parent_plan: SongPlan,
    decision_report: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    ready = _ready_candidates(candidates)
    payload = {
        "task": {
            "task_id": task.task_id,
            "title": task.title,
            "summary": task.summary,
            "notes": task.review_snapshot.get("notes_excerpt") if isinstance(task.review_snapshot, dict) else "",
            "tags": task.review_snapshot.get("tags", []) if isinstance(task.review_snapshot, dict) else [],
            "markers": _marker_summary(task.review_snapshot.get("markers", []) if isinstance(task.review_snapshot, dict) else []),
            "target": _target_summary(task.target),
            "priority": task.priority,
            "status": task.status,
        },
        "parent_song": _parent_song_summary(parent_plan),
        "candidates": [_candidate_prompt_summary(candidate) for candidate in ready],
        "decision_report": _decision_prompt_summary(decision_report),
        "instruction": {
            "judge_dimensions": ["review_fit", "target_precision", "musicality", "novelty", "risk", "confidence"],
            "output_json_only": True,
            "manual_apply_required": True,
            "note": sanitize_sensitive_text(str(note or ""))[:500],
        },
    }
    return sanitize_metadata(payload)


def run_provider_review_judge(
    *,
    project_id: str,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    parent_plan: SongPlan,
    template: PromptTemplate,
    config: ProviderConfig,
    decision_report: dict[str, Any] | None = None,
    note: str = "",
    now: str | None = None,
    client: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or now_iso()
    config.validate_ready_for_provider()
    if not template.enabled:
        raise ReviewJudgeError("Prompt template is disabled.")
    ready = _ready_candidates(candidates)
    if not ready:
        raise ReviewJudgeError("Review judge requires at least one ready candidate.")
    payload = build_review_judge_prompt_payload(task=task, candidates=ready, parent_plan=parent_plan, decision_report=decision_report, note=note)
    prompt = render_prompt_template(template, payload)
    client = client or _client_for_config(config)
    try:
        if hasattr(client, "generate_review_judge_json"):
            response = client.generate_review_judge_json(parent_plan, payload, config, prompt=prompt)
        else:
            raise ProviderConfigError("Provider client does not support review judge.")
        data, usage, request_id = _provider_response_parts(response)
        report = build_judge_report(
            project_id=project_id,
            task=task,
            candidates=ready,
            parent_plan=parent_plan,
            template=template,
            provider_output=data,
            provider_snapshot={
                "wire_api": config.wire_api,
                "model": config.review_model or config.model,
                "template_id": template.template_id,
                "usage": usage,
                "request_id": request_id,
            },
            now=now,
        )
    except (ReviewJudgeError, ValueError) as exc:
        raise ProviderOutputError(str(exc)) from exc
    snapshot = {
        "mode": "provider",
        "operation": "provider_review_judge",
        "wire_api": config.wire_api,
        "model": config.review_model or config.model,
        "template_id": template.template_id,
        "usage": usage,
        "request_id": request_id,
        "candidate_count": len(ready),
    }
    return report, sanitize_metadata(snapshot)


def build_judge_report(
    *,
    project_id: str,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    parent_plan: SongPlan,
    template: PromptTemplate,
    provider_output: dict[str, Any],
    provider_snapshot: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    if not isinstance(provider_output, dict):
        raise ReviewJudgeError("Provider judge output must be a JSON object.")
    ready_ids = [candidate.candidate_id for candidate in _ready_candidates(candidates)]
    if not ready_ids:
        raise ReviewJudgeError("Review judge requires ready candidates.")
    recommended_id = _candidate_id(provider_output.get("recommended_candidate_id"), ready_ids, "recommended_candidate_id")
    scores = _candidate_scores(provider_output.get("candidate_scores"), ready_ids)
    scored_ids = {score["candidate_id"] for score in scores}
    warnings = _text_list(provider_output.get("warnings"), max_items=12, max_length=240)
    missing_ids = [candidate_id for candidate_id in ready_ids if candidate_id not in scored_ids]
    if missing_ids:
        warnings.append(f"Provider judge omitted scores for: {', '.join(missing_ids[:6])}.")
    comparison = _comparison_summary(provider_output.get("comparison_summary"), ready_ids, recommended_id)
    usage = _as_document(provider_snapshot.get("usage"))
    report = {
        "schema_version": REVIEW_JUDGE_SCHEMA_VERSION,
        "project_id": project_id,
        "task_id": task.task_id,
        "created_at": now,
        "status": "completed",
        "source_hash_version": 2,
        "source_hash": judge_source_hash(task=task, candidates=candidates, parent_plan=parent_plan, template=template),
        "parent_version_id": task.parent_version_id,
        "parent_plan_hash": song_plan_hash(parent_plan),
        "template_id": template.template_id,
        "template_updated_at": template.updated_at,
        "provider": {
            "wire_api": provider_snapshot.get("wire_api"),
            "model": provider_snapshot.get("model"),
            "request_id": provider_snapshot.get("request_id"),
        },
        "recommended_candidate_id": recommended_id,
        "candidate_scores": scores,
        "comparison_summary": comparison,
        "manual_review_required": True,
        "risk_flags": _risk_flags(scores),
        "warnings": warnings[:12],
        "provider_usage": _usage_summary(usage),
    }
    return sanitize_metadata(report)


def judge_source_hash(*, task: ReviewTask, candidates: list[ReviewCandidate], parent_plan: SongPlan, template: PromptTemplate) -> str:
    ready = _ready_candidates(candidates)
    source = {
        "task": {
            "task_id": task.task_id,
            "priority": task.priority,
            "title": task.title,
            "summary": task.summary,
            "source": task.source,
            "review_snapshot": task.review_snapshot,
            "target": task.target,
            "hashes": task.hashes,
        },
        "parent_plan_hash": song_plan_hash(parent_plan),
        "template": {
            "template_id": template.template_id,
            "updated_at": template.updated_at,
            "enabled": template.enabled,
        },
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "rank": candidate.rank,
                "candidate_type": candidate.candidate_type,
                "strategy": candidate.strategy,
                "summary": candidate.summary,
                "intents": candidate.intents,
                "patch": candidate.patch,
                "validator": candidate.validator,
                "scores": candidate.scores,
                "warnings": candidate.warnings,
                "hashes": candidate.hashes,
            }
            for candidate in ready
        ],
    }
    payload = json.dumps(sanitize_metadata(source), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def judge_report_stale(
    report: dict[str, Any] | None,
    *,
    task: ReviewTask,
    candidates: list[ReviewCandidate],
    parent_plan: SongPlan,
    template: PromptTemplate,
) -> bool:
    if not isinstance(report, dict) or not report:
        return False
    expected = str(report.get("source_hash") or "")
    if not expected:
        return True
    return expected != judge_source_hash(task=task, candidates=candidates, parent_plan=parent_plan, template=template)


def read_judge_report_with_stale(
    task_store: Any,
    task: ReviewTask,
    *,
    candidates: list[ReviewCandidate] | None = None,
    parent_plan: SongPlan | None = None,
    template: PromptTemplate | None = None,
) -> dict[str, Any]:
    report = task_store.read_judge_report(task.task_id, default={})
    if not report:
        return {}
    if parent_plan is None or template is None:
        return mark_judge_report_stale(report, stale=True)
    try:
        stale = judge_report_stale(report, task=task, candidates=candidates or task_store.list_candidates(task.task_id), parent_plan=parent_plan, template=template)
    except (OSError, ValueError, TypeError):
        stale = True
    return mark_judge_report_stale(report, stale=stale)


def mark_judge_report_stale(report: dict[str, Any] | None, *, stale: bool) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    data = dict(report)
    data["stale"] = bool(stale)
    if stale and data.get("status") == "completed":
        data["status"] = "stale"
    return sanitize_metadata(data)


def judge_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {"status": "not_started", "manual_review_required": True}
    scores = _as_list(report.get("candidate_scores"))
    top = _top_score(scores, str(report.get("recommended_candidate_id") or ""))
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "task_id": report.get("task_id"),
            "status": report.get("status") or "not_started",
            "stale": bool(report.get("stale", False)),
            "created_at": report.get("created_at"),
            "recommended_candidate_id": report.get("recommended_candidate_id"),
            "top_overall": top.get("overall"),
            "top_confidence": top.get("confidence"),
            "top_risk": top.get("risk"),
            "manual_review_required": bool(report.get("manual_review_required", True)),
            "risk_flags": _as_list(report.get("risk_flags")),
            "warning_count": len(report.get("warnings", [])) if isinstance(report.get("warnings"), list) else 0,
            "provider_usage": _usage_summary(_as_document(report.get("provider_usage"))),
        }
    )


def sprint_judge_summary(
    *,
    sprint_id: str,
    task_reports: list[dict[str, Any]],
    provider_usage_records: list[dict[str, Any]] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    reports = [report for report in task_reports if isinstance(report, dict) and report]
    completed = [report for report in reports if report.get("status") == "completed"]
    stale = [report for report in reports if report.get("stale") or report.get("status") == "stale"]
    recommended = [report for report in completed if report.get("recommended_candidate_id")]
    task_summaries = [judge_report_summary(report) for report in reports]
    top_summary = sorted(
        [summary for summary in task_summaries if summary.get("recommended_candidate_id")],
        key=lambda item: (-int(item.get("top_overall") or 0), int(item.get("top_risk") or 0), str(item.get("task_id") or "")),
    )
    high_risk = 0
    risk_flags: list[str] = []
    tokens = 0
    for report in reports:
        usage = _as_document(report.get("provider_usage"))
        tokens += int(usage.get("total_tokens") or 0)
        for flag in report.get("risk_flags", []) if isinstance(report.get("risk_flags"), list) else []:
            risk_flags.append(str(flag))
        for score in report.get("candidate_scores", []) if isinstance(report.get("candidate_scores"), list) else []:
            if isinstance(score, dict) and int(score.get("risk") or 0) >= 70:
                high_risk += 1
    return sanitize_metadata(
        {
            "schema_version": REVIEW_JUDGE_SCHEMA_VERSION,
            "sprint_id": sprint_id,
            "created_at": now,
            "judged_task_count": len(completed),
            "stale_judge_count": len(stale),
            "recommended_candidate_count": len(recommended),
            "judge_provider_tokens": tokens,
            "high_risk_candidate_count": high_risk,
            "risk_flags": sorted(set(risk_flags))[:20],
            "top_judge_recommendation": top_summary[0] if top_summary else {},
            "task_summaries": task_summaries,
        }
    )


def judge_summary_for_apply(report: dict[str, Any] | None, *, candidate_id: str, stale: bool = False) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    summary = judge_report_summary(mark_judge_report_stale(report, stale=stale))
    return sanitize_metadata(
        {
            "task_id": report.get("task_id"),
            "judge_report_created_at": report.get("created_at"),
            "judge_recommended_candidate_id": report.get("recommended_candidate_id"),
            "applied_matches_judge": bool(report.get("recommended_candidate_id") == candidate_id),
            "top_overall": summary.get("top_overall"),
            "confidence": summary.get("top_confidence"),
            "manual_review_required": summary.get("manual_review_required"),
            "judge_stale_at_apply": bool(stale),
        }
    )


def _ready_candidates(candidates: list[ReviewCandidate]) -> list[ReviewCandidate]:
    return [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]


def _candidate_prompt_summary(candidate: ReviewCandidate) -> ImplementationDocument:
    scores = _as_document(candidate.scores)
    validator = _as_document(candidate.validator)
    patch = _as_document(candidate.patch)
    operations = _as_list(patch.get("operations"))
    return sanitize_metadata(
        {
            "candidate_id": candidate.candidate_id,
            "source": "provider" if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider") else "local",
            "candidate_type": candidate.candidate_type,
            "strategy": candidate.strategy,
            "rank": candidate.rank,
            "status": candidate.status,
            "summary": candidate.summary,
            "scores": {key: scores.get(key) for key in ("combined", "review_fit", "target_precision", "quality_delta", "quality_overall", "novelty", "safety", "risk")},
            "validator": {
                "status": validator.get("status"),
                "errors": _as_list(validator.get("errors")),
                "warnings": _as_list(validator.get("warnings")),
            },
            "changed_sections": _changed_values(candidate.intents, "section_name"),
            "changed_tracks": _changed_values(candidate.intents, "track_name"),
            "patch_summary": {
                "operation_count": len(operations),
                "operations": [
                    {"op": op.get("op"), "section_name": op.get("section_name"), "track_name": op.get("track_name")}
                    for op in operations[:8]
                    if isinstance(op, dict)
                ],
            },
            "warnings": list(candidate.warnings[:8]),
        }
    )


def _parent_song_summary(parent_plan: SongPlan) -> ImplementationDocument:
    plan = parent_plan.to_dict()
    quality = _as_document(plan.get("quality"))
    return sanitize_metadata(
        {
            "title": plan.get("title"),
            "style": plan.get("style"),
            "tempo_bpm": plan.get("tempo_bpm"),
            "key": plan.get("key"),
            "quality": _document_or(quality.get("scores"), quality),
            "sections": [
                {
                    "name": section.get("name"),
                    "role": section.get("role"),
                    "bars": section.get("bars"),
                    "energy": section.get("energy"),
                }
                for section in plan.get("sections", [])[:12]
                if isinstance(section, dict)
            ],
            "tracks": [
                {"name": track.get("name"), "role": track.get("role"), "instrument": track.get("instrument")}
                for track in plan.get("tracks", [])[:16]
                if isinstance(track, dict)
            ],
        }
    )


def _decision_prompt_summary(report: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(report, dict):
        return {}
    return sanitize_metadata(
        {
            "recommended_candidate_id": report.get("recommended_candidate_id"),
            "risk_flags": _as_list(report.get("risk_flags")),
            "source_breakdown": _as_document(report.get("source_breakdown")),
            "ranking": [
                {
                    "candidate_id": item.get("candidate_id"),
                    "rank": item.get("rank"),
                    "combined": item.get("combined"),
                    "risk": item.get("risk"),
                }
                for item in report.get("ranking", [])[:8]
                if isinstance(item, dict)
            ],
        }
    )


def _marker_summary(markers: list[Any]) -> list[ImplementationDocument]:
    result = []
    for marker in markers[:20]:
        if not isinstance(marker, dict):
            continue
        result.append({"beat": marker.get("beat"), "kind": marker.get("kind"), "label": marker.get("label")})
    return sanitize_metadata(result)


def _target_summary(target: ImplementationDocument) -> ImplementationDocument:
    if not isinstance(target, dict):
        return {}
    return sanitize_metadata(
        {
            "section_name": target.get("section_name"),
            "track_name": target.get("track_name"),
            "role": target.get("role"),
            "global_marker_beat": target.get("global_marker_beat"),
        }
    )


def _candidate_scores(value: Any, ready_ids: list[str]) -> list[ImplementationDocument]:
    if not isinstance(value, list) or not value:
        raise ReviewJudgeError("candidate_scores must be a non-empty list.")
    scores = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ReviewJudgeError("candidate_scores items must be objects.")
        candidate_id = _candidate_id(item.get("candidate_id"), ready_ids, "candidate_scores.candidate_id")
        if candidate_id in seen:
            raise ReviewJudgeError(f"duplicate judge score for candidate: {candidate_id}.")
        seen.add(candidate_id)
        score: ImplementationDocument = {"candidate_id": candidate_id}
        for field_name in JUDGE_SCORE_FIELDS:
            score[field_name] = _score_0_100(item.get(field_name), field_name)
        score["confidence"] = _confidence(item.get("confidence"))
        score["reason"] = sanitize_sensitive_text(str(item.get("reason") or ""))[:1000]
        score["risks"] = _text_list(item.get("risks"), max_items=8, max_length=120)
        scores.append(score)
    return scores


def _comparison_summary(value: Any, ready_ids: list[str], recommended_id: str) -> ImplementationDocument:
    value = _as_document(value)
    best_id = value.get("best_candidate_id") or recommended_id
    return sanitize_metadata(
        {
            "best_candidate_id": _candidate_id(best_id, ready_ids, "comparison_summary.best_candidate_id"),
            "reason": sanitize_sensitive_text(str(value.get("reason") or ""))[:1000],
            "tradeoffs": _text_list(value.get("tradeoffs"), max_items=8, max_length=240),
        }
    )


def _candidate_id(value: Any, ready_ids: list[str], field_name: str) -> str:
    candidate_id = validate_review_candidate_id(str(value or ""))
    if candidate_id not in ready_ids:
        raise ReviewJudgeError(f"{field_name} must reference a ready candidate for this task.")
    return candidate_id


def _score_0_100(value: Any, field_name: str) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        raise ReviewJudgeError(f"{field_name} must be an integer from 0 to 100.") from None
    if score < 0 or score > 100:
        raise ReviewJudgeError(f"{field_name} must be an integer from 0 to 100.")
    return score


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        raise ReviewJudgeError("confidence must be between 0 and 1.") from None
    if confidence < 0.0 or confidence > 1.0:
        raise ReviewJudgeError("confidence must be between 0 and 1.")
    return round(confidence, 4)


def _text_list(value: Any, *, max_items: int, max_length: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReviewJudgeError("text fields must be arrays when provided.")
    return [sanitize_sensitive_text(str(item))[:max_length] for item in value[:max_items] if str(item).strip()]


def _risk_flags(scores: list[ImplementationDocument]) -> list[str]:
    flags: list[str] = []
    if any(int(score.get("risk") or 0) >= 70 for score in scores):
        flags.append("high_risk_candidate_present")
    if any(float(score.get("confidence") or 0) < 0.4 for score in scores):
        flags.append("low_confidence_candidate_present")
    return flags


def _usage_summary(usage: ImplementationDocument) -> dict[str, int]:
    return {
        "prompt_tokens": _usage_int(usage, "prompt_tokens"),
        "completion_tokens": _usage_int(usage, "completion_tokens"),
        "total_tokens": _usage_int(usage, "total_tokens") or _usage_int(usage, "prompt_tokens") + _usage_int(usage, "completion_tokens"),
    }


def _usage_int(usage: ImplementationDocument, field_name: str) -> int:
    try:
        return max(0, int((usage or {}).get(field_name) or 0))
    except (TypeError, ValueError):
        return 0


def _provider_response_parts(response: Any) -> tuple[ImplementationDocument, ImplementationDocument, str | None]:
    if isinstance(response, ProviderEditResponse):
        return response.data, dict(response.usage or {}), response.request_id
    if isinstance(response, dict) and "data" in response and isinstance(response.get("data"), dict):
        usage = _as_document(response.get("usage"))
        request_id = response.get("request_id")
        return response["data"], dict(usage), None if request_id is None else str(request_id)
    if isinstance(response, dict):
        return response, {}, None
    raise ReviewJudgeError("provider judge response must be a JSON object.")


def _client_for_config(config: ProviderConfig) -> Any:
    if config.wire_api == "mock":
        from song_agent.domains.creation.providers.mock import MockProviderClient

        return MockProviderClient()
    if config.wire_api == "openai_chat_completions":
        from song_agent.domains.creation.providers.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient()
    raise ProviderConfigError(f"Unsupported provider wire_api: {config.wire_api}.")


def _top_score(scores: list[Any], candidate_id: str) -> ImplementationDocument:
    clean = [score for score in scores if isinstance(score, dict)]
    for score in clean:
        if score.get("candidate_id") == candidate_id:
            return score
    return sorted(clean, key=lambda item: -int(item.get("overall") or 0))[0] if clean else {}


def _changed_values(intents: list[ImplementationDocument], field_name: str) -> list[str]:
    values: list[str] = []
    for intent in intents[:20]:
        if not isinstance(intent, dict):
            continue
        target = _as_document(intent.get("target"))
        value = target.get(field_name)
        if value and str(value) not in values:
            values.append(str(value))
    return values[:12]
