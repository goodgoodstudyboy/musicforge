from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectMix:
    def _handle_project_mix_route(self, method: str, project_id: str, version_id: str, action: str, resource_id: str | None = None) -> None:
        mix_store = _interfaces_api_runtime.MixRenderStore(self.project_store, self.store)
        control_store = _interfaces_api_runtime.MixControlStore(self.project_store.project_dir(project_id))
        try:
            if action == "mix-state":
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                run_dir = _interfaces_api_runtime.Path(version.output_dir)
                plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(run_dir / "data" / "song-plan.json"))
                if method == "GET":
                    state = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict(), "summary": {"mix_state_hash": _interfaces_api_runtime.mix_state_hash(state)}})
                    return
                if method == "POST":
                    current = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
                    state = control_store.write_state(type(current).from_dict({**self._read_json_body(), "project_id": project_id, "version_id": version.version_id, "updated_at": _interfaces_api_runtime._utc_now()}))
                    self.project_store.append_event(project_id, "mix_state_saved", {"version_id": version.version_id, "mix_state_hash": _interfaces_api_runtime.mix_state_hash(state)})
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "mix-state-reset":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                run_dir = _interfaces_api_runtime.Path(version.output_dir)
                plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(run_dir / "data" / "song-plan.json"))
                state = control_store.reset_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "mix_state_reset", {"version_id": version.version_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
                return
            if action == "mix-preview-create":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview, patch, _preview_dir = mix_store.create_preview(project_id=project_id, version_id=version_id, payload=self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "mix_preview_created", {"version_id": version_id, "preview_id": preview.preview_id, "patch_id": patch.patch_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "mix-preview-detail" and resource_id:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "integrity_ok": _interfaces_api_runtime.mix_preview_integrity_ok(preview)})
                return
            if action == "mix-preview-midi" and resource_id:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if not _interfaces_api_runtime.mix_preview_integrity_ok(preview):
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Mix preview integrity failed.")
                    return
                self._send_file(mix_store.preview_dir(project_id, version_id, resource_id) / "song.mid", "audio/midi", filename=f"{project_id}-{resource_id}.mid")
                return
            if action == "mix-preview-audio" and resource_id:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if not _interfaces_api_runtime.mix_preview_integrity_ok(preview):
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Mix preview integrity failed.")
                    return
                audio_path = mix_store.preview_dir(project_id, version_id, resource_id) / "song.wav"
                if not audio_path.exists():
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mix preview audio is not available.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{resource_id}.wav")
                return
            if action == "mix-preview-render-audio" and resource_id:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.render_preview_audio(project_id=project_id, version_id=version_id, preview_id=resource_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict()})
                return
            if action == "mix-preview-apply" and resource_id:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document, version, job = mix_store.apply_preview(project_id=project_id, version_id=version_id, preview_id=resource_id, payload=self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, **document, "version": version.to_dict(), "job": job.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "mix-preview-delete" and resource_id:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if preview.applied_version_id:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Applied mix previews cannot be deleted.")
                    return
                preview_dir = mix_store.preview_dir(project_id, version_id, resource_id)
                if preview_dir.exists():
                    _interfaces_api_runtime.shutil.rmtree(preview_dir)
                self.project_store.append_event(project_id, "mix_preview_deleted", {"version_id": version_id, "preview_id": resource_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview_id": resource_id, "deleted": True})
                return
            if action == "mix-stems-render":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "mix_stems_rendered", {"version_id": version_id, "status": result["summary"].get("status")})
                self._send_json(result)
                return
            if action == "mix-stems-health":
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                if method == "GET":
                    report = _interfaces_api_runtime.read_stem_health_report(_interfaces_api_runtime.Path(version.output_dir))
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "stem_health": report, "summary": _interfaces_api_runtime.stem_health_summary(report)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_interfaces_api_runtime._utc_now())
                    self._send_json(result)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc) or "Mix resource not found.")
            return
        except _interfaces_api_runtime.MixControlStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.MixControlError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mix route not found.")

    def _handle_project_editor_preview_root(self, method: str, project_id: str, action: str) -> None:
        store = _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id))
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
                result = store.cleanup_previews(
                    delete_unapplied_older_than_days=int(payload.get("delete_unapplied_older_than_days", 7) or 7),
                    keep_latest=int(payload.get("keep_latest", 20) or 20),
                    now=_interfaces_api_runtime._utc_now(),
                )
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
        preview_store = _interfaces_api_runtime.EditorPreviewStore(project_dir)
        audition_store = _interfaces_api_runtime.EditorAuditionStore(project_dir)
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
                if source == "parent":
                    source_plan = parent_plan
                    source_state = None
                else:
                    patch = preview_store.read_patch(preview_id)
                    result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch)
                    source_plan = result.plan
                    source_state = _interfaces_api_runtime.build_editor_view_from_result(result)
                payload = {**payload, "source": source}
                audition = audition_store.create_audition(project_id=project_id, preview=preview, source_plan=source_plan, editor_state=source_state, payload=payload, now=_interfaces_api_runtime._utc_now())
                if bool(payload.get("render_audio", False)):
                    config, _sources = _interfaces_api_runtime.load_renderer_config()
                    config.validate_ready_for_render()
                    audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition.audition_id, config=config, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(
                    project_id,
                    "editor_audition_created",
                    {"parent_version_id": parent.version_id, "preview_id": preview_id, "audition_id": audition.audition_id, "source": audition.source},
                )
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

    def _handle_project_editor_audition_route(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = _interfaces_api_runtime.EditorPreviewStore(project_dir)
        audition_store = _interfaces_api_runtime.EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "audition": audition_store.read_audition(preview_id, audition_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.midi_path(preview_id, audition_id), "audio/midi", filename=f"{project_id}-{preview_id}-{audition_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.audio_path(preview_id, audition_id), "audio/wav", filename=f"{project_id}-{preview_id}-{audition_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = _interfaces_api_runtime.load_renderer_config()
                config.validate_ready_for_render()
                audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition_id, config=config, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_audition_audio_rendered", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict()})
                return
            if action == "review":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.update_review(preview_id, audition_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_audition_review_updated", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "review": audition.review})
                return
            if action == "markers":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.add_marker(preview_id, audition_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                marker = (audition.review.get("markers") or [])[-1]
                self.project_store.append_event(project_id, "editor_audition_marker_added", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker.get("marker_id")})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "create-asset":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = audition_store.read_audition(preview_id, audition_id)
                plan = audition_store.read_plan(preview_id, audition_id)
                asset_payload = _interfaces_api_runtime.audition_asset_payload(plan, manifest, self._read_json_body())
                asset = self.asset_store.create_asset(asset_payload, now=_interfaces_api_runtime._utc_now())
                audition = audition_store.record_asset_created(preview_id, audition_id, asset.asset_id, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "editor_audition_asset_created", {"preview_id": preview_id, "audition_id": audition_id, "asset_id": asset.asset_id})
                self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset), "audition": audition.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "review-task":
                self._handle_project_review_task_create(method, project_id, preview_id, audition_id)
                return
            if action in {"review-edit-preview", "review-edit", "provider-review-edit-preview", "create-context-pack"}:
                self._handle_project_editor_audition_next_action(method, project_id, preview_id, audition_id, action)
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.delete_audition(preview_id, audition_id)
                self.project_store.append_event(project_id, "editor_audition_deleted", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "deleted": True, "audition_id": audition_id})
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
