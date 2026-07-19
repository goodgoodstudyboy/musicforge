# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import shutil as shutil
import threading as threading
from pathlib import Path as Path
from typing import Callable as Callable
from song_agent.domains.quality.audio_lab import AudioLabStore as AudioLabStore
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.creation.schemas.song import SongRequest as SongRequest
from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.creation.renderers.midi import render_midi as render_midi

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

ch = _make_deferred_global('ch')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch
    ch = namespace.get('ch', ch)
    _bind_deferred_defaults(namespace)


AUDIO_FIX_SCHEMA_VERSION = 1
HIGH_SEVERITIES = {"high", "critical"}
FIX_CATEGORIES = {"mix_balance", "timing", "arrangement", "noise", "mastering", "performance", "other"}




class AudioFixSprintError(ValueError):
    pass

class AudioFixSprintNotFoundError(AudioFixSprintError):
    pass

class AudioFixSprintStateError(AudioFixSprintError):
    pass

class AudioFixSprintValidationError(AudioFixSprintError, ValueError):
    pass

def _collect_fix_items(sessions: list[DomainDocument], *, include_test_audio: bool, existing_keys: set[str]) -> list[DomainDocument]:
    collected: list[DomainDocument] = []
    categories: dict[str, int] = {}
    counter = 0
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for item in session.get("items", []):
            if item.get("stale"):
                continue
            renderer = _as_document(item.get("renderer"))
            if renderer.get("runner_kind") == "test_fake" and not include_test_audio:
                continue
            if not item.get("artifact_hashes", {}).get("wav_sha256"):
                continue
            review = _as_document(item.get("review"))
            markers = [marker for marker in item.get("markers", []) if isinstance(marker, dict)]
            review_status = str(review.get("status") or "")
            review_markers = [marker for marker in markers if str(marker.get("severity") or "") in HIGH_SEVERITIES or str(marker.get("category") or "") in FIX_CATEGORIES]
            if review_status in {"needs_fix", "rejected"} and not review_markers:
                review_markers = [{"marker_id": "review", "severity": "high" if review_status == "rejected" else "medium", "category": "other", "message": review.get("notes") or review_status, "source_hash": review.get("source_hash")}]
            for marker in review_markers:
                key = stable_hash({"session_id": session_id, "item_id": item.get("item_id"), "marker_id": marker.get("marker_id"), "marker_source_hash": marker.get("source_hash")})
                if key in existing_keys:
                    raise AudioFixSprintStateError("Audio Lab marker is already assigned to an open Audio Fix Sprint.")
                counter += 1
                severity = str(marker.get("severity") or "medium")
                category = str(marker.get("category") or "other")
                categories[category] = categories.get(category, 0) + 1
                fix_item = {
                    "fix_item_id": f"afi-{counter:06d}",
                    "status": "open",
                    "priority": 0,
                    "category": category,
                    "severity": severity,
                    "source_key": key,
                    "source_marker": {
                        "session_id": session_id,
                        "item_id": item.get("item_id"),
                        "marker_id": marker.get("marker_id"),
                        "marker_source_hash": marker.get("source_hash"),
                        "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256"),
                    },
                    "target": {
                        "song_id": item.get("song_id"),
                        "title": item.get("title"),
                        "time_seconds": marker.get("time_seconds"),
                        "track_hint": marker.get("track_hint") or category,
                    },
                    "review_status": review_status,
                    "recommended_actions": _recommended_actions(category),
                    "artifact_relpaths": dict(item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(item.get("artifact_hashes") or {}),
                    "renderer": renderer,
                    "drafts": {},
                    "candidates": [],
                    "selected_candidate_id": None,
                    "resolution": None,
                    "stale": False,
                    "stale_reasons": [],
                }
                fix_item["priority"] = _priority(fix_item, repeated_category=False)
                fix_item["source_hash"] = stable_hash(_fix_item_source(fix_item))
                fix_item["integrity_hash"] = _integrity_hash(fix_item)
                collected.append(fix_item)
    for item in collected:
        if categories.get(str(item.get("category") or ""), 0) > 1:
            item["priority"] = _priority(item, repeated_category=True)
    return sorted(collected, key=lambda row: (-int(row.get("priority") or 0), str(row.get("fix_item_id") or "")))

def _priority(item: DomainDocument, *, repeated_category: bool) -> int:
    score = {"critical": 50, "high": 35, "medium": 20, "low": 10}.get(str(item.get("severity") or ""), 10)
    score += {"rejected": 40, "needs_fix": 25}.get(str(item.get("review_status") or ""), 0)
    if repeated_category:
        score += 10
    if item.get("renderer", {}).get("runner_kind") == "test_fake":
        score -= 20
    return max(0, score)

def _recommended_actions(category: str) -> list[str]:
    if category in {"mix_balance", "mastering"}:
        return ["mix_patch", "audio_revision", "review_task"]
    if category in {"timing", "arrangement", "performance"}:
        return ["audio_revision", "review_task"]
    return ["review_task", "audio_revision", "mix_patch"]

def _session_ids_from_payload(payload: DomainDocument) -> list[str]:
    raw = payload.get("session_ids") or payload.get("from_sessions") or payload.get("from_session") or payload.get("session_id")
    if isinstance(raw, list):
        session_ids = [str(item).strip() for item in raw if str(item).strip()]
    else:
        session_ids = [str(raw or "").strip()]
    session_ids = [_validate_id(item, "als") for item in session_ids if item]
    if not session_ids:
        raise AudioFixSprintValidationError("from_session is required.")
    return session_ids

def _session_source_hash(session: DomainDocument) -> str:
    items = []
    for item in session.get("items", []):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "item_id": item.get("item_id"),
                "source_hash": item.get("source_hash"),
                "artifact_hashes": item.get("artifact_hashes"),
                "audio_status": item.get("audio_status"),
                "renderer": item.get("renderer"),
                "review": _review_core(item.get("review") or {}) if isinstance(item.get("review"), dict) else {},
                "markers": [
                    {
                        "marker_id": marker.get("marker_id"),
                        "severity": marker.get("severity"),
                        "category": marker.get("category"),
                        "source_hash": marker.get("source_hash"),
                    }
                    for marker in item.get("markers", [])
                    if isinstance(marker, dict)
                ],
            }
        )
    return stable_hash({"session_id": session.get("session_id"), "source": session.get("source"), "items": items})

def _selected_item_ids(payload: DomainDocument, items: list[DomainDocument]) -> set[str]:
    raw = payload.get("fix_item_ids") or payload.get("item_ids")
    if not raw:
        raw = [item.get("fix_item_id") for item in items]
    if not isinstance(raw, list):
        raw = [raw]
    selected = {_validate_id(str(item), "afi") for item in raw if str(item).strip()}
    if not selected:
        raise AudioFixSprintValidationError("At least one fix_item_id is required.")
    return selected

def _build_draft(sprint: DomainDocument, item: DomainDocument, draft_type: str) -> DomainDocument:
    prefix = {"review_task": "alfsrt", "audio_revision": "alfsar", "mix_patch": "alfsmp"}[draft_type]
    draft = {
        "schema_version": AUDIO_FIX_SCHEMA_VERSION,
        "draft_id": f"{prefix}-{item.get('fix_item_id')}",
        "draft_type": draft_type,
        "status": "draft",
        "created_at": now_iso(),
        "fix_sprint_id": sprint.get("fix_sprint_id"),
        "fix_item_id": item.get("fix_item_id"),
        "title": f"Fix {item.get('category')} {item.get('severity')}",
        "instruction": f"Address Audio Lab marker {item.get('source_marker', {}).get('marker_id')} from session {item.get('source_marker', {}).get('session_id')}.",
        "provenance": {
            "source_type": "audio_fix_sprint_item",
            "sprint_source_hash": sprint.get("source_hash"),
            "fix_item_source_hash": item.get("source_hash"),
            "marker_source_hash": item.get("source_marker", {}).get("marker_source_hash"),
            "wav_sha256": item.get("source_marker", {}).get("wav_sha256"),
        },
        "auto_apply": False,
    }
    draft["integrity_hash"] = _integrity_hash(draft)
    return draft

def _candidate_review(payload: DomainDocument) -> DomainDocument:
    if bool(payload.get("playback_confirmed")) is not True:
        raise AudioFixSprintValidationError("Candidate A/B review requires playback_confirmed=true.")
    review_mode = str(payload.get("review_mode") or "manual")
    if review_mode != "manual":
        raise AudioFixSprintValidationError("Candidate A/B review must be manual.")
    preferred = str(payload.get("preferred") or "").strip()
    if preferred not in {"left", "right", "same"}:
        raise AudioFixSprintValidationError("preferred must be left, right, or same.")
    reviewer = _as_document(payload.get("reviewer"))
    name = _bounded(reviewer.get("name") or payload.get("reviewer_name") or payload.get("reviewer"), 120)
    role = _bounded(reviewer.get("role") or payload.get("role"), 80)
    if not name or not role:
        raise AudioFixSprintValidationError("Candidate A/B review requires reviewer name and role.")
    review = {
        "status": "accepted" if preferred in {"right", "same"} else "rejected",
        "preferred": preferred,
        "rating": max(1, min(5, int(payload.get("rating") or 0))),
        "rating_delta": int(payload.get("rating_delta") or 0),
        "review_mode": "manual",
        "playback_confirmed": True,
        "reviewer": {"name": name, "role": role},
        "notes": _bounded(payload.get("notes"), 1000),
        "created_at": now_iso(),
    }
    review["source_hash"] = stable_hash(_review_core(review))
    review["integrity_hash"] = _integrity_hash(review)
    return review

def _manual_review(payload: DomainDocument) -> DomainDocument:
    result = str(payload.get("result") or payload.get("status") or "").strip()
    if result not in {"accepted", "needs_fix", "rejected"}:
        raise AudioFixSprintValidationError("result must be accepted, needs_fix, or rejected.")
    review = _candidate_review({**payload, "preferred": "right" if result == "accepted" else "left"})
    review["status"] = result
    review["source_hash"] = stable_hash(_review_core(review))
    review["integrity_hash"] = _integrity_hash(review)
    return review

def _find_item_candidate(sprint: DomainDocument, item_id: str, candidate_id: str) -> tuple[DomainDocument, DomainDocument]:
    item_id = _validate_id(item_id, "afi")
    candidate_id = _validate_id(candidate_id, "afc")
    item = next((row for row in sprint.get("items", []) if row.get("fix_item_id") == item_id), None)
    if not item:
        raise AudioFixSprintNotFoundError(f"Audio Fix item not found: {item_id}.")
    candidate = _candidate_by_id(item, candidate_id)
    if not candidate:
        raise AudioFixSprintNotFoundError(f"Audio Fix candidate not found: {candidate_id}.")
    return item, candidate

def _candidate_by_id(item: DomainDocument, candidate_id: str) -> DomainDocument:
    return next((row for row in item.get("candidates", []) if row.get("candidate_id") == candidate_id), {})

def _candidate_is_stale(candidate: DomainDocument, sprint_dir: Path) -> bool:
    artifacts = _as_document(candidate.get("artifacts"))
    hashes = _as_document(candidate.get("artifact_hashes"))
    midi_rel = artifacts.get("midi")
    wav_rel = artifacts.get("wav")
    if midi_rel and (not (sprint_dir / str(midi_rel)).exists() or _sha256_path(sprint_dir / str(midi_rel)) != hashes.get("midi_sha256")):
        return True
    if wav_rel and (not (sprint_dir / str(wav_rel)).exists() or _sha256_path(sprint_dir / str(wav_rel)) != hashes.get("wav_sha256")):
        return True
    return False

def _candidate_selected_stale(item: DomainDocument, sprint_dir: Path) -> bool:
    candidate_id = item.get("selected_candidate_id")
    if not candidate_id:
        return False
    candidate = _candidate_by_id(item, str(candidate_id))
    return bool(candidate and _candidate_is_stale(candidate, sprint_dir))

def _closeout_blockers(sprint: DomainDocument, recheck: DomainDocument | None, sprint_dir: Path) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if sprint.get("stale"):
        blockers.append("sprint_stale")
    items = sprint.get("items", [])
    if any(not item.get("selected_candidate_id") for item in items):
        blockers.append("unselected_fix_items")
    if any(_candidate_selected_stale(item, sprint_dir) for item in items):
        blockers.append("selected_candidate_stale")
    if not recheck:
        blockers.append("recheck_session_missing")
    else:
        summary = _recheck_summary(recheck.get("items", []), str(recheck.get("status") or "needs_review"))
        if summary.get("stale_count"):
            blockers.append("recheck_stale")
        if int(summary.get("manual_review_count") or 0) < int(summary.get("item_count") or 0):
            blockers.append("manual_recheck_missing")
        if summary.get("needs_fix_count") or summary.get("rejected_count"):
            blockers.append("recheck_not_accepted")
        if summary.get("test_fake_count"):
            blockers.append("test_fake_audio_not_release_ready")
        if int(summary.get("release_ready_audio_count") or 0) < int(summary.get("item_count") or 0):
            blockers.append("audio_recheck_not_release_ready")
    return sorted(set(blockers)), warnings

def _closeout_summary(sprint: DomainDocument, recheck: DomainDocument | None, status: str) -> DomainDocument:
    items = sprint.get("items", [])
    recheck_summary = _recheck_summary((recheck or {}).get("items", []), str((recheck or {}).get("status") or "missing")) if recheck else {"item_count": 0, "manual_review_count": 0, "test_fake_count": 0, "release_ready_audio_count": 0, "accepted_count": 0, "needs_fix_count": 0, "rejected_count": 0}
    return {
        "status": status,
        "fix_item_count": len(items),
        "selected_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "resolved_count": recheck_summary.get("accepted_count", 0),
        "unresolved_count": len(items) - int(recheck_summary.get("accepted_count") or 0),
        "manual_recheck_count": recheck_summary.get("manual_review_count", 0),
        "test_fake_count": recheck_summary.get("test_fake_count", 0),
        "release_ready_audio_count": recheck_summary.get("release_ready_audio_count", 0),
    }

def _recheck_status(items: list[DomainDocument]) -> str:
    summary = _recheck_summary(items, "needs_review")
    if summary["stale_count"]:
        return "stale"
    if summary["manual_review_count"] < summary["item_count"]:
        return "needs_review"
    if summary["rejected_count"]:
        return "failed"
    if summary["needs_fix_count"]:
        return "needs_fix"
    return "passed"

def _recheck_summary(items: list[DomainDocument], status: str) -> DomainDocument:
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    return {
        "status": status,
        "item_count": len(items),
        "manual_review_count": sum(1 for review in reviews if _as_document(review).get("review_mode") == "manual"),
        "accepted_count": sum(1 for review in reviews if _as_document(review).get("status") == "accepted"),
        "needs_fix_count": sum(1 for review in reviews if _as_document(review).get("status") == "needs_fix"),
        "rejected_count": sum(1 for review in reviews if _as_document(review).get("status") == "rejected"),
        "stale_count": sum(1 for item in items if item.get("stale")),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake" or item.get("renderer", {}).get("source_runner_kind") == "test_fake"),
        "release_ready_audio_count": sum(1 for item in items if item.get("renderer", {}).get("release_ready") is True),
    }

def _sprint_summary(items: list[DomainDocument], status: str) -> DomainDocument:
    return {
        "status": status,
        "issue_count": len(items),
        "high_or_critical_count": sum(1 for item in items if item.get("severity") in HIGH_SEVERITIES),
        "candidate_count": sum(len(item.get("candidates") or []) for item in items),
        "selected_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "resolved_count": sum(1 for item in items if item.get("status") == "resolved"),
        "needs_recheck_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake" or item.get("renderer", {}).get("source_runner_kind") == "test_fake"),
    }

def _sprint_warnings(items: list[DomainDocument]) -> list[str]:
    warnings = []
    if any(item.get("renderer", {}).get("runner_kind") == "test_fake" for item in items):
        warnings.append("test_fake_audio_not_release_ready")
    return warnings

def _issue_index_row(item: DomainDocument) -> DomainDocument:
    reasons = [str(item.get("severity") or "medium"), str(item.get("review_status") or "marker")]
    if item.get("renderer", {}).get("runner_kind") == "test_fake":
        reasons.append("test_fake_source")
    return {"fix_item_id": item.get("fix_item_id"), "priority": item.get("priority"), "category": item.get("category"), "severity": item.get("severity"), "status": item.get("status"), "reason": reasons}

def _top_category(items: list[DomainDocument]) -> str | None:
    counts: dict[str, int] = {}
    for item in items:
        category = str(item.get("category") or "")
        counts[category] = counts.get(category, 0) + 1
    return max(counts.items(), key=lambda row: row[1])[0] if counts else None

def _public_sprint(sprint: DomainDocument) -> DomainDocument:
    public = {key: value for key, value in sprint.items() if key != "items"}
    public["items"] = [_public_item(item) for item in sprint.get("items", [])]
    return public

def _public_item(item: DomainDocument) -> DomainDocument:
    return dict(item)

def _fix_item_source(item: DomainDocument) -> DomainDocument:
    return {"source_marker": item.get("source_marker"), "artifact_hashes": item.get("artifact_hashes"), "renderer": item.get("renderer"), "selected_candidate_id": item.get("selected_candidate_id")}

def _review_core(review: DomainDocument) -> DomainDocument:
    return {key: review.get(key) for key in ("status", "preferred", "rating", "rating_delta", "review_mode", "playback_confirmed", "reviewer")}

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _rel_to_sprint(path: Path, sprint_dir: Path) -> str:
    return path.resolve().relative_to(sprint_dir.resolve()).as_posix()

def _bounded(value: object, limit: int = 240) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    return text[:limit]

def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(f"{prefix}-") or any(ch in text for ch in "/\\:"):
        raise AudioFixSprintValidationError(f"Invalid {prefix} id.")
    return text

def _append_event(path: Path, event: str, payload: DomainDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"created_at": now_iso(), "event": event, "payload": payload}
    row["event_hash"] = stable_hash(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

def _style_for_category(category: str) -> str:
    if category in {"mix_balance", "mastering"}:
        return "balanced instrumental pop"
    if category in {"timing", "performance"}:
        return "tight rhythmic instrumental"
    if category == "arrangement":
        return "clear structured instrumental"
    return "instrumental demo"
