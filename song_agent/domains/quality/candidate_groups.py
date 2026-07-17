from __future__ import annotations

import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.candidate_scoring import group_status_for_candidates as group_status_for_candidates, rank_candidate_summaries as rank_candidate_summaries
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


GROUP_ID_PATTERN = re.compile(r"^cg-[0-9]{3,5}$")
CANDIDATE_ID_PATTERN = re.compile(r"^cand-[0-9]{3,5}$")
GROUP_STATUSES = {"creating", "ready", "partial_ready", "failed", "applied", "deleted"}
CANDIDATE_STATUSES = {"ready", "failed", "applied", "skipped"}
MAX_CANDIDATE_COUNT = 5
MIN_CANDIDATE_COUNT = 2


@dataclass(frozen=True)
class CandidateSummary:
    candidate_id: str
    group_id: str
    status: str
    rank: int | None = None
    summary: str = ""
    scores: dict[str, Any] = field(default_factory=dict)
    patch: dict[str, Any] = field(default_factory=dict)
    validator: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] | None = None
    provider_usage: dict[str, Any] = field(default_factory=dict)
    provider_request_id: str | None = None
    midi_status: str = "not_started"
    midi_error: str | None = None
    midi_size_bytes: int = 0
    midi_url: str | None = None
    audio_status: str = "not_started"
    audio_error: str | None = None
    audio_size_bytes: int = 0
    audio_url: str | None = None
    error: str | None = None
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateSummary":
        candidate_id = validate_candidate_id(str(data.get("candidate_id") or ""))
        group_id = validate_group_id(str(data.get("group_id") or ""))
        status = str(data.get("status") or "failed")
        if status not in CANDIDATE_STATUSES:
            status = "failed"
        return cls(
            candidate_id=candidate_id,
            group_id=group_id,
            status=status,
            rank=_optional_int(data.get("rank")),
            summary=str(data.get("summary") or ""),
            scores=dict(data.get("scores") or {}),
            patch=dict(data.get("patch") or {}),
            validator=dict(data.get("validator") or {}),
            quality=data.get("quality") if isinstance(data.get("quality"), dict) else None,
            provider_usage=dict(data.get("provider_usage") or {}),
            provider_request_id=None if data.get("provider_request_id") is None else str(data.get("provider_request_id")),
            midi_status=str(data.get("midi_status") or "not_started"),
            midi_error=None if data.get("midi_error") is None else str(data.get("midi_error")),
            midi_size_bytes=int(data.get("midi_size_bytes") or 0),
            midi_url=None if data.get("midi_url") is None else str(data.get("midi_url")),
            audio_status=str(data.get("audio_status") or "not_started"),
            audio_error=None if data.get("audio_error") is None else str(data.get("audio_error")),
            audio_size_bytes=int(data.get("audio_size_bytes") or 0),
            audio_url=None if data.get("audio_url") is None else str(data.get("audio_url")),
            error=None if data.get("error") is None else str(data.get("error")),
            created_at=str(data.get("created_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateGroup:
    group_id: str
    project_id: str
    parent_version_id: str
    parent_job_id: str
    instruction: str
    template_id: str
    candidate_count: int
    status: str
    created_at: str
    updated_at: str
    source: dict[str, Any]
    candidates: list[CandidateSummary] = field(default_factory=list)
    ranking: list[dict[str, Any]] = field(default_factory=list)
    selected_candidate_id: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None
    provider_usage: dict[str, Any] = field(default_factory=dict)
    provider_request_id: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateGroup":
        group_id = validate_group_id(str(data.get("group_id") or ""))
        status = str(data.get("status") or "failed")
        if status not in GROUP_STATUSES:
            status = "failed"
        candidates = [CandidateSummary.from_dict(item) for item in data.get("candidates", []) if isinstance(item, dict)]
        return cls(
            group_id=group_id,
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            parent_job_id=str(data.get("parent_job_id") or ""),
            instruction=str(data.get("instruction") or ""),
            template_id=str(data.get("template_id") or "provider-edit-candidates"),
            candidate_count=_candidate_count(data.get("candidate_count")),
            status=status,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            source=dict(data.get("source") or {}),
            candidates=candidates,
            ranking=[dict(item) for item in data.get("ranking", []) if isinstance(item, dict)],
            selected_candidate_id=_optional_candidate_id(data.get("selected_candidate_id")),
            applied_version_id=None if data.get("applied_version_id") is None else str(data.get("applied_version_id")),
            applied_job_id=None if data.get("applied_job_id") is None else str(data.get("applied_job_id")),
            provider_usage=dict(data.get("provider_usage") or {}),
            provider_request_id=None if data.get("provider_request_id") is None else str(data.get("provider_request_id")),
            error=None if data.get("error") is None else str(data.get("error")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "project_id": self.project_id,
            "parent_version_id": self.parent_version_id,
            "parent_job_id": self.parent_job_id,
            "instruction": self.instruction,
            "template_id": self.template_id,
            "candidate_count": self.candidate_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": dict(self.source),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "ranking": [dict(item) for item in self.ranking],
            "selected_candidate_id": self.selected_candidate_id,
            "applied_version_id": self.applied_version_id,
            "applied_job_id": self.applied_job_id,
            "provider_usage": dict(self.provider_usage),
            "provider_request_id": self.provider_request_id,
            "error": self.error,
        }


class CandidateGroupStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir)
        self.root = self.project_dir / "candidate-groups"
        self.lock = threading.RLock()

    def create_group(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_job_id: str,
        instruction: str,
        template_id: str,
        candidate_count: int,
        source: dict[str, Any],
        provider_usage: dict[str, Any] | None = None,
        provider_request_id: str | None = None,
        now: str | None = None,
    ) -> CandidateGroup:
        now = now or now_iso()
        count = _candidate_count(candidate_count)
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            group_id = self._next_group_id()
            group_dir = self.group_dir(group_id)
            group_dir.mkdir(parents=True, exist_ok=False)
            (group_dir / "candidates").mkdir(parents=True, exist_ok=True)
            group = CandidateGroup(
                group_id=group_id,
                project_id=project_id,
                parent_version_id=parent_version_id,
                parent_job_id=parent_job_id,
                instruction=instruction,
                template_id=template_id,
                candidate_count=count,
                status="creating",
                created_at=now,
                updated_at=now,
                source=dict(source),
                provider_usage=dict(provider_usage or {}),
                provider_request_id=provider_request_id,
            )
            self.write_group(group)
            return group

    def write_group(self, group: CandidateGroup) -> CandidateGroup:
        with self.lock:
            validate_group_id(group.group_id)
            status = group.status if group.status in GROUP_STATUSES else group_status_for_candidates([candidate.to_dict() for candidate in group.candidates])
            ranking = group.ranking or rank_candidate_summaries([candidate.to_dict() for candidate in group.candidates])
            rank_by_id = {str(item.get("candidate_id")): int(item.get("rank") or index + 1) for index, item in enumerate(ranking)}
            candidates = [
                CandidateSummary(
                    **{
                        **candidate.to_dict(),
                        "rank": rank_by_id.get(candidate.candidate_id, candidate.rank),
                    }
                )
                for candidate in group.candidates
            ]
            updated = CandidateGroup(
                group_id=group.group_id,
                project_id=group.project_id,
                parent_version_id=group.parent_version_id,
                parent_job_id=group.parent_job_id,
                instruction=group.instruction,
                template_id=group.template_id,
                candidate_count=group.candidate_count,
                status=status,
                created_at=group.created_at,
                updated_at=now_iso(),
                source=dict(group.source),
                candidates=candidates,
                ranking=ranking,
                selected_candidate_id=group.selected_candidate_id,
                applied_version_id=group.applied_version_id,
                applied_job_id=group.applied_job_id,
                provider_usage=dict(group.provider_usage),
                provider_request_id=group.provider_request_id,
                error=group.error,
            )
            group_dir = self.group_dir(updated.group_id)
            group_dir.mkdir(parents=True, exist_ok=True)
            write_json(group_dir / "group.json", updated.to_dict())
            return updated

    def read_group(self, group_id: str) -> CandidateGroup:
        group_dir = self.group_dir(group_id)
        if not (group_dir / "group.json").exists():
            raise FileNotFoundError(group_id)
        return CandidateGroup.from_dict(read_json(group_dir / "group.json"))

    def list_groups(self) -> list[CandidateGroup]:
        if not self.root.exists():
            return []
        groups = []
        for path in self.root.glob("*/group.json"):
            try:
                groups.append(CandidateGroup.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError):
                continue
        return sorted(groups, key=lambda group: group.created_at, reverse=True)

    def add_candidate(
        self,
        group: CandidateGroup,
        *,
        summary: str,
        status: str,
        patch: dict[str, Any],
        scores: dict[str, Any],
        validator: dict[str, Any],
        quality: dict[str, Any] | None,
        provider_usage: dict[str, Any] | None = None,
        provider_request_id: str | None = None,
        error: str | None = None,
        candidate_plan: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> CandidateSummary:
        now = now or now_iso()
        if status not in CANDIDATE_STATUSES:
            raise ValueError(f"Unsupported candidate status: {status}.")
        with self.lock:
            current = self.read_group(group.group_id)
            candidate_id = self._next_candidate_id(current.group_id)
            candidate_dir = self.candidate_dir(current.group_id, candidate_id)
            candidate_dir.mkdir(parents=True, exist_ok=False)
            candidate = CandidateSummary(
                candidate_id=candidate_id,
                group_id=current.group_id,
                status=status,
                summary=summary,
                scores=dict(scores),
                patch=dict(patch),
                validator=dict(validator),
                quality=quality,
                provider_usage=dict(provider_usage or {}),
                provider_request_id=provider_request_id,
                error=error,
                created_at=now,
            )
            write_json(candidate_dir / "candidate.json", candidate.to_dict())
            write_json(candidate_dir / "patch.json", dict(patch))
            write_json(candidate_dir / "validator-report.json", dict(validator))
            write_json(candidate_dir / "quality.json", quality or {})
            write_json(candidate_dir / "critic.json", {"scores": dict(scores), "error": error})
            write_json(candidate_dir / "provider-usage.json", {"usage": dict(provider_usage or {}), "request_id": provider_request_id})
            if candidate_plan is not None:
                write_json(candidate_dir / "candidate-song-plan.json", candidate_plan)
            candidates = [*current.candidates, candidate]
            self._write_candidates(current, candidates)
            return candidate

    def render_candidate_midi(self, group_id: str, candidate_id: str) -> CandidateSummary:
        candidate_dir = self.candidate_dir(group_id, candidate_id)
        plan = SongPlan.from_dict(self.read_candidate_plan(group_id, candidate_id))
        midi_path = candidate_midi_path(candidate_dir)
        report: dict[str, Any] = {
            "candidate_id": candidate_id,
            "group_id": group_id,
            "status": "completed",
            "rendered_at": now_iso(),
            "midi_path": str(midi_path),
        }
        candidate = self._candidate_by_id(group_id, candidate_id)
        try:
            render_midi(plan, midi_path)
            report["midi_size_bytes"] = midi_path.stat().st_size
            updated = CandidateSummary.from_dict(
                {
                    **candidate.to_dict(),
                    "midi_status": "completed",
                    "midi_error": None,
                    "midi_size_bytes": midi_path.stat().st_size,
                    "midi_url": candidate_midi_url(self.project_dir.name, group_id, candidate_id),
                }
            )
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = str(exc)
            updated = CandidateSummary.from_dict(
                {
                    **candidate.to_dict(),
                    "midi_status": "failed",
                    "midi_error": str(exc),
                    "midi_size_bytes": 0,
                    "midi_url": None,
                }
            )
        write_json(candidate_dir / "render-report.json", report)
        return self._replace_candidate(group_id, updated)

    def render_group_midi(self, group_id: str) -> CandidateGroup:
        group = self.read_group(group_id)
        for candidate in group.candidates:
            if candidate.status == "ready":
                self.render_candidate_midi(group_id, candidate.candidate_id)
        return self.read_group(group_id)

    def render_candidate_audio(self, group_id: str, candidate_id: str, config: RendererConfig) -> CandidateSummary:
        candidate_dir = self.candidate_dir(group_id, candidate_id)
        midi_path = candidate_midi_path(candidate_dir)
        if not midi_path.exists():
            self.render_candidate_midi(group_id, candidate_id)
        wav_path = candidate_audio_path(candidate_dir)
        candidate = self._candidate_by_id(group_id, candidate_id)
        report: dict[str, Any] = {
            "candidate_id": candidate_id,
            "group_id": group_id,
            "status": "completed",
            "rendered_at": now_iso(),
            "audio_path": str(wav_path),
        }
        try:
            render_audio(midi_path, wav_path, config)
            report["audio_size_bytes"] = wav_path.stat().st_size
            updated = CandidateSummary.from_dict(
                {
                    **candidate.to_dict(),
                    "audio_status": "completed",
                    "audio_error": None,
                    "audio_size_bytes": wav_path.stat().st_size,
                    "audio_url": candidate_audio_url(self.project_dir.name, group_id, candidate_id),
                    "midi_status": "completed",
                    "midi_size_bytes": midi_path.stat().st_size,
                    "midi_url": candidate_midi_url(self.project_dir.name, group_id, candidate_id),
                }
            )
        except RendererError as exc:
            report["status"] = "failed"
            report["error"] = str(exc)
            updated = CandidateSummary.from_dict(
                {
                    **candidate.to_dict(),
                    "audio_status": "failed",
                    "audio_error": str(exc),
                    "audio_size_bytes": 0,
                    "audio_url": None,
                }
            )
        write_json(candidate_dir / "audio-render-report.json", report)
        return self._replace_candidate(group_id, updated)

    def render_group_audio(self, group_id: str, config: RendererConfig) -> CandidateGroup:
        group = self.read_group(group_id)
        for candidate in group.candidates:
            if candidate.status == "ready":
                self.render_candidate_audio(group_id, candidate.candidate_id, config)
        return self.read_group(group_id)

    def mark_applied(self, group_id: str, candidate_id: str, *, version_id: str, job_id: str) -> CandidateGroup:
        with self.lock:
            group = self.read_group(group_id)
            validate_candidate_id(candidate_id)
            if not any(candidate.candidate_id == candidate_id for candidate in group.candidates):
                raise FileNotFoundError(candidate_id)
            candidates = [
                CandidateSummary.from_dict({**candidate.to_dict(), "status": "applied" if candidate.candidate_id == candidate_id else candidate.status})
                for candidate in group.candidates
            ]
            updated = CandidateGroup(
                group_id=group.group_id,
                project_id=group.project_id,
                parent_version_id=group.parent_version_id,
                parent_job_id=group.parent_job_id,
                instruction=group.instruction,
                template_id=group.template_id,
                candidate_count=group.candidate_count,
                status="applied",
                created_at=group.created_at,
                updated_at=now_iso(),
                source=dict(group.source),
                candidates=candidates,
                ranking=list(group.ranking),
                selected_candidate_id=candidate_id,
                applied_version_id=version_id,
                applied_job_id=job_id,
                provider_usage=dict(group.provider_usage),
                provider_request_id=group.provider_request_id,
                error=group.error,
            )
            return self.write_group(updated)

    def delete_group(self, group_id: str) -> None:
        group_dir = self.group_dir(group_id)
        if not group_dir.exists():
            raise FileNotFoundError(group_id)
        resolved = group_dir.resolve()
        base = self.root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to delete outside candidate-groups.") from exc
        if resolved.is_symlink():
            raise ValueError("Refusing to delete symlink candidate group.")
        shutil.rmtree(resolved)

    def read_candidate_patch(self, group_id: str, candidate_id: str) -> dict[str, Any]:
        candidate_dir = self.candidate_dir(group_id, candidate_id)
        if not (candidate_dir / "patch.json").exists():
            raise FileNotFoundError(candidate_id)
        return read_json(candidate_dir / "patch.json")

    def read_candidate_plan(self, group_id: str, candidate_id: str) -> dict[str, Any]:
        candidate_dir = self.candidate_dir(group_id, candidate_id)
        if not (candidate_dir / "candidate-song-plan.json").exists():
            raise FileNotFoundError(candidate_id)
        return read_json(candidate_dir / "candidate-song-plan.json")

    def _candidate_by_id(self, group_id: str, candidate_id: str) -> CandidateSummary:
        group = self.read_group(group_id)
        for candidate in group.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise FileNotFoundError(candidate_id)

    def _replace_candidate(self, group_id: str, updated_candidate: CandidateSummary) -> CandidateSummary:
        group = self.read_group(group_id)
        replaced = False
        candidates = []
        for candidate in group.candidates:
            if candidate.candidate_id == updated_candidate.candidate_id:
                candidates.append(updated_candidate)
                replaced = True
            else:
                candidates.append(candidate)
        if not replaced:
            raise FileNotFoundError(updated_candidate.candidate_id)
        self._write_candidate_file(group_id, updated_candidate)
        self._write_candidates(group, candidates)
        return updated_candidate

    def _write_candidate_file(self, group_id: str, candidate: CandidateSummary) -> None:
        write_json(self.candidate_dir(group_id, candidate.candidate_id) / "candidate.json", candidate.to_dict())

    def _write_candidates(self, group: CandidateGroup, candidates: list[CandidateSummary]) -> CandidateGroup:
        status_value = group.status if group.status in {"applied", "deleted"} else group_status_for_candidates([item.to_dict() for item in candidates])
        ranking = rank_candidate_summaries([item.to_dict() for item in candidates])
        updated = CandidateGroup(
            group_id=group.group_id,
            project_id=group.project_id,
            parent_version_id=group.parent_version_id,
            parent_job_id=group.parent_job_id,
            instruction=group.instruction,
            template_id=group.template_id,
            candidate_count=group.candidate_count,
            status=status_value,
            created_at=group.created_at,
            updated_at=now_iso(),
            source=dict(group.source),
            candidates=candidates,
            ranking=ranking,
            selected_candidate_id=group.selected_candidate_id,
            applied_version_id=group.applied_version_id,
            applied_job_id=group.applied_job_id,
            provider_usage=dict(group.provider_usage),
            provider_request_id=group.provider_request_id,
            error=group.error,
        )
        return self.write_group(updated)

    def group_dir(self, group_id: str) -> Path:
        group_id = validate_group_id(group_id)
        base = self.root.resolve()
        target = (base / group_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside candidate-groups.") from exc
        return target

    def candidate_dir(self, group_id: str, candidate_id: str) -> Path:
        candidate_id = validate_candidate_id(candidate_id)
        base = (self.group_dir(group_id) / "candidates").resolve()
        target = (base / candidate_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside candidates.") from exc
        return target

    def _next_group_id(self) -> str:
        for index in range(1, 10_000):
            group_id = f"cg-{index:03d}"
            if not (self.root / group_id).exists():
                return group_id
        raise RuntimeError("Could not allocate candidate group id.")

    def _next_candidate_id(self, group_id: str) -> str:
        candidates_root = self.group_dir(group_id) / "candidates"
        for index in range(1, 10_000):
            candidate_id = f"cand-{index:03d}"
            if not (candidates_root / candidate_id).exists():
                return candidate_id
        raise RuntimeError("Could not allocate candidate id.")


def validate_group_id(group_id: str) -> str:
    if not GROUP_ID_PATTERN.match(group_id):
        raise ValueError("Invalid candidate group id.")
    return group_id


def validate_candidate_id(candidate_id: str) -> str:
    if not CANDIDATE_ID_PATTERN.match(candidate_id):
        raise ValueError("Invalid candidate id.")
    return candidate_id


def candidate_group_stale(group: CandidateGroup, source_hash: str) -> bool:
    expected = str(group.source.get("song_plan_sha256") or "")
    return bool(expected and expected != source_hash)


def candidate_midi_path(candidate_dir: Path) -> Path:
    return _safe_artifact_path(candidate_dir, "song.mid")


def candidate_audio_path(candidate_dir: Path) -> Path:
    return _safe_artifact_path(candidate_dir, "song.wav")


def candidate_midi_url(project_id: str, group_id: str, candidate_id: str) -> str:
    return f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/midi"


def candidate_audio_url(project_id: str, group_id: str, candidate_id: str) -> str:
    return f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/audio"


def _candidate_count(value: Any) -> int:
    count = int(value or MIN_CANDIDATE_COUNT)
    if count < MIN_CANDIDATE_COUNT or count > MAX_CANDIDATE_COUNT:
        raise ValueError(f"candidate_count must be between {MIN_CANDIDATE_COUNT} and {MAX_CANDIDATE_COUNT}.")
    return count


def _optional_candidate_id(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return validate_candidate_id(str(value))


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _safe_artifact_path(candidate_dir: Path, filename: str) -> Path:
    base = candidate_dir.resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside candidate directory.") from exc
    return target
