from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class ProgramRoutesPart002:
    def _handle_unified_command_center_release_trains_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/unified-command-center-release-trains":
                if method == "GET":
                    trains = self.unified_command_center_release_train_store.list_trains()
                    self._send_json({"ok": True, "trains": trains, "summary": {"train_count": len(trains)}})
                    return
                if method == "POST":
                    train = self.unified_command_center_release_train_store.create_train(self._optional_json_body())
                    self._send_json({"ok": True, "train": train, "summary": {"train_id": train.get("train_id")}, "status": train.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            prefix = "/api/unified-command-center-release-trains/"
            if not path.startswith(prefix):
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Release Train route not found.")
                return
            parts = path.removeprefix(prefix).strip("/").split("/")
            train_id = parts[0]
            tail = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                train = self.unified_command_center_release_train_store.read_train(train_id)
                docs = self.unified_command_center_release_train_store.read_docs(train_id) if self.unified_command_center_release_train_store.report_path(train_id).exists() else {}
                report = docs.get("report", {}) if docs else {}
                self._send_json({"ok": True, "train": train, "docs": docs, "summary": report.get("summary", {}), "status": report.get("status") or train.get("status")})
                return
            if tail == "/lifecycle":
                if method == "GET":
                    report = self.unified_command_center_release_train_lifecycle_store.read_report(train_id) if self.unified_command_center_release_train_lifecycle_store.report_path(train_id).exists() else {}
                    self._send_json({"ok": True, "report": report, "summary": report.get("summary", {}) if report else {}, "status": report.get("status") if report else "not_configured"})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/lifecycle/"):
                lifecycle_tail = tail.removeprefix("/lifecycle/").strip("/")
                if lifecycle_tail == "refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_release_train_lifecycle_store.refresh_report(train_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if lifecycle_tail == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.unified_command_center_release_train_lifecycle_store.export_package(train_id, self._optional_json_body())
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                if lifecycle_tail == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_release_train_lifecycle_store.build_zip(train_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if lifecycle_tail == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_release_train_lifecycle_store.verify_package(train_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if lifecycle_tail == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_release_train_lifecycle_store.zip_path(train_id), "application/zip", filename="musicforge-unified-command-center-release-train-lifecycle.zip")
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Train Lifecycle route not found.")
                return
            if tail == "/handoffs":
                if method == "GET":
                    handoffs = self.unified_command_center_release_train_handoff_store.list_handoffs(train_id)
                    self._send_json({"ok": True, "handoffs": handoffs, "summary": {"handoff_count": len(handoffs)}, "status": "passed"})
                    return
                if method == "POST":
                    detail = self.unified_command_center_release_train_handoff_store.create_handoff(train_id, self._optional_json_body())
                    report = detail.get("report", {})
                    self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/handoffs/"):
                handoff_parts = tail.removeprefix("/handoffs/").strip("/").split("/")
                handoff_id = handoff_parts[0]
                action = "/".join(handoff_parts[1:]) if len(handoff_parts) > 1 else ""
                if action == "":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    detail = self.unified_command_center_release_train_handoff_store.get_handoff(train_id, handoff_id)
                    report = detail.get("report", {})
                    self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if action == "refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_release_train_handoff_store.refresh_report(train_id, handoff_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if action == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.unified_command_center_release_train_handoff_store.export_handoff(train_id, handoff_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_release_train_handoff_store.build_zip(train_id, handoff_id)
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_release_train_handoff_store.verify_package(train_id, handoff_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if action == "import-response":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_release_train_handoff_store.import_response(train_id, handoff_id, self._read_json_body())
                    self._send_json({"ok": result.get("verification", {}).get("status") == "passed", **result, "summary": result.get("verification", {}).get("summary", {}), "status": result.get("response", {}).get("decision")}, status=HTTPStatus.CREATED)
                    return
                if action.startswith("accepted-evidence/"):
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response_id = action.removeprefix("accepted-evidence/").strip("/")
                    evidence = self.unified_command_center_release_train_handoff_store.create_accepted_evidence(train_id, handoff_id, response_id)
                    self._send_json({"ok": True, "accepted_evidence": evidence, "summary": evidence.get("public_summary", {}), "status": "passed"}, status=HTTPStatus.CREATED)
                    return
                if action == "signoff":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    signoff = self.unified_command_center_release_train_handoff_store.signoff(train_id, handoff_id, self._optional_json_body())
                    self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signed_by": signoff.get("signed_by")}, "status": signoff.get("status")})
                    return
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_release_train_handoff_store.zip_path(train_id, handoff_id), "application/zip", filename="musicforge-unified-command-center-release-train-handoff.zip")
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Train Handoff route not found.")
                return
            if tail == "/changes":
                if method == "GET":
                    report = self.unified_command_center_release_train_change_control_store.refresh_report(train_id) if self.unified_command_center_release_train_change_control_store.change_dir(train_id).exists() else {}
                    requests = self.unified_command_center_release_train_change_control_store.list_requests(train_id)
                    self._send_json({"ok": True, "report": report, "change_requests": requests, "summary": report.get("summary", {}) if report else {}, "status": report.get("status") if report else "not_configured"})
                    return
                if method == "POST":
                    request = self.unified_command_center_release_train_change_control_store.create_request(train_id, self._optional_json_body())
                    self._send_json({"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/changes/"):
                change_tail = tail.removeprefix("/changes/").strip("/")
                if change_tail == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.unified_command_center_release_train_change_control_store.export_package(train_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                if change_tail == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_release_train_change_control_store.build_zip(train_id)
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if change_tail == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_release_train_change_control_store.verify_package(train_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if change_tail == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_release_train_change_control_store.zip_path(train_id), "application/zip", filename="musicforge-unified-command-center-release-train-change-control.zip")
                    return
                change_parts = change_tail.split("/")
                request_id = change_parts[0]
                action = "/" + "/".join(change_parts[1:]) if len(change_parts) > 1 else ""
                if action in {"", "/"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    request = self.unified_command_center_release_train_change_control_store.read_request(train_id, request_id)
                    self._send_json({"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")})
                    return
                if action == "/approve":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    approval = self.unified_command_center_release_train_change_control_store.approve_request(train_id, request_id, self._optional_json_body())
                    self._send_json({"ok": approval.get("status") == "approved", "approval": approval, "summary": {"approval_hash": approval.get("integrity_hash")}, "status": approval.get("status")})
                    return
                if action == "/reset":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    proof = self.unified_command_center_release_train_change_control_store.reset_train_signoff(train_id, request_id, self._optional_json_body())
                    self._send_json({"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Train Change Control route not found.")
                return
            if tail == "/items":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.unified_command_center_release_train_store.add_item(train_id, self._read_json_body())
                self._send_json({"ok": True, "item": item, "summary": {"item_id": item.get("item_id")}, "status": item.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_command_center_release_train_store.refresh(train_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "go", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_release_train_store.run_safe(train_id, self._optional_json_body())
                failed_count = int((result.get("summary") or {}).get("failed_count") or 0)
                self._send_json({"ok": failed_count == 0, "runbook_result": result, "summary": result.get("summary", {}), "status": "passed" if failed_count == 0 else "failed"})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_command_center_release_train_store.signoff(train_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/archive":
                if method == "GET":
                    manifest_path = self.unified_command_center_release_train_store.archive_manifest_path(train_id)
                    manifest = read_json(manifest_path) if manifest_path.exists() else {}
                    self._send_json({"ok": bool(manifest), "manifest": manifest, "summary": manifest.get("summary", {}) if manifest else {}})
                    return
                if method == "POST":
                    manifest = self.unified_command_center_release_train_store.export_archive(train_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_release_train_store.build_zip(train_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_command_center_release_train_store.verify_archive(train_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.unified_command_center_release_train_store.zip_path(train_id), "application/zip", filename="musicforge-unified-command-center-release-train.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Release Train route not found.")
        except UnifiedCommandCenterReleaseTrainNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterReleaseTrainChangeControlNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterReleaseTrainLifecycleNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterReleaseTrainStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedCommandCenterReleaseTrainChangeControlStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedCommandCenterReleaseTrainLifecycleStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedCommandCenterReleaseTrainChangeControlError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedCommandCenterReleaseTrainLifecycleError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedCommandCenterReleaseTrainError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_unified_release_programs_route(self, method: str, path: str) -> None:
        self.program_application.dispatch_http(self, method, path)
