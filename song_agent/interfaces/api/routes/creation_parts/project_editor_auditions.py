from __future__ import annotations

from pathlib import Path

from song_agent.application.http_ports import creation as creation_ports
from song_agent.application.http_ports.creation import EditorPreview, ProjectPaths, ProjectVersion
from song_agent.application.interface_persistence import write_interface_document
from song_agent.application.jobs.model import JobState
from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext
from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories
from song_agent.platform.contracts.coercion import as_int as _as_int
from song_agent.platform.contracts.documents import JsonDocument

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


def _preview_apply_metadata(
    project_dir: Path,
    *,
    project_id: str,
    parent: ProjectVersion,
    parent_job: JobState,
    preview: EditorPreview,
    patch: creation_ports.EditorPatch,
    result: creation_ports.EditorPatchResult,
    now: str,
    preview_plan_mismatch: bool,
) -> JsonDocument:
    metadata = _interfaces_api_runtime.editor_edit_metadata(
        project_id=project_id,
        parent_version_id=parent.version_id,
        parent_job_id=parent_job.job_id,
        preview_id=preview.preview_id,
        patch=patch,
        result=result,
        created_at=now,
    )
    audition = _interfaces_api_runtime.audition_summary_for_preview(project_dir, preview.preview_id)
    if audition.get("audition_count"):
        metadata["audition_summary"] = audition
        summary = metadata.get("summary")
        if isinstance(summary, dict):
            summary["audition_count"] = audition.get("audition_count", 0)
            summary["audition_sources"] = audition.get("sources", [])
    if preview_plan_mismatch:
        metadata["warnings"] = [
            *metadata.get("warnings", []),
            "Preview song-plan.json differed from recomputed editor patch result; applied recomputed plan.",
        ]
        metadata["preview_plan_mismatch"] = True
    return metadata


def _write_preview_apply_artifacts(
    project_id: str,
    parent: ProjectVersion,
    parent_job: JobState,
    preview: EditorPreview,
    patch: JsonDocument,
    plan: creation_ports.SongPlan,
    run_dir: Path,
    metadata: JsonDocument,
) -> tuple[ProjectPaths, Path, Path, Path, JsonDocument, JsonDocument]:
    paths = _interfaces_api_runtime.ProjectPaths.create(run_dir)
    plan_path = paths.data / "song-plan.json"
    midi_path = paths.renders / "song.mid"
    report_path = paths.data / "validator-report.json"
    request = {
        **parent.request,
        "project_id": project_id,
        "parent_version_id": parent.version_id,
        "parent_job_id": parent_job.job_id,
        "editor_preview_id": preview.preview_id,
        "edit_type": "manual_editor_edit",
    }
    write_interface_document(paths.data / "request.json", request)
    write_interface_document(paths.data / "editor-patch.json", patch)
    write_interface_document(paths.data / "edit-metadata.json", metadata)
    write_interface_document(plan_path, plan.to_dict())
    _interfaces_api_runtime.render_midi(plan, midi_path)
    _interfaces_api_runtime.clear_stem_artifacts(run_dir)
    write_interface_document(report_path, _interfaces_api_runtime._build_validator_report(plan_path, midi_path))
    summary = _interfaces_api_runtime._build_summary(plan_path, midi_path)
    summary["edit"] = metadata["summary"]
    return paths, plan_path, midi_path, report_path, request, summary


class CreationProjectEditorAuditionRoutes(CreationRouteContext):
    def _handle_project_editor_preview_root(self, method: str, project_id: str, action: str) -> None:
        store = _api_store_factories.editor_preview_store(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "list":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "project_id": project_id, "previews": [preview.to_dict() for preview in store.list_previews()]})
                return
            if action == "cleanup":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = store.cleanup_previews(delete_unapplied_older_than_days=_as_int(payload.get("delete_unapplied_older_than_days", 7) or 7), keep_latest=_as_int(payload.get("keep_latest", 20) or 20), now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_previews_cleanup", result)
                self._send_json({"ok": True, **result})
                return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _handle_project_editor_auditions_root(self, method: str, project_id: str, preview_id: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = _api_store_factories.editor_preview_store(project_dir)
        audition_store = _api_store_factories.editor_audition_store(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview = preview_store.read_preview(preview_id)
            if method == "GET":
                auditions = audition_store.list_auditions(preview_id)
                self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, "auditions": [item.to_dict() for item in auditions]})
                return
            if method == "POST":
                payload = self._read_json_body()
                source = str(payload.get("source") or "preview").strip()
                if source not in {"preview", "parent"}:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "source must be parent or preview.")
                    return
                _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
                if preview.parent_job_id != parent_job.job_id:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
                    return
                if _interfaces_api_runtime.editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
                    return
                source_plan, source_state = (parent_plan, None) if source == "parent" else self._editor_audition_preview_source(preview_store, preview_id, parent_plan)
                audition = audition_store.create_audition(project_id=project_id, preview=preview, source_plan=source_plan, editor_state=source_state, payload={**payload, "source": source}, now=_interfaces_api_runtime._utc_now())
                if bool(payload.get("render_audio", False)):
                    config, _sources = _interfaces_api_runtime.load_renderer_config()
                    config.validate_ready_for_render()
                    audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition.audition_id, config=config, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_audition_created", {"parent_version_id": parent.version_id, "preview_id": preview_id, "audition_id": audition.audition_id, "source": audition.source})
                self._send_json({"ok": True, "audition": audition.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor preview not found.")
        except _interfaces_api_runtime.EditorAuditionUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(_interfaces_api_runtime.sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except (_interfaces_api_runtime.EditorAuditionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _editor_audition_preview_source(self, preview_store: creation_ports.EditorPreviewStore, preview_id: str, parent_plan: creation_ports.SongPlan):
        patch = preview_store.read_patch(preview_id)
        result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch)
        return result.plan, _interfaces_api_runtime.build_editor_view_from_result(result)

    def _handle_project_editor_audition_route(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = _api_store_factories.editor_preview_store(project_dir)
        audition_store = _api_store_factories.editor_audition_store(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            if self._dispatch_editor_audition_read(method, project_id, preview_id, audition_id, action, audition_store):
                return
            if self._dispatch_editor_audition_update(method, project_id, preview_id, audition_id, action, audition_store):
                return
            if action == "review-task":
                self._handle_project_review_task_create(method, project_id, preview_id, audition_id)
                return
            if action in {"review-edit-preview", "review-edit", "provider-review-edit-preview", "create-context-pack"}:
                self._handle_project_editor_audition_next_action(method, project_id, preview_id, audition_id, action)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor audition route not found.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor audition not found.")
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(_interfaces_api_runtime.sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except _interfaces_api_runtime.EditorReviewError as exc:
            status = _interfaces_api_runtime.HTTPStatus.CONFLICT if "no notes" in str(exc).lower() else _interfaces_api_runtime.HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except (_interfaces_api_runtime.EditorAuditionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _dispatch_editor_audition_read(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str, store: creation_ports.EditorAuditionStore) -> bool:
        if action not in {"detail", "midi", "audio"}:
            return False
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        audition = store.read_audition(preview_id, audition_id)
        if action == "detail":
            self._send_json({"ok": True, "audition": audition.to_dict()})
        elif action == "midi":
            self._send_file(store.midi_path(preview_id, audition_id), "audio/midi", filename=f"{project_id}-{preview_id}-{audition_id}.mid")
        else:
            self._send_file(store.audio_path(preview_id, audition_id), "audio/wav", filename=f"{project_id}-{preview_id}-{audition_id}.wav")
        return True

    def _dispatch_editor_audition_update(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str, store: creation_ports.EditorAuditionStore) -> bool:
        if action not in {"render-audio", "review", "markers", "create-asset", "delete"}:
            return False
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        if action == "render-audio":
            config, _sources = _interfaces_api_runtime.load_renderer_config()
            config.validate_ready_for_render()
            audition = store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition_id, config=config, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "editor_audition_audio_rendered", {"preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "audition": audition.to_dict()})
        elif action == "review":
            audition = store.update_review(preview_id, audition_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "editor_audition_review_updated", {"preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "audition": audition.to_dict(), "review": audition.review})
        elif action == "markers":
            audition = store.add_marker(preview_id, audition_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            marker = (audition.review.get("markers") or [])[-1]
            self.project_store.append_event(project_id, "editor_audition_marker_added", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker.get("marker_id")})
            self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        elif action == "create-asset":
            manifest = store.read_audition(preview_id, audition_id)
            plan = store.read_plan(preview_id, audition_id)
            asset = self.asset_store.create_asset(_interfaces_api_runtime.audition_asset_payload(plan, manifest, self._read_json_body()), now=_interfaces_api_runtime._utc_now())
            audition = store.record_asset_created(preview_id, audition_id, asset.asset_id, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "editor_audition_asset_created", {"preview_id": preview_id, "audition_id": audition_id, "asset_id": asset.asset_id})
            self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset), "audition": audition.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        else:
            store.delete_audition(preview_id, audition_id)
            self.project_store.append_event(project_id, "editor_audition_deleted", {"preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "deleted": True, "audition_id": audition_id})
        return True
