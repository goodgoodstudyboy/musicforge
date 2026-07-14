from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustRoutesPart002:
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
