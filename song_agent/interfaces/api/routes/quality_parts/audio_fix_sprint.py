from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesAudioFixSprint:
    def _handle_audio_fix_sprint_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-fix-sprints":
                if method == "GET":
                    sprints = self.audio_fix_sprint_store.list_sprints()
                    self._send_json({"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}})
                    return
                if method == "POST":
                    sprint = self.audio_fix_sprint_store.create_sprint(self._read_json_body())
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-fix-sprints/"):
                parts = path.removeprefix("/api/audio-fix-sprints/").strip("/").split("/")
                sprint_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    sprint = self.audio_fix_sprint_store.read_sprint(sprint_id)
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})})
                    return
                action = parts[1]
                if len(parts) == 2 and action == "refresh":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    sprint = self.audio_fix_sprint_store.refresh_sprint(sprint_id)
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})})
                    return
                if len(parts) == 2 and action == "drafts":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.create_drafts(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "candidates":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.generate_candidates(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "recheck-session":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.create_recheck_session(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "closeout":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_fix_sprint_store.closeout_report(sprint_id)
                    self._send_json({"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "close":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.close_sprint(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 6 and parts[1] == "items" and parts[3] == "candidates" and parts[5] == "review":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.review_candidate(sprint_id, parts[2], parts[4], self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 6 and parts[1] == "items" and parts[3] == "candidates" and parts[5] == "select":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.select_candidate(sprint_id, parts[2], parts[4], self._optional_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 4 and parts[1] == "recheck-items" and parts[3] == "review":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.review_recheck_item(sprint_id, parts[2], self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Fix Sprint route not found.")
        except _interfaces_api_runtime.AudioFixSprintNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioFixSprintStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioFixSprintValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioFixSprintError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_campaign_route(self, method: str, path: str) -> None:
        try:
            self.audio_campaign_governance_store.campaign_store = self.audio_campaign_store
            self.audio_campaign_governance_store.analytics_store.campaign_store = self.audio_campaign_store
            if path == "/api/audio-campaigns":
                if method == "GET":
                    campaigns = self.audio_campaign_store.list_campaigns()
                    self._send_json({"ok": True, "campaigns": campaigns, "summary": {"campaign_count": len(campaigns)}})
                    return
                if method == "POST":
                    campaign = self.audio_campaign_store.create_campaign(self._read_json_body())
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-campaigns/"):
                parts = path.removeprefix("/api/audio-campaigns/").strip("/").split("/")
                campaign_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    campaign = self.audio_campaign_store.read_campaign(campaign_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                action = parts[1]
                if len(parts) == 2 and action == "refresh":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    campaign = self.audio_campaign_store.refresh_campaign(campaign_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                if len(parts) == 2 and action == "link-listening-session":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    session_id = str(payload.get("session_id") or payload.get("from_session") or "")
                    campaign = self.audio_campaign_store.link_listening_session(campaign_id, session_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                if len(parts) == 2 and action == "fix-sprints":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.create_fix_sprints(campaign_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "report":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_campaign_store.refresh_report(campaign_id)
                    self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "signoff":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.signoff(campaign_id, self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 2 and action == "export":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.export_campaign(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 2 and action == "zip":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.build_zip(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 2 and action == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.audio_campaign_store.verify_zip(
                        campaign_id,
                        strict=bool(payload.get("strict")),
                        require_real_audio=bool(payload.get("require_real_audio")),
                        require_manual_review=bool(payload.get("require_manual_review")),
                        require_fix_sprints_closed=bool(payload.get("require_fix_sprints_closed")),
                        require_signed=bool(payload.get("require_signed")),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "governance":
                    if method == "GET":
                        report = self.audio_campaign_governance_store.read_governance_report(campaign_id, default={})
                        self._send_json({"ok": True, "governance": report, "summary": report.get("summary", {}) if isinstance(report, dict) else {}})
                        return
                    if method == "POST":
                        report = self.audio_campaign_governance_store.refresh_governance_report(campaign_id)
                        self._send_json({"ok": report.get("status") == "signed", "governance": report, "summary": report.get("summary", {})})
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 2 and action == "analytics":
                    if method == "GET":
                        analytics = self.audio_campaign_governance_store.analytics_store.read(campaign_id, default={})
                        self._send_json({"ok": True, "analytics": analytics, "summary": analytics.get("summary", {}) if isinstance(analytics, dict) else {}})
                        return
                    if method == "POST":
                        analytics = self.audio_campaign_governance_store.refresh_analytics(campaign_id)
                        self._send_json({"ok": True, "analytics": analytics, "summary": analytics.get("summary", {})})
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 2 and action == "archive":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.audio_campaign_governance_store.export_archive(campaign_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {})})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "zip":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_governance_store.build_archive_zip(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_campaign_governance_store.verify_archive(campaign_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "download":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.audio_campaign_governance_store.archive_zip_path(campaign_id), "application/zip", filename="audio-campaign-archive.zip")
                    return
                if len(parts) == 2 and action == "change-requests":
                    if method == "GET":
                        rows = self.audio_campaign_governance_store.list_change_requests(campaign_id)
                        self._send_json({"ok": True, "change_requests": rows, "summary": {"count": len(rows)}})
                        return
                    if method == "POST":
                        cr = self.audio_campaign_governance_store.create_change_request(campaign_id, self._read_json_body())
                        self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                        return
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 4 and parts[1] == "change-requests" and parts[3] == "approve":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    cr = self.audio_campaign_governance_store.approve_change_request(campaign_id, parts[2], self._optional_json_body())
                    self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}})
                    return
                if len(parts) == 3 and parts[1] == "signoff" and parts[2] == "reset":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    result = self.audio_campaign_governance_store.reset_signoff(campaign_id, str(payload.get("change_request_id") or ""), payload)
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio Campaign route not found.")
        except _interfaces_api_runtime.AudioCampaignNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioCampaignStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioCampaignGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioCampaignValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioCampaignError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioCampaignGovernanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
