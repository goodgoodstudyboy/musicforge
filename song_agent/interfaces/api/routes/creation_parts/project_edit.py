from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext



import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectEdit(CreationRouteContext):
    def _handle_project_edit_part_01(self, method: str, project_id: str, version_id: str, _split_state):
        if method == 'GET':
            try:
                _split_state['document'] = self.project_store.sync_project(project_id, self.store.get_job)
                _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].version_id == version_id))
            except StopIteration:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Version not found.')
                return (True, None)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            metadata = _interfaces_api_runtime._read_edit_metadata_for_run(_interfaces_api_runtime.Path(_split_state['version'].output_dir))
            if metadata is None:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Edit metadata not found.')
                return (True, None)
            self._send_json({'version_id': _split_state['version'].version_id, 'edit': metadata})
            return (True, None)
        if method != 'POST':
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        _split_state['payload'] = self._read_json_body()
        try:
            _split_state['document'] = self.project_store.sync_project(project_id, self.store.get_job)
            _split_state['parent'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].version_id == version_id))
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Version not found.')
            return (True, None)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
            return (True, None)
        _split_state['parent_job'] = self.store.get_job(_split_state['parent'].job_id)
        if _split_state['parent_job'] is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Parent version job is missing.')
            return (True, None)
        if _split_state['parent'].status != 'completed' or _split_state['parent_job'].status != 'completed':
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Parent version must be completed before editing.')
            return (True, None)
        _split_state['parent_plan_path'] = _interfaces_api_runtime.Path(_split_state['parent'].output_dir) / 'data' / 'song-plan.json'
        if not _split_state['parent_plan_path'].exists():
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Parent song-plan.json is missing.')
            return (True, None)
        _split_state['preset_ref'] = None
        return (False, None)

    def _handle_project_edit_part_02(self, method: str, project_id: str, version_id: str, _split_state):
        try:
            _split_state['payload'] = self._expand_context_pack_payload(_split_state['payload'])
            parent_plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(_split_state['parent_plan_path']))
            preset_id = str(_split_state['payload'].get('preset_id') or '').strip()
            intent_payload = _split_state['payload']
            if preset_id:
                preset = self.edit_preset_store.get_preset(preset_id)
                intent_payload = _interfaces_api_runtime.merge_preset_intent(preset, _split_state['payload'], parent_plan)
                _split_state['preset_ref'] = preset.public_ref()
            intent = _interfaces_api_runtime.EditIntent.from_dict(intent_payload)
            _interfaces_api_runtime.validate_edit_intent(parent_plan, intent)
            job = self.store.create_edit_job(project_id=project_id, parent_version_id=_split_state['parent'].version_id, parent_job=_split_state['parent_job'], parent_plan=parent_plan, intent=intent, preset=_split_state['preset_ref'], name=str(_split_state['payload'].get('name') or ''), start_immediately=bool(_split_state['payload'].get('start_immediately', True)), asset_refs=_split_state['payload'].get('asset_refs') if isinstance(_split_state['payload'].get('asset_refs'), list) else None, reference_refs=_split_state['payload'].get('reference_refs') if isinstance(_split_state['payload'].get('reference_refs'), list) else None, context_pack=_split_state['payload'].get('context_pack') if isinstance(_split_state['payload'].get('context_pack'), dict) else None)
            variant_type = _interfaces_api_runtime.edit_variant_type(intent.edit_type)
            _split_state['document'] = self.project_store.add_version_from_job(project_id, job, name=str(_split_state['payload'].get('name') or '') or f"Edit {len(_split_state['document'].versions) + 1}", note=str(_split_state['payload'].get('note') or ''), parent_version_id=_split_state['parent'].version_id, variant_type=variant_type, change_summary=str(_split_state['payload'].get('change_summary') or _interfaces_api_runtime.edit_change_summary(intent)))
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Edit preset not found.')
            return (True, None)
        except NotImplementedError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return (True, None)
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return (True, None)
        _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].job_id == job.job_id))
        self.project_store.append_event(project_id, 'version_edit_created', {'parent_version_id': _split_state['parent'].version_id, 'version_id': _split_state['version'].version_id, 'job_id': job.job_id, 'edit_type': intent.edit_type})
        self._send_json({'ok': True, **_split_state['document'].to_dict(), 'version': _split_state['version'].to_dict(), 'job': job.to_dict(), 'edit': job.edit_metadata}, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
        return (False, None)

    def _handle_project_edit(self, method: str, project_id: str, version_id: str) -> None:
        _split_state: ImplementationDocument = {}
        _split_result = self._handle_project_edit_part_01(method, project_id, version_id, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_edit_part_02(method, project_id, version_id, _split_state)
        if _split_result[0]:
            return _split_result[1]

    def _handle_project_edit_targets(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = _interfaces_api_runtime.Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "song-plan.json is not available for this version.")
            return
        try:
            plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(plan_path))
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(_interfaces_api_runtime.build_edit_targets(plan))

    def _handle_project_editor_state(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            state = _interfaces_api_runtime.build_editor_state(plan)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorPatchError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, **state})

    def _handle_project_editor_view(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            view = _interfaces_api_runtime.build_editor_view(plan)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorPatchError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, "view": view})

    def _handle_project_editor_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch_data)
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": list(result.warnings),
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response: ImplementationDocument = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(result.patch.operations),
                "summary": summary,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", False)):
                response["view"] = _interfaces_api_runtime.build_editor_view_from_result(result)
            if bool(payload.get("include_diff", False)):
                response["diff"] = _interfaces_api_runtime.build_editor_diff(parent_plan, result.plan, result.patch)
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
        self._send_json(response)

    def _handle_project_editor_clips(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _parent_job, _parent_plan = self._project_edit_parent(project_id, version_id)
            catalog = _interfaces_api_runtime.list_editor_clips(
                project_id=project_id,
                version_id=version.version_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
            )
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except _interfaces_api_runtime.EditorClipError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(catalog)

    def _handle_project_editor_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = _interfaces_api_runtime.build_editor_clip_from_ref(
                payload.get("clip_ref"),
                default_project_id=project_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
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
            patch_data, clip_summary, clip_warnings = _interfaces_api_runtime.build_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = _interfaces_api_runtime.apply_editor_patch(parent_plan, combined_patch)
            warnings = [*clip_warnings, *result.warnings]
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
                "clip_summary": clip_summary,
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_clip_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = _interfaces_api_runtime.build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = _interfaces_api_runtime.build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Clip or version not found.")
            return
        except _interfaces_api_runtime.EditorClipUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except _interfaces_api_runtime.EditorPatchStaleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.EditorClipError, _interfaces_api_runtime.EditorPatchError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)
