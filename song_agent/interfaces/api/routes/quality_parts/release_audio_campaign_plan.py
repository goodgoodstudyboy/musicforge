from __future__ import annotations

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAudioCampaignPlan(QualityRouteContext):
    def _handle_release_audio_campaign_plan(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                status = self.server.audio_campaign_planner_store.status(release_id)
                self._send_json({"ok": True, **status})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.server.audio_campaign_planner_store.refresh_plan(release_id, self._optional_json_body())
                self._send_json({"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("preflight_summary", {})})
                return
            if tail == "/preflight":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preflight = self.server.audio_campaign_planner_store.preflight(release_id, self._optional_json_body())
                self._send_json({"ok": preflight.get("status") == "passed", "preflight": preflight, "summary": preflight.get("summary", {})})
                return
            if tail == "/create":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.server.audio_campaign_planner_store.create_campaign_from_release(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("link", {}).get("coverage", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/status":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                status = self.server.audio_campaign_planner_store.status(release_id)
                self._send_json({"ok": status.get("status") != "failed", **status})
                return
            if tail == "/link":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                link = self.server.audio_campaign_planner_store.link_campaign(release_id, str(payload.get("campaign_id") or ""), payload)
                self._send_json({"ok": True, "link": link, "summary": link.get("coverage", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Campaign plan route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignPlannerNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignPlannerStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioCampaignPlannerValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioCampaignPlannerError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_campaign_remediation(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.read_plan(release_id, default={})
                queue = self.audio_campaign_remediation_store.read_queue(release_id, default={})
                closeout = self.audio_campaign_remediation_store.read_closeout(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "queue": queue, "closeout": closeout, "status": closeout.get("status") or plan.get("status") or "missing"})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.refresh_plan(release_id, self._optional_json_body())
                self._send_json({"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("summary", {})})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.run_safe_actions(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {})})
                return
            if tail == "/status":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.refresh_plan(release_id)
                queue = self.audio_campaign_remediation_store.build_action_queue(release_id)
                closeout = self.audio_campaign_remediation_store.closeout_report(release_id)
                self._send_json({"ok": closeout.get("status") == "passed", "plan": plan, "queue": queue, "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                return
            if tail == "/closeout":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.audio_campaign_remediation_store.closeout_report(release_id)
                self._send_json({"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.audio_campaign_remediation_store.verify_zip(release_id, strict=bool(payload.get("strict")), require_passed=bool(payload.get("require_passed", True)), require_signed=bool(payload.get("require_signed", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.audio_campaign_remediation_store.zip_path(release_id), "application/zip", filename="audio-campaign-remediation.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Campaign remediation route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignRemediationNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignRemediationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioCampaignRemediationValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioCampaignRemediationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_certification(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_certification_store.read_report(release_id, default={})
                matrix = self.release_audio_certification_store.read_matrix(release_id, default={})
                evidence = self.release_audio_certification_store.read_evidence_index(release_id, default={})
                blockers = self.release_audio_certification_store.read_blocker_register(release_id, default={})
                signoff = _interfaces_api_runtime.read_json(self.release_audio_certification_store.signoff_path(release_id)) if self.release_audio_certification_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "report": report, "matrix": matrix, "evidence_index": evidence, "blocker_register": blockers, "signoff": signoff, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_certification_store.refresh_report(release_id)
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {})})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_certification_store.verify_zip(
                    release_id,
                    strict=bool(payload.get("strict", True)),
                    require_passed=bool(payload.get("require_passed", True)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_real_audio=bool(payload.get("require_real_audio", True)),
                    require_manual_review=bool(payload.get("require_manual_review", True)),
                    require_remediation_when_needed=bool(payload.get("require_remediation_when_needed", True)),
                )
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_certification_store.zip_path(release_id), "application/zip", filename="release-audio-certification.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Certification route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCertificationNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCertificationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCertificationValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioCertificationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
