from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioDownloadsRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_downloads(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if len(parts) != 2:
            return False
        if self._dispatch_portfolio_governance_downloads(method, portfolio_id, action):
            return True
        if self._dispatch_portfolio_attestation_downloads(method, portfolio_id, action):
            return True
        if self._dispatch_portfolio_acceptance_downloads(method, portfolio_id, action):
            return True
        return self._dispatch_portfolio_acknowledgement_download(method, portfolio_id, action)

    def _portfolio_download_allowed(self, method: str) -> bool:
        if method == "GET":
            return True
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        return False

    def _dispatch_portfolio_governance_downloads(self, method: str, portfolio_id: str, action: str) -> bool:
        if action == "governance-audit.zip":
            if not self._portfolio_download_allowed(method):
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(
                self.release_portfolio_governance_audit_store.zip_path(portfolio_id),
                "application/zip",
                filename=f"musicforge-{portfolio_id}-portfolio-governance-audit.zip",
            )
            return True
        if action == "governance-reviewer-pack.zip":
            if not self._portfolio_download_allowed(method):
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(
                self.release_portfolio_governance_reviewer_pack_store.zip_path(portfolio_id),
                "application/zip",
                filename=f"musicforge-{portfolio_id}-portfolio-governance-reviewer-pack.zip",
            )
            return True
        if action == "governance-final-board.zip":
            if not self._portfolio_download_allowed(method):
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(
                self.release_portfolio_governance_final_board_store.archive_zip_path(portfolio_id),
                "application/zip",
                filename=f"musicforge-{portfolio_id}-portfolio-governance-final-board-archive.zip",
            )
            return True
        if action == "governance-evidence-vault.zip":
            if not self._portfolio_download_allowed(method):
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(
                self.release_portfolio_governance_evidence_vault_store.zip_path(portfolio_id),
                "application/zip",
                filename=f"musicforge-{portfolio_id}-portfolio-governance-evidence-vault.zip",
            )
            return True
        return False

    def _dispatch_portfolio_attestation_downloads(self, method: str, portfolio_id: str, action: str) -> bool:
        if action not in {"governance-attestation.zip", "governance-attestation-registry.zip", "governance-attestation-portal.zip"}:
            return False
        if not self._portfolio_download_allowed(method):
            return True
        query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
        profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
        self.release_portfolio_audit_store.get_portfolio(portfolio_id)
        if action == "governance-attestation.zip":
            path = self.release_portfolio_governance_attestation_store.zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-public-attestation.zip"
        elif action == "governance-attestation-registry.zip":
            path = self.release_portfolio_governance_attestation_registry_store.zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-registry.zip"
        else:
            path = self.release_portfolio_governance_attestation_portal_store.zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-portal.zip"
        self._send_file(path, "application/zip", filename=filename)
        return True

    def _dispatch_portfolio_acceptance_downloads(self, method: str, portfolio_id: str, action: str) -> bool:
        if action not in {
            "governance-attestation-portal-review-pack.zip",
            "governance-attestation-accepted-evidence.zip",
            "governance-attestation-transparency.zip",
        }:
            return False
        if not self._portfolio_download_allowed(method):
            return True
        query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
        profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
        self.release_portfolio_governance_audit_store.portfolio_store.get_portfolio(portfolio_id)
        if action == "governance-attestation-portal-review-pack.zip":
            path = self.release_portfolio_governance_attestation_portal_review_store.pack_zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-portal-review-pack.zip"
        elif action == "governance-attestation-accepted-evidence.zip":
            path = self.release_portfolio_governance_attestation_accepted_evidence_store.zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-accepted-evidence.zip"
        else:
            path = self.release_portfolio_governance_attestation_transparency_store.zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency.zip"
        self._send_file(path, "application/zip", filename=filename)
        return True

    def _dispatch_portfolio_acknowledgement_download(self, method: str, portfolio_id: str, action: str) -> bool:
        if action not in {
            "governance-attestation-transparency-acknowledgement-pack.zip",
            "governance-attestation-transparency-acknowledgement-evidence.zip",
        }:
            return False
        if not self._portfolio_download_allowed(method):
            return True
        query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
        profile = str(query.get("profile", ["public_summary"])[0] or "public_summary")
        self.release_portfolio_governance_audit_store.portfolio_store.get_portfolio(portfolio_id)
        if action.endswith("pack.zip"):
            path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-pack.zip"
        else:
            path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_zip_path(portfolio_id, profile)
            filename = f"musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-evidence.zip"
        self._send_file(path, "application/zip", filename=filename)
        return True
