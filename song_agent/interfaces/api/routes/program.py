from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *

class ProgramRoutes:
    @property
    def unified_command_center_store(self) -> UnifiedCommandCenterStore:
        store = self.server.unified_command_center_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        return store

    @property
    def unified_command_center_signoff_store(self) -> UnifiedCommandCenterSignoffStore:
        store = self.server.unified_command_center_signoff_store  # type: ignore[attr-defined]
        store.center_store = self.unified_command_center_store
        return store

    @property
    def unified_command_center_handoff_store(self) -> UnifiedCommandCenterHandoffStore:
        store = self.server.unified_command_center_handoff_store  # type: ignore[attr-defined]
        store.signoff_store = self.unified_command_center_signoff_store
        return store

    @property
    def unified_command_center_continuous_review_store(self) -> UnifiedCommandCenterContinuousReviewStore:
        store = self.server.unified_command_center_continuous_review_store  # type: ignore[attr-defined]
        store.center_store = self.unified_command_center_store
        store.signoff_store = self.unified_command_center_signoff_store
        store.handoff_store = self.unified_command_center_handoff_store
        return store

    @property
    def unified_command_center_drift_response_store(self) -> UnifiedCommandCenterDriftResponseStore:
        store = self.server.unified_command_center_drift_response_store  # type: ignore[attr-defined]
        store.center_store = self.unified_command_center_store
        store.signoff_store = self.unified_command_center_signoff_store
        store.handoff_store = self.unified_command_center_handoff_store
        store.review_store = self.unified_command_center_continuous_review_store
        return store

    @property
    def unified_command_center_evidence_review_store(self) -> UnifiedCommandCenterEvidenceReviewStore:
        store = self.server.unified_command_center_evidence_review_store  # type: ignore[attr-defined]
        store.center_store = self.unified_command_center_store
        store.signoff_store = self.unified_command_center_signoff_store
        store.handoff_store = self.unified_command_center_handoff_store
        store.review_store = self.unified_command_center_continuous_review_store
        store.drift_response_store = self.unified_command_center_drift_response_store
        return store

    @property
    def unified_command_center_reviewer_decision_board_store(self) -> UnifiedCommandCenterReviewerDecisionBoardStore:
        store = self.server.unified_command_center_reviewer_decision_board_store  # type: ignore[attr-defined]
        store.center_store = self.unified_command_center_store
        store.evidence_review_store = self.unified_command_center_evidence_review_store
        return store

    @property
    def unified_command_center_release_train_store(self) -> UnifiedCommandCenterReleaseTrainStore:
        return self.server.unified_command_center_release_train_store  # type: ignore[attr-defined]

    @property
    def unified_command_center_release_train_change_control_store(self) -> UnifiedCommandCenterReleaseTrainChangeControlStore:
        return self.server.unified_command_center_release_train_change_control_store  # type: ignore[attr-defined]

    @property
    def unified_command_center_release_train_lifecycle_store(self) -> UnifiedCommandCenterReleaseTrainLifecycleStore:
        return self.server.unified_command_center_release_train_lifecycle_store  # type: ignore[attr-defined]

    @property
    def unified_command_center_release_train_handoff_store(self) -> UnifiedCommandCenterReleaseTrainHandoffStore:
        return self.server.unified_command_center_release_train_handoff_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_store(self) -> UnifiedReleaseProgramStore:
        return self.server.unified_release_program_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_operations_store(self) -> UnifiedReleaseProgramOperationsStore:
        return self.server.unified_release_program_operations_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_handoff_store(self) -> UnifiedReleaseProgramHandoffStore:
        return self.server.unified_release_program_handoff_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_vault_store(self) -> UnifiedReleaseProgramVaultStore:
        return self.server.unified_release_program_vault_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_vault_operations_store(self) -> UnifiedReleaseProgramVaultOperationsStore:
        return self.server.unified_release_program_vault_operations_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_store(self) -> UnifiedReleaseProgramContinuityStore:
        return self.server.unified_release_program_continuity_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_distribution_store(self) -> UnifiedReleaseProgramContinuityDistributionStore:
        return self.server.unified_release_program_continuity_distribution_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_acceptance_store(self) -> UnifiedReleaseProgramContinuityAcceptanceStore:
        return self.server.unified_release_program_continuity_acceptance_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_acceptance_change_store(self) -> UnifiedReleaseProgramContinuityAcceptanceChangeStore:
        return self.server.unified_release_program_continuity_acceptance_change_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_command_center_store(self) -> UnifiedReleaseProgramContinuityCommandCenterStore:
        return self.server.unified_release_program_continuity_command_center_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_command_center_signoff_store(self) -> UnifiedReleaseProgramContinuityCommandCenterSignoffStore:
        return self.server.unified_release_program_continuity_command_center_signoff_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_command_center_acceptance_store(self) -> UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore:
        return self.server.unified_release_program_continuity_command_center_acceptance_store  # type: ignore[attr-defined]

    @property
    def unified_release_program_continuity_command_center_acceptance_change_store(self) -> UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore:
        return self.server.unified_release_program_continuity_command_center_acceptance_change_store  # type: ignore[attr-defined]

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
        try:
            if path == "/api/unified-release-programs":
                if method == "GET":
                    programs = self.unified_release_program_store.list_programs()
                    self._send_json({"ok": True, "programs": programs, "summary": {"program_count": len(programs)}})
                    return
                if method == "POST":
                    program = self.unified_release_program_store.create_program(self._optional_json_body())
                    self._send_json({"ok": True, "program": program, "summary": {"program_id": program.get("program_id")}, "status": program.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            prefix = "/api/unified-release-programs/"
            if not path.startswith(prefix):
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Release Program route not found.")
                return
            parts = path.removeprefix(prefix).strip("/").split("/")
            program_id = parts[0]
            tail = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_store.get_program(program_id)
                report = detail.get("report", {})
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or detail.get("program", {}).get("status")})
                return
            if tail == "/items":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.unified_release_program_store.add_train_item(program_id, self._read_json_body())
                self._send_json({"ok": True, "item": item, "summary": {"item_id": item.get("item_id")}, "status": item.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_store.refresh_report(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_store.signoff(program_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_store.export_program(program_id)
                self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_store.build_zip(program_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_store.verify_package(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_store.gate(
                    program_zip_path=payload.get("program_zip"),
                    verification_report_path=payload.get("program_verification_report"),
                    external_evidence_manifest_path=payload.get("external_evidence_manifest"),
                    program_signoff_binding_path=payload.get("program_signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/handoff":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_handoff_store.get_handoff(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_handoff_store.refresh_handoff(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") in {"ready_for_review", "ready_for_signoff"}, "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/review-pack":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.unified_release_program_handoff_store.export_review_pack(program_id, self._optional_json_body())
                self._send_json({"ok": pack.get("status") == "ready", "review_pack": pack, "summary": {"review_pack_id": pack.get("review_pack_id")}, "status": pack.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/handoff/review-packs/") and tail.endswith("/zip"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review_pack_id = tail.split("/")[3]
                result = self.unified_release_program_handoff_store.build_review_pack_zip(program_id, review_pack_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail.startswith("/handoff/review-packs/") and tail.endswith("/verify"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review_pack_id = tail.split("/")[3]
                report = self.unified_release_program_handoff_store.verify_review_pack_zip(program_id, review_pack_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/responses/import":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                response = self.unified_release_program_handoff_store.import_response(program_id, self._read_json_body())
                self._send_json({"ok": response.get("status") == "imported", "response": response.get("response"), "verification": response.get("verification"), "summary": {"response_id": response.get("response", {}).get("response_id")}, "status": response.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/handoff/responses/") and tail.endswith("/accepted-evidence"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                response_id = tail.split("/")[3]
                result = self.unified_release_program_handoff_store.create_accepted_evidence(program_id, response_id)
                self._send_json({"ok": result.get("status") == "accepted", **result, "summary": {"evidence_id": result.get("evidence", {}).get("evidence_id")}}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/handoff/accepted-evidence/") and tail.endswith("/zip"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                evidence_id = tail.split("/")[3]
                result = self.unified_release_program_handoff_store.build_accepted_evidence_zip(program_id, evidence_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail.startswith("/handoff/accepted-evidence/") and tail.endswith("/verify"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                evidence_id = tail.split("/")[3]
                report = self.unified_release_program_handoff_store.verify_accepted_evidence_zip(program_id, evidence_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/decision-board/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                board = self.unified_release_program_handoff_store.refresh_decision_board(program_id, self._optional_json_body())
                self._send_json({"ok": board.get("status") == "ready_for_signoff", "decision_board": board, "summary": board.get("readiness", {}), "status": board.get("status")})
                return
            if tail == "/handoff/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_handoff_store.signoff_handoff(program_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/handoff/archive/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_handoff_store.export_handoff_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/handoff/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_handoff_store.build_handoff_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/handoff/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_handoff_store.verify_handoff_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_handoff_store.gate(
                    program_id,
                    required=True,
                    handoff_archive_zip_path=payload.get("handoff_archive_zip"),
                    handoff_archive_verification_report_path=payload.get("handoff_archive_verification_report"),
                    external_evidence_manifest=payload.get("external_evidence_manifest"),
                    handoff_signoff_binding=payload.get("handoff_signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/vault":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_vault_store.get_vault(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/vault/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_vault_store.refresh_vault(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/vault/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_vault_store.export_vault(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/vault/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_vault_store.build_vault_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "anchor_path": result.get("anchor_path")}})
                return
            if tail == "/vault/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_vault_store.verify_vault_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/vault/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_vault_store.gate(
                    program_id,
                    required=True,
                    vault_zip_path=payload.get("vault_zip") or payload.get("vault"),
                    vault_verification_report_path=payload.get("vault_verification_report"),
                    vault_anchor_path=payload.get("vault_anchor") or payload.get("anchor"),
                    require_current_program=bool(payload.get("require_current_program", False)),
                    require_current_operations=bool(payload.get("require_current_operations", False)),
                    require_current_handoff=bool(payload.get("require_current_handoff", False)),
                    require_accepted_evidence=bool(payload.get("require_accepted_evidence", True)),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/vault-operations":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_vault_operations_store.get_operations(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/vault-operations/policy":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                policy = self.unified_release_program_vault_operations_store.init_policy(program_id, self._optional_json_body())
                self._send_json({"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/vault-operations/register-vault":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                registry = self.unified_release_program_vault_operations_store.register_vault(program_id, self._optional_json_body())
                self._send_json({"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/vault-operations/refresh-registry":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                registry = self.unified_release_program_vault_operations_store.refresh_registry(program_id, self._optional_json_body())
                self._send_json({"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")})
                return
            if tail == "/vault-operations/review":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.unified_release_program_vault_operations_store.run_custody_review(program_id, self._optional_json_body())
                self._send_json({"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")})
                return
            if tail == "/vault-operations/rotation-plan":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.unified_release_program_vault_operations_store.create_rotation_plan(program_id, self._optional_json_body())
                self._send_json({"ok": True, "rotation_plan": plan, "summary": {"plan_id": plan.get("plan_id")}, "status": plan.get("status")})
                return
            if tail == "/vault-operations/supersede":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                registry = self.unified_release_program_vault_operations_store.supersede_vault(program_id, self._optional_json_body())
                self._send_json({"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")})
                return
            if tail == "/vault-operations/revoke":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                registry = self.unified_release_program_vault_operations_store.revoke_vault(program_id, self._optional_json_body())
                self._send_json({"ok": registry.get("status") != "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")})
                return
            if tail == "/vault-operations/transfer-pack":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                transfer = self.unified_release_program_vault_operations_store.create_transfer_pack(program_id, self._optional_json_body())
                self._send_json({"ok": transfer.get("status") == "ready", "transfer_report": transfer, "summary": transfer.get("summary", {}), "status": transfer.get("status")})
                return
            if tail == "/vault-operations/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_vault_operations_store.signoff_operations(program_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/vault-operations/archive/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_vault_operations_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/vault-operations/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_vault_operations_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/vault-operations/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_vault_operations_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/vault-operations/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_vault_operations_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip") or payload.get("vault_operations_archive"),
                    verification_report_path=payload.get("verification_report") or payload.get("vault_operations_verification_report"),
                    signoff_binding_path=payload.get("signoff_binding") or payload.get("vault_operations_signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_store.get_continuity(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity/policy":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                policy = self.unified_release_program_continuity_store.init_policy(program_id, self._optional_json_body())
                self._send_json({"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity/plan":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.unified_release_program_continuity_store.create_recovery_plan(program_id, self._optional_json_body())
                self._send_json({"ok": plan.get("status") == "planned", "recovery_plan": plan, "summary": {"plan_hash": plan.get("integrity_hash")}, "status": plan.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity/drill":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                drill = self.unified_release_program_continuity_store.run_recovery_drill(program_id, self._optional_json_body())
                self._send_json({"ok": drill.get("status") == "passed", "drill_report": drill, "summary": drill.get("summary", {}), "status": drill.get("status")})
                return
            if tail == "/continuity/readiness":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                readiness = self.unified_release_program_continuity_store.refresh_readiness(program_id, self._optional_json_body())
                self._send_json({"ok": readiness.get("status") == "passed", "readiness": readiness, "summary": readiness.get("summary", {}), "status": readiness.get("status")})
                return
            if tail == "/continuity/runbook":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook = self.unified_release_program_continuity_store.generate_runbook(program_id, self._optional_json_body())
                self._send_json({"ok": runbook.get("status") == "ready", "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")})
                return
            if tail == "/continuity/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_continuity_store.signoff_continuity(program_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity/archive/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/continuity/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/continuity/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip") or payload.get("continuity_archive"),
                    verification_report_path=payload.get("verification_report") or payload.get("continuity_verification_report"),
                    signoff_binding_path=payload.get("signoff_binding") or payload.get("continuity_signoff_binding"),
                    vault_operations_archive_path=payload.get("vault_operations_archive"),
                    vault_operations_verification_report_path=payload.get("vault_operations_verification_report"),
                    vault_operations_signoff_binding_path=payload.get("vault_operations_signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity-kit":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_distribution_store.get_kit(program_id)
                source = detail.get("source_binding") or {}
                self._send_json({"ok": True, **detail, "summary": source, "status": source.get("status") or "unknown"})
                return
            if tail == "/continuity-kit/prepare":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                source = self.unified_release_program_continuity_distribution_store.prepare_kit(program_id, self._optional_json_body())
                self._send_json({"ok": source.get("status") == "passed", "source_binding": source, "summary": source, "status": source.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity-kit/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_distribution_store.export_kit(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/continuity-kit/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_distribution_store.build_kit_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/continuity-kit/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_distribution_store.verify_kit(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-kit/receipt-template":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.unified_release_program_continuity_distribution_store.create_receiver_receipt_template(program_id, self._optional_json_body())
                self._send_json({"ok": True, "receiver_receipt_template": template, "summary": {"kit_sha256": template.get("kit_sha256")}, "status": "passed"})
                return
            if tail == "/continuity-kit/receipts":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                receipt = self.unified_release_program_continuity_distribution_store.import_receiver_receipt(program_id, self._read_json_body())
                self._send_json({"ok": receipt.get("decision") == "accepted", "receiver_receipt": receipt, "summary": {"receipt_id": receipt.get("receipt_id")}, "status": receipt.get("decision")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/continuity-kit/receipts/") and tail.endswith("/verify"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                receipt_id = tail.split("/")[3]
                report = self.unified_release_program_continuity_distribution_store.verify_receiver_receipt(program_id, receipt_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-kit/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_distribution_store.gate(
                    program_id,
                    required=True,
                    kit_zip_path=payload.get("kit_zip") or payload.get("continuity_kit"),
                    verification_report_path=payload.get("verification_report") or payload.get("continuity_kit_verification_report"),
                    receiver_receipt_path=payload.get("receiver_receipt"),
                    require_receiver_receipt=bool(payload.get("require_receiver_receipt", False)),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity-acceptance":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_acceptance_store.get_board(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"})
                return
            if tail == "/continuity-acceptance/responses":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_acceptance_store.import_response(program_id, self._read_json_body())
                self._send_json({"ok": result.get("status") == "imported", **result, "summary": {"response_id": result.get("response", {}).get("response_id")}, "status": result.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/continuity-acceptance/responses/") and tail.endswith("/accepted-evidence"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                response_id = tail.split("/")[3]
                result = self.unified_release_program_continuity_acceptance_store.create_accepted_evidence(program_id, response_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "accepted", **result, "summary": {"evidence_id": result.get("evidence", {}).get("evidence_id")}, "status": result.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity-acceptance/board":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                board = self.unified_release_program_continuity_acceptance_store.refresh_decision_board(program_id, self._optional_json_body())
                self._send_json({"ok": board.get("status") == "ready_for_signoff", "board": board, "summary": board.get("readiness", {}), "status": board.get("status")})
                return
            if tail == "/continuity-acceptance/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_continuity_acceptance_store.signoff_acceptance(program_id, self._read_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")})
                return
            if tail == "/continuity-acceptance/archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_acceptance_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/continuity-acceptance/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_acceptance_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/continuity-acceptance/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_acceptance_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-acceptance/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_acceptance_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip") or payload.get("continuity_acceptance_archive"),
                    verification_report_path=payload.get("verification_report") or payload.get("continuity_acceptance_verification_report"),
                    continuity_kit=payload.get("continuity_kit"),
                    continuity_kit_verification_report=payload.get("continuity_kit_verification_report"),
                    signoff_binding=payload.get("signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity-acceptance/change-control":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_acceptance_change_store.get_state(program_id)
                state = detail.get("state") or {}
                self._send_json({"ok": True, **detail, "summary": state, "status": state.get("status") or "unknown"})
                return
            if tail == "/continuity-acceptance/change-control/change-requests":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request = self.unified_release_program_continuity_acceptance_change_store.create_change_request(program_id, self._optional_json_body())
                self._send_json({"ok": request.get("status") in {"submitted", "approved"}, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/continuity-acceptance/change-control/change-requests/") and tail.endswith("/approve"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request_id = tail.split("/")[4]
                approval = self.unified_release_program_continuity_acceptance_change_store.approve_change_request(program_id, request_id, self._optional_json_body())
                self._send_json({"ok": approval.get("status") == "approved", "approval": approval, "summary": {"change_request_id": approval.get("change_request_id")}, "status": approval.get("status")})
                return
            if tail == "/continuity-acceptance/change-control/reset-signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                proof = self.unified_release_program_continuity_acceptance_change_store.reset_acceptance_signoff(program_id, payload)
                self._send_json({"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_proof_hash": proof.get("integrity_hash")}, "status": proof.get("status")})
                return
            if tail == "/continuity-acceptance/change-control/lifecycle":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_acceptance_change_store.refresh_lifecycle_audit(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "lifecycle_report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-acceptance/change-control/archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_acceptance_change_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/continuity-acceptance/change-control/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_acceptance_change_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/continuity-acceptance/change-control/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_acceptance_change_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-acceptance/change-control/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_acceptance_change_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip") or payload.get("change_control_archive"),
                    verification_report_path=payload.get("verification_report") or payload.get("change_control_verification_report"),
                    acceptance_archive=payload.get("acceptance_archive"),
                    acceptance_verification_report=payload.get("acceptance_verification_report"),
                    acceptance_signoff_binding=payload.get("acceptance_signoff_binding"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity-command-center":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_command_center_store.get_command_center(program_id)
                report = detail.get("report") or {}
                self._send_json({"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"})
                return
            if tail == "/continuity-command-center/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_store.refresh_command_center(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-command-center/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_store.run_safe(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") in {"passed", "warning"}, "runbook_result": result, "summary": result.get("summary", {}), "status": result.get("status")})
                return
            if tail == "/continuity-command-center/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_command_center_store.export_package(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/continuity-command-center/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_store.build_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}})
                return
            if tail == "/continuity-command-center/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_store.verify_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/continuity-command-center/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_command_center_store.gate(
                    program_id,
                    required=True,
                    command_center_zip_path=payload.get("command_center_zip") or payload.get("continuity_command_center"),
                    verification_report_path=payload.get("verification_report") or payload.get("command_center_verification_report"),
                    evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("evidence_manifest"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")})
                return
            if tail == "/continuity-command-center-signoff":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                state = self.unified_release_program_continuity_command_center_signoff_store.get_state(program_id)
                self._send_json({"ok": True, **state, "summary": {"status": state.get("status")}})
                return
            if tail == "/continuity-command-center-signoff/preflight":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_signoff_store.preflight(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "preflight": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            if tail == "/continuity-command-center-signoff/sign":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_continuity_command_center_signoff_store.signoff(program_id, self._optional_json_body())
                self._send_json({"ok": True, "signoff": signoff, "status": signoff.get("status"), "summary": signoff.get("summary", {})})
                return
            if tail == "/continuity-command-center-signoff/change-requests":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request = self.unified_release_program_continuity_command_center_signoff_store.create_change_request(program_id, self._optional_json_body())
                self._send_json({"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/continuity-command-center-signoff/change-requests/") and tail.endswith("/approve"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request_id = tail.split("/")[3]
                approval = self.unified_release_program_continuity_command_center_signoff_store.approve_change_request(program_id, request_id, self._optional_json_body())
                self._send_json({"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"change_request_id": request_id}})
                return
            if tail == "/continuity-command-center-signoff/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                proof = self.unified_release_program_continuity_command_center_signoff_store.reset_signoff(program_id, str(payload.get("change_request_id") or ""), payload)
                self._send_json({"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_event_hash": proof.get("reset_event_hash")}})
                return
            if tail == "/continuity-command-center-signoff/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_command_center_signoff_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}})
                return
            if tail == "/continuity-command-center-signoff/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_signoff_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": True, **result})
                return
            if tail == "/continuity-command-center-signoff/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_signoff_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            if tail == "/continuity-command-center-signoff/handoff/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_command_center_signoff_store.export_final_handoff(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}})
                return
            if tail == "/continuity-command-center-signoff/handoff/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_signoff_store.build_final_handoff_zip(program_id, self._optional_json_body())
                self._send_json({"ok": True, **result})
                return
            if tail == "/continuity-command-center-signoff/handoff/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_signoff_store.verify_final_handoff_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            if tail == "/continuity-command-center-signoff/gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.unified_release_program_continuity_command_center_signoff_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip"),
                    archive_verification_report_path=payload.get("archive_verification_report"),
                    signoff_binding_path=payload.get("signoff_binding"),
                    command_center_zip_path=payload.get("command_center"),
                    command_center_verification_report_path=payload.get("command_center_verification_report"),
                    command_center_external_evidence_manifest_path=payload.get("command_center_external_evidence_manifest"),
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})})
                return
            if tail == "/continuity-command-center-acceptance":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                state = self.unified_release_program_continuity_command_center_acceptance_store.status(program_id)
                self._send_json({"ok": True, **state})
                return
            if tail == "/continuity-command-center-acceptance/review-pack":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_acceptance_store.create_review_pack(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity-command-center-acceptance/review-pack/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_acceptance_store.verify_review_pack(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            if tail == "/continuity-command-center-acceptance/responses/import":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                forbidden = sorted({str(key) for key in payload if str(key).lower() in {"source_path", "local_path", "file_path", "path"}})
                if forbidden:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Receiver response import does not accept path fields: " + ", ".join(forbidden))
                    return
                result = self.unified_release_program_continuity_command_center_acceptance_store.import_response(program_id, payload)
                self._send_json({"ok": result.get("status") == "imported", **result, "summary": {"response_id": result["response"].get("response_id")}}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/continuity-command-center-acceptance/responses/") and tail.endswith("/accepted-evidence"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                response_id = tail.split("/")[3]
                result = self.unified_release_program_continuity_command_center_acceptance_store.create_accepted_evidence(program_id, response_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "accepted", **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/continuity-command-center-acceptance/board/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_acceptance_store.refresh_board(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "ready_for_signoff", "report": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            if tail == "/continuity-command-center-acceptance/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_release_program_continuity_command_center_acceptance_store.signoff(program_id, self._optional_json_body())
                self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "status": signoff.get("status"), "summary": {"signoff_hash": signoff.get("integrity_hash")}})
                return
            if tail == "/continuity-command-center-acceptance/archive/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_continuity_command_center_acceptance_store.export_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}})
                return
            if tail == "/continuity-command-center-acceptance/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_continuity_command_center_acceptance_store.build_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/continuity-command-center-acceptance/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_continuity_command_center_acceptance_store.verify_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})})
                return
            change_roots = {
                "/continuity-command-center-acceptance/change-control",
                "/continuity-command-center/acceptance/change",
            }
            if tail in change_roots:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.unified_release_program_continuity_command_center_acceptance_change_store.get_state(program_id)
                state = detail.get("state") or {}
                self._send_json({"ok": True, **detail, "status": state.get("status") or "not_configured", "summary": state})
                return
            if tail in {root + "/cr" for root in change_roots}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request = self.unified_release_program_continuity_command_center_acceptance_change_store.create_change_request(program_id, self._optional_json_body())
                self._send_json({"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}, status=HTTPStatus.CREATED)
                return
            if any(tail.startswith(root + "/cr/") and tail.endswith("/approve") for root in change_roots):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request_id = tail.split("/")[-2]
                approval = self.unified_release_program_continuity_command_center_acceptance_change_store.approve_change_request(program_id, request_id, self._optional_json_body())
                self._send_json({"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"approval_hash": approval.get("integrity_hash")}})
                return
            if any(tail.startswith(root + "/cr/") and tail.endswith("/reset-signoff") for root in change_roots):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request_id = tail.split("/")[-2]
                proof = self.unified_release_program_continuity_command_center_acceptance_change_store.reset_receiver_acceptance_signoff(program_id, request_id, self._optional_json_body())
                self._send_json({"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_proof_hash": proof.get("integrity_hash")}})
                return
            action_routes = {
                "/lifecycle": "lifecycle",
                "/export": "export",
                "/zip": "zip",
                "/verify": "verify",
                "/gate": "gate",
            }
            matched_action = next((action for suffix, action in action_routes.items() if tail in {root + suffix for root in change_roots}), None)
            if matched_action:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if matched_action == "lifecycle":
                    report = self.unified_release_program_continuity_command_center_acceptance_change_store.refresh_lifecycle_audit(program_id, payload)
                    self._send_json({"ok": report.get("status") == "passed", "lifecycle_report": report, "status": report.get("status"), "summary": report.get("summary", {})})
                    return
                if matched_action == "export":
                    manifest = self.unified_release_program_continuity_command_center_acceptance_change_store.export_archive(program_id, payload)
                    self._send_json({"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}})
                    return
                if matched_action == "zip":
                    result = self.unified_release_program_continuity_command_center_acceptance_change_store.build_archive_zip(program_id, payload)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if matched_action == "verify":
                    report = self.unified_release_program_continuity_command_center_acceptance_change_store.verify_archive_zip(program_id, payload)
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})})
                    return
                gate = self.unified_release_program_continuity_command_center_acceptance_change_store.gate(
                    program_id,
                    required=True,
                    archive_zip_path=payload.get("archive_zip") or payload.get("change_archive"),
                    verification_report_path=payload.get("verification_report") or payload.get("change_verification_report"),
                    **{key: value for key, value in payload.items() if key not in {"archive_zip", "change_archive", "verification_report", "change_verification_report"}},
                )
                self._send_json({"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})})
                return
            if tail == "/operations/change-requests":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request = self.unified_release_program_operations_store.create_change_request(program_id, self._optional_json_body())
                self._send_json({"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/operations/change-requests/") and tail.endswith("/approve"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                request_id = tail.split("/")[3]
                approval = self.unified_release_program_operations_store.approve_change_request(program_id, request_id, self._optional_json_body())
                self._send_json({"ok": True, "approval": approval, "summary": {"change_request_id": approval.get("change_request_id")}, "status": approval.get("status")})
                return
            if tail == "/operations/reset-signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                proof = self.unified_release_program_operations_store.reset_program_signoff(program_id, self._optional_json_body())
                self._send_json({"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")})
                return
            if tail == "/operations/runbooks":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook = self.unified_release_program_operations_store.create_runbook(program_id, self._optional_json_body())
                self._send_json({"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/operations/runbooks/") and tail.endswith("/run-safe"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook_id = tail.split("/")[3]
                result = self.unified_release_program_operations_store.run_safe(program_id, runbook_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") in {"completed", "completed_with_manual_actions"}, **result})
                return
            if tail == "/operations/continuous-review/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.unified_release_program_operations_store.refresh_continuous_review(program_id, self._optional_json_body())
                self._send_json({"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")})
                return
            if tail == "/operations/lifecycle/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_operations_store.refresh_lifecycle_audit(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "lifecycle": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/operations/archive/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.unified_release_program_operations_store.export_operations_archive(program_id, self._optional_json_body())
                self._send_json({"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"})
                return
            if tail == "/operations/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_release_program_operations_store.build_operations_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/operations/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_release_program_operations_store.verify_operations_archive_zip(program_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
            self._send_file(self.unified_release_program_store.zip_path(program_id), "application/zip", filename="musicforge-unified-release-program.zip")
            return
            self._send_error(HTTPStatus.NOT_FOUND, "Unified Release Program route not found.")
        except UnifiedReleaseProgramVaultNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramVaultStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramVaultError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramVaultOperationsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramVaultOperationsStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramVaultOperationsError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityDistributionNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityDistributionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityDistributionError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramHandoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramHandoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramHandoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramOperationsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramOperationsStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramOperationsError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_unified_command_centers_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/unified-command-centers":
                if method == "GET":
                    centers = self.unified_command_center_store.list_centers()
                    self._send_json({"ok": True, "centers": centers, "summary": {"center_count": len(centers)}})
                    return
                if method == "POST":
                    center = self.unified_command_center_store.create(self._optional_json_body())
                    self._send_json({"ok": True, "center": center, "summary": {"center_id": center.get("center_id")}, "status": center.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            prefix = "/api/unified-command-centers/"
            if not path.startswith(prefix):
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center route not found.")
                return
            parts = path.removeprefix(prefix).strip("/").split("/")
            center_id = parts[0]
            tail = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
            if tail == "/continuous-reviews":
                if method == "GET":
                    reviews = self.unified_command_center_continuous_review_store.list_reviews(center_id)
                    self._send_json({"ok": True, "reviews": reviews, "summary": {"review_count": len(reviews)}})
                    return
                if method == "POST":
                    plan = self.unified_command_center_continuous_review_store.create_plan(center_id, self._optional_json_body())
                    self._send_json({"ok": True, "plan": plan, "summary": {"review_id": plan.get("review_id")}, "status": plan.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/continuous-reviews/"):
                review_tail = tail.removeprefix("/continuous-reviews/")
                review_parts = review_tail.split("/")
                review_id = review_parts[0]
                review_action = "/" + "/".join(review_parts[1:]) if len(review_parts) > 1 else ""
                if review_action in {"", "/"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    review = self.unified_command_center_continuous_review_store.read_review(center_id, review_id)
                    self._send_json({"ok": True, "review": review, "summary": (review.get("drift_report") or {}).get("summary", {}), "status": (review.get("drift_report") or review.get("plan") or {}).get("status")})
                    return
                if review_action == "/run":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_continuous_review_store.run_review(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if review_action == "/export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_continuous_review_store.export_package(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if review_action == "/zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_continuous_review_store.build_zip(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if review_action == "/verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.unified_command_center_continuous_review_store.verify_package(center_id, review_id, payload)
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if review_action == "/download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_continuous_review_store.zip_path(center_id, review_id), "application/zip", filename="musicforge-unified-command-center-continuous-review.zip")
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Continuous Review route not found.")
                return
            if tail == "/drift-responses":
                if method == "GET":
                    responses = self.unified_command_center_drift_response_store.list_responses(center_id)
                    self._send_json({"ok": True, "responses": responses, "summary": {"response_count": len(responses)}})
                    return
                if method == "POST":
                    result = self.unified_command_center_drift_response_store.create_response(center_id, self._optional_json_body())
                    case = result.get("case", {})
                    self._send_json({"ok": True, **result, "summary": {"response_id": case.get("response_id")}, "status": case.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/drift-responses/"):
                response_tail = tail.removeprefix("/drift-responses/")
                response_parts = response_tail.split("/")
                response_id = response_parts[0]
                response_action = "/" + "/".join(response_parts[1:]) if len(response_parts) > 1 else ""
                if response_action in {"", "/"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response = self.unified_command_center_drift_response_store.read_response(center_id, response_id)
                    self._send_json({"ok": True, "response": response, "summary": (response.get("closeout") or {}).get("summary", {}), "status": (response.get("closeout") or response.get("case") or {}).get("status")})
                    return
                if response_action == "/run-safe":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.run_safe(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": int((result.get("summary") or {}).get("failed_count") or 0) == 0, "action_results": result, "summary": result.get("summary", {}), "status": "passed" if int((result.get("summary") or {}).get("failed_count") or 0) == 0 else "failed"})
                    return
                if response_action == "/bind-cr":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.bind_change_request(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": True, "change_request_bindings": result, "summary": result.get("summary", {}), "status": "passed"})
                    return
                if response_action == "/bind-recheck":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.bind_recheck(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", "recheck": result, "summary": result.get("summary", {}), "status": result.get("status")})
                    return
                if response_action == "/closeout":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.closeout(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "closed", "closeout": result, "summary": result.get("summary", {}), "status": result.get("status")})
                    return
                if response_action == "/export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.export_package(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "closed", **result})
                    return
                if response_action == "/zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_drift_response_store.build_zip(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "closed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if response_action == "/verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_drift_response_store.verify_package(center_id, response_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if response_action == "/download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_drift_response_store.zip_path(center_id, response_id), "application/zip", filename="musicforge-unified-command-center-drift-response.zip")
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Drift Response route not found.")
                return
            if tail == "/evidence-reviews":
                if method == "GET":
                    reviews = self.unified_command_center_evidence_review_store.list_reviews(center_id)
                    self._send_json({"ok": True, "reviews": reviews, "summary": {"review_count": len(reviews)}})
                    return
                if method == "POST":
                    docs = self.unified_command_center_evidence_review_store.create_review(center_id, self._optional_json_body())
                    source = docs.get("source", {})
                    self._send_json({"ok": True, "review": docs, "summary": {"review_id": source.get("review_id")}, "status": source.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/evidence-reviews/"):
                review_tail = tail.removeprefix("/evidence-reviews/")
                review_parts = review_tail.split("/")
                review_id = review_parts[0]
                review_action = "/" + "/".join(review_parts[1:]) if len(review_parts) > 1 else ""
                if review_action in {"", "/"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    review = self.unified_command_center_evidence_review_store.get_review(center_id, review_id)
                    replay = review.get("replay_result") or {}
                    self._send_json({"ok": True, "review": review, "summary": replay.get("summary", {}), "status": replay.get("status") or (review.get("source") or {}).get("status")})
                    return
                if review_action == "/refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    docs = self.unified_command_center_evidence_review_store.refresh_review(center_id, review_id, self._optional_json_body())
                    source = docs.get("source", {})
                    self._send_json({"ok": True, "review": docs, "summary": {"review_id": review_id}, "status": source.get("status")})
                    return
                if review_action == "/replay":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    replay = self.unified_command_center_evidence_review_store.run_replay(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": replay.get("status") == "passed", "replay_result": replay, "summary": replay.get("summary", {}), "status": replay.get("status")})
                    return
                if review_action == "/export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_evidence_review_store.export_review(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if review_action == "/zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_evidence_review_store.build_zip(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if review_action == "/verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_evidence_review_store.verify_zip(center_id, review_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if review_action == "/download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_evidence_review_store.zip_path(center_id, review_id), "application/zip", filename="musicforge-unified-command-center-evidence-review.zip")
                    return
                if review_action == "/responses":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    responses = self.unified_command_center_evidence_review_store.list_responses(center_id, review_id)
                    self._send_json({"ok": True, "responses": responses, "summary": {"response_count": len(responses)}})
                    return
                if review_action == "/responses/import":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response = self.unified_command_center_evidence_review_store.import_response(center_id, review_id, self._read_json_body())
                    self._send_json({"ok": response.get("status") == "current", "response": response, "summary": {"response_id": response.get("response_id")}, "status": response.get("status")}, status=HTTPStatus.CREATED)
                    return
                if review_action.startswith("/responses/") and review_action.endswith("/accepted-evidence"):
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response_id = review_action.split("/")[2]
                    result = self.unified_command_center_evidence_review_store.create_acceptance_evidence(center_id, review_id, response_id)
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence_id")}}, status=HTTPStatus.CREATED)
                    return
                if review_action.startswith("/accepted-evidence/"):
                    evidence_tail = review_action.removeprefix("/accepted-evidence/")
                    evidence_parts = evidence_tail.split("/")
                    evidence_id = evidence_parts[0]
                    evidence_action = "/" + "/".join(evidence_parts[1:]) if len(evidence_parts) > 1 else ""
                    if evidence_action == "/verify":
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        report = self.unified_command_center_evidence_review_store.verify_acceptance_evidence(center_id, review_id, evidence_id, self._optional_json_body())
                        self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                        return
                    if evidence_action == "/download":
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        self._send_file(self.unified_command_center_evidence_review_store.accepted_evidence_zip_path(center_id, review_id, evidence_id), "application/zip", filename="musicforge-unified-command-center-evidence-review-acceptance.zip")
                        return
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Evidence Review route not found.")
                return
            if tail == "/reviewer-decision-boards":
                if method == "GET":
                    boards = self.unified_command_center_reviewer_decision_board_store.list_boards(center_id)
                    self._send_json({"ok": True, "boards": boards, "summary": {"board_count": len(boards)}})
                    return
                if method == "POST":
                    docs = self.unified_command_center_reviewer_decision_board_store.create_board(center_id, self._optional_json_body())
                    decision = docs.get("decision_report", {})
                    self._send_json({"ok": decision.get("status") == "ready_for_signoff", "board": docs, "summary": decision.get("summary", {}), "status": decision.get("status")}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/reviewer-decision-boards/"):
                board_tail = tail.removeprefix("/reviewer-decision-boards/")
                board_parts = board_tail.split("/")
                board_id = board_parts[0]
                board_action = "/" + "/".join(board_parts[1:]) if len(board_parts) > 1 else ""
                if board_action in {"", "/"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    board = self.unified_command_center_reviewer_decision_board_store.get_board(center_id, board_id)
                    decision = board.get("decision_report") or {}
                    self._send_json({"ok": True, "board": board, "summary": decision.get("summary", {}), "status": decision.get("status")})
                    return
                if board_action == "/refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    docs = self.unified_command_center_reviewer_decision_board_store.refresh_board(center_id, board_id, self._optional_json_body())
                    decision = docs.get("decision_report", {})
                    self._send_json({"ok": decision.get("status") == "ready_for_signoff", "board": docs, "summary": decision.get("summary", {}), "status": decision.get("status")})
                    return
                if board_action == "/signoff":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    signoff = self.unified_command_center_reviewer_decision_board_store.signoff(center_id, board_id, self._optional_json_body())
                    self._send_json({"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")})
                    return
                if board_action == "/export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_reviewer_decision_board_store.export_archive(center_id, board_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "signed", **result})
                    return
                if board_action == "/zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.unified_command_center_reviewer_decision_board_store.build_zip(center_id, board_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                    return
                if board_action == "/verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.unified_command_center_reviewer_decision_board_store.verify_archive(center_id, board_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if board_action == "/download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.unified_command_center_reviewer_decision_board_store.zip_path(center_id, board_id), "application/zip", filename="musicforge-unified-command-center-reviewer-decision-board.zip")
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center Reviewer Decision Board route not found.")
                return
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                center = self.unified_command_center_store.read_center(center_id)
                report = self.unified_command_center_store.read_report(center_id) if self.unified_command_center_store.report_path(center_id).exists() else {}
                inventory = read_json(self.unified_command_center_store.inventory_path(center_id)) if self.unified_command_center_store.inventory_path(center_id).exists() else {}
                readiness = read_json(self.unified_command_center_store.readiness_path(center_id)) if self.unified_command_center_store.readiness_path(center_id).exists() else {}
                gap_plan = read_json(self.unified_command_center_store.gap_plan_path(center_id)) if self.unified_command_center_store.gap_plan_path(center_id).exists() else {}
                runbook = read_json(self.unified_command_center_store.runbook_path(center_id)) if self.unified_command_center_store.runbook_path(center_id).exists() else {}
                self._send_json({"ok": True, "center": center, "report": report, "inventory": inventory, "readiness": readiness, "gap_plan": gap_plan, "runbook": runbook, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.unified_command_center_store.refresh(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
                self._send_json({"ok": report.get("status") == "ready", "center_id": center_id, "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/runbook":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook = self.unified_command_center_store.create_runbook(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
                self._send_json({"ok": True, "center_id": center_id, "runbook": runbook, "summary": runbook.get("summary", {})})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_store.run_safe(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
                self._send_json({"ok": result.get("summary", {}).get("failed_count") == 0, "center_id": center_id, "runbook_result": result, "summary": result.get("summary", {})})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_store.export_package(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
                self._send_json({"ok": result.get("status") == "ready", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_store.build_zip(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
                self._send_json({"ok": result.get("status") == "ready", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.unified_command_center_store.verify_zip(center_id, evidence=self._unified_command_center_evidence_from_payload(payload), strict=bool(payload.get("strict", True)), require_ready=bool(payload.get("require_ready", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.unified_command_center_signoff_store.signoff(center_id, self._optional_json_body())
                self._send_json({"ok": True, "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")})
                return
            if tail == "/archive":
                if method == "GET":
                    manifest = read_json(self.unified_command_center_signoff_store.archive_manifest_path(center_id)) if self.unified_command_center_signoff_store.archive_manifest_path(center_id).exists() else {}
                    self._send_json({"ok": bool(manifest), "manifest": manifest, "summary": manifest.get("summary", {}) if manifest else {}})
                    return
                if method == "POST":
                    manifest = self.unified_command_center_signoff_store.export_archive(center_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/archive/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_signoff_store.build_archive_zip(center_id)
                self._send_json({"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/archive/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.unified_command_center_signoff_store.verify_archive(center_id, payload)
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/archive/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.unified_command_center_signoff_store.archive_zip_path(center_id), "application/zip", filename="unified-command-center-archive.zip")
                return
            if tail == "/handoff":
                if method == "GET":
                    manifest = read_json(self.unified_command_center_handoff_store.manifest_path(center_id)) if self.unified_command_center_handoff_store.manifest_path(center_id).exists() else {}
                    self._send_json({"ok": bool(manifest), "manifest": manifest, "summary": manifest.get("summary", {}) if manifest else {}})
                    return
                if method == "POST":
                    manifest = self.unified_command_center_handoff_store.export_handoff(center_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/handoff/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.unified_command_center_handoff_store.build_handoff_zip(center_id)
                self._send_json({"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/handoff/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.unified_command_center_handoff_store.verify_handoff(center_id, payload)
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/handoff/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.unified_command_center_handoff_store.zip_path(center_id), "application/zip", filename="musicforge-final-handoff-pack.zip")
                return
            if tail == "/change-requests":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                cr = self.unified_command_center_signoff_store.create_change_request(center_id, self._optional_json_body())
                self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}, status=HTTPStatus.CREATED)
                return
            if tail.startswith("/change-requests/") and tail.endswith("/approve"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                change_request_id = tail.split("/")[2]
                cr = self.unified_command_center_signoff_store.approve_change_request(center_id, change_request_id, self._optional_json_body())
                self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")})
                return
            if tail.startswith("/signoff/reset/"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                change_request_id = tail.split("/")[-1]
                result = self.unified_command_center_signoff_store.reset_signoff(center_id, change_request_id, self._optional_json_body())
                self._send_json({"ok": True, **result})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.unified_command_center_store.zip_path(center_id), "application/zip", filename="musicforge-unified-command-center.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center route not found.")
        except UnifiedCommandCenterNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (UnifiedCommandCenterSignoffNotFoundError,) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterContinuousReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterDriftResponseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterEvidenceReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterReviewerDecisionBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (UnifiedCommandCenterSignoffStateError, UnifiedCommandCenterHandoffStateError, UnifiedCommandCenterContinuousReviewStateError, UnifiedCommandCenterDriftResponseStateError, UnifiedCommandCenterEvidenceReviewStateError, UnifiedCommandCenterReviewerDecisionBoardStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedCommandCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (UnifiedCommandCenterSignoffError, UnifiedCommandCenterHandoffError, UnifiedCommandCenterContinuousReviewError, UnifiedCommandCenterDriftResponseError, UnifiedCommandCenterEvidenceReviewError, UnifiedCommandCenterReviewerDecisionBoardError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _unified_command_center_evidence_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = dict(payload or {})
        for key, zip_key, report_key in (
            ("release", "release_zip", "release_verification_report"),
            ("audio-command-center", "release_audio_command_center_zip", "release_audio_command_center_verification_report"),
            ("operations", "release_operations_zip", "release_operations_verification_report"),
            ("trust-operations-hub", "trust_operations_hub_zip", "trust_operations_hub_verification_report"),
            ("public-trust-center", "public_trust_center_zip", "public_trust_center_verification_report"),
            ("maintenance", "maintenance_backup_zip", "maintenance_backup_verification_report"),
        ):
            if payload.get(zip_key) or payload.get(report_key):
                evidence[key] = {"zip": payload.get(zip_key), "verification_report": payload.get(report_key)}
        if payload.get("distribution_zips") or payload.get("distribution_zip") or payload.get("distribution_verification_reports") or payload.get("distribution_verification_report"):
            evidence["distribution"] = {
                "zips": payload.get("distribution_zips") or ([payload.get("distribution_zip")] if payload.get("distribution_zip") else []),
                "verification_reports": payload.get("distribution_verification_reports") or ([payload.get("distribution_verification_report")] if payload.get("distribution_verification_report") else []),
            }
        if payload.get("submission_zips") or payload.get("submission_zip") or payload.get("submission_verification_reports") or payload.get("submission_verification_report"):
            evidence["submission"] = {
                "zips": payload.get("submission_zips") or ([payload.get("submission_zip")] if payload.get("submission_zip") else []),
                "verification_reports": payload.get("submission_verification_reports") or ([payload.get("submission_verification_report")] if payload.get("submission_verification_report") else []),
            }
        if payload.get("ga_readiness_report") or payload.get("ga_readiness_verification_report"):
            evidence["ga-readiness"] = {"report": payload.get("ga_readiness_report"), "verification_report": payload.get("ga_readiness_verification_report")}
        if payload.get("release_check_report"):
            evidence["release-check"] = {"report": payload.get("release_check_report")}
        if isinstance(payload.get("requirements"), dict):
            evidence["requirements"] = payload["requirements"]
        return evidence
