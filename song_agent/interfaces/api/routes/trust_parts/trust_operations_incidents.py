from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesTrustOperationsIncidents:
    def _handle_trust_operations_incidents(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                board = {}
                try:
                    board = self.trust_operations_incident_store.read_board(hub_id)
                except _interfaces_api_runtime.TrustOperationsIncidentNotFoundError:
                    pass
                self._send_json({"ok": True, "hub_id": hub_id, "incident_board": board, "incidents": self.trust_operations_incident_store.list_incidents(hub_id)})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.trust_operations_incident_store.refresh_board(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.trust_operations_incident_store.export_board(hub_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.trust_operations_incident_store.build_zip(hub_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.trust_operations_incident_store.verify_zip(hub_id, self._optional_json_body())
                _interfaces_api_runtime.write_trust_operations_hub_incident_verification_report(report, self.trust_operations_incident_store.verification_report_path(hub_id))
                self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                return
            parts = [part for part in tail.split("/") if part]
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Incident route not found.")
                return
            incident_id = _interfaces_api_runtime.unquote(parts[0])
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                incident = self.trust_operations_incident_store.read_incident(hub_id, incident_id)
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            action = parts[1]
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            if action == "triage":
                incident = self.trust_operations_incident_store.triage_incident(hub_id, incident_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            if action == "plan":
                plan = self.trust_operations_incident_store.create_plan(hub_id, incident_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "plan": plan}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "evidence":
                evidence = self.trust_operations_incident_store.add_evidence(hub_id, incident_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "evidence": evidence}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "verify-fix":
                result = self.trust_operations_incident_store.verify_fix(hub_id, incident_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": result.get("status") == "passed", "hub_id": hub_id, "result": result})
                return
            if action == "close":
                closeout = self.trust_operations_incident_store.close_incident(hub_id, incident_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "closeout": closeout})
                return
            if action == "archive":
                incident = self.trust_operations_incident_store.archive_incident(hub_id, incident_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "incident": incident})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Incident route not found.")
        except _interfaces_api_runtime.TrustOperationsIncidentNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.TrustOperationsIncidentStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
