from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectFinalExport:
    def _handle_project_final_export(self, method: str, project_id: str) -> None:
        if method == "GET":
            try:
                project_dir = self.project_store.project_dir(project_id)
                self.project_store.get_project(project_id)
                manifest = _interfaces_api_runtime.read_final_export_manifest(project_dir)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Final export not found.")
                return
            self._send_json({"final_export": manifest})
            return
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        payload = self._optional_json_body()
        options = _interfaces_api_runtime.FinalExportOptions.from_dict(payload)
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return

        version_id = options.version_id or document.state.final_version_id
        if not version_id:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Project has no final version.")
            return
        version = next((item for item in document.versions if item.version_id == version_id), None)
        if version is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        if version.status != "completed":
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Only completed versions can be exported.")
            return
        if self.store.get_job(version.job_id) is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Version job is missing.")
            return

        gate_result = self._evaluate_project_version(project_id, version)
        document = self.project_store.update_version_quality_gate(project_id, version.version_id, gate_result)
        version = next(item for item in document.versions if item.version_id == version_id)
        if gate_result.status not in {"passed", "warning"} and not options.force:
            self.project_store.append_event(
                project_id,
                "final_export_gate_failed",
                {"version_id": version.version_id, "status": gate_result.status, "score": gate_result.score},
            )
            self._send_json(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": gate_result.to_dict(),
                },
                status=_interfaces_api_runtime.HTTPStatus.CONFLICT,
            )
            return

        project_dir = self.project_store.project_dir(project_id)
        project_export = self.project_store.export_project(project_id)
        document = self.project_store.get_project(project_id)
        version = next(item for item in document.versions if item.version_id == version_id)
        try:
            manifest = _interfaces_api_runtime.build_final_export_bundle(
                project=document.state,
                version=version,
                project_dir=project_dir,
                run_dir=_interfaces_api_runtime.Path(version.output_dir),
                gate=gate_result,
                options=options,
                now=_interfaces_api_runtime._utc_now(),
                project_export=project_export,
            )
        except _interfaces_api_runtime.FinalExportError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        document = self.project_store.update_version_final_export(
            project_id,
            version.version_id,
            _interfaces_api_runtime.final_export_dir(project_dir),
        )
        version = next(item for item in document.versions if item.version_id == version_id)
        self._send_json(
            {
                "ok": True,
                "version": version.to_dict(),
                "quality_gate": gate_result.to_dict(),
                "final_export": manifest,
                **document.to_dict(),
            }
        )

    def _handle_project_final_export_zip(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_info = _interfaces_api_runtime.build_final_export_zip(project_dir, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "final_export_zip_created", zip_info)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Final export has not been generated.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "zip": zip_info})

    def _handle_project_final_export_zip_download(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_path = _interfaces_api_runtime.final_export_zip_path(project_dir)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_file(zip_path, "application/zip", filename=f"musicforge-{project_id}-final-export.zip")

    def _handle_project_delivery_qa(self, method: str, project_id: str, *, refresh: bool) -> None:
        if refresh and method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if not refresh and method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self._get_or_refresh_delivery_qa(project_id, refresh=refresh)
            if refresh:
                self.project_store.append_event(project_id, "delivery_qa_refreshed", {"status": report.get("status"), "readiness": report.get("readiness")})
            self._send_json({"ok": True, "project_id": project_id, "delivery_qa": report, "summary": _interfaces_api_runtime.delivery_qa_summary(report)})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))

    def _handle_project_delivery_signoff(self, method: str, project_id: str, *, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if action == "get":
            if method == "GET":
                signoff = self.project_store.read_delivery_signoff(project_id, default={})
                self._send_json({"ok": True, "project_id": project_id, "signoff": signoff, "summary": _interfaces_api_runtime.delivery_signoff_summary(signoff)})
                return
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            existing = self.project_store.read_delivery_signoff(project_id, default={})
            if existing:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Delivery is already signed off. Reset signoff before signing again.")
                return
            report = self._get_or_refresh_delivery_qa(project_id, refresh=True)
            force = bool(payload.get("force", False))
            if not _interfaces_api_runtime.delivery_qa_allows_signoff(report) and not force:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Delivery QA gate failed. Refresh QA or pass force=true with override_reason.")
                return
            if force and not str(payload.get("override_reason") or "").strip():
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
                return
            try:
                record = _interfaces_api_runtime.build_delivery_signoff_record(project_id=project_id, report=report, payload={**payload, "force": force}, now=_interfaces_api_runtime._utc_now())
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            signoff = self.project_store.write_delivery_signoff(project_id, record, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "delivery_force_signed" if force else "delivery_signed", {"status": report.get("status"), "final_version_id": signoff.get("final_version_id"), "forced": force})
            self._send_json({"ok": True, "project_id": project_id, "signoff": signoff, "summary": _interfaces_api_runtime.delivery_signoff_summary(signoff)})
            return
        if action == "reset":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            reason = str(payload.get("reason") or "").strip()
            if not reason:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "reason is required to reset delivery signoff.")
                return
            existing = self.project_store.read_delivery_signoff(project_id, default={})
            if not existing:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Delivery signoff does not exist.")
                return
            event = _interfaces_api_runtime.signoff_history_event("delivery_signoff_reset", existing, reason, now=_interfaces_api_runtime._utc_now())
            self.project_store.reset_delivery_signoff(project_id, event)
            self.project_store.append_event(project_id, "delivery_signoff_reset", {"reason": event.get("reason"), "previous_status": _interfaces_api_runtime.delivery_signoff_summary(existing).get("status")})
            self._send_json({"ok": True, "project_id": project_id, "summary": {"status": "reset"}, "history_event": event})
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Delivery signoff route not found.")

    def _renderer_profile_from_payload(self, payload: ImplementationDocument | None) -> _interfaces_api_runtime.Any | None:
        profile_id = str((payload or {}).get("profile_id") or "").strip()
        if not profile_id:
            return None
        return self.audio_profile_store.get_profile(profile_id)

    def _renderer_config_from_payload(self, payload: ImplementationDocument | None) -> _interfaces_api_runtime.Any | None:
        profile = self._renderer_profile_from_payload(payload)
        if profile is None:
            return None
        return profile.to_renderer_config()

    def _evaluate_project_version(self, project_id: str, version: Any) -> _interfaces_api_runtime.Any:
        config = _interfaces_api_runtime.load_quality_gate_config(self.project_store.project_dir(project_id))
        return _interfaces_api_runtime.evaluate_quality_gate(_interfaces_api_runtime.Path(version.output_dir), config, now=_interfaces_api_runtime._utc_now())

    def _handle_project_variation(self, method: str, project_id: str, parent_version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            parent = next(version for version in document.versions if version.version_id == parent_version_id)
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Parent version job is missing.")
            return
        request_patch = payload.get("request_patch") or {}
        if not isinstance(request_patch, dict):
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "request_patch must be an object.")
            return
        try:
            request_payload = _interfaces_api_runtime._variation_request_payload(
                parent.request,
                request_patch,
                generation_mode=payload.get("generation_mode"),
                pipeline_mode=payload.get("pipeline_mode"),
            )
            if isinstance(payload.get("asset_refs"), list):
                request_payload["asset_refs"] = payload["asset_refs"]
            if isinstance(payload.get("reference_refs"), list):
                request_payload["reference_refs"] = payload["reference_refs"]
            if payload.get("context_pack_id"):
                request_payload["context_pack_id"] = payload["context_pack_id"]
            request_payload = self._expand_context_pack_payload(request_payload)
            job = self.store.create_job(request_payload)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or ""),
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=str(payload.get("variant_type") or "manual"),
                change_summary=str(payload.get("change_summary") or ""),
            )
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        version = next(version for version in document.versions if version.job_id == job.job_id)
        self.project_store.append_event(
            project_id,
            "variation_created",
            {
                "parent_version_id": parent.version_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
                "variant_type": version.variant_type,
            },
        )
        self._send_json(
            {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
            status=_interfaces_api_runtime.HTTPStatus.ACCEPTED,
        )
