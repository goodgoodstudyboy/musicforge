from __future__ import annotations

from typing import Any as _InferenceType

from typing import Any as _InterfaceType

from song_agent.interfaces.api.route_contexts.studio import StudioRouteContext

from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioRoutesApplyReviewTaskCandidate(StudioRouteContext):
    def _apply_review_task_candidate_part_01(self, project_id: str, task_store: _InterfaceType, task: Any, candidate: Any, parent: Any, parent_job: _InterfaceType, parent_plan: _InterfaceType, payload: ImplementationDocument, _split_state):
        _interfaces_api_runtime._ensure_task_open_for_apply(task)
        if candidate.status != 'ready':
            raise _interfaces_api_runtime.ReviewTaskStateError('Candidate is not ready.')
        _split_state['result'] = _interfaces_api_runtime.apply_candidate_intents(parent_plan, [_interfaces_api_runtime.EditIntent.from_dict(item) for item in candidate.intents])
        primary = _interfaces_api_runtime.EditIntent.from_dict(candidate.intents[0])
        name = str(payload.get('name') or payload.get('version_name') or f'Review Candidate {candidate.candidate_id}')
        _split_state['job'] = self.store.create_edit_job(project_id=project_id, parent_version_id=parent.version_id, parent_job=parent_job, parent_plan=parent_plan, intent=primary, name=name, start_immediately=False, asset_refs=payload.get('asset_refs') if isinstance(payload.get('asset_refs'), list) else None, reference_refs=payload.get('reference_refs') if isinstance(payload.get('reference_refs'), list) else None, context_pack=payload.get('context_pack') if isinstance(payload.get('context_pack'), dict) else None)
        decision_report = _interfaces_api_runtime._try_read_review_decision_report(task_store, task.task_id)
        judge_report = self._read_review_task_judge_report(project_id, task_store, task, task_store.list_candidates(task.task_id), parent_plan=parent_plan)
        metadata = {**_split_state['job'].edit_metadata, **_interfaces_api_runtime.candidate_apply_metadata(task, candidate, _split_state['result'], decision_report=decision_report), 'edit_type': primary.edit_type, 'target': primary.target.to_dict(), 'instruction': primary.instruction, 'preserve': list(primary.preserve), 'strength': primary.strength}
        judge_apply_summary = _interfaces_api_runtime.judge_summary_for_apply(judge_report, candidate_id=candidate.candidate_id, stale=bool(judge_report.get('stale'))) if judge_report else {}
        if judge_apply_summary:
            metadata['review_judge'] = judge_apply_summary
        sprint_membership = self._review_sprint_membership_summary(project_id, task.task_id)
        if sprint_membership:
            metadata['review_sprint'] = sprint_membership
        sprint_recommendation = self._review_sprint_recommendation_summary_for_task(project_id, task.task_id)
        if sprint_recommendation:
            metadata['review_sprint_recommendation'] = sprint_recommendation
        sprint_action_queue = self._review_sprint_action_queue_summary_for_task(project_id, task.task_id)
        if sprint_action_queue:
            metadata['review_sprint_action_queue'] = sprint_action_queue
        _split_state['job'].edit_metadata = metadata
        _split_state['job'].input_payload['review_task_id'] = task.task_id
        _split_state['job'].input_payload['review_candidate_id'] = candidate.candidate_id
        _split_state['job'].input_payload['review_task'] = _interfaces_api_runtime.review_task_summary(task, candidate)
        _split_state['job'].input_payload['review_candidate'] = _interfaces_api_runtime.review_candidate_summary(candidate)
        if decision_report:
            _split_state['job'].input_payload['review_decision'] = _interfaces_api_runtime.review_decision_summary(decision_report)
        if judge_apply_summary:
            _split_state['job'].input_payload['review_judge'] = judge_apply_summary
        if sprint_membership:
            _split_state['job'].input_payload['review_sprint'] = sprint_membership
        if sprint_recommendation:
            _split_state['job'].input_payload['review_sprint_recommendation'] = sprint_recommendation
        if sprint_action_queue:
            _split_state['job'].input_payload['review_sprint_action_queue'] = sprint_action_queue
        persist_interface_job(self.store, _split_state['job'])
        write_interface_document(_interfaces_api_runtime.ProjectPaths.create(_interfaces_api_runtime.Path(_split_state['job'].output_dir)).data / 'edit-metadata.json', metadata)
        self.store.start_job(_split_state['job'].job_id)
        document = self.project_store.add_version_from_job(project_id, _split_state['job'], name=name, note=str(payload.get('note') or payload.get('version_note') or ''), parent_version_id=parent.version_id, variant_type=_interfaces_api_runtime.edit_variant_type(primary.edit_type), change_summary=str(payload.get('change_summary') or f'Review task {task.task_id} candidate {candidate.candidate_id}'))
        _split_state['version'] = next((_split_state['version'] for _split_state['version'] in document.versions if _split_state['version'].job_id == _split_state['job'].job_id))
        return (False, None)

    def _apply_review_task_candidate_part_02(self, project_id: str, task_store: _InterfaceType, task: Any, candidate: Any, parent: Any, parent_job: _InterfaceType, parent_plan: _InterfaceType, payload: ImplementationDocument, _split_state):
        candidate = task_store.update_candidate(type(candidate).from_dict({**candidate.to_dict(), 'status': 'applied'}), event='review_candidate_applied', payload={'version_id': _split_state['version'].version_id, 'job_id': _split_state['job'].job_id}, now=_interfaces_api_runtime._utc_now())
        task = task_store.update_task(type(task).from_dict({**task.to_dict(), 'status': 'applied', 'selected_candidate_id': candidate.candidate_id, 'applied_version_id': _split_state['version'].version_id, 'applied_job_id': _split_state['job'].job_id}), event='review_task_candidate_applied', payload={'candidate_id': candidate.candidate_id, 'version_id': _split_state['version'].version_id, 'job_id': _split_state['job'].job_id}, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(project_id, 'review_task_candidate_applied', {'task_id': task.task_id, 'candidate_id': candidate.candidate_id, 'version_id': _split_state['version'].version_id, 'job_id': _split_state['job'].job_id})
        return (True, (task, candidate, _split_state['version'], _split_state['job'], _split_state['result']))
        return (False, None)

    def _apply_review_task_candidate(self, project_id: str, task_store: _InterfaceType, task: Any, candidate: Any, parent: Any, parent_job: _InterfaceType, parent_plan: _InterfaceType, payload: ImplementationDocument) -> tuple[Any, Any, Any, _InterfaceType, Any]:
        _split_state: dict[str, _InferenceType] = {}
        _split_result = self._apply_review_task_candidate_part_01(project_id, task_store, task, candidate, parent, parent_job, parent_plan, payload, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._apply_review_task_candidate_part_02(project_id, task_store, task, candidate, parent, parent_job, parent_plan, payload, _split_state)
        if _split_result[0]:
            return _split_result[1]
        raise RuntimeError("_apply_review_task_candidate did not produce a result.")

    def _create_review_task_follow_up(self, project_id: str, task_store: _InterfaceType, task: Any, payload: ImplementationDocument) -> tuple[Any, Any]:
        if task.status != "applied" or not task.applied_version_id:
            raise _interfaces_api_runtime.ReviewTaskStateError("Only applied review tasks can be marked needs_more_work.")
        candidate = task_store.read_candidate(task.task_id, task.selected_candidate_id or "")
        _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.applied_version_id)
        preview = _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(task.preview_id)
        audition_store = _interfaces_api_runtime.EditorAuditionStore(self.project_store.project_dir(project_id))
        audition = audition_store.read_audition(task.preview_id, task.audition_id)
        audition_plan = audition_store.read_plan(task.preview_id, task.audition_id)
        follow_up = task_store.create_task(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_plan=parent_plan,
            preview=preview,
            audition=audition,
            audition_plan=audition_plan,
            payload={
                "title": payload.get("title") or f"Follow-up for {task.task_id}",
            },
            previous={
                "previous_task_id": task.task_id,
                "previous_candidate_id": candidate.candidate_id,
                "previous_applied_version_id": task.applied_version_id,
            },
            now=_interfaces_api_runtime._utc_now(),
        )
        task = task_store.update_task(
            type(task).from_dict({**task.to_dict(), "status": "needs_more_work", "follow_up_task_id": follow_up.task_id, "resolution_note": str(payload.get("note") or "")}),
            event="review_task_needs_more_work",
            payload={"follow_up_task_id": follow_up.task_id, "note": payload.get("note") or ""},
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_needs_more_work", {"task_id": task.task_id, "follow_up_task_id": follow_up.task_id, "version_id": task.applied_version_id})
        return task, follow_up

    def _rollback_prompt_ab_groups(self, project_id: str, group_ids: list[str]) -> None:
        if not group_ids:
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(project_dir)
            deleted = []
            for group_id in group_ids:
                try:
                    group_store.delete_group(group_id)
                    deleted.append(group_id)
                except (FileNotFoundError, ValueError):
                    continue
            if deleted:
                self.project_store.append_event(project_id, "provider_prompt_ab_rolled_back", {"group_ids": deleted})
        except (FileNotFoundError, ValueError):
            return

    def _send_runtime_view(self, job: _InterfaceType, view_name: str) -> None:
        run_dir = _interfaces_api_runtime.Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        validator_path = run_dir / "data" / "validator-report.json"
        if view_name in {"timeline", "tracks", "quality"} and not plan_path.exists():
            self._send_error(
                _interfaces_api_runtime.HTTPStatus.CONFLICT,
                "song-plan.json is not available for this job yet.",
            )
            return

        if view_name == "validator":
            report = _interfaces_api_runtime.read_json(validator_path) if validator_path.exists() else None
            plan = _interfaces_api_runtime.read_json(plan_path) if plan_path.exists() else None
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": _interfaces_api_runtime.build_validator_view(report, plan),
                }
            )
            return
        if view_name == "quality":
            plan = _interfaces_api_runtime.read_json(plan_path)
            critic_report = _interfaces_api_runtime._read_critic_report(run_dir)
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": _interfaces_api_runtime.build_quality_view(plan, critic_report),
                }
            )
            return

        plan = _interfaces_api_runtime.read_json(plan_path)
        if view_name == "timeline":
            view = _interfaces_api_runtime.build_timeline_view(plan)
        elif view_name == "tracks":
            view = _interfaces_api_runtime.build_tracks_view(plan)
        else:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Runtime view not found.")
            return
        self._send_json({"job_id": job.job_id, "view": view})

    def _send_nodes_list(self, job: _InterfaceType) -> None:
        records = _interfaces_api_runtime.NodeStore(_interfaces_api_runtime.Path(job.output_dir)).list_nodes()
        self._send_json(
            {
                "job_id": job.job_id,
                "nodes": [record.to_summary_dict() for record in records],
            }
        )

    def _send_node_retry(self, method: str, job: _InterfaceType, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "nodes" or parts[2] != "retry":
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Node route not found.")
            return
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        node_name = _interfaces_api_runtime.unquote(parts[1])
        job, status, error, retry = self.store.retry_job_node(job.job_id, node_name)
        if error is not None:
            self._send_error(status, error)
            return
        self._send_json(
            {"ok": True, "job": job.to_dict() if job is not None else None, "retry": retry},
            status=status,
        )

    def _send_node_route(self, method: str, job: _InterfaceType, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) == 2:
            _nodes, node_name = parts
            try:
                record = _interfaces_api_runtime.NodeStore(_interfaces_api_runtime.Path(job.output_dir)).read_node(_interfaces_api_runtime.unquote(node_name))
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Node record not found.")
                return
            self._send_json({"job_id": job.job_id, "node": record.to_dict()})
            return
        if len(parts) == 3 and parts[2] == "dependencies":
            try:
                node_name = _interfaces_api_runtime.unquote(parts[1])
                upstream = _interfaces_api_runtime.upstream_nodes(node_name)
                downstream = _interfaces_api_runtime.downstream_nodes(node_name)
            except ValueError as exc:
                if str(exc).startswith("Unknown node:"):
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Node record not found.")
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(
                {
                    "job_id": job.job_id,
                    "node": node_name,
                    "upstream": upstream,
                    "downstream": downstream,
                    "affected_nodes": [node_name, *downstream],
                }
            )
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Node route not found.")

    def _send_stem_file(self, job: _InterfaceType, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "stems" or parts[2] not in {"midi", "audio"}:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Stem route not found.")
            return
        stem_id = _interfaces_api_runtime.unquote(parts[1])
        run_dir = _interfaces_api_runtime.Path(job.output_dir)
        manifest = _interfaces_api_runtime.read_stem_manifest(run_dir)
        if manifest is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Stem manifest not found.")
            return
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet.")
            return
        try:
            plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(plan_path))
            if _interfaces_api_runtime.stem_manifest_stale(manifest, plan):
                _interfaces_api_runtime.clear_stem_artifacts(run_dir)
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Stem manifest is stale. Render stems again.")
                return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        try:
            if parts[2] == "midi":
                self._send_file(_interfaces_api_runtime.stem_midi_path(run_dir, manifest, stem_id), "audio/midi")
            else:
                self._send_file(_interfaces_api_runtime.stem_audio_path(run_dir, manifest, stem_id), "audio/wav")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Stem not found.")
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _read_json_body(self) -> ImplementationDocument:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            raise ValueError("Request body must be JSON.")
        data = _interfaces_api_runtime.json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _optional_json_body(self) -> ImplementationDocument:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            return {}
        data = _interfaces_api_runtime.json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _merge_editor_patch_metadata(self, left: ImplementationDocument | None, right: ImplementationDocument | None) -> ImplementationDocument:
        return _interfaces_api_runtime._merge_editor_patch_metadata(left, right)

    def _send_json(self, data: ImplementationDocument, status: _InterfaceType = _interfaces_api_runtime.HTTPStatus.OK) -> None:
        body = _interfaces_api_runtime.json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
