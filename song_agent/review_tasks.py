from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from song_agent.candidate_scoring import score_provider_edit_candidate
from song_agent.edits import EditIntent, EditedSongPlanResult, apply_edit_intent, validate_edit_intent
from song_agent.editor_audition import EditorAuditionManifest
from song_agent.music_quality import attach_quality
from song_agent.projectio import read_json, write_json
from song_agent.provider import ProviderConfig
from song_agent.provider_edits import ProviderEditPatch, apply_provider_edit_patch, generate_provider_edit_candidates, provider_patch_to_intents
from song_agent.prompt_templates import PromptTemplate
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.renderers.audio import RendererConfig, RendererError, render_audio
from song_agent.renderers.midi import render_midi
from song_agent.review_edits import build_review_edit
from song_agent.schemas.song import SongPlan, SongSection, TrackPlan
from song_agent.song_editor import song_plan_hash


REVIEW_TASK_SCHEMA_VERSION = 1
REVIEW_CANDIDATE_SCHEMA_VERSION = 1
REVIEW_DECISION_REPORT_SCHEMA_VERSION = 1
TASK_ID_PATTERN = re.compile(r"^review-task-[0-9]{3,6}$")
CANDIDATE_ID_PATTERN = re.compile(r"^revcand-[0-9]{3,6}$")
TASK_STATUSES = {"open", "candidate_ready", "applied", "resolved", "needs_more_work", "archived", "stale"}
CANDIDATE_STATUSES = {"queued", "ready", "failed", "applied", "stale", "deleted"}
STRATEGIES = ("conservative", "balanced", "bold")
PROVIDER_STRATEGY = "provider"
TERMINAL_TASK_STATUSES = {"resolved", "archived", "stale", "needs_more_work"}
FIX_MARKERS = {"fix", "issue", "drop"}
PRESERVE_MARKERS = {"keep", "hook"}
_LOCKS_GUARD = threading.RLock()
_STORE_LOCKS: dict[str, threading.RLock] = {}


class ReviewTaskError(ValueError):
    pass


class ReviewTaskStateError(ReviewTaskError):
    pass


@dataclass(frozen=True)
class ReviewTask:
    schema_version: int
    task_id: str
    project_id: str
    parent_version_id: str
    preview_id: str
    audition_id: str
    status: str
    priority: int
    title: str
    summary: str
    source: dict[str, Any] = field(default_factory=dict)
    review_snapshot: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    selected_candidate_id: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None
    resolved_at: str | None = None
    resolution_note: str = ""
    follow_up_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewTask":
        if not isinstance(data, dict):
            raise ReviewTaskError("review task must be an object.")
        status = str(data.get("status") or "open")
        if status not in TASK_STATUSES:
            raise ReviewTaskError(f"status must be one of: {', '.join(sorted(TASK_STATUSES))}.")
        candidate_id = data.get("selected_candidate_id")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_TASK_SCHEMA_VERSION) or REVIEW_TASK_SCHEMA_VERSION),
            task_id=validate_review_task_id(str(data.get("task_id") or "review-task-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            preview_id=str(data.get("preview_id") or ""),
            audition_id=str(data.get("audition_id") or ""),
            status=status,
            priority=_clamp_int(data.get("priority"), 0, 100, 50),
            title=sanitize_sensitive_text(str(data.get("title") or ""))[:160],
            summary=sanitize_sensitive_text(str(data.get("summary") or ""))[:800],
            source=sanitize_metadata(dict(data.get("source") or {})),
            review_snapshot=sanitize_metadata(dict(data.get("review_snapshot") or {})),
            target=sanitize_metadata(dict(data.get("target") or {})),
            hashes={str(k): str(v) for k, v in dict(data.get("hashes") or {}).items()},
            counts={str(k): int(v) for k, v in dict(data.get("counts") or {}).items() if isinstance(v, (int, float, str))},
            selected_candidate_id=None if candidate_id in {None, ""} else validate_review_candidate_id(str(candidate_id)),
            applied_version_id=_optional_str(data.get("applied_version_id")),
            applied_job_id=_optional_str(data.get("applied_job_id")),
            resolved_at=_optional_str(data.get("resolved_at")),
            resolution_note=sanitize_sensitive_text(str(data.get("resolution_note") or ""))[:500],
            follow_up_task_id=None if not data.get("follow_up_task_id") else validate_review_task_id(str(data.get("follow_up_task_id"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewCandidate:
    schema_version: int
    candidate_id: str
    task_id: str
    project_id: str
    parent_version_id: str
    candidate_type: str
    strategy: str
    status: str
    rank: int = 0
    summary: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    intents: list[dict[str, Any]] = field(default_factory=list)
    patch: dict[str, Any] | None = None
    validator: dict[str, Any] = field(default_factory=dict)
    scores: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    midi_status: str = "not_started"
    midi_url: str | None = None
    midi_size_bytes: int = 0
    audio_status: str = "not_started"
    audio_url: str | None = None
    audio_size_bytes: int = 0
    audio_error: str | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewCandidate":
        if not isinstance(data, dict):
            raise ReviewTaskError("review candidate must be an object.")
        status = str(data.get("status") or "queued")
        if status not in CANDIDATE_STATUSES:
            raise ReviewTaskError(f"candidate status must be one of: {', '.join(sorted(CANDIDATE_STATUSES))}.")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_CANDIDATE_SCHEMA_VERSION) or REVIEW_CANDIDATE_SCHEMA_VERSION),
            candidate_id=validate_review_candidate_id(str(data.get("candidate_id") or "revcand-001")),
            task_id=validate_review_task_id(str(data.get("task_id") or "review-task-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            candidate_type=_candidate_type(data.get("candidate_type")),
            strategy=_strategy(data.get("strategy")),
            status=status,
            rank=max(0, int(data.get("rank") or 0)),
            summary=sanitize_sensitive_text(str(data.get("summary") or ""))[:800],
            source=sanitize_metadata(dict(data.get("source") or {})),
            intents=[EditIntent.from_dict(dict(item)).to_dict() for item in data.get("intents", []) if isinstance(item, dict)],
            patch=sanitize_metadata(dict(data["patch"])) if isinstance(data.get("patch"), dict) else None,
            validator=sanitize_metadata(dict(data.get("validator") or {})),
            scores=sanitize_metadata(dict(data.get("scores") or {})),
            warnings=[sanitize_sensitive_text(str(item)) for item in data.get("warnings", [])],
            artifacts={str(k): str(v) for k, v in dict(data.get("artifacts") or {}).items()},
            midi_status=str(data.get("midi_status") or "not_started"),
            midi_url=_optional_str(data.get("midi_url")),
            midi_size_bytes=max(0, int(data.get("midi_size_bytes") or 0)),
            audio_status=str(data.get("audio_status") or "not_started"),
            audio_url=_optional_str(data.get("audio_url")),
            audio_size_bytes=max(0, int(data.get("audio_size_bytes") or 0)),
            audio_error=None if data.get("audio_error") in {None, ""} else sanitize_sensitive_text(str(data.get("audio_error"))),
            hashes={str(k): str(v) for k, v in dict(data.get("hashes") or {}).items()},
            error=None if data.get("error") in {None, ""} else sanitize_sensitive_text(str(data.get("error"))),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        preview: Any,
        audition: EditorAuditionManifest,
        audition_plan: SongPlan,
        payload: dict[str, Any] | None = None,
        previous: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> ReviewTask:
        payload = payload if isinstance(payload, dict) else {}
        now = now or now_iso()
        review = audition.review if isinstance(audition.review, dict) else {}
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

    def update_task(self, task: ReviewTask, *, event: str | None = None, payload: dict[str, Any] | None = None, now: str | None = None) -> ReviewTask:
        now = now or now_iso()
        updated = ReviewTask.from_dict({**task.to_dict(), "updated_at": now})
        with self.lock:
            write_json(self.task_dir(updated.task_id) / "task.json", updated.to_dict())
            if event:
                _append_event(self.task_dir(updated.task_id), event, payload or {}, now)
        return updated

    def read_events(self, task_id: str) -> list[dict[str, Any]]:
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

    def read_decision_report(self, task_id: str) -> dict[str, Any]:
        path = self.decision_report_path(task_id)
        if not path.exists():
            raise FileNotFoundError(task_id)
        data = read_json(path)
        if not isinstance(data, dict):
            raise ReviewTaskError("Review decision report must be an object.")
        return sanitize_metadata(data)

    def write_decision_report(self, task: ReviewTask, report: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        data = sanitize_metadata(dict(report or {}))
        with self.lock:
            write_json(self.decision_report_path(task.task_id), data)
            _append_event(self.task_dir(task.task_id), "review_task_decision_report_written", {"candidate_count": data.get("candidate_count"), "recommended_candidate_id": data.get("recommended_candidate_id")}, now)
        return data

    def create_candidate(
        self,
        *,
        task: ReviewTask,
        candidate: ReviewCandidate,
        candidate_plan: SongPlan | None,
        validator: dict[str, Any],
        summary: dict[str, Any],
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

    def update_candidate(self, candidate: ReviewCandidate, *, event: str | None = None, payload: dict[str, Any] | None = None, now: str | None = None) -> ReviewCandidate:
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


def build_local_review_candidates(task: ReviewTask, parent_plan: SongPlan, *, strategies: list[str] | None = None) -> list[tuple[ReviewCandidate, SongPlan | None, dict[str, Any], dict[str, Any]]]:
    _ensure_task_open_for_generation(task)
    strategies = [str(item or "").strip() for item in (strategies or list(STRATEGIES))]
    strategies = [item for item in strategies if item in STRATEGIES]
    if not strategies:
        strategies = list(STRATEGIES)
    result = []
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
    asset_references: list[dict[str, Any]] | None = None,
    reference_references: list[dict[str, Any]] | None = None,
    client: Any | None = None,
) -> tuple[list[tuple[ReviewCandidate, SongPlan | None, dict[str, Any], dict[str, Any]]], dict[str, Any], str]:
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
    generated: list[tuple[ReviewCandidate, SongPlan | None, dict[str, Any], dict[str, Any]]] = []
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    if parent_plan is not None:
        ensure_task_current(task, parent_plan)
    parent_hash = task.hashes.get("parent_plan_hash") or (song_plan_hash(parent_plan) if parent_plan is not None else "")
    usable = [candidate for candidate in candidates if candidate.status in {"ready", "applied"}]
    ranked = sorted(usable, key=lambda item: (item.rank or 9999, -int(item.scores.get("combined") or 0), item.candidate_id))
    recommended = ranked[0] if ranked else None
    report = {
        "schema_version": REVIEW_DECISION_REPORT_SCHEMA_VERSION,
        "task_id": task.task_id,
        "project_id": task.project_id,
        "parent_version_id": task.parent_version_id,
        "parent_song_plan_hash": parent_hash,
        "created_at": now or now_iso(),
        "candidate_count": len(candidates),
        "recommended_candidate_id": recommended.candidate_id if recommended else None,
        "recommendation_reason": _recommendation_reason(recommended) if recommended else "No ready candidate is available.",
        "requires_manual_apply": True,
        "ranking": [_decision_rank_entry(candidate, index + 1) for index, candidate in enumerate(ranked)],
        "source_breakdown": review_candidate_source_breakdown(candidates),
        "risk_flags": _decision_risk_flags(task, candidates, recommended),
        "notes": sanitize_sensitive_text(notes)[:1000],
    }
    return sanitize_metadata(report)


def review_decision_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "task_id": report.get("task_id"),
            "recommended_candidate_id": report.get("recommended_candidate_id"),
            "candidate_count": report.get("candidate_count"),
            "requires_manual_apply": bool(report.get("requires_manual_apply", True)),
            "source_breakdown": report.get("source_breakdown") if isinstance(report.get("source_breakdown"), dict) else {},
            "risk_flags": report.get("risk_flags") if isinstance(report.get("risk_flags"), list) else [],
            "created_at": report.get("created_at"),
        }
    )


def review_candidate_source_breakdown(candidates: list[ReviewCandidate]) -> dict[str, Any]:
    provider = [candidate for candidate in candidates if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")]
    local = [candidate for candidate in candidates if candidate.candidate_type == "local_review_intents"]
    usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    models: set[str] = set()
    templates: set[str] = set()
    seen_usage_calls: set[tuple[str, str, str, int]] = set()
    for candidate in provider:
        source = candidate.source
        usage_data = source.get("usage") if isinstance(source.get("usage"), dict) else {}
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


def _decision_rank_entry(candidate: ReviewCandidate, rank: int) -> dict[str, Any]:
    scores = candidate.scores if isinstance(candidate.scores, dict) else {}
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


def _recommendation_reason(candidate: ReviewCandidate | None) -> str:
    if candidate is None:
        return "No ready candidate is available."
    score = int(candidate.scores.get("combined") or 0)
    source = "provider" if candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider") else candidate.strategy
    return sanitize_sensitive_text(f"Ranked first by combined review score ({score}) from {source} candidate {candidate.candidate_id}.")[:500]


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


def _provider_patch_summary(patch: dict[str, Any]) -> dict[str, Any]:
    operations = patch.get("operations") if isinstance(patch.get("operations"), list) else []
    return sanitize_metadata(
        {
            "schema_version": patch.get("schema_version"),
            "summary": patch.get("summary"),
            "operation_count": len(operations),
            "operations": [
                {
                    "op": operation.get("op"),
                    "section_name": operation.get("section_name"),
                    "track_name": operation.get("track_name"),
                    "preserve": operation.get("preserve") if isinstance(operation.get("preserve"), list) else [],
                }
                for operation in operations
                if isinstance(operation, dict)
            ],
            "warnings": patch.get("warnings") if isinstance(patch.get("warnings"), list) else [],
            "confidence": patch.get("confidence"),
        }
    )


def candidate_intents_for_strategy(task: ReviewTask, strategy: str) -> list[EditIntent]:
    strategy = _strategy(strategy)
    if strategy not in STRATEGIES:
        raise ReviewTaskError("Invalid local review candidate strategy.")
    target = task.target
    section_name = str(target.get("section_name") or "")
    track_name = str(target.get("track_name") or "")
    role = str(target.get("role") or "")
    snapshot = task.review_snapshot
    text = " ".join([str(snapshot.get("notes_excerpt") or ""), " ".join(str(tag) for tag in snapshot.get("tags", [])), str(snapshot.get("status") or "")]).lower()
    markers = [item for item in snapshot.get("markers", []) if isinstance(item, dict)]
    marker_kinds = {str(marker.get("kind") or "") for marker in markers}
    intents: list[EditIntent] = []

    if track_name and (_has_any(text, ("busy", "dense", "reduce", "less", "太满", "太密", "减少")) or role in {"bass", "drums"} or marker_kinds & FIX_MARKERS):
        scale = {"conservative": 0.84, "balanced": 0.72, "bold": 0.62}[strategy]
        strength = {"conservative": 3, "balanced": 4, "bold": 5}[strategy]
        intents.append(_intent("track_density", section_name=section_name, track_name=track_name, strength=strength, instruction=f"{strategy} review task density adjustment.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"density_scale": scale, "source": "review_task", "strategy": strategy}))

    wants_energy = _has_any(text, ("strong", "energy", "lift", "chorus", "更强", "能量", "高潮", "更炸")) or "drop" in marker_kinds
    if section_name and strategy in {"balanced", "bold"} and (wants_energy or strategy in {"balanced", "bold"}):
        strength = {"conservative": 6, "balanced": 7, "bold": 8}[strategy]
        intents.append(_intent("section_energy", section_name=section_name, strength=strength, instruction=f"{strategy} review task section lift.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"source": "review_task", "strategy": strategy}))

    if strategy == "bold" and not (marker_kinds & PRESERVE_MARKERS):
        if _has_any(text, ("hook", "melody", "旋律", "副歌")):
            intents.append(_intent("melody_variation", section_name=section_name, strength=5, instruction="Bold review task melody variation.", preserve=["tempo", "key", "structure", "harmony"], payload={"source": "review_task", "strategy": strategy}))
        elif _has_any(text, ("arrangement", "transition", "过渡", "编曲")):
            intents.append(_intent("arrangement_variation", section_name=section_name, track_name=track_name or None, strength=6, instruction="Bold review task arrangement variation.", preserve=["tempo", "key", "structure"], payload={"source": "review_task", "strategy": strategy}))
        elif track_name:
            intents.append(_intent("arrangement_variation", section_name=section_name, track_name=track_name, strength=6, instruction="Bold review task arrangement color.", preserve=["tempo", "key", "structure"], payload={"source": "review_task", "strategy": strategy, "instrument": f"{track_name} alt"}))

    if marker_kinds & PRESERVE_MARKERS and strategy != "conservative":
        intents = [intent for intent in intents if intent.edit_type != "melody_variation"]
    if not intents and section_name:
        intents.append(_intent("section_energy", section_name=section_name, strength=6, instruction=f"{strategy} review task fallback section lift.", preserve=["tempo", "key", "structure", "lyrics", "harmony"], payload={"source": "review_task", "strategy": strategy}))
    return intents[:4]


def apply_candidate_intents(parent_plan: SongPlan, intents: list[EditIntent]) -> EditedSongPlanResult:
    current = parent_plan
    summaries = []
    warnings: list[str] = []
    for intent in intents:
        validate_edit_intent(current, intent)
        result = apply_edit_intent(current, intent)
        current = result.plan
        summaries.append(result.summary)
        warnings.extend(result.warnings)
    plan = attach_quality(current)
    plan.validate()
    return EditedSongPlanResult(
        plan=plan,
        summary={
            "edit_source": "review_task_candidate",
            "operation_count": len(intents),
            "changed_sections": sorted({section for summary in summaries for section in summary.get("changed_sections", [])}),
            "changed_tracks": sorted({track for summary in summaries for track in summary.get("changed_tracks", [])}),
            "operations": summaries,
        },
        warnings=warnings,
    )


def review_task_target(parent_plan: SongPlan, audition: EditorAuditionManifest, review: dict[str, Any]) -> dict[str, Any]:
    markers = [item for item in review.get("markers", []) if isinstance(item, dict)]
    marker = _primary_marker(markers)
    range_data = audition.range if isinstance(audition.range, dict) else {}
    local_beat = _float_or_none(marker.get("beat") if marker else None)
    global_beat = None if local_beat is None else _range_start(range_data) + local_beat
    section = _section_from_range_or_marker(parent_plan, range_data, global_beat)
    text = _review_text(review, audition)
    track = _target_track(parent_plan, audition, text)
    return sanitize_metadata(
        {
            "range_mode": str(range_data.get("mode") or ""),
            "range_start_beat": _range_start(range_data),
            "local_marker_beat": local_beat,
            "global_marker_beat": global_beat,
            "section_name": section.name,
            "section_start_beat": _section_start(section),
            "section_end_beat": _section_end(section),
            "track_name": track.name if track else "",
            "track_id": _track_id(parent_plan, track) if track else "",
            "role": _role_for_track(track, text) if track else _role_from_text(text) or "",
            "marker_kind": str(marker.get("kind") or "") if marker else "",
        }
    )


def review_snapshot(review: dict[str, Any]) -> dict[str, Any]:
    markers = [
        {
            "marker_id": str(marker.get("marker_id") or ""),
            "beat": _float_or_none(marker.get("beat")),
            "kind": str(marker.get("kind") or ""),
            "severity": str(marker.get("severity") or "medium"),
            "label": sanitize_sensitive_text(str(marker.get("label") or ""))[:160],
        }
        for marker in review.get("markers", [])
        if isinstance(marker, dict)
    ]
    return sanitize_metadata(
        {
            "rating": int(review.get("rating") or 0),
            "status": str(review.get("status") or "unreviewed"),
            "favorite": bool(review.get("favorite", False)),
            "notes_excerpt": sanitize_sensitive_text(str(review.get("notes") or ""))[:500],
            "tags": [sanitize_sensitive_text(str(tag))[:40] for tag in review.get("tags", [])],
            "markers": markers,
            "marker_kinds": sorted({str(marker.get("kind") or "") for marker in markers if marker.get("kind")}),
            "asset_ids": [str(review.get("last_asset_id"))] if review.get("last_asset_id") else [],
        }
    )


def review_task_summary(task: ReviewTask, selected: ReviewCandidate | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "task_id": task.task_id,
            "status": task.status,
            "source_type": task.source.get("source_type"),
            "preview_id": task.preview_id,
            "audition_id": task.audition_id,
            "parent_version_id": task.parent_version_id,
            "target": {
                "section_name": task.target.get("section_name"),
                "track_name": task.target.get("track_name"),
                "global_marker_beat": task.target.get("global_marker_beat"),
            },
            "selected_candidate_id": task.selected_candidate_id,
            "applied_version_id": task.applied_version_id,
            "follow_up_task_id": task.follow_up_task_id,
            "summary": task.summary,
            "selected_candidate": review_candidate_summary(selected) if selected else {},
        }
    )


def review_candidate_summary(candidate: ReviewCandidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return sanitize_metadata(
        {
            "candidate_id": candidate.candidate_id,
            "candidate_type": candidate.candidate_type,
            "strategy": candidate.strategy,
            "rank": candidate.rank,
            "score": candidate.scores.get("combined"),
            "summary": candidate.summary,
        }
    )


def task_list_summary(tasks: list[ReviewTask]) -> dict[str, int]:
    summary = {"total": len(tasks), "open": 0, "candidate_ready": 0, "applied": 0, "resolved": 0, "needs_more_work": 0, "archived": 0, "stale": 0}
    for task in tasks:
        summary[task.status] = summary.get(task.status, 0) + 1
    return summary


def mark_task_resolved(task: ReviewTask, note: str = "", *, now: str | None = None) -> ReviewTask:
    if task.status != "applied":
        raise ReviewTaskStateError("Only applied review tasks can be resolved.")
    return ReviewTask.from_dict({**task.to_dict(), "status": "resolved", "resolved_at": now or now_iso(), "resolution_note": sanitize_sensitive_text(str(note or ""))[:500]})


def mark_task_archived(task: ReviewTask) -> ReviewTask:
    if task.status == "stale":
        raise ReviewTaskStateError("Stale review task cannot be archived here.")
    return ReviewTask.from_dict({**task.to_dict(), "status": "archived"})


def candidate_apply_metadata(task: ReviewTask, candidate: ReviewCandidate, result: EditedSongPlanResult, *, decision_report: dict[str, Any] | None = None) -> dict[str, Any]:
    primary = EditIntent.from_dict(candidate.intents[0])
    metadata = {
        "schema_version": 1,
        "project_id": task.project_id,
        "parent_version_id": task.parent_version_id,
        "edit_source": "review_task_candidate",
        **primary.to_dict(),
        "operation_count": len(candidate.intents),
        "summary": result.summary,
        "warnings": result.warnings,
        "review_task": review_task_summary(task, candidate),
        "review_candidate": review_candidate_summary(candidate),
        "review_edit": {
            "review_edit_id": f"{task.task_id}-candidate",
            "intent_count": len(candidate.intents),
            "confidence": min(0.95, max(0.1, float(candidate.scores.get("combined") or 0) / 100.0)),
        },
        "review_candidate_intents": [dict(intent) for intent in candidate.intents],
    }
    if candidate.source:
        metadata["review_candidate_source"] = candidate.source
    if candidate.patch:
        metadata["review_provider_patch"] = _provider_patch_summary(candidate.patch)
    if isinstance(decision_report, dict):
        metadata["review_decision"] = review_decision_summary(decision_report)
    return sanitize_metadata(metadata)


def validate_review_task_id(task_id: str) -> str:
    if not TASK_ID_PATTERN.match(str(task_id or "")):
        raise ValueError("Invalid review task id.")
    return task_id


def validate_review_candidate_id(candidate_id: str) -> str:
    if not CANDIDATE_ID_PATTERN.match(str(candidate_id or "")):
        raise ValueError("Invalid review candidate id.")
    return candidate_id


def _ensure_task_open_for_generation(task: ReviewTask) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        raise ReviewTaskStateError(f"Cannot generate candidates for a {task.status} review task.")
    if task.status == "applied":
        raise ReviewTaskStateError("Review task has already applied a candidate.")


def _ensure_task_open_for_apply(task: ReviewTask) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        raise ReviewTaskStateError(f"Cannot apply candidate for a {task.status} review task.")
    if task.status == "applied" or task.selected_candidate_id:
        raise ReviewTaskStateError("Review task has already applied a candidate.")


def ensure_task_current(task: ReviewTask, parent_plan: SongPlan) -> None:
    if song_plan_hash(parent_plan) != task.hashes.get("parent_plan_hash"):
        raise ReviewTaskStateError("Review task is stale because the parent song-plan.json has changed.")


def ensure_candidate_current(task: ReviewTask, candidate: ReviewCandidate, parent_plan: SongPlan) -> None:
    ensure_task_current(task, parent_plan)
    _ensure_candidate_current(task, candidate)


def _ensure_candidate_current(task: ReviewTask, candidate: ReviewCandidate) -> None:
    if candidate.status in {"failed", "deleted", "stale"}:
        raise ReviewTaskStateError(f"Cannot use a {candidate.status} review candidate.")
    if candidate.hashes.get("parent_plan_hash") and candidate.hashes.get("parent_plan_hash") != task.hashes.get("parent_plan_hash"):
        raise ReviewTaskStateError("Review candidate is stale.")


def _candidate_type(value: Any) -> str:
    candidate_type = str(value or "local_review_intents").strip()
    if candidate_type not in {"local_review_intents", "provider_review_patch", "manual_override"}:
        raise ReviewTaskError("Unsupported review candidate type.")
    return candidate_type


def _strategy(value: Any) -> str:
    strategy = str(value or "balanced").strip()
    if strategy not in {*STRATEGIES, PROVIDER_STRATEGY}:
        raise ReviewTaskError("Invalid review candidate strategy.")
    return strategy


def _candidate_source(task: ReviewTask) -> dict[str, Any]:
    return {
        "review_task_id": task.task_id,
        "audition_id": task.audition_id,
        "preview_id": task.preview_id,
        "source_type": "audition_review",
    }


def _provider_candidate_source(task: ReviewTask, provider_snapshot: dict[str, Any], template_id: str, candidate_index: int) -> dict[str, Any]:
    usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
    return sanitize_metadata(
        {
            "review_task_id": task.task_id,
            "audition_id": task.audition_id,
            "preview_id": task.preview_id,
            "source_type": "provider_review_candidate",
            "provider": True,
            "template_id": template_id,
            "wire_api": provider_snapshot.get("wire_api"),
            "model": provider_snapshot.get("model"),
            "request_id": provider_snapshot.get("request_id"),
            "usage": {
                "prompt_tokens": _usage_int(usage, "prompt_tokens"),
                "completion_tokens": _usage_int(usage, "completion_tokens"),
                "total_tokens": _usage_int(usage, "total_tokens"),
            },
            "candidate_index": candidate_index,
            "provider_run_id": provider_snapshot.get("provider_run_id"),
            "provider_snapshot": provider_snapshot,
        }
    )


def _provider_snapshot_for_candidate(snapshot: dict[str, Any]) -> dict[str, Any]:
    data = sanitize_metadata(dict(snapshot or {}))
    data.pop("api_key", None)
    data.pop("api_key_set", None)
    data.pop("api_key_masked", None)
    return data


def _candidate_artifacts(task_id: str, candidate_id: str) -> dict[str, str]:
    base = f"review-tasks/{task_id}/candidates/{candidate_id}"
    return {
        "candidate_song_plan_path": f"{base}/candidate-song-plan.json",
        "validator_report_path": f"{base}/validator-report.json",
        "summary_path": f"{base}/summary.json",
        "midi_path": f"{base}/renders/song.mid",
        "audio_path": f"{base}/renders/song.wav",
    }


def _validator(status: str, errors: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {"status": status, "errors": errors or [], "warnings": warnings or [], "checked_at": now_iso()}


def _usage_int(usage: dict[str, Any], field_name: str) -> int:
    try:
        return max(0, int((usage or {}).get(field_name) or 0))
    except (TypeError, ValueError):
        return 0


def score_review_candidate(task: ReviewTask, candidate_plan: SongPlan, intents: list[EditIntent], strategy: str, parent_plan: SongPlan) -> dict[str, Any]:
    edit_types = {intent.edit_type for intent in intents}
    target_section = str(task.target.get("section_name") or "")
    target_track = str(task.target.get("track_name") or "")
    changed_sections = {intent.target.section_name for intent in intents if intent.target.section_name}
    changed_tracks = {intent.target.track_name for intent in intents if intent.target.track_name}
    review_fit = 45
    if "track_density" in edit_types:
        review_fit += 25
    if "section_energy" in edit_types:
        review_fit += 20
    if "melody_variation" in edit_types:
        review_fit += 10
    target_precision = 40
    if target_section and target_section in changed_sections:
        target_precision += 35
    if target_track and target_track in changed_tracks:
        target_precision += 25
    if len(changed_sections) <= 1:
        target_precision += 10
    if len(changed_tracks) <= 1:
        target_precision += 5
    parent_quality = parent_plan.quality.scores.overall if parent_plan.quality and parent_plan.quality.scores else 0
    candidate_quality = candidate_plan.quality.scores.overall if candidate_plan.quality and candidate_plan.quality.scores else 0
    quality_delta = candidate_quality - parent_quality
    novelty = {"conservative": 40, "balanced": 62, "bold": 78}[strategy]
    safety = {"conservative": 100, "balanced": 90, "bold": 78}[strategy]
    combined = round(0.34 * _clamp(review_fit, 0, 100) + 0.28 * _clamp(target_precision, 0, 100) + 0.18 * _clamp(candidate_quality, 0, 100) + 0.1 * novelty + 0.1 * safety)
    return {
        "combined": _clamp(combined, 0, 100),
        "review_fit": _clamp(review_fit, 0, 100),
        "target_precision": _clamp(target_precision, 0, 100),
        "quality_delta": quality_delta,
        "quality_overall": candidate_quality,
        "novelty": novelty,
        "safety": safety,
    }


def candidate_summary(task: ReviewTask, strategy: str, intents: list[EditIntent]) -> str:
    edits = ", ".join(intent.edit_type for intent in intents)
    target = task.target
    return sanitize_sensitive_text(f"{strategy} candidate for {target.get('section_name') or 'song'} {target.get('track_name') or ''}: {edits}")[:800]


def _candidate_warnings(task: ReviewTask, strategy: str) -> list[str]:
    kinds = set(task.review_snapshot.get("marker_kinds") or [])
    if kinds & PRESERVE_MARKERS and strategy != "conservative":
        return ["Hook/keep markers were treated as preserve signals."]
    return []


def _task_title(snapshot: dict[str, Any], target: dict[str, Any]) -> str:
    section = target.get("section_name") or "song"
    track = target.get("track_name") or "arrangement"
    return sanitize_sensitive_text(f"Review task: {section} {track}")[:160]


def _task_summary(snapshot: dict[str, Any], target: dict[str, Any]) -> str:
    status = snapshot.get("status") or "review"
    notes = snapshot.get("notes_excerpt") or ""
    target_text = " ".join(str(item) for item in (target.get("section_name"), target.get("track_name")) if item)
    return sanitize_sensitive_text(f"{status}: {target_text}. {notes}")[:800]


def _priority(snapshot: dict[str, Any]) -> int:
    rating = int(snapshot.get("rating") or 0)
    status = str(snapshot.get("status") or "")
    score = 50 + (5 - rating) * 6 if rating else 58
    if status == "needs_fix":
        score += 16
    if status == "reject":
        score += 8
    if snapshot.get("favorite"):
        score -= 8
    return _clamp(score, 0, 100)


def _primary_marker(markers: list[dict[str, Any]]) -> dict[str, Any] | None:
    for kind in ("fix", "issue", "drop"):
        for marker in markers:
            if str(marker.get("kind") or "") == kind:
                return marker
    for kind in ("note", "maybe"):
        for marker in markers:
            if str(marker.get("kind") or "") == kind:
                return marker
    for marker in markers:
        if str(marker.get("kind") or "") in PRESERVE_MARKERS:
            return marker
    return markers[0] if markers else None


def _section_from_range_or_marker(plan: SongPlan, range_data: dict[str, Any], global_beat: float | None) -> SongSection:
    if global_beat is not None:
        section = _section_for_beat(plan, global_beat)
        if section is not None:
            return section
    if range_data.get("mode") == "section":
        section = _find_section(plan, str(range_data.get("section_name") or ""))
        if section is not None:
            return section
    start = _float_or_none(range_data.get("start_beat"))
    if start is not None:
        section = _section_for_beat(plan, start)
        if section is not None:
            return section
    for section in plan.sections:
        if "chorus" in section.name.lower():
            return section
    return plan.sections[0]


def _target_track(parent_plan: SongPlan, audition: EditorAuditionManifest, text: str) -> TrackPlan | None:
    if audition.track_mode == "solo" and len(audition.track_ids) == 1:
        index = _track_state(parent_plan).get(audition.track_ids[0])
        if index is not None:
            return parent_plan.tracks[index]
    role = _role_from_text(text)
    return _track_by_role(parent_plan, role) if role else None


def _review_text(review: dict[str, Any], audition: EditorAuditionManifest) -> str:
    parts = [
        str(review.get("notes") or ""),
        " ".join(str(tag) for tag in review.get("tags", [])),
        str(review.get("status") or ""),
        " ".join(str(marker.get("kind") or "") + " " + str(marker.get("label") or "") for marker in review.get("markers", []) if isinstance(marker, dict)),
        str(audition.range.get("section_name") if isinstance(audition.range, dict) else ""),
    ]
    return sanitize_sensitive_text(" ".join(parts))[:2000].lower()


def _role_from_text(text: str) -> str | None:
    roles = {
        "bass": ("bass", "低音", "贝斯"),
        "drums": ("drum", "drums", "kick", "snare", "鼓", "军鼓", "底鼓"),
        "melody": ("melody", "lead", "hook", "旋律", "主旋律"),
        "chords": ("chord", "harmony", "pad", "和弦", "和声"),
    }
    for role, keywords in roles.items():
        if any(keyword in text for keyword in keywords):
            return role
    return None


def _track_by_role(plan: SongPlan, role: str | None) -> TrackPlan | None:
    if not role:
        return None
    for track in plan.tracks:
        text = f"{track.name} {track.instrument}".lower()
        if role in text or (role == "drums" and "drum" in text) or (role == "chords" and ("chord" in text or "pad" in text)):
            return track
    return None


def _role_for_track(track: TrackPlan | None, text: str) -> str:
    if track is None:
        return _role_from_text(text) or ""
    lowered = f"{track.name} {track.instrument}".lower()
    for role in ("bass", "drums", "melody", "chords"):
        if role in lowered:
            return role
    return _role_from_text(text) or ""


def _track_id(plan: SongPlan, track: TrackPlan | None) -> str:
    if track is None:
        return ""
    for index, item in enumerate(plan.tracks):
        if item.name == track.name:
            return f"track-{index + 1:03d}"
    return ""


def _track_state(plan: SongPlan) -> dict[str, int]:
    return {f"track-{index + 1:03d}": index for index, _track in enumerate(plan.tracks)}


def _find_section(plan: SongPlan, name: str) -> SongSection | None:
    for section in plan.sections:
        if section.name.lower() == str(name or "").lower():
            return section
    return None


def _section_for_beat(plan: SongPlan, beat: float) -> SongSection | None:
    for section in plan.sections:
        if _section_start(section) <= beat < _section_end(section):
            return section
    return None


def _section_start(section: SongSection) -> float:
    return float((section.start_bar - 1) * 4)


def _section_end(section: SongSection) -> float:
    return _section_start(section) + float(section.bars * 4)


def _range_start(range_data: dict[str, Any]) -> float:
    return _float_or_none(range_data.get("start_beat")) or 0.0


def _intent(
    edit_type: str,
    *,
    section_name: str | None = None,
    track_name: str | None = None,
    strength: int,
    instruction: str,
    preserve: list[str],
    payload: dict[str, Any],
) -> EditIntent:
    target: dict[str, Any] = {}
    if section_name:
        target["section_name"] = section_name
    if track_name:
        target["track_name"] = track_name
    target["field"] = "notes"
    return EditIntent.from_dict({"edit_type": edit_type, "target": target, "instruction": instruction, "preserve": preserve, "strength": strength, "provider_mode": "local", "payload": payload})


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return _clamp(int(value), low, high)
    except (TypeError, ValueError):
        return default


def _clamp(value: int | float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _lock_for_project(project_dir: Path) -> threading.RLock:
    key = str(project_dir.resolve())
    with _LOCKS_GUARD:
        if key not in _STORE_LOCKS:
            _STORE_LOCKS[key] = threading.RLock()
        return _STORE_LOCKS[key]


def _append_event(root: Path, event_type: str, payload: dict[str, Any], now: str) -> None:
    event_path = root / "events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"timestamp": now, "event": event_type, **sanitize_metadata(payload)}, ensure_ascii=False) + "\n")
