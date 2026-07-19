from __future__ import annotations

from typing import Any as _InterfaceType

from song_agent.interfaces.api.route_contexts.delivery import DeliveryRouteContext

from typing import Any

from song_agent.domains.creation.redaction import sanitize_sensitive_text

from song_agent.platform.contracts.documents import ImplementationDocument


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesReleaseOperationsReviewerPack(DeliveryRouteContext):
    def _handle_release_operations_reviewer_pack(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_reviewer_pack_store.read_report(release_id, default={})
                retrospective = self.release_operations_reviewer_pack_store.read_retrospective(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": _interfaces_api_runtime.reviewer_pack_summary(report), "retrospective_summary": _interfaces_api_runtime.retrospective_summary(retrospective) if retrospective else {"status": "missing"}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_operations_reviewer_pack_store.refresh(release_id, now=_interfaces_api_runtime._utc_now())
                retrospective = self.release_operations_reviewer_pack_store.read_retrospective(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "summary": _interfaces_api_runtime.reviewer_pack_summary(report), "retrospective_summary": _interfaces_api_runtime.retrospective_summary(retrospective)})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.release_operations_reviewer_pack_store.export_pack(release_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.release_operations_reviewer_pack_store.build_zip(release_id, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_operations_reviewer_pack_store.read_export_manifest(release_id)
                self._send_json({"ok": True, "release_id": release_id, "zip": zip_info, "summary": manifest.get("summary", {})})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = _interfaces_api_runtime.verify_release_operations_reviewer_pack(
                    self.release_operations_reviewer_pack_store.zip_path(release_id),
                    strict=bool(payload.get("strict", False)),
                    require_audit=bool(payload.get("require_audit", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_archive=bool(payload.get("require_archive", False)),
                )
                _interfaces_api_runtime.write_release_operations_reviewer_pack_verification_report(report, self.release_operations_reviewer_pack_store.verification_report_path(release_id))
                self._send_json({"ok": True, "release_id": release_id, "verification": report, "summary": _interfaces_api_runtime.release_operations_reviewer_pack_verification_summary(report)})
                return
            if tail == ".zip":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.release_store.get_release(release_id)
                self._send_file(self.release_operations_reviewer_pack_store.zip_path(release_id), "application/zip", filename=f"musicforge-{release_id}-operations-reviewer-pack.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Operations Reviewer Pack route not found.")
        except _interfaces_api_runtime.ReleaseOperationsReviewerPackNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseOperationsReviewerPackStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseOperationsReviewerPackError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))

    def _handle_release_operations_runbooks(self, method: str, release_id: str, tail: str) -> None:
        if tail in {"", "/"}:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
                include_archived = str(query.get("include_archived", [""])[0]).lower() in {"1", "true", "yes"}
                runbooks = self.release_operations_runbook_store.list_runbooks(release_id, include_archived=include_archived)
                self._send_json({"ok": True, "release_id": release_id, "runbooks": runbooks, "summary": {"count": len(runbooks)}})
                return
            if method == "POST":
                runbook = self.release_operations_runbook_store.create_from_operations_report(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        parts = [part for part in tail.strip("/").split("/") if part]
        if not parts:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Operations Runbook route not found.")
            return
        runbook_id = parts[0]
        if len(parts) == 1:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.get_runbook(release_id, runbook_id)
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)})
            return
        action = parts[1]
        if len(parts) == 2 and action == "run-safe":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.run_safe_actions(release_id, runbook_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)})
            return
        if len(parts) == 2 and action == "refresh-stale":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            result = self.release_operations_runbook_store.refresh_stale_status(release_id, runbook_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, **result, "summary": _interfaces_api_runtime.runbook_summary(result.get("runbook", {}))})
            return
        if len(parts) == 2 and action == "archive":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.archive_runbook(release_id, runbook_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)})
            return
        if len(parts) == 2 and action == "export":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            manifest = self.release_operations_runbook_store.export_runbook(release_id, runbook_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "manifest": manifest, "summary": manifest.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        if len(parts) == 3 and action == "export" and parts[2] == "zip":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            zip_info = self.release_operations_runbook_store.build_zip(release_id, runbook_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "zip": zip_info})
            return
        if len(parts) == 2 and action == "export.zip":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._send_file(self.release_operations_runbook_store.zip_path(release_id, runbook_id), "application/zip", filename=f"musicforge-{release_id}-{runbook_id}-runbook.zip")
            return
        if len(parts) == 2 and action == "verify":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            report = _interfaces_api_runtime.verify_release_operations_runbook_package(
                self.release_operations_runbook_store.zip_path(release_id, runbook_id),
                strict=bool(payload.get("strict", False)),
                require_completed=bool(payload.get("require_completed", False)),
                require_current=bool(payload.get("require_current", False)),
            )
            _interfaces_api_runtime.write_release_operations_runbook_verification_report(report, self.release_operations_runbook_store.runbook_dir(release_id, runbook_id) / "runbook-verification-report.json")
            self._send_json({"ok": True, "release_id": release_id, "runbook_id": runbook_id, "verification": report, "summary": _interfaces_api_runtime.release_operations_runbook_verification_summary(report)})
            return
        if len(parts) == 4 and action == "items" and parts[3] == "retry":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.retry_item(release_id, runbook_id, parts[2], now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)})
            return
        if len(parts) == 4 and action == "items" and parts[3] == "waive":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            runbook = self.release_operations_runbook_store.waive_item(release_id, runbook_id, parts[2], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": _interfaces_api_runtime.runbook_summary(runbook)})
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Operations Runbook route not found.")

    def _get_or_refresh_release_qa(self, release_id: str, *, refresh: bool, options: ImplementationDocument) -> ImplementationDocument:
        document = self.release_store.get_release(release_id)
        if not refresh:
            existing = self.release_store.read_qa(release_id, default={})
            if existing:
                current_hash = _interfaces_api_runtime.release_source_hash(document, project_store=self.project_store, release_store=self.release_store)
                if str(existing.get("source_hash") or "") != current_hash:
                    return _interfaces_api_runtime.mark_release_qa_stale(existing, current_source_hash=current_hash)
                return existing
        report = _interfaces_api_runtime.build_release_qa_report(release=document, release_store=self.release_store, project_store=self.project_store, options=options, now=_interfaces_api_runtime._utc_now())
        report = self.release_store.write_qa(release_id, report)
        self.release_store.update_qa_summary(release_id, _interfaces_api_runtime.release_qa_summary(report))
        return report

    def _get_or_refresh_release_metadata_qa(self, release_id: str, *, refresh: bool) -> ImplementationDocument:
        document = self.release_store.get_release(release_id)
        metadata = _interfaces_api_runtime.read_release_metadata(self.release_store, release_id, default={})
        if not metadata:
            report = _interfaces_api_runtime.build_release_metadata_qa_report(release=document, metadata={}, now=_interfaces_api_runtime._utc_now())
            return _interfaces_api_runtime.write_release_metadata_qa(self.release_store, release_id, report)
        if not refresh:
            existing = _interfaces_api_runtime.read_release_metadata_qa(self.release_store, release_id, default={})
            if existing:
                current_hash = _interfaces_api_runtime.release_metadata_source_hash(document, metadata)
                if str(existing.get("source_hash") or "") != current_hash:
                    return _interfaces_api_runtime.mark_release_metadata_qa_stale(existing, current_source_hash=current_hash)
                return existing
        report = _interfaces_api_runtime.build_release_metadata_qa_report(release=document, metadata=metadata, now=_interfaces_api_runtime._utc_now())
        return _interfaces_api_runtime.write_release_metadata_qa(self.release_store, release_id, report)

    def _ensure_release_export_mutable(self, release_id: str, *, document: Any | None = None) -> None:
        document = document or self.release_store.get_release(release_id)
        if document.status == "archived":
            raise _interfaces_api_runtime.ReleaseStateError("Archived releases are read-only.")
        if document.status == "signed":
            raise _interfaces_api_runtime.ReleaseStateError("Signed releases cannot rebuild export or ZIP. Reset signoff before exporting again.")

    def _release_declarative_policy_gate(self, payload: ImplementationDocument) -> ImplementationDocument | None:
        policy_id = str(payload.get("gate_policy") or payload.get("policy") or "").strip()
        if not policy_id:
            return None
        if policy_id == "release.audio_strict":
            policy_id = "release.audio"
        if policy_id not in {"release.standard", "release.audio"}:
            return {
                "status": "failed",
                "hard_block": True,
                "policy_id": policy_id,
                "message": "Release signoff only accepts release.standard or release.audio policy.",
                "blockers": ["release_policy_id"],
            }
        workspace = self.release_store.root.parent.resolve()
        try:
            from song_agent.application.evidence_policy_gate import evaluate_evidence_policy_gate, resolve_workspace_evidence_manifest

            manifest_path = resolve_workspace_evidence_manifest(
                workspace,
                manifest_id=payload.get("evidence_manifest_id"),
                manifest=payload.get("evidence_manifest"),
            )
            result = evaluate_evidence_policy_gate(policy_id, manifest_path, allowed_root=workspace)
            result["message"] = "Release Evidence Graph policy passed." if result["status"] == "passed" else "Release Evidence Graph policy failed."
            result.pop("graph", None)
            result.pop("checks", None)
            return result
        except Exception:
            return {
                "status": "failed",
                "hard_block": True,
                "policy_id": policy_id,
                "message": "Release Evidence Graph policy could not be evaluated.",
                "blockers": ["release_policy_runtime"],
            }

    def _release_mix_gate(self, release_id: str, *, require_stem_health: bool, require_current_mix: bool) -> ImplementationDocument:
        if not (require_stem_health or require_current_mix):
            return {}
        try:
            document = self.release_store.get_release(release_id)
        except Exception as exc:
            return {"status": "failed", "message": f"Release is unavailable: {sanitize_sensitive_text(str(exc))}"}
        tracks: list[ImplementationDocument] = []
        blockers: list[str] = []
        for track in document.tracks:
            project_dir = self.project_store.project_dir(track.project_id)
            export_dir = _interfaces_api_runtime.final_export_dir(project_dir)
            mix_state_path = export_dir / "mix-state.json"
            song_plan_path = export_dir / "song-plan.json"
            midi_path = export_dir / "song.mid"
            stem_health_path = export_dir / "stems" / "stem-health.json"
            mix_state = _interfaces_api_runtime.read_json(mix_state_path) if mix_state_path.exists() else {}
            stem_report = _interfaces_api_runtime.read_json(stem_health_path) if stem_health_path.exists() else {}
            mix_ok = bool(mix_state) and _interfaces_api_runtime.mix_state_integrity_ok(mix_state)
            mix_stale_reasons: list[str] = []
            plan: _InterfaceType | None = None
            try:
                plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(song_plan_path))
            except Exception:
                if require_current_mix or stem_report:
                    mix_stale_reasons.append("song_plan_unavailable")
            if not mix_state:
                mix_stale_reasons.append("mix_state_missing")
            elif not mix_ok:
                mix_stale_reasons.append("mix_state_integrity")
            elif plan is not None:
                try:
                    mix_stale_reasons.extend(_interfaces_api_runtime.mix_state_stale_reasons(mix_state, plan=plan, midi_path=midi_path))
                except Exception:
                    mix_stale_reasons.append("mix_state_source_unavailable")
            mix_stale_reasons = sorted(set(mix_stale_reasons))
            mix_current = mix_ok and not mix_stale_reasons
            if require_current_mix and not mix_current:
                blockers.append(f"{track.track_id}: current mix-state evidence is missing, tampered, or stale")
            stem_ok = False
            stem_summary = _interfaces_api_runtime.stem_health_summary(stem_report)
            try:
                current_source = None
                if stem_report and plan is not None:
                    current_source = _interfaces_api_runtime.stable_hash(_interfaces_api_runtime.stem_health_source_state(run_dir=export_dir, project_id=track.project_id, version_id=track.version_id, plan=plan, mix_state=mix_state if mix_current else None))
                stem_ok = _interfaces_api_runtime.stem_health_allows_signoff(stem_report, current_source_hash=current_source)
            except Exception:
                stem_ok = False
            if require_stem_health and not stem_ok:
                blockers.append(f"{track.track_id}: stem audio health is missing, stale, or failed")
            tracks.append(
                {
                    "track_id": track.track_id,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "mix_state_hash": _interfaces_api_runtime.mix_state_hash(mix_state) if mix_ok else None,
                    "mix_state_integrity_ok": mix_ok,
                    "mix_state_current": mix_current,
                    "mix_state_stale_reasons": mix_stale_reasons,
                    "stem_health": stem_summary,
                    "stem_health_integrity_ok": _interfaces_api_runtime.stem_health_integrity_ok(stem_report) if stem_report else False,
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
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "reason is required.")
            return
        existing = self.release_store.read_signoff(release_id, default={})
        if not existing:
            self._send_json({"ok": True, "release_id": release_id, "summary": {"status": "not_signed"}})
            return
        event = _interfaces_api_runtime.release_signoff_history_event(existing, reason=reason, now=_interfaces_api_runtime._utc_now())
        self.release_store.reset_signoff(release_id, event)
        self.release_store.append_event(release_id, "release_signoff_reset", {"reason": event.get("reason"), "previous_status": _interfaces_api_runtime.release_signoff_summary(existing).get("status")})
        self._send_json({"ok": True, "release_id": release_id, "summary": {"status": "reset"}, "history_event": event})
