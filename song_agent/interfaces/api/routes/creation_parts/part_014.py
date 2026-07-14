from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart014:
    def _create_project_candidate_group(self, project_id: str, version_id: str, payload: dict[str, Any], *, mark_asset_usage: bool = True) -> Any:
        _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
        instruction = str(payload.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("instruction is required.")
        candidate_count = int(payload.get("candidate_count") or 3)
        template_id = str(payload.get("template_id") or "provider-edit-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ValueError("Prompt template is disabled.")
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        patches, provider_snapshot = generate_provider_edit_candidates(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            candidate_count=candidate_count,
            asset_references=asset_prompt_refs,
            reference_references=reference_prompt_refs,
        )
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        project_dir = self.project_store.project_dir(project_id)
        group_store = CandidateGroupStore(project_dir)
        group = group_store.create_group(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job_id=parent_job.job_id,
            instruction=instruction,
            template_id=template.template_id,
            candidate_count=len(patches),
            source={
                "parent_version_id": parent.version_id,
                "parent_job_id": parent_job.job_id,
                "song_plan_sha256": song_plan_hash(parent_plan),
                "asset_refs": list(asset_snapshot["asset_refs"]),
                "reference_refs": list(reference_snapshot["reference_refs"]),
                **({"context_pack": dict(payload["context_pack"])} if isinstance(payload.get("context_pack"), dict) else {}),
            },
            provider_usage=provider_usage,
            provider_request_id=None if provider_snapshot.get("request_id") is None else str(provider_snapshot.get("request_id")),
            now=_utc_now(),
        )
        usage_record = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_edit_candidates",
            template_id=template.template_id,
            started_at=group.created_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(project_dir / "candidate-groups" / group.group_id / "provider-usage.json", usage_record)
        for patch in patches:
            try:
                result = apply_provider_edit_patch(parent_plan, patch)
                validator = {
                    "status": "passed",
                    "checks": ["provider_edit_patch_schema", "edit_intent_validation", "song_plan_validation"],
                    "checked_at": _utc_now(),
                }
                scores = score_provider_edit_candidate(
                    parent_plan=parent_plan,
                    candidate_plan=result.plan,
                    patch=patch,
                    validator_status="passed",
                )
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="ready",
                    patch=patch.to_dict(),
                    scores=scores.to_dict(),
                    validator=validator,
                    quality=result.plan.quality.to_dict() if result.plan.quality else None,
                    provider_usage={},
                    candidate_plan=result.plan.to_dict(),
                    now=_utc_now(),
                )
                current_group = group_store.read_group(group.group_id)
                latest_candidate = current_group.candidates[-1]
                group_store.render_candidate_midi(group.group_id, latest_candidate.candidate_id)
            except Exception as exc:
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="failed",
                    patch=patch.to_dict(),
                    scores={},
                    validator={"status": "failed", "error": str(exc), "checked_at": _utc_now()},
                    quality=None,
                    error=str(exc),
                    now=_utc_now(),
                )
            group = group_store.read_group(group.group_id)
        if asset_snapshot["asset_refs"] and mark_asset_usage:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
        if reference_snapshot["reference_refs"] and mark_asset_usage:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
        self.project_store.append_event(
            project_id,
            "provider_edit_candidate_group_created",
            {
                "parent_version_id": parent.version_id,
                "group_id": group.group_id,
                "candidate_count": len(group.candidates),
                "template_id": template.template_id,
                "status": group.status,
            },
        )
        return group

    def _handle_project_candidate_groups_list(self, project_id: str) -> None:
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            self._send_json({"project_id": project_id, "groups": [group.to_dict() for group in group_store.list_groups()]})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_detail(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            self._send_json({"project_id": project_id, "group": group.to_dict()})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_usage(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            CandidateGroupStore(project_dir).read_group(group_id)
            records = collect_candidate_group_provider_usage_records(project_id, group_id, project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(build_provider_usage_report(scope="candidate_group", project_id=project_id, records=records))

    def _handle_project_candidate_group_apply(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
            if parent is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
                return
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
            if candidate_group_stale(group, song_plan_hash(parent_plan)):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
                return
            if group.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group has already been applied.")
                return
            candidate_id = str(payload.get("candidate_id") or _top_ranked_candidate_id(group) or "")
            candidate = next((item for item in group.candidates if item.candidate_id == candidate_id), None)
            if candidate is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
                return
            if candidate.status != "ready":
                self._send_error(HTTPStatus.CONFLICT, "Only ready candidates can be applied.")
                return
            patch = ProviderEditPatch.from_dict(group_store.read_candidate_patch(group.group_id, candidate.candidate_id))
            candidate_plan = SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate.candidate_id))
            candidate_plan.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": group.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"candidate_group_id": group.group_id, "candidate_id": candidate.candidate_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_candidate_apply",
                template_id=group.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=group.provider_usage,
                request_id=group.provider_request_id,
            )
            name = str(payload.get("name") or "") or f"Provider Candidate {len(document.versions) + 1}"
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=name,
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=group.template_id,
                preview_id=group.group_id,
                candidate_group_id=group.group_id,
                candidate_id=candidate.candidate_id,
                candidate=_candidate_source_summary(
                    {
                        "candidate_group_id": group.group_id,
                        "candidate_id": candidate.candidate_id,
                        "rank": candidate.rank,
                        "score": candidate.scores.get("combined"),
                        "quality_overall": candidate.scores.get("quality_overall"),
                        "summary": candidate.summary,
                        "status": candidate.status,
                        "created_at": candidate.created_at,
                    }
                ),
                asset_refs=group.source.get("asset_refs") if isinstance(group.source.get("asset_refs"), list) else None,
                reference_refs=group.source.get("reference_refs") if isinstance(group.source.get("reference_refs"), list) else None,
                context_pack=group.source.get("context_pack") if isinstance(group.source.get("context_pack"), dict) else None,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=name,
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            group = group_store.mark_applied(group.group_id, candidate.candidate_id, version_id=version.version_id, job_id=job.job_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_candidate_applied",
                {
                    "parent_version_id": parent.version_id,
                    "group_id": group.group_id,
                    "candidate_id": candidate.candidate_id,
                    "version_id": version.version_id,
                    "job_id": job.job_id,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "group": group.to_dict(), "version": version.to_dict(), "job": job.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_candidate_group_delete(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group_store.delete_group(group_id)
            self.project_store.append_event(project_id, "provider_edit_candidate_group_deleted", {"group_id": group_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "group_id": group_id})

    def _handle_project_candidate_group_render(self, method: str, project_id: str, group_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            if action == "render-midi":
                group = group_store.render_group_midi(group.group_id)
            else:
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                group = group_store.render_group_audio(group.group_id, config)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()})
