from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesAcceptance:
    def _handle_acceptance_route(self, method: str, suite_id: str, tail: str) -> None:
        try:
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                if method == "GET":
                    suite = self.acceptance_store.get_suite(suite_id)
                    cases = self.acceptance_store.list_cases(suite_id)
                    self._send_json({"ok": True, "suite": suite.to_dict(), "cases": [case.to_dict() for case in cases], "summary": _interfaces_api_runtime.acceptance_suite_summary(suite), "events": self.acceptance_store.read_events(suite_id)})
                    return
                if method == "POST":
                    suite = self.acceptance_store.get_suite(suite_id)
                    self.acceptance_store.ensure_mutable(suite)
                    payload = self._optional_json_body()
                    if payload.get("name"):
                        suite.name = str(payload.get("name"))
                    if payload.get("mode"):
                        suite.mode = str(payload.get("mode"))
                    if payload.get("min_rating") is not None:
                        suite.min_rating = int(payload.get("min_rating"))
                    suite = self.acceptance_store.save_suite(suite)
                    self._send_json({"ok": True, "suite": suite.to_dict(), "summary": _interfaces_api_runtime.acceptance_suite_summary(suite)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["cases"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                case = self.acceptance_store.add_case(suite_id, self._read_json_body())
                self._send_json({"ok": True, "case": case.to_dict(), "summary": _interfaces_api_runtime.acceptance_suite_summary(self.acceptance_store.get_suite(suite_id))}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return

            if parts == ["report"]:
                if method == "GET":
                    report = self.acceptance_store.read_report(suite_id, default={})
                    self._send_json({"ok": True, "suite_id": suite_id, "report": report, "summary": _interfaces_api_runtime.acceptance_report_summary(report)})
                    return
                if method == "POST":
                    report = self.acceptance_store.build_report(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "report": report, "summary": _interfaces_api_runtime.acceptance_report_summary(report)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["signoff"]:
                if method == "GET":
                    signoff = self.acceptance_store.read_signoff(suite_id, default={})
                    self._send_json({"ok": True, "suite_id": suite_id, "signoff": signoff, "summary": _interfaces_api_runtime.acceptance_signoff_summary(signoff)})
                    return
                if method == "POST":
                    signoff = self.acceptance_store.signoff(suite_id, self._optional_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, "signoff": signoff, "summary": _interfaces_api_runtime.acceptance_signoff_summary(signoff)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["signoff", "reset"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                if not reason:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "reason is required.")
                    return
                event = self.acceptance_store.reset_signoff(suite_id, reason)
                self._send_json({"ok": True, "suite_id": suite_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if parts == ["archive"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                suite = self.acceptance_store.archive_suite(suite_id)
                self._send_json({"ok": True, "suite": suite.to_dict(), "summary": _interfaces_api_runtime.acceptance_suite_summary(suite)})
                return

            if parts == ["diff"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                other_suite_id = str(payload.get("other_suite_id") or payload.get("left_suite_id") or "").strip()
                if not other_suite_id:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "other_suite_id is required.")
                    return
                left = self.acceptance_store.read_report(other_suite_id)
                right = self.acceptance_store.read_report(suite_id)
                diff = _interfaces_api_runtime.build_acceptance_diff(left, right)
                self._send_json({"ok": True, "suite_id": suite_id, "other_suite_id": other_suite_id, "diff": diff, "summary": diff.get("summary", {})})
                return

            if parts == ["analytics"]:
                self._handle_suite_acceptance_analytics(method, suite_id)
                return

            if parts == ["analytics", "refresh"]:
                self._handle_suite_acceptance_analytics_refresh(method, suite_id)
                return

            if parts == ["human-review-packs"]:
                if method == "GET":
                    packs = self.human_review_pack_store.list_packs(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "packs": packs, "summary": {"pack_count": len(packs)}})
                    return
                if method == "POST":
                    result = self.human_review_pack_store.create_pack(suite_id, self._optional_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) >= 2 and parts[0] == "human-review-packs":
                pack_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    pack = self.human_review_pack_store.get_pack(suite_id, pack_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "pack": pack})
                    return
                if action == "zip":
                    if method == "POST":
                        result = self.human_review_pack_store.build_zip(suite_id, pack_id)
                        self._send_json({"ok": True, "suite_id": suite_id, **result})
                        return
                    if method == "GET":
                        self._send_file(self.human_review_pack_store.zip_path(suite_id, pack_id), "application/zip", filename=f"{suite_id}-{pack_id}-human-review-pack.zip")
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.human_review_pack_store.verify_pack(suite_id, pack_id, strict=bool(payload.get("strict", False)))
                    self._send_json({"ok": report.get("status") == "passed", "suite_id": suite_id, "pack_id": pack_id, "report": report, "summary": report.get("summary", {})})
                    return

            if parts == ["review-imports"]:
                if method == "GET":
                    imports = self.human_review_pack_store.list_imports(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "imports": imports, "summary": {"import_count": len(imports)}})
                    return
                if method == "POST":
                    record = self.human_review_pack_store.import_response(suite_id, self._read_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, "import": record, "summary": record.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) == 2 and parts[0] == "review-imports":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                record = self.human_review_pack_store.get_import(suite_id, parts[1])
                self._send_json({"ok": True, "suite_id": suite_id, "import": record, "summary": record.get("summary", {})})
                return

            if len(parts) >= 2 and parts[0] == "cases":
                case_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    case = self.acceptance_store.get_case(suite_id, case_id)
                    self._send_json({"ok": True, "case": case.to_dict(), "health": self.acceptance_store.read_health(suite_id, case_id, default={}), "review": self.acceptance_store.read_review(suite_id, case_id, default={})})
                    return
                if action == "generate":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    case = self.acceptance_store.generate_case(suite_id, case_id, render_audio_mode=str(payload.get("render_audio") or "auto"))
                    self._send_json({"ok": True, "case": case.to_dict()})
                    return
                if action == "health":
                    if method == "GET":
                        report = self.acceptance_store.read_health(suite_id, case_id, default={})
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "health": report})
                        return
                    if method == "POST":
                        report = self.acceptance_store.run_health(suite_id, case_id)
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "health": report})
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "render-audio":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = self._renderer_profile_from_payload(payload)
                    config = profile.to_renderer_config() if profile is not None else None
                    result = self.acceptance_store.render_audio(suite_id, case_id, mode=str(payload.get("mode") or "auto"), config=config)
                    self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, **result})
                    return
                if action == "review":
                    if method == "GET":
                        review = self.acceptance_store.read_review(suite_id, case_id, default={})
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "review": review, "summary": _interfaces_api_runtime.listening_review_summary(review)})
                        return
                    if method == "POST":
                        review = self.acceptance_store.write_review(suite_id, case_id, self._read_json_body())
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "review": review, "summary": _interfaces_api_runtime.listening_review_summary(review)})
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "midi":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / "song.mid", "audio/midi", filename=f"{suite_id}-{case_id}.mid")
                    return
                if action == "audio":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / "song.wav", "audio/wav", filename=f"{suite_id}-{case_id}.wav")
                    return

            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Acceptance route not found.")
        except _interfaces_api_runtime.AcceptanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.HumanReviewPackStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.HumanReviewPackNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.HumanReviewPackValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics(self, method: str, suite_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics_refresh(self, method: str, suite_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics_refresh(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics(self, method: str, release_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics_refresh(self, method: str, release_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_root(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime._analytics_scope_from_query(query_string)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, _interfaces_api_runtime.ReleaseNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
