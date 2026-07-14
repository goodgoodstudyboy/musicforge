from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart011:
    def _handle_project_review_task_route(self, method: str, project_id: str, task_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.read_task(task_id)
            if task.project_id != project_id:
                raise FileNotFoundError(task_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidates = task_store.list_candidates(task.task_id)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                judge_report = self._read_review_task_judge_report(project_id, task_store, task, candidates)
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in candidates], "decision_report": decision_report, "judge_report": judge_report, "judge_summary": judge_report_summary(judge_report), "provider_summary": review_candidate_source_breakdown(candidates), "events": task_store.read_events(task.task_id)})
                return
            if action == "candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else None
                generated = []
                for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, parent_plan, strategies=strategies):
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=bool(payload.get("render_midi", True)),
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
                self.project_store.append_event(project_id, "review_task_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated)})
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in ranked], "created": [candidate.to_dict() for candidate in generated], "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(ranked)}, status=HTTPStatus.CREATED)
                return
            if action == "provider-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                payload = self._expand_context_pack_payload(payload)
                _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                template_id = str(payload.get("template_id") or "provider-review-candidates").strip()
                template = self.prompt_template_store.get_template(template_id)
                if not template.enabled:
                    self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
                    return
                candidate_count = int(payload.get("candidate_count") or 3)
                config, _sources = load_provider_config()
                asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
                asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
                reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
                reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
                local_context = task_store.list_candidates(task.task_id) if bool(payload.get("include_local_context", True)) else []
                generated_specs, provider_snapshot, instruction = build_provider_review_candidates(
                    task=task,
                    parent_plan=parent_plan,
                    template=template,
                    config=config,
                    candidate_count=candidate_count,
                    local_candidates=local_context,
                    asset_references=asset_prompt_refs,
                    reference_references=reference_prompt_refs,
                )
                generated = []
                for candidate, candidate_plan, validator, summary in generated_specs:
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=bool(payload.get("render_midi", True)),
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
                usage_record = _provider_usage_record(
                    config_snapshot=provider_snapshot,
                    operation="provider_review_candidates",
                    template_id=template.template_id,
                    started_at=_utc_now(),
                    status="completed",
                    provider_usage=provider_usage,
                    request_id=provider_snapshot.get("request_id"),
                )
                write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or "")), now=_utc_now())
                if asset_snapshot["asset_refs"]:
                    self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_task_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
                if reference_snapshot["reference_refs"]:
                    self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_task_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
                self.project_store.append_event(project_id, "review_task_provider_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated), "template_id": template.template_id})
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in ranked], "created": [candidate.to_dict() for candidate in generated], "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(ranked), "provider_snapshot": provider_snapshot, "instruction": instruction}, status=HTTPStatus.CREATED)
                return
            if action == "decision-report":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidates = task_store.rank_candidates(task)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                if not decision_report:
                    _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                    judge_report = self._read_review_task_judge_report(project_id, task_store, task, candidates, parent_plan=parent_plan)
                    decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=candidates, parent_plan=parent_plan, now=_utc_now(), judge_report=judge_report), now=_utc_now())
                self._send_json({"ok": True, "task": task.to_dict(), "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(candidates)})
                return
            if action == "decision-report-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                candidates = task_store.rank_candidates(task)
                judge_report = self._read_review_task_judge_report(project_id, task_store, task, candidates, parent_plan=parent_plan)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=candidates, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("note") or ""), judge_report=judge_report), now=_utc_now())
                self.project_store.append_event(project_id, "review_task_decision_report_refreshed", {"task_id": task.task_id, "recommended_candidate_id": decision_report.get("recommended_candidate_id")})
                self._send_json({"ok": True, "task": task.to_dict(), "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(candidates)})
                return
            if action == "judge-report":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidates = task_store.rank_candidates(task)
                judge_report = self._read_review_task_judge_report(project_id, task_store, task, candidates)
                self._send_json({"ok": True, "task": task.to_dict(), "judge_report": judge_report, "summary": judge_report_summary(judge_report), "provider_summary": review_candidate_source_breakdown(candidates)})
                return
            if action == "judge-report-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self._refresh_review_task_judge_report(project_id, task_store, task, payload)
                self._send_json(result)
                return
            if action == "resolve":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task = task_store.update_task(mark_task_resolved(task, str(payload.get("note") or ""), now=_utc_now()), event="review_task_resolved", payload={"note": payload.get("note") or ""}, now=_utc_now())
                self.project_store.append_event(project_id, "review_task_resolved", {"task_id": task.task_id, "candidate_id": task.selected_candidate_id, "version_id": task.applied_version_id})
                self._send_json({"ok": True, "task": task.to_dict()})
                return
            if action == "needs-more-work":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task, follow_up = self._create_review_task_follow_up(project_id, task_store, task, payload)
                self._send_json({"ok": True, "task": task.to_dict(), "follow_up_task": follow_up.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                task = task_store.update_task(mark_task_archived(task), event="review_task_archived", payload={}, now=_utc_now())
                self.project_store.append_event(project_id, "review_task_archived", {"task_id": task.task_id})
                self._send_json({"ok": True, "task": task.to_dict()})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review task route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review task not found.")
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (ReviewTaskError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_task_candidate_route(self, method: str, project_id: str, task_id: str, candidate_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.read_task(task_id)
            candidate = task_store.read_candidate(task_id, candidate_id)
            if task.project_id != project_id or candidate.project_id != project_id:
                raise FileNotFoundError(candidate_id)
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
            ensure_candidate_current(task, candidate, parent_plan)
            if action == "render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidate = task_store.render_candidate_midi(task, candidate, now=_utc_now())
                self._send_json({"ok": True, "task": task_store.read_task(task.task_id).to_dict(), "candidate": candidate.to_dict()})
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                candidate = task_store.render_candidate_audio(task, candidate, config, now=_utc_now())
                self._send_json({"ok": True, "task": task_store.read_task(task.task_id).to_dict(), "candidate": candidate.to_dict()})
                return
            if action in {"midi", "audio"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                path = task_store.candidate_midi_path(task_id, candidate_id) if action == "midi" else task_store.candidate_audio_path(task_id, candidate_id)
                if not path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Review candidate artifact not found.")
                    return
                self._send_file(path, "audio/midi" if action == "midi" else "audio/wav", filename=f"{project_id}-{task_id}-{candidate_id}.{ 'mid' if action == 'midi' else 'wav' }")
                return
            if action == "apply":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task, candidate, version, job, result = self._apply_review_task_candidate(project_id, task_store, task, candidate, parent, parent_job, parent_plan, payload)
                self._send_json({"ok": True, "task": task.to_dict(), "candidate": candidate.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "summary": result.summary}, status=HTTPStatus.ACCEPTED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review candidate route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review candidate not found.")
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewTaskError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "unsafe" in str(exc).lower() or "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))

    def _create_review_edit_job(
        self,
        *,
        project_id: str,
        parent: Any,
        parent_job: JobState,
        parent_plan: SongPlan,
        review_edit: Any,
        result: Any,
        payload: dict[str, Any],
    ) -> JobState:
        primary_intent = EditIntent.from_dict(review_edit.intents[0])
        job = self.store.create_edit_job(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job=parent_job,
            parent_plan=parent_plan,
            intent=primary_intent,
            name=str(payload.get("version_name") or payload.get("name") or "Review Edit"),
            start_immediately=False,
            asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
            reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
            context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
        )
        metadata = {
            **job.edit_metadata,
            **review_edit_metadata(review_edit, result),
            "edit_type": primary_intent.edit_type,
            "target": primary_intent.target.to_dict(),
            "instruction": primary_intent.instruction,
            "preserve": list(primary_intent.preserve),
            "strength": primary_intent.strength,
        }
        job.edit_metadata = metadata
        job.input_payload["review_edit_id"] = review_edit.review_edit_id
        job.input_payload["review_edit"] = review_edit_summary(review_edit, result)
        persist_interface_job(self.store, job)
        write_interface_document(ProjectPaths.create(Path(job.output_dir)).data / "edit-metadata.json", metadata)
        self.store.start_job(job.job_id)
        return job

    def _handle_provider_review_edit_preview(self, project_id: str, parent: Any, parent_job: JobState, parent_plan: SongPlan, review_edit: Any, payload: dict[str, Any]) -> None:
        template_id = str(payload.get("template_id") or "provider-review-edit-intent").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
            return
        config, _sources = load_provider_config()
        instruction = review_edit_instruction_for_provider(review_edit)
        patch, provider_snapshot = generate_provider_edit_patch(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            asset_references=[],
            reference_references=[],
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
        )
        preview_dir = self.project_store.project_dir(project_id) / "edit-previews" / preview.preview_id
        data = preview.to_dict()
        data["source"] = {**data.get("source", {}), "review_edit": review_edit.to_dict()}
        write_interface_document(preview_dir / "preview.json", data)
        usage = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_review_edit_preview",
            template_id=template.template_id,
            started_at=preview.created_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(preview_dir / "provider-usage.json", usage)
        self.project_store.append_event(project_id, "provider_review_edit_preview_created", {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "template_id": template.template_id})
        self._send_json({"ok": True, "preview": read_provider_edit_preview(self.project_store.project_dir(project_id), preview.preview_id).to_dict(), "patch": patch.to_dict(), "review_edit": review_edit.to_dict()}, status=HTTPStatus.CREATED)
