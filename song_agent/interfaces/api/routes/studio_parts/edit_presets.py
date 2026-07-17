from __future__ import annotations

from song_agent.platform.contracts.coercion import as_list as _as_list

from typing import Any as _InterfaceType

from song_agent.interfaces.api.route_contexts.studio import StudioRouteContext

from song_agent.platform.contracts.documents import ImplementationDocument

from typing import Any


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioRoutesEditPresets(StudioRouteContext):
    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PATCH(self) -> None:
        self._handle_request("PATCH")

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def store(self) -> _InterfaceType:
        return self.server.job_store

    @property
    def human_review_pack_store(self) -> _InterfaceType:
        return self.server.human_review_pack_store

    @property
    def edit_preset_store(self) -> _InterfaceType:
        return self.server.edit_preset_store

    @property
    def auth_config(self) -> _InterfaceType:
        return self.server.auth_config

    def _handle_edit_presets_root(self, method: str) -> None:
        if method == "GET":
            self._send_json(self.edit_preset_store.to_response())
            return
        if method == "POST":
            try:
                preset = self.edit_preset_store.save_preset(self._read_json_body())
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_edit_preset_route(self, method: str, preset_id: str, tail: str) -> None:
        if tail == "":
            if method == "GET":
                try:
                    preset = self.edit_preset_store.get_preset(preset_id)
                except (FileNotFoundError, ValueError):
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Edit preset not found.")
                    return
                self._send_json({"preset": preset.to_dict()})
                return
            if method == "POST":
                try:
                    preset = self.edit_preset_store.save_preset(self._read_json_body(), preset_id=preset_id)
                except ValueError as exc:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.edit_preset_store.delete_preset(preset_id)
            except PermissionError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return
            except (FileNotFoundError, ValueError):
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Edit preset not found.")
                return
            self._send_json({"ok": True, **self.edit_preset_store.to_response()})
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Edit preset route not found.")

    def _handle_edit_presets_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self.edit_preset_store.reset()
        self._send_json({"ok": True, **self.edit_preset_store.to_response()})

    def _get_or_refresh_delivery_qa(self, project_id: str, *, refresh: bool) -> ImplementationDocument:
        project_dir = self.project_store.project_dir(project_id)
        if not refresh:
            existing = self.project_store.read_delivery_qa(project_id, default={})
            if existing:
                try:
                    document = self.project_store.sync_project(project_id, self.store.get_job)
                except FileNotFoundError:
                    document = self.project_store.get_project(project_id)
                project_export = self.project_store.project_export_snapshot(project_id)
                try:
                    manifest = _interfaces_api_runtime.read_final_export_manifest(project_dir)
                except FileNotFoundError:
                    manifest = {}
                current_hash = _interfaces_api_runtime.delivery_qa_source_hash(project_id=project_id, project_document=document, project_dir=project_dir, project_export=project_export, final_export_manifest=manifest)
                if str(existing.get("source_hash") or "") != current_hash:
                    return _interfaces_api_runtime.mark_delivery_qa_stale(existing, current_source_hash=current_hash)
                return existing
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            document = self.project_store.get_project(project_id)
        project_export = self.project_store.project_export_snapshot(project_id)
        try:
            manifest = _interfaces_api_runtime.read_final_export_manifest(project_dir)
        except FileNotFoundError:
            manifest = {}
        report = _interfaces_api_runtime.build_delivery_qa_report(
            project_id=project_id,
            project_document=document,
            project_dir=project_dir,
            project_export=project_export,
            final_export_manifest=manifest,
            now=_interfaces_api_runtime._utc_now(),
        )
        return self.project_store.write_delivery_qa(project_id, report, now=_interfaces_api_runtime._utc_now())

    def _set_final_version_with_gate(self, project_id: str, version_id: str, *, force: bool) -> tuple[Any, Any]:
        document = self.project_store.get_project(project_id)
        version = next((version for version in document.versions if version.version_id == version_id), None)
        if version is None:
            raise FileNotFoundError(version_id)
        if version.status != "completed":
            raise ValueError("Only completed versions can be marked final.")
        result = self._evaluate_project_version(project_id, version)
        self.project_store.update_version_quality_gate(project_id, version.version_id, result)
        if result.status not in {"passed", "warning"} and not force:
            self.project_store.append_event(
                project_id,
                "final_version_gate_failed",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
            raise PermissionError(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": result.to_dict(),
                }
            )
        document = self.project_store.set_final_version(project_id, version.version_id)
        if force and result.status not in {"passed", "warning"}:
            self.project_store.append_event(
                project_id,
                "final_version_force_set",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
        return document, result

    def _review_sprint_response(
        self,
        sprint_store: _InterfaceType,
        task_store: _InterfaceType,
        sprint: Any,
        *,
        include_events: bool = False,
    ) -> ImplementationDocument:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
        action_queue_summary_data = self._review_sprint_action_queue_summary(sprint_store, sprint)
        closeout_report = sprint_store.read_closeout_report(sprint.sprint_id, default={})
        signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
        response = {
            "ok": True,
            "sprint": sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": _interfaces_api_runtime.recommendation_report_summary(recommendation_report),
            "judge_summary": judge_summary_data,
            "action_queue_summary": action_queue_summary_data,
            "metrics_summary": self._review_sprint_metrics_summary(sprint_store, sprint),
            "closeout_report": closeout_report,
            "closeout_summary": _interfaces_api_runtime.closeout_report_summary(closeout_report),
            "signoff": signoff,
            "signoff_summary": _interfaces_api_runtime.signoff_summary(signoff),
            "export_summary": _interfaces_api_runtime.review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, action_queue_summary_data, judge_summary_data),
            "tasks": self._review_sprint_task_items(task_store, sprint),
        }
        if include_events:
            response["events"] = sprint_store.read_events(sprint.sprint_id)
        return response

    def _review_sprint_public_payload(self, sprint_store: _InterfaceType, sprint: Any) -> ImplementationDocument:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
        action_queue_summary_data = self._review_sprint_action_queue_summary(sprint_store, sprint)
        closeout_report = sprint_store.read_closeout_report(sprint.sprint_id, default={})
        signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
        return {
            **sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": _interfaces_api_runtime.recommendation_report_summary(recommendation_report),
            "judge_summary": judge_summary_data,
            "action_queue_summary": action_queue_summary_data,
            "metrics_summary": self._review_sprint_metrics_summary(sprint_store, sprint),
            "closeout_summary": _interfaces_api_runtime.closeout_report_summary(closeout_report),
            "signoff_summary": _interfaces_api_runtime.signoff_summary(signoff),
            "export_summary": _interfaces_api_runtime.review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, action_queue_summary_data, judge_summary_data),
        }

    def _review_sprint_metrics_summary(self, sprint_store: _InterfaceType, sprint: Any) -> ImplementationDocument:
        try:
            metrics_store = _interfaces_api_runtime.ReviewMetricsStore(sprint_store.project_dir)
            return _interfaces_api_runtime.sprint_metrics_summary(metrics_store.read_sprint_metrics(sprint.sprint_id, default={}))
        except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
            return {}

    def _review_sprint_action_queue_summary(self, sprint_store: _InterfaceType, sprint: Any) -> ImplementationDocument:
        try:
            queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
            return _interfaces_api_runtime.action_queue_collection_summary(_as_list(queue_store.list_queues(include_archived=True)))
        except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
            return {}

    def _get_or_refresh_sprint_closeout(
        self,
        project_id: str,
        sprint_store: _InterfaceType,
        task_store: _InterfaceType,
        sprint: Any,
        *,
        refresh: bool,
    ) -> ImplementationDocument:
        project_dir = self.project_store.project_dir(project_id)
        if not refresh:
            existing = sprint_store.read_closeout_report(sprint.sprint_id, default={})
            if existing:
                try:
                    project_document = self.project_store.sync_project(project_id, self.store.get_job)
                except FileNotFoundError:
                    project_document = self.project_store.get_project(project_id)
                queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                metrics_store = _interfaces_api_runtime.ReviewMetricsStore(project_dir)
                current_hash = _interfaces_api_runtime.closeout_source_hash(
                    sprint=sprint,
                    project_document=project_document,
                    task_store=task_store,
                    sprint_store=sprint_store,
                    queue_store=queue_store,
                    metrics_report=metrics_store.read_sprint_metrics(sprint.sprint_id, default={}),
                    judge_summary=sprint_store.read_judge_summary(sprint.sprint_id, default={}),
                    recommendation_report=sprint_store.read_recommendation_report(sprint.sprint_id, default={}),
                    conflict_report=sprint_store.read_conflict_report(sprint.sprint_id, default={}),
                )
                if str(existing.get("source_hash") or "") != current_hash:
                    return _interfaces_api_runtime.mark_closeout_report_stale(existing, current_source_hash=current_hash)
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        metrics_report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=refresh)
        report = _interfaces_api_runtime.build_closeout_report(
            project_id=project_id,
            sprint=sprint,
            project_document=project_document,
            task_store=task_store,
            sprint_store=sprint_store,
            queue_store=_interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
            metrics_report=metrics_report,
            judge_summary=sprint_store.read_judge_summary(sprint.sprint_id, default={}),
            recommendation_report=sprint_store.read_recommendation_report(sprint.sprint_id, default={}),
            conflict_report=sprint_store.read_conflict_report(sprint.sprint_id, default={}),
            now=_interfaces_api_runtime._utc_now(),
        )
        return sprint_store.write_closeout_report(sprint, report, now=_interfaces_api_runtime._utc_now())

    def _get_or_refresh_sprint_metrics(
        self,
        project_id: str,
        sprint_store: _InterfaceType,
        task_store: _InterfaceType,
        sprint: Any,
        *,
        refresh: bool,
    ) -> ImplementationDocument:
        project_dir = self.project_store.project_dir(project_id)
        metrics_store = _interfaces_api_runtime.ReviewMetricsStore(project_dir)
        if not refresh:
            existing = metrics_store.read_sprint_metrics(sprint.sprint_id, default={})
            if existing:
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        provider_records = _interfaces_api_runtime.collect_project_provider_usage_records(project_id, project_document.versions, project_dir)
        queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
        report = _interfaces_api_runtime.build_sprint_metrics_report(
            project_id=project_id,
            sprint=sprint,
            project_document=project_document,
            task_store=task_store,
            sprint_store=sprint_store,
            queue_store=queue_store,
            provider_usage_records=provider_records,
            now=_interfaces_api_runtime._utc_now(),
        )
        return metrics_store.write_sprint_metrics(sprint.sprint_id, report)
