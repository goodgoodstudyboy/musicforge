from __future__ import annotations
from song_agent.interfaces.api.route_contexts.core import CoreRouteContext
import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class MaintenanceRoutes(CoreRouteContext):
    def _handle_ga_route(self, method: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        from song_agent.domains.trust.ga_readiness import build_ga_readiness_report

        report = build_ga_readiness_report(repo_root=_interfaces_api_runtime.Path.cwd())
        self._send_json({"ok": report.get("status") != "blocked", "report": report, "summary": report.get("summary", {})})

    def _handle_ga_check_route(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        from song_agent.domains.trust.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
        from song_agent.release_check.runner import run_release_check_matrix

        payload = self._optional_json_body()
        policy_id = str(payload.get("policy") or "").strip() or None
        evidence_manifest = None
        if policy_id:
            try:
                from song_agent.application.evidence_policy_gate import resolve_workspace_evidence_manifest

                evidence_manifest = resolve_workspace_evidence_manifest(
                    self.server.release_store.root.parent,
                    manifest_id=payload.get("evidence_manifest_id"),
                    manifest=payload.get("evidence_manifest"),
                )
            except Exception as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
        report = build_ga_readiness_report(
            repo_root=_interfaces_api_runtime.Path.cwd(),
            policy=policy_id,
            evidence_manifest_path=evidence_manifest,
            strict=bool(payload.get("strict", False)),
            allow_dirty=bool(payload.get("allow_dirty", False)),
            require_manual_acceptance=bool(payload.get("require_manual_acceptance", False)),
            require_audio=bool(payload.get("require_audio", False)),
            require_audio_campaign=bool(payload.get("require_audio_campaign", False) or payload.get("audio_campaign_id")),
            audio_campaign_id=payload.get("audio_campaign_id"),
            audio_campaign_archive_zip_path=payload.get("audio_campaign_archive_zip_path") or payload.get("audio_campaign_archive"),
            audio_campaign_archive_verification_report_path=payload.get("audio_campaign_archive_verification_report_path") or payload.get("audio_campaign_archive_verification_report"),
            require_final_readiness=bool(payload.get("require_final_readiness", False)),
            final_handoff_verification_report_path=payload.get("final_handoff_verification_report_path"),
            release_check_latest_report_path=payload.get("release_check_latest_report_path"),
            release_check_ga_report_path=payload.get("release_check_ga_report_path"),
            run_release_checks=bool(payload.get("run_release_checks", False)),
            skip_tests=bool(payload.get("skip_tests", True)),
            release_check_executor=run_release_check_matrix,
        )
        write_ga_readiness_report(report)
        self._send_json({"ok": report.get("status") != "blocked", "report": report, "summary": report.get("summary", {})})

    def _handle_docs_index_route(self, method: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        from song_agent.domains.trust.ga_readiness import REQUIRED_DOCS

        docs = []
        for rel in REQUIRED_DOCS:
            path = _interfaces_api_runtime.Path(rel)
            docs.append(
                {
                    "path": rel,
                    "exists": path.exists(),
                    "title": path.stem.replace("_", " ").replace("-", " ").title(),
                }
            )
        self._send_json({"ok": True, "docs": docs, "summary": {"required_count": len(REQUIRED_DOCS), "present_count": sum(1 for item in docs if item["exists"])}})

    def _handle_maintenance_route(self, method: str, path: str) -> None:
        from song_agent.domains.creation import lts_maintenance

        store = lts_maintenance.LTSMaintenanceStore(repo_root=_interfaces_api_runtime.Path.cwd())
        if path == "/api/maintenance/status":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            status = store.status()
            self._send_json({"ok": status.get("status") != "blocked", "status": status, "summary": {"status": status.get("status"), "backup_count": status.get("backups", {}).get("count")}})
            return
        if path == "/api/maintenance/backups":
            if method == "GET":
                backups = store.backups.list_backups()
                self._send_json({"ok": True, "backups": backups, "summary": {"count": len(backups)}})
                return
            if method == "POST":
                payload = self._optional_json_body()
                result = store.backups.create_backup(mode=str(payload.get("mode") or "workspace"))
                ok = result.get("verification", {}).get("status") == "passed"
                self._send_json({"ok": ok, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED if ok else _interfaces_api_runtime.HTTPStatus.CONFLICT)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "maintenance" and parts[2] == "backups":
            if len(parts) < 4:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Backup id required.")
                return
            backup_id = parts[3]
            tail = "/".join(parts[4:])
            if not tail and method == "GET":
                self._send_json({"ok": True, **store.backups.read_backup(backup_id)})
                return
            if tail == "verify" and method == "POST":
                report = store.backups.verify_backup(backup_id)
                self._send_json({"ok": report.get("status") == "passed", "backup_id": backup_id, "verification": report, "summary": report.get("summary", {})})
                return
            if tail == "download" and method == "GET":
                self._send_file(store.backups.backup_zip_path(backup_id), "application/zip")
                return
            if tail == "restore-plan" and method == "POST":
                payload = self._read_json_body()
                plan = store.backups.restore_plan(backup_id=backup_id, target=_interfaces_api_runtime.Path(str(payload.get("target") or "")))
                self._send_json({"ok": plan.get("status") == "ready", "restore_plan": plan})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if path == "/api/maintenance/upgrade/preflight":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = store.run_upgrade_preflight(
                target_version=str(payload.get("target_version") or _interfaces_api_runtime.__version__),
                require_verified_backup=bool(payload.get("require_verified_backup", False)),
                allow_dirty=bool(payload.get("allow_dirty", False)),
            )
            self._send_json({"ok": report.get("status") != "blocked", "preflight": report, "summary": report.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        if path == "/api/maintenance/migrations":
            if method == "GET":
                self._send_json({"ok": True, "migration": store.migration_status(), "plan": store.migration_plan()})
                return
            if method == "POST":
                payload = self._optional_json_body()
                result = store.run_migrations(require_backup=bool(payload.get("require_backup", False)))
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if path == "/api/maintenance/checks":
            if method == "GET":
                runs = store.list_check_runs()
                self._send_json({"ok": True, "runs": runs, "profiles": ["daily", "emergency", "release", "weekly"], "summary": {"count": len(runs)}})
                return
            if method == "POST":
                payload = self._optional_json_body()
                report = store.run_check(profile=str(payload.get("profile") or "daily"))
                self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": {"status": report.get("status")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if len(parts) == 4 and parts[:3] == ["api", "maintenance", "checks"] and method == "GET":
            report = _interfaces_api_runtime.read_json(store.check_runs_dir / parts[3] / "maintenance-check-report.json")
            self._send_json({"ok": True, "report": report})
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Maintenance route not found.")
