from __future__ import annotations

from song_agent.interfaces.api.route_contexts.program_ucc import ProgramUccRouteContext
from song_agent.platform.contracts.coercion import as_document as _as_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class ProgramUccCoreRoutes(ProgramUccRouteContext):
    def _dispatch_ucc_core(self, method: str, center_id: str, tail: str) -> bool:
        if tail in {"", "/"}:
            return self._send_ucc_center(method, center_id)
        if self._dispatch_ucc_package_action(method, center_id, tail):
            return True
        return self._dispatch_ucc_signoff_action(method, center_id, tail)

    def _send_ucc_center(self, method: str, center_id: str) -> bool:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        store = self.server.unified_command_center_store
        center = store.read_center(center_id)
        report = store.read_report(center_id) if store.report_path(center_id).exists() else {}
        inventory = _interfaces_api_runtime.read_json(store.inventory_path(center_id)) if store.inventory_path(center_id).exists() else {}
        readiness = _interfaces_api_runtime.read_json(store.readiness_path(center_id)) if store.readiness_path(center_id).exists() else {}
        gap_plan = _interfaces_api_runtime.read_json(store.gap_plan_path(center_id)) if store.gap_plan_path(center_id).exists() else {}
        runbook = _interfaces_api_runtime.read_json(store.runbook_path(center_id)) if store.runbook_path(center_id).exists() else {}
        self._send_json(
            {
                "ok": True,
                "center": center,
                "report": report,
                "inventory": inventory,
                "readiness": readiness,
                "gap_plan": gap_plan,
                "runbook": runbook,
                "summary": report.get("summary", {}) if report else {},
            }
        )
        return True

    def _dispatch_ucc_package_action(self, method: str, center_id: str, tail: str) -> bool:
        if tail not in {"/refresh", "/runbook", "/run-safe", "/export", "/zip", "/verify"}:
            return False
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        store = self.server.unified_command_center_store
        payload = self._optional_json_body()
        evidence = self._unified_command_center_evidence_from_payload(payload)
        if tail == "/refresh":
            report = store.refresh(center_id, evidence)
            self._send_json({"ok": report.get("status") == "ready", "center_id": center_id, "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
        elif tail == "/runbook":
            runbook = store.create_runbook(center_id, evidence)
            self._send_json({"ok": True, "center_id": center_id, "runbook": runbook, "summary": runbook.get("summary", {})})
        elif tail == "/run-safe":
            result = store.run_safe(center_id, evidence)
            summary = _as_document(result.get("summary"))
            self._send_json({"ok": summary.get("failed_count") == 0, "center_id": center_id, "runbook_result": result, "summary": summary})
        elif tail == "/export":
            result = store.export_package(center_id, evidence)
            self._send_json({"ok": result.get("status") == "ready", **result})
        elif tail == "/zip":
            result = store.build_zip(center_id, evidence)
            self._send_json({"ok": result.get("status") == "ready", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
        else:
            report = store.verify_zip(center_id, evidence=evidence, strict=bool(payload.get("strict", True)), require_ready=bool(payload.get("require_ready", False)))
            self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
        return True

    def _dispatch_ucc_signoff_action(self, method: str, center_id: str, tail: str) -> bool:
        store = self.server.unified_command_center_signoff_store
        if tail == "/signoff":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            signoff = store.signoff(center_id, self._optional_json_body())
            self._send_json({"ok": True, "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")})
            return True
        if tail == "/archive":
            if method == "GET":
                manifest = _interfaces_api_runtime.read_json(store.archive_manifest_path(center_id)) if store.archive_manifest_path(center_id).exists() else {}
                self._send_json({"ok": bool(manifest), "manifest": manifest, "summary": manifest.get("summary", {}) if manifest else {}})
                return True
            if method == "POST":
                manifest = store.export_archive(center_id)
                self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return True
        if tail == "/archive/zip":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return True
            result = store.build_archive_zip(center_id)
            self._send_json({"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
            return True
        return False
