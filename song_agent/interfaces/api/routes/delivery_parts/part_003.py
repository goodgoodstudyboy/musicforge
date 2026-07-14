from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class DeliveryRoutesPart003:
    def _handle_release_operations(self, method: str, release_id: str, tail: str) -> None:
        if tail == "/runbooks" or tail.startswith("/runbooks/"):
            self._handle_release_operations_runbooks(method, release_id, tail.removeprefix("/runbooks"))
            return
        if tail == "/signoff" or tail == "/signoff/reset":
            self._handle_release_operations_signoff(method, release_id, tail.removeprefix("/signoff"))
            return
        if tail == "/change-requests" or tail.startswith("/change-requests/"):
            self._handle_release_operations_change_requests(method, release_id, tail.removeprefix("/change-requests"))
            return
        if tail == "/archive/export" or tail == "/archive/export/zip" or tail == "/archive/verify" or tail == "/archive.zip":
            self._handle_release_operations_archive(method, release_id, tail.removeprefix("/archive"))
            return
        if tail == "/audit" or tail.startswith("/audit/") or tail == "/audit.zip":
            self._handle_release_operations_audit(method, release_id, tail.removeprefix("/audit"))
            return
        if tail == "/reviewer-pack" or tail.startswith("/reviewer-pack/") or tail == "/reviewer-pack.zip":
            self._handle_release_operations_reviewer_pack(method, release_id, tail.removeprefix("/reviewer-pack"))
            return
        if tail in {"", "/"}:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_json(self.release_operations_store.overview(release_id))
            return
        if tail == "/refresh":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.release_operations_store.refresh(release_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": operations_report_summary(report)})
            return
        if tail == "/export":
            if method == "GET":
                try:
                    manifest = self.release_operations_store.read_export_manifest(release_id)
                except FileNotFoundError:
                    self._send_json({"ok": True, "release_id": release_id, "manifest": {}, "summary": {"status": "missing"}})
                    return
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})})
                return
            if method == "POST":
                manifest = self.release_operations_store.export_operations(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/export/zip":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            zip_info = self.release_operations_store.build_zip(release_id, now=_utc_now())
            manifest = self.release_operations_store.read_export_manifest(release_id)
            self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
            return
        if tail == "/export.zip":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self.release_store.get_release(release_id)
            self._send_file(self.release_operations_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations.zip")
            return
        if tail == "/verify":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = verify_release_operations_package(
                self.release_operations_store.zip_path(release_id),
                strict=bool(payload.get("strict", False)),
                require_accepted=bool(payload.get("require_accepted", False)),
                require_submission_evidence=bool(payload.get("require_submission_evidence", False)),
            )
            write_release_operations_verification_report(report, self.release_operations_store.operations_dir(release_id) / "operations-verification-report.json")
            self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_verification_summary(report)})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Release Operations route not found.")

    def _handle_release_operations_signoff(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    signoff = self.release_operations_signoff_store.read_signoff(release_id, default={})
                    gate = self.release_operations_signoff_store.gate(release_id, {}, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=self.release_operations_store.build_report(release_id, persist=False)), "gate": gate})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    try:
                        signoff = self.release_operations_signoff_store.signoff(release_id, payload, now=_utc_now())
                    except ReleaseOperationsSignoffStateError as exc:
                        gate = self.release_operations_signoff_store.gate(release_id, payload, now=_utc_now())
                        self._send_json({"error": str(exc), "gate": gate}, status=HTTPStatus.CONFLICT)
                        return
                    self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=self.release_operations_store.build_report(release_id, persist=False))})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reset = self.release_operations_signoff_store.reset_signoff(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "signoff": reset, "summary": operations_signoff_summary(reset)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Signoff route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_operations_change_requests(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    rows = self.release_operations_signoff_store.list_change_requests(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "change_requests": rows, "summary": self.release_operations_signoff_store.change_request_summary(release_id)})
                    return
                if method == "POST":
                    item = self.release_operations_signoff_store.create_change_request(release_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Operations Change Request route not found.")
                return
            change_request_id = parts[0]
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.release_operations_signoff_store.get_change_request(release_id, change_request_id)
                self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)})
                return
            if len(parts) == 2 and parts[1] in {"submit", "approve", "reject", "cancel"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.release_operations_signoff_store.update_change_request_status(release_id, change_request_id, parts[1], self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Operations Change Request route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_operations_archive(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_signoff_store.export_archive(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_signoff_store.build_archive_zip(release_id, now=_utc_now())
                manifest = self.release_operations_signoff_store.read_archive_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_operations_archive_package(
                    self.release_operations_signoff_store.archive_zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                )
                write_release_operations_archive_verification_report(report, self.release_operations_signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_archive_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_signoff_store.archive_zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-archive.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Archive route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations_audit(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_audit_store.read_report(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": audit_summary(report) if report else {"status": "missing", "entry_count": 0}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_audit_store.refresh(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": audit_summary(report)})
                return
            if tail == "/entries":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                entries = self.release_operations_audit_store.entries(
                    release_id,
                    domain=query.get("domain", [None])[0],
                    risk=query.get("risk", [None])[0],
                    event_type=query.get("event_type", [None])[0],
                    limit=int(query.get("limit", ["200"])[0] or 200),
                )
                self._send_json({"ok": True, "release_id": release_id, "entries": entries, "summary": {"entry_count": len(entries)}})
                return
            if tail == "/graph":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "release_id": release_id, "graph": self.release_operations_audit_store.graph(release_id)})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_audit_store.export_audit(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_audit_store.build_zip(release_id, now=_utc_now())
                manifest = self.release_operations_audit_store.read_export_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_operations_audit_package(
                    self.release_operations_audit_store.zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_current=bool(payload.get("require_current", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_archive=bool(payload.get("require_archive", False)),
                )
                write_release_operations_audit_verification_report(report, self.release_operations_audit_store.verification_report_path(release_id))
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_audit_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_audit_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-audit.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Audit route not found.")
        except ReleaseOperationsAuditNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsAuditStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsAuditError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
