from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument
from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext



import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectSectionTemplateCreate(CreationRouteContext):
    def _handle_project_section_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_section_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                section_id=str(payload.get("section_id") or ""),
                payload=payload,
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "section_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorTemplateUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.EditorTemplateError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": _interfaces_api_runtime.section_template_public_dict(template, project_store=self.project_store)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _handle_project_track_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_track_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                track_id=str(payload.get("track_id") or ""),
                payload=payload,
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "track_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorTemplateUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.EditorTemplateError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": _interfaces_api_runtime.track_template_public_dict(template)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _handle_project_editor_template_mapping(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = _interfaces_api_runtime.build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            state = _interfaces_api_runtime.build_editor_state(parent_plan)
            suggestions = _interfaces_api_runtime.suggest_lane_mappings(clip, state)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except _interfaces_api_runtime.EditorTemplateUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.EditorTemplateError, _interfaces_api_runtime.EditorPatchError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "clip": clip.summary(), "suggestions": suggestions})

    def _handle_project_editor_multitrack_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = _interfaces_api_runtime.build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            existing_patch_data = payload.get("current_patch")
            existing_result = None
            draft_plan = None
            existing_operations: list[ImplementationDocument] = []
            existing_metadata: ImplementationDocument = {}
            draft_state = None
            if isinstance(existing_patch_data, dict):
                existing_result = _interfaces_api_runtime.apply_editor_patch(parent_plan, existing_patch_data)
                draft_plan = existing_result.plan
                existing_operations = list(existing_result.patch.operations)
                existing_metadata = dict(existing_result.patch.metadata)
                draft_state = _interfaces_api_runtime.build_editor_view_from_result(existing_result)
            patch_data, template_summary, template_warnings = _interfaces_api_runtime.build_multitrack_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = _interfaces_api_runtime.apply_editor_patch(parent_plan, combined_patch)
            warnings = [*template_warnings, *result.warnings]
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": warnings,
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(patch_data["operations"]),
                "patch": patch_data,
                "combined_patch": result.patch.to_dict(),
                "template_summary": template_summary,
                "mapping_suggestions": _interfaces_api_runtime.suggest_lane_mappings(clip, _interfaces_api_runtime.build_editor_state(parent_plan)),
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_template_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = _interfaces_api_runtime.build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = _interfaces_api_runtime.build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except _interfaces_api_runtime.EditorTemplateUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except _interfaces_api_runtime.EditorPatchStaleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.EditorTemplateError, _interfaces_api_runtime.EditorPatchError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_editor_preview_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch_data)
            project_dir = self.project_store.project_dir(project_id)
            preview, _preview_dir = _interfaces_api_runtime.EditorPreviewStore(project_dir).create_preview(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                parent_plan=parent_plan,
                patch=result.patch,
                result=result,
                render_midi=bool(payload.get("render_midi", True)),
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "editor_preview_created",
                {
                    "parent_version_id": parent.version_id,
                    "preview_id": preview.preview_id,
                    "operation_count": preview.operation_count,
                },
            )
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorPatchStaleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except _interfaces_api_runtime.EditorPatchError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
