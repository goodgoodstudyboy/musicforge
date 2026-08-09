from __future__ import annotations

from song_agent.application.http_ports import delivery as delivery_ports
from song_agent.interfaces.api.route_contexts.delivery import DeliveryRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesDistributionProfiles(DeliveryRouteContext):
    @property
    def audio_revision_store(self) -> delivery_ports.AudioRevisionStore:
        return self.server.audio_revision_store

    @property
    def release_store(self) -> delivery_ports.ReleaseStore:
        return self.server.release_store

    @property
    def release_operations_store(self) -> delivery_ports.ReleaseOperationsStore:
        return self.server.release_operations_store

    @property
    def release_operations_runbook_store(self) -> delivery_ports.ReleaseOperationsRunbookStore:
        return self.server.release_operations_runbook_store

    @property
    def release_operations_signoff_store(self) -> delivery_ports.ReleaseOperationsSignoffStore:
        return self.server.release_operations_signoff_store

    @property
    def release_operations_audit_store(self) -> delivery_ports.ReleaseOperationsAuditStore:
        return self.server.release_operations_audit_store

    @property
    def release_operations_reviewer_pack_store(self) -> delivery_ports.ReleaseOperationsReviewerPackStore:
        return self.server.release_operations_reviewer_pack_store

    @property
    def distribution_store(self) -> delivery_ports.DistributionStore:
        return self.server.distribution_store

    @property
    def submission_store(self) -> delivery_ports.SubmissionStore:
        return self.server.submission_store

    @property
    def submission_evidence_store(self) -> delivery_ports.SubmissionEvidenceStore:
        return self.server.submission_evidence_store

    @property
    def distribution_template_store(self) -> delivery_ports.TemplatePackStore:
        return self.server.distribution_template_store

    @property
    def encoded_audio_acceptance_store(self) -> delivery_ports.EncodedAudioAcceptanceStore:
        return self.server.encoded_audio_acceptance_store

    @property
    def format_decision_store(self) -> delivery_ports.FormatDecisionStore:
        return self.server.format_decision_store

    @property
    def project_store(self) -> delivery_ports.ProjectStore:
        return self.server.project_store

    @property
    def rights_clearance_store(self) -> delivery_ports.RightsClearanceStore:
        return self.server.rights_clearance_store

    def _handle_distribution_profiles_root(self, method: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self._send_json({"ok": True, "profiles": _interfaces_api_runtime.list_distribution_profiles()})

    def _handle_distribution_profile_route(self, method: str, profile_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self._send_json({"ok": True, "profile": _interfaces_api_runtime.get_distribution_profile(profile_id)})
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))

    def _handle_distribution_templates_root(self, method: str) -> None:
        try:
            if method == "GET":
                templates = self.distribution_template_store.list_templates()
                self._send_json({"ok": True, "template_packs": templates, "summary": {"count": len(templates)}})
                return
            if method == "POST":
                template = self.distribution_template_store.create_template(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.DistributionTemplateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_distribution_template_import(self, method: str, query: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            rename = _interfaces_api_runtime.parse_qs(query).get("rename", ["0"])[0] in {"1", "true", "yes"}
            template = self.distribution_template_store.import_template(self._read_json_body(), rename=rename, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except _interfaces_api_runtime.DistributionTemplateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_distribution_template_route(self, method: str, route: tuple[str, str]) -> None:
        template_id, action = route
        try:
            if action == "":
                if method == "GET":
                    template = self.distribution_template_store.get_template(template_id)
                    self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template)})
                    return
                if method in {"POST", "PATCH"}:
                    self.distribution_store.ensure_template_pack_mutable(template_id)
                    template = self.distribution_template_store.update_template(template_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    stale_targets = self.distribution_store.mark_template_dependents_stale(template_id, "template_updated")
                    self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template), "stale_targets": stale_targets})
                    return
            if action == "clone":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.distribution_template_store.clone_template(template_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.distribution_store.ensure_template_pack_deletable(template_id)
                result = self.distribution_template_store.delete_template(template_id)
                self._send_json({"ok": True, **result})
                return
            if action == "export":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.distribution_template_store.get_template(template_id)
                self._send_json({"ok": True, "template": template, "summary": _interfaces_api_runtime.template_summary(template)})
                return
            if action == "validate":
                if method not in {"GET", "POST"}:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body() if method == "POST" else {"template": self.distribution_template_store.get_template(template_id)}
                self._send_json({"ok": True, "validation": self.distribution_template_store.validate_payload(payload)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.DistributionStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.DistributionTemplateError as exc:
            message = str(exc)
            status = _interfaces_api_runtime.HTTPStatus.CONFLICT if "Builtin" in message or "already exists" in message or "cannot" in message else _interfaces_api_runtime.HTTPStatus.BAD_REQUEST
            self._send_error(status, message)

    def _handle_releases_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
            documents = self.release_store.list_releases(include_hidden=include_hidden)
            self._send_json({"releases": [_interfaces_api_runtime.release_summary(document) for document in documents]})
            return
        if method == "POST":
            payload = self._read_json_body()
            try:
                document = self.release_store.create_release(payload)
            except _interfaces_api_runtime.ReleaseValidationError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "release": document.to_dict(), "summary": _interfaces_api_runtime.release_summary(document)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_project_release_targets(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        releases = [
            _interfaces_api_runtime.release_summary(document)
            for document in self.release_store.list_releases(include_hidden=False)
            if document.status not in {"signed", "archived"}
        ]
        self._send_json({"ok": True, "project_id": project_id, "releases": releases})

    def _handle_project_add_to_release(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
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
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
            return
        except (_interfaces_api_runtime.ReleaseValidationError, _interfaces_api_runtime.ReleaseMetadataError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except (_interfaces_api_runtime.ReleaseConflictError, _interfaces_api_runtime.ReleaseStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"ok": True, "release": document.to_dict(), "summary": _interfaces_api_runtime.release_summary(document)})
