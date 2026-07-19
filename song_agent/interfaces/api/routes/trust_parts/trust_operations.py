from __future__ import annotations

from typing import Any as _InterfaceType


from song_agent.interfaces.api.route_contexts.trust import TrustRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesTrustOperations(TrustRouteContext):
    @property
    def trust_operations_hub_store(self) -> _InterfaceType:
        return self.server.trust_operations_hub_store

    @property
    def trust_operations_incident_store(self) -> _InterfaceType:
        return self.server.trust_operations_incident_store

    @property
    def trust_operations_incident_knowledge_store(self) -> _InterfaceType:
        return self.server.trust_operations_incident_knowledge_store

    @property
    def trust_operations_control_store(self) -> _InterfaceType:
        return self.server.trust_operations_control_store

    @property
    def trust_operations_control_signoff_store(self) -> _InterfaceType:
        return self.server.trust_operations_control_signoff_store

    @property
    def trust_operations_assurance_store(self) -> _InterfaceType:
        return self.server.trust_operations_assurance_store

    @property
    def trust_operations_assurance_watch_store(self) -> _InterfaceType:
        return self.server.trust_operations_assurance_watch_store

    @property
    def trust_operations_assurance_watch_signoff_store(self) -> _InterfaceType:
        return self.server.trust_operations_assurance_watch_signoff_store

    @property
    def trust_operations_final_readiness_store(self) -> _InterfaceType:
        return self.server.trust_operations_final_readiness_store

    @property
    def release_portfolio_audit_store(self) -> _InterfaceType:
        return self.server.release_portfolio_audit_store

    @property
    def release_portfolio_governance_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_store

    @property
    def release_portfolio_governance_signoff_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_signoff_store

    @property
    def release_portfolio_governance_audit_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_audit_store

    @property
    def release_portfolio_governance_reviewer_pack_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_reviewer_pack_store

    @property
    def release_portfolio_governance_final_board_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_final_board_store

    @property
    def release_portfolio_governance_evidence_vault_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_evidence_vault_store

    @property
    def release_portfolio_governance_attestation_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_store

    @property
    def release_portfolio_governance_attestation_registry_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_registry_store

    @property
    def release_portfolio_governance_attestation_portal_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_portal_store

    @property
    def release_portfolio_governance_attestation_portal_review_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_portal_review_store

    @property
    def release_portfolio_governance_attestation_accepted_evidence_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_accepted_evidence_store

    @property
    def release_portfolio_governance_attestation_transparency_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_transparency_store

    @property
    def release_portfolio_governance_attestation_transparency_acknowledgement_store(self) -> _InterfaceType:
        return self.server.release_portfolio_governance_attestation_transparency_acknowledgement_store

    @property
    def public_trust_center_store(self) -> _InterfaceType:
        return self.server.public_trust_center_store

    @property
    def public_trust_center_anchor_registry_store(self) -> _InterfaceType:
        return self.server.public_trust_center_anchor_registry_store

    @property
    def public_trust_center_anchor_transparency_store(self) -> _InterfaceType:
        return self.server.public_trust_center_anchor_transparency_store

    @property
    def public_trust_center_distribution_kit_store(self) -> _InterfaceType:
        return self.server.public_trust_center_distribution_kit_store

    @property
    def public_trust_center_distribution_kit_acceptance_store(self) -> _InterfaceType:
        return self.server.public_trust_center_distribution_kit_acceptance_store

    @property
    def public_trust_center_acceptance_board_store(self) -> _InterfaceType:
        return self.server.public_trust_center_acceptance_board_store

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
            self._handle_trust_operations_control_signoff(method, _interfaces_api_runtime.unquote(hub_id), "/" + rest if rest else "")
            return
        prefix = "/api/trust-operations/hubs/"
        if not path.startswith(prefix):
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations route not found.")
            return
        tail = path.removeprefix(prefix)
        hub_id, sep, rest = tail.partition("/")
        if not hub_id or not sep:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Hub route not found.")
            return
        rest = "/" + rest
        if rest == "/incidents.zip":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.trust_operations_incident_store.zip_path(_interfaces_api_runtime.unquote(hub_id)), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-incidents.zip")
            return
        if rest == "/knowledge.zip":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.trust_operations_incident_knowledge_store.zip_path(_interfaces_api_runtime.unquote(hub_id)), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-knowledge.zip")
            return
        if rest.startswith("/controls/") and rest.endswith(".zip"):
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in rest.split("/") if part]
            if len(parts) == 2:
                assessment_id = _interfaces_api_runtime.unquote(parts[1].removesuffix(".zip"))
                self._send_file(self.trust_operations_control_store.zip_path(_interfaces_api_runtime.unquote(hub_id), assessment_id), "application/zip", filename=f"musicforge-{hub_id}-trust-operations-controls.zip")
                return
        if rest == "/controls" or rest.startswith("/controls/"):
            self._handle_trust_operations_controls(method, _interfaces_api_runtime.unquote(hub_id), rest.removeprefix("/controls"))
            return
        if rest == "/incidents" or rest.startswith("/incidents/"):
            self._handle_trust_operations_incidents(method, _interfaces_api_runtime.unquote(hub_id), rest.removeprefix("/incidents"))
            return
        if rest == "/knowledge" or rest.startswith("/knowledge/"):
            self._handle_trust_operations_knowledge(method, _interfaces_api_runtime.unquote(hub_id), rest.removeprefix("/knowledge"))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Hub route not found.")

    def _handle_trust_operations_assurance(self, method: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "runs": self.trust_operations_assurance_store.list_runs()})
                return
            if tail == "/runs":
                if method == "GET":
                    query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
                    hub_id = query.get("hub_id", [None])[0]
                    self._send_json({"ok": True, "runs": self.trust_operations_assurance_store.list_runs(hub_id=hub_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    hub_id = str(payload.get("hub_id") or "hub")
                    policy_id = str(payload.get("policy_id") or "default")
                    result = self.trust_operations_assurance_store.refresh_run(hub_id, payload, policy_id=policy_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": result.get("run", {}).get("status") == "passed", **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) >= 2 and parts[0] == "runs":
                run_id = _interfaces_api_runtime.unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, **self.trust_operations_assurance_store.summary(run_id)})
                    return
                action = parts[2]
                if action == "download":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.trust_operations_assurance_store.archive_zip_path(run_id), "application/zip", filename=f"musicforge-{run_id}-trust-operations-assurance.zip")
                    return
                if action == "export":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.trust_operations_assurance_store.export_archive(run_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "run_id": run_id, "manifest": manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.trust_operations_assurance_store.build_archive_zip(run_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "run_id": run_id, "zip": zip_info})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.trust_operations_assurance_store.verify_archive_zip(run_id, self._optional_json_body())
                    _interfaces_api_runtime.write_trust_operations_assurance_verification_report(report, self.trust_operations_assurance_store.verification_report_path(run_id))
                    self._send_json({"ok": report.get("status") != "failed", "run_id": run_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Assurance route not found.")
        except _interfaces_api_runtime.TrustOperationsAssuranceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.TrustOperationsAssuranceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
