from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext
from song_agent.platform.contracts.documents import JsonDocument

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioPortalReviewRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_portal_review(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if action != "governance-attestation-portal-review":
            return False
        query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
        profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
        if len(parts) == 2:
            return self._send_portfolio_portal_review(method, portfolio_id, profile)
        subaction = parts[2] if len(parts) > 2 else ""
        if subaction == "pack" and self._dispatch_portfolio_portal_review_pack(method, parts, portfolio_id, profile):
            return True
        if subaction == "responses" and self._dispatch_portfolio_portal_review_responses(method, parts, portfolio_id, profile):
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Portfolio Governance Attestation Portal Review route not found.")
        return True

    def _send_portfolio_portal_review(self, method: str, portfolio_id: str, profile: str) -> bool:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        store = self.release_portfolio_governance_attestation_portal_review_store
        pack = store.read_pack(portfolio_id, profile=profile, default={})
        summary: JsonDocument = _interfaces_api_runtime.portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {"status": "missing", "profile": profile}
        if pack:
            summary["stale"] = store.pack_is_stale(portfolio_id, pack, profile=profile)
        self._send_json(
            {
                "ok": True,
                "portfolio_id": portfolio_id,
                "profile": profile,
                "review_pack": pack,
                "summary": summary,
                "responses": store.list_responses(portfolio_id, profile=profile),
            }
        )
        return True

    def _dispatch_portfolio_portal_review_pack(self, method: str, parts: list[str], portfolio_id: str, profile: str) -> bool:
        if len(parts) != 4:
            return False
        store = self.release_portfolio_governance_attestation_portal_review_store
        pack_action = parts[3]
        if pack_action in {"refresh", "export", "zip"}:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            payload = self._optional_json_body()
            payload.setdefault("profile", profile)
            if pack_action == "refresh":
                pack = store.refresh_pack(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "review_pack": pack, "summary": _interfaces_api_runtime.portfolio_governance_attestation_portal_review_pack_summary(pack)})
            elif pack_action == "export":
                manifest = store.export_pack(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "manifest": manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            else:
                zip_info = store.build_pack_zip(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "portfolio_id": portfolio_id, "zip": zip_info})
            return True
        if pack_action == "verify":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            payload = self._optional_json_body()
            active_profile = str(payload.get("profile") or profile)
            report = _interfaces_api_runtime.verify_release_portfolio_governance_attestation_portal_review_pack(
                store.pack_zip_path(portfolio_id, active_profile),
                strict=bool(payload.get("strict", False)),
                require_current=bool(payload.get("require_current", False)),
            )
            _interfaces_api_runtime.write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, store.pack_verification_report_path(portfolio_id, active_profile))
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
            return True
        return False

    def _dispatch_portfolio_portal_review_responses(self, method: str, parts: list[str], portfolio_id: str, profile: str) -> bool:
        store = self.release_portfolio_governance_attestation_portal_review_store
        if len(parts) == 3:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "responses": store.list_responses(portfolio_id, profile=profile)})
            return True
        if len(parts) == 4 and parts[3] == "import":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            payload = self._read_json_body()
            payload.setdefault("profile", profile)
            imported = store.import_response(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, **imported}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        response_id = parts[3] if len(parts) > 3 else ""
        if len(parts) == 4:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            response = store.get_response(portfolio_id, response_id, profile=profile)
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "response": response, "summary": _interfaces_api_runtime.portfolio_governance_attestation_portal_response_summary(response)})
            return True
        if len(parts) == 5 and parts[4] == "verify":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            report = store.verify_response(portfolio_id, response_id, profile=profile, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "portfolio_id": portfolio_id, "verification": report})
            return True
        if len(parts) == 5 and parts[4] == "create-change-request":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            result = store.create_change_request(portfolio_id, response_id, self._optional_json_body(), profile=profile, now=_interfaces_api_runtime._utc_now())
            status = _interfaces_api_runtime.HTTPStatus.OK if result.get("existing") else _interfaces_api_runtime.HTTPStatus.CREATED
            self._send_json({"ok": True, "portfolio_id": portfolio_id, **result}, status=status)
            return True
        return False
