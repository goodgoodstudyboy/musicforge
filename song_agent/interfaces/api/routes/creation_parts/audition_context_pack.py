from __future__ import annotations

from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories

from dataclasses import dataclass
from pathlib import Path

from song_agent.platform.contracts.coercion import as_document as _as_document

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

from song_agent.platform.contracts.documents import JsonDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.application.jobs.model import JobState
from song_agent.application.http_ports import creation as creation_ports
from song_agent.application.http_ports.creation import EditorPreview, ProjectDocument, ProjectPaths, ProjectVersion
from song_agent.interfaces.api.routes.creation_parts.project_editor_auditions import (
    _preview_apply_metadata,
    _write_preview_apply_artifacts,
)

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


@dataclass(frozen=True)
class _PreviewApplyPrepared:
    store: creation_ports.EditorPreviewStore
    preview: EditorPreview
    document: ProjectDocument
    parent: ProjectVersion
    run_title: str
    run_dir: Path
    job_id: str
    now: str
    metadata: JsonDocument
    paths: ProjectPaths
    plan_path: Path
    midi_path: Path
    validator_report_path: Path
    request_payload: JsonDocument
    summary: JsonDocument


@dataclass(frozen=True)
class _PreviewApplyResult:
    document: ProjectDocument
    version: ProjectVersion
    job: JobState
    preview: EditorPreview


class CreationRoutesAuditionContextPack(CreationRouteContext):
    def _handle_audition_context_pack(self, project_id: str, preview_id: str, audition_id: str, payload: JsonDocument) -> None:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        audition = _api_store_factories.editor_audition_store(project_dir).read_audition(preview_id, audition_id)
        review = _as_document(audition.review)
        asset_id = str(payload.get("asset_id") or review.get("last_asset_id") or "").strip()
        if not asset_id:
            raise _interfaces_api_runtime.ReviewEditUnavailableError("No audition asset is available for context pack creation.")
        pack = self.context_pack_store.create_pack(
            {
                "name": payload.get("name") or f"Context from {audition_id}",
                "description": payload.get("description") or "Created from audition review.",
                "created_from": {
                    "source_type": "audition_review",
                    "project_id": project_id,
                    "preview_id": preview_id,
                    "audition_id": audition_id,
                    "rating": review.get("rating", 0),
                    "status": review.get("status", "unreviewed"),
                },
                "asset_refs": [{"asset_id": asset_id, "role": "audition_review_favorite", "strength": 0.9}],
                "selection": {
                    "mode": "audition_review",
                    "selected_by": "user",
                    "score_summary": [{"asset_id": asset_id, "rating": review.get("rating", 0), "favorite": bool(review.get("favorite", False))}],
                },
            },
            asset_store=self.asset_store,
            reference_store=self.reference_store,
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(
            project_id,
            "audition_review_context_pack_created",
            {"preview_id": preview_id, "audition_id": audition_id, "pack_id": pack.pack_id, "asset_id": asset_id},
        )
        self._send_json(
            {"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack)},
            status=_interfaces_api_runtime.HTTPStatus.CREATED,
        )

    def _handle_project_editor_audition_marker_route(self, method: str, project_id: str, preview_id: str, audition_id: str, marker_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = _api_store_factories.editor_preview_store(project_dir)
        audition_store = _api_store_factories.editor_audition_store(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            audition_store.read_audition(preview_id, audition_id)
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "update":
                audition = audition_store.update_marker(preview_id, audition_id, marker_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                marker = next((item for item in audition.review.get("markers", []) if item.get("marker_id") == marker_id), None)
                self.project_store.append_event(
                    project_id,
                    "editor_audition_marker_updated",
                    {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id},
                )
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker})
                return
            if action == "delete":
                audition = audition_store.delete_marker(preview_id, audition_id, marker_id, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(
                    project_id,
                    "editor_audition_marker_deleted",
                    {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id},
                )
                self._send_json({"ok": True, "audition": audition.to_dict(), "deleted": True, "marker_id": marker_id})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor audition marker route not found.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor audition marker not found.")
        except (_interfaces_api_runtime.EditorReviewError, _interfaces_api_runtime.EditorAuditionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_audition_reviews(self, method: str, project_id: str, preview_id: str | None, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            if preview_id is not None:
                _api_store_factories.editor_preview_store(self.project_store.project_dir(project_id)).read_preview(preview_id)
            query = _interfaces_api_runtime.parse_qs(query_string)
            filters = {key: _interfaces_api_runtime._query_value(query, key) for key in ("source", "status", "favorite", "min_rating", "track_mode", "range_mode", "sort", "order", "limit") if _interfaces_api_runtime._query_value(query, key)}
            board = _api_store_factories.editor_audition_store(self.project_store.project_dir(project_id)).review_board(preview_id=preview_id, filters=filters)
            self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, **board})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project or editor preview not found.")
        except (_interfaces_api_runtime.EditorReviewError, _interfaces_api_runtime.EditorAuditionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_preview_route(self, method: str, project_id: str, preview_id: str, action: str) -> None:
        store = _api_store_factories.editor_preview_store(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = store.read_preview(preview_id)
                self._send_json({"ok": True, "preview": preview.to_dict()})
                return
            if action == "patch":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                include_operations = "include_operations=true" in self.path or "include_operations=1" in self.path
                self._send_json({"ok": True, "patch": store.read_patch_summary(preview_id, include_operations=include_operations)})
                return
            if action == "song-plan":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "song_plan": store.read_plan(preview_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                self._send_file(store.preview_dir(preview_id) / "song.mid", "audio/midi", filename=f"{project_id}-{preview_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                audio_path = store.preview_dir(preview_id) / "song.wav"
                if not audio_path.exists():
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Preview audio render is not available.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{preview_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "preview": self._render_editor_preview_audio(project_id, preview_id).to_dict()})
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.delete_preview(preview_id)
                self.project_store.append_event(project_id, "editor_preview_deleted", {"preview_id": preview_id})
                self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})
                return
            if action == "apply":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                self._handle_project_editor_preview_apply(project_id, preview_id, payload)
                return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor preview not found.")
            return
        except _interfaces_api_runtime.EditorPatchStaleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(
                _interfaces_api_runtime.HTTPStatus.BAD_REQUEST,
                str(_interfaces_api_runtime.sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."),
            )
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _prepare_project_editor_preview_apply(
        self,
        project_id: str,
        preview_id: str,
        payload: JsonDocument,
        store: creation_ports.EditorPreviewStore,
    ) -> _PreviewApplyPrepared | None:
        preview = store.read_preview(preview_id)
        if preview.applied_version_id:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Editor preview has already been applied.")
            return None
        try:
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Parent version not found.")
            return None
        if preview.parent_job_id != parent_job.job_id:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
            return None
        if _interfaces_api_runtime.editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
            return None
        patch = store.read_patch(preview_id)
        result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch)
        result.plan.validate()
        preview_plan_mismatch = False
        try:
            preview_plan = store.read_plan(preview_id)
            preview_plan_mismatch = _interfaces_api_runtime.editor_song_plan_hash(preview_plan) != _interfaces_api_runtime.editor_song_plan_hash(result.plan)
        except (OSError, ValueError, TypeError, KeyError):
            preview_plan_mismatch = True
        run_title = str(payload.get("version_name") or payload.get("name") or preview.label or "Editor Version")
        run_dir = self.store._reserve_run_dir(run_title)
        job_id = run_dir.name
        now = _interfaces_api_runtime._utc_now()
        metadata = _preview_apply_metadata(
            self.project_store.project_dir(project_id),
            project_id=project_id,
            parent=parent,
            parent_job=parent_job,
            preview=preview,
            patch=patch,
            result=result,
            now=now,
            preview_plan_mismatch=preview_plan_mismatch,
        )
        paths, plan_path, midi_path, validator_report_path, request_payload, summary = _write_preview_apply_artifacts(
            project_id, parent, parent_job, preview, patch.to_dict(), result.plan, run_dir, metadata
        )
        return _PreviewApplyPrepared(
            store,
            preview,
            document,
            parent,
            run_title,
            run_dir,
            job_id,
            now,
            metadata,
            paths,
            plan_path,
            midi_path,
            validator_report_path,
            request_payload,
            summary,
        )

    def _complete_project_editor_preview_apply(
        self,
        project_id: str,
        preview_id: str,
        payload: JsonDocument,
        prepared: _PreviewApplyPrepared,
    ) -> _PreviewApplyResult:
        write_interface_document(prepared.paths.data / "run-summary.json", prepared.summary)
        _interfaces_api_runtime.append_event(
            prepared.paths,
            {"event": "editor_preview_applied", "preview_id": prepared.preview.preview_id, "parent_version_id": prepared.parent.version_id},
        )
        job = _interfaces_api_runtime.JobState(
            job_id=prepared.job_id,
            title=prepared.run_title,
            output_dir=str(prepared.run_dir),
            status="completed",
            created_at=prepared.now,
            updated_at=prepared.now,
            step="completed",
            message="Editor patch applied.",
            summary=prepared.summary,
            input_payload=prepared.request_payload,
            provider_snapshot={"mode": "local", "summary": "Visual editor patch"},
            artifacts={
                **_interfaces_api_runtime._job_artifacts(prepared.run_dir, prepared.plan_path, prepared.midi_path, prepared.validator_report_path),
                "editor_patch": str(prepared.paths.data / "editor-patch.json"),
            },
            finished_at=prepared.now,
            heartbeat_at=prepared.now,
            generation_mode="local",
            pipeline_mode=prepared.parent.pipeline_mode,
            job_type="edit",
            edit_metadata=prepared.metadata,
        )
        self.store.jobs[job.job_id] = job
        persist_interface_job(self.store, job)
        document = self.project_store.add_version_from_job(
            project_id,
            job,
            name=prepared.run_title,
            note=str(payload.get("version_note") or payload.get("note") or ""),
            parent_version_id=prepared.parent.version_id,
            variant_type="manual_editor_edit",
            change_summary=str(payload.get("change_summary") or prepared.preview.label or "Visual editor patch"),
        )
        version = next(version for version in document.versions if version.job_id == job.job_id)
        updated_preview = prepared.store.mark_applied(preview_id, version_id=version.version_id, job_id=job.job_id, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(
            project_id,
            "editor_preview_applied",
            {
                "parent_version_id": prepared.parent.version_id,
                "preview_id": preview_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
            },
        )
        return _PreviewApplyResult(document, version, job, updated_preview)

    def _handle_project_editor_preview_apply(self, project_id: str, preview_id: str, payload: JsonDocument) -> None:
        store = _api_store_factories.editor_preview_store(self.project_store.project_dir(project_id))
        with self.project_store.lock, store.lock:
            prepared = self._prepare_project_editor_preview_apply(project_id, preview_id, payload, store)
            if prepared is None:
                return
            result = self._complete_project_editor_preview_apply(project_id, preview_id, payload, prepared)
        self._send_json(
            {
                "ok": True,
                **result.document.to_dict(),
                "version": result.version.to_dict(),
                "job": result.job.to_dict(),
                "preview": result.preview.to_dict(),
            },
            status=_interfaces_api_runtime.HTTPStatus.CREATED,
        )
