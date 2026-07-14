from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class DeliveryRoutesPart007:
    def _handle_submission_route(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    batches = self.submission_store.list_submissions(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "submissions": [self._submission_payload_with_evidence_summary(release_id, batch) for batch in batches], "summary": self.submission_store.summary(release_id)})
                    return
                if method == "POST":
                    batch = self.submission_store.create_submission(release_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail == "/batches" or tail == "":
                if method == "GET":
                    batches = self.submission_store.list_submissions(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "submissions": [self._submission_payload_with_evidence_summary(release_id, batch) for batch in batches], "summary": self.submission_store.summary(release_id)})
                    return
                if method == "POST":
                    batch = self.submission_store.create_submission(release_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            route = _match_submission_tail(tail)
            if route is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Submission route not found.")
                return
            submission_id, action, item_id = route
            batch = self.submission_store.get_submission(release_id, submission_id)
            if action == "":
                if method == "GET":
                    signoff = self.submission_store.read_signoff(release_id, submission_id, default={})
                    qa = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                    self._send_json({"ok": True, "release_id": release_id, "submission": self._submission_payload_with_evidence_summary(release_id, batch), "summary": submission_batch_summary(batch), "qa_summary": submission_qa_summary(qa), "signoff_summary": submission_signoff_summary(signoff), "events": self.submission_store.read_events(release_id, submission_id)})
                    return
                if method in {"POST", "PATCH"}:
                    batch = self.submission_store.update_submission(release_id, submission_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "targets":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                target_id = str(payload.get("target_id") or "").strip()
                if not target_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "target_id is required.")
                    return
                batch = self.submission_store.add_target(release_id, submission_id, target_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "remove-item":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.remove_target(release_id, submission_id, item_id or "")
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.refresh_items(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "qa":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "submission_qa": report, "summary": submission_qa_summary(report)})
                return

            if action == "qa-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.ensure_mutable(batch)
                report = self._get_or_refresh_submission_qa(release_id, batch, refresh=True)
                self.submission_store.append_event(release_id, submission_id, "submission_qa_refreshed", {"status": report.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "submission_qa": report, "summary": submission_qa_summary(report)})
                return

            if action == "export":
                if method == "GET":
                    try:
                        manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                    except FileNotFoundError:
                        self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": {}, "summary": submission_export_summary({})})
                        return
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": submission_export_summary(manifest)})
                    return
                if method == "POST":
                    self.submission_store.ensure_mutable(batch)
                    report = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                    manifest = build_submission_export_bundle(store=self.submission_store, release_id=release_id, submission=batch, qa_report=report, now=_utc_now())
                    batch = self.submission_store.get_submission(release_id, submission_id)
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "manifest": manifest, "summary": submission_export_summary(manifest)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "export-zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.ensure_mutable(batch)
                zip_info = build_submission_package_zip(self.submission_store, release_id, batch, now=_utc_now())
                manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                batch = self.submission_store.update_export_summary(release_id, submission_id, submission_export_summary(manifest))
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "zip": zip_info, "summary": submission_export_summary(manifest)})
                return

            if action == "export-zip-download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.get_submission(release_id, submission_id)
                self._send_file(self.submission_store.package_zip_path(release_id, submission_id), "application/zip", filename=f"musicforge-{release_id}-{submission_id}-submission.zip")
                return

            if action == "signoff":
                if method == "GET":
                    signoff = self.submission_store.read_signoff(release_id, submission_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_signoff_summary(signoff)})
                    return
                if method == "POST":
                    self.submission_store.ensure_mutable(batch)
                    report = self._get_or_refresh_submission_qa(release_id, batch, refresh=True)
                    payload = self._optional_json_body()
                    if bool(payload.get("require_rights_clearance", False)):
                        rights_gate = self.rights_clearance_store.gate(release_id, required=True, now=_utc_now())
                        if rights_gate.get("hard_block") and rights_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(rights_gate.get("message") or "Rights clearance gate failed."), "rights_clearance": rights_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        try:
                            export_manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                        except FileNotFoundError:
                            export_manifest = {}
                        export_gate = self._package_rights_clearance_export_gate(export_manifest, rights_gate, package_label="Submission")
                        if export_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(export_gate.get("message") or "Submission Export is stale. Rebuild export before signoff."), "rights_clearance": rights_gate, "rights_clearance_export": export_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        payload = {**payload, "require_rights_clearance": True, "rights_clearance": rights_gate}
                    signoff = sign_submission_package(store=self.submission_store, release_id=release_id, submission=batch, qa_report=report, payload=payload, now=_utc_now())
                    batch = self.submission_store.get_submission(release_id, submission_id)
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "signoff": signoff, "summary": submission_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "signoff-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                if not reason:
                    self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
                    return
                event = self.submission_store.reset_signoff(release_id, submission_id, reason)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if action == "verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_submission_package(
                    self.submission_store.package_zip_path(release_id, submission_id),
                    strict=bool(payload.get("strict", False)),
                    require_submitted=bool(payload.get("require_submitted", False)),
                    require_accepted=bool(payload.get("require_accepted", False)),
                    deep=bool(payload.get("deep", False)),
                )
                write_submission_verification_report(report, self.submission_store.submission_dir(release_id, submission_id) / "submission-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "verification": report, "summary": submission_verification_summary(report)})
                return

            if action == "evidence":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                overview = self.submission_evidence_store.overview(release_id, submission_id)
                self._send_json({"ok": True, **overview})
                return

            if action == "evidence-report-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.submission_evidence_store.refresh_report(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "evidence_report": report, "summary": submission_evidence_report_summary(report)})
                return

            if action == "evidence-export":
                if method == "GET":
                    try:
                        manifest = self.submission_evidence_store.read_export_manifest(release_id, submission_id)
                    except SubmissionEvidenceNotFoundError:
                        self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": {}, "summary": {"status": "missing"}})
                        return
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": manifest.get("summary", {})})
                    return
                if method == "POST":
                    manifest = self.submission_evidence_store.export_evidence(release_id, submission_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "evidence-export-zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.submission_evidence_store.build_zip(release_id, submission_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "zip": zip_info})
                return

            if action == "evidence-export-zip-download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.submission_evidence_store.package_zip_path(release_id, submission_id), "application/zip", filename=f"musicforge-{release_id}-{submission_id}-submission-evidence.zip")
                return

            if action == "evidence-signoff":
                if method == "GET":
                    signoff = self.submission_evidence_store.read_signoff(release_id, submission_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_evidence_signoff_summary(signoff)})
                    return
                if method == "POST":
                    signoff = self.submission_evidence_store.signoff_evidence(release_id, submission_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_evidence_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "evidence-signoff-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                event = self.submission_evidence_store.reset_signoff(release_id, submission_id, reason)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if action == "evidence-verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_submission_evidence_package(
                    self.submission_evidence_store.package_zip_path(release_id, submission_id),
                    strict=bool(payload.get("strict", False)),
                    deep=bool(payload.get("deep", False)),
                    require_submitted=bool(payload.get("require_submitted", False)),
                    require_accepted=bool(payload.get("require_accepted", False)),
                    require_rights_clearance=bool(payload.get("require_rights_clearance", False)),
                )
                write_submission_evidence_verification_report(report, self.submission_store.submission_dir(release_id, submission_id) / "submission-evidence-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "verification": report, "summary": submission_evidence_verification_summary(report)})
                return

            if action == "evidence-upload-attachment":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                attachment = self.submission_evidence_store.upload_attachment(release_id, submission_id, item_id or "", self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "item_id": item_id, "attachment": attachment}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-submission-receipt":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_submission(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-feedback":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_feedback(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-acceptance":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.mark_accepted(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-resubmission-round":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                round_record = self.submission_evidence_store.create_resubmission_round(release_id, submission_id, item_id or "", self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "item_id": item_id, "round": round_record}, status=HTTPStatus.CREATED)
                return

            if action == "record-submission":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_submission(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "record-feedback":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_feedback(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "mark-accepted":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.mark_accepted(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.archive_submission(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Submission route not found.")
        except (ReleaseNotFoundError, SubmissionNotFoundError, SubmissionEvidenceNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (SubmissionStateError, SubmissionEvidenceStateError, SubmissionExportError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (SubmissionValidationError, SubmissionEvidenceValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
