from __future__ import annotations

from song_agent.interfaces.api.route_contexts.program_ucc import ProgramUccRouteContext
from song_agent.platform.contracts.coercion import as_document as _as_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class ProgramUccEvidence_DetailRoutes(ProgramUccRouteContext):
    def _dispatch_ucc_evidence_detail(self, method: str, center_id: str, tail: str) -> bool:
        if not tail.startswith("/evidence-reviews/"):
            return False
        review_tail = tail.removeprefix("/evidence-reviews/")
        review_parts = review_tail.split("/")
        review_id = review_parts[0]
        action = "/" + "/".join(review_parts[1:]) if len(review_parts) > 1 else ""
        if self._dispatch_ucc_evidence_review(method, center_id, review_id, action):
            return True
        if self._dispatch_ucc_evidence_responses(method, center_id, review_id, action):
            return True
        if self._dispatch_ucc_accepted_evidence(method, center_id, review_id, action):
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Unified Command Center Evidence Review route not found.")
        return True

    def _dispatch_ucc_evidence_review(self, method: str, center_id: str, review_id: str, action: str) -> bool:
        store = self.server.unified_command_center_evidence_review_store
        if action in {"", "/"}:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            review = store.get_review(center_id, review_id)
            replay = _as_document(review.get("replay_result"))
            source = _as_document(review.get("source"))
            self._send_json({"ok": True, "review": review, "summary": _as_document(replay.get("summary")), "status": replay.get("status") or source.get("status")})
            return True
        if action == "/download":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            self._send_file(store.zip_path(center_id, review_id), "application/zip", filename="musicforge-unified-command-center-evidence-review.zip")
            return True
        if action not in {"/refresh", "/replay", "/export", "/zip", "/verify"}:
            return False
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        payload = self._optional_json_body()
        if action == "/refresh":
            docs = store.refresh_review(center_id, review_id, payload)
            source = _as_document(docs.get("source"))
            self._send_json({"ok": True, "review": docs, "summary": {"review_id": review_id}, "status": source.get("status")})
        elif action == "/replay":
            replay = store.run_replay(center_id, review_id, payload)
            self._send_json({"ok": replay.get("status") == "passed", "replay_result": replay, "summary": replay.get("summary", {}), "status": replay.get("status")})
        elif action == "/export":
            result = store.export_review(center_id, review_id, payload)
            self._send_json({"ok": result.get("status") == "passed", **result})
        elif action == "/zip":
            result = store.build_zip(center_id, review_id, payload)
            self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
        else:
            report = store.verify_zip(center_id, review_id, payload)
            self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
        return True

    def _dispatch_ucc_evidence_responses(self, method: str, center_id: str, review_id: str, action: str) -> bool:
        store = self.server.unified_command_center_evidence_review_store
        if action == "/responses":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            responses = store.list_responses(center_id, review_id)
            self._send_json({"ok": True, "responses": responses, "summary": {"response_count": len(responses)}})
            return True
        if action == "/responses/import":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            response = store.import_response(center_id, review_id, self._read_json_body())
            self._send_json(
                {"ok": response.get("status") == "current", "response": response, "summary": {"response_id": response.get("response_id")}, "status": response.get("status")},
                status=_interfaces_api_runtime.HTTPStatus.CREATED,
            )
            return True
        if action.startswith("/responses/") and action.endswith("/accepted-evidence"):
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            response_id = action.split("/")[2]
            result = store.create_acceptance_evidence(center_id, review_id, response_id)
            self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence_id")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        return False

    def _dispatch_ucc_accepted_evidence(self, method: str, center_id: str, review_id: str, action: str) -> bool:
        if not action.startswith("/accepted-evidence/"):
            return False
        evidence_tail = action.removeprefix("/accepted-evidence/")
        evidence_parts = evidence_tail.split("/")
        evidence_id = evidence_parts[0]
        evidence_action = "/" + "/".join(evidence_parts[1:]) if len(evidence_parts) > 1 else ""
        store = self.server.unified_command_center_evidence_review_store
        if evidence_action == "/verify":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            report = store.verify_acceptance_evidence(center_id, review_id, evidence_id, self._optional_json_body())
            self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
            return True
        if evidence_action == "/download":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            self._send_file(store.accepted_evidence_zip_path(center_id, review_id, evidence_id), "application/zip", filename="musicforge-unified-command-center-evidence-review-acceptance.zip")
            return True
        return False
