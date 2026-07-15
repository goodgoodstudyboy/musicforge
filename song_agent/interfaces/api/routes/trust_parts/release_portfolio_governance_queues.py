from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesReleasePortfolioGovernanceQueues:
    def _handle_release_portfolio_governance_queues(self, method: str, path: str) -> None:
        prefix = "/api/release-portfolio-governance-queues"
        tail = path[len(prefix):]
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
                portfolio_id = str(query.get("portfolio_id", [""])[0] or "").strip() or None
                include_archived = str(query.get("include_archived", [""])[0]).lower() in {"1", "true", "yes"}
                queues = self.release_portfolio_governance_store.list_queues(portfolio_id=portfolio_id, include_archived=include_archived)
                self._send_json({"ok": True, "queues": queues, "summary": {"count": len(queues)}})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Portfolio Governance Queue route not found.")
                return
            queue_id = parts[0]
            action = parts[1] if len(parts) > 1 else ""
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.get_queue(queue_id)
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json(
                    {
                        "ok": True,
                        "queue": queue,
                        "summary": _interfaces_api_runtime.queue_summary(queue, execution),
                        "signoff_summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id),
                        "archive_summary": self.release_portfolio_governance_signoff_store.archive_summary(queue_id),
                        "change_request_summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id),
                    }
                )
                return
            if action == "plan" and len(parts) == 2:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_portfolio_governance_store.read_action_plan(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "action_plan": plan, "summary": {"item_count": len(plan.get("items", []) if isinstance(plan.get("items"), list) else [])}})
                return
            if action == "execution" and len(parts) == 2:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "execution_report": execution, "summary": execution.get("summary", {})})
                return
            if action == "manual-actions" and len(parts) == 2:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manual = self.release_portfolio_governance_store.read_manual_action_list(queue_id, default={})
                self._send_json({"ok": True, "queue_id": queue_id, "manual_action_list": manual, "summary": {"count": len(manual.get("items", []) if isinstance(manual.get("items"), list) else [])}})
                return
            if action == "run-safe" and len(parts) == 2:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.run_safe_actions(queue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                execution = self.release_portfolio_governance_store.read_execution_report(queue_id, default={})
                self._send_json({"ok": True, "queue": queue, "execution_report": execution, "summary": _interfaces_api_runtime.queue_summary(queue, execution)})
                return
            if action == "export" and len(parts) == 2:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_portfolio_governance_store.export_queue(queue_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "export" and len(parts) == 3 and parts[2] == "zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_portfolio_governance_store.build_zip(queue_id, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_portfolio_governance_store.read_export_manifest(queue_id)
                self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if action == "verify" and len(parts) == 2:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = _interfaces_api_runtime.verify_release_portfolio_governance_package(
                    self.release_portfolio_governance_store.zip_path(queue_id),
                    strict=bool(payload.get("strict", False)),
                    require_manual_actions=bool(payload.get("require_manual_actions", False)),
                    require_no_blocked=bool(payload.get("require_no_blocked", False)),
                )
                _interfaces_api_runtime.write_release_portfolio_governance_verification_report(report, self.release_portfolio_governance_store.verification_report_path(queue_id))
                self._send_json({"ok": True, "queue_id": queue_id, "verification": report, "summary": _interfaces_api_runtime.release_portfolio_governance_verification_summary(report)})
                return
            if action == "signoff" and len(parts) == 2:
                if method == "GET":
                    signoff = self.release_portfolio_governance_signoff_store.read_signoff(queue_id, default={})
                    gate = self.release_portfolio_governance_signoff_store.gate(queue_id, {}, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff), "gate": gate})
                    return
                if method == "POST":
                    signoff = self.release_portfolio_governance_signoff_store.signoff(queue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "signoff" and len(parts) == 3 and parts[2] == "reset":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                signoff = self.release_portfolio_governance_signoff_store.reset_signoff(queue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "queue_id": queue_id, "signoff": signoff, "summary": self.release_portfolio_governance_signoff_store.signoff_summary(queue_id, signoff=signoff)})
                return
            if action == "change-requests":
                if len(parts) == 2:
                    if method == "GET":
                        rows = self.release_portfolio_governance_signoff_store.list_change_requests(queue_id)
                        self._send_json({"ok": True, "queue_id": queue_id, "change_requests": rows, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)})
                        return
                    if method == "POST":
                        item = self.release_portfolio_governance_signoff_store.create_change_request(queue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                        self._send_json({"ok": True, "queue_id": queue_id, "change_request": item, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                change_request_id = parts[2]
                if len(parts) == 3 and method == "GET":
                    item = self.release_portfolio_governance_signoff_store.get_change_request(queue_id, change_request_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "change_request": item})
                    return
                if len(parts) == 4 and method == "POST" and parts[3] in {"approve", "reject", "archive"}:
                    item = self.release_portfolio_governance_signoff_store.update_change_request_status(queue_id, change_request_id, parts[3], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "change_request": item, "summary": self.release_portfolio_governance_signoff_store.change_request_summary(queue_id)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Portfolio Governance Change Request route not found.")
                return
            if action == "archive.zip" and len(parts) == 2:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_governance_store.get_queue(queue_id)
                self._send_file(self.release_portfolio_governance_signoff_store.archive_zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-portfolio-governance-archive.zip")
                return
            if action == "archive" and len(parts) >= 2:
                if len(parts) == 2 and method == "GET":
                    manifest = self.release_portfolio_governance_signoff_store.read_archive_manifest(queue_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": self.release_portfolio_governance_signoff_store.archive_summary(queue_id)})
                    return
                if len(parts) == 3 and parts[2] == "export":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.release_portfolio_governance_signoff_store.export_archive(queue_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "queue_id": queue_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if len(parts) == 3 and parts[2] == "zip":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.release_portfolio_governance_signoff_store.build_archive_zip(queue_id, now=_interfaces_api_runtime._utc_now())
                    manifest = self.release_portfolio_governance_signoff_store.read_archive_manifest(queue_id)
                    self._send_json({"ok": True, "queue_id": queue_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                    return
                if len(parts) == 3 and parts[2] == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = _interfaces_api_runtime.verify_release_portfolio_governance_archive_package(
                        self.release_portfolio_governance_signoff_store.archive_zip_path(queue_id),
                        strict=bool(payload.get("strict", False)),
                        require_signed=bool(payload.get("require_signed", False)),
                        require_no_force=bool(payload.get("require_no_force", False)),
                    )
                    _interfaces_api_runtime.write_release_portfolio_governance_archive_verification_report(report, self.release_portfolio_governance_signoff_store.archive_verification_report_path(queue_id))
                    self._send_json({"ok": True, "queue_id": queue_id, "verification": report, "summary": _interfaces_api_runtime.release_portfolio_governance_archive_verification_summary(report)})
                    return
            if action == "download" and len(parts) == 2:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_portfolio_governance_store.get_queue(queue_id)
                self._send_file(self.release_portfolio_governance_store.zip_path(queue_id), "application/zip", filename=f"musicforge-{queue_id}-portfolio-governance.zip")
                return
            if action == "archive" and len(parts) == 2:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_portfolio_governance_store.archive(queue_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "queue": queue, "summary": _interfaces_api_runtime.queue_summary(queue)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Portfolio Governance Queue route not found.")
        except _interfaces_api_runtime.ReleasePortfolioGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
