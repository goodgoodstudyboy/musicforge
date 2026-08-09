from __future__ import annotations

from song_agent.application.http_ports import creation as creation_ports
from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class CreationProjectMixOperations(CreationRouteContext):
    def _handle_project_mix_route_part_01(
        self,
        method: str,
        project_id: str,
        version_id: str,
        action: str,
        resource_id: str | None,
        mix_store: creation_ports.MixRenderStore,
        control_store: creation_ports.MixControlStore,
    ) -> bool:
        if self._handle_mix_state_action(method, project_id, version_id, action, control_store):
            return True
        return self._handle_mix_preview_read_action(method, project_id, version_id, action, resource_id, mix_store)

    def _handle_mix_state_action(self, method: str, project_id: str, version_id: str, action: str, control_store: creation_ports.MixControlStore) -> bool:
        if action not in {"mix-state", "mix-state-reset"}:
            return False
        if action == "mix-state-reset" and method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        document = self.project_store.sync_project(project_id, self.store.get_job)
        version = next((item for item in document.versions if item.version_id == version_id), None)
        if version is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return True
        run_dir = _interfaces_api_runtime.Path(version.output_dir)
        plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(run_dir / "data" / "song-plan.json"))
        if action == "mix-state-reset":
            state = control_store.reset_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "mix_state_reset", {"version_id": version.version_id})
            self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
            return True
        if method == "GET":
            state = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict(), "summary": {"mix_state_hash": _interfaces_api_runtime.mix_state_hash(state)}})
            return True
        if method == "POST":
            current = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_interfaces_api_runtime._utc_now())
            state = control_store.write_state(type(current).from_dict({**self._read_json_body(), "project_id": project_id, "version_id": version.version_id, "updated_at": _interfaces_api_runtime._utc_now()}))
            self.project_store.append_event(project_id, "mix_state_saved", {"version_id": version.version_id, "mix_state_hash": _interfaces_api_runtime.mix_state_hash(state)})
            self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        return True

    def _handle_mix_preview_read_action(self, method: str, project_id: str, version_id: str, action: str, resource_id: str | None, mix_store: creation_ports.MixRenderStore) -> bool:
        if action == "mix-preview-create":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            preview, patch, _preview_dir = mix_store.create_preview(project_id=project_id, version_id=version_id, payload=self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "mix_preview_created", {"version_id": version_id, "preview_id": preview.preview_id, "patch_id": patch.patch_id})
            self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        if action not in {"mix-preview-detail", "mix-preview-midi"} or not resource_id:
            return False
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        preview = mix_store.read_preview(project_id, version_id, resource_id)
        if action == "mix-preview-detail":
            self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "integrity_ok": _interfaces_api_runtime.mix_preview_integrity_ok(preview)})
            return True
        if not _interfaces_api_runtime.mix_preview_integrity_ok(preview):
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Mix preview integrity failed.")
            return True
        self._send_file(mix_store.preview_dir(project_id, version_id, resource_id) / "song.mid", "audio/midi", filename=f"{project_id}-{resource_id}.mid")
        return True

    def _handle_project_mix_route_part_02(
        self,
        method: str,
        project_id: str,
        version_id: str,
        action: str,
        resource_id: str | None,
        mix_store: creation_ports.MixRenderStore,
    ) -> bool:
        if self._handle_mix_preview_mutation_action(method, project_id, version_id, action, resource_id, mix_store):
            return True
        return self._handle_mix_stem_action(method, project_id, version_id, action, mix_store)

    def _handle_mix_preview_mutation_action(self, method: str, project_id: str, version_id: str, action: str, resource_id: str | None, mix_store: creation_ports.MixRenderStore) -> bool:
        if action not in {"mix-preview-audio", "mix-preview-render-audio", "mix-preview-apply", "mix-preview-delete"} or not resource_id:
            return False
        if action == "mix-preview-audio":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            preview = mix_store.read_preview(project_id, version_id, resource_id)
            if not _interfaces_api_runtime.mix_preview_integrity_ok(preview):
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Mix preview integrity failed.")
                return True
            audio_path = mix_store.preview_dir(project_id, version_id, resource_id) / "song.wav"
            if not audio_path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mix preview audio is not available.")
                return True
            self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{resource_id}.wav")
            return True
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        if action == "mix-preview-render-audio":
            preview = mix_store.render_preview_audio(project_id=project_id, version_id=version_id, preview_id=resource_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict()})
        elif action == "mix-preview-apply":
            document, version, job = mix_store.apply_preview(project_id=project_id, version_id=version_id, preview_id=resource_id, payload=self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, **document, "version": version.to_dict(), "job": job.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        else:
            preview = mix_store.read_preview(project_id, version_id, resource_id)
            if preview.applied_version_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Applied mix previews cannot be deleted.")
                return True
            preview_dir = mix_store.preview_dir(project_id, version_id, resource_id)
            if preview_dir.exists():
                _interfaces_api_runtime.shutil.rmtree(preview_dir)
            self.project_store.append_event(project_id, "mix_preview_deleted", {"version_id": version_id, "preview_id": resource_id})
            self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview_id": resource_id, "deleted": True})
        return True

    def _handle_mix_stem_action(self, method: str, project_id: str, version_id: str, action: str, mix_store: creation_ports.MixRenderStore) -> bool:
        if action == "mix-stems-render":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            payload = self._optional_json_body()
            result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "mix_stems_rendered", {"version_id": version_id, "status": result["summary"].get("status")})
            self._send_json(result)
            return True
        if action != "mix-stems-health":
            return False
        document = self.project_store.sync_project(project_id, self.store.get_job)
        version = next((item for item in document.versions if item.version_id == version_id), None)
        if version is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return True
        if method == "GET":
            report = _interfaces_api_runtime.read_stem_health_report(_interfaces_api_runtime.Path(version.output_dir))
            self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "stem_health": report, "summary": _interfaces_api_runtime.stem_health_summary(report)})
            return True
        if method == "POST":
            payload = self._optional_json_body()
            result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_interfaces_api_runtime._utc_now())
            self._send_json(result)
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        return True
