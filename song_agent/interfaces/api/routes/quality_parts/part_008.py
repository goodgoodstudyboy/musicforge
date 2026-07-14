from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class QualityRoutesPart008:
    def _handle_audio_quality_actions_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-quality-actions":
                if method == "GET":
                    rows = self.release_audio_quality_action_queue_store.list_queues()
                    self._send_json({"ok": True, "queues": rows, "summary": {"queue_count": len(rows)}})
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    queue = self.release_audio_quality_action_queue_store.create_from_observatory(
                        payload.get("observatory_id", ""),
                        name=payload.get("name"),
                        include_risks=bool(payload.get("include_risks", True)),
                        include_recommendations=bool(payload.get("include_recommendations", True)),
                        severity_floor=str(payload.get("severity_floor") or "warning"),
                        policy=payload.get("policy") if isinstance(payload.get("policy"), dict) else {},
                    )
                    self._send_json({"ok": True, "queue": queue, "summary": queue.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-quality-actions/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                queue_id = parts[0]
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_audio_quality_action_queue_store.read_queue(queue_id)
                summary = self.release_audio_quality_action_queue_store.read_summary(queue_id) if self.release_audio_quality_action_queue_store.summary_path(queue_id).exists() else {}
                self._send_json({"ok": True, "queue": queue, "summary_report": summary, "summary": summary.get("summary", {}) if summary else {}})
                return
            if len(parts) == 2:
                queue_id, action = parts
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_action_queue_store.zip_path(queue_id), "application/zip", filename="release-audio-quality-action-queue.zip")
                    return
                if action == "archive-download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_action_signoff_store.archive_zip_path(queue_id), "application/zip", filename="release-audio-quality-action-queue-signoff-archive.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if action == "refresh":
                    summary = self.release_audio_quality_action_queue_store.refresh_status(queue_id)
                    self._send_json({"ok": summary.get("status") != "stale", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")})
                    return
                if action == "run-safe":
                    result = self.release_audio_quality_action_queue_store.run_safe(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "export":
                    result = self.release_audio_quality_action_queue_store.export_package(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "zip":
                    result = self.release_audio_quality_action_queue_store.build_zip(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "verify":
                    report = self.release_audio_quality_action_queue_store.verify_zip(
                        queue_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_observatory=bool(payload.get("require_current_observatory", False)),
                        observatory_zip_path=payload.get("observatory_zip"),
                        observatory_verification_report_path=payload.get("observatory_verification_report"),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                        require_no_blocking=bool(payload.get("require_no_blocking", True)),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if action == "manual-items":
                    result = self.release_audio_quality_action_signoff_store.list_manual_items(queue_id)
                    self._send_json({"ok": True, **result, "status": "passed"})
                    return
                if action == "resolve-manual":
                    item_id = str(payload.get("item_id") or "")
                    result = self.release_audio_quality_action_signoff_store.resolve_manual_item(queue_id, item_id, payload)
                    self._send_json({"ok": True, "resolution": result, "status": "passed"})
                    return
                if action == "closeout":
                    closeout = self.release_audio_quality_action_signoff_store.refresh_closeout(queue_id)
                    self._send_json({"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                    return
                if action == "signoff":
                    result = self.release_audio_quality_action_signoff_store.signoff(queue_id, payload)
                    self._send_json({"ok": True, **result})
                    return
                if action == "archive":
                    result = self.release_audio_quality_action_signoff_store.export_archive(queue_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "archive-zip":
                    result = self.release_audio_quality_action_signoff_store.build_archive_zip(queue_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "archive-verify":
                    report = self.release_audio_quality_action_signoff_store.verify_archive(
                        queue_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_queue=bool(payload.get("require_current_queue", True)),
                        require_signed=bool(payload.get("require_signed", True)),
                        queue_zip_path=payload.get("queue_zip"),
                        queue_verification_report_path=payload.get("queue_verification_report"),
                        observatory_zip_path=payload.get("observatory_zip"),
                        observatory_verification_report_path=payload.get("observatory_verification_report"),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Action Queue route not found.")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Action Queue route not found.")
        except ReleaseAudioQualityActionQueueNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioQualityActionQueueStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioQualityActionQueueValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioQualityActionQueueSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioQualityActionQueueSignoffValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_mastering_profiles_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/mastering/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.mastering_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.mastering_profile_store.create_profile(self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/mastering/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.mastering_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.mastering_profile_store.update_profile(profile_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.mastering_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.mastering_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
        except MasteringProfileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except MasteringProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_encoding_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-encoding/config":
                if method == "GET":
                    self._send_json({"ok": True, "config": self.audio_encoding_store.read_config().public_summary()})
                    return
                if method == "POST":
                    config = self.audio_encoding_store.write_config(self._read_json_body())
                    self._send_json({"ok": True, "config": config})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path == "/api/audio-encoding/config/test":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.audio_encoding_store.test_config()})
                return
            if path == "/api/audio-encoding/config/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "config": self.audio_encoding_store.reset_config()})
                return
            if path == "/api/audio-encoding/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.audio_encoding_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.audio_encoding_profile_store.create_profile(self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-encoding/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.audio_encoding_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.audio_encoding_profile_store.update_profile(profile_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.audio_encoding_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.audio_encoding_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
        except AudioEncodingProfileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioEncodingProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
