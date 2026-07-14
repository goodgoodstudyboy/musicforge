from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class DeliveryRoutesPart005:
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
