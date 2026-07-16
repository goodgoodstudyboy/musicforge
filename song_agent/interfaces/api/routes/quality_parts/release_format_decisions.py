from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseFormatDecisions:
    def _handle_release_format_decisions(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    sessions = self.format_decision_store.list_sessions(release_id, include_archived=True)
                    active = self.format_decision_store.read_active_session(release_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "sessions": sessions, "active_session": active})
                    return
                if method == "POST":
                    session = self.format_decision_store.create_session(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Format decision route not found.")
                return
            session_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    session = self.format_decision_store.read_session(release_id, session_id)
                    matrix = self.format_decision_store.read_matrix(release_id, session_id, default={})
                    recommendation = self.format_decision_store.read_recommendation(release_id, session_id, default={})
                    report = self.format_decision_store.read_report(release_id, session_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "session": session, "matrix": matrix, "recommendation": recommendation, "report": report})
                    return
                if method == "DELETE":
                    session = self.format_decision_store.archive_session(release_id, session_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session})
                    return
            if len(parts) == 2 and parts[1] == "matrix":
                if method == "GET":
                    matrix = self.format_decision_store.read_matrix(release_id, session_id)
                    self._send_json({"ok": True, "release_id": release_id, "matrix": matrix})
                    return
                if method == "POST":
                    matrix = self.format_decision_store.build_matrix(release_id, session_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "matrix": matrix})
                    return
            if len(parts) == 2 and parts[1] == "recommend":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                recommendation = self.format_decision_store.build_recommendation(release_id, session_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "recommendation": recommendation})
                return
            if len(parts) == 2 and parts[1] == "recommendation":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                recommendation = self.format_decision_store.read_recommendation(release_id, session_id)
                self._send_json({"ok": True, "release_id": release_id, "recommendation": recommendation})
                return
            if len(parts) == 2 and parts[1] == "select":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.format_decision_store.select_profiles(release_id, session_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "session": session})
                return
            if len(parts) == 2 and parts[1] == "report":
                if method == "GET":
                    report = self.format_decision_store.read_report(release_id, session_id)
                    self._send_json({"ok": True, "release_id": release_id, "report": report})
                    return
                if method == "POST":
                    report = self.format_decision_store.build_report(release_id, session_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "report": report})
                    return
            if len(parts) == 2 and parts[1] == "activate":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                active = self.format_decision_store.activate_session(release_id, session_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "active_session": active})
                return
            if len(parts) == 2 and parts[1] == "gate":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.format_decision_store.gate(
                    release_id,
                    required=True,
                    session_id=session_id,
                    required_profiles=_interfaces_api_runtime.normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("profiles") or []),
                )
                self._send_json({"ok": True, "release_id": release_id, "gate": gate})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Format decision route not found.")
        except (_interfaces_api_runtime.ReleaseNotFoundError, _interfaces_api_runtime.FormatDecisionNotFoundError, FileNotFoundError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.ReleaseStateError, _interfaces_api_runtime.FormatDecisionStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.FormatDecisionError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_rights(self, method: str, release_id: str, tail: str) -> None:
        try:
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.rights_clearance_store.read_report(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "parties": self.rights_clearance_store.list_parties(release_id)})
                return
            if parts == ["refresh"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.rights_clearance_store.refresh_report(release_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "report": report})
                return
            if parts == ["gate"]:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                gate = self.rights_clearance_store.gate(release_id, required=True, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "gate": gate})
                return
            if parts == ["parties"]:
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "parties": self.rights_clearance_store.list_parties(release_id)})
                    return
                if method == "POST":
                    party = self.rights_clearance_store.upsert_party(release_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "party": party}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[0] == "parties":
                if method not in {"POST", "PATCH"}:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                party = self.rights_clearance_store.upsert_party(release_id, {**self._read_json_body(), "party_id": parts[1]}, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "party": party})
                return
            if len(parts) >= 2 and parts[0] == "tracks":
                track_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    if method == "GET":
                        record = self.rights_clearance_store.read_track(release_id, track_id, default={})
                        self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                        return
                    if method in {"POST", "PATCH"}:
                        record = self.rights_clearance_store.upsert_track(release_id, track_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                        return
                if action == "contributors":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    contributors = payload.get("contributors") if isinstance(payload.get("contributors"), list) else payload if isinstance(payload, list) else []
                    record = self.rights_clearance_store.upsert_track(release_id, track_id, {"contributors": contributors}, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "sources":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    sources = payload.get("source_usages") if isinstance(payload.get("source_usages"), list) else payload.get("sources") if isinstance(payload.get("sources"), list) else payload if isinstance(payload, list) else []
                    record = self.rights_clearance_store.upsert_track(release_id, track_id, {"source_usages": sources}, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "review":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    record = self.rights_clearance_store.review_track(release_id, track_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "reset-review":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    reason = str(payload.get("reason") or "").strip()
                    if not reason:
                        self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "reason is required.")
                        return
                    record = self.rights_clearance_store.reset_track_review(release_id, track_id, reason=reason, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Rights clearance route not found.")
        except (_interfaces_api_runtime.ReleaseNotFoundError, _interfaces_api_runtime.RightsClearanceNotFoundError, FileNotFoundError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.ReleaseStateError, _interfaces_api_runtime.RightsClearanceStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.RightsClearanceError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _job_audio_artifact_stale_reasons(self, job: JobState) -> list[str]:
        run_dir = _interfaces_api_runtime.Path(job.output_dir)
        wav_path = run_dir / "renders" / "song.wav"
        midi_path = run_dir / "renders" / "song.mid"
        plan_path = run_dir / "data" / "song-plan.json"
        manifest = _interfaces_api_runtime.read_audio_artifact_manifest(run_dir / "renders" / _interfaces_api_runtime.AUDIO_ARTIFACT_FILENAME, default={})
        profile = None
        renderer = manifest.get("renderer") if isinstance(manifest.get("renderer"), dict) else {}
        profile_id = str(renderer.get("profile_id") or "")
        if profile_id.startswith("arp-"):
            try:
                profile = self.audio_profile_store.get_profile(profile_id)
            except _interfaces_api_runtime.AudioProfileError:
                profile = None
        return _interfaces_api_runtime.audio_artifact_stale_reasons_for_profile(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=plan_path, profile=profile)

    def _release_mastering_export_gate(self, export_manifest: ImplementationDocument, mastering_gate: ImplementationDocument) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_mastering = export_manifest.get("mastering") if isinstance(export_manifest.get("mastering"), dict) else {}
        required_fields = ("analysis_hash", "plan_hash", "selected_candidate_id", "selected_candidate_hash")
        missing_fields = [field for field in required_fields if not manifest_mastering.get(field)]
        mismatched_fields = [
            field
            for field in required_fields
            if str(manifest_mastering.get(field) or "") != str(mastering_gate.get(field) or "")
        ]
        manifest_status = str(manifest_mastering.get("status") or "")
        if manifest_status not in {"passed", "warning"}:
            mismatched_fields.append("status")
        failed = bool(missing_fields or mismatched_fields)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current Mastering QA evidence.",
            "missing_fields": sorted(set(missing_fields)),
            "mismatched_fields": sorted(set(mismatched_fields)),
            "manifest_selected_candidate_id": manifest_mastering.get("selected_candidate_id"),
            "current_selected_candidate_id": mastering_gate.get("selected_candidate_id"),
            "manifest_status": manifest_status or "missing",
        }

    def _release_encoded_audio_export_gate(self, export_manifest: ImplementationDocument, encoded_gate: ImplementationDocument) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_encoded = export_manifest.get("encoded_audio") if isinstance(export_manifest.get("encoded_audio"), dict) else {}
        manifest_profiles = manifest_encoded.get("profiles") if isinstance(manifest_encoded.get("profiles"), list) else []
        by_profile = {str(row.get("profile_id") or ""): row for row in manifest_profiles if isinstance(row, dict)}
        missing: list[str] = []
        mismatched: list[str] = []
        for row in encoded_gate.get("profiles", []) if isinstance(encoded_gate.get("profiles"), list) else []:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "")
            manifest_row = by_profile.get(profile_id)
            if not manifest_row:
                missing.append(profile_id)
                continue
            for field in ("source_hash", "manifest_hash"):
                if str(manifest_row.get(field) or "") != str(row.get(field) or ""):
                    mismatched.append(f"{profile_id}:{field}")
            if str(manifest_row.get("status") or "") != "completed":
                mismatched.append(f"{profile_id}:status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current encoded audio evidence.",
            "missing_profiles": missing,
            "mismatched_profiles": sorted(set(mismatched)),
        }
