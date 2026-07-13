from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *

class TrustRoutes:
    @property
    def trust_operations_hub_store(self) -> TrustOperationsHubStore:
        return self.server.trust_operations_hub_store  # type: ignore[attr-defined]

    @property
    def trust_operations_incident_store(self) -> TrustOperationsIncidentStore:
        return self.server.trust_operations_incident_store  # type: ignore[attr-defined]

    @property
    def trust_operations_incident_knowledge_store(self) -> TrustOperationsIncidentKnowledgeStore:
        return self.server.trust_operations_incident_knowledge_store  # type: ignore[attr-defined]

    @property
    def trust_operations_control_store(self) -> TrustOperationsControlStore:
        return self.server.trust_operations_control_store  # type: ignore[attr-defined]

    @property
    def trust_operations_control_signoff_store(self) -> TrustOperationsControlSignoffStore:
        return self.server.trust_operations_control_signoff_store  # type: ignore[attr-defined]

    @property
    def trust_operations_assurance_store(self) -> TrustOperationsAssuranceStore:
        return self.server.trust_operations_assurance_store  # type: ignore[attr-defined]

    @property
    def trust_operations_assurance_watch_store(self) -> TrustOperationsAssuranceWatchStore:
        return self.server.trust_operations_assurance_watch_store  # type: ignore[attr-defined]

    @property
    def trust_operations_assurance_watch_signoff_store(self) -> TrustOperationsAssuranceWatchSignoffStore:
        return self.server.trust_operations_assurance_watch_signoff_store  # type: ignore[attr-defined]

    @property
    def trust_operations_final_readiness_store(self) -> TrustOperationsFinalReadinessStore:
        return self.server.trust_operations_final_readiness_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_audit_store(self) -> ReleasePortfolioAuditStore:
        return self.server.release_portfolio_audit_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_store(self) -> ReleasePortfolioGovernanceStore:
        return self.server.release_portfolio_governance_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_signoff_store(self) -> ReleasePortfolioGovernanceSignoffStore:
        return self.server.release_portfolio_governance_signoff_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_audit_store(self) -> ReleasePortfolioGovernanceAuditStore:
        return self.server.release_portfolio_governance_audit_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_reviewer_pack_store(self) -> ReleasePortfolioGovernanceReviewerPackStore:
        return self.server.release_portfolio_governance_reviewer_pack_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_final_board_store(self) -> ReleasePortfolioGovernanceFinalBoardStore:
        return self.server.release_portfolio_governance_final_board_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_evidence_vault_store(self) -> ReleasePortfolioGovernanceEvidenceVaultStore:
        return self.server.release_portfolio_governance_evidence_vault_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_store(self) -> ReleasePortfolioGovernanceAttestationStore:
        return self.server.release_portfolio_governance_attestation_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_registry_store(self) -> ReleasePortfolioGovernanceAttestationRegistryStore:
        return self.server.release_portfolio_governance_attestation_registry_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_portal_store(self) -> ReleasePortfolioGovernanceAttestationPortalStore:
        return self.server.release_portfolio_governance_attestation_portal_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_portal_review_store(self) -> ReleasePortfolioGovernanceAttestationPortalReviewStore:
        return self.server.release_portfolio_governance_attestation_portal_review_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_accepted_evidence_store(self) -> ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore:
        return self.server.release_portfolio_governance_attestation_accepted_evidence_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_transparency_store(self) -> ReleasePortfolioGovernanceAttestationTransparencyStore:
        return self.server.release_portfolio_governance_attestation_transparency_store  # type: ignore[attr-defined]

    @property
    def release_portfolio_governance_attestation_transparency_acknowledgement_store(self) -> ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore:
        return self.server.release_portfolio_governance_attestation_transparency_acknowledgement_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_store(self) -> PublicTrustCenterStore:
        return self.server.public_trust_center_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_anchor_registry_store(self) -> PublicTrustCenterAnchorRegistryStore:
        return self.server.public_trust_center_anchor_registry_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_anchor_transparency_store(self) -> PublicTrustCenterAnchorTransparencyStore:
        return self.server.public_trust_center_anchor_transparency_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_distribution_kit_store(self) -> PublicTrustCenterDistributionKitStore:
        return self.server.public_trust_center_distribution_kit_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_distribution_kit_acceptance_store(self) -> PublicTrustCenterDistributionKitAcceptanceStore:
        return self.server.public_trust_center_distribution_kit_acceptance_store  # type: ignore[attr-defined]

    @property
    def public_trust_center_acceptance_board_store(self) -> PublicTrustCenterAcceptanceBoardStore:
        return self.server.public_trust_center_acceptance_board_store  # type: ignore[attr-defined]

    def _handle_trust_operations(self, method: str, path: str) -> None:
        final_prefix = "/api/trust-operations/final-readiness"
        if path == final_prefix or path.startswith(final_prefix + "/"):
            self._handle_trust_operations_final_readiness(method, path.removeprefix(final_prefix))
            return
        watch_prefix = "/api/trust-operations/assurance-watch"
        if path == watch_prefix or path.startswith(watch_prefix + "/"):
            self._handle_trust_operations_assurance_watch(method, path.removeprefix(watch_prefix))
            return
        assurance_prefix = "/api/trust-operations/assurance"
        if path == assurance_prefix or path.startswith(assurance_prefix + "/"):
            self._handle_trust_operations_assurance(method, path.removeprefix(assurance_prefix))
            return
        signoff_prefix = "/api/trust-operations/control-signoff/"
        if path.startswith(signoff_prefix):
            hub_tail = path.removeprefix(signoff_prefix)
            hub_id, _sep, rest = hub_tail.partition("/")
            self._handle_trust_operations_control_signoff(method, unquote(hub_id), "/" + rest if rest else "")
            return
        prefix = "/api/trust-operations/hubs/"
        if not path.startswith(prefix):
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations route not found.")
            return
        tail = path.removeprefix(prefix)
        hub_id, sep, rest = tail.partition("/")
        if not hub_id or not sep:
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Hub route not found.")
            return
        rest = "/" + rest
        if rest == "/incidents.zip":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.trust_operations_incident_store.zip_path(unquote(hub_id)), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-incidents.zip")
            return
        if rest == "/knowledge.zip":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.trust_operations_incident_knowledge_store.zip_path(unquote(hub_id)), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-knowledge.zip")
            return
        if rest.startswith("/controls/") and rest.endswith(".zip"):
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in rest.split("/") if part]
            if len(parts) == 2:
                assessment_id = unquote(parts[1].removesuffix(".zip"))
                self._send_file(self.trust_operations_control_store.zip_path(unquote(hub_id), assessment_id), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-controls.zip")
                return
        if rest == "/controls" or rest.startswith("/controls/"):
            self._handle_trust_operations_controls(method, unquote(hub_id), rest.removeprefix("/controls"))
            return
        if rest == "/incidents" or rest.startswith("/incidents/"):
            self._handle_trust_operations_incidents(method, unquote(hub_id), rest.removeprefix("/incidents"))
            return
        if rest == "/knowledge" or rest.startswith("/knowledge/"):
            self._handle_trust_operations_knowledge(method, unquote(hub_id), rest.removeprefix("/knowledge"))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Hub route not found.")

    def _handle_trust_operations_assurance(self, method: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "runs": self.trust_operations_assurance_store.list_runs()})
                return
            if tail == "/runs":
                if method == "GET":
                    query = parse_qs(urlparse(self.path).query)
                    hub_id = query.get("hub_id", [None])[0]
                    self._send_json({"ok": True, "runs": self.trust_operations_assurance_store.list_runs(hub_id=hub_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    hub_id = str(payload.get("hub_id") or "hub")
                    policy_id = str(payload.get("policy_id") or "default")
                    result = self.trust_operations_assurance_store.refresh_run(hub_id, payload, policy_id=policy_id, now=_utc_now())
                    self._send_json({"ok": result.get("run", {}).get("status") == "passed", **result}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) >= 2 and parts[0] == "runs":
                run_id = unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, **self.trust_operations_assurance_store.summary(run_id)})
                    return
                action = parts[2]
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.trust_operations_assurance_store.archive_zip_path(run_id), "application/zip", filename=f"musicforge-{run_id}-trust-operations-assurance.zip")
                    return
                if action == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.trust_operations_assurance_store.export_archive(run_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "run_id": run_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.trust_operations_assurance_store.build_archive_zip(run_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "run_id": run_id, "zip": zip_info})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.trust_operations_assurance_store.verify_archive_zip(run_id, self._optional_json_body())
                    write_trust_operations_assurance_verification_report(report, self.trust_operations_assurance_store.verification_report_path(run_id))
                    self._send_json({"ok": report.get("status") != "failed", "run_id": run_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Assurance route not found.")
        except TrustOperationsAssuranceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsAssuranceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_assurance_watch(self, method: str, tail: str) -> None:
        try:
            if tail == "/signoffs" or tail.startswith("/signoffs/"):
                self._handle_trust_operations_assurance_watch_signoff(method, tail.removeprefix("/signoffs"))
                return
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "queues": self.trust_operations_assurance_watch_store.list_queues()})
                return
            if tail == "/schedule":
                if method == "GET":
                    self._send_json({"ok": True, "schedule": self.trust_operations_assurance_watch_store.read_schedule("default")})
                    return
                if method == "POST":
                    schedule = self.trust_operations_assurance_watch_store.write_schedule(self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "schedule": schedule}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/queues":
                if method == "GET":
                    query = parse_qs(urlparse(self.path).query)
                    schedule_id = query.get("schedule_id", [None])[0]
                    self._send_json({"ok": True, "queues": self.trust_operations_assurance_watch_store.list_queues(schedule_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    schedule_id = str(payload.get("schedule_id") or "default")
                    result = self.trust_operations_assurance_watch_store.refresh_queue(payload, schedule_id=schedule_id, now=_utc_now())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) >= 2 and parts[0] == "queues":
                queue_id = unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, **self.trust_operations_assurance_watch_store.summary(queue_id)})
                    return
                action = parts[2]
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.trust_operations_assurance_watch_store.watch_zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-trust-operations-assurance-watch.zip")
                    return
                if action == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.trust_operations_assurance_watch_store.export_watch(queue_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.trust_operations_assurance_watch_store.build_watch_zip(queue_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.trust_operations_assurance_watch_store.verify_watch_zip(queue_id, self._optional_json_body())
                    write_trust_operations_assurance_watch_verification_report(report, self.trust_operations_assurance_watch_store.verification_report_path(queue_id))
                    self._send_json({"ok": report.get("status") != "failed", "queue_id": queue_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Assurance Watch route not found.")
        except TrustOperationsAssuranceWatchNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsAssuranceWatchStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_assurance_watch_signoff(self, method: str, tail: str) -> None:
        try:
            parts = [part for part in tail.split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Assurance Watch Signoff route not found.")
                return
            queue_id = unquote(parts[0])
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.trust_operations_assurance_watch_signoff_store.summary(queue_id)})
                return
            action = parts[1]
            if action == "download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.trust_operations_assurance_watch_signoff_store.archive_zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-trust-operations-assurance-watch-signoff.zip")
                return
            if action == "closeout":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.trust_operations_assurance_watch_signoff_store.refresh_closeout(queue_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": closeout.get("status") == "passed", "queue_id": queue_id, "closeout": closeout, "summary": closeout.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if action == "sign":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.trust_operations_assurance_watch_signoff_store.sign(queue_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff}, status=HTTPStatus.CREATED)
                return
            if action == "change-requests":
                if len(parts) == 2:
                    if method == "GET":
                        self._send_json({"ok": True, "queue_id": queue_id, "change_requests": self.trust_operations_assurance_watch_signoff_store.list_change_requests(queue_id)})
                        return
                    if method == "POST":
                        change = self.trust_operations_assurance_watch_signoff_store.create_change_request(queue_id, self._optional_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "queue_id": queue_id, "change_request": change}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 4 and parts[3] == "approve":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    change = self.trust_operations_assurance_watch_signoff_store.approve_change_request(queue_id, unquote(parts[2]), self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "change_request": change})
                    return
            if action == "reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                change_request_id = str(payload.get("change_request_id") or "")
                if not change_request_id:
                    raise ValueError("change_request_id is required.")
                reset = self.trust_operations_assurance_watch_signoff_store.reset_signoff(queue_id, change_request_id, now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "reset": reset})
                return
            if action == "export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_assurance_watch_signoff_store.export_archive(queue_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                return
            if action == "zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_assurance_watch_signoff_store.build_archive_zip(queue_id, now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info})
                return
            if action == "verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_assurance_watch_signoff_store.verify_archive_zip(queue_id, self._optional_json_body())
                write_trust_operations_assurance_watch_signoff_verification_report(report, self.trust_operations_assurance_watch_signoff_store.verification_report_path(queue_id))
                self._send_json({"ok": report.get("status") != "failed", "queue_id": queue_id, "verification": report, "summary": report.get("summary", {})})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Assurance Watch Signoff route not found.")
        except TrustOperationsAssuranceWatchSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsAssuranceWatchSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_final_readiness(self, method: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.trust_operations_final_readiness_store.summary()})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.trust_operations_final_readiness_store.handoff_zip_path(), "application/zip", filename="musicforge-trust-operations-final-handoff.zip")
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.trust_operations_final_readiness_store.refresh_report(self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": result.get("report", {}).get("status") == "ready", **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/certificate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                certificate = self.trust_operations_final_readiness_store.create_certificate(self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "certificate": certificate}, status=HTTPStatus.CREATED)
                return
            if tail == "/sign":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.trust_operations_final_readiness_store.sign(self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "signoff": signoff}, status=HTTPStatus.CREATED)
                return
            if tail == "/change-requests":
                if method == "GET":
                    self._send_json({"ok": True, "change_requests": self.trust_operations_final_readiness_store.list_change_requests()})
                    return
                if method == "POST":
                    change = self.trust_operations_final_readiness_store.create_change_request(self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "change_request": change}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) == 3 and parts[0] == "change-requests" and parts[2] == "approve":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                change = self.trust_operations_final_readiness_store.approve_change_request(unquote(parts[1]), self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "change_request": change})
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                change_request_id = str(payload.get("change_request_id") or "")
                if not change_request_id:
                    raise ValueError("change_request_id is required.")
                reset = self.trust_operations_final_readiness_store.reset_signoff(change_request_id, now=_utc_now())
                self._send_json({"ok": True, "reset": reset})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_final_readiness_store.export_handoff(self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "manifest": manifest}, status=HTTPStatus.CREATED)
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_final_readiness_store.build_handoff_zip(now=_utc_now())
                self._send_json({"ok": True, "zip": zip_info})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_final_readiness_store.verify_handoff_zip(self._optional_json_body())
                write_trust_operations_final_handoff_verification_report(report, self.trust_operations_final_readiness_store.verification_report_path())
                self._send_json({"ok": report.get("status") != "failed", "verification": report, "summary": report.get("summary", {})})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Final Readiness route not found.")
        except TrustOperationsFinalReadinessNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsFinalReadinessStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_knowledge(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                base = {}
                try:
                    base = self.trust_operations_incident_knowledge_store.read_base(hub_id)
                except TrustOperationsKnowledgeNotFoundError:
                    pass
                self._send_json(
                    {
                        "ok": True,
                        "hub_id": hub_id,
                        "knowledge_base": base,
                        "entries": self.trust_operations_incident_knowledge_store.list_entries(hub_id),
                        "guards": self.trust_operations_incident_knowledge_store.list_guards(hub_id),
                    }
                )
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.trust_operations_incident_knowledge_store.refresh(hub_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/recurrence/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_incident_knowledge_store.refresh_recurrence(hub_id, now=_utc_now())
                self._send_json({"ok": report.get("status") == "passed", "hub_id": hub_id, "recurrence": report})
                return
            if tail == "/guards/run-all":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.trust_operations_incident_knowledge_store.run_all_guards(hub_id, now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_incident_knowledge_store.export_knowledge(hub_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_incident_knowledge_store.build_zip(hub_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_incident_knowledge_store.verify_zip(hub_id, self._optional_json_body())
                write_trust_operations_incident_knowledge_verification_report(report, self.trust_operations_incident_knowledge_store.verification_report_path(hub_id))
                self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) >= 2 and parts[0] == "entries":
                entry_id = unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    entry = self.trust_operations_incident_knowledge_store.read_entry(hub_id, entry_id)
                    self._send_json({"ok": True, "hub_id": hub_id, "entry": entry})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                action = parts[2]
                if action == "hide":
                    entry = self.trust_operations_incident_knowledge_store.hide_entry(hub_id, entry_id, now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "entry": entry})
                    return
                if action == "unhide":
                    entry = self.trust_operations_incident_knowledge_store.unhide_entry(hub_id, entry_id, now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "entry": entry})
                    return
                if action == "guards":
                    guard = self.trust_operations_incident_knowledge_store.create_guard(hub_id, entry_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "guard": guard}, status=HTTPStatus.CREATED)
                    return
            if len(parts) >= 2 and parts[0] == "guards":
                guard_id = unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    guard = self.trust_operations_incident_knowledge_store.read_guard(hub_id, guard_id)
                    self._send_json({"ok": True, "hub_id": hub_id, "guard": guard})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if parts[2] == "run":
                    run = self.trust_operations_incident_knowledge_store.run_guard(hub_id, guard_id, now=_utc_now())
                    self._send_json({"ok": run.get("status") == "passed", "hub_id": hub_id, "guard_run": run})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Knowledge route not found.")
        except TrustOperationsKnowledgeNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsKnowledgeStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_control_signoff(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.trust_operations_control_signoff_store.summary(hub_id)})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.trust_operations_control_signoff_store.archive_zip_path(hub_id), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-control-signoff.zip")
                return
            if tail == "/sign":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                assessment_id = str(payload.get("assessment_id") or "")
                if not assessment_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "assessment_id is required.")
                    return
                signoff = self.trust_operations_control_signoff_store.sign(hub_id, assessment_id, payload, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "signoff": signoff}, status=HTTPStatus.CREATED)
                return
            if tail == "/exceptions":
                if method == "GET":
                    self._send_json({"ok": True, "hub_id": hub_id, "exceptions": self.trust_operations_control_signoff_store.list_exceptions(hub_id)})
                    return
                if method == "POST":
                    exception = self.trust_operations_control_signoff_store.request_exception(hub_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "exception": exception}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/change-requests":
                if method == "GET":
                    self._send_json({"ok": True, "hub_id": hub_id, "change_requests": self.trust_operations_control_signoff_store.list_change_requests(hub_id)})
                    return
                if method == "POST":
                    cr = self.trust_operations_control_signoff_store.create_change_request(hub_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "change_request": cr}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                cr_id = str(payload.get("change_request_id") or "")
                if not cr_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "change_request_id is required.")
                    return
                result = self.trust_operations_control_signoff_store.reset_signoff(hub_id, cr_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, **result})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_control_signoff_store.export_archive(hub_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_control_signoff_store.build_archive_zip(hub_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_control_signoff_store.verify_archive_zip(hub_id, self._optional_json_body())
                write_trust_operations_control_signoff_verification_report(report, self.trust_operations_control_signoff_store.verification_report_path(hub_id))
                self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) == 3 and parts[0] == "exceptions" and parts[2] in {"approve", "reject"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if parts[2] == "approve":
                    exception = self.trust_operations_control_signoff_store.approve_exception(hub_id, unquote(parts[1]), self._optional_json_body(), now=_utc_now())
                else:
                    exception = self.trust_operations_control_signoff_store.reject_exception(hub_id, unquote(parts[1]), self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "exception": exception})
                return
            if len(parts) == 3 and parts[0] == "change-requests" and parts[2] == "approve":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                cr = self.trust_operations_control_signoff_store.approve_change_request(hub_id, unquote(parts[1]), self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "change_request": cr})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Control Signoff route not found.")
        except TrustOperationsControlSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsControlSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_controls(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                catalog = {}
                try:
                    catalog = self.trust_operations_control_store.read_catalog(hub_id)
                except TrustOperationsControlNotFoundError:
                    pass
                self._send_json({"ok": True, "hub_id": hub_id, "catalog": catalog, "policies": self.trust_operations_control_store.list_policies(hub_id)})
                return
            if tail == "/catalog/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                catalog = self.trust_operations_control_store.refresh_catalog(hub_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "catalog": catalog}, status=HTTPStatus.CREATED)
                return
            if tail == "/policies":
                if method == "GET":
                    self._send_json({"ok": True, "hub_id": hub_id, "policies": self.trust_operations_control_store.list_policies(hub_id)})
                    return
                if method == "POST":
                    policy = self.trust_operations_control_store.create_policy_bundle(hub_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "policy": policy}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/assess":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                policy_id = str(payload.get("policy_id") or "")
                if not policy_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "policy_id is required.")
                    return
                result = self.trust_operations_control_store.assess_policy(hub_id, policy_id, payload, now=_utc_now())
                self._send_json({"ok": result.get("assessment", {}).get("status") == "passed", "hub_id": hub_id, **result}, status=HTTPStatus.CREATED)
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) == 2 and parts[0] == "policies":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                policy = self.trust_operations_control_store.read_policy(hub_id, unquote(parts[1]))
                self._send_json({"ok": True, "hub_id": hub_id, "policy": policy})
                return
            if len(parts) >= 2 and parts[0] == "assessments":
                assessment_id = unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    assessment = self.trust_operations_control_store.read_assessment(hub_id, assessment_id)
                    self._send_json({"ok": True, "hub_id": hub_id, "assessment": assessment})
                    return
                action = parts[2]
                if action == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.trust_operations_control_store.export_controls(hub_id, assessment_id, now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.trust_operations_control_store.build_zip(hub_id, assessment_id, now=_utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.trust_operations_control_store.verify_zip(hub_id, assessment_id, self._optional_json_body())
                    write_trust_operations_control_verification_report(report, self.trust_operations_control_store.verification_report_path(hub_id, assessment_id))
                    self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Control route not found.")
        except TrustOperationsControlNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsControlStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_incidents(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                board = {}
                try:
                    board = self.trust_operations_incident_store.read_board(hub_id)
                except TrustOperationsIncidentNotFoundError:
                    pass
                self._send_json({"ok": True, "hub_id": hub_id, "incident_board": board, "incidents": self.trust_operations_incident_store.list_incidents(hub_id)})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.trust_operations_incident_store.refresh_board(hub_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_incident_store.export_board(hub_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_incident_store.build_zip(hub_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_incident_store.verify_zip(hub_id, self._optional_json_body())
                write_trust_operations_hub_incident_verification_report(report, self.trust_operations_incident_store.verification_report_path(hub_id))
                self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                return
            parts = [part for part in tail.split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Incident route not found.")
                return
            incident_id = unquote(parts[0])
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                incident = self.trust_operations_incident_store.read_incident(hub_id, incident_id)
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            action = parts[1]
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            if action == "triage":
                incident = self.trust_operations_incident_store.triage_incident(hub_id, incident_id, payload, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            if action == "plan":
                plan = self.trust_operations_incident_store.create_plan(hub_id, incident_id, payload, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "plan": plan}, status=HTTPStatus.CREATED)
                return
            if action == "evidence":
                evidence = self.trust_operations_incident_store.add_evidence(hub_id, incident_id, payload, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "evidence": evidence}, status=HTTPStatus.CREATED)
                return
            if action == "verify-fix":
                result = self.trust_operations_incident_store.verify_fix(hub_id, incident_id, now=_utc_now())
                self._send_json({"ok": result.get("status") == "passed", "hub_id": hub_id, "result": result})
                return
            if action == "close":
                closeout = self.trust_operations_incident_store.close_incident(hub_id, incident_id, payload, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "closeout": closeout})
                return
            if action == "archive":
                incident = self.trust_operations_incident_store.archive_incident(hub_id, incident_id, now=_utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Trust Operations Incident route not found.")
        except TrustOperationsIncidentNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except TrustOperationsIncidentStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_portfolio_audits(self, method: str, path: str) -> None:
        prefix = "/api/release-portfolio-audits"
        tail = path[len(prefix):]
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    query = parse_qs(urlparse(self.path).query)
                    include_archived = str(query.get("include_archived", [""])[0]).lower() in {"1", "true", "yes"}
                    portfolios = self.release_portfolio_audit_store.list_portfolios(include_archived=include_archived)
                    self._send_json({"ok": True, "portfolios": portfolios, "summary": {"count": len(portfolios)}})
                    return
                if method == "POST":
                    portfolio = self.release_portfolio_audit_store.create(self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio": portfolio, "summary": {"portfolio_id": portfolio.get("portfolio_id"), "status": portfolio.get("status")}}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Audit route not found.")
                return
            portfolio_id = parts[0]
            action = parts[1] if len(parts) > 1 else ""
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                portfolio = self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                report = self.release_portfolio_audit_store.read_report(portfolio_id, default={})
                stale = self.release_portfolio_audit_store.report_is_stale(portfolio_id, report) if report else False
                summary = portfolio_audit_summary(report) if report else {"status": "missing"}
                summary["stale"] = stale
                self._send_json({"ok": True, "portfolio": portfolio, "report": report, "summary": summary, "stale": stale})
                return
            if action == "refresh" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_portfolio_audit_store.refresh(portfolio_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_audit_summary(report)})
                return
            if action == "report" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_portfolio_audit_store.read_report(portfolio_id, default={})
                stale = self.release_portfolio_audit_store.report_is_stale(portfolio_id, report) if report else False
                summary = portfolio_audit_summary(report) if report else {"status": "missing"}
                summary["stale"] = stale
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": summary, "stale": stale})
                return
            if action == "trends" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                trend = self.release_portfolio_audit_store.read_trend_report(portfolio_id, default={})
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "trend_report": trend, "summary": {"status": trend.get("status") or "missing", "finding_count": len(trend.get("trend_findings", []) if isinstance(trend.get("trend_findings"), list) else [])}})
                return
            if action == "risks" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                risks = self.release_portfolio_audit_store.read_risk_register(portfolio_id, default={})
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "risk_register": risks, "summary": {"risk_count": len(risks.get("risks", []) if isinstance(risks.get("risks"), list) else [])}})
                return
            if action == "governance-audit.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_audit_store.zip_path(portfolio_id),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-audit.zip",
                )
                return
            if action == "governance-reviewer-pack.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_reviewer_pack_store.zip_path(portfolio_id),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-reviewer-pack.zip",
                )
                return
            if action == "governance-final-board.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_final_board_store.archive_zip_path(portfolio_id),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-final-board-archive.zip",
                )
                return
            if action == "governance-evidence-vault.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_evidence_vault_store.zip_path(portfolio_id),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-evidence-vault.zip",
                )
                return
            if action == "governance-attestation.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_store.zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-public-attestation.zip",
                )
                return
            if action == "governance-attestation-registry.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_registry_store.zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-attestation-registry.zip",
                )
                return
            if action == "governance-attestation-portal.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_portal_store.zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-attestation-portal.zip",
                )
                return
            if action == "governance-attestation-portal-review-pack.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_portal_review_store.pack_zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-attestation-portal-review-pack.zip",
                )
                return
            if action == "governance-attestation-accepted-evidence.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_accepted_evidence_store.zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-attestation-accepted-evidence.zip",
                )
                return
            if action == "governance-attestation-transparency.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
                self._send_file(
                    self.release_portfolio_governance_attestation_transparency_store.zip_path(portfolio_id, profile),
                    "application/zip",
                    filename=f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency.zip",
                )
                return
            if action in {"governance-attestation-transparency-acknowledgement-pack.zip", "governance-attestation-transparency-acknowledgement-evidence.zip"} and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
                if action.endswith("pack.zip"):
                    path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_zip_path(portfolio_id, profile)
                    filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-pack.zip"
                else:
                    path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_zip_path(portfolio_id, profile)
                    filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-evidence.zip"
                self._send_file(path, "application/zip", filename=filename)
                return
            if action == "governance-audit":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_audit_store.read_report(portfolio_id, default={})
                    stale = self.release_portfolio_governance_audit_store.report_is_stale(portfolio_id, report) if report else False
                    summary = portfolio_governance_audit_summary(report) if report else {"status": "missing"}
                    summary["stale"] = stale
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": summary, "stale": stale})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_audit_store.refresh(portfolio_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_audit_summary(report)})
                    return
                if subaction == "ledger" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    query = parse_qs(urlparse(self.path).query)
                    limit_raw = str(query.get("limit", [""])[0] or "").strip()
                    limit = max(0, int(limit_raw)) if limit_raw.isdigit() else 0
                    entries = self.release_portfolio_governance_audit_store.read_ledger(portfolio_id)
                    if limit:
                        entries = entries[-limit:]
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "entries": entries, "summary": {"entry_count": len(entries)}})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_audit_store.export_audit(portfolio_id, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_audit_store.build_zip(portfolio_id, now=_utc_now())
                    manifest = self.release_portfolio_governance_audit_store.read_export_manifest(portfolio_id)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = verify_release_portfolio_governance_audit_package(
                        self.release_portfolio_governance_audit_store.zip_path(portfolio_id),
                        strict=bool(payload.get("strict", False)),
                        require_signed=bool(payload.get("require_signed", False)),
                        require_archives=bool(payload.get("require_archives", False)),
                        require_no_force=bool(payload.get("require_no_force", False)),
                        require_reset_cr_causality=bool(payload.get("require_reset_cr_causality", False)),
                    )
                    write_release_portfolio_governance_audit_verification_report(report, self.release_portfolio_governance_audit_store.verification_report_path(portfolio_id))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": release_portfolio_governance_audit_verification_summary(report)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Audit route not found.")
                return
            if action == "governance-reviewer-pack":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_reviewer_pack_store.read_report(portfolio_id, default={})
                    stale = self.release_portfolio_governance_reviewer_pack_store.report_is_stale(portfolio_id, report) if report else False
                    summary = portfolio_governance_reviewer_pack_summary(report) if report else {"status": "missing"}
                    summary["stale"] = stale
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "report": report,
                            "retrospective": self.release_portfolio_governance_reviewer_pack_store.read_retrospective(portfolio_id, default={}),
                            "evidence_index": self.release_portfolio_governance_reviewer_pack_store.read_evidence_index(portfolio_id, default={}),
                            "timeline": self.release_portfolio_governance_reviewer_pack_store.read_timeline(portfolio_id, default={}),
                            "summary": summary,
                            "stale": stale,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_reviewer_pack_store.refresh(portfolio_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_reviewer_pack_summary(report)})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_reviewer_pack_store.export_pack(portfolio_id, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_reviewer_pack_store.build_zip(portfolio_id, now=_utc_now())
                    manifest = self.release_portfolio_governance_reviewer_pack_store.read_export_manifest(portfolio_id)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = verify_release_portfolio_governance_reviewer_pack(
                        self.release_portfolio_governance_reviewer_pack_store.zip_path(portfolio_id),
                        strict=bool(payload.get("strict", False)),
                        require_audit=bool(payload.get("require_audit", False)),
                        require_signed=bool(payload.get("require_signed", False)),
                        require_archives=bool(payload.get("require_archives", False)),
                        require_no_force=bool(payload.get("require_no_force", False)),
                        require_reset_cr_causality=bool(payload.get("require_reset_cr_causality", False)),
                    )
                    write_release_portfolio_governance_reviewer_pack_verification_report(report, self.release_portfolio_governance_reviewer_pack_store.verification_report_path(portfolio_id))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": release_portfolio_governance_reviewer_pack_verification_summary(report)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Reviewer Pack route not found.")
                return
            if action == "governance-final-board":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_final_board_store.read_report(portfolio_id, default={})
                    signoff = self.release_portfolio_governance_final_board_store.read_signoff(portfolio_id, default={})
                    stale = self.release_portfolio_governance_final_board_store.report_is_stale(portfolio_id, report) if report else False
                    summary = portfolio_governance_final_board_summary(report) if report else {"status": "missing"}
                    summary["stale"] = stale
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "report": report,
                            "signoff": signoff,
                            "signoff_summary": self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff) if signoff else portfolio_governance_final_board_signoff_summary(signoff),
                            "reviewer_responses": self.release_portfolio_governance_final_board_store.list_reviewer_responses(portfolio_id),
                            "change_requests": self.release_portfolio_governance_final_board_store.list_change_requests(portfolio_id),
                            "verification": read_json(self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id)) if self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id).exists() else {},
                            "summary": summary,
                            "stale": stale,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_final_board_store.refresh_report(portfolio_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_final_board_summary(report)})
                    return
                if subaction == "reviewer-responses" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    responses = self.release_portfolio_governance_final_board_store.list_reviewer_responses(portfolio_id)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "reviewer_responses": responses, "summary": {"count": len(responses)}})
                    return
                if subaction == "reviewer-responses" and len(parts) == 4 and parts[3] == "import":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response = self.release_portfolio_governance_final_board_store.import_reviewer_response(portfolio_id, self._read_json_body(), now=_utc_now())
                    report = self.release_portfolio_governance_final_board_store.refresh_report(portfolio_id, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "response": response, "report": report, "summary": portfolio_governance_final_board_summary(report)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "signoff" and len(parts) == 3:
                    if method == "GET":
                        signoff = self.release_portfolio_governance_final_board_store.read_signoff(portfolio_id, default={})
                        report = self.release_portfolio_governance_final_board_store.read_report(portfolio_id, default={})
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": signoff, "summary": self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff), "report_summary": portfolio_governance_final_board_summary(report)})
                        return
                    if method == "POST":
                        signoff = self.release_portfolio_governance_final_board_store.signoff(portfolio_id, self._optional_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": signoff, "summary": self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff)})
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if subaction == "signoff" and len(parts) == 4 and parts[3] == "reset":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    reset = self.release_portfolio_governance_final_board_store.reset_signoff(portfolio_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": reset, "summary": self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=reset)})
                    return
                if subaction == "change-requests" and len(parts) == 3:
                    if method == "GET":
                        items = self.release_portfolio_governance_final_board_store.list_change_requests(portfolio_id)
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_requests": items, "summary": {"count": len(items)}})
                        return
                    if method == "POST":
                        item = self.release_portfolio_governance_final_board_store.create_change_request(portfolio_id, self._read_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_request": item}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if subaction == "change-requests" and len(parts) == 5 and parts[4] in {"approve", "reject"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    item = self.release_portfolio_governance_final_board_store.update_change_request_status(portfolio_id, parts[3], parts[4], self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_request": item})
                    return
                if subaction == "archive" and len(parts) == 4 and parts[3] == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_final_board_store.export_archive(portfolio_id, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("final_board_signoff", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "archive" and len(parts) == 4 and parts[3] == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_final_board_store.build_archive_zip(portfolio_id, now=_utc_now())
                    manifest = self.release_portfolio_governance_final_board_store.read_export_manifest(portfolio_id)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("final_board_signoff", {})})
                    return
                if subaction == "archive" and len(parts) == 4 and parts[3] == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = verify_release_portfolio_governance_final_board_package(
                        self.release_portfolio_governance_final_board_store.archive_zip_path(portfolio_id),
                        strict=bool(payload.get("strict", False)),
                        require_signed=bool(payload.get("require_signed", False)),
                        require_reviewer_pack=bool(payload.get("require_reviewer_pack", False)),
                        require_audit=bool(payload.get("require_audit", False)),
                        require_archives=bool(payload.get("require_archives", False)),
                        require_reviewer_response=bool(payload.get("require_reviewer_response", False)),
                        require_no_force=bool(payload.get("require_no_force", False)),
                        require_reset_cr_causality=bool(payload.get("require_reset_cr_causality", False)),
                    )
                    write_release_portfolio_governance_final_board_verification_report(report, self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": release_portfolio_governance_final_board_verification_summary(report)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Final Board route not found.")
                return
            if action == "governance-evidence-vault":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_evidence_vault_store.read_report(portfolio_id, default={})
                    stale = self.release_portfolio_governance_evidence_vault_store.report_is_stale(portfolio_id, report) if report else False
                    summary = portfolio_governance_evidence_vault_summary(report) if report else {"status": "missing"}
                    summary["stale"] = stale
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "report": report,
                            "package_index": self.release_portfolio_governance_evidence_vault_store.read_package_index(portfolio_id, default={}),
                            "verification_index": self.release_portfolio_governance_evidence_vault_store.read_verification_index(portfolio_id, default={}),
                            "chain_of_custody": self.release_portfolio_governance_evidence_vault_store.read_chain_of_custody(portfolio_id, default={}),
                            "verification": read_json(self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id)) if self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id).exists() else {},
                            "summary": summary,
                            "stale": stale,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_evidence_vault_store.refresh_report(portfolio_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_evidence_vault_summary(report)})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_evidence_vault_store.export_vault(portfolio_id, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_evidence_vault_store.build_zip(portfolio_id, now=_utc_now())
                    manifest = self.release_portfolio_governance_evidence_vault_store.read_export_manifest(portfolio_id)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = verify_release_portfolio_governance_evidence_vault_package(
                        self.release_portfolio_governance_evidence_vault_store.zip_path(portfolio_id),
                        strict=bool(payload.get("strict", False)),
                        deep=bool(payload.get("deep", False)),
                        require_final_board=bool(payload.get("require_final_board", False)),
                        require_reviewer_pack=bool(payload.get("require_reviewer_pack", False)),
                        require_audit=bool(payload.get("require_audit", False)),
                        require_archives=bool(payload.get("require_archives", False)),
                        require_queue_packages=bool(payload.get("require_queue_packages", False)),
                    )
                    write_release_portfolio_governance_evidence_vault_verification_report(report, self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": portfolio_governance_evidence_vault_summary(self.release_portfolio_governance_evidence_vault_store.read_report(portfolio_id, default={}))})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Evidence Vault route not found.")
                return
            if action == "governance-attestation":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_attestation_store.read_report(portfolio_id, profile=query_profile, default={})
                    stale = self.release_portfolio_governance_attestation_store.report_is_stale(portfolio_id, report, profile=query_profile) if report else False
                    summary = portfolio_governance_attestation_summary(report) if report else {"status": "missing", "profile": query_profile}
                    summary["stale"] = stale
                    certificate = self.release_portfolio_governance_attestation_store.read_certificate(portfolio_id, profile=query_profile, default={})
                    verification_path = self.release_portfolio_governance_attestation_store.verification_report_path(portfolio_id, query_profile)
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "profile": query_profile,
                            "report": report,
                            "certificate": certificate,
                            "verification": read_json(verification_path) if verification_path.exists() else {},
                            "summary": summary,
                            "stale": stale,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.release_portfolio_governance_attestation_store.refresh_report(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_attestation_summary(report)})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_attestation_store.export_attestation(portfolio_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    zip_info = self.release_portfolio_governance_attestation_store.build_zip(portfolio_id, payload, now=_utc_now())
                    manifest = self.release_portfolio_governance_attestation_store.read_export_manifest(portfolio_id, profile=str(payload.get("profile") or "public_summary"))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = str(payload.get("profile") or "public_summary")
                    report = verify_release_portfolio_governance_attestation(
                        self.release_portfolio_governance_attestation_store.zip_path(portfolio_id, profile),
                        strict=bool(payload.get("strict", False)),
                        require_vault=bool(payload.get("require_vault", False)),
                        require_final_board=bool(payload.get("require_final_board", False)),
                    )
                    write_release_portfolio_governance_attestation_verification_report(report, self.release_portfolio_governance_attestation_store.verification_report_path(portfolio_id, profile))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": portfolio_governance_attestation_summary(self.release_portfolio_governance_attestation_store.read_report(portfolio_id, profile=profile, default={}))})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Public Attestation route not found.")
                return
            if action == "governance-attestation-registry":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    registry = self.release_portfolio_governance_attestation_registry_store.read_registry(portfolio_id, profile=query_profile, default={})
                    report = self.release_portfolio_governance_attestation_registry_store.read_report(portfolio_id, profile=query_profile, default={})
                    verification_path = self.release_portfolio_governance_attestation_registry_store.verification_report_path(portfolio_id, query_profile)
                    summary = portfolio_governance_attestation_registry_summary(registry) if registry else {"status": "missing", "profile": query_profile}
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "profile": query_profile,
                            "registry": registry,
                            "report": report,
                            "verification": read_json(verification_path) if verification_path.exists() else {},
                            "summary": summary,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "register-current" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    result = self.release_portfolio_governance_attestation_registry_store.register_current_attestation(portfolio_id, payload, now=_utc_now())
                    status = HTTPStatus.OK if result.get("existing") else HTTPStatus.CREATED
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "entry": result.get("entry"), "registry": result.get("registry"), "summary": portfolio_governance_attestation_registry_summary(result.get("registry", {})), "existing": bool(result.get("existing"))}, status=status)
                    return
                if subaction == "entries" and len(parts) == 5 and parts[4] == "publish":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    result = self.release_portfolio_governance_attestation_registry_store.publish_entry(portfolio_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "entry": result.get("entry"), "registry": result.get("registry"), "summary": portfolio_governance_attestation_registry_summary(result.get("registry", {}))})
                    return
                if subaction == "entries" and len(parts) == 5 and parts[4] == "revoke":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    result = self.release_portfolio_governance_attestation_registry_store.revoke_entry(portfolio_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "entry": result.get("entry"), "registry": result.get("registry"), "summary": portfolio_governance_attestation_registry_summary(result.get("registry", {}))})
                    return
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    report = self.release_portfolio_governance_attestation_registry_store.refresh_report(portfolio_id, payload, now=_utc_now())
                    registry = self.release_portfolio_governance_attestation_registry_store.read_registry(portfolio_id, profile=str(payload.get("profile") or "public_summary"), default={})
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_attestation_registry_summary(registry)})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    manifest = self.release_portfolio_governance_attestation_registry_store.export_registry(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    zip_info = self.release_portfolio_governance_attestation_registry_store.build_zip(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = str(payload.get("profile") or query_profile)
                    report = verify_release_portfolio_governance_attestation_registry(
                        self.release_portfolio_governance_attestation_registry_store.zip_path(portfolio_id, profile),
                        strict=bool(payload.get("strict", False)),
                        require_current=bool(payload.get("require_current", False)),
                        require_published=bool(payload.get("require_published", False)),
                        require_no_revoked_current=bool(payload.get("require_no_revoked_current", False)),
                        require_accepted_evidence=bool(payload.get("require_accepted_evidence", False)),
                    )
                    write_release_portfolio_governance_attestation_registry_verification_report(report, self.release_portfolio_governance_attestation_registry_store.verification_report_path(portfolio_id, profile))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "verification_summary": portfolio_governance_attestation_registry_verification_summary(report)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Registry route not found.")
                return
            if action == "governance-attestation-portal":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.release_portfolio_governance_attestation_portal_store.read_report(portfolio_id, profile=query_profile, default={})
                    verification_path = self.release_portfolio_governance_attestation_portal_store.verification_report_path(portfolio_id, query_profile)
                    summary = portfolio_governance_attestation_portal_summary(report) if report else {"status": "missing", "profile": query_profile}
                    if report:
                        summary["stale"] = self.release_portfolio_governance_attestation_portal_store.report_is_stale(portfolio_id, report, profile=query_profile)
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "profile": query_profile,
                            "report": report,
                            "verification": read_json(verification_path) if verification_path.exists() else {},
                            "summary": summary,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    report = self.release_portfolio_governance_attestation_portal_store.refresh_report(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": portfolio_governance_attestation_portal_summary(report)})
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    manifest = self.release_portfolio_governance_attestation_portal_store.export_portal(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    zip_info = self.release_portfolio_governance_attestation_portal_store.build_zip(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = str(payload.get("profile") or query_profile)
                    report = verify_release_portfolio_governance_attestation_portal(
                        self.release_portfolio_governance_attestation_portal_store.zip_path(portfolio_id, profile),
                        strict=bool(payload.get("strict", False)),
                        require_current=bool(payload.get("require_current", False)),
                        require_registry=bool(payload.get("require_registry", False)),
                        require_attestation=bool(payload.get("require_attestation", False)),
                        require_accepted_evidence=bool(payload.get("require_accepted_evidence", False)),
                    )
                    write_release_portfolio_governance_attestation_portal_verification_report(report, self.release_portfolio_governance_attestation_portal_store.verification_report_path(portfolio_id, profile))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "verification_summary": portfolio_governance_attestation_portal_verification_summary(report)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Portal route not found.")
                return
            if action == "governance-attestation-portal-review":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    pack = self.release_portfolio_governance_attestation_portal_review_store.read_pack(portfolio_id, profile=query_profile, default={})
                    summary = portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {"status": "missing", "profile": query_profile}
                    if pack:
                        summary["stale"] = self.release_portfolio_governance_attestation_portal_review_store.pack_is_stale(portfolio_id, pack, profile=query_profile)
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "profile": query_profile,
                            "review_pack": pack,
                            "summary": summary,
                            "responses": self.release_portfolio_governance_attestation_portal_review_store.list_responses(portfolio_id, profile=query_profile),
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "pack" and len(parts) >= 3:
                    pack_action = parts[3] if len(parts) > 3 else ""
                    if pack_action == "refresh" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        pack = self.release_portfolio_governance_attestation_portal_review_store.refresh_pack(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "review_pack": pack, "summary": portfolio_governance_attestation_portal_review_pack_summary(pack)})
                        return
                    if pack_action == "export" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        manifest = self.release_portfolio_governance_attestation_portal_review_store.export_pack(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                        return
                    if pack_action == "zip" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        zip_info = self.release_portfolio_governance_attestation_portal_review_store.build_pack_zip(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                        return
                    if pack_action == "verify" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        profile = str(payload.get("profile") or query_profile)
                        report = verify_release_portfolio_governance_attestation_portal_review_pack(
                            self.release_portfolio_governance_attestation_portal_review_store.pack_zip_path(portfolio_id, profile),
                            strict=bool(payload.get("strict", False)),
                            require_current=bool(payload.get("require_current", False)),
                        )
                        write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, self.release_portfolio_governance_attestation_portal_review_store.pack_verification_report_path(portfolio_id, profile))
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                        return
                if subaction == "responses" and len(parts) >= 3:
                    if len(parts) == 3:
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "responses": self.release_portfolio_governance_attestation_portal_review_store.list_responses(portfolio_id, profile=query_profile)})
                        return
                    if parts[3] == "import" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._read_json_body()
                        payload.setdefault("profile", query_profile)
                        imported = self.release_portfolio_governance_attestation_portal_review_store.import_response(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, **imported}, status=HTTPStatus.CREATED)
                        return
                    response_id = parts[3]
                    if len(parts) == 4:
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        response = self.release_portfolio_governance_attestation_portal_review_store.get_response(portfolio_id, response_id, profile=query_profile)
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "response": response, "summary": portfolio_governance_attestation_portal_response_summary(response)})
                        return
                    if len(parts) == 5 and parts[4] == "verify":
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        report = self.release_portfolio_governance_attestation_portal_review_store.verify_response(portfolio_id, response_id, profile=query_profile, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                        return
                    if len(parts) == 5 and parts[4] == "create-change-request":
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        result = self.release_portfolio_governance_attestation_portal_review_store.create_change_request(portfolio_id, response_id, self._optional_json_body(), profile=query_profile, now=_utc_now())
                        status = HTTPStatus.OK if result.get("existing") else HTTPStatus.CREATED
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, **result}, status=status)
                        return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Portal Review route not found.")
                return
            if action == "governance-attestation-accepted-evidence":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.read_evidence(portfolio_id, profile=query_profile, default={})
                    summary = portfolio_governance_attestation_accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing", "profile": query_profile}
                    if evidence:
                        summary["stale"] = self.release_portfolio_governance_attestation_accepted_evidence_store.evidence_is_stale(portfolio_id, evidence, profile=query_profile)
                    verification_path = self.release_portfolio_governance_attestation_accepted_evidence_store.verification_report_path(portfolio_id, query_profile)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "profile": query_profile, "accepted_evidence": evidence, "summary": summary, "verification": read_json(verification_path) if verification_path.exists() else {}})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.refresh_evidence(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "accepted_evidence": evidence, "summary": portfolio_governance_attestation_accepted_evidence_summary(evidence)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    manifest = self.release_portfolio_governance_attestation_accepted_evidence_store.export_evidence(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("public_summary", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    zip_info = self.release_portfolio_governance_attestation_accepted_evidence_store.build_zip(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = str(payload.get("profile") or query_profile)
                    report = verify_release_portfolio_governance_attestation_accepted_evidence(
                        self.release_portfolio_governance_attestation_accepted_evidence_store.zip_path(portfolio_id, profile),
                        strict=bool(payload.get("strict", False)),
                        require_current=bool(payload.get("require_current", False)),
                    )
                    write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, self.release_portfolio_governance_attestation_accepted_evidence_store.verification_report_path(portfolio_id, profile))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                    return
                if subaction == "archive" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.archive_evidence(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "accepted_evidence": evidence, "summary": portfolio_governance_attestation_accepted_evidence_summary(evidence)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Accepted Evidence route not found.")
                return
            if action == "governance-attestation-transparency":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    feed = self.release_portfolio_governance_attestation_transparency_store.read_feed(portfolio_id, profile=query_profile, default={})
                    report = self.release_portfolio_governance_attestation_transparency_store.read_report(portfolio_id, profile=query_profile, default={})
                    summary = portfolio_governance_attestation_transparency_summary(feed) if feed else {"status": "missing", "profile": query_profile}
                    if feed:
                        summary["stale"] = self.release_portfolio_governance_attestation_transparency_store.feed_is_stale(portfolio_id, feed, profile=query_profile)
                    verification_path = self.release_portfolio_governance_attestation_transparency_store.verification_report_path(portfolio_id, query_profile)
                    verification = read_json(verification_path) if verification_path.exists() else {}
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "profile": query_profile, "feed": feed, "report": report, "summary": summary, "verification": verification})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "refresh" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    feed = self.release_portfolio_governance_attestation_transparency_store.refresh_feed(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "feed": feed, "summary": portfolio_governance_attestation_transparency_summary(feed)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    manifest = self.release_portfolio_governance_attestation_transparency_store.export_transparency(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("current_public_state", {})}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    payload.setdefault("profile", query_profile)
                    zip_info = self.release_portfolio_governance_attestation_transparency_store.build_zip(portfolio_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = str(payload.get("profile") or query_profile)
                    report = verify_release_portfolio_governance_attestation_transparency(
                        self.release_portfolio_governance_attestation_transparency_store.zip_path(portfolio_id, profile),
                        strict=bool(payload.get("strict", False)),
                        require_current=bool(payload.get("require_current", False)),
                        require_accepted_evidence=bool(payload.get("require_accepted_evidence", False)),
                        require_no_revoked_current=bool(payload.get("require_no_revoked_current", False)),
                        require_contiguous_chain=bool(payload.get("require_contiguous_chain", False)),
                    )
                    write_release_portfolio_governance_attestation_transparency_verification_report(report, self.release_portfolio_governance_attestation_transparency_store.verification_report_path(portfolio_id, profile))
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                    return
                if subaction == "notices" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    notices = self.release_portfolio_governance_attestation_transparency_store.list_notices(portfolio_id, profile=query_profile)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "notices": notices})
                    return
                if subaction == "notices" and len(parts) == 4:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    notice = self.release_portfolio_governance_attestation_transparency_store.get_notice(portfolio_id, parts[3], profile=query_profile)
                    self._send_json({"ok": True, "portfolio_id": portfolio_id, "notice": notice})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Transparency route not found.")
                return
            if action == "governance-attestation-transparency-acknowledgement":
                query = parse_qs(urlparse(self.path).query)
                query_profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    pack = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_pack(portfolio_id, profile=query_profile, default={})
                    evidence = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_evidence(portfolio_id, profile=query_profile, default={})
                    summary = {"status": pack.get("status", "missing") if pack else "missing", "profile": query_profile, "pack_id": pack.get("pack_id") if pack else None}
                    if pack:
                        summary["stale"] = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_is_stale(portfolio_id, pack, profile=query_profile)
                    evidence_summary = portfolio_governance_attestation_transparency_acknowledgement_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing"}
                    if evidence:
                        evidence_summary["stale"] = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_is_stale(portfolio_id, evidence, profile=query_profile)
                    self._send_json(
                        {
                            "ok": True,
                            "portfolio_id": portfolio_id,
                            "profile": query_profile,
                            "pack": pack,
                            "responses": self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_responses(portfolio_id, profile=query_profile),
                            "acknowledgement_evidence": evidence,
                            "change_requests": self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_change_requests(portfolio_id, profile=query_profile),
                            "summary": summary,
                            "evidence_summary": evidence_summary,
                        }
                    )
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "pack" and len(parts) >= 4:
                    pack_action = parts[3]
                    if pack_action == "refresh" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        pack = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.refresh_pack(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "pack": pack, "summary": {"status": pack.get("status"), "pack_id": pack.get("pack_id")}}, status=HTTPStatus.CREATED)
                        return
                    if pack_action == "export" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        manifest = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.export_pack(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                        return
                    if pack_action == "zip" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        zip_info = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.build_pack_zip(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                        return
                    if pack_action == "verify" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        profile = str(payload.get("profile") or query_profile)
                        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
                            self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_zip_path(portfolio_id, profile),
                            strict=bool(payload.get("strict", False)),
                            require_pack=True,
                            require_transparency=bool(payload.get("require_transparency", False)),
                        )
                        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_verification_report_path(portfolio_id, profile))
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                        return
                if subaction == "responses" and len(parts) >= 3:
                    if len(parts) == 3:
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "responses": self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_responses(portfolio_id, profile=query_profile)})
                        return
                    if parts[3] == "import" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._read_json_body()
                        payload.setdefault("profile", query_profile)
                        imported = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.import_response(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, **imported}, status=HTTPStatus.CREATED)
                        return
                    response_id = parts[3]
                    if len(parts) == 4:
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        response = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_response(portfolio_id, response_id, profile=query_profile)
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "response": response})
                        return
                    if len(parts) == 5 and parts[4] == "verify":
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        report = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.verify_response(portfolio_id, response_id, profile=query_profile, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                        return
                    if len(parts) == 5 and parts[4] == "create-change-request":
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        change_request = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.create_change_request(portfolio_id, response_id, self._optional_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_request": change_request}, status=HTTPStatus.CREATED)
                        return
                if subaction == "evidence" and len(parts) >= 4:
                    evidence_action = parts[3]
                    if evidence_action == "refresh" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        evidence = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.refresh_evidence(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "acknowledgement_evidence": evidence, "summary": portfolio_governance_attestation_transparency_acknowledgement_summary(evidence)}, status=HTTPStatus.CREATED)
                        return
                    if evidence_action == "export" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        manifest = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.export_evidence(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                        return
                    if evidence_action == "zip" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        payload.setdefault("profile", query_profile)
                        zip_info = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.build_evidence_zip(portfolio_id, payload, now=_utc_now())
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
                        return
                    if evidence_action == "verify" and len(parts) == 4:
                        if method != "POST":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        payload = self._optional_json_body()
                        profile = str(payload.get("profile") or query_profile)
                        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
                            self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_zip_path(portfolio_id, profile),
                            strict=bool(payload.get("strict", False)),
                            require_response=True,
                            require_accepted=bool(payload.get("require_accepted", False)),
                        )
                        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_verification_report_path(portfolio_id, profile))
                        self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
                        return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Transparency Acknowledgement route not found.")
                return
            if action == "governance-queues" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.create_from_portfolio(portfolio_id, self._optional_json_body(), now=_utc_now())
                status = HTTPStatus.OK if queue.get("existing") else HTTPStatus.CREATED
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "queue": queue, "summary": queue_summary(queue)}, status=status)
                return
            if action == "export" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_portfolio_audit_store.export_portfolio(portfolio_id, now=_utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if action == "export" and len(parts) == 3 and parts[2] == "zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_portfolio_audit_store.build_zip(portfolio_id, now=_utc_now())
                manifest = self.release_portfolio_audit_store.read_export_manifest(portfolio_id)
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if action == "verify" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_portfolio_audit_package(
                    self.release_portfolio_audit_store.zip_path(portfolio_id),
                    strict=bool(payload.get("strict", False)),
                    require_reviewer_packs=bool(payload.get("require_reviewer_packs", False)),
                    require_audit=bool(payload.get("require_audit", False)),
                    require_archive=bool(payload.get("require_archive", False)),
                )
                write_release_portfolio_audit_verification_report(report, self.release_portfolio_audit_store.verification_report_path(portfolio_id))
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": release_portfolio_audit_verification_summary(report)})
                return
            if action == "download" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_audit_store.get_portfolio(portfolio_id)
                self._send_file(self.release_portfolio_audit_store.zip_path(portfolio_id), "application/zip", filename=f"musicforge-{portfolio_id}-portfolio-audit.zip")
                return
            if action == "archive" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                portfolio = self.release_portfolio_audit_store.archive(portfolio_id, now=_utc_now())
                self._send_json({"ok": True, "portfolio": portfolio, "summary": {"status": portfolio.get("status")}})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Audit route not found.")
        except ReleasePortfolioAuditNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioAuditStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioAuditError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAuditNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAuditStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAuditError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceReviewerPackNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceReviewerPackStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceReviewerPackError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceFinalBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceFinalBoardStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceFinalBoardError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceEvidenceVaultNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceEvidenceVaultStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceEvidenceVaultError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationRegistryNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationRegistryStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationRegistryError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalReviewStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationPortalReviewError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationAcceptedEvidenceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_public_trust_centers(self, method: str, path: str) -> None:
        prefix = "/api/public-trust-centers"
        tail = path[len(prefix):]
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    centers = self.public_trust_center_store.list_centers()
                    self._send_json({"ok": True, "centers": centers, "summary": {"count": len(centers)}})
                    return
                if method == "POST":
                    config = self.public_trust_center_store.create_or_update_center(self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "center": config, "summary": public_trust_center_summary(self.public_trust_center_store.read_report(str(config.get("center_id") or "ptc-default"), default={}))}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center route not found.")
                return
            center_id = parts[0]
            if center_id.endswith(".zip") and len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                actual_id = center_id[:-4]
                self.public_trust_center_store.get_center(actual_id)
                self._send_file(self.public_trust_center_store.zip_path(actual_id), "application/zip", filename=f"musicforge-{actual_id}-public-trust-center.zip")
                return
            action = parts[1] if len(parts) > 1 else ""
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.public_trust_center_store.get_center(center_id)
                self._send_json({"ok": True, **detail})
                return
            if action == "refresh" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.public_trust_center_store.refresh_report(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_summary(report)}, status=HTTPStatus.CREATED)
                return
            if action == "export" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.public_trust_center_store.export_center(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                return
            if action == "zip" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.public_trust_center_store.build_zip(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                return
            if action == "verify" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_public_trust_center_package(
                    self.public_trust_center_store.zip_path(center_id),
                    strict=bool(payload.get("strict", True)),
                    require_registry_current=bool(payload.get("require_registry_current", False)),
                    require_portal_current=bool(payload.get("require_portal_current", False)),
                    require_transparency_current=bool(payload.get("require_transparency_current", False)),
                    require_acknowledgement_current=bool(payload.get("require_acknowledgement_current", False)),
                    require_release_readiness=bool(payload.get("require_release_readiness", False)),
                    require_delivery_readiness=bool(payload.get("require_delivery_readiness", False)),
                    require_distribution_ready=bool(payload.get("require_distribution_ready", False)),
                    require_submission_accepted=bool(payload.get("require_submission_accepted", False)),
                    require_submission_evidence=bool(payload.get("require_submission_evidence", False)),
                    require_operations_signed=bool(payload.get("require_operations_signed", False)),
                    require_operations_audit=bool(payload.get("require_operations_audit", False)),
                    require_operations_reviewer_pack=bool(payload.get("require_operations_reviewer_pack", False)),
                    delivery_anchor_path=self.public_trust_center_store.delivery_anchor_path(center_id),
                    anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(center_id) if bool(payload.get("require_anchor_registry_current", False)) or bool(payload.get("require_anchor_published", False)) or bool(payload.get("require_anchor_not_revoked", False)) or bool(payload.get("use_anchor_registry", False)) else None,
                    anchor_transparency_path=self.public_trust_center_anchor_transparency_store.zip_path(center_id) if bool(payload.get("require_anchor_transparency_current", False)) or bool(payload.get("require_anchor_checkpoint", False)) or bool(payload.get("use_anchor_transparency", False)) else None,
                    anchor_checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id) if bool(payload.get("require_anchor_checkpoint", False)) or bool(payload.get("use_anchor_transparency", False)) else None,
                    require_anchor_registry_current=bool(payload.get("require_anchor_registry_current", False)),
                    require_anchor_published=bool(payload.get("require_anchor_published", False)),
                    require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", False)),
                    require_anchor_transparency_current=bool(payload.get("require_anchor_transparency_current", False)),
                    require_anchor_checkpoint=bool(payload.get("require_anchor_checkpoint", False)),
                )
                write_public_trust_center_verification_report(report, self.public_trust_center_store.verification_report_path(center_id))
                self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                return
            if action == "anchor-registry":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    registry = self.public_trust_center_anchor_registry_store.read_registry(center_id, default={})
                    report = self.public_trust_center_anchor_registry_store.read_report(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "registry": registry, "report": report, "summary": self.public_trust_center_anchor_registry_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_registry_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-anchor-registry.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "register-current" and len(parts) == 3:
                    result = self.public_trust_center_anchor_registry_store.register_current_anchor(center_id, payload, now=_utc_now())
                    status = HTTPStatus.OK if result.get("existing") else HTTPStatus.CREATED
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})}, status=status)
                    return
                if subaction == "publish" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.publish_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "revoke" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.revoke_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "supersede" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.supersede_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_anchor_registry_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_anchor_registry_summary(self.public_trust_center_anchor_registry_store.read_registry(center_id, default={}))}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_anchor_registry_store.export_registry(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_anchor_registry_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = verify_public_trust_center_anchor_registry_package(
                        self.public_trust_center_anchor_registry_store.zip_path(center_id),
                        strict=bool(payload.get("strict", True)),
                        require_current=bool(payload.get("require_current", False)),
                        require_anchor_published=bool(payload.get("require_anchor_published", False)),
                        require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", False)),
                    )
                    write_public_trust_center_anchor_registry_verification_report(report, self.public_trust_center_anchor_registry_store.verification_report_path(center_id))
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Anchor Registry route not found.")
                return
            if action == "anchor-transparency":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.public_trust_center_anchor_transparency_store.read_report(center_id, default={})
                    checkpoint = self.public_trust_center_anchor_transparency_store.read_checkpoint(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "checkpoint": checkpoint, "summary": self.public_trust_center_anchor_transparency_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_transparency_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-anchor-transparency.zip")
                    return
                if subaction == "checkpoint" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id), "application/json", filename=f"musicforge-{center_id}-anchor-checkpoint.json")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_anchor_transparency_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_anchor_transparency_summary(report)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "checkpoint" and len(parts) == 4 and parts[3] == "create":
                    checkpoint = self.public_trust_center_anchor_transparency_store.create_checkpoint(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "checkpoint": checkpoint}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_anchor_transparency_store.export_transparency(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_anchor_transparency_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = verify_public_trust_center_anchor_transparency_package(
                        self.public_trust_center_anchor_transparency_store.zip_path(center_id),
                        strict=bool(payload.get("strict", True)),
                        checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id) if bool(payload.get("require_current_checkpoint", False)) or bool(payload.get("use_checkpoint", False)) else None,
                        anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(center_id) if bool(payload.get("use_anchor_registry", False)) or bool(payload.get("require_published_anchor", False)) or bool(payload.get("require_not_revoked", False)) else None,
                        require_current_checkpoint=bool(payload.get("require_current_checkpoint", False)),
                        require_published_anchor=bool(payload.get("require_published_anchor", False)),
                        require_not_revoked=bool(payload.get("require_not_revoked", False)),
                    )
                    write_public_trust_center_anchor_transparency_verification_report(report, self.public_trust_center_anchor_transparency_store.verification_report_path(center_id))
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Anchor Transparency route not found.")
                return
            if action == "distribution-kit":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.public_trust_center_distribution_kit_store.read_report(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": self.public_trust_center_distribution_kit_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "acceptance":
                    self._handle_public_trust_center_distribution_kit_acceptance(method, center_id, parts)
                    return
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_distribution_kit_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-distribution-kit.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_distribution_kit_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_distribution_kit_summary(report)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_distribution_kit_store.export_kit(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_distribution_kit_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = self.public_trust_center_distribution_kit_store.verify_zip(
                        center_id,
                        {
                            "strict": bool(payload.get("strict", True)),
                            "deep": bool(payload.get("deep", True)),
                            "require_current": bool(payload.get("require_current", True)),
                            "require_delivery_readiness": bool(payload.get("require_delivery_readiness", True)),
                            "require_anchor_registry_current": bool(payload.get("require_anchor_registry_current", True)),
                            "require_anchor_published": bool(payload.get("require_anchor_published", True)),
                            "require_anchor_not_revoked": bool(payload.get("require_anchor_not_revoked", True)),
                            "require_anchor_transparency_current": bool(payload.get("require_anchor_transparency_current", True)),
                            "require_anchor_checkpoint": bool(payload.get("require_anchor_checkpoint", True)),
                        },
                        now=_utc_now(),
                    )
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Distribution Kit route not found.")
                return
            if action == "acceptance-board":
                self._handle_public_trust_center_acceptance_board(method, center_id, parts)
                return
            if action == "archive" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                archive = self.public_trust_center_store.archive_snapshot(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "archive": archive, "summary": {"status": "archived", "zip_sha256": archive.get("zip_sha256")}})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center route not found.")
        except PublicTrustCenterNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAnchorRegistryNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAnchorRegistryStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAnchorRegistryError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAnchorTransparencyNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAnchorTransparencyStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAnchorTransparencyError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterDistributionKitNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterDistributionKitStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterDistributionKitError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAcceptanceBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAcceptanceBoardStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAcceptanceBoardError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_public_trust_center_acceptance_board(self, method: str, center_id: str, parts: list[str]) -> None:
        try:
            if len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(
                    {
                        "ok": True,
                        "center_id": center_id,
                        "report": self.public_trust_center_acceptance_board_store.read_report(center_id, default={}),
                        "conflict_report": self.public_trust_center_acceptance_board_store.read_conflict_report(center_id, default={}),
                        "policy": self.public_trust_center_acceptance_board_store.read_policy(center_id),
                        "summary": self.public_trust_center_acceptance_board_store.summary(center_id),
                    }
                )
                return
            subaction = parts[2] if len(parts) > 2 else ""
            if subaction == "download" and len(parts) == 3:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.public_trust_center_acceptance_board_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-acceptance-board.zip")
                return
            if subaction == "signoff-archive" and len(parts) >= 4 and parts[3] == "download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.public_trust_center_acceptance_board_store.signoff_archive_zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-acceptance-board-signoff-archive.zip")
                return
            if subaction == "policy" and len(parts) == 3:
                if method == "GET":
                    policy = self.public_trust_center_acceptance_board_store.read_policy(center_id)
                    self._send_json({"ok": True, "center_id": center_id, "policy": policy})
                    return
                if method == "POST":
                    policy = self.public_trust_center_acceptance_board_store.save_policy(center_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "policy": policy}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            if subaction == "refresh" and len(parts) == 3:
                report = self.public_trust_center_acceptance_board_store.refresh_report(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": self.public_trust_center_acceptance_board_store.summary(center_id)}, status=HTTPStatus.CREATED)
                return
            if subaction == "export" and len(parts) == 3:
                manifest = self.public_trust_center_acceptance_board_store.export_board(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                return
            if subaction == "zip" and len(parts) == 3:
                zip_info = self.public_trust_center_acceptance_board_store.build_zip(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                return
            if subaction == "verify" and len(parts) == 3:
                report = self.public_trust_center_acceptance_board_store.verify_zip(
                    center_id,
                    {
                        "strict": bool(payload.get("strict", True)),
                        "require_ready": bool(payload.get("require_ready", False)),
                        "require_quorum": bool(payload.get("require_quorum", False)),
                        "require_no_conflicts": bool(payload.get("require_no_conflicts", False)),
                        "min_accepted_count": int(payload.get("min_accepted_count") or 0),
                        "min_accepted_organizations": int(payload.get("min_accepted_organizations") or 0),
                        "required_roles": payload.get("required_roles") if isinstance(payload.get("required_roles"), list) else [],
                        "use_distribution_kit": bool(payload.get("use_distribution_kit", True)),
                    },
                )
                self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                return
            if subaction == "signoff-draft" and len(parts) == 3:
                draft = self.public_trust_center_acceptance_board_store.create_signoff_draft(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "draft": draft}, status=HTTPStatus.CREATED)
                return
            if subaction == "signoff" and len(parts) == 3:
                signoff = self.public_trust_center_acceptance_board_store.signoff(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "signoff": signoff, "summary": self.public_trust_center_acceptance_board_store.summary(center_id)}, status=HTTPStatus.CREATED)
                return
            if subaction == "change-request" and len(parts) == 3:
                change = self.public_trust_center_acceptance_board_store.create_change_request(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "change_request": change}, status=HTTPStatus.CREATED)
                return
            if subaction == "change-requests" and len(parts) >= 5 and parts[4] == "approve":
                change = self.public_trust_center_acceptance_board_store.approve_change_request(center_id, parts[3], payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "change_request": change})
                return
            if subaction == "reset-signoff" and len(parts) == 3:
                reset = self.public_trust_center_acceptance_board_store.reset_signoff(center_id, payload, now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "reset": reset, "summary": self.public_trust_center_acceptance_board_store.summary(center_id)})
                return
            if subaction == "signoff-archive" and len(parts) == 4:
                archive_action = parts[3]
                if archive_action == "export":
                    manifest = self.public_trust_center_acceptance_board_store.export_signoff_archive(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                    return
                if archive_action == "zip":
                    zip_info = self.public_trust_center_acceptance_board_store.build_signoff_archive_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if archive_action == "verify":
                    report = self.public_trust_center_acceptance_board_store.verify_signoff_archive_zip(center_id, {"strict": bool(payload.get("strict", True)), "require_signed": True, "require_current": True, "require_ready": True})
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Acceptance Board route not found.")
        except PublicTrustCenterAcceptanceBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAcceptanceBoardStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAcceptanceBoardError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_public_trust_center_distribution_kit_acceptance(self, method: str, center_id: str, parts: list[str]) -> None:
        try:
            if len(parts) == 3:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(
                    {
                        "ok": True,
                        "center_id": center_id,
                        "summary": self.public_trust_center_distribution_kit_acceptance_store.summary(center_id),
                        "responses": self.public_trust_center_distribution_kit_acceptance_store.list_responses(center_id),
                        "change_requests": self.public_trust_center_distribution_kit_acceptance_store.list_change_requests(center_id),
                    }
                )
                return
            if len(parts) == 4 and parts[3] == "template":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.public_trust_center_distribution_kit_acceptance_store.create_response_template(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "template": template}, status=HTTPStatus.CREATED)
                return
            if len(parts) == 4 and parts[3] == "import":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                imported = self.public_trust_center_distribution_kit_acceptance_store.import_response(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, **imported}, status=HTTPStatus.CREATED)
                return
            if len(parts) >= 5 and parts[3] == "responses":
                response_id = parts[4]
                if len(parts) == 5:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    response = self.public_trust_center_distribution_kit_acceptance_store.read_response(center_id, response_id)
                    self._send_json({"ok": True, "center_id": center_id, "response": response})
                    return
                response_action = parts[5] if len(parts) > 5 else ""
                if response_action == "verify" and len(parts) == 6:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.public_trust_center_distribution_kit_acceptance_store.verify_response(center_id, response_id, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "response_id": response_id, "verification": report, "summary": report.get("summary", {})})
                    return
                if response_action == "change-request-draft" and len(parts) == 6:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    draft = self.public_trust_center_distribution_kit_acceptance_store.create_change_request_draft(center_id, response_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "draft": draft}, status=HTTPStatus.CREATED)
                    return
                if response_action == "evidence" and len(parts) >= 7:
                    evidence_action = parts[6]
                    if evidence_action == "download" and len(parts) == 7:
                        if method != "GET":
                            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                            return
                        evidence = self.public_trust_center_distribution_kit_acceptance_store.refresh_accepted_evidence(center_id, {"response_id": response_id}, now=_utc_now())
                        self._send_file(self.public_trust_center_distribution_kit_acceptance_store.evidence_zip_path(center_id, str(evidence.get("evidence_id") or "")), "application/zip", filename=f"musicforge-{center_id}-distribution-kit-accepted-evidence.zip")
                        return
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if evidence_action == "export" and len(parts) == 7:
                        manifest = self.public_trust_center_distribution_kit_acceptance_store.export_accepted_evidence(center_id, response_id, now=_utc_now())
                        self._send_json({"ok": True, "center_id": center_id, "manifest": manifest}, status=HTTPStatus.CREATED)
                        return
                    if evidence_action == "zip" and len(parts) == 7:
                        zip_info = self.public_trust_center_distribution_kit_acceptance_store.build_accepted_evidence_zip(center_id, response_id, now=_utc_now())
                        evidence = self.public_trust_center_distribution_kit_acceptance_store.read_evidence(center_id, str(zip_info.get("evidence_id") or ""), default={})
                        self._send_json({"ok": True, "center_id": center_id, "zip": zip_info, "summary": public_trust_center_distribution_kit_accepted_evidence_summary(evidence)})
                        return
                    if evidence_action == "verify" and len(parts) == 7:
                        evidence = self.public_trust_center_distribution_kit_acceptance_store.refresh_accepted_evidence(center_id, {"response_id": response_id}, now=_utc_now())
                        report = self.public_trust_center_distribution_kit_acceptance_store.verify_accepted_evidence_zip(center_id, str(evidence.get("evidence_id") or ""), {"strict": True, "require_current": True})
                        self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                        return
            self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Distribution Kit Acceptance route not found.")
        except PublicTrustCenterDistributionKitAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_portfolio_governance_queues(self, method: str, path: str) -> None:
        prefix = "/api/release-portfolio-governance-queues"
        tail = path[len(prefix):]
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                portfolio_id = str(query.get("portfolio_id", [""])[0] or "").strip() or None
                include_archived = str(query.get("include_archived", [""])[0]).lower() in {"1", "true", "yes"}
                queues = self.release_portfolio_governance_store.list_queues(portfolio_id=portfolio_id, include_archived=include_archived)
                self._send_json({"ok": True, "queues": queues, "summary": {"count": len(queues)}})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Queue route not found.")
                return
            queue_id = parts[0]
            action = parts[1] if len(parts) > 1 else ""
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.get_queue(queue_id)
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json(
                    {
                        "ok": True,
                        "queue": queue,
                        "summary": queue_summary(queue, execution),
                        "signoff_summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id),
                        "archive_summary": self.release_portfolio_governance_signoff_store.archive_summary(queue_id),
                        "change_request_summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id),
                    }
                )
                return
            if action == "plan" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_portfolio_governance_store.read_action_plan(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "action_plan": plan, "summary": {"item_count": len(plan.get("items", []) if isinstance(plan.get("items"), list) else [])}})
                return
            if action == "execution" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "execution_report": execution, "summary": execution.get("summary", {})})
                return
            if action == "manual-actions" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manual = self.release_portfolio_governance_store.read_manual_action_list(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "manual_action_list": manual, "summary": {"count": len(manual.get("items", []) if isinstance(manual.get("items"), list) else [])}})
                return
            if action == "run-safe" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.run_safe_actions(queue_id, self._optional_json_body(), now=_utc_now())
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json({"ok": True, "queue": queue, "execution_report": execution, "summary": queue_summary(queue, execution)})
                return
            if action == "export" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_portfolio_governance_store.export_queue(queue_id, now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if action == "export" and len(parts) == 3 and parts[2] == "zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_portfolio_governance_store.build_zip(queue_id, now=_utc_now())
                manifest = self.release_portfolio_governance_store.read_export_manifest(queue_id)
                self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if action == "verify" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_portfolio_governance_package(
                    self.release_portfolio_governance_store.zip_path(queue_id),
                    strict=bool(payload.get("strict", False)),
                    require_manual_actions=bool(payload.get("require_manual_actions", False)),
                    require_no_blocked=bool(payload.get("require_no_blocked", False)),
                )
                write_release_portfolio_governance_verification_report(report, self.release_portfolio_governance_store.verification_report_path(queue_id))
                self._send_json({"ok": True, "queue_id": queue_id, "verification": report, "summary": release_portfolio_governance_verification_summary(report)})
                return
            if action == "signoff" and len(parts) == 2:
                if method == "GET":
                    signoff = self.release_portfolio_governance_signoff_store.read_signoff(queue_id, default={})
                    gate = self.release_portfolio_governance_signoff_store.gate(queue_id, {}, now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff), "gate": gate})
                    return
                if method == "POST":
                    signoff = self.release_portfolio_governance_signoff_store.signoff(queue_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "signoff" and len(parts) == 3 and parts[2] == "reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.release_portfolio_governance_signoff_store.reset_signoff(queue_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff)})
                return
            if action == "change-requests":
                if len(parts) == 2:
                    if method == "GET":
                        rows = self.release_portfolio_governance_signoff_store.list_change_requests(queue_id)
                        self._send_json({"ok": True, "queue_id": queue_id, "change_requests": rows, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)})
                        return
                    if method == "POST":
                        item = self.release_portfolio_governance_signoff_store.create_change_request(queue_id, self._optional_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "queue_id": queue_id, "change_request": item, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                change_request_id = parts[2]
                if len(parts) == 3 and method == "GET":
                    item = self.release_portfolio_governance_signoff_store.get_change_request(queue_id, change_request_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "change_request": item})
                    return
                if len(parts) == 4 and method == "POST" and parts[3] in {"approve", "reject", "archive"}:
                    item = self.release_portfolio_governance_signoff_store.update_change_request_status(queue_id, change_request_id, parts[3], self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "change_request": item, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Change Request route not found.")
                return
            if action == "archive.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_governance_store.get_queue(queue_id)
                self._send_file(self.release_portfolio_governance_signoff_store.archive_zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-portfolio-governance-archive.zip")
                return
            if action == "archive" and len(parts) >= 2:
                if len(parts) == 2 and method == "GET":
                    manifest = self.release_portfolio_governance_signoff_store.read_archive_manifest(queue_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": self.release_portfolio_governance_signoff_store.archive_summary(queue_id)})
                    return
                if len(parts) == 3 and parts[2] == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_signoff_store.export_archive(queue_id, now=_utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 3 and parts[2] == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_signoff_store.build_archive_zip(queue_id, now=_utc_now())
                    manifest = self.release_portfolio_governance_signoff_store.read_archive_manifest(queue_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if len(parts) == 3 and parts[2] == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = verify_release_portfolio_governance_archive_package(
                        self.release_portfolio_governance_signoff_store.archive_zip_path(queue_id),
                        strict=bool(payload.get("strict", False)),
                        require_signed=bool(payload.get("require_signed", False)),
                        require_no_force=bool(payload.get("require_no_force", False)),
                    )
                    write_release_portfolio_governance_archive_verification_report(report, self.release_portfolio_governance_signoff_store.archive_verification_report_path(queue_id))
                    self._send_json({"ok": True, "queue_id": queue_id, "verification": report, "summary": release_portfolio_governance_archive_verification_summary(report)})
                    return
            if action == "download" and len(parts) == 2:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_governance_store.get_queue(queue_id)
                self._send_file(self.release_portfolio_governance_store.zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-portfolio-governance.zip")
                return
            if action == "archive" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.archive(queue_id, now=_utc_now())
                self._send_json({"ok": True, "queue": queue, "summary": queue_summary(queue)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Governance Queue route not found.")
        except ReleasePortfolioGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleasePortfolioGovernanceSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleasePortfolioGovernanceSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleasePortfolioGovernanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
