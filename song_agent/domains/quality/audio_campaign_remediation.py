# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore as AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore as AudioCampaignStore
from song_agent.domains.quality.audio_fix_sprints import AudioFixSprintStore as AudioFixSprintStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.audio_campaign_remediation_contracts import AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE as AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE, AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION as AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION


HIGH_SEVERITIES = {"high", "critical"}


from song_agent.domains.quality import v142_acr_readiness as _v142_acr_readiness
from song_agent.domains.quality.v142_acr_readiness import AudioCampaignRemediationError as AudioCampaignRemediationError, AudioCampaignRemediationNotFoundError as AudioCampaignRemediationNotFoundError, AudioCampaignRemediationStateError as AudioCampaignRemediationStateError, AudioCampaignRemediationValidationError as AudioCampaignRemediationValidationError, _issues_from_campaign as _issues_from_campaign, _issue_closeout as _issue_closeout, _sprint_state as _sprint_state, _action as _action, _release_track_current_row as _release_track_current_row, _track_identity as _track_identity, _issue_severity as _issue_severity, _issue_category as _issue_category, _marker_public as _marker_public, _plan_summary as _plan_summary, _queue_summary as _queue_summary, _linked_fix_sprints as _linked_fix_sprints, _readme as _readme, _file_record as _file_record, _sha256_path as _sha256_path, _bounded as _bounded, _integrity_hash as _integrity_hash, _append_event as _append_event









class AudioCampaignRemediationStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        project_store: ProjectStore | None = None,
        planner_store: AudioCampaignPlannerStore | None = None,
        campaign_store: AudioCampaignStore | None = None,
        fix_sprint_store: AudioFixSprintStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.project_store = project_store or self.release_store.project_store
        self.campaign_store = campaign_store or AudioCampaignStore()
        self.fix_sprint_store = fix_sprint_store or self.campaign_store.audio_fix_sprint_store
        self.planner_store = planner_store or AudioCampaignPlannerStore(release_store=self.release_store, project_store=self.project_store, audio_campaign_store=self.campaign_store)
        self.lock = threading.RLock()

    def remediation_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-campaign-remediation"

    def plan_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "remediation-plan.json"

    def queue_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "action-queue.json"

    def closeout_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "closeout-report.json"

    def signoff_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "remediation-signoff.json"

    def export_dir(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "export"

    def zip_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "audio-campaign-remediation.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "verification-report.json"

    def events_path(self, release_id: str) -> Path:
        return self.remediation_dir(release_id) / "events.jsonl"

    def read_plan(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        if not self.plan_path(release_id).exists():
            if default is not None:
                return default
            raise AudioCampaignRemediationNotFoundError(f"Audio Campaign remediation plan not found: {release_id}.")
        return sanitize_metadata(read_json(self.plan_path(release_id)))

    def read_queue(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        if not self.queue_path(release_id).exists():
            if default is not None:
                return default
            raise AudioCampaignRemediationNotFoundError(f"Audio Campaign remediation queue not found: {release_id}.")
        return sanitize_metadata(read_json(self.queue_path(release_id)))

    def read_closeout(self, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        if not self.closeout_path(release_id).exists():
            if default is not None:
                return default
            raise AudioCampaignRemediationNotFoundError(f"Audio Campaign remediation closeout not found: {release_id}.")
        return sanitize_metadata(read_json(self.closeout_path(release_id)))

    def _current_source_state(self, release_id: str, *, refresh_campaign: bool = True) -> ImplementationDocument:
        release = self.release_store.get_release(release_id)
        link = self.planner_store.read_link(release_id)
        campaign_id = str(link.get("campaign_id") or "")
        if not campaign_id:
            raise AudioCampaignRemediationStateError("Release Audio Campaign link is missing campaign_id.")
        campaign = self.campaign_store.read_campaign(campaign_id)
        if refresh_campaign:
            campaign_report = self.campaign_store.refresh_report(campaign_id)
        else:
            report_path = self.campaign_store.campaign_dir(campaign_id) / "campaign-report.json"
            campaign_report = read_json(report_path) if report_path.exists() else self.campaign_store.refresh_report(campaign_id)
        case_index = read_json(self.campaign_store.case_index_path(campaign_id))
        track_rows = [_release_track_current_row(self.project_store, track) for track in release.tracks]
        blockers: list[ImplementationDocument] = []
        if link.get("coverage_status") != "passed":
            blockers.append({"check_id": "release_campaign_link_coverage", "message": "Release Audio Campaign link coverage is not passed."})
        stale_tracks = [row for row in track_rows if row.get("status") != "passed"]
        for row in stale_tracks:
            blockers.append(
                {
                    "check_id": "release_track_final_export_current",
                    "track_id": row.get("track_id"),
                    "message": "Release track Final Export is stale.",
                    "expected_hash": row.get("expected_hash"),
                    "current_hash": row.get("current_hash"),
                }
            )
        source = {
            "release_id": release_id,
            "release_track_identities_hash": stable_hash([_track_identity(track) for track in release.tracks]),
            "campaign_id": campaign_id,
            "campaign_source_hash": campaign.get("source_hash"),
            "campaign_report_hash": stable_hash(
                {
                    "status": campaign_report.get("status"),
                    "source_hash": campaign_report.get("source_hash"),
                    "summary": campaign_report.get("summary"),
                    "blockers": campaign_report.get("blockers"),
                    "cases": campaign_report.get("cases"),
                }
            ),
            "case_index_hash": stable_hash({"cases": case_index.get("cases", [])}),
            "link_hash": link.get("integrity_hash"),
            "track_final_exports": track_rows,
        }
        source["source_hash"] = stable_hash(source)
        return {
            "release": release,
            "link": link,
            "campaign": campaign,
            "campaign_id": campaign_id,
            "campaign_report": campaign_report,
            "case_index": case_index,
            "track_rows": track_rows,
            "blockers": blockers,
            "source": source,
        }

    def refresh_plan(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            state = self._current_source_state(release_id, refresh_campaign=True)
            campaign_id = str(state["campaign_id"])
            campaign = state["campaign"]
            campaign_report = state["campaign_report"]
            case_index = state["case_index"]
            issues = _issues_from_campaign(campaign, campaign_report, case_index)
            blockers = list(state["blockers"])
            source = state["source"]
            status = "blocked" if blockers else "passed" if not issues else "needs_action"
            plan = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": campaign_id,
                    "status": status,
                    "created_at": self.read_plan(release_id, default={}).get("created_at") or now_iso(),
                    "updated_at": now_iso(),
                    "source": source,
                    "issues": issues,
                    "summary": _plan_summary(issues, blockers),
                    "blockers": blockers,
                    "warnings": [],
                }
            )
            plan["source_hash"] = source["source_hash"]
            plan["integrity_hash"] = _integrity_hash(plan)
            write_json(self.plan_path(release_id), plan)
            _append_event(self.events_path(release_id), "audio_campaign_remediation_plan_refreshed", {"release_id": release_id, "campaign_id": campaign_id, "status": status, "issue_count": len(issues)})
            return plan

    def _assert_signed_current(self, release_id: str) -> ImplementationDocument:
        if not self.signoff_path(release_id).exists():
            raise AudioCampaignRemediationStateError("Audio Campaign remediation signoff is missing.")
        signoff = read_json(self.signoff_path(release_id))
        closeout = self.read_closeout(release_id)
        if signoff.get("status") != "signed":
            raise AudioCampaignRemediationStateError("Audio Campaign remediation signoff is not signed.")
        if signoff.get("closeout_hash") != closeout.get("integrity_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation closeout no longer matches signoff.")
        if signoff.get("source_hash") != closeout.get("source_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation signoff source no longer matches closeout.")
        plan = self.read_plan(release_id)
        queue = self.read_queue(release_id)
        if closeout.get("source", {}).get("plan_source_hash") != plan.get("source_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation closeout no longer matches remediation plan.")
        if closeout.get("source", {}).get("queue_integrity_hash") != queue.get("integrity_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation closeout no longer matches action queue.")
        state = self._current_source_state(release_id, refresh_campaign=True)
        current_source_hash = state.get("source", {}).get("source_hash")
        if state.get("blockers"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation source is stale. Refresh and re-sign before using remediation evidence.")
        if current_source_hash != closeout.get("source", {}).get("plan_source_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation source is stale. Refresh and re-sign before using remediation evidence.")
        return {"signoff": signoff, "closeout": closeout, "plan": plan, "queue": queue, "current_source": state.get("source", {})}

    def build_action_queue(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        del payload
        with self.lock:
            plan = self.refresh_plan(release_id)
            actions: list[ImplementationDocument] = []
            index = 1
            for issue in plan.get("issues", []):
                sprint_id = str(issue.get("fix_sprint_id") or "")
                if not sprint_id:
                    actions.append(_action(index, issue, "create_fix_sprint", "safe", "pending"))
                    index += 1
                else:
                    try:
                        sprint = self.fix_sprint_store.read_sprint(sprint_id)
                    except Exception:
                        actions.append(_action(index, issue, "create_fix_sprint", "safe", "pending"))
                        index += 1
                        continue
                    state = _sprint_state(sprint, self.fix_sprint_store, sprint_id)
                    if state.get("candidate_count", 0) == 0:
                        actions.append(_action(index, issue, "create_draft", "safe", "pending", sprint_id=sprint_id))
                        index += 1
                        actions.append(_action(index, issue, "generate_candidate", "safe", "pending", sprint_id=sprint_id))
                        index += 1
                    if not state.get("manual_ab_reviewed"):
                        actions.append(_action(index, issue, "manual_ab_review", "manual_required", "manual_required", sprint_id=sprint_id))
                        index += 1
                    elif not state.get("selected_candidate"):
                        actions.append(_action(index, issue, "select_candidate", "manual_required", "manual_required", sprint_id=sprint_id))
                        index += 1
                    elif not state.get("recheck_created"):
                        actions.append(_action(index, issue, "create_recheck_session", "safe", "pending", sprint_id=sprint_id))
                        index += 1
                    elif not state.get("manual_recheck_accepted"):
                        actions.append(_action(index, issue, "manual_recheck", "manual_required", "manual_required", sprint_id=sprint_id))
                        index += 1
                    elif state.get("closeout_status") != "passed":
                        actions.append(_action(index, issue, "refresh_closeout_report", "safe", "pending", sprint_id=sprint_id))
                        index += 1
                    elif state.get("sprint_status") != "closed":
                        actions.append(_action(index, issue, "close_fix_sprint", "safe", "pending", sprint_id=sprint_id))
                        index += 1
            queue_status = "blocked" if plan.get("blockers") else "completed" if not actions else "pending"
            queue = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": plan.get("campaign_id"),
                    "status": queue_status,
                    "created_at": self.read_queue(release_id, default={}).get("created_at") or now_iso(),
                    "updated_at": now_iso(),
                    "plan_source_hash": plan.get("source_hash"),
                    "actions": actions,
                    "summary": _queue_summary(actions),
                }
            )
            queue["integrity_hash"] = _integrity_hash(queue)
            write_json(self.queue_path(release_id), queue)
            return queue

    def run_safe_actions(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            plan = self.refresh_plan(release_id)
            if plan.get("status") == "blocked":
                raise AudioCampaignRemediationStateError("Audio Campaign remediation source is blocked. Refresh Release Audio Campaign evidence before running safe actions.")
            results: list[ImplementationDocument] = []
            campaign_id = str(plan.get("campaign_id") or "")
            for _ in range(8):
                queue = self.build_action_queue(release_id)
                self._ensure_queue_current(release_id, queue)
                safe_items = [item for item in queue.get("actions", []) if item.get("kind") == "safe" and item.get("status") == "pending"]
                if not safe_items:
                    break
                blocked_count = 0
                for item in safe_items:
                    action_type = str(item.get("action_type") or "")
                    try:
                        if action_type == "create_fix_sprint":
                            created = self.campaign_store.create_fix_sprints(campaign_id)
                            created_ids = [row.get("fix_sprint_id") for row in created.get("fix_sprints", [])]
                            results.append({"action_id": item.get("action_id"), "status": "completed", "created_fix_sprint_ids": created_ids})
                        elif action_type == "create_draft":
                            sprint_id = str(item.get("fix_sprint_id") or "")
                            result = self.fix_sprint_store.create_drafts(sprint_id, {"draft_type": "mix_patch"})
                            results.append({"action_id": item.get("action_id"), "status": "completed", "draft_count": len(result.get("drafts", [])), "fix_sprint_id": sprint_id})
                        elif action_type == "generate_candidate":
                            sprint_id = str(item.get("fix_sprint_id") or "")
                            result = self.fix_sprint_store.generate_candidates(sprint_id)
                            results.append({"action_id": item.get("action_id"), "status": "completed", "candidate_count": len(result.get("candidates", [])), "fix_sprint_id": sprint_id})
                        elif action_type == "create_recheck_session":
                            sprint_id = str(item.get("fix_sprint_id") or "")
                            result = self.fix_sprint_store.create_recheck_session(sprint_id)
                            results.append({"action_id": item.get("action_id"), "status": "completed", "recheck_session_id": result.get("recheck_session", {}).get("session_id"), "fix_sprint_id": sprint_id})
                        elif action_type == "refresh_closeout_report":
                            sprint_id = str(item.get("fix_sprint_id") or "")
                            report = self.fix_sprint_store.closeout_report(sprint_id)
                            status = "completed" if report.get("status") == "passed" else "blocked"
                            if status == "blocked":
                                blocked_count += 1
                            results.append({"action_id": item.get("action_id"), "status": status, "closeout_status": report.get("status"), "fix_sprint_id": sprint_id})
                        elif action_type == "close_fix_sprint":
                            sprint_id = str(item.get("fix_sprint_id") or "")
                            result = self.fix_sprint_store.close_sprint(sprint_id, {"closed_by": payload.get("closed_by") or "audio-campaign-remediation"})
                            results.append({"action_id": item.get("action_id"), "status": "completed", "fix_sprint_id": sprint_id, "sprint_status": result.get("sprint", {}).get("status")})
                        else:
                            results.append({"action_id": item.get("action_id"), "status": "skipped", "reason": "not a safe action"})
                    except Exception as exc:
                        blocked_count += 1
                        results.append({"action_id": item.get("action_id"), "status": "blocked", "reason": str(exc), "action_type": action_type})
                if blocked_count == len(safe_items):
                    break
            queue = self.build_action_queue(release_id)
            closeout = self.closeout_report(release_id)
            _append_event(self.events_path(release_id), "audio_campaign_remediation_safe_actions_run", {"result_count": len(results), "queue_status": queue.get("status"), "closeout_status": closeout.get("status")})
            return {"status": "completed_with_warnings" if any(row.get("status") == "blocked" for row in results) else "completed", "results": results, "queue": queue, "closeout": closeout}

    def closeout_report(self, release_id: str) -> DomainDocument:
        with self.lock:
            plan = self.refresh_plan(release_id)
            queue = self.build_action_queue(release_id)
            blockers: list[str] = []
            warnings: list[str] = []
            issue_results = []
            if plan.get("blockers"):
                blockers.append("remediation_source_blocked")
            for issue in plan.get("issues", []):
                result = _issue_closeout(issue, self.fix_sprint_store)
                issue_results.append(result)
                blockers.extend(result.get("blockers", []))
                warnings.extend(result.get("warnings", []))
            if any(action.get("kind") == "manual_required" for action in queue.get("actions", [])):
                blockers.append("manual_action_required")
            status = "passed" if not blockers else "failed"
            report = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": plan.get("campaign_id"),
                    "status": status,
                    "generated_at": now_iso(),
                    "summary": {
                        "issue_count": len(issue_results),
                        "passed_issue_count": sum(1 for row in issue_results if row.get("status") == "passed"),
                        "manual_required_count": sum(1 for action in queue.get("actions", []) if action.get("kind") == "manual_required"),
                        "fix_sprint_count": len({row.get("fix_sprint_id") for row in issue_results if row.get("fix_sprint_id")}),
                    },
                    "issues": issue_results,
                    "blockers": sorted(set(blockers)),
                    "warnings": sorted(set(warnings)),
                    "source": {"plan_source_hash": plan.get("source_hash"), "queue_integrity_hash": queue.get("integrity_hash")},
                }
            )
            report["source_hash"] = stable_hash(report["source"])
            report["integrity_hash"] = _integrity_hash(report)
            write_json(self.closeout_path(release_id), report)
            return report

    def signoff(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            if self.signoff_path(release_id).exists():
                raise AudioCampaignRemediationStateError("Audio Campaign remediation is already signed.")
            closeout = self.closeout_report(release_id)
            if closeout.get("status") != "passed":
                raise AudioCampaignRemediationStateError("Audio Campaign remediation closeout has blockers.")
            signed_by = _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-remediation", 120)
            signoff = sanitize_metadata(
                {
                    "schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": closeout.get("campaign_id"),
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": signed_by,
                    "role": _bounded(payload.get("role") or "audio-remediation-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release Audio Campaign remediation accepted.", 1000),
                    "closeout_hash": closeout.get("integrity_hash"),
                    "source_hash": closeout.get("source_hash"),
                    "summary": closeout.get("summary", {}),
                }
            )
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id), signoff)
            _append_event(self.events_path(release_id), "audio_campaign_remediation_signed", {"signoff_hash": signoff.get("integrity_hash")})
            return {"status": "signed", "signoff": signoff, "closeout": closeout}

    def export_package(self, release_id: str) -> DomainDocument:
        with self.lock:
            if self.signoff_path(release_id).exists():
                signed_snapshot = self._assert_signed_current(release_id)
                closeout = signed_snapshot["closeout"]
            else:
                closeout = self.closeout_report(release_id)
            plan = self.read_plan(release_id)
            queue = self.read_queue(release_id)
            export_dir = self.export_dir(release_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[ImplementationDocument] = []

            def write_entry(rel: str, payload: DomainDocument | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("remediation-plan.json", plan)
            write_entry("action-queue.json", queue)
            write_entry("closeout-report.json", closeout)
            if self.signoff_path(release_id).exists():
                write_entry("remediation-signoff.json", read_json(self.signoff_path(release_id)))
            write_entry("linked-fix-sprints.json", {"schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION, "release_id": release_id, "fix_sprints": _linked_fix_sprints(plan, self.fix_sprint_store)})
            write_entry("README.txt", _readme(plan, closeout))
            manifest = sanitize_metadata(
                {
                    "package_type": AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE,
                    "schema_version": AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION,
                    "release_id": release_id,
                    "campaign_id": plan.get("campaign_id"),
                    "generated_at": now_iso(),
                    "source_hash": plan.get("source_hash"),
                    "plan_hash": plan.get("integrity_hash"),
                    "queue_hash": queue.get("integrity_hash"),
                    "closeout_hash": closeout.get("integrity_hash"),
                    "signoff_hash": read_json(self.signoff_path(release_id)).get("integrity_hash") if self.signoff_path(release_id).exists() else None,
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": closeout.get("status"), "manifest": manifest, "export_dir": str(export_dir)}

    def build_zip(self, release_id: str) -> DomainDocument:
        if self.signoff_path(release_id).exists():
            self._assert_signed_current(release_id)
        exported = self.export_package(release_id)
        export_dir = self.export_dir(release_id)
        zip_path = self.zip_path(release_id)
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(export_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(export_dir).as_posix())
        with zipfile.ZipFile(zip_path) as zf:
            entries = sorted(item.filename for item in zf.infolist())
        manifest = read_json(export_dir / "manifest.json")
        manifest["zip"] = {"filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
        manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(export_dir / "manifest.json", manifest)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(export_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(export_dir).as_posix())
        return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, **kwargs: Any) -> DomainDocument:
        from song_agent.domains.quality.audio_campaign_remediation_verifier import verify_audio_campaign_remediation_package, write_audio_campaign_remediation_verification_report

        if self.signoff_path(release_id).exists():
            self._assert_signed_current(release_id)
        if not self.zip_path(release_id).exists():
            self.build_zip(release_id)
        report = verify_audio_campaign_remediation_package(self.zip_path(release_id), **kwargs)
        write_audio_campaign_remediation_verification_report(report, self.verification_report_path(release_id))
        return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            signed = self.signoff_path(release_id).exists()
            signed_snapshot = self._assert_signed_current(release_id) if signed else {}
            closeout = signed_snapshot.get("closeout") if signed else self.closeout_report(release_id)
            result = {"status": "passed" if _as_document(closeout).get("status") == "passed" else "failed", "hard_block": _as_document(closeout).get("status") != "passed", "closeout": closeout, "message": "Audio Campaign remediation closeout is passed."}
            if _as_document(closeout).get("status") != "passed":
                result["message"] = "Audio Campaign remediation closeout has blockers."
            if signed:
                signoff = signed_snapshot["signoff"]
                if require_signed:
                    result["signoff"] = signoff
            elif require_signed:
                signoff = read_json(self.signoff_path(release_id)) if self.signoff_path(release_id).exists() else {}
                result["signoff"] = signoff
                if signoff.get("status") != "signed" or signoff.get("closeout_hash") != _as_document(closeout).get("integrity_hash"):
                    result.update({"status": "failed", "hard_block": True, "message": "Audio Campaign remediation signoff is missing or stale."})
            return sanitize_metadata(result)
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": str(exc)}

    def _ensure_queue_current(self, release_id: str, queue: ImplementationDocument) -> None:
        plan = self.refresh_plan(release_id)
        if queue.get("plan_source_hash") != plan.get("source_hash"):
            raise AudioCampaignRemediationStateError("Audio Campaign remediation queue is stale. Refresh before running safe actions.")

_v142_acr_readiness.bind_globals(globals())
