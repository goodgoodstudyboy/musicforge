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
ReviewTaskError = _make_deferred_global('ReviewTaskError')
ReviewTaskStateError = _make_deferred_global('ReviewTaskStateError')
_append_event = _make_deferred_global('_append_event')
_candidate_artifacts = _make_deferred_global('_candidate_artifacts')
_ensure_candidate_current = _make_deferred_global('_ensure_candidate_current')
_lock_for_project = _make_deferred_global('_lock_for_project')
_priority = _make_deferred_global('_priority')
_task_summary = _make_deferred_global('_task_summary')
_task_title = _make_deferred_global('_task_title')
item = _make_deferred_global('item')
review_snapshot = _make_deferred_global('review_snapshot')
review_task_target = _make_deferred_global('review_task_target')
validate_review_candidate_id = _make_deferred_global('validate_review_candidate_id')
validate_review_task_id = _make_deferred_global('validate_review_task_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReviewCandidate, ReviewTask, ReviewTaskError, ReviewTaskStateError, _append_event, _candidate_artifacts, _ensure_candidate_current, _lock_for_project
    global _priority, _task_summary, _task_title, item, review_snapshot, review_task_target, validate_review_candidate_id
    global validate_review_task_id
    ReviewCandidate = namespace.get('ReviewCandidate', ReviewCandidate)
    ReviewTask = namespace.get('ReviewTask', ReviewTask)
    ReviewTaskError = namespace.get('ReviewTaskError', ReviewTaskError)
    ReviewTaskStateError = namespace.get('ReviewTaskStateError', ReviewTaskStateError)
    _append_event = namespace.get('_append_event', _append_event)
    _candidate_artifacts = namespace.get('_candidate_artifacts', _candidate_artifacts)
    _ensure_candidate_current = namespace.get('_ensure_candidate_current', _ensure_candidate_current)
    _lock_for_project = namespace.get('_lock_for_project', _lock_for_project)
    _priority = namespace.get('_priority', _priority)
    _task_summary = namespace.get('_task_summary', _task_summary)
    _task_title = namespace.get('_task_title', _task_title)
    item = namespace.get('item', item)
    review_snapshot = namespace.get('review_snapshot', review_snapshot)
    review_task_target = namespace.get('review_task_target', review_task_target)
    validate_review_candidate_id = namespace.get('validate_review_candidate_id', validate_review_candidate_id)
    validate_review_task_id = namespace.get('validate_review_task_id', validate_review_task_id)
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




class ReviewTaskStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.root = self.project_dir / "review-tasks"
        self.lock = _lock_for_project(self.project_dir)

    def create_task(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_plan: SongPlan,
        preview: object,
        audition: EditorAuditionManifest,
        audition_plan: SongPlan,
        payload: DomainDocument | None = None,
        previous: DomainDocument | None = None,
        now: str | None = None,
    ) -> ReviewTask:
        payload = _as_document(payload)
        now = now or now_iso()
        review = _as_document(audition.review)
        status = str(review.get("status") or "unreviewed")
        rating = int(review.get("rating") or 0)
        if status == "unreviewed" and rating <= 0 and not review.get("notes") and not review.get("markers"):
            raise ReviewTaskStateError("Audition review is missing.")
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            task_id, task_dir = self._reserve_task_dir()
            target = review_task_target(parent_plan, audition, review)
            source = sanitize_metadata(
                {
                    "source_type": "audition_review",
                    "previous_task_id": (previous or {}).get("previous_task_id"),
                    "previous_candidate_id": (previous or {}).get("previous_candidate_id"),
                    "previous_applied_version_id": (previous or {}).get("previous_applied_version_id"),
                    "audition_source": audition.source,
                    "track_mode": audition.track_mode,
                    "track_ids": list(audition.track_ids),
                    "audition_range": dict(audition.range or {}),
                }
            )
            snapshot = review_snapshot(review)
            task = ReviewTask.from_dict(
                {
                    "schema_version": REVIEW_TASK_SCHEMA_VERSION,
                    "task_id": task_id,
                    "project_id": project_id,
                    "parent_version_id": parent_version_id,
                    "preview_id": audition.preview_id,
                    "audition_id": audition.audition_id,
                    "status": "open",
                    "priority": _priority(snapshot),
                    "title": payload.get("title") or _task_title(snapshot, target),
                    "summary": _task_summary(snapshot, target),
                    "source": source,
                    "review_snapshot": snapshot,
                    "target": target,
                    "hashes": {
                        "parent_plan_hash": song_plan_hash(parent_plan),
                        "audition_plan_hash": song_plan_hash(audition_plan),
                        "source_plan_hash": audition.source_plan_hash or song_plan_hash(audition_plan),
                        "base_plan_hash": getattr(preview, "base_plan_hash", ""),
                    },
                    "counts": {"candidate_count": 0, "ready_candidate_count": 0, "failed_candidate_count": 0},
                    "created_at": now,
                    "updated_at": now,
                }
            )
            try:
                write_json(task_dir / "task.json", task.to_dict())
                _append_event(task_dir, "review_task_created", {"preview_id": task.preview_id, "audition_id": task.audition_id}, now)
            except Exception:
                if task_dir.exists() and not (task_dir / "task.json").exists():
                    shutil.rmtree(task_dir)
                raise
            return task

    def list_tasks(self, *, include_archived: bool = False, status: str | None = None) -> list[ReviewTask]:
        if not self.root.exists():
            return []
        tasks = []
        for path in self.root.glob("review-task-*/task.json"):
            try:
                task = ReviewTask.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if task.status == "archived" and not include_archived:
                continue
            if status and task.status != status:
                continue
            tasks.append(task)
        return sorted(tasks, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_task(self, task_id: str) -> ReviewTask:
        path = self.task_dir(task_id) / "task.json"
        if not path.exists():
            raise FileNotFoundError(task_id)
        return ReviewTask.from_dict(read_json(path))

    def update_task(self, task: ReviewTask, *, event: str | None = None, payload: DomainDocument | None = None, now: str | None = None) -> ReviewTask:
        now = now or now_iso()
        updated = ReviewTask.from_dict({**task.to_dict(), "updated_at": now})
        with self.lock:
            write_json(self.task_dir(updated.task_id) / "task.json", updated.to_dict())
            if event:
                _append_event(self.task_dir(updated.task_id), event, payload or {}, now)
        return updated

    def read_events(self, task_id: str) -> list[DomainDocument]:
        path = self.task_dir(task_id) / "events.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def decision_report_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "decision-report.json"

    def read_decision_report(self, task_id: str) -> DomainDocument:
        path = self.decision_report_path(task_id)
        if not path.exists():
            raise FileNotFoundError(task_id)
        data = read_json(path)
        if not isinstance(data, dict):
            raise ReviewTaskError("Review decision report must be an object.")
        return sanitize_metadata(data)

    def write_decision_report(self, task: ReviewTask, report: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        data = sanitize_metadata(dict(report or {}))
        with self.lock:
            write_json(self.decision_report_path(task.task_id), data)
            _append_event(self.task_dir(task.task_id), "review_task_decision_report_written", {"candidate_count": data.get("candidate_count"), "recommended_candidate_id": data.get("recommended_candidate_id")}, now)
        return data

    def judge_report_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "judge-report.json"

    def read_judge_report(self, task_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.judge_report_path(task_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(task_id)
        data = read_json(path)
        if not isinstance(data, dict):
            raise ReviewTaskError("Review judge report must be an object.")
        return sanitize_metadata(data)

    def write_judge_report(self, task: ReviewTask, report: DomainDocument, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        data = sanitize_metadata(dict(report or {}))
        with self.lock:
            write_json(self.judge_report_path(task.task_id), data)
            _append_event(
                self.task_dir(task.task_id),
                "review_task_judge_report_written",
                {"recommended_candidate_id": data.get("recommended_candidate_id"), "status": data.get("status")},
                now,
            )
        return data

    def judge_provider_usage_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "judge-provider-usage.json"

    def create_candidate(
        self,
        *,
        task: ReviewTask,
        candidate: ReviewCandidate,
        candidate_plan: SongPlan | None,
        validator: DomainDocument,
        summary: DomainDocument,
        render_midi_file: bool = True,
        now: str | None = None,
    ) -> ReviewCandidate:
        now = now or now_iso()
        with self.lock:
            candidate_id, candidate_dir = self._reserve_candidate_dir(task.task_id)
            data = {
                **candidate.to_dict(),
                "candidate_id": candidate_id,
                "created_at": now,
                "updated_at": now,
                "midi_url": f"/api/projects/{task.project_id}/review-tasks/{task.task_id}/candidates/{candidate_id}/midi",
                "audio_url": f"/api/projects/{task.project_id}/review-tasks/{task.task_id}/candidates/{candidate_id}/audio",
            }
            if candidate_plan is not None:
                data["hashes"] = {**data.get("hashes", {}), "candidate_plan_hash": song_plan_hash(candidate_plan)}
                data["artifacts"] = _candidate_artifacts(task.task_id, candidate_id)
            stored = ReviewCandidate.from_dict(data)
            try:
                write_json(candidate_dir / "candidate.json", stored.to_dict())
                if candidate_plan is not None:
                    write_json(candidate_dir / "candidate-song-plan.json", candidate_plan.to_dict())
                    write_json(candidate_dir / "validator-report.json", validator)
                    write_json(candidate_dir / "summary.json", summary)
                    if render_midi_file:
                        stored = self.render_candidate_midi(task, stored, candidate_plan=candidate_plan, now=now)
                write_json(candidate_dir / "candidate.json", stored.to_dict())
                _append_event(candidate_dir, "review_candidate_created", {"status": stored.status, "strategy": stored.strategy}, now)
            except Exception:
                if candidate_dir.exists() and not (candidate_dir / "candidate.json").exists():
                    shutil.rmtree(candidate_dir)
                raise
            return stored

    def read_candidate(self, task_id: str, candidate_id: str) -> ReviewCandidate:
        path = self.candidate_dir(task_id, candidate_id) / "candidate.json"
        if not path.exists():
            raise FileNotFoundError(candidate_id)
        return ReviewCandidate.from_dict(read_json(path))

    def list_candidates(self, task_id: str) -> list[ReviewCandidate]:
        root = self.task_dir(task_id) / "candidates"
        if not root.exists():
            return []
        candidates = []
        for path in root.glob("revcand-*/candidate.json"):
            try:
                candidate = ReviewCandidate.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if candidate.status != "deleted":
                candidates.append(candidate)
        return sorted(candidates, key=lambda item: (item.rank or 999, item.candidate_id))

    def update_candidate(self, candidate: ReviewCandidate, *, event: str | None = None, payload: DomainDocument | None = None, now: str | None = None) -> ReviewCandidate:
        now = now or now_iso()
        updated = ReviewCandidate.from_dict({**candidate.to_dict(), "updated_at": now})
        with self.lock:
            candidate_dir = self.candidate_dir(updated.task_id, updated.candidate_id)
            write_json(candidate_dir / "candidate.json", updated.to_dict())
            if event:
                _append_event(candidate_dir, event, payload or {}, now)
        return updated

    def update_counts(self, task: ReviewTask, *, now: str | None = None) -> ReviewTask:
        candidates = self.list_candidates(task.task_id)
        ready = len([item for item in candidates if item.status in {"ready", "applied"}])
        failed = len([item for item in candidates if item.status == "failed"])
        status = task.status
        if status == "open" and ready:
            status = "candidate_ready"
        updated = ReviewTask.from_dict(
            {
                **task.to_dict(),
                "status": status,
                "counts": {"candidate_count": len(candidates), "ready_candidate_count": ready, "failed_candidate_count": failed},
                "updated_at": now or now_iso(),
            }
        )
        write_json(self.task_dir(updated.task_id) / "task.json", updated.to_dict())
        return updated

    def rank_candidates(self, task: ReviewTask) -> list[ReviewCandidate]:
        candidates = self.list_candidates(task.task_id)
        ready = [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]
        ready = sorted(ready, key=lambda item: (-int(item.scores.get("combined") or 0), STRATEGIES.index(item.strategy) if item.strategy in STRATEGIES else 99, item.candidate_id))
        ranked_by_id = {candidate.candidate_id: index + 1 for index, candidate in enumerate(ready)}
        updated = []
        for candidate in candidates:
            rank = ranked_by_id.get(candidate.candidate_id, 0)
            if rank != candidate.rank:
                candidate = self.update_candidate(ReviewCandidate.from_dict({**candidate.to_dict(), "rank": rank}))
            updated.append(candidate)
        return sorted(updated, key=lambda item: (item.rank or 999, item.candidate_id))

    def render_candidate_midi(self, task: ReviewTask, candidate: ReviewCandidate, *, candidate_plan: SongPlan | None = None, now: str | None = None) -> ReviewCandidate:
        _ensure_candidate_current(task, candidate)
        plan = candidate_plan or self.read_candidate_plan(task.task_id, candidate.candidate_id)
        midi_path = self.candidate_midi_path(task.task_id, candidate.candidate_id)
        try:
            render_midi(plan, midi_path)
        except Exception as exc:
            failed = ReviewCandidate.from_dict({**candidate.to_dict(), "midi_status": "failed", "error": sanitize_sensitive_text(str(exc)), "midi_size_bytes": 0, "updated_at": now or now_iso()})
            if (self.candidate_dir(candidate.task_id, candidate.candidate_id) / "candidate.json").exists():
                self.update_candidate(failed, event="review_candidate_midi_failed", payload={"error": failed.error}, now=now)
            return failed
        updated = ReviewCandidate.from_dict({**candidate.to_dict(), "midi_status": "completed", "midi_size_bytes": midi_path.stat().st_size, "error": None, "updated_at": now or now_iso()})
        if (self.candidate_dir(candidate.task_id, candidate.candidate_id) / "candidate.json").exists():
            self.update_candidate(updated, event="review_candidate_midi_rendered", payload={"size_bytes": updated.midi_size_bytes}, now=now)
        return updated

    def render_candidate_audio(self, task: ReviewTask, candidate: ReviewCandidate, config: RendererConfig, *, now: str | None = None) -> ReviewCandidate:
        _ensure_candidate_current(task, candidate)
        midi_path = self.candidate_midi_path(task.task_id, candidate.candidate_id)
        if not midi_path.exists():
            candidate = self.render_candidate_midi(task, candidate, now=now)
        try:
            wav_path = render_audio(self.candidate_midi_path(task.task_id, candidate.candidate_id), self.candidate_audio_path(task.task_id, candidate.candidate_id), config)
        except RendererError as exc:
            failed = ReviewCandidate.from_dict({**candidate.to_dict(), "audio_status": "failed", "audio_error": sanitize_sensitive_text(str(exc)), "audio_size_bytes": 0})
            return self.update_candidate(failed, event="review_candidate_audio_failed", payload={"error": failed.audio_error}, now=now)
        updated = ReviewCandidate.from_dict({**candidate.to_dict(), "audio_status": "completed", "audio_error": None, "audio_size_bytes": wav_path.stat().st_size})
        return self.update_candidate(updated, event="review_candidate_audio_rendered", payload={"size_bytes": updated.audio_size_bytes}, now=now)

    def read_candidate_plan(self, task_id: str, candidate_id: str) -> SongPlan:
        return SongPlan.from_dict(read_json(self.candidate_dir(task_id, candidate_id) / "candidate-song-plan.json"))

    def candidate_midi_path(self, task_id: str, candidate_id: str) -> Path:
        return self._safe_render_path(task_id, candidate_id, "song.mid")

    def candidate_audio_path(self, task_id: str, candidate_id: str) -> Path:
        return self._safe_render_path(task_id, candidate_id, "song.wav")

    def candidate_dir(self, task_id: str, candidate_id: str) -> Path:
        task_id = validate_review_task_id(task_id)
        candidate_id = validate_review_candidate_id(candidate_id)
        base = (self.task_dir(task_id) / "candidates").resolve()
        target = (base / candidate_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside review candidates.") from exc
        return target

    def task_dir(self, task_id: str) -> Path:
        task_id = validate_review_task_id(task_id)
        base = self.root.resolve()
        target = (base / task_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside review tasks.") from exc
        return target

    def _reserve_task_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            task_id = f"review-task-{index:03d}"
            task_dir = self.task_dir(task_id)
            try:
                task_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return task_id, task_dir
        raise RuntimeError("Could not allocate review task id.")

    def _reserve_candidate_dir(self, task_id: str) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            candidate_id = f"revcand-{index:03d}"
            candidate_dir = self.candidate_dir(task_id, candidate_id)
            try:
                candidate_dir.mkdir(parents=True, exist_ok=False)
                (candidate_dir / "renders").mkdir(parents=True, exist_ok=True)
            except FileExistsError:
                continue
            return candidate_id, candidate_dir
        raise RuntimeError("Could not allocate review candidate id.")

    def _safe_render_path(self, task_id: str, candidate_id: str, filename: str) -> Path:
        if filename not in {"song.mid", "song.wav"}:
            raise ValueError("Invalid review candidate artifact.")
        candidate = self.read_candidate(task_id, candidate_id)
        artifact_key = "midi_path" if filename.endswith(".mid") else "audio_path"
        artifact = str(candidate.artifacts.get(artifact_key) or "")
        expected_suffix = f"review-tasks/{task_id}/candidates/{candidate_id}/renders/{filename}"
        if artifact and artifact.replace("\\", "/") != expected_suffix:
            raise ValueError("Review candidate artifact path is unsafe.")
        base = (self.candidate_dir(task_id, candidate_id) / "renders").resolve()
        target = (base / filename).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside candidate renders.") from exc
        if target.is_symlink():
            raise ValueError("Refusing to serve symlink candidate artifact.")
        return target
