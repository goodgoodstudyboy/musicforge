from __future__ import annotations

from typing import Any


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectCandidateArtifact:
    def _handle_project_candidate_artifact(self, method: str, project_id: str, group_id: str, candidate_id: str, action: str) -> None:
        try:
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            candidate_dir = group_store.candidate_dir(group.group_id, candidate_id)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "midi":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = _interfaces_api_runtime.candidate_midi_path(candidate_dir)
            if not path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate MIDI preview not found.")
                return
            self._send_file(path, "audio/midi")
            return

        if action == "audio":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = _interfaces_api_runtime.candidate_audio_path(candidate_dir)
            if not path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate WAV preview not found.")
                return
            self._send_file(path, "audio/wav")
            return

        if action == "render-midi":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                candidate = group_store.render_candidate_midi(group.group_id, candidate_id)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate not found.")
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "render-audio":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                config, _sources = _interfaces_api_runtime.load_renderer_config()
                config.validate_ready_for_render()
                candidate = group_store.render_candidate_audio(group.group_id, candidate_id, config)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate not found.")
            except _interfaces_api_runtime.RendererError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return

        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate artifact route not found.")

    def _project_candidate_group_or_conflict(self, project_id: str, group_store: _interfaces_api_runtime.CandidateGroupStore, group_id: str) -> Any | None:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        group = group_store.read_group(group_id)
        parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
        if parent is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Parent version not found.")
            return None
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
        if _interfaces_api_runtime.candidate_group_stale(group, _interfaces_api_runtime.song_plan_hash(parent_plan)):
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
            return None
        return group

    def _handle_project_prompt_ab_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        created_group_ids: list[str] = []
        try:
            payload = self._expand_context_pack_payload(payload)
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                raise ValueError("instruction is required.")
            candidate_count = int(payload.get("candidate_count") or 2)
            template_ids = _interfaces_api_runtime._prompt_ab_template_ids(payload.get("template_ids"))
            groups = []
            for template_id in template_ids:
                group = self._create_project_candidate_group(
                    project_id,
                    version_id,
                    {
                        **payload,
                        "instruction": instruction,
                        "candidate_count": candidate_count,
                        "template_id": template_id,
                    },
                    mark_asset_usage=False,
                )
                groups.append(group)
                created_group_ids.append(group.group_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = _interfaces_api_runtime.PromptABStore(project_dir).create_experiment(
                project_id=project_id,
                parent_version_id=version_id,
                instruction=instruction,
                candidate_count=candidate_count,
                template_ids=template_ids,
                group_ids=[group.group_id for group in groups],
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "provider_prompt_ab_created",
                {"ab_id": experiment.ab_id, "group_ids": list(experiment.group_ids), "template_ids": list(template_ids)},
            )
            for group in groups:
                refs = group.source.get("asset_refs") if isinstance(group.source, dict) else None
                if isinstance(refs, list) and refs:
                    self.asset_store.mark_used(
                        refs,
                        {
                            "usage_type": "prompt_ab_candidate_generation",
                            "project_id": project_id,
                            "version_id": version_id,
                            "candidate_group_id": group.group_id,
                            "prompt_ab_id": experiment.ab_id,
                        },
                    )
                reference_refs = group.source.get("reference_refs") if isinstance(group.source, dict) else None
                if isinstance(reference_refs, list) and reference_refs:
                    self.reference_store.mark_used(
                        reference_refs,
                        {
                            "usage_type": "prompt_ab_candidate_generation",
                            "project_id": project_id,
                            "version_id": version_id,
                            "candidate_group_id": group.group_id,
                            "prompt_ab_id": experiment.ab_id,
                        },
                    )
        except FileNotFoundError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, message)
            return
        except _interfaces_api_runtime.ContextPackStaleError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except _interfaces_api_runtime.ProviderError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "experiment": experiment.to_dict(), "groups": [group.to_dict() for group in groups]},
            status=_interfaces_api_runtime.HTTPStatus.CREATED,
        )

    def _handle_project_prompt_ab_list(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            experiments = _interfaces_api_runtime.PromptABStore(self.project_store.project_dir(project_id)).list_experiments()
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiments": [experiment.to_dict() for experiment in experiments]})

    def _handle_project_prompt_ab_detail(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = _interfaces_api_runtime.PromptABStore(project_dir).read_experiment(ab_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(project_dir)
            groups = [group_store.read_group(group_id).to_dict() for group_id in experiment.group_ids]
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiment": experiment.to_dict(), "groups": groups})

    def _handle_project_prompt_ab_delete(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            _interfaces_api_runtime.PromptABStore(self.project_store.project_dir(project_id)).delete_experiment(ab_id)
            self.project_store.append_event(project_id, "provider_prompt_ab_deleted", {"ab_id": ab_id})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "ab_id": ab_id})

    def _handle_project_provider_usage(self, project_id: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        usage_records = []
        for version in document.versions:
            usage_path = _interfaces_api_runtime.Path(version.output_dir) / "data" / "provider-usage.json"
            if usage_path.exists():
                usage = _interfaces_api_runtime.read_json(usage_path)
                usage_records.append({"version_id": version.version_id, "job_id": version.job_id, "usage": usage})
        group_records = []
        groups_dir = self.project_store.project_dir(project_id) / "candidate-groups"
        if groups_dir.exists():
            for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
                try:
                    usage = _interfaces_api_runtime.read_json(usage_path)
                except (OSError, ValueError, TypeError, _interfaces_api_runtime.json.JSONDecodeError):
                    continue
                group_records.append({"group_id": usage_path.parent.name, "usage": usage})
        total_tokens = sum(int(record["usage"].get("total_tokens") or 0) for record in usage_records)
        total_tokens += sum(int(record["usage"].get("total_tokens") or 0) for record in group_records)
        self._send_json(
            {
                "project_id": project_id,
                "total_calls": len(usage_records) + len(group_records),
                "total_tokens": total_tokens,
                "records": usage_records,
                "candidate_group_records": group_records,
            }
        )

    def _handle_project_provider_usage_report(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            project_dir = self.project_store.project_dir(project_id)
            records = _interfaces_api_runtime.collect_project_provider_usage_records(project_id, document.versions, project_dir)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_json(_interfaces_api_runtime.build_provider_usage_report(scope="project", project_id=project_id, records=records))

    def _handle_project_review_metrics(self, method: str, project_id: str, *, refresh: bool) -> None:
        expected = "POST" if refresh else "GET"
        if method != expected:
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self._get_or_refresh_project_review_metrics(project_id, refresh=refresh)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if refresh:
            self.project_store.append_event(project_id, "project_review_metrics_refreshed", {"latest_readiness": report.get("latest_readiness"), "sprint_count": report.get("sprint_count")})
        self._send_json({"ok": True, "project_id": project_id, "review_metrics": report, "summary": _interfaces_api_runtime.project_review_metrics_summary(report)})

    def _project_edit_parent(self, project_id: str, version_id: str) -> tuple[Any, Any, _interfaces_api_runtime.JobState, _interfaces_api_runtime.SongPlan]:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        parent = next((version for version in document.versions if version.version_id == version_id), None)
        if parent is None:
            raise FileNotFoundError(version_id)
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            raise ValueError("Parent version job is missing.")
        if parent.status != "completed" or parent_job.status != "completed":
            raise ValueError("Parent version must be completed before editing.")
        parent_plan_path = _interfaces_api_runtime.Path(parent.output_dir) / "data" / "song-plan.json"
        if not parent_plan_path.exists():
            raise ValueError("Parent song-plan.json is missing.")
        parent_plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(parent_plan_path))
        return document, parent, parent_job, parent_plan
