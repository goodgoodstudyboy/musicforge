from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from song_agent.application.maintenance import MaintenanceServerPort
from song_agent.interfaces.api.route_contexts.core import CoreRouteContext
from song_agent.platform.contracts.coercion import as_document
from song_agent.platform.contracts.documents import normalize_json_value


class MaintenanceOperationsRoutes(CoreRouteContext):
    server: MaintenanceServerPort

    def _handle_backup_collection(self, method: str) -> None:
        application = self.server.maintenance_application
        if method == "GET":
            backup_rows = application.list_backups()
            self._send_json({"ok": True, "backups": normalize_json_value(backup_rows), "summary": {"count": len(backup_rows)}})
            return
        if method == "POST":
            payload = self._optional_json_body()
            result = application.create_backup(str(payload.get("mode") or "workspace"))
            ok = as_document(result.get("verification")).get("status") == "passed"
            self._send_json({"ok": ok, **result}, status=HTTPStatus.CREATED if ok else HTTPStatus.CONFLICT)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_backup_route(self, method: str, parts: list[str]) -> None:
        if len(parts) < 4:
            self._send_error(HTTPStatus.NOT_FOUND, "Backup id required.")
            return
        application = self.server.maintenance_application
        backup_id = parts[3]
        tail = "/".join(parts[4:])
        if not tail and method == "GET":
            self._send_json({"ok": True, **application.read_backup(backup_id)})
            return
        if tail == "verify" and method == "POST":
            report = application.verify_backup(backup_id)
            self._send_json({"ok": report.get("status") == "passed", "backup_id": backup_id, "verification": report, "summary": report.get("summary", {})})
            return
        if tail == "download" and method == "GET":
            self._send_file(application.backup_zip_path(backup_id), "application/zip")
            return
        if tail == "restore-plan" and method == "POST":
            payload = self._read_json_body()
            plan = application.restore_plan(backup_id=backup_id, zip_path=None, target=Path(str(payload.get("target") or "")))
            self._send_json({"ok": plan.get("status") == "ready", "restore_plan": plan})
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_maintenance_check_route(self, method: str, parts: list[str]) -> None:
        application = self.server.maintenance_application
        if len(parts) == 3:
            if method == "GET":
                runs = application.list_check_runs()
                self._send_json({"ok": True, "runs": normalize_json_value(runs), "profiles": ["daily", "emergency", "release", "weekly"], "summary": {"count": len(runs)}})
                return
            if method == "POST":
                report = application.run_check(str(self._optional_json_body().get("profile") or "daily"))
                self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": {"status": report.get("status")}}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if len(parts) == 4:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_json({"ok": True, "report": application.read_check(parts[3])})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Maintenance check not found.")
