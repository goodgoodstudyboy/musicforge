from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class DeliveryRoutesPart002:
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
