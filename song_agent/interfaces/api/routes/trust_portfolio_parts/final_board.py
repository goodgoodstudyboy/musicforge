from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext
from song_agent.platform.contracts.documents import JsonDocument

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioFinalBoardRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_final_board(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if action != "governance-final-board":
            return False
        if len(parts) == 2:
            return self._send_portfolio_final_board(method, portfolio_id)
        subaction = parts[2] if len(parts) > 2 else ""
        if self._dispatch_portfolio_final_board_report(method, parts, portfolio_id, subaction):
            return True
        if self._dispatch_portfolio_final_board_signoff(method, parts, portfolio_id, subaction):
            return True
        if self._dispatch_portfolio_final_board_changes(method, parts, portfolio_id, subaction):
            return True
        if self._dispatch_portfolio_final_board_archive(method, parts, portfolio_id, subaction):
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Portfolio Governance Final Board route not found.")
        return True

    def _send_portfolio_final_board(self, method: str, portfolio_id: str) -> bool:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        store = self.release_portfolio_governance_final_board_store
        report = store.read_report(portfolio_id, default={})
        signoff = store.read_signoff(portfolio_id, default={})
        stale = store.report_is_stale(portfolio_id, report) if report else False
        summary: JsonDocument = _interfaces_api_runtime.sanitize_metadata(
            _interfaces_api_runtime.portfolio_governance_final_board_summary(report) if report else {"status": "missing"}
        )
        summary["stale"] = stale
        self._send_json(
            {
                "ok": True,
                "portfolio_id": portfolio_id,
                "report": report,
                "signoff": signoff,
                "signoff_summary": store.signoff_summary(portfolio_id, signoff=signoff) if signoff else _interfaces_api_runtime.portfolio_governance_final_board_signoff_summary(signoff),
                "reviewer_responses": store.list_reviewer_responses(portfolio_id),
                "change_requests": store.list_change_requests(portfolio_id),
                "verification": _interfaces_api_runtime.read_json(store.verification_report_path(portfolio_id)) if store.verification_report_path(portfolio_id).exists() else {},
                "summary": summary,
                "stale": stale,
            }
        )
        return True

    def _dispatch_portfolio_final_board_report(self, method: str, parts: list[str], portfolio_id: str, subaction: str) -> bool:
        store = self.release_portfolio_governance_final_board_store
        if subaction == "refresh" and len(parts) == 3:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            report = store.refresh_report(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "report": report, "summary": _interfaces_api_runtime.portfolio_governance_final_board_summary(report)})
            return True
        if subaction == "reviewer-responses" and len(parts) == 3:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            responses = store.list_reviewer_responses(portfolio_id)
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "reviewer_responses": responses, "summary": {"count": len(responses)}})
            return True
        if subaction == "reviewer-responses" and len(parts) == 4 and parts[3] == "import":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            response = store.import_reviewer_response(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            report = store.refresh_report(portfolio_id, now=_interfaces_api_runtime._utc_now())
            self._send_json(
                {"ok": True, "portfolio_id": portfolio_id, "response": response, "report": report, "summary": _interfaces_api_runtime.portfolio_governance_final_board_summary(report)},
                status=_interfaces_api_runtime.HTTPStatus.CREATED,
            )
            return True
        return False

    def _dispatch_portfolio_final_board_signoff(self, method: str, parts: list[str], portfolio_id: str, subaction: str) -> bool:
        if subaction != "signoff":
            return False
        store = self.release_portfolio_governance_final_board_store
        if len(parts) == 3:
            if method == "GET":
                signoff = store.read_signoff(portfolio_id, default={})
                report = store.read_report(portfolio_id, default={})
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": signoff, "summary": store.signoff_summary(portfolio_id, signoff=signoff), "report_summary": _interfaces_api_runtime.portfolio_governance_final_board_summary(report)})
                return True
            if method == "POST":
                signoff = store.signoff(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": signoff, "summary": store.signoff_summary(portfolio_id, signoff=signoff)})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        if len(parts) == 4 and parts[3] == "reset":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            reset = store.reset_signoff(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "signoff": reset, "summary": store.signoff_summary(portfolio_id, signoff=reset)})
            return True
        return False

    def _dispatch_portfolio_final_board_changes(self, method: str, parts: list[str], portfolio_id: str, subaction: str) -> bool:
        if subaction != "change-requests":
            return False
        store = self.release_portfolio_governance_final_board_store
        if len(parts) == 3:
            if method == "GET":
                items = store.list_change_requests(portfolio_id)
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_requests": items, "summary": {"count": len(items)}})
                return True
            if method == "POST":
                item = store.create_change_request(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_request": item}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        if len(parts) == 5 and parts[4] in {"approve", "reject"}:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            item = store.update_change_request_status(portfolio_id, parts[3], parts[4], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "change_request": item})
            return True
        return False

    def _dispatch_portfolio_final_board_archive(self, method: str, parts: list[str], portfolio_id: str, subaction: str) -> bool:
        if subaction != "archive" or len(parts) != 4:
            return False
        store = self.release_portfolio_governance_final_board_store
        archive_action = parts[3]
        if archive_action == "export":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            manifest = store.export_archive(portfolio_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest, "summary": manifest.get("final_board_signoff", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        if archive_action == "zip":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            zip_info = store.build_archive_zip(portfolio_id, now=_interfaces_api_runtime._utc_now())
            manifest = store.read_export_manifest(portfolio_id)
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info, "summary": manifest.get("final_board_signoff", {})})
            return True
        if archive_action == "verify":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            payload = self._optional_json_body()
            report = _interfaces_api_runtime.verify_release_portfolio_governance_final_board_package(
                store.archive_zip_path(portfolio_id),
                strict=bool(payload.get("strict", False)),
                require_signed=bool(payload.get("require_signed", False)),
                require_reviewer_pack=bool(payload.get("require_reviewer_pack", False)),
                require_audit=bool(payload.get("require_audit", False)),
                require_archives=bool(payload.get("require_archives", False)),
                require_reviewer_response=bool(payload.get("require_reviewer_response", False)),
                require_no_force=bool(payload.get("require_no_force", False)),
                require_reset_cr_causality=bool(payload.get("require_reset_cr_causality", False)),
            )
            _interfaces_api_runtime.write_release_portfolio_governance_final_board_verification_report(report, store.verification_report_path(portfolio_id))
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report, "summary": _interfaces_api_runtime.release_portfolio_governance_final_board_verification_summary(report)})
            return True
        return False
