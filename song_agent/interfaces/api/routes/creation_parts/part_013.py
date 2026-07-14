from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart013:
    def _handle_project_edit_preview(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            payload = self._expand_context_pack_payload(payload)
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                self._send_error(HTTPStatus.BAD_REQUEST, "instruction is required.")
                return
            template_id = str(payload.get("template_id") or "provider-edit-intent").strip()
            template = self.prompt_template_store.get_template(template_id)
            if not template.enabled:
                self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
                return
            config, _sources = load_provider_config()
            asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
            asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
            reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
            reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
            patch, provider_snapshot = generate_provider_edit_patch(
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                config=config,
                asset_references=asset_prompt_refs,
                reference_references=reference_prompt_refs,
            )
            provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
            preview = create_provider_edit_preview(
                project_dir=self.project_store.project_dir(project_id),
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                patch=patch,
                now=_utc_now(),
                provider_usage=provider_usage,
                provider_request_id=None if provider_snapshot.get("request_id") is None else str(provider_snapshot.get("request_id")),
                asset_refs=asset_snapshot["asset_refs"],
                reference_refs=reference_snapshot["reference_refs"],
                context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
            )
            if asset_snapshot["asset_refs"]:
                self.asset_store.mark_used(
                    asset_snapshot["asset_refs"],
                    {
                        "usage_type": "provider_edit_preview",
                        "project_id": project_id,
                        "version_id": parent.version_id,
                        "preview_id": preview.preview_id,
                    },
                )
            if reference_snapshot["reference_refs"]:
                self.reference_store.mark_used(
                    reference_snapshot["reference_refs"],
                    {
                        "usage_type": "provider_edit_preview",
                        "project_id": project_id,
                        "version_id": parent.version_id,
                        "preview_id": preview.preview_id,
                    },
                )
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_preview",
                template_id=template.template_id,
                started_at=preview.created_at,
                status="completed",
                provider_usage=provider_usage,
                request_id=provider_snapshot.get("request_id"),
            )
            write_interface_document(
                self.project_store.project_dir(project_id) / "edit-previews" / preview.preview_id / "provider-usage.json",
                usage,
            )
            self.project_store.append_event(
                project_id,
                "provider_edit_preview_created",
                {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "template_id": template.template_id},
            )
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_edit_preview_apply(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            preview = read_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            if preview.parent_version_id != parent.version_id:
                self._send_error(HTTPStatus.CONFLICT, "Preview does not belong to this parent version.")
                return
            if preview.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview has already been applied.")
                return
            if preview_stale(preview, parent_plan):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview is stale because the parent song-plan.json has changed.")
                return
            patch = preview_patch(self.project_store.project_dir(project_id), preview_id)
            candidate = preview_candidate_plan(self.project_store.project_dir(project_id), preview_id)
            candidate.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": preview.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"preview_id": preview_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_apply",
                template_id=preview.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=preview.provider_usage,
                request_id=preview.provider_request_id,
            )
            context_pack = preview.source.get("context_pack") if isinstance(preview.source.get("context_pack"), dict) else None
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=preview.template_id,
                preview_id=preview_id,
                asset_refs=preview.source.get("asset_refs") if isinstance(preview.source.get("asset_refs"), list) else None,
                reference_refs=preview.source.get("reference_refs") if isinstance(preview.source.get("reference_refs"), list) else None,
                context_pack=context_pack,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            mark_provider_edit_preview_applied(self.project_store.project_dir(project_id), preview_id, job.job_id, version.version_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_applied",
                {"parent_version_id": parent.version_id, "preview_id": preview_id, "version_id": version.version_id, "job_id": job.job_id},
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "preview": preview.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_edit_preview_delete(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            delete_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            self.project_store.append_event(project_id, "provider_edit_preview_deleted", {"preview_id": preview_id, "parent_version_id": version_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})

    def _handle_project_edit_candidates(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            payload = self._expand_context_pack_payload(payload)
            group = self._create_project_candidate_group(project_id, version_id, payload)
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()}, status=HTTPStatus.CREATED)
