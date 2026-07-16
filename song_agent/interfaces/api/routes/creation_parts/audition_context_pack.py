from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesAuditionContextPack:
    def _handle_audition_context_pack(self, project_id: str, preview_id: str, audition_id: str, payload: ImplementationDocument) -> None:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        audition = _interfaces_api_runtime.EditorAuditionStore(project_dir).read_audition(preview_id, audition_id)
        review = audition.review if isinstance(audition.review, dict) else {}
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
        self.project_store.append_event(project_id, "audition_review_context_pack_created", {"preview_id": preview_id, "audition_id": audition_id, "pack_id": pack.pack_id, "asset_id": asset_id})
        self._send_json({"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _handle_project_editor_audition_marker_route(self, method: str, project_id: str, preview_id: str, audition_id: str, marker_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = _interfaces_api_runtime.EditorPreviewStore(project_dir)
        audition_store = _interfaces_api_runtime.EditorAuditionStore(project_dir)
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
                self.project_store.append_event(project_id, "editor_audition_marker_updated", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker})
                return
            if action == "delete":
                audition = audition_store.delete_marker(preview_id, audition_id, marker_id, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_audition_marker_deleted", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
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
                _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(preview_id)
            query = _interfaces_api_runtime.parse_qs(query_string)
            filters = {
                key: _interfaces_api_runtime._query_value(query, key)
                for key in ("source", "status", "favorite", "min_rating", "track_mode", "range_mode", "sort", "order", "limit")
                if _interfaces_api_runtime._query_value(query, key)
            }
            board = _interfaces_api_runtime.EditorAuditionStore(self.project_store.project_dir(project_id)).review_board(preview_id=preview_id, filters=filters)
            self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, **board})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project or editor preview not found.")
        except (_interfaces_api_runtime.EditorReviewError, _interfaces_api_runtime.EditorAuditionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_preview_route(self, method: str, project_id: str, preview_id: str, action: str) -> None:
        store = _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id))
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
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(_interfaces_api_runtime.sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _handle_project_editor_preview_apply_part_01(self, project_id: str, preview_id: str, payload: ImplementationDocument, _split_state):
        _split_state['preview'] = _split_state['store'].read_preview(preview_id)
        if _split_state['preview'].applied_version_id:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Editor preview has already been applied.')
            return (True, None)
        try:
            _split_state['document'], _split_state['parent'], parent_job, parent_plan = self._project_edit_parent(project_id, _split_state['preview'].parent_version_id)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Parent version not found.')
            return (True, None)
        if _split_state['preview'].parent_job_id != parent_job.job_id:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Editor preview parent job does not match the current version.')
            return (True, None)
        if _interfaces_api_runtime.editor_song_plan_hash(parent_plan) != _split_state['preview'].base_plan_hash:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Editor preview is stale because the parent song-plan.json has changed.')
            return (True, None)
        patch = _split_state['store'].read_patch(preview_id)
        result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch)
        result.plan.validate()
        preview_plan_mismatch = False
        try:
            preview_plan = _split_state['store'].read_plan(preview_id)
            preview_plan_mismatch = _interfaces_api_runtime.editor_song_plan_hash(preview_plan) != _interfaces_api_runtime.editor_song_plan_hash(result.plan)
        except (OSError, ValueError, TypeError, KeyError):
            preview_plan_mismatch = True
        _split_state['run_title'] = str(payload.get('version_name') or payload.get('name') or _split_state['preview'].label or 'Editor Version')
        _split_state['run_dir'] = self.store._reserve_run_dir(_split_state['run_title'])
        _split_state['job_id'] = _split_state['run_dir'].name
        _split_state['now'] = _interfaces_api_runtime._utc_now()
        _split_state['metadata'] = _interfaces_api_runtime.editor_edit_metadata(project_id=project_id, parent_version_id=_split_state['parent'].version_id, parent_job_id=parent_job.job_id, preview_id=_split_state['preview'].preview_id, patch=patch, result=result, created_at=_split_state['now'])
        audition_summary = _interfaces_api_runtime.audition_summary_for_preview(self.project_store.project_dir(project_id), _split_state['preview'].preview_id)
        if audition_summary.get('audition_count'):
            _split_state['metadata']['audition_summary'] = audition_summary
            if isinstance(_split_state['metadata'].get('summary'), dict):
                _split_state['metadata']['summary']['audition_count'] = audition_summary.get('audition_count', 0)
                _split_state['metadata']['summary']['audition_sources'] = audition_summary.get('sources', [])
        if preview_plan_mismatch:
            _split_state['metadata']['warnings'] = [*_split_state['metadata'].get('warnings', []), 'Preview song-plan.json differed from recomputed editor patch result; applied recomputed plan.']
            _split_state['metadata']['preview_plan_mismatch'] = True
        _split_state['paths'] = _interfaces_api_runtime.ProjectPaths.create(_split_state['run_dir'])
        _split_state['plan_path'] = _split_state['paths'].data / 'song-plan.json'
        _split_state['midi_path'] = _split_state['paths'].renders / 'song.mid'
        _split_state['validator_report_path'] = _split_state['paths'].data / 'validator-report.json'
        _split_state['request_payload'] = {**_split_state['parent'].request, 'project_id': project_id, 'parent_version_id': _split_state['parent'].version_id, 'parent_job_id': parent_job.job_id, 'editor_preview_id': _split_state['preview'].preview_id, 'edit_type': 'manual_editor_edit'}
        write_interface_document(_split_state['paths'].data / 'request.json', _split_state['request_payload'])
        write_interface_document(_split_state['paths'].data / 'editor-patch.json', patch.to_dict())
        write_interface_document(_split_state['paths'].data / 'edit-metadata.json', _split_state['metadata'])
        write_interface_document(_split_state['plan_path'], result.plan.to_dict())
        _interfaces_api_runtime.render_midi(result.plan, _split_state['midi_path'])
        _interfaces_api_runtime.clear_stem_artifacts(_split_state['run_dir'])
        write_interface_document(_split_state['validator_report_path'], _interfaces_api_runtime._build_validator_report(_split_state['plan_path'], _split_state['midi_path']))
        _split_state['summary'] = _interfaces_api_runtime._build_summary(_split_state['plan_path'], _split_state['midi_path'])
        _split_state['summary']['edit'] = _split_state['metadata']['summary']
        return (False, None)

    def _handle_project_editor_preview_apply_part_02(self, project_id: str, preview_id: str, payload: ImplementationDocument, _split_state):
        write_interface_document(_split_state['paths'].data / 'run-summary.json', _split_state['summary'])
        _interfaces_api_runtime.append_event(_split_state['paths'], {'event': 'editor_preview_applied', 'preview_id': _split_state['preview'].preview_id, 'parent_version_id': _split_state['parent'].version_id})
        _split_state['job'] = _interfaces_api_runtime.JobState(job_id=_split_state['job_id'], title=_split_state['run_title'], output_dir=str(_split_state['run_dir']), status='completed', created_at=_split_state['now'], updated_at=_split_state['now'], step='completed', message='Editor patch applied.', summary=_split_state['summary'], input_payload=_split_state['request_payload'], provider_snapshot={'mode': 'local', 'summary': 'Visual editor patch'}, artifacts={**_interfaces_api_runtime._job_artifacts(_split_state['run_dir'], _split_state['plan_path'], _split_state['midi_path'], _split_state['validator_report_path']), 'editor_patch': str(_split_state['paths'].data / 'editor-patch.json')}, finished_at=_split_state['now'], heartbeat_at=_split_state['now'], generation_mode='local', pipeline_mode=_split_state['parent'].pipeline_mode, job_type='edit', edit_metadata=_split_state['metadata'])
        self.store.jobs[_split_state['job'].job_id] = _split_state['job']
        persist_interface_job(self.store, _split_state['job'])
        _split_state['document'] = self.project_store.add_version_from_job(project_id, _split_state['job'], name=_split_state['run_title'], note=str(payload.get('version_note') or payload.get('note') or ''), parent_version_id=_split_state['parent'].version_id, variant_type='manual_editor_edit', change_summary=str(payload.get('change_summary') or _split_state['preview'].label or 'Visual editor patch'))
        _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].job_id == _split_state['job'].job_id))
        _split_state['updated_preview'] = _split_state['store'].mark_applied(preview_id, version_id=_split_state['version'].version_id, job_id=_split_state['job'].job_id, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(project_id, 'editor_preview_applied', {'parent_version_id': _split_state['parent'].version_id, 'preview_id': preview_id, 'version_id': _split_state['version'].version_id, 'job_id': _split_state['job'].job_id})
        return (False, None)

    def _handle_project_editor_preview_apply(self, project_id: str, preview_id: str, payload: ImplementationDocument) -> None:
        _split_state = {}
        _split_state['store'] = _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id))
        with self.project_store.lock, _split_state['store'].lock:
            _split_result = self._handle_project_editor_preview_apply_part_01(project_id, preview_id, payload, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_editor_preview_apply_part_02(project_id, preview_id, payload, _split_state)
            if _split_result[0]:
                return _split_result[1]
        self._send_json({'ok': True, **_split_state['document'].to_dict(), 'version': _split_state['version'].to_dict(), 'job': _split_state['job'].to_dict(), 'preview': _split_state['updated_preview'].to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
