from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustRoutesPart006:
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
