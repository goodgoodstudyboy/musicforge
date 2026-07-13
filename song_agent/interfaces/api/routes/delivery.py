from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *

class DeliveryRoutes:
    @property
    def release_store(self) -> ReleaseStore:
        return self.server.release_store  # type: ignore[attr-defined]

    @property
    def release_operations_store(self) -> ReleaseOperationsStore:
        return self.server.release_operations_store  # type: ignore[attr-defined]

    @property
    def release_operations_runbook_store(self) -> ReleaseOperationsRunbookStore:
        return self.server.release_operations_runbook_store  # type: ignore[attr-defined]

    @property
    def release_operations_signoff_store(self) -> ReleaseOperationsSignoffStore:
        return self.server.release_operations_signoff_store  # type: ignore[attr-defined]

    @property
    def release_operations_audit_store(self) -> ReleaseOperationsAuditStore:
        return self.server.release_operations_audit_store  # type: ignore[attr-defined]

    @property
    def release_operations_reviewer_pack_store(self) -> ReleaseOperationsReviewerPackStore:
        return self.server.release_operations_reviewer_pack_store  # type: ignore[attr-defined]

    @property
    def distribution_store(self) -> DistributionStore:
        return self.server.distribution_store  # type: ignore[attr-defined]

    @property
    def submission_store(self) -> SubmissionStore:
        return self.server.submission_store  # type: ignore[attr-defined]

    @property
    def submission_evidence_store(self) -> SubmissionEvidenceStore:
        return self.server.submission_evidence_store  # type: ignore[attr-defined]

    @property
    def distribution_template_store(self) -> TemplatePackStore:
        return self.server.distribution_template_store  # type: ignore[attr-defined]

    def _handle_distribution_profiles_root(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self._send_json({"ok": True, "profiles": list_distribution_profiles()})

    def _handle_distribution_profile_route(self, method: str, profile_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self._send_json({"ok": True, "profile": get_distribution_profile(profile_id)})
        except ValueError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_distribution_templates_root(self, method: str) -> None:
        try:
            if method == "GET":
                templates = self.distribution_template_store.list_templates()
                self._send_json({"ok": True, "template_packs": templates, "summary": {"count": len(templates)}})
                return
            if method == "POST":
                template = self.distribution_template_store.create_template(self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "template": template, "summary": template_summary(template)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except DistributionTemplateError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_distribution_template_import(self, method: str, query: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            rename = parse_qs(query).get("rename", ["0"])[0] in {"1", "true", "yes"}
            template = self.distribution_template_store.import_template(self._read_json_body(), rename=rename, now=_utc_now())
            self._send_json({"ok": True, "template": template, "summary": template_summary(template)}, status=HTTPStatus.CREATED)
        except DistributionTemplateError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_distribution_template_route(self, method: str, route: tuple[str, str]) -> None:
        template_id, action = route
        try:
            if action == "":
                if method == "GET":
                    template = self.distribution_template_store.get_template(template_id)
                    self._send_json({"ok": True, "template": template, "summary": template_summary(template)})
                    return
                if method in {"POST", "PATCH"}:
                    self.distribution_store.ensure_template_pack_mutable(template_id)
                    template = self.distribution_template_store.update_template(template_id, self._read_json_body(), now=_utc_now())
                    stale_targets = self.distribution_store.mark_template_dependents_stale(template_id, "template_updated")
                    self._send_json({"ok": True, "template": template, "summary": template_summary(template), "stale_targets": stale_targets})
                    return
            if action == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.distribution_template_store.clone_template(template_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "template": template, "summary": template_summary(template)}, status=HTTPStatus.CREATED)
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.distribution_store.ensure_template_pack_deletable(template_id)
                result = self.distribution_template_store.delete_template(template_id)
                self._send_json({"ok": True, **result})
                return
            if action == "export":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.distribution_template_store.get_template(template_id)
                self._send_json({"ok": True, "template": template, "summary": template_summary(template)})
                return
            if action == "validate":
                if method not in {"GET", "POST"}:
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body() if method == "POST" else {"template": self.distribution_template_store.get_template(template_id)}
                self._send_json({"ok": True, "validation": self.distribution_template_store.validate_payload(payload)})
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except DistributionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except DistributionTemplateError as exc:
            message = str(exc)
            status = HTTPStatus.CONFLICT if "Builtin" in message or "already exists" in message or "cannot" in message else HTTPStatus.BAD_REQUEST
            self._send_error(status, message)

    def _handle_releases_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
            documents = self.release_store.list_releases(include_hidden=include_hidden)
            self._send_json({"releases": [release_summary(document) for document in documents]})
            return
        if method == "POST":
            payload = self._read_json_body()
            try:
                document = self.release_store.create_release(payload)
            except ReleaseValidationError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_project_release_targets(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        releases = [
            release_summary(document)
            for document in self.release_store.list_releases(include_hidden=False)
            if document.status not in {"signed", "archived"}
        ]
        self._send_json({"ok": True, "project_id": project_id, "releases": releases})

    def _handle_project_add_to_release(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            release_id = str(payload.get("release_id") or "").strip()
            if not release_id:
                release = self.release_store.create_release(
                    {
                        "name": str(payload.get("release_name") or "Untitled Release"),
                        "release_type": str(payload.get("release_type") or "demo_pack"),
                        "primary_artist": str(payload.get("primary_artist") or ""),
                        "language": payload.get("language"),
                        "notes": payload.get("notes"),
                    }
                )
                release_id = release.release_id
            document = self.release_store.add_track(
                release_id,
                {
                    **payload,
                    "project_id": project_id,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            return
        except (ReleaseValidationError, ReleaseMetadataError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except (ReleaseConflictError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})

    def _handle_release_route(self, method: str, release_id: str, tail: str, query_string: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    document = self.release_store.get_release(release_id)
                    self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document), "events": self.release_store.read_events(release_id)})
                    return
                if method == "PATCH":
                    payload = self._read_json_body()
                    document = self.release_store.update_release(release_id, payload)
                    self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document = self.release_store.hide_release(release_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                return

            if tail == "/archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document = self.release_store.archive_release(release_id)
                self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                return

            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.release_store.delete_release(release_id)})
                return

            if tail == "/tracks":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                document = self.release_store.add_track(release_id, payload)
                self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                return

            if tail == "/tracks/reorder":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document = self.release_store.reorder_tracks(release_id, self._read_json_body())
                self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                return

            track_route = _match_release_track_tail(tail)
            if track_route is not None:
                track_id, action = track_route
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "remove":
                    document = self.release_store.remove_track(release_id, track_id)
                elif action == "refresh":
                    document = self.release_store.refresh_track(release_id, track_id)
                elif action == "replace-version":
                    self.audio_revision_store.replace_release_track_version(release_id, track_id, self._read_json_body(), now=_utc_now())
                    document = self.release_store.get_release(release_id)
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "Release track route not found.")
                    return
                self._send_json({"ok": True, "release": document.to_dict(), "summary": release_summary(document)})
                return

            if tail == "/qa":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_release_qa(release_id, refresh=False, options={})
                self._send_json({"ok": True, "release_id": release_id, "release_qa": report, "summary": release_qa_summary(report)})
                return

            if tail == "/qa/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_release_qa(release_id, refresh=True, options=self._optional_json_body())
                self.release_store.append_event(release_id, "release_qa_refreshed", {"status": report.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "release_qa": report, "summary": release_qa_summary(report)})
                return

            if tail == "/audio-qa":
                self._handle_release_audio_qa(method, release_id)
                return

            if tail == "/audio-reviews" or tail.startswith("/audio-reviews/"):
                self._handle_release_audio_reviews(method, release_id, tail.removeprefix("/audio-reviews"))
                return

            if tail == "/audio-revisions" or tail.startswith("/audio-revisions/"):
                self._handle_release_audio_revisions(method, release_id, tail.removeprefix("/audio-revisions"))
                return

            if tail == "/audio-campaign-plan" or tail.startswith("/audio-campaign-plan/"):
                self._handle_release_audio_campaign_plan(method, release_id, tail.removeprefix("/audio-campaign-plan"))
                return

            if tail == "/audio-campaign-remediation" or tail.startswith("/audio-campaign-remediation/"):
                self._handle_release_audio_campaign_remediation(method, release_id, tail.removeprefix("/audio-campaign-remediation"))
                return

            if tail == "/audio-certification" or tail.startswith("/audio-certification/"):
                self._handle_release_audio_certification(method, release_id, tail.removeprefix("/audio-certification"))
                return

            if tail == "/audio-timelines" or tail.startswith("/audio-timelines/"):
                self._handle_release_audio_timeline(method, release_id, tail.removeprefix("/audio-timelines"))
                return

            if tail == "/audio-regression" or tail.startswith("/audio-regression/"):
                self._handle_release_audio_regression(method, release_id, tail.removeprefix("/audio-regression"))
                return

            if tail == "/audio-regression-response" or tail.startswith("/audio-regression-response/"):
                self._handle_release_audio_regression_response(method, release_id, tail.removeprefix("/audio-regression-response"))
                return

            if tail == "/audio-command-center" or tail.startswith("/audio-command-center/"):
                self._handle_release_audio_command_center(method, release_id, tail.removeprefix("/audio-command-center"))
                return

            if tail == "/mastering" or tail.startswith("/mastering/"):
                self._handle_release_mastering(method, release_id, tail.removeprefix("/mastering"))
                return

            if tail == "/encoded-audio" or tail.startswith("/encoded-audio/"):
                self._handle_release_encoded_audio(method, release_id, tail.removeprefix("/encoded-audio"))
                return

            if tail == "/format-decisions" or tail.startswith("/format-decisions/"):
                self._handle_release_format_decisions(method, release_id, tail.removeprefix("/format-decisions"))
                return

            if tail == "/rights" or tail.startswith("/rights/"):
                self._handle_release_rights(method, release_id, tail.removeprefix("/rights"))
                return

            if tail == "/metadata":
                if method == "GET":
                    metadata = read_release_metadata(self.release_store, release_id, default={})
                    qa_report = self._get_or_refresh_release_metadata_qa(release_id, refresh=False) if metadata else {}
                    self._send_json(
                        {
                            "ok": True,
                            "release_id": release_id,
                            "metadata": metadata,
                            "history": read_release_metadata_history(self.release_store, release_id),
                            "summary": release_metadata_summary(metadata, qa_report, metadata_export_summary(_safe_read_release_export_manifest(self.release_store, release_id))),
                        }
                    )
                    return
                if method == "POST":
                    metadata = write_release_metadata(self.release_store, release_id, self._read_json_body(), now=_utc_now())
                    report = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
                    self._send_json({"ok": True, "release_id": release_id, "metadata": metadata, "summary": release_metadata_summary(metadata, report)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail == "/metadata/init":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                metadata = initialize_release_metadata(self.release_store, release_id, force=bool(payload.get("force", False)), merge=bool(payload.get("merge", False)), now=_utc_now())
                report = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
                self._send_json({"ok": True, "release_id": release_id, "metadata": metadata, "summary": release_metadata_summary(metadata, report)})
                return

            if tail == "/metadata/qa":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_release_metadata_qa(release_id, refresh=False)
                self._send_json({"ok": True, "release_id": release_id, "metadata_qa": report, "summary": release_metadata_qa_summary(report)})
                return

            if tail == "/metadata/qa/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
                self.release_store.append_event(release_id, "release_metadata_qa_refreshed", {"status": report.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "metadata_qa": report, "summary": release_metadata_qa_summary(report)})
                return

            if tail == "/metadata/export":
                if method == "GET":
                    manifest = _safe_read_release_export_manifest(self.release_store, release_id)
                    self._send_json({"ok": True, "release_id": release_id, "metadata_export": manifest.get("metadata", {}), "summary": metadata_export_summary(manifest)})
                    return
                if method == "POST":
                    self._ensure_release_export_mutable(release_id)
                    report = self._get_or_refresh_release_metadata_qa(release_id, refresh=False)
                    export_summary = export_release_metadata_files(release_store=self.release_store, release_id=release_id, qa_report=report, now=_utc_now())
                    manifest = attach_metadata_export_to_manifest(self.release_store, release_id, export_summary)
                    build_release_export_zip(self.release_store, release_id, now=_utc_now())
                    manifest = read_release_export_manifest(self.release_store, release_id)
                    document = self.release_store.update_export_summary(release_id, release_export_summary(manifest))
                    self.release_store.append_event(release_id, "release_metadata_exported", {"file_count": len(export_summary.get("files", []))})
                    self._send_json({"ok": True, "release": document.to_dict(), "manifest": manifest, "metadata_export": export_summary, "summary": metadata_export_summary(manifest)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail in {"/metadata/platform.csv", "/metadata/credits.csv"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                filename = "platform-metadata.csv" if tail.endswith("platform.csv") else "credits.csv"
                self.release_store.get_release(release_id)
                self._send_file(self.release_store.export_dir(release_id) / filename, "text/csv; charset=utf-8", filename=filename)
                return

            if tail == "/operations" or tail.startswith("/operations/"):
                self._handle_release_operations(method, release_id, tail.removeprefix("/operations"))
                return

            if tail.startswith("/distribution"):
                self._handle_distribution_route(method, release_id, tail.removeprefix("/distribution"))
                return

            if tail.startswith("/submissions"):
                self._handle_submission_route(method, release_id, tail.removeprefix("/submissions"))
                return

            if tail == "/acceptance-analytics":
                self._handle_release_acceptance_analytics(method, release_id)
                return

            if tail == "/acceptance-analytics/refresh":
                self._handle_release_acceptance_analytics_refresh(method, release_id)
                return

            if tail == "/export":
                if method == "GET":
                    try:
                        manifest = read_release_export_manifest(self.release_store, release_id)
                    except FileNotFoundError:
                        self._send_json({"ok": True, "release_id": release_id, "manifest": {}, "summary": release_export_summary({})})
                        return
                    self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": release_export_summary(manifest)})
                    return
                if method == "POST":
                    document = self.release_store.get_release(release_id)
                    self._ensure_release_export_mutable(release_id, document=document)
                    report = self._get_or_refresh_release_qa(release_id, refresh=False, options={})
                    manifest = build_release_export_bundle(release=document, release_store=self.release_store, project_store=self.project_store, qa_report=report, now=_utc_now())
                    document = self.release_store.update_export_summary(release_id, release_export_summary(manifest))
                    self.release_store.append_event(release_id, "release_export_created", {"file_count": manifest.get("summary", {}).get("file_count")})
                    self._send_json({"ok": True, "release": document.to_dict(), "manifest": manifest, "summary": release_export_summary(manifest)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._ensure_release_export_mutable(release_id)
                zip_info = build_release_export_zip(self.release_store, release_id, now=_utc_now())
                manifest = read_release_export_manifest(self.release_store, release_id)
                document = self.release_store.update_export_summary(release_id, release_export_summary(manifest))
                self.release_store.append_event(release_id, "release_export_zip_created", {"sha256": zip_info.get("sha256")})
                self._send_json({"ok": True, "release": document.to_dict(), "zip": zip_info, "summary": release_export_summary(manifest)})
                return

            if tail == "/export.zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-release-export.zip")
                return

            if tail == "/signoff":
                self._handle_release_signoff(method, release_id)
                return

            if tail == "/signoff/reset":
                self._handle_release_signoff_reset(method, release_id)
                return

            if tail == "/events":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_json({"events": self.release_store.read_events(release_id)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Release route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ReleaseConflictError, ReleaseStateError, ReleaseExportError, ReleaseOperationsError, ReleaseOperationsRunbookStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsRunbookNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ReleaseValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations(self, method: str, release_id: str, tail: str) -> None:
        if tail == "/runbooks" or tail.startswith("/runbooks/"):
            self._handle_release_operations_runbooks(method, release_id, tail.removeprefix("/runbooks"))
            return
        if tail == "/signoff" or tail == "/signoff/reset":
            self._handle_release_operations_signoff(method, release_id, tail.removeprefix("/signoff"))
            return
        if tail == "/change-requests" or tail.startswith("/change-requests/"):
            self._handle_release_operations_change_requests(method, release_id, tail.removeprefix("/change-requests"))
            return
        if tail == "/archive/export" or tail == "/archive/export/zip" or tail == "/archive/verify" or tail == "/archive.zip":
            self._handle_release_operations_archive(method, release_id, tail.removeprefix("/archive"))
            return
        if tail == "/audit" or tail.startswith("/audit/") or tail == "/audit.zip":
            self._handle_release_operations_audit(method, release_id, tail.removeprefix("/audit"))
            return
        if tail == "/reviewer-pack" or tail.startswith("/reviewer-pack/") or tail == "/reviewer-pack.zip":
            self._handle_release_operations_reviewer_pack(method, release_id, tail.removeprefix("/reviewer-pack"))
            return
        if tail in {"", "/"}:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_json(self.release_operations_store.overview(release_id))
            return
        if tail == "/refresh":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.release_operations_store.refresh(release_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": operations_report_summary(report)})
            return
        if tail == "/export":
            if method == "GET":
                try:
                    manifest = self.release_operations_store.read_export_manifest(release_id)
                except FileNotFoundError:
                    self._send_json({"ok": True, "release_id": release_id, "manifest": {}, "summary": {"status": "missing"}})
                    return
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})})
                return
            if method == "POST":
                manifest = self.release_operations_store.export_operations(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/export/zip":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            zip_info = self.release_operations_store.build_zip(release_id, now=_utc_now())
            manifest = self.release_operations_store.read_export_manifest(release_id)
            self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
            return
        if tail == "/export.zip":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self.release_store.get_release(release_id)
            self._send_file(self.release_operations_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations.zip")
            return
        if tail == "/verify":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = verify_release_operations_package(
                self.release_operations_store.zip_path(release_id),
                strict=bool(payload.get("strict", False)),
                require_accepted=bool(payload.get("require_accepted", False)),
                require_submission_evidence=bool(payload.get("require_submission_evidence", False)),
            )
            write_release_operations_verification_report(report, self.release_operations_store.operations_dir(release_id) / "operations-verification-report.json")
            self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_verification_summary(report)})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Release Operations route not found.")

    def _handle_release_operations_signoff(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    signoff = self.release_operations_signoff_store.read_signoff(release_id, default={})
                    gate = self.release_operations_signoff_store.gate(release_id, {}, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=self.release_operations_store.build_report(release_id, persist=False)), "gate": gate})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    try:
                        signoff = self.release_operations_signoff_store.signoff(release_id, payload, now=_utc_now())
                    except ReleaseOperationsSignoffStateError as exc:
                        gate = self.release_operations_signoff_store.gate(release_id, payload, now=_utc_now())
                        self._send_json({"error": str(exc), "gate": gate}, status=HTTPStatus.CONFLICT)
                        return
                    self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=self.release_operations_store.build_report(release_id, persist=False))})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reset = self.release_operations_signoff_store.reset_signoff(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "signoff": reset, "summary": operations_signoff_summary(reset)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Signoff route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_operations_change_requests(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    rows = self.release_operations_signoff_store.list_change_requests(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "change_requests": rows, "summary": self.release_operations_signoff_store.change_request_summary(release_id)})
                    return
                if method == "POST":
                    item = self.release_operations_signoff_store.create_change_request(release_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Operations Change Request route not found.")
                return
            change_request_id = parts[0]
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.release_operations_signoff_store.get_change_request(release_id, change_request_id)
                self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)})
                return
            if len(parts) == 2 and parts[1] in {"submit", "approve", "reject", "cancel"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                item = self.release_operations_signoff_store.update_change_request_status(release_id, change_request_id, parts[1], self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "change_request": item, "integrity_ok": operations_change_request_integrity_ok(item)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Operations Change Request route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_operations_archive(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_signoff_store.export_archive(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_signoff_store.build_archive_zip(release_id, now=_utc_now())
                manifest = self.release_operations_signoff_store.read_archive_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_operations_archive_package(
                    self.release_operations_signoff_store.archive_zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                )
                write_release_operations_archive_verification_report(report, self.release_operations_signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_archive_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_signoff_store.archive_zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-archive.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Archive route not found.")
        except ReleaseOperationsSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations_audit(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_audit_store.read_report(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": audit_summary(report) if report else {"status": "missing", "entry_count": 0}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_audit_store.refresh(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": audit_summary(report)})
                return
            if tail == "/entries":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                query = parse_qs(urlparse(self.path).query)
                entries = self.release_operations_audit_store.entries(
                    release_id,
                    domain=query.get("domain", [None])[0],
                    risk=query.get("risk", [None])[0],
                    event_type=query.get("event_type", [None])[0],
                    limit=int(query.get("limit", ["200"])[0] or 200),
                )
                self._send_json({"ok": True, "release_id": release_id, "entries": entries, "summary": {"entry_count": len(entries)}})
                return
            if tail == "/graph":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "release_id": release_id, "graph": self.release_operations_audit_store.graph(release_id)})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_audit_store.export_audit(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_audit_store.build_zip(release_id, now=_utc_now())
                manifest = self.release_operations_audit_store.read_export_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_operations_audit_package(
                    self.release_operations_audit_store.zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_current=bool(payload.get("require_current", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_archive=bool(payload.get("require_archive", False)),
                )
                write_release_operations_audit_verification_report(report, self.release_operations_audit_store.verification_report_path(release_id))
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_audit_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_audit_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-audit.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Audit route not found.")
        except ReleaseOperationsAuditNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsAuditStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsAuditError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations_reviewer_pack(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_reviewer_pack_store.read_report(release_id, default={})
                retrospective = self.release_operations_reviewer_pack_store.read_retrospective(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(retrospective) if retrospective else {"status": "missing"}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_reviewer_pack_store.refresh(release_id, now=_utc_now())
                retrospective = self.release_operations_reviewer_pack_store.read_retrospective(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(retrospective)})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_reviewer_pack_store.export_pack(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_reviewer_pack_store.build_zip(release_id, now=_utc_now())
                manifest = self.release_operations_reviewer_pack_store.read_export_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_release_operations_reviewer_pack(
                    self.release_operations_reviewer_pack_store.zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_audit=bool(payload.get("require_audit", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_archive=bool(payload.get("require_archive", False)),
                )
                write_release_operations_reviewer_pack_verification_report(report, self.release_operations_reviewer_pack_store.verification_report_path(release_id))
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": release_operations_reviewer_pack_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_reviewer_pack_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-reviewer-pack.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Reviewer Pack route not found.")
        except ReleaseOperationsReviewerPackNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseOperationsReviewerPackStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseOperationsReviewerPackError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations_runbooks(self, method: str, release_id: str, tail: str) -> None:
        if tail in {"", "/"}:
            if method == "GET":
                query = parse_qs(urlparse(self.path).query)
                include_archived = str(query.get("include_archived", [""])[0]).lower() in {"1", "true", "yes"}
                runbooks = self.release_operations_runbook_store.list_runbooks(release_id, include_archived=include_archived)
                self._send_json({"ok": True, "release_id": release_id, "runbooks": runbooks, "summary": {"count": len(runbooks)}})
                return
            if method == "POST":
                runbook = self.release_operations_runbook_store.create_from_operations_report(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        parts = [part for part in tail.strip("/").split("/") if part]
        if not parts:
            self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Runbook route not found.")
            return
        runbook_id = parts[0]
        if len(parts) == 1:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.get_runbook(release_id, runbook_id)
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)})
            return
        action = parts[1]
        if len(parts) == 2 and action == "run-safe":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.run_safe_actions(release_id, runbook_id, self._optional_json_body(), now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)})
            return
        if len(parts) == 2 and action == "refresh-stale":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            result = self.release_operations_runbook_store.refresh_stale_status(release_id, runbook_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, **result, "summary": runbook_summary(result.get("runbook", {}))})
            return
        if len(parts) == 2 and action == "archive":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.archive_runbook(release_id, runbook_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)})
            return
        if len(parts) == 2 and action == "export":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            manifest = self.release_operations_runbook_store.export_runbook(release_id, runbook_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
            return
        if len(parts) == 3 and action == "export" and parts[2] == "zip":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            zip_info = self.release_operations_runbook_store.build_zip(release_id, runbook_id, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "zip": zip_info})
            return
        if len(parts) == 2 and action == "export.zip":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.release_operations_runbook_store.zip_path(release_id, runbook_id), "application/zip", filename=f"musicforge-{release_id}-{runbook_id}-runbook.zip")
            return
        if len(parts) == 2 and action == "verify":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = verify_release_operations_runbook_package(
                self.release_operations_runbook_store.zip_path(release_id, runbook_id),
                strict=bool(payload.get("strict", False)),
                require_completed=bool(payload.get("require_completed", False)),
                require_current=bool(payload.get("require_current", False)),
            )
            write_release_operations_runbook_verification_report(report, self.release_operations_runbook_store.runbook_dir(release_id, runbook_id) / "runbook-verification-report.json")
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "verification": report, "summary": release_operations_runbook_verification_summary(report)})
            return
        if len(parts) == 4 and action == "items" and parts[3] == "retry":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.retry_item(release_id, runbook_id, parts[2], now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)})
            return
        if len(parts) == 4 and action == "items" and parts[3] == "waive":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.waive_item(release_id, runbook_id, parts[2], self._optional_json_body(), now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook_summary(runbook)})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Release Operations Runbook route not found.")

    def _get_or_refresh_release_qa(self, release_id: str, *, refresh: bool, options: dict[str, Any]) -> dict[str, Any]:
        document = self.release_store.get_release(release_id)
        if not refresh:
            existing = self.release_store.read_qa(release_id, default={})
            if existing:
                current_hash = release_source_hash(document, project_store=self.project_store, release_store=self.release_store)
                if str(existing.get("source_hash") or "") != current_hash:
                    return mark_release_qa_stale(existing, current_source_hash=current_hash)
                return existing
        report = build_release_qa_report(release=document, release_store=self.release_store, project_store=self.project_store, options=options, now=_utc_now())
        report = self.release_store.write_qa(release_id, report)
        self.release_store.update_qa_summary(release_id, release_qa_summary(report))
        return report

    def _get_or_refresh_release_metadata_qa(self, release_id: str, *, refresh: bool) -> dict[str, Any]:
        document = self.release_store.get_release(release_id)
        metadata = read_release_metadata(self.release_store, release_id, default={})
        if not metadata:
            report = build_release_metadata_qa_report(release=document, metadata={}, now=_utc_now())
            return write_release_metadata_qa(self.release_store, release_id, report)
        if not refresh:
            existing = read_release_metadata_qa(self.release_store, release_id, default={})
            if existing:
                current_hash = release_metadata_source_hash(document, metadata)
                if str(existing.get("source_hash") or "") != current_hash:
                    return mark_release_metadata_qa_stale(existing, current_source_hash=current_hash)
                return existing
        report = build_release_metadata_qa_report(release=document, metadata=metadata, now=_utc_now())
        return write_release_metadata_qa(self.release_store, release_id, report)

    def _ensure_release_export_mutable(self, release_id: str, *, document: Any | None = None) -> None:
        document = document or self.release_store.get_release(release_id)
        if document.status == "archived":
            raise ReleaseStateError("Archived releases are read-only.")
        if document.status == "signed":
            raise ReleaseStateError("Signed releases cannot rebuild export or ZIP. Reset signoff before exporting again.")

    def _handle_release_signoff(self, method: str, release_id: str) -> None:
        if method == "GET":
            signoff = self.release_store.read_signoff(release_id, default={})
            self._send_json({"ok": True, "release_id": release_id, "signoff": signoff, "summary": release_signoff_summary(signoff)})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        existing = self.release_store.read_signoff(release_id, default={})
        if existing:
            self._send_error(HTTPStatus.CONFLICT, "Release is already signed off. Reset signoff before signing again.")
            return
        document = self.release_store.get_release(release_id)
        report = self._get_or_refresh_release_qa(release_id, refresh=True, options={})
        force = bool(payload.get("force", False))
        acceptance_gate = self._release_acceptance_gate({**payload, "release_id": release_id, "force": force})
        audio_gate = self._release_audio_gate(release_id, payload)
        if audio_gate:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio"] = audio_gate
            if audio_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_gate.get("message") or "Release audio gate failed.")
        require_mastering_qa = bool(payload.get("require_mastering_qa", False))
        mastering_gate = self.mastering_store.gate(
            release_id,
            required=require_mastering_qa,
            profile_id=str(payload.get("mastering_profile_id") or "") or None,
            force=force,
        )
        if mastering_gate and require_mastering_qa:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["mastering"] = mastering_gate
            if mastering_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(mastering_gate.get("message") or "Mastering QA gate failed.")
        require_encoded_audio = bool(payload.get("require_encoded_audio", False))
        required_encoded_profiles = normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("audio_format_profiles") or [])
        encoded_gate = encoded_audio_gate(
            self.audio_encoding_store,
            release_id,
            required_profiles=required_encoded_profiles,
            required=require_encoded_audio,
            force=force,
        )
        if encoded_gate and require_encoded_audio:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["encoded_audio"] = encoded_gate
            if encoded_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(encoded_gate.get("message") or "Encoded audio gate failed.")
        require_encoded_audio_review = bool(payload.get("require_encoded_audio_review", False))
        encoded_acceptance_gate = self.encoded_audio_acceptance_store.gate(
            release_id,
            required_profiles=required_encoded_profiles,
            required=require_encoded_audio_review,
            now=_utc_now(),
        )
        if encoded_acceptance_gate and require_encoded_audio_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["encoded_audio_acceptance"] = encoded_acceptance_gate
            if encoded_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(encoded_acceptance_gate.get("message") or "Encoded audio acceptance gate failed.")
        require_format_decision = bool(payload.get("require_format_decision", False))
        format_decision_gate = self.format_decision_store.gate(
            release_id,
            required=require_format_decision,
            session_id=str(payload.get("format_decision_session_id") or "") or None,
            required_profiles=required_encoded_profiles,
        )
        if format_decision_gate and require_format_decision:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["format_decision"] = format_decision_gate
            if format_decision_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(format_decision_gate.get("message") or "Format decision gate failed.")
        require_rights_clearance = bool(payload.get("require_rights_clearance", False))
        rights_gate = self.rights_clearance_store.gate(release_id, required=require_rights_clearance, now=_utc_now())
        if rights_gate and require_rights_clearance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["rights_clearance"] = rights_gate
            if rights_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(rights_gate.get("message") or "Rights clearance gate failed.")
        require_audio_campaign = bool(payload.get("require_audio_campaign", False))
        audio_campaign_gate = self._release_audio_campaign_gate(release_id, payload, required=require_audio_campaign)
        if audio_campaign_gate and require_audio_campaign:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio_campaign"] = audio_campaign_gate
            if audio_campaign_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_campaign_gate.get("message") or "Audio Campaign gate failed.")
        require_audio_campaign_remediation = bool(payload.get("require_audio_campaign_remediation", False))
        audio_campaign_remediation_gate = self.audio_campaign_remediation_store.gate(release_id, required=require_audio_campaign_remediation, require_signed=bool(payload.get("require_audio_campaign_remediation_signed", False)))
        if audio_campaign_remediation_gate and require_audio_campaign_remediation:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["audio_campaign_remediation"] = audio_campaign_remediation_gate
            if audio_campaign_remediation_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(audio_campaign_remediation_gate.get("message") or "Audio Campaign remediation gate failed.")
        require_release_audio_certification = bool(payload.get("require_release_audio_certification", False))
        release_audio_certification_gate = self.release_audio_certification_store.gate(
            release_id,
            required=require_release_audio_certification,
            require_signed=bool(payload.get("require_release_audio_certification_signed", require_release_audio_certification)),
        )
        if release_audio_certification_gate and require_release_audio_certification:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_certification"] = release_audio_certification_gate
            if release_audio_certification_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_certification_gate.get("message") or "Release Audio Certification gate failed.")
        require_release_audio_timeline = bool(payload.get("require_release_audio_timeline", False))
        release_audio_timeline_gate = self.release_audio_timeline_store.gate(
            release_id,
            required=require_release_audio_timeline,
            require_signed=bool(payload.get("require_release_audio_timeline_signed", require_release_audio_timeline)),
            require_current_certification=bool(payload.get("require_release_audio_timeline_current_certification", True)),
        )
        if release_audio_timeline_gate and require_release_audio_timeline:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_timeline"] = release_audio_timeline_gate
            if release_audio_timeline_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_timeline_gate.get("message") or "Release Audio Timeline gate failed.")
        require_release_audio_regression = bool(payload.get("require_release_audio_regression_guard", False))
        release_audio_regression_gate = self.release_audio_regression_store.gate(
            release_id,
            required=require_release_audio_regression,
            require_signed=bool(payload.get("require_release_audio_regression_signed", require_release_audio_regression)),
        )
        if release_audio_regression_gate and require_release_audio_regression:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_regression_guard"] = release_audio_regression_gate
            if release_audio_regression_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_regression_gate.get("message") or "Release Audio Regression gate failed.")
        require_release_audio_baseline_governance = bool(payload.get("require_release_audio_baseline_governance", False))
        release_audio_baseline_governance_gate = self.release_audio_baseline_governance_store.gate(
            release_id,
            baseline_id=payload.get("release_audio_baseline_id"),
            required=require_release_audio_baseline_governance,
        )
        if release_audio_baseline_governance_gate and require_release_audio_baseline_governance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_baseline_governance"] = release_audio_baseline_governance_gate
            if release_audio_baseline_governance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_baseline_governance_gate.get("message") or "Release Audio Baseline Governance gate failed.")
        require_release_audio_regression_response = bool(payload.get("require_release_audio_regression_response", False))
        release_audio_regression_response_gate = self.release_audio_regression_response_store.gate(
            release_id,
            required=require_release_audio_regression_response,
            require_signed=bool(payload.get("require_release_audio_regression_response_signed", require_release_audio_regression_response)),
        )
        if release_audio_regression_response_gate and require_release_audio_regression_response:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_regression_response"] = release_audio_regression_response_gate
            if release_audio_regression_response_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_regression_response_gate.get("message") or "Release Audio Regression Response gate failed.")
        require_release_audio_quality_observatory = bool(payload.get("require_release_audio_quality_observatory", False))
        release_audio_quality_observatory_gate = self.release_audio_quality_observatory_store.gate(
            release_id,
            observatory_id=payload.get("release_audio_quality_observatory_id"),
            required=require_release_audio_quality_observatory,
            require_no_critical_risk=bool(payload.get("require_no_critical_audio_quality_risk", require_release_audio_quality_observatory)),
        )
        if release_audio_quality_observatory_gate and require_release_audio_quality_observatory:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_observatory"] = release_audio_quality_observatory_gate
            if release_audio_quality_observatory_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_observatory_gate.get("message") or "Release Audio Quality Observatory gate failed.")
        require_release_audio_quality_action_queue = bool(payload.get("require_release_audio_quality_action_queue", False))
        release_audio_quality_action_queue_gate = self.release_audio_quality_action_queue_store.gate(
            release_id,
            queue_id=payload.get("release_audio_quality_action_queue_id"),
            required=require_release_audio_quality_action_queue,
            require_no_blocking=bool(payload.get("require_no_blocking_audio_quality_action", True)),
        )
        if release_audio_quality_action_queue_gate and require_release_audio_quality_action_queue:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_action_queue"] = release_audio_quality_action_queue_gate
            if release_audio_quality_action_queue_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_action_queue_gate.get("message") or "Release Audio Quality Action Queue gate failed.")
        require_release_audio_quality_action_queue_signoff = bool(payload.get("require_release_audio_quality_action_queue_signoff", False))
        release_audio_quality_action_queue_signoff_gate = self.release_audio_quality_action_signoff_store.gate(
            release_id,
            queue_id=payload.get("release_audio_quality_action_queue_id") or payload.get("release_audio_quality_action_queue_signoff_id"),
            required=require_release_audio_quality_action_queue_signoff,
        )
        if release_audio_quality_action_queue_signoff_gate and require_release_audio_quality_action_queue_signoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_quality_action_queue_signoff"] = release_audio_quality_action_queue_signoff_gate
            if release_audio_quality_action_queue_signoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_quality_action_queue_signoff_gate.get("message") or "Release Audio Quality Action Queue signoff gate failed.")
        require_release_audio_command_center = bool(payload.get("require_release_audio_command_center", False))
        release_audio_command_center_gate = self.release_audio_command_center_store.gate(
            release_id,
            required=require_release_audio_command_center,
            command_center_zip_path=payload.get("release_audio_command_center_zip") or payload.get("release_audio_command_center"),
            command_center_verification_report_path=payload.get("release_audio_command_center_verification_report"),
            evidence={
                "certification": {"zip": payload.get("release_audio_certification_zip"), "verification_report": payload.get("release_audio_certification_verification_report")},
                "timeline": {"zip": payload.get("release_audio_timeline_zip"), "verification_report": payload.get("release_audio_timeline_verification_report")},
                "regression": {"zip": payload.get("release_audio_regression_zip"), "verification_report": payload.get("release_audio_regression_verification_report")},
                "baseline_governance": {"zip": payload.get("release_audio_baseline_registry_zip"), "verification_report": payload.get("release_audio_baseline_registry_verification_report")},
                "regression_response": {"zip": payload.get("release_audio_regression_response_zip"), "verification_report": payload.get("release_audio_regression_response_verification_report")},
                "observatory": {"zip": payload.get("release_audio_quality_observatory_zip"), "verification_report": payload.get("release_audio_quality_observatory_verification_report")},
                "action_queue": {"zip": payload.get("release_audio_quality_action_queue_zip"), "verification_report": payload.get("release_audio_quality_action_queue_verification_report")},
                "action_queue_signoff": {"zip": payload.get("release_audio_quality_action_queue_signoff_archive"), "verification_report": payload.get("release_audio_quality_action_queue_signoff_verification_report")},
                "evidence_root": payload.get("release_audio_quality_observatory_evidence_root"),
            },
        )
        if release_audio_command_center_gate and require_release_audio_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["release_audio_command_center"] = release_audio_command_center_gate
            if release_audio_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(release_audio_command_center_gate.get("message") or "Release Audio Command Center gate failed.")
        require_unified_command_center = bool(payload.get("require_unified_command_center", False))
        unified_command_center_gate = self.unified_command_center_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center,
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            evidence={
                "audio-command-center": {"zip": payload.get("release_audio_command_center_zip") or payload.get("release_audio_command_center"), "verification_report": payload.get("release_audio_command_center_verification_report")},
                "ga-readiness": {"report": payload.get("ga_readiness_report")},
                "release-check": {"report": payload.get("release_check_report")},
                "requirements": {"require_audio_command_center": bool(payload.get("require_release_audio_command_center", False))},
            },
        )
        if unified_command_center_gate and require_unified_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center"] = unified_command_center_gate
            if unified_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_gate.get("message") or "Unified Command Center gate failed.")
        require_unified_command_center_archive = bool(payload.get("require_unified_command_center_archive", False))
        unified_command_center_archive_gate = self.unified_command_center_signoff_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_archive,
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
        )
        if unified_command_center_archive_gate and require_unified_command_center_archive:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_archive"] = unified_command_center_archive_gate
            if unified_command_center_archive_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_archive_gate.get("message") or "Unified Command Center Archive gate failed.")
        require_unified_command_center_handoff = bool(payload.get("require_unified_command_center_handoff", False))
        unified_command_center_handoff_gate = self.unified_command_center_handoff_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_handoff,
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
        )
        if unified_command_center_handoff_gate and require_unified_command_center_handoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_handoff"] = unified_command_center_handoff_gate
            if unified_command_center_handoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_handoff_gate.get("message") or "Unified Command Center Handoff gate failed.")
        require_unified_command_center_continuous_review = bool(payload.get("require_unified_command_center_continuous_review", False))
        unified_command_center_continuous_review_gate = self.unified_command_center_continuous_review_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_continuous_review,
            review_id=payload.get("unified_command_center_continuous_review_id"),
            review_zip_path=payload.get("unified_command_center_continuous_review") or payload.get("unified_command_center_continuous_review_zip"),
            review_verification_report_path=payload.get("unified_command_center_continuous_review_verification_report"),
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            signoff_binding_path=payload.get("unified_command_center_signoff_binding"),
        )
        if unified_command_center_continuous_review_gate and require_unified_command_center_continuous_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_continuous_review"] = unified_command_center_continuous_review_gate
            if unified_command_center_continuous_review_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_continuous_review_gate.get("message") or "Unified Command Center Continuous Review gate failed.")
        require_unified_command_center_drift_response = bool(payload.get("require_unified_command_center_drift_response", False))
        unified_command_center_drift_response_gate = self.unified_command_center_drift_response_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_drift_response,
            response_id=payload.get("unified_command_center_drift_response_id"),
            response_zip_path=payload.get("unified_command_center_drift_response") or payload.get("unified_command_center_drift_response_zip"),
            response_verification_report_path=payload.get("unified_command_center_drift_response_verification_report"),
            source_review_zip_path=payload.get("unified_command_center_drift_source_review") or payload.get("unified_command_center_drift_source_review_zip"),
            source_review_verification_report_path=payload.get("unified_command_center_drift_source_review_verification_report"),
            recheck_review_zip_path=payload.get("unified_command_center_drift_recheck_review") or payload.get("unified_command_center_drift_recheck_review_zip"),
            recheck_review_verification_report_path=payload.get("unified_command_center_drift_recheck_review_verification_report"),
            change_request_binding_report_path=payload.get("unified_command_center_drift_change_request_binding_report"),
            archive_zip_path=payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip"),
            archive_verification_report_path=payload.get("unified_command_center_archive_verification_report"),
            handoff_zip_path=payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip"),
            handoff_verification_report_path=payload.get("unified_command_center_handoff_verification_report"),
            command_center_zip_path=payload.get("unified_command_center_zip") or payload.get("unified_command_center"),
            command_center_verification_report_path=payload.get("unified_command_center_verification_report"),
            signoff_binding_path=payload.get("unified_command_center_signoff_binding"),
        )
        if unified_command_center_drift_response_gate and require_unified_command_center_drift_response:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_drift_response"] = unified_command_center_drift_response_gate
            if unified_command_center_drift_response_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_drift_response_gate.get("message") or "Unified Command Center Drift Response gate failed.")
        require_unified_command_center_evidence_review = bool(payload.get("require_unified_command_center_evidence_review", False))
        unified_command_center_evidence_review_gate = self.unified_command_center_evidence_review_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_evidence_review,
            review_id=payload.get("unified_command_center_evidence_review_id"),
            review_zip_path=payload.get("unified_command_center_evidence_review") or payload.get("unified_command_center_evidence_review_zip"),
            review_verification_report_path=payload.get("unified_command_center_evidence_review_verification_report"),
            require_accepted=bool(payload.get("require_unified_command_center_evidence_review_accepted", False)),
            acceptance_zip_path=payload.get("unified_command_center_evidence_review_acceptance") or payload.get("unified_command_center_evidence_review_acceptance_zip"),
            acceptance_verification_report_path=payload.get("unified_command_center_evidence_review_acceptance_verification_report"),
            acceptance_response_verification_report_path=payload.get("unified_command_center_evidence_review_acceptance_response_verification_report"),
            payload=payload,
        )
        if unified_command_center_evidence_review_gate and require_unified_command_center_evidence_review:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_evidence_review"] = unified_command_center_evidence_review_gate
            if unified_command_center_evidence_review_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_evidence_review_gate.get("message") or "Unified Command Center Evidence Review gate failed.")
        require_unified_command_center_reviewer_decision_board = bool(payload.get("require_unified_command_center_reviewer_decision_board", False))
        unified_command_center_reviewer_decision_board_gate = self.unified_command_center_reviewer_decision_board_store.gate(
            str(payload.get("unified_command_center_id") or payload.get("unified_command_center_center_id") or "ucc-000001"),
            required=require_unified_command_center_reviewer_decision_board,
            board_id=payload.get("unified_command_center_reviewer_decision_board_id"),
            archive_zip_path=payload.get("unified_command_center_reviewer_decision_board_archive") or payload.get("unified_command_center_reviewer_decision_board_zip"),
            verification_report_path=payload.get("unified_command_center_reviewer_decision_board_verification_report"),
            require_signed=bool(payload.get("require_unified_command_center_reviewer_decision_board_signed", True)),
            require_quorum=bool(payload.get("require_unified_command_center_reviewer_decision_board_quorum", True)),
            payload=payload,
        )
        if unified_command_center_reviewer_decision_board_gate and require_unified_command_center_reviewer_decision_board:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_reviewer_decision_board"] = unified_command_center_reviewer_decision_board_gate
            if unified_command_center_reviewer_decision_board_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_reviewer_decision_board_gate.get("message") or "Unified Command Center Reviewer Decision Board gate failed.")
        require_unified_command_center_release_train = bool(payload.get("require_unified_command_center_release_train", False))
        unified_command_center_release_train_gate = self.unified_command_center_release_train_store.gate(
            str(payload.get("unified_command_center_release_train_id") or "uct-000001"),
            required=require_unified_command_center_release_train,
            archive_zip_path=payload.get("unified_command_center_release_train_archive") or payload.get("unified_command_center_release_train_zip"),
            verification_report_path=payload.get("unified_command_center_release_train_verification_report"),
            external_evidence_manifest_path=payload.get("unified_command_center_release_train_external_evidence_manifest"),
            signoff_binding_path=payload.get("unified_command_center_release_train_signoff_binding"),
        )
        if unified_command_center_release_train_gate and require_unified_command_center_release_train:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_command_center_release_train"] = unified_command_center_release_train_gate
            if unified_command_center_release_train_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_command_center_release_train_gate.get("message") or "Unified Command Center Release Train gate failed.")
        require_unified_release_program_handoff = bool(payload.get("require_unified_release_program_handoff", False))
        unified_release_program_handoff_gate = self.unified_release_program_handoff_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_handoff_program_id") or "urp-000001"),
            required=require_unified_release_program_handoff,
            handoff_archive_zip_path=payload.get("unified_release_program_handoff_archive") or payload.get("unified_release_program_handoff_zip"),
            handoff_archive_verification_report_path=payload.get("unified_release_program_handoff_verification_report"),
            external_evidence_manifest=payload.get("unified_release_program_handoff_external_evidence_manifest"),
            handoff_signoff_binding=payload.get("unified_release_program_handoff_signoff_binding"),
        )
        if unified_release_program_handoff_gate and require_unified_release_program_handoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_handoff"] = unified_release_program_handoff_gate
            if unified_release_program_handoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_handoff_gate.get("message") or "Unified Release Program Handoff gate failed.")
        require_unified_release_program_vault = bool(payload.get("require_unified_release_program_vault", False))
        unified_release_program_vault_gate = self.unified_release_program_vault_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_vault_program_id") or "urp-000001"),
            required=require_unified_release_program_vault,
            vault_zip_path=payload.get("unified_release_program_vault") or payload.get("unified_release_program_vault_zip"),
            vault_verification_report_path=payload.get("unified_release_program_vault_verification_report"),
            vault_anchor_path=payload.get("unified_release_program_vault_anchor"),
            require_current_program=bool(payload.get("unified_release_program_vault_require_current_program", False)),
            require_current_operations=bool(payload.get("unified_release_program_vault_require_current_operations", False)),
            require_current_handoff=bool(payload.get("unified_release_program_vault_require_current_handoff", False)),
            require_accepted_evidence=bool(payload.get("unified_release_program_vault_require_accepted_evidence", True)),
        )
        if unified_release_program_vault_gate and require_unified_release_program_vault:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_vault"] = unified_release_program_vault_gate
            if unified_release_program_vault_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_vault_gate.get("message") or "Unified Release Program Evidence Vault gate failed.")
        require_unified_release_program_vault_operations = bool(payload.get("require_unified_release_program_vault_operations", False))
        unified_release_program_vault_operations_gate = self.unified_release_program_vault_operations_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_vault_operations_program_id") or "urp-000001"),
            required=require_unified_release_program_vault_operations,
            archive_zip_path=payload.get("unified_release_program_vault_operations") or payload.get("unified_release_program_vault_operations_archive"),
            verification_report_path=payload.get("unified_release_program_vault_operations_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_vault_operations_signoff_binding"),
        )
        if unified_release_program_vault_operations_gate and require_unified_release_program_vault_operations:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_vault_operations"] = unified_release_program_vault_operations_gate
            if unified_release_program_vault_operations_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_vault_operations_gate.get("message") or "Unified Release Program Vault Operations gate failed.")
        require_unified_release_program_continuity = bool(payload.get("require_unified_release_program_continuity", False))
        unified_release_program_continuity_gate = self.unified_release_program_continuity_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity,
            archive_zip_path=payload.get("unified_release_program_continuity") or payload.get("unified_release_program_continuity_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_continuity_signoff_binding"),
            vault_operations_archive_path=payload.get("unified_release_program_vault_operations") or payload.get("unified_release_program_vault_operations_archive"),
            vault_operations_verification_report_path=payload.get("unified_release_program_vault_operations_verification_report"),
            vault_operations_signoff_binding_path=payload.get("unified_release_program_vault_operations_signoff_binding"),
        )
        if unified_release_program_continuity_gate and require_unified_release_program_continuity:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity"] = unified_release_program_continuity_gate
            if unified_release_program_continuity_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_gate.get("message") or "Unified Release Program Continuity gate failed.")
        require_unified_release_program_continuity_kit = bool(payload.get("require_unified_release_program_continuity_kit", False))
        unified_release_program_continuity_kit_gate = self.unified_release_program_continuity_distribution_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_kit_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_kit,
            kit_zip_path=payload.get("unified_release_program_continuity_kit") or payload.get("unified_release_program_continuity_kit_zip"),
            verification_report_path=payload.get("unified_release_program_continuity_kit_verification_report"),
            receiver_receipt_path=payload.get("unified_release_program_continuity_kit_receiver_receipt"),
            require_receiver_receipt=bool(payload.get("require_unified_release_program_continuity_kit_receiver_receipt", False)),
        )
        if unified_release_program_continuity_kit_gate and require_unified_release_program_continuity_kit:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_kit"] = unified_release_program_continuity_kit_gate
            if unified_release_program_continuity_kit_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_kit_gate.get("message") or "Unified Release Program Continuity Distribution Kit gate failed.")
        require_unified_release_program_continuity_acceptance = bool(payload.get("require_unified_release_program_continuity_acceptance", False))
        unified_release_program_continuity_acceptance_gate = self.unified_release_program_continuity_acceptance_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_acceptance_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_acceptance,
            archive_zip_path=payload.get("unified_release_program_continuity_acceptance") or payload.get("unified_release_program_continuity_acceptance_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_acceptance_verification_report"),
            continuity_kit=payload.get("unified_release_program_continuity_kit") or payload.get("unified_release_program_continuity_kit_zip"),
            continuity_kit_verification_report=payload.get("unified_release_program_continuity_kit_verification_report"),
            signoff_binding=payload.get("unified_release_program_continuity_acceptance_signoff_binding"),
        )
        if unified_release_program_continuity_acceptance_gate and require_unified_release_program_continuity_acceptance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_acceptance"] = unified_release_program_continuity_acceptance_gate
            if unified_release_program_continuity_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_acceptance_gate.get("message") or "Unified Release Program Continuity Acceptance gate failed.")
        require_unified_release_program_continuity_command_center = bool(payload.get("require_unified_release_program_continuity_command_center", False))
        unified_release_program_continuity_command_center_gate = self.unified_release_program_continuity_command_center_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center,
            command_center_zip_path=payload.get("unified_release_program_continuity_command_center") or payload.get("unified_release_program_continuity_command_center_zip"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_verification_report"),
            evidence_manifest_path=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_gate and require_unified_release_program_continuity_command_center:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center"] = unified_release_program_continuity_command_center_gate
            if unified_release_program_continuity_command_center_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_gate.get("message") or "Unified Release Program Continuity Command Center gate failed.")
        require_unified_release_program_continuity_command_center_signoff = bool(payload.get("require_unified_release_program_continuity_command_center_signoff", False))
        unified_release_program_continuity_command_center_signoff_gate = self.unified_release_program_continuity_command_center_signoff_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center_signoff,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            archive_verification_report_path=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            signoff_binding_path=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center_zip_path=payload.get("unified_release_program_continuity_command_center") or payload.get("unified_release_program_continuity_command_center_zip"),
            command_center_verification_report_path=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_external_evidence_manifest_path=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_signoff_gate and require_unified_release_program_continuity_command_center_signoff:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_signoff"] = unified_release_program_continuity_command_center_signoff_gate
            if unified_release_program_continuity_command_center_signoff_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_signoff_gate.get("message") or "Unified Release Program Continuity Command Center signoff gate failed.")
        require_unified_release_program_continuity_command_center_acceptance = bool(payload.get("require_unified_release_program_continuity_command_center_acceptance", False))
        unified_release_program_continuity_command_center_acceptance_gate = self.unified_release_program_continuity_command_center_acceptance_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_unified_release_program_continuity_command_center_acceptance,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_acceptance_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_acceptance_verification_report"),
            acceptance_signoff_binding=payload.get("unified_release_program_continuity_command_center_acceptance_signoff_binding"),
            review_pack=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack"),
            review_pack_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack_verification_report"),
            accepted_evidence_dir=payload.get("unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir"),
            response_proof_dir=payload.get("unified_release_program_continuity_command_center_acceptance_response_proof_dir"),
            command_center_signoff_archive=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            command_center_signoff_archive_verification_report=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            command_center_final_handoff=payload.get("unified_release_program_continuity_command_center_final_handoff"),
            command_center_final_handoff_verification_report=payload.get("unified_release_program_continuity_command_center_final_handoff_verification_report"),
            command_center_signoff_binding=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center=payload.get("unified_release_program_continuity_command_center"),
            command_center_verification_report=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_evidence_manifest=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if unified_release_program_continuity_command_center_acceptance_gate and require_unified_release_program_continuity_command_center_acceptance:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_acceptance"] = unified_release_program_continuity_command_center_acceptance_gate
            if unified_release_program_continuity_command_center_acceptance_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(unified_release_program_continuity_command_center_acceptance_gate.get("message") or "Unified Release Program Continuity Command Center Receiver Acceptance gate failed.")
        require_receiver_acceptance_change = bool(
            payload.get("require_unified_release_program_continuity_command_center_acceptance_change_control", False)
        )
        receiver_acceptance_change_gate = self.unified_release_program_continuity_command_center_acceptance_change_store.gate(
            str(payload.get("unified_release_program_id") or payload.get("unified_release_program_continuity_command_center_program_id") or "urp-000001"),
            required=require_receiver_acceptance_change,
            archive_zip_path=payload.get("unified_release_program_continuity_command_center_acceptance_change_archive"),
            verification_report_path=payload.get("unified_release_program_continuity_command_center_acceptance_change_verification_report"),
            acceptance_archive=payload.get("unified_release_program_continuity_command_center_acceptance_archive"),
            acceptance_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_verification_report"),
            acceptance_signoff_binding=payload.get("unified_release_program_continuity_command_center_acceptance_signoff_binding"),
            previous_acceptance_root=payload.get("unified_release_program_continuity_command_center_acceptance_previous_root"),
            review_pack=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack"),
            review_pack_verification_report=payload.get("unified_release_program_continuity_command_center_acceptance_review_pack_verification_report"),
            accepted_evidence_dir=payload.get("unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir"),
            response_proof_dir=payload.get("unified_release_program_continuity_command_center_acceptance_response_proof_dir"),
            command_center_signoff_archive=payload.get("unified_release_program_continuity_command_center_signoff_archive"),
            command_center_signoff_archive_verification_report=payload.get("unified_release_program_continuity_command_center_signoff_verification_report"),
            command_center_final_handoff=payload.get("unified_release_program_continuity_command_center_final_handoff"),
            command_center_final_handoff_verification_report=payload.get("unified_release_program_continuity_command_center_final_handoff_verification_report"),
            command_center_signoff_binding=payload.get("unified_release_program_continuity_command_center_signoff_binding"),
            command_center=payload.get("unified_release_program_continuity_command_center"),
            command_center_verification_report=payload.get("unified_release_program_continuity_command_center_verification_report"),
            command_center_evidence_manifest=payload.get("unified_release_program_continuity_command_center_external_evidence_manifest"),
        )
        if receiver_acceptance_change_gate and require_receiver_acceptance_change:
            acceptance_gate = dict(acceptance_gate or {})
            acceptance_gate["unified_release_program_continuity_command_center_acceptance_change_control"] = receiver_acceptance_change_gate
            if receiver_acceptance_change_gate.get("status") == "failed":
                acceptance_gate["status"] = "failed"
                acceptance_gate["message"] = str(
                    receiver_acceptance_change_gate.get("message")
                    or "Receiver Acceptance Change Control gate failed."
                )
        if audio_gate.get("hard_block") and audio_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(audio_gate.get("message") or "Release audio gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if mastering_gate.get("hard_block") and mastering_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(mastering_gate.get("message") or "Mastering QA gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if encoded_gate.get("hard_block") and encoded_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(encoded_gate.get("message") or "Encoded audio gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if encoded_acceptance_gate.get("hard_block") and encoded_acceptance_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(encoded_acceptance_gate.get("message") or "Encoded audio acceptance gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if format_decision_gate.get("hard_block") and format_decision_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(format_decision_gate.get("message") or "Format decision gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if rights_gate.get("hard_block") and rights_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(rights_gate.get("message") or "Rights clearance gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if audio_campaign_gate.get("hard_block") and audio_campaign_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(audio_campaign_gate.get("message") or "Audio Campaign gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if audio_campaign_remediation_gate.get("hard_block") and audio_campaign_remediation_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(audio_campaign_remediation_gate.get("message") or "Audio Campaign remediation gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_certification_gate.get("hard_block") and release_audio_certification_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_certification_gate.get("message") or "Release Audio Certification gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_timeline_gate.get("hard_block") and release_audio_timeline_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_timeline_gate.get("message") or "Release Audio Timeline gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_regression_gate.get("hard_block") and release_audio_regression_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_regression_gate.get("message") or "Release Audio Regression gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_baseline_governance_gate.get("hard_block") and release_audio_baseline_governance_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_baseline_governance_gate.get("message") or "Release Audio Baseline Governance gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_regression_response_gate.get("hard_block") and release_audio_regression_response_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_regression_response_gate.get("message") or "Release Audio Regression Response gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_quality_observatory_gate.get("hard_block") and release_audio_quality_observatory_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_quality_observatory_gate.get("message") or "Release Audio Quality Observatory gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_quality_action_queue_gate.get("hard_block") and release_audio_quality_action_queue_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_quality_action_queue_gate.get("message") or "Release Audio Quality Action Queue gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_quality_action_queue_signoff_gate.get("hard_block") and release_audio_quality_action_queue_signoff_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_quality_action_queue_signoff_gate.get("message") or "Release Audio Quality Action Queue signoff gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if release_audio_command_center_gate.get("hard_block") and release_audio_command_center_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(release_audio_command_center_gate.get("message") or "Release Audio Command Center gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_gate.get("hard_block") and unified_command_center_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_gate.get("message") or "Unified Command Center gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_continuous_review_gate.get("hard_block") and unified_command_center_continuous_review_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_continuous_review_gate.get("message") or "Unified Command Center Continuous Review gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_drift_response_gate.get("hard_block") and unified_command_center_drift_response_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_drift_response_gate.get("message") or "Unified Command Center Drift Response gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_evidence_review_gate.get("hard_block") and unified_command_center_evidence_review_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_evidence_review_gate.get("message") or "Unified Command Center Evidence Review gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_reviewer_decision_board_gate.get("hard_block") and unified_command_center_reviewer_decision_board_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_reviewer_decision_board_gate.get("message") or "Unified Command Center Reviewer Decision Board gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_command_center_release_train_gate.get("hard_block") and unified_command_center_release_train_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_command_center_release_train_gate.get("message") or "Unified Command Center Release Train gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_handoff_gate.get("hard_block") and unified_release_program_handoff_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_handoff_gate.get("message") or "Unified Release Program Handoff gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_vault_gate.get("hard_block") and unified_release_program_vault_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_vault_gate.get("message") or "Unified Release Program Evidence Vault gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_vault_operations_gate.get("hard_block") and unified_release_program_vault_operations_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_vault_operations_gate.get("message") or "Unified Release Program Vault Operations gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_gate.get("hard_block") and unified_release_program_continuity_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_gate.get("message") or "Unified Release Program Continuity gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_kit_gate.get("hard_block") and unified_release_program_continuity_kit_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_kit_gate.get("message") or "Unified Release Program Continuity Distribution Kit gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_acceptance_gate.get("hard_block") and unified_release_program_continuity_acceptance_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_acceptance_gate.get("message") or "Unified Release Program Continuity Acceptance gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_command_center_gate.get("hard_block") and unified_release_program_continuity_command_center_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_command_center_gate.get("message") or "Unified Release Program Continuity Command Center gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_command_center_signoff_gate.get("hard_block") and unified_release_program_continuity_command_center_signoff_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_command_center_signoff_gate.get("message") or "Unified Release Program Continuity Command Center signoff gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if unified_release_program_continuity_command_center_acceptance_gate.get("hard_block") and unified_release_program_continuity_command_center_acceptance_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(unified_release_program_continuity_command_center_acceptance_gate.get("message") or "Unified Release Program Continuity Command Center Receiver Acceptance gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        if receiver_acceptance_change_gate.get("hard_block") and receiver_acceptance_change_gate.get("status") == "failed":
            self._send_json(
                {
                    "error": str(receiver_acceptance_change_gate.get("message") or "Receiver Acceptance Change Control gate failed."),
                    "acceptance_gate": acceptance_gate,
                },
                status=HTTPStatus.CONFLICT,
            )
            return
        hard_gate = acceptance_gate.get("planning_rule_impact") if isinstance(acceptance_gate.get("planning_rule_impact"), dict) else {}
        if hard_gate.get("hard_block") and hard_gate.get("status") == "failed":
            self._send_error(HTTPStatus.CONFLICT, str(hard_gate.get("message") or "Planning Rule Impact gate failed."))
            return
        if acceptance_gate.get("status") == "failed" and not force:
            self._send_error(HTTPStatus.CONFLICT, str(acceptance_gate.get("message") or "Acceptance release gate failed."))
            return
        if not release_qa_allows_signoff(report) and not force:
            self._send_error(HTTPStatus.CONFLICT, "Release QA gate failed. Refresh QA or pass force=true with override_reason.")
            return
        if force and not str(payload.get("override_reason") or "").strip():
            self._send_error(HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
            return
        try:
            export_manifest = read_release_export_manifest(self.release_store, release_id)
        except FileNotFoundError:
            export_manifest = {}
        if require_mastering_qa:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            mastering_export_gate = self._release_mastering_export_gate(export_manifest, mastering_gate)
            if mastering_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["mastering_export"] = mastering_export_gate
                self._send_json(
                    {
                        "error": str(mastering_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_encoded_audio:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            encoded_export_gate = self._release_encoded_audio_export_gate(export_manifest, encoded_gate)
            if encoded_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["encoded_audio_export"] = encoded_export_gate
                self._send_json(
                    {
                        "error": str(encoded_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_encoded_audio_review:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_format_decision:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            format_decision_export_gate = self._release_format_decision_export_gate(export_manifest, format_decision_gate)
            if format_decision_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["format_decision_export"] = format_decision_export_gate
                self._send_json(
                    {
                        "error": str(format_decision_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            encoded_acceptance_export_gate = self._release_encoded_audio_acceptance_export_gate(export_manifest, encoded_acceptance_gate)
            if encoded_acceptance_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["encoded_audio_acceptance_export"] = encoded_acceptance_export_gate
                self._send_json(
                    {
                        "error": str(encoded_acceptance_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if require_rights_clearance:
            if not export_manifest:
                self._send_json(
                    {
                        "error": "Release Export has not been generated.",
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
            rights_export_gate = self._release_rights_clearance_export_gate(export_manifest, rights_gate)
            if rights_export_gate.get("status") == "failed":
                acceptance_gate = dict(acceptance_gate or {})
                acceptance_gate["rights_clearance_export"] = rights_export_gate
                self._send_json(
                    {
                        "error": str(rights_export_gate.get("message") or "Release Export is stale. Rebuild export before signoff."),
                        "acceptance_gate": acceptance_gate,
                    },
                    status=HTTPStatus.CONFLICT,
                )
                return
        if not export_manifest and not force:
            self._send_error(HTTPStatus.CONFLICT, "Release Export has not been generated.")
            return
        if export_manifest and not force:
            if export_manifest.get("source_hash") != report.get("source_hash"):
                self._send_error(HTTPStatus.CONFLICT, "Release Export is stale. Rebuild export before signoff.")
                return
            zip_summary = export_manifest.get("zip") if isinstance(export_manifest.get("zip"), dict) else {}
            zip_path = self.release_store.zip_path(release_id)
            if bool(payload.get("require_zip", True)) and not (zip_path.exists() and zip_path.is_file() and not zip_path.is_symlink() and zip_summary.get("entry_count")):
                self._send_error(HTTPStatus.CONFLICT, "Release ZIP has not been generated.")
                return
        try:
            pending_signoff = build_release_signoff_record(release=document, report=report, payload={**payload, "force": force}, export_manifest={}, now=_utc_now())
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        if acceptance_gate:
            pending_signoff["acceptance_gate"] = acceptance_gate
        self.release_store.write_signoff(release_id, {**pending_signoff, "export_manifest_hash": None})
        try:
            final_manifest = refresh_release_export_signoff_summary(self.release_store, release_id)
            final_manifest.pop("zip", None)
            final_hash = stable_hash(final_manifest)
            signoff = {**pending_signoff, "export_manifest_hash": final_hash}
            signoff = self.release_store.write_signoff(release_id, signoff)
            refresh_release_export_signoff_summary(self.release_store, release_id)
            build_release_export_zip(self.release_store, release_id, now=_utc_now(), allow_signed=True)
        except FileNotFoundError:
            signoff = self.release_store.write_signoff(release_id, pending_signoff)
        document = self.release_store.update_signoff_summary(release_id, release_signoff_summary(signoff))
        self.release_store.append_event(release_id, "release_force_signed" if force else "release_signed", {"status": report.get("status"), "forced": force})
        self._send_json({"ok": True, "release": document.to_dict(), "signoff": signoff, "summary": release_signoff_summary(signoff)})

    def _release_mix_gate(self, release_id: str, *, require_stem_health: bool, require_current_mix: bool) -> dict[str, Any]:
        if not (require_stem_health or require_current_mix):
            return {}
        try:
            document = self.release_store.get_release(release_id)
        except Exception as exc:
            return {"status": "failed", "message": f"Release is unavailable: {sanitize_sensitive_text(str(exc))}"}
        tracks: list[dict[str, Any]] = []
        blockers: list[str] = []
        for track in document.tracks:
            project_dir = self.project_store.project_dir(track.project_id)
            export_dir = final_export_dir(project_dir)
            mix_state_path = export_dir / "mix-state.json"
            song_plan_path = export_dir / "song-plan.json"
            midi_path = export_dir / "song.mid"
            stem_health_path = export_dir / "stems" / "stem-health.json"
            mix_state = read_json(mix_state_path) if mix_state_path.exists() else {}
            stem_report = read_json(stem_health_path) if stem_health_path.exists() else {}
            mix_ok = bool(mix_state) and mix_state_integrity_ok(mix_state)
            mix_stale_reasons: list[str] = []
            plan: SongPlan | None = None
            try:
                plan = SongPlan.from_dict(read_json(song_plan_path))
            except Exception:
                if require_current_mix or stem_report:
                    mix_stale_reasons.append("song_plan_unavailable")
            if not mix_state:
                mix_stale_reasons.append("mix_state_missing")
            elif not mix_ok:
                mix_stale_reasons.append("mix_state_integrity")
            elif plan is not None:
                try:
                    mix_stale_reasons.extend(mix_state_stale_reasons(mix_state, plan=plan, midi_path=midi_path))
                except Exception:
                    mix_stale_reasons.append("mix_state_source_unavailable")
            mix_stale_reasons = sorted(set(mix_stale_reasons))
            mix_current = mix_ok and not mix_stale_reasons
            if require_current_mix and not mix_current:
                blockers.append(f"{track.track_id}: current mix-state evidence is missing, tampered, or stale")
            stem_ok = False
            stem_summary = stem_health_summary(stem_report)
            try:
                current_source = None
                if stem_report and plan is not None:
                    current_source = stable_hash(stem_health_source_state(run_dir=export_dir, project_id=track.project_id, version_id=track.version_id, plan=plan, mix_state=mix_state if mix_current else None))
                stem_ok = stem_health_allows_signoff(stem_report, current_source_hash=current_source)
            except Exception:
                stem_ok = False
            if require_stem_health and not stem_ok:
                blockers.append(f"{track.track_id}: stem audio health is missing, stale, or failed")
            tracks.append(
                {
                    "track_id": track.track_id,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "mix_state_hash": mix_state_hash(mix_state) if mix_ok else None,
                    "mix_state_integrity_ok": mix_ok,
                    "mix_state_current": mix_current,
                    "mix_state_stale_reasons": mix_stale_reasons,
                    "stem_health": stem_summary,
                    "stem_health_integrity_ok": stem_health_integrity_ok(stem_report) if stem_report else False,
                    "stem_health_current": stem_ok,
                }
            )
        return {
            "status": "failed" if blockers else "passed",
            "require_stem_audio_health": require_stem_health,
            "require_current_mix_state": require_current_mix,
            "track_count": len(tracks),
            "tracks": tracks,
            "blockers": blockers,
            "message": "Release mix gate failed." if blockers else "Release mix gate passed.",
        }

    def _handle_release_signoff_reset(self, method: str, release_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
            return
        existing = self.release_store.read_signoff(release_id, default={})
        if not existing:
            self._send_json({"ok": True, "release_id": release_id, "summary": {"status": "not_signed"}})
            return
        event = release_signoff_history_event(existing, reason=reason, now=_utc_now())
        self.release_store.reset_signoff(release_id, event)
        self.release_store.append_event(release_id, "release_signoff_reset", {"reason": event.get("reason"), "previous_status": release_signoff_summary(existing).get("status")})
        self._send_json({"ok": True, "release_id": release_id, "summary": {"status": "reset"}, "history_event": event})

    def _handle_distribution_route(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                targets = self.distribution_store.list_targets(release_id)
                self._send_json(
                    {
                        "ok": True,
                        "release_id": release_id,
                        "summary": self.distribution_store.summary(release_id),
                        "targets": [target.to_dict() for target in targets],
                        "template_packs": self.distribution_template_store.list_templates(),
                        "events": self.distribution_store.read_events(release_id),
                    }
                )
                return

            if tail == "/targets":
                if method == "GET":
                    targets = self.distribution_store.list_targets(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "targets": [target.to_dict() for target in targets], "summary": self.distribution_store.summary(release_id), "template_packs": self.distribution_template_store.list_templates()})
                    return
                if method == "POST":
                    target = self.distribution_store.create_target(release_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "summary": distribution_target_summary(target)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail == "/artwork":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                rows = list_distribution_artwork(self.distribution_store, release_id)
                self._send_json({"ok": True, "release_id": release_id, "artwork": rows, "latest": rows[0] if rows else {}, "summary": distribution_artwork_summary(rows[0] if rows else {})})
                return

            if tail == "/artwork/import":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                artwork = import_distribution_artwork(self.distribution_store, release_id, self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "artwork": artwork, "summary": distribution_artwork_summary(artwork)}, status=HTTPStatus.CREATED)
                return

            artwork_route = _match_distribution_artwork_tail(tail)
            if artwork_route is not None:
                artwork_id, action = artwork_route
                if action == "":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    artwork = read_distribution_artwork(self.distribution_store, release_id, artwork_id)
                    self._send_json({"ok": True, "release_id": release_id, "artwork": artwork, "summary": distribution_artwork_summary(artwork)})
                    return
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    artwork = read_distribution_artwork(self.distribution_store, release_id, artwork_id)
                    path = distribution_artwork_file_path(self.distribution_store, release_id, artwork)
                    self._send_file(path, str(artwork.get("media_type") or "application/octet-stream"), filename=str(artwork.get("stored_filename") or path.name))
                    return
                if action == "delete":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = delete_distribution_artwork(self.distribution_store, release_id, artwork_id)
                    self._send_json({"ok": True, **result})
                    return

            target_route = _match_distribution_target_tail(tail)
            if target_route is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Distribution route not found.")
                return
            target_id, action = target_route
            target = self.distribution_store.get_target(release_id, target_id)
            if action == "":
                if method == "GET":
                    signoff = self.distribution_store.read_signoff(release_id, target, default={})
                    qa = self._get_or_refresh_distribution_qa(release_id, target, refresh=False)
                    template = self.distribution_store.resolve_target_template(target)
                    checklist = reconcile_distribution_checklist(self.distribution_store, release_id, target, template, write=False) if template else read_distribution_checklist(self.distribution_store, release_id, target_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "template": template, "template_summary": template_summary(template) if template else {}, "checklist": checklist, "checklist_summary": checklist_summary(checklist), "summary": distribution_target_summary(target), "qa_summary": distribution_qa_summary(qa), "signoff_summary": distribution_signoff_summary(signoff)})
                    return
                if method in {"POST", "PATCH"}:
                    target = self.distribution_store.update_target(release_id, target_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "summary": distribution_target_summary(target)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.distribution_store.delete_target(release_id, target_id)})
                return
            if action == "qa":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_distribution_qa(release_id, target, refresh=False)
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "distribution_qa": report, "summary": distribution_qa_summary(report)})
                return
            if action == "checklist":
                template = self.distribution_store.resolve_target_template(target)
                if method == "GET":
                    checklist = reconcile_distribution_checklist(self.distribution_store, release_id, target, template, write=False) if template else read_distribution_checklist(self.distribution_store, release_id, target_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "checklist": checklist, "summary": checklist_summary(checklist)})
                    return
                if method == "POST":
                    if not template:
                        self._send_error(HTTPStatus.BAD_REQUEST, "Distribution target has no template_pack_id.")
                        return
                    checklist = initialize_distribution_checklist(self.distribution_store, release_id, target, template, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "checklist": checklist, "summary": checklist_summary(checklist)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "layout":
                if method not in {"GET", "POST"}:
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                layout = self._build_distribution_layout(release_id, target)
                if method == "POST":
                    layout = self.distribution_store.write_layout(release_id, target_id, layout)
                    self.distribution_store.append_event(release_id, "distribution_layout_refreshed", {"target_id": target_id, "status": layout.get("summary", {}).get("status")})
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "layout": layout, "summary": layout_summary(layout)})
                return
            if action.startswith("checklist-item:"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.distribution_store.resolve_target_template(target)
                if not template:
                    self._send_error(HTTPStatus.BAD_REQUEST, "Distribution target has no template_pack_id.")
                    return
                item_id = action.split(":", 1)[1]
                checklist = update_distribution_checklist_item(self.distribution_store, release_id, target, template, item_id, self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "checklist": checklist, "summary": checklist_summary(checklist)})
                return
            if action == "qa-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.distribution_store.ensure_target_mutable(release_id, target)
                report = self._get_or_refresh_distribution_qa(release_id, target, refresh=True)
                self.distribution_store.append_event(release_id, "distribution_qa_refreshed", {"target_id": target_id, "status": report.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "distribution_qa": report, "summary": distribution_qa_summary(report)})
                return
            if action == "export":
                if method == "GET":
                    package_id = self.distribution_store.latest_package_id(target)
                    if not package_id:
                        self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "manifest": {}, "summary": distribution_export_summary({})})
                        return
                    manifest = read_distribution_export_manifest(self.distribution_store, release_id, package_id)
                    self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "manifest": manifest, "summary": distribution_export_summary(manifest)})
                    return
                if method == "POST":
                    self.distribution_store.ensure_target_mutable(release_id, target)
                    report = self._get_or_refresh_distribution_qa(release_id, target, refresh=False)
                    manifest = build_distribution_export_package(store=self.distribution_store, release_id=release_id, target=target, qa_report=report, now=_utc_now())
                    target = self.distribution_store.get_target(release_id, target_id)
                    self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "manifest": manifest, "summary": distribution_export_summary(manifest), "layout_summary": layout_summary(manifest.get("layout") if isinstance(manifest.get("layout"), dict) else {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "export-zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.distribution_store.ensure_target_mutable(release_id, target)
                zip_info = build_distribution_package_zip(self.distribution_store, release_id, target, now=_utc_now())
                target = self.distribution_store.get_target(release_id, target_id)
                package_id = self.distribution_store.latest_package_id(target)
                manifest = read_distribution_export_manifest(self.distribution_store, release_id, package_id) if package_id else {}
                self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "zip": zip_info, "summary": distribution_export_summary(manifest)})
                return
            if action == "export-zip-download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                package_id = self.distribution_store.latest_package_id(target)
                if not package_id:
                    self._send_error(HTTPStatus.NOT_FOUND, "Distribution package ZIP not found.")
                    return
                self._send_file(self.distribution_store.package_zip_path(release_id, package_id), "application/zip", filename=f"musicforge-{release_id}-{target_id}-distribution.zip")
                return
            if action == "verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                package_id = self.distribution_store.latest_package_id(target)
                if not package_id:
                    self._send_error(HTTPStatus.NOT_FOUND, "Distribution package ZIP not found.")
                    return
                payload = self._optional_json_body()
                report = verify_distribution_package(
                    self.distribution_store.package_zip_path(release_id, package_id),
                    strict=bool(payload.get("strict", False)),
                    require_audio=bool(payload.get("require_audio", False)),
                    require_artwork=bool(payload.get("require_artwork", False)),
                    require_encoded_audio=bool(payload.get("require_encoded_audio", False)),
                    require_encoded_audio_review=bool(payload.get("require_encoded_audio_review", False)),
                )
                write_distribution_verification_report(report, self.distribution_store.package_dir(release_id, package_id) / "verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "verification": report, "summary": distribution_verification_summary(report)})
                return
            if action == "signoff":
                if method == "GET":
                    signoff = self.distribution_store.read_signoff(release_id, target, default={})
                    self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "signoff": signoff, "summary": distribution_signoff_summary(signoff)})
                    return
                if method == "POST":
                    self.distribution_store.ensure_target_mutable(release_id, target)
                    report = self._get_or_refresh_distribution_qa(release_id, target, refresh=True)
                    payload = self._optional_json_body()
                    require_encoded_review = bool(payload.get("require_encoded_audio_review", False) or (target.options or {}).get("require_encoded_audio_review", False))
                    require_format_decision = bool(payload.get("require_format_decision", False) or (target.options or {}).get("require_format_decision", False))
                    require_rights_clearance = bool(payload.get("require_rights_clearance", False) or (target.options or {}).get("require_rights_clearance", False))
                    if require_encoded_review:
                        template = self.distribution_store.resolve_target_template(target)
                        required_profiles = [
                            profile_id
                            for profile_id in resolve_target_audio_format_profiles(target, template)
                            if profile_id != "wav_master"
                        ]
                        encoded_acceptance_gate = self.encoded_audio_acceptance_store.gate(
                            release_id,
                            required_profiles=required_profiles,
                            required=True,
                            now=_utc_now(),
                        )
                        if encoded_acceptance_gate.get("hard_block") and encoded_acceptance_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(encoded_acceptance_gate.get("message") or "Encoded audio acceptance gate failed."), "encoded_audio_acceptance": encoded_acceptance_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        package_id = self.distribution_store.latest_package_id(target)
                        export_manifest = read_distribution_export_manifest(self.distribution_store, release_id, package_id) if package_id else {}
                        export_gate = self._distribution_encoded_audio_acceptance_export_gate(export_manifest, encoded_acceptance_gate)
                        if export_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(export_gate.get("message") or "Distribution Export is stale. Rebuild export before signoff."), "encoded_audio_acceptance": encoded_acceptance_gate, "encoded_audio_acceptance_export": export_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        payload = {**payload, "require_encoded_audio_review": True, "encoded_audio_acceptance": encoded_acceptance_gate}
                    if require_format_decision:
                        format_decision_gate = self.format_decision_store.distribution_gate(
                            release_id,
                            target,
                            required=True,
                            session_id=str(payload.get("format_decision_session_id") or "") or None,
                        )
                        if format_decision_gate.get("hard_block") and format_decision_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(format_decision_gate.get("message") or "Format decision gate failed."), "format_decision": format_decision_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        package_id = self.distribution_store.latest_package_id(target)
                        export_manifest = read_distribution_export_manifest(self.distribution_store, release_id, package_id) if package_id else {}
                        export_gate = self._distribution_format_decision_export_gate(export_manifest, format_decision_gate)
                        if export_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(export_gate.get("message") or "Distribution Export is stale. Rebuild export before signoff."), "format_decision": format_decision_gate, "format_decision_export": export_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        payload = {**payload, "require_format_decision": True, "format_decision": format_decision_gate}
                    if require_rights_clearance:
                        rights_gate = self.rights_clearance_store.gate(release_id, required=True, now=_utc_now())
                        if rights_gate.get("hard_block") and rights_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(rights_gate.get("message") or "Rights clearance gate failed."), "rights_clearance": rights_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        package_id = self.distribution_store.latest_package_id(target)
                        export_manifest = read_distribution_export_manifest(self.distribution_store, release_id, package_id) if package_id else {}
                        export_gate = self._package_rights_clearance_export_gate(export_manifest, rights_gate, package_label="Distribution")
                        if export_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(export_gate.get("message") or "Distribution Export is stale. Rebuild export before signoff."), "rights_clearance": rights_gate, "rights_clearance_export": export_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        payload = {**payload, "require_rights_clearance": True, "rights_clearance": rights_gate}
                    signoff = sign_distribution_package(store=self.distribution_store, release_id=release_id, target=target, qa_report=report, payload=payload, now=_utc_now())
                    target = self.distribution_store.get_target(release_id, target_id)
                    self._send_json({"ok": True, "release_id": release_id, "target": target.to_dict(), "signoff": signoff, "summary": distribution_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "signoff-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                if not reason:
                    self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
                    return
                event = self.distribution_store.reset_signoff(release_id, target_id, reason)
                self._send_json({"ok": True, "release_id": release_id, "target_id": target_id, "summary": {"status": "reset"}, "history_event": event})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Distribution target route not found.")
        except (ReleaseNotFoundError, DistributionNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (DistributionStateError, DistributionExportError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (DistributionChecklistError, DistributionValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _get_or_refresh_distribution_qa(self, release_id: str, target: Any, *, refresh: bool) -> dict[str, Any]:
        if not refresh:
            existing = self.distribution_store.read_qa(release_id, target.target_id, default={})
            if existing:
                release = self.release_store.get_release(release_id)
                current = stable_hash(distribution_source_state(store=self.distribution_store, release=release, target=target))
                if str(existing.get("source_hash") or "") != current:
                    return mark_distribution_qa_stale(existing, current_source_hash=current)
                return existing
        report = build_distribution_qa_report(store=self.distribution_store, release_id=release_id, target=target, now=_utc_now())
        report = self.distribution_store.write_qa(release_id, target.target_id, report)
        self.distribution_store.update_qa_summary(release_id, target.target_id, distribution_qa_summary(report))
        return report

    def _handle_submission_route(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    batches = self.submission_store.list_submissions(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "submissions": [self._submission_payload_with_evidence_summary(release_id, batch) for batch in batches], "summary": self.submission_store.summary(release_id)})
                    return
                if method == "POST":
                    batch = self.submission_store.create_submission(release_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if tail == "/batches" or tail == "":
                if method == "GET":
                    batches = self.submission_store.list_submissions(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "submissions": [self._submission_payload_with_evidence_summary(release_id, batch) for batch in batches], "summary": self.submission_store.summary(release_id)})
                    return
                if method == "POST":
                    batch = self.submission_store.create_submission(release_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            route = _match_submission_tail(tail)
            if route is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Submission route not found.")
                return
            submission_id, action, item_id = route
            batch = self.submission_store.get_submission(release_id, submission_id)
            if action == "":
                if method == "GET":
                    signoff = self.submission_store.read_signoff(release_id, submission_id, default={})
                    qa = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                    self._send_json({"ok": True, "release_id": release_id, "submission": self._submission_payload_with_evidence_summary(release_id, batch), "summary": submission_batch_summary(batch), "qa_summary": submission_qa_summary(qa), "signoff_summary": submission_signoff_summary(signoff), "events": self.submission_store.read_events(release_id, submission_id)})
                    return
                if method in {"POST", "PATCH"}:
                    batch = self.submission_store.update_submission(release_id, submission_id, self._optional_json_body())
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "targets":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                target_id = str(payload.get("target_id") or "").strip()
                if not target_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "target_id is required.")
                    return
                batch = self.submission_store.add_target(release_id, submission_id, target_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "remove-item":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.remove_target(release_id, submission_id, item_id or "")
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.refresh_items(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            if action == "qa":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "submission_qa": report, "summary": submission_qa_summary(report)})
                return

            if action == "qa-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.ensure_mutable(batch)
                report = self._get_or_refresh_submission_qa(release_id, batch, refresh=True)
                self.submission_store.append_event(release_id, submission_id, "submission_qa_refreshed", {"status": report.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "submission_qa": report, "summary": submission_qa_summary(report)})
                return

            if action == "export":
                if method == "GET":
                    try:
                        manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                    except FileNotFoundError:
                        self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": {}, "summary": submission_export_summary({})})
                        return
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": submission_export_summary(manifest)})
                    return
                if method == "POST":
                    self.submission_store.ensure_mutable(batch)
                    report = self._get_or_refresh_submission_qa(release_id, batch, refresh=False)
                    manifest = build_submission_export_bundle(store=self.submission_store, release_id=release_id, submission=batch, qa_report=report, now=_utc_now())
                    batch = self.submission_store.get_submission(release_id, submission_id)
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "manifest": manifest, "summary": submission_export_summary(manifest)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "export-zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.ensure_mutable(batch)
                zip_info = build_submission_package_zip(self.submission_store, release_id, batch, now=_utc_now())
                manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                batch = self.submission_store.update_export_summary(release_id, submission_id, submission_export_summary(manifest))
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "zip": zip_info, "summary": submission_export_summary(manifest)})
                return

            if action == "export-zip-download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.submission_store.get_submission(release_id, submission_id)
                self._send_file(self.submission_store.package_zip_path(release_id, submission_id), "application/zip", filename=f"musicforge-{release_id}-{submission_id}-submission.zip")
                return

            if action == "signoff":
                if method == "GET":
                    signoff = self.submission_store.read_signoff(release_id, submission_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_signoff_summary(signoff)})
                    return
                if method == "POST":
                    self.submission_store.ensure_mutable(batch)
                    report = self._get_or_refresh_submission_qa(release_id, batch, refresh=True)
                    payload = self._optional_json_body()
                    if bool(payload.get("require_rights_clearance", False)):
                        rights_gate = self.rights_clearance_store.gate(release_id, required=True, now=_utc_now())
                        if rights_gate.get("hard_block") and rights_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(rights_gate.get("message") or "Rights clearance gate failed."), "rights_clearance": rights_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        try:
                            export_manifest = read_submission_export_manifest(self.submission_store, release_id, submission_id)
                        except FileNotFoundError:
                            export_manifest = {}
                        export_gate = self._package_rights_clearance_export_gate(export_manifest, rights_gate, package_label="Submission")
                        if export_gate.get("status") == "failed":
                            self._send_json(
                                {"error": str(export_gate.get("message") or "Submission Export is stale. Rebuild export before signoff."), "rights_clearance": rights_gate, "rights_clearance_export": export_gate},
                                status=HTTPStatus.CONFLICT,
                            )
                            return
                        payload = {**payload, "require_rights_clearance": True, "rights_clearance": rights_gate}
                    signoff = sign_submission_package(store=self.submission_store, release_id=release_id, submission=batch, qa_report=report, payload=payload, now=_utc_now())
                    batch = self.submission_store.get_submission(release_id, submission_id)
                    self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "signoff": signoff, "summary": submission_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "signoff-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                if not reason:
                    self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
                    return
                event = self.submission_store.reset_signoff(release_id, submission_id, reason)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if action == "verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_submission_package(
                    self.submission_store.package_zip_path(release_id, submission_id),
                    strict=bool(payload.get("strict", False)),
                    require_submitted=bool(payload.get("require_submitted", False)),
                    require_accepted=bool(payload.get("require_accepted", False)),
                    deep=bool(payload.get("deep", False)),
                )
                write_submission_verification_report(report, self.submission_store.submission_dir(release_id, submission_id) / "submission-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "verification": report, "summary": submission_verification_summary(report)})
                return

            if action == "evidence":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                overview = self.submission_evidence_store.overview(release_id, submission_id)
                self._send_json({"ok": True, **overview})
                return

            if action == "evidence-report-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.submission_evidence_store.refresh_report(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "evidence_report": report, "summary": submission_evidence_report_summary(report)})
                return

            if action == "evidence-export":
                if method == "GET":
                    try:
                        manifest = self.submission_evidence_store.read_export_manifest(release_id, submission_id)
                    except SubmissionEvidenceNotFoundError:
                        self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": {}, "summary": {"status": "missing"}})
                        return
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": manifest.get("summary", {})})
                    return
                if method == "POST":
                    manifest = self.submission_evidence_store.export_evidence(release_id, submission_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "evidence-export-zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.submission_evidence_store.build_zip(release_id, submission_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "zip": zip_info})
                return

            if action == "evidence-export-zip-download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.submission_evidence_store.package_zip_path(release_id, submission_id), "application/zip", filename=f"musicforge-{release_id}-{submission_id}-submission-evidence.zip")
                return

            if action == "evidence-signoff":
                if method == "GET":
                    signoff = self.submission_evidence_store.read_signoff(release_id, submission_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_evidence_signoff_summary(signoff)})
                    return
                if method == "POST":
                    signoff = self.submission_evidence_store.signoff_evidence(release_id, submission_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "signoff": signoff, "summary": submission_evidence_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if action == "evidence-signoff-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                event = self.submission_evidence_store.reset_signoff(release_id, submission_id, reason)
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if action == "evidence-verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_submission_evidence_package(
                    self.submission_evidence_store.package_zip_path(release_id, submission_id),
                    strict=bool(payload.get("strict", False)),
                    deep=bool(payload.get("deep", False)),
                    require_submitted=bool(payload.get("require_submitted", False)),
                    require_accepted=bool(payload.get("require_accepted", False)),
                    require_rights_clearance=bool(payload.get("require_rights_clearance", False)),
                )
                write_submission_evidence_verification_report(report, self.submission_store.submission_dir(release_id, submission_id) / "submission-evidence-verification-report.json")
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "verification": report, "summary": submission_evidence_verification_summary(report)})
                return

            if action == "evidence-upload-attachment":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                attachment = self.submission_evidence_store.upload_attachment(release_id, submission_id, item_id or "", self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "item_id": item_id, "attachment": attachment}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-submission-receipt":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_submission(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-feedback":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_feedback(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-acceptance":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.mark_accepted(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)}, status=HTTPStatus.CREATED)
                return

            if action == "evidence-resubmission-round":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                round_record = self.submission_evidence_store.create_resubmission_round(release_id, submission_id, item_id or "", self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission_id": submission_id, "item_id": item_id, "round": round_record}, status=HTTPStatus.CREATED)
                return

            if action == "record-submission":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_submission(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "record-feedback":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.record_feedback(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "mark-accepted":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch, evidence = self.submission_evidence_store.mark_accepted(release_id, submission_id, item_id or "", self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "evidence": evidence, "summary": submission_batch_summary(batch)})
                return

            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                batch = self.submission_store.archive_submission(release_id, submission_id)
                self._send_json({"ok": True, "release_id": release_id, "submission": batch.to_dict(), "summary": submission_batch_summary(batch)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Submission route not found.")
        except (ReleaseNotFoundError, SubmissionNotFoundError, SubmissionEvidenceNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (SubmissionStateError, SubmissionEvidenceStateError, SubmissionExportError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (SubmissionValidationError, SubmissionEvidenceValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _get_or_refresh_submission_qa(self, release_id: str, batch: Any, *, refresh: bool) -> dict[str, Any]:
        if not refresh:
            existing = self.submission_store.read_qa(release_id, batch.submission_id, default={})
            if existing:
                current = stable_hash(submission_source_state(store=self.submission_store, release_id=release_id, submission=batch))
                if str(existing.get("source_hash") or "") != current:
                    return mark_submission_qa_stale(existing, current_source_hash=current)
                return existing
        report = build_submission_qa_report(store=self.submission_store, release_id=release_id, submission=batch, now=_utc_now())
        report = self.submission_store.write_qa(release_id, batch.submission_id, report)
        self.submission_store.update_qa_summary(release_id, batch.submission_id, submission_qa_summary(report))
        return report

    def _submission_payload_with_evidence_summary(self, release_id: str, batch: Any) -> dict[str, Any]:
        payload = batch.to_dict()
        try:
            overview = self.submission_evidence_store.overview(release_id, batch.submission_id)
            summary = overview.get("summary") if isinstance(overview.get("summary"), dict) else {}
            report_summary = overview.get("report_summary") if isinstance(overview.get("report_summary"), dict) else {}
            signoff_summary = overview.get("signoff_summary") if isinstance(overview.get("signoff_summary"), dict) else {}
            payload["latest_evidence_summary"] = {
                **summary,
                "status": report_summary.get("status") or summary.get("status") or "not_started",
                "signoff_status": signoff_summary.get("status") or summary.get("signoff_status") or "not_signed",
                "report_hash": report_summary.get("integrity_hash"),
            }
        except Exception:
            payload["latest_evidence_summary"] = {"status": "not_started", "signoff_status": "not_signed"}
        return payload

    def _build_distribution_layout(self, release_id: str, target: Any) -> dict[str, Any]:
        release = self.release_store.get_release(release_id)
        try:
            release_manifest = read_release_export_manifest(self.release_store, release_id)
        except FileNotFoundError:
            release_manifest = {}
        metadata = read_release_metadata(self.release_store, release_id, default={})
        template = self.distribution_store.resolve_target_template(target)
        artwork_id = str((target.options or {}).get("artwork_id") or "").strip()
        artwork = read_distribution_artwork(self.distribution_store, release_id, artwork_id) if artwork_id else latest_distribution_artwork(self.distribution_store, release_id)
        return build_distribution_layout_plan(
            release_id=release_id,
            target=target,
            release=release,
            release_manifest=release_manifest,
            release_metadata=metadata,
            template=template,
            artwork=artwork if isinstance(artwork, dict) else {},
            release_export_dir=self.release_store.export_dir(release_id),
        )
