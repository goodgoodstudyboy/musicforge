from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.quality.mix_controls import MixControlError, MixControlStateError, MixControlStore, MixPatch, apply_mix_state_to_plan, apply_patch_and_render_plan, build_mix_patch, default_mix_state, file_sha256, marker_to_mix_patch_operations, mix_patch_hash, mix_state_hash, mix_state_integrity_ok, song_plan_hash, stable_hash
from song_agent.domains.studio.projectio import ProjectPaths, append_event, read_json, write_json
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.creation.renderers.audio import RendererError, load_renderer_config, render_audio
from song_agent.domains.creation.renderers.midi import render_midi, render_midi_stem
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.creation.stem_health import build_stem_health_report, stem_health_summary, write_stem_health_report
from song_agent.domains.creation.stems import build_stem_manifest, write_stem_manifest


MIX_PREVIEW_SCHEMA_VERSION = 1
MIX_PREVIEW_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}


@dataclass(frozen=True)
class MixPreview:
    schema_version: int
    preview_id: str
    project_id: str
    parent_version_id: str
    parent_job_id: str
    patch_id: str
    base_song_plan_hash: str
    base_mix_state_hash: str
    status: str
    created_at: str
    updated_at: str
    summary: dict[str, Any]
    midi_path: str
    audio_path: str | None = None
    audio_status: str = "not_started"
    audio_error: str | None = None
    applied_version_id: str | None = None
    applied_job_id: str | None = None
    integrity_hash: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MixPreview":
        return cls(
            schema_version=int(data.get("schema_version", MIX_PREVIEW_SCHEMA_VERSION) or MIX_PREVIEW_SCHEMA_VERSION),
            preview_id=_validate_preview_id(str(data.get("preview_id") or "mixprev-000001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            parent_job_id=str(data.get("parent_job_id") or ""),
            patch_id=str(data.get("patch_id") or ""),
            base_song_plan_hash=str(data.get("base_song_plan_hash") or ""),
            base_mix_state_hash=str(data.get("base_mix_state_hash") or ""),
            status=str(data.get("status") or "created"),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            summary=sanitize_metadata(data.get("summary") if isinstance(data.get("summary"), dict) else {}),
            midi_path=str(data.get("midi_path") or "song.mid"),
            audio_path=None if data.get("audio_path") is None else str(data.get("audio_path")),
            audio_status=str(data.get("audio_status") or "not_started"),
            audio_error=None if data.get("audio_error") is None else str(data.get("audio_error")),
            applied_version_id=None if data.get("applied_version_id") is None else str(data.get("applied_version_id")),
            applied_job_id=None if data.get("applied_job_id") is None else str(data.get("applied_job_id")),
            integrity_hash=str(data.get("integrity_hash") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MixRenderStore:
    def __init__(self, project_store: ProjectStore, job_store: Any | None = None) -> None:
        self.project_store = project_store
        self.job_store = job_store
        self.lock = threading.RLock()

    def project_mix_dir(self, project_id: str) -> Path:
        return self.project_store.project_dir(project_id) / "mix"

    def preview_root(self, project_id: str, version_id: str) -> Path:
        return self.project_mix_dir(project_id) / version_id / "previews"

    def preview_dir(self, project_id: str, version_id: str, preview_id: str) -> Path:
        preview_id = _validate_preview_id(preview_id)
        base = self.preview_root(project_id, version_id).resolve()
        target = (base / preview_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise MixControlError("Refusing to access preview outside project mix directory.") from exc
        return target

    def create_preview(
        self,
        *,
        project_id: str,
        version_id: str,
        payload: dict[str, Any],
        now: str | None = None,
    ) -> tuple[MixPreview, MixPatch, Path]:
        now = now or now_iso()
        document, version, parent_job, parent_plan, midi_path = _project_version_context(self.project_store, self.job_store, project_id, version_id)
        store = MixControlStore(self.project_store.project_dir(project_id))
        state = store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=parent_plan, midi_path=midi_path, now=now)
        if not mix_state_integrity_ok(state):
            raise MixControlStateError("Mix state integrity failed.")
        operations = payload.get("operations")
        if not isinstance(operations, list):
            patch_payload = payload.get("patch") if isinstance(payload.get("patch"), dict) else {}
            operations = patch_payload.get("operations")
        if not isinstance(operations, list) or not operations:
            raise MixControlError("operations must be a non-empty list.")
        patch_id = store.reserve_patch_id(version.version_id)
        patch = build_mix_patch(
            patch_id=patch_id,
            project_id=project_id,
            version_id=version.version_id,
            state=state,
            plan=parent_plan,
            operations=operations,
            source=payload.get("source") if isinstance(payload.get("source"), dict) else {"source_type": "manual_mix_patch"},
            label=str(payload.get("label") or payload.get("name") or "Mix preview"),
            now=now,
        )
        patch = store.write_patch(patch)
        result = apply_patch_and_render_plan(state, patch, parent_plan, now=now)
        preview_id, preview_dir = self._reserve_preview_dir(project_id, version.version_id)
        write_json(preview_dir / "mix-patch.json", patch.to_dict())
        write_json(preview_dir / "mix-state.json", result.state.to_dict())
        write_json(preview_dir / "song-plan.json", result.plan.to_dict())
        render_midi(result.plan, preview_dir / "song.mid", track_pans=result.track_pans, track_volumes=result.track_volumes)
        summary = {
            **result.summary,
            "midi_sha256": file_sha256(preview_dir / "song.mid"),
            "patch_hash": mix_patch_hash(patch),
        }
        preview = with_preview_integrity(
            MixPreview(
                schema_version=MIX_PREVIEW_SCHEMA_VERSION,
                preview_id=preview_id,
                project_id=project_id,
                parent_version_id=version.version_id,
                parent_job_id=parent_job.job_id if parent_job is not None else version.job_id,
                patch_id=patch.patch_id,
                base_song_plan_hash=song_plan_hash(parent_plan),
                base_mix_state_hash=patch.base_mix_state_hash,
                status="completed",
                created_at=now,
                updated_at=now,
                summary=summary,
                midi_path="song.mid",
            )
        )
        write_json(preview_dir / "preview.json", preview.to_dict())
        append_event(ProjectPaths.create(preview_dir), {"event": "mix_preview_created", "patch_id": patch.patch_id})
        return preview, patch, preview_dir

    def read_preview(self, project_id: str, version_id: str, preview_id: str) -> MixPreview:
        return MixPreview.from_dict(read_json(self.preview_dir(project_id, version_id, preview_id) / "preview.json"))

    def render_preview_audio(self, *, project_id: str, version_id: str, preview_id: str, now: str | None = None) -> MixPreview:
        now = now or now_iso()
        preview = self.read_preview(project_id, version_id, preview_id)
        preview_dir = self.preview_dir(project_id, version_id, preview.preview_id)
        try:
            config, _sources = load_renderer_config()
            wav_path = render_audio(preview_dir / "song.mid", preview_dir / "song.wav", config)
            updated = MixPreview.from_dict({**preview.to_dict(), "audio_path": "song.wav", "audio_status": "completed", "audio_error": None, "updated_at": now, "summary": {**preview.summary, "audio_size_bytes": wav_path.stat().st_size}})
        except RendererError as exc:
            updated = MixPreview.from_dict({**preview.to_dict(), "audio_status": "failed", "audio_error": str(exc)[:500], "updated_at": now})
        updated = with_preview_integrity(updated)
        write_json(preview_dir / "preview.json", updated.to_dict())
        return updated

    def apply_preview(
        self,
        *,
        project_id: str,
        version_id: str,
        preview_id: str,
        payload: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> tuple[dict[str, Any], Any, Any]:
        now = now or now_iso()
        payload = payload or {}
        with self.lock:
            document, parent, parent_job, parent_plan, parent_midi = _project_version_context(self.project_store, self.job_store, project_id, version_id)
            preview = self.read_preview(project_id, version_id, preview_id)
            if preview.applied_version_id:
                raise MixControlStateError("Mix preview has already been applied.")
            if preview.parent_version_id != parent.version_id:
                raise MixControlStateError("Mix preview does not belong to this parent version.")
            if preview.parent_job_id != parent.job_id:
                raise MixControlStateError("Mix preview parent job does not match current version.")
            if preview.base_song_plan_hash != song_plan_hash(parent_plan):
                raise MixControlStateError("Mix preview is stale because the parent SongPlan changed.")
            store = MixControlStore(self.project_store.project_dir(project_id))
            state = store.read_state(parent.version_id)
            if preview.base_mix_state_hash != mix_state_hash(state):
                raise MixControlStateError("Mix preview is stale because the parent mix state changed.")
            patch = MixPatch.from_dict(read_json(self.preview_dir(project_id, version_id, preview_id) / "mix-patch.json"))
            result = apply_patch_and_render_plan(state, patch, parent_plan, now=now)
            run_title = str(payload.get("version_name") or payload.get("name") or patch.label or "Mix Control Edit")
            run_dir = self.job_store._reserve_run_dir(run_title) if self.job_store is not None else (Path("runs") / run_title.lower().replace(" ", "-"))
            if self.job_store is None:
                run_dir.mkdir(parents=True, exist_ok=False)
            job_id = run_dir.name
            paths = ProjectPaths.create(run_dir)
            request_payload = {
                **parent.request,
                "project_id": project_id,
                "parent_version_id": parent.version_id,
                "parent_job_id": parent.job_id,
                "mix_preview_id": preview.preview_id,
                "mix_patch_id": patch.patch_id,
                "edit_type": "mix_control_edit",
            }
            metadata = {
                "schema_version": 1,
                "edit_source": "mix_control",
                "edit_type": "mix_control_edit",
                "project_id": project_id,
                "parent_version_id": parent.version_id,
                "parent_job_id": parent.job_id,
                "preview_id": preview.preview_id,
                "operation_count": len(patch.operations),
                "changed_tracks": result.summary.get("changed_tracks", []),
                "changed_sections": [],
                "mix": {
                    "mix_state_hash": mix_state_hash(result.state),
                    "mix_patch_hash": mix_patch_hash(patch),
                    "patch_id": patch.patch_id,
                },
                "summary": result.summary,
                "warnings": list(result.warnings),
                "created_at": now,
            }
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            write_json(paths.data / "request.json", request_payload)
            write_json(paths.data / "edit-metadata.json", metadata)
            write_json(paths.data / "mix-state.json", result.state.to_dict())
            write_json(paths.data / "mix-patch.json", patch.to_dict())
            write_json(plan_path, result.plan.to_dict())
            render_midi(result.plan, midi_path, track_pans=result.track_pans, track_volumes=result.track_volumes)
            validator = _validator_report(plan_path, midi_path)
            write_json(paths.data / "validator-report.json", validator)
            summary = _run_summary(plan_path, midi_path)
            summary["edit"] = metadata["summary"]
            write_json(paths.data / "run-summary.json", summary)
            append_event(paths, {"event": "mix_preview_applied", "preview_id": preview.preview_id, "parent_version_id": parent.version_id})
            job = _job_state(self.job_store, job_id, run_dir, run_title, now, summary, request_payload, metadata, parent.pipeline_mode)
            if self.job_store is not None:
                self.job_store.jobs[job.job_id] = job
                self.job_store._write_job(job)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=run_title,
                note=str(payload.get("version_note") or payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="mix_control_edit",
                change_summary=str(payload.get("change_summary") or patch.label or "Mix control edit"),
            )
            version = next(item for item in document.versions if item.job_id == job.job_id)
            child_store = MixControlStore(self.project_store.project_dir(project_id))
            child_base = default_mix_state(project_id=project_id, version_id=version.version_id, plan=result.plan, midi_path=midi_path, now=now)
            child_source = {
                **child_base.source,
                "source_type": "applied_mix_version",
                "parent_version_id": parent.version_id,
                "parent_job_id": parent.job_id,
                "mix_preview_id": preview.preview_id,
                "mix_patch_id": patch.patch_id,
                "project_id": project_id,
                "version_id": version.version_id,
                "song_plan_hash": song_plan_hash(result.plan),
                "midi_sha256": file_sha256(midi_path),
            }
            child_state = child_store.write_state(
                type(child_base).from_dict(
                    {
                        **child_base.to_dict(),
                        "project_id": project_id,
                        "version_id": version.version_id,
                        "base_song_plan_hash": song_plan_hash(result.plan),
                        "base_midi_hash": file_sha256(midi_path),
                        "source": child_source,
                        "source_hash": stable_hash(child_source),
                        "updated_at": now,
                    }
                )
            )
            write_json(paths.data / "mix-state.json", child_state.to_dict())
            updated_preview = with_preview_integrity(MixPreview.from_dict({**preview.to_dict(), "status": "applied", "applied_version_id": version.version_id, "applied_job_id": job.job_id, "updated_at": now}))
            write_json(self.preview_dir(project_id, parent.version_id, preview.preview_id) / "preview.json", updated_preview.to_dict())
            self.project_store.append_event(project_id, "mix_preview_applied", {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "version_id": version.version_id, "job_id": job.job_id})
            return document.to_dict(), version, job

    def render_stems(self, *, project_id: str, version_id: str, require_wav: bool = False, render_wav: bool = False, force: bool = False, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        _document, version, _job, plan, _midi = _project_version_context(self.project_store, self.job_store, project_id, version_id)
        run_dir = Path(version.output_dir)
        store = MixControlStore(self.project_store.project_dir(project_id))
        state = store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=now)
        mixed_plan, track_pans, track_volumes, _summary = apply_mix_state_to_plan(plan, state, ignore_solo=True)
        manifest = build_stem_manifest(mixed_plan, run_dir, version.job_id, now=now)
        rendered = []
        for index, stem in enumerate(manifest.stems):
            midi_path = run_dir / stem.midi_path
            if stem.note_count:
                render_midi_stem(mixed_plan, index, midi_path, pan=track_pans.get(index), volume=track_volumes.get(index))
            rendered.append(
                type(stem).from_dict(
                    {
                        **stem.to_dict(),
                        "midi_exists": midi_path.exists(),
                        "audio_exists": (run_dir / stem.audio_path).exists(),
                        "audio_status": "completed" if (run_dir / stem.audio_path).exists() else "not_started",
                        "updated_at": now,
                    }
                )
            )
        manifest = write_stem_manifest(run_dir, type(manifest)(version=manifest.version, job_id=manifest.job_id, source_song_plan=manifest.source_song_plan, source_hash=manifest.source_hash, created_at=manifest.created_at, updated_at=now, stems=rendered))
        if render_wav:
            try:
                config, _sources = load_renderer_config()
                for stem in manifest.stems:
                    if not stem.note_count:
                        continue
                    render_audio(run_dir / stem.midi_path, run_dir / stem.audio_path, config)
            except RendererError:
                pass
        report = build_stem_health_report(run_dir=run_dir, project_id=project_id, version_id=version.version_id, mix_state=state.to_dict(), require_wav=require_wav, now=now)
        report = write_stem_health_report(run_dir, report)
        return {"ok": True, "project_id": project_id, "version_id": version.version_id, "manifest": manifest.to_dict(), "stem_health": report, "summary": stem_health_summary(report)}

    def marker_mix_patch_draft(self, *, release_store: Any, audio_review_store: Any, release_id: str, review_id: str, marker_id: str, payload: dict[str, Any] | None = None, now: str | None = None) -> dict[str, Any]:
        now = now or now_iso()
        review = audio_review_store.read_review(release_id, review_id)
        if review.get("stale"):
            raise MixControlStateError("Audio review is stale. Refresh review before creating a mix patch draft.")
        markers = review.get("markers") if isinstance(review.get("markers"), list) else []
        marker = next((item for item in markers if isinstance(item, dict) and item.get("marker_id") == marker_id), None)
        if marker is None:
            raise FileNotFoundError(marker_id)
        project_id = str(review.get("project_id") or "")
        version_id = str(review.get("version_id") or "")
        _document, version, _job, plan, midi_path = _project_version_context(self.project_store, self.job_store, project_id, version_id)
        control_store = MixControlStore(self.project_store.project_dir(project_id))
        state = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=midi_path, now=now)
        operations = marker_to_mix_patch_operations(marker, review, plan, payload)
        patch_id = control_store.reserve_patch_id(version.version_id)
        source = {
            "source_type": "release_audio_review_marker",
            "release_id": release_id,
            "review_id": review_id,
            "marker_id": marker_id,
            "track_id": review.get("track_id"),
            "category": marker.get("category"),
            "severity": marker.get("severity"),
            "mapped": marker.get("mapped") if isinstance(marker.get("mapped"), dict) else {},
        }
        patch = build_mix_patch(patch_id=patch_id, project_id=project_id, version_id=version.version_id, state=state, plan=plan, operations=operations, source=source, label="Audio review mix patch draft", now=now)
        patch = control_store.write_patch(patch)
        marker["mix_patch_id"] = patch.patch_id
        audio_review_store._write_review_with_markers(release_id, review, markers, now=now)
        return {"status": "created", "project_id": project_id, "version_id": version.version_id, "patch": patch.to_dict(), "marker": marker}

    def _reserve_preview_dir(self, project_id: str, version_id: str) -> tuple[str, Path]:
        root = self.preview_root(project_id, version_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            preview_id = f"mixprev-{index:06d}"
            target = self.preview_dir(project_id, version_id, preview_id)
            try:
                target.mkdir(parents=True, exist_ok=False)
                return preview_id, target
            except FileExistsError:
                continue
        raise MixControlError("Could not allocate mix preview id.")


def with_preview_integrity(preview: MixPreview) -> MixPreview:
    data = preview.to_dict()
    data["integrity_hash"] = mix_preview_hash(data)
    return MixPreview.from_dict(data)


def mix_preview_hash(preview: MixPreview | dict[str, Any]) -> str:
    data = preview.to_dict() if isinstance(preview, MixPreview) else dict(preview)
    from song_agent.domains.delivery.releases import stable_hash

    return stable_hash({key: value for key, value in data.items() if key not in MIX_PREVIEW_INTEGRITY_EXCLUDE_KEYS})


def mix_preview_integrity_ok(preview: MixPreview | dict[str, Any]) -> bool:
    data = preview.to_dict() if isinstance(preview, MixPreview) else dict(preview)
    expected = str(data.get("integrity_hash") or "")
    return bool(expected) and expected == mix_preview_hash(data)


def _project_version_context(project_store: ProjectStore, job_store: Any | None, project_id: str, version_id: str) -> tuple[Any, Any, Any, SongPlan, Path]:
    document = project_store.sync_project(project_id, job_store.get_job) if job_store is not None else project_store.get_project(project_id)
    version = next((item for item in document.versions if item.version_id == version_id), None)
    if version is None:
        raise FileNotFoundError("Version not found.")
    parent_job = job_store.get_job(version.job_id) if job_store is not None else None
    if parent_job is None and job_store is not None:
        raise MixControlStateError("Version job is missing.")
    run_dir = Path(version.output_dir)
    plan_path = run_dir / "data" / "song-plan.json"
    midi_path = run_dir / "renders" / "song.mid"
    if not plan_path.exists() or not midi_path.exists():
        raise MixControlStateError("Version song-plan.json or song.mid is missing.")
    return document, version, parent_job, SongPlan.from_dict(read_json(plan_path)), midi_path


def _validator_report(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    return {
        "status": "passed",
        "checks": ["song_plan_schema", "song_plan_validation", "midi_render", "mix_control_edit"],
        "title": plan.get("title"),
        "midi_exists": midi_path.exists(),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
        "checked_at": now_iso(),
    }


def _run_summary(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    tracks = plan.get("tracks", []) if isinstance(plan.get("tracks"), list) else []
    sections = plan.get("sections", []) if isinstance(plan.get("sections"), list) else []
    return {
        "title": plan.get("title"),
        "tempo_bpm": plan.get("tempo_bpm"),
        "key": plan.get("key"),
        "meter": plan.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(track.get("notes", [])) for track in tracks if isinstance(track, dict)),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
    }


def _job_state(job_store: Any | None, job_id: str, run_dir: Path, title: str, now: str, summary: dict[str, Any], request_payload: dict[str, Any], metadata: dict[str, Any], pipeline_mode: str) -> Any:
    from song_agent.application.jobs.model import JobState

    artifacts = {
        "request": str(run_dir / "data" / "request.json"),
        "song_plan": str(run_dir / "data" / "song-plan.json"),
        "run_summary": str(run_dir / "data" / "run-summary.json"),
        "validator_report": str(run_dir / "data" / "validator-report.json"),
        "job_state": str(run_dir / "data" / "job-state.json"),
        "events": str(run_dir / "logs" / "events.jsonl"),
        "midi": str(run_dir / "renders" / "song.mid"),
        "edit_metadata": str(run_dir / "data" / "edit-metadata.json"),
        "mix_state": str(run_dir / "data" / "mix-state.json"),
        "mix_patch": str(run_dir / "data" / "mix-patch.json"),
    }
    return JobState(
        job_id=job_id,
        title=title,
        output_dir=str(run_dir),
        status="completed",
        created_at=now,
        updated_at=now,
        step="completed",
        message="Mix control edit applied.",
        summary=summary,
        input_payload=request_payload,
        provider_snapshot={"mode": "local", "summary": "Mix control edit"},
        artifacts=artifacts,
        finished_at=now,
        heartbeat_at=now,
        generation_mode="local",
        pipeline_mode=pipeline_mode,
        job_type="edit",
        edit_metadata=metadata,
    )


def _validate_preview_id(value: str) -> str:
    import re

    if not re.match(r"^mixprev-[0-9]{6}$", value):
        raise MixControlError("Invalid mix preview id.")
    return value
