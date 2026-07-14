from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class QualityRoutesPart016:
    def _handle_acceptance_fix_sprint_route(self, method: str, route: tuple[str, list[str]]) -> None:
        fix_sprint_id, parts = route
        try:
            if not parts:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                return

            if parts == ["archive"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.archive_sprint(fix_sprint_id, now=_utc_now())
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "summary": fix_sprint_summary(sprint)})
                return

            if parts == ["refresh-status"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.refresh_status(fix_sprint_id, now=_utc_now())
                items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                return

            if parts == ["items"]:
                if method == "GET":
                    items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                    sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                    self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                    return
                if method == "POST":
                    item = self.acceptance_fix_sprint_store.add_item(fix_sprint_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) >= 3 and parts[0] == "items":
                item_id = parts[1]
                action = parts[2]
                if action == "waive":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    item = self.acceptance_fix_sprint_store.waive_item(fix_sprint_id, item_id, str(payload.get("reason") or payload.get("notes") or ""), now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()})
                    return
                if action == "reopen":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    item = self.acceptance_fix_sprint_store.reopen_item(fix_sprint_id, item_id, now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()})
                    return
                if action == "create-review-task":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.acceptance_fix_sprint_store.create_review_tasks(fix_sprint_id, item_id=item_id, now=_utc_now())
                    created = any(row.get("status") == "created" for row in result.get("results", []) if isinstance(row, dict))
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED if created else HTTPStatus.OK)
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Sprint item route not found.")
                return

            if parts == ["create-review-tasks"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_sprint_store.create_review_tasks(fix_sprint_id, now=_utc_now())
                created = any(row.get("status") == "created" for row in result.get("results", []) if isinstance(row, dict))
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED if created else HTTPStatus.OK)
                return

            if parts == ["create-recheck-suite"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_sprint_store.create_recheck_suite(fix_sprint_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return

            if parts == ["link-recheck-suite"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                sprint = self.acceptance_fix_sprint_store.link_recheck_suite(fix_sprint_id, str(payload.get("suite_id") or ""), now=_utc_now())
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "summary": fix_sprint_summary(sprint)})
                return

            if parts == ["delta"]:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                delta = self.acceptance_fix_sprint_store.read_delta(fix_sprint_id)
                self._send_json({"ok": True, "delta_report": delta, "summary": delta.get("summary", {})})
                return

            if parts == ["delta", "refresh"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                delta = self.acceptance_fix_sprint_store.refresh_delta(fix_sprint_id, now=_utc_now())
                self._send_json({"ok": True, "delta_report": delta, "summary": delta.get("summary", {})})
                return

            if parts == ["closeout"]:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.acceptance_fix_sprint_store.read_closeout(fix_sprint_id)
                self._send_json({"ok": True, "closeout_report": closeout, "summary": acceptance_fix_closeout_summary(closeout)})
                return

            if parts == ["close"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.acceptance_fix_sprint_store.close(fix_sprint_id, self._optional_json_body(), now=_utc_now())
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "closeout_report": closeout, "summary": acceptance_fix_closeout_summary(closeout)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Sprint route not found.")
        except AcceptanceFixSprintNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceFixSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceFixSprintError, AcceptanceAnalyticsError, AcceptanceNotFoundError, FileNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_root(self, method: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.latest_report()
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_refresh(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.refresh(self._optional_json_body(), now=_utc_now())
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}, status=HTTPStatus.CREATED)
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_report(self, method: str, report_id: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.get_report(report_id)
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)})
        except AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entries(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.list_entries(include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entry_route(self, method: str, route: tuple[str, str]) -> None:
        entry_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.read_entry(entry_id)
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)})
                return
            if action in {"hide", "unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.hide_entry(entry_id, hidden=action == "hide", now=_utc_now())
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance KB entry route not found.")
        except AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_search(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            payload = {
                "issue_type": _query_value(query, "issue_type") or "",
                "style": _query_value(query, "style") or "",
                "song_id": _query_value(query, "song_id") or "",
                "project_id": _query_value(query, "project_id") or "",
                "release_id": _query_value(query, "release_id") or "",
                "outcome_status": _query_value(query, "outcome_status") or "",
            }
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.search_entries(payload, include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_recommend(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            recommendation = self.acceptance_kb_store.recommend(self._optional_json_body())
            self._send_json({"ok": True, "recommendation": recommendation})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_version_audio_route(self, method: str, project_id: str, version_id: str, action: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next((item for item in document.versions if item.version_id == version_id), None)
            if version is None:
                raise FileNotFoundError(version_id)
            job = self.store.get_job(version.job_id)
            if job is None:
                raise FileNotFoundError(version.job_id)
            audio_path = Path(job.output_dir) / "renders" / "song.wav"
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Audio render is not available for this version.")
                    return
                stale_reasons = self._job_audio_artifact_stale_reasons(job)
                if stale_reasons:
                    self._send_error(HTTPStatus.CONFLICT, f"Audio artifact is stale: {', '.join(stale_reasons)}.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{version_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                profile = self._renderer_profile_from_payload(payload)
                config = profile.to_renderer_config() if profile is not None else None
                audio, status, error = self.store.render_job_audio(job.job_id, config=config, audio_profile=profile)
                if error is not None:
                    self._send_error(status, str(sanitize_metadata({"error": error}).get("error") or "Audio render failed."))
                    return
                self.project_store.append_event(project_id, "project_version_audio_rendered", {"version_id": version_id, "job_id": job.job_id})
                wav_path = Path(job.output_dir) / "renders" / "song.wav"
                self._send_json(
                    {
                        "ok": True,
                        "version_id": version_id,
                        "job_id": job.job_id,
                        "audio_status": "completed",
                        "audio_url": f"/api/projects/{project_id}/versions/{version_id}/audio",
                        "audio": {"exists": wav_path.exists(), "size_bytes": wav_path.stat().st_size if wav_path.exists() else 0, **audio},
                    },
                    status=status,
                )
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Project version audio route not found.")
