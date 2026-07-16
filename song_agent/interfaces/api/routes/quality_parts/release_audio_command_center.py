from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAudioCommandCenter:
    def _handle_release_audio_command_center(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_command_center_store.read_report(release_id) if self.release_audio_command_center_store.report_path(release_id).exists() else {}
                inventory = self.release_audio_command_center_store.read_inventory(release_id) if self.release_audio_command_center_store.inventory_path(release_id).exists() else {}
                readiness = _interfaces_api_runtime.read_json(self.release_audio_command_center_store.readiness_path(release_id)) if self.release_audio_command_center_store.readiness_path(release_id).exists() else {}
                gap_plan = _interfaces_api_runtime.read_json(self.release_audio_command_center_store.gap_plan_path(release_id)) if self.release_audio_command_center_store.gap_plan_path(release_id).exists() else {}
                runbook = _interfaces_api_runtime.read_json(self.release_audio_command_center_store.runbook_path(release_id)) if self.release_audio_command_center_store.runbook_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "report": report, "inventory": inventory, "readiness": readiness, "gap_plan": gap_plan, "runbook": runbook, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_command_center_store.refresh(release_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/runbook":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook = self.release_audio_command_center_store.create_runbook(release_id, self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook.get("summary", {})})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.run_safe(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("summary", {}).get("failed_count") == 0, "release_id": release_id, "runbook_results": result, "summary": result.get("summary", {})})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.export_package(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.build_zip(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_command_center_store.verify_zip(release_id, evidence=payload, strict=bool(payload.get("strict", True)), require_ready=bool(payload.get("require_ready", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_command_center_store.zip_path(release_id), "application/zip", filename="release-audio-command-center.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Command Center route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCommandCenterNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCommandCenterStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCommandCenterError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_baselines_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-baselines":
                if method == "GET":
                    baselines = self.release_audio_baseline_governance_store.list_baselines()
                    self._send_json({"ok": True, "baselines": baselines, "summary": {"baseline_count": len(baselines)}})
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    release_id = str(payload.get("release_id") or "")
                    if not release_id:
                        self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "release_id is required.")
                        return
                    baseline = self.release_audio_baseline_governance_store.create_from_release(release_id, payload)
                    self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path == "/api/audio-baselines/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_baseline_governance_store.export_registry()
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if path == "/api/audio-baselines/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_baseline_governance_store.build_zip()
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if path == "/api/audio-baselines/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_baseline_governance_store.verify_zip(strict=bool(payload.get("strict", True)), require_active=bool(payload.get("require_active", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                return
            if path == "/api/audio-baselines/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_baseline_governance_store.zip_path(), "application/zip", filename="release-audio-baseline-registry.zip")
                return
            rest = path.removeprefix("/api/audio-baselines/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                baseline = self.release_audio_baseline_governance_store.read_baseline(parts[0])
                self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}})
                return
            if len(parts) == 2:
                baseline_id, action = parts
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "approve":
                    baseline = self.release_audio_baseline_governance_store.approve(baseline_id, self._read_json_body())
                elif action == "activate":
                    baseline = self.release_audio_baseline_governance_store.activate(baseline_id, self._optional_json_body())
                elif action == "revoke":
                    baseline = self.release_audio_baseline_governance_store.revoke(baseline_id, self._read_json_body())
                else:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Baseline route not found.")
                    return
                self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Baseline route not found.")
        except _interfaces_api_runtime.ReleaseAudioBaselineGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioBaselineGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioBaselineGovernanceValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioBaselineGovernanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_quality_observatories_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-quality-observatories":
                if method == "GET":
                    rows = self.release_audio_quality_observatory_store.list_observatories()
                    self._send_json({"ok": True, "observatories": rows, "summary": {"observatory_count": len(rows)}})
                    return
                if method == "POST":
                    config = self.release_audio_quality_observatory_store.create(self._optional_json_body())
                    self._send_json({"ok": True, "observatory": config, "summary": {"observatory_id": config.get("observatory_id")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-quality-observatories/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                observatory_id = parts[0]
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config = self.release_audio_quality_observatory_store.read_config(observatory_id)
                summary = self.release_audio_quality_observatory_store.read_summary(observatory_id) if self.release_audio_quality_observatory_store.summary_path(observatory_id).exists() else {}
                self._send_json({"ok": True, "observatory": config, "summary_report": summary, "summary": summary.get("summary", {}) if summary else {}})
                return
            if len(parts) == 2:
                observatory_id, action = parts
                if action == "download":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_observatory_store.zip_path(observatory_id), "application/zip", filename="release-audio-quality-observatory.zip")
                    return
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if action == "refresh":
                    summary = self.release_audio_quality_observatory_store.refresh(observatory_id, payload)
                    self._send_json({"ok": summary.get("status") == "passed", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")})
                    return
                if action == "export":
                    result = self.release_audio_quality_observatory_store.export_package(observatory_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "zip":
                    result = self.release_audio_quality_observatory_store.build_zip(observatory_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "verify":
                    report = self.release_audio_quality_observatory_store.verify_zip(
                        observatory_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_evidence=bool(payload.get("require_current_evidence", False)),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                        require_no_critical_risk=bool(payload.get("require_no_critical_risk", False)),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Quality Observatory route not found.")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Quality Observatory route not found.")
        except _interfaces_api_runtime.ReleaseAudioQualityObservatoryNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityObservatoryStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityObservatoryValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityObservatoryError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
