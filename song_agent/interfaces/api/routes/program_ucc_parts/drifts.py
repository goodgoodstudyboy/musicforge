from __future__ import annotations

from song_agent.interfaces.api.route_contexts.program_ucc import ProgramUccRouteContext
from song_agent.platform.contracts.coercion import as_document, as_int

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class ProgramUccDriftsRoutes(ProgramUccRouteContext):
    def _dispatch_ucc_drifts(self, method: str, center_id: str, tail: str) -> bool:
        if tail == "/drift-responses":
            return self._dispatch_ucc_drift_collection(method, center_id)
        if not tail.startswith("/drift-responses/"):
            return False
        response_tail = tail.removeprefix("/drift-responses/")
        response_parts = response_tail.split("/")
        response_id = response_parts[0]
        action = "/" + "/".join(response_parts[1:]) if len(response_parts) > 1 else ""
        if self._dispatch_ucc_drift_response_state(method, center_id, response_id, action):
            return True
        if self._dispatch_ucc_drift_response_package(method, center_id, response_id, action):
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Unified Command Center Drift Response route not found.")
        return True

    def _dispatch_ucc_drift_collection(self, method: str, center_id: str) -> bool:
        store = self.server.unified_command_center_drift_response_store
        if method == "GET":
            responses = store.list_responses(center_id)
            self._send_json({"ok": True, "responses": responses, "summary": {"response_count": len(responses)}})
            return True
        if method == "POST":
            result = store.create_response(center_id, self._optional_json_body())
            case = as_document(result.get("case"))
            self._send_json({"ok": True, **result, "summary": {"response_id": case.get("response_id")}, "status": case.get("status")}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        return True

    def _dispatch_ucc_drift_response_state(self, method: str, center_id: str, response_id: str, action: str) -> bool:
        store = self.server.unified_command_center_drift_response_store
        if action in {"", "/"}:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            response = store.read_response(center_id, response_id)
            state = as_document(response.get("closeout")) or as_document(response.get("case"))
            self._send_json({"ok": True, "response": response, "summary": state.get("summary", {}), "status": state.get("status")})
            return True
        if action not in {"/run-safe", "/bind-cr", "/bind-recheck", "/closeout"}:
            return False
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        payload = self._optional_json_body()
        if action == "/run-safe":
            result = store.run_safe(center_id, response_id, payload)
            summary = as_document(result.get("summary"))
            failed_count = as_int(summary.get("failed_count") or 0)
            self._send_json({"ok": failed_count == 0, "action_results": result, "summary": summary, "status": "passed" if failed_count == 0 else "failed"})
        elif action == "/bind-cr":
            result = store.bind_change_request(center_id, response_id, payload)
            self._send_json({"ok": True, "change_request_bindings": result, "summary": result.get("summary", {}), "status": "passed"})
        elif action == "/bind-recheck":
            result = store.bind_recheck(center_id, response_id, payload)
            self._send_json({"ok": result.get("status") == "passed", "recheck": result, "summary": result.get("summary", {}), "status": result.get("status")})
        else:
            result = store.closeout(center_id, response_id, payload)
            self._send_json({"ok": result.get("status") == "closed", "closeout": result, "summary": result.get("summary", {}), "status": result.get("status")})
        return True

    def _dispatch_ucc_drift_response_package(self, method: str, center_id: str, response_id: str, action: str) -> bool:
        if action not in {"/export", "/zip", "/verify", "/download"}:
            return False
        store = self.server.unified_command_center_drift_response_store
        if action == "/download":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            self._send_file(store.zip_path(center_id, response_id), "application/zip", filename="musicforge-unified-command-center-drift-response.zip")
            return True
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        payload = self._optional_json_body()
        if action == "/export":
            result = store.export_package(center_id, response_id, payload)
            self._send_json({"ok": result.get("status") == "closed", **result})
        elif action == "/zip":
            result = store.build_zip(center_id, response_id, payload)
            self._send_json({"ok": result.get("status") == "closed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
        else:
            report = store.verify_package(center_id, response_id, payload)
            self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
        return True
