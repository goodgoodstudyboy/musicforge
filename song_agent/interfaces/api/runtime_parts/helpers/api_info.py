from __future__ import annotations

from typing import Protocol

from song_agent.platform.contracts import JsonDocument, as_document as _as_document
from song_agent.platform.contracts.coercion import as_int as _as_int
from song_agent.platform.contracts.documents import normalize_json_value

from song_agent.interfaces.bootstrap.api.core import AuthConfig, Path, __version__, datetime, json, os, timezone, webbrowser

from song_agent.interfaces.bootstrap.api.creation_quality import SprintActionItem, SprintActionQueue, StemManifest, read_json, sanitize_metadata

from song_agent.interfaces.api.runtime_parts.core import RUNS_DIR


class _ReviewDecisionReportPort(Protocol):
    def read_decision_report(self, task_id: str) -> JsonDocument: ...

def api_info(
    auth_config: AuthConfig | None = None,
    *,
    authorized: bool = True,
) -> JsonDocument:
    auth_required = bool(auth_config and auth_config.enabled)
    public_info: JsonDocument = {
        "app": "MusicForge",
        "version": __version__,
        "auth_required": auth_required,
    }
    if auth_required and not authorized:
        return public_info
    return {
        **public_info,
        "cwd": str(Path.cwd()),
        "runs_dir": str(RUNS_DIR),
        "mode": "local-deterministic",
        "provider": {"enabled": False, "summary": "Local deterministic composer"},
    }

def api_template() -> JsonDocument:
    return {
        "defaults": {
            "title": "Rainy Convenience Store",
            "language": "zh",
            "style": "city pop, soft rock, warm synths, clean electric guitar",
            "theme": "a person remembers an old friend during a rainy night in the city",
            "duration_seconds": 180,
            "vocal_mode": "guide_melody",
            "tempo_bpm": 92,
            "key": "C major",
        },
        "presets": [
            {
                "name": "City Pop 120s",
                "style": "city pop, soft rock, warm synths, clean electric guitar",
                "duration_seconds": 120,
                "tempo_bpm": 92,
                "key": "C major",
            },
            {
                "name": "Lo-fi Loop 60s",
                "style": "lo-fi hip hop, mellow keys, dusty drums",
                "duration_seconds": 60,
                "tempo_bpm": 78,
                "key": "A minor",
            },
            {
                "name": "Game Battle Loop 45s",
                "style": "game battle loop, synth bass, tight drums",
                "duration_seconds": 45,
                "tempo_bpm": 132,
                "key": "D minor",
            },
        ],
    }

def _artifact_kind(path: Path) -> str:
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".jsonl":
        return "events"
    if path.suffix == ".mid":
        return "midi"
    if path.suffix == ".wav":
        return "audio"
    return "file"

def _artifact_dict(path: Path) -> JsonDocument:
    return {
        "name": path.name,
        "path": str(path),
        "kind": _artifact_kind(path),
        "size": path.stat().st_size,
        "size_bytes": path.stat().st_size,
    }

def discover_artifacts(run_dir: Path) -> list[JsonDocument]:
    artifacts: list[JsonDocument] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            artifacts.append(
                _artifact_dict(path)
            )
    return artifacts

def open_folder(path: Path) -> None:
    startfile = getattr(os, "startfile", None)
    if os.name == "nt" and callable(startfile):
        startfile(path)
        return
    webbrowser.open(path.resolve().as_uri())

def _build_summary(plan_path: Path, midi_path: Path) -> JsonDocument:
    plan = read_json(plan_path)
    tracks = plan.get("tracks", [])
    sections = plan.get("sections", [])
    return {
        "title": plan.get("title"),
        "tempo_bpm": plan.get("tempo_bpm"),
        "key": plan.get("key"),
        "meter": plan.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(track.get("notes", [])) for track in tracks),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
    }

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _build_validator_report(plan_path: Path, midi_path: Path) -> JsonDocument:
    plan = read_json(plan_path)
    return {
        "status": "passed",
        "checks": [
            "song_request_schema",
            "song_plan_schema",
            "song_plan_validation",
            "midi_render",
        ],
        "title": plan.get("title"),
        "midi_path": str(midi_path),
        "midi_exists": midi_path.exists(),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
        "checked_at": _utc_now(),
    }

def _usage_int(usage: JsonDocument, field_name: str) -> int:
    value = usage.get(field_name)
    if value is None:
        return 0
    try:
        return max(0, _as_int(value))
    except (TypeError, ValueError):
        return 0

def _provider_usage_record(
    *,
    config_snapshot: JsonDocument,
    operation: str,
    template_id: str,
    started_at: str,
    status: str,
    provider_usage: JsonDocument | None = None,
    request_id: object = None,
) -> JsonDocument:
    provider_usage = provider_usage or {}
    prompt_tokens = _usage_int(provider_usage, "prompt_tokens")
    completion_tokens = _usage_int(provider_usage, "completion_tokens")
    total_tokens = _usage_int(provider_usage, "total_tokens") or prompt_tokens + completion_tokens
    return {
        "provider_type": config_snapshot.get("wire_api") or "unknown",
        "model": config_snapshot.get("model") or "",
        "operation": operation,
        "template_id": template_id,
        "started_at": started_at,
        "completed_at": _utc_now() if status != "queued" else None,
        "latency_ms": None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": None,
        "request_id": None if request_id is None else str(request_id),
        "status": status,
    }

def _try_read_review_decision_report(
    task_store: _ReviewDecisionReportPort,
    task_id: str,
) -> JsonDocument:
    try:
        return task_store.read_decision_report(task_id)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}

def _review_sprints_list_summary(sprints: list[JsonDocument]) -> JsonDocument:
    statuses: dict[str, int] = {}
    total_conflicts = 0
    blocking_conflicts = 0
    for sprint in sprints:
        status = str(sprint.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        summary = _as_document(sprint.get("summary"))
        counts = _as_document(summary.get("counts"))
        total_conflicts += _as_int(counts.get("conflict_count") or 0)
        blocking_conflicts += _as_int(counts.get("blocking_conflict_count") or 0)
    return sanitize_metadata(
        {
            "total": len(sprints),
            "statuses": normalize_json_value(statuses),
            "conflict_count": total_conflicts,
            "blocking_conflict_count": blocking_conflicts,
        }
    )

def _action_queue_run_sort_key(item: SprintActionItem) -> tuple[int, int, int, str]:
    order = {
        "refresh_conflicts": 0,
        "refresh_recommendations": 1,
        "save_recommended_context_pack": 2,
        "generate_local_candidates": 3,
        "generate_provider_candidates": 4,
        "refresh_decision_report": 5,
    }.get(item.action, 9)
    return (order, int(item.rank or 9999), -int(item.priority or 0), item.item_id)

def _select_action_queue_items(queue: SprintActionQueue, selected_ids: list[str], *, rerun_failed: bool = False) -> list[SprintActionItem]:
    selected = set(selected_ids)
    items = []
    for item in queue.items:
        if selected and item.item_id not in selected:
            continue
        if item.status == "pending" or (rerun_failed and item.status == "failed"):
            items.append(item)
    return sorted(items, key=_action_queue_run_sort_key)

def _audio_report(audio_path: Path) -> JsonDocument:
    return {
        "exists": audio_path.exists(),
        "path": str(audio_path),
        "size_bytes": audio_path.stat().st_size if audio_path.exists() else 0,
    }

def _stem_audio_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    statuses = {stem.audio_status for stem in manifest.stems}
    if statuses <= {"completed", "skipped"}:
        return "completed"
    if "failed" in statuses and ("completed" in statuses or "skipped" in statuses):
        return "partial_failed"
    if "failed" in statuses:
        return "failed"
    if "completed" in statuses:
        return "partial_completed"
    return "not_started"

def _stem_midi_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if all(stem.midi_exists or stem.audio_status == "skipped" for stem in manifest.stems):
        return "completed"
    if any(stem.midi_exists for stem in manifest.stems):
        return "partial_failed"
    return "failed"

def _stem_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if any(stem.audio_exists for stem in manifest.stems):
        return _stem_audio_manifest_status(manifest)
    if any(stem.midi_exists for stem in manifest.stems):
        return _stem_midi_manifest_status(manifest)
    return "not_started"

def _manifest_response(
    job_id: str,
    manifest: StemManifest,
    *,
    status: str | None = None,
) -> JsonDocument:
    return {
        "job_id": job_id,
        "status": status or _stem_manifest_status(manifest),
        "manifest": manifest.to_dict(),
    }

__all__ = ['_action_queue_run_sort_key', '_artifact_dict', '_artifact_kind', '_audio_report', '_build_summary', '_build_validator_report', '_manifest_response', '_provider_usage_record', '_review_sprints_list_summary', '_select_action_queue_items', '_stem_audio_manifest_status', '_stem_manifest_status', '_stem_midi_manifest_status', '_try_read_review_decision_report', '_usage_int', '_utc_now', 'api_info', 'api_template', 'discover_artifacts', 'open_folder']
