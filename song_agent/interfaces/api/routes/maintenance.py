from __future__ import annotations

from http import HTTPStatus

from song_agent.application.maintenance import MaintenanceServerPort
from song_agent.application.maintenance import EvidencePolicyGateError, GaReadinessCommand
from song_agent.interfaces.api.routes.maintenance_operations import MaintenanceOperationsRoutes
from song_agent.platform.contracts.coercion import as_document


class MaintenanceRoutes(MaintenanceOperationsRoutes):
    server: MaintenanceServerPort

    def _handle_ga_route(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        report = self.server.maintenance_application.ga_status()
        self._send_json(
            {
                "ok": report.get("status") != "blocked",
                "report": report,
                "summary": report.get("summary", {}),
            }
        )

    def _handle_ga_check_route(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self.server.maintenance_application.run_ga_check(GaReadinessCommand.from_document(self._optional_json_body()))
        except (EvidencePolicyGateError, OSError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {
                "ok": report.get("status") != "blocked",
                "report": report,
                "summary": report.get("summary", {}),
            }
        )

    def _handle_docs_index_route(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        result = self.server.maintenance_application.docs_index()
        self._send_json({"ok": True, **result})

    def _handle_maintenance_route(self, method: str, path: str) -> None:
        application = self.server.maintenance_application
        if path == "/api/maintenance/status":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            status = application.status()
            backups = as_document(status.get("backups"))
            self._send_json(
                {
                    "ok": status.get("status") != "blocked",
                    "status": status,
                    "summary": {
                        "status": status.get("status"),
                        "backup_count": backups.get("count"),
                    },
                }
            )
            return
        if path == "/api/maintenance/backups":
            self._handle_backup_collection(method)
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[:3] == ["api", "maintenance", "backups"]:
            self._handle_backup_route(method, parts)
            return
        if path == "/api/maintenance/upgrade/preflight":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = application.run_upgrade_preflight(
                target_version=(str(payload["target_version"]) if payload.get("target_version") else None),
                require_verified_backup=bool(payload.get("require_verified_backup", False)),
                allow_dirty=bool(payload.get("allow_dirty", False)),
            )
            self._send_json(
                {
                    "ok": report.get("status") != "blocked",
                    "preflight": report,
                    "summary": report.get("summary", {}),
                },
                status=HTTPStatus.CREATED,
            )
            return
        if path == "/api/maintenance/migrations":
            if method == "GET":
                self._send_json({"ok": True, **application.migration_overview()})
                return
            if method == "POST":
                payload = self._optional_json_body()
                result = application.run_migrations(require_backup=bool(payload.get("require_backup", False)))
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if len(parts) >= 3 and parts[:3] == ["api", "maintenance", "checks"]:
            self._handle_maintenance_check_route(method, parts)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Maintenance route not found.")
