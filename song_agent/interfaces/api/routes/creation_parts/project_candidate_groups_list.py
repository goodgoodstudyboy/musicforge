from __future__ import annotations


from song_agent.platform.contracts.coercion import as_document as _as_document

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectCandidateGroupsList(CreationRouteContext):
    def _create_project_candidate_group_part_01(self, project_id: str, version_id: str, payload: ImplementationDocument, mark_asset_usage: bool, _split_state):
        _document, _split_state['parent'], parent_job, _split_state['parent_plan'] = self._project_edit_parent(project_id, version_id)
        instruction = str(payload.get('instruction') or '').strip()
        if not instruction:
            raise ValueError('instruction is required.')
        candidate_count = int(payload.get('candidate_count') or 3)
        template_id = str(payload.get('template_id') or 'provider-edit-candidates').strip()
        _split_state['template'] = self.prompt_template_store.get_template(template_id)
        if not _split_state['template'].enabled:
            raise ValueError('Prompt template is disabled.')
        config, _sources = _interfaces_api_runtime.load_provider_config()
        _split_state['asset_snapshot'] = _interfaces_api_runtime.asset_refs_snapshot(self.asset_store, payload.get('asset_refs'), captured_at=_interfaces_api_runtime._utc_now())
        asset_prompt_refs = _interfaces_api_runtime.asset_prompt_summaries(self.asset_store, payload.get('asset_refs'))
        _split_state['reference_snapshot'] = _interfaces_api_runtime.reference_refs_snapshot(self.reference_store, payload.get('reference_refs'), captured_at=_interfaces_api_runtime._utc_now())
        reference_prompt_refs = _interfaces_api_runtime.reference_prompt_summaries(self.reference_store, payload.get('reference_refs'))
        _split_state['patches'], provider_snapshot = _interfaces_api_runtime.generate_provider_edit_candidates(parent_plan=_split_state['parent_plan'], instruction=instruction, template=_split_state['template'], config=config, candidate_count=candidate_count, asset_references=asset_prompt_refs, reference_references=reference_prompt_refs)
        provider_usage = _as_document(provider_snapshot.get('usage'))
        project_dir = self.project_store.project_dir(project_id)
        _split_state['group_store'] = _interfaces_api_runtime.CandidateGroupStore(project_dir)
        _split_state['group'] = _split_state['group_store'].create_group(project_id=project_id, parent_version_id=_split_state['parent'].version_id, parent_job_id=parent_job.job_id, instruction=instruction, template_id=_split_state['template'].template_id, candidate_count=len(_split_state['patches']), source={'parent_version_id': _split_state['parent'].version_id, 'parent_job_id': parent_job.job_id, 'song_plan_sha256': _interfaces_api_runtime.song_plan_hash(_split_state['parent_plan']), 'asset_refs': list(_split_state['asset_snapshot']['asset_refs']), 'reference_refs': list(_split_state['reference_snapshot']['reference_refs']), **({'context_pack': dict(payload['context_pack'])} if isinstance(payload.get('context_pack'), dict) else {})}, provider_usage=provider_usage, provider_request_id=None if provider_snapshot.get('request_id') is None else str(provider_snapshot.get('request_id')), now=_interfaces_api_runtime._utc_now())
        usage_record = _interfaces_api_runtime._provider_usage_record(config_snapshot=provider_snapshot, operation='provider_edit_candidates', template_id=_split_state['template'].template_id, started_at=_split_state['group'].created_at, status='completed', provider_usage=provider_usage, request_id=provider_snapshot.get('request_id'))
        write_interface_document(project_dir / 'candidate-groups' / _split_state['group'].group_id / 'provider-usage.json', usage_record)
        return (False, None)

    def _create_project_candidate_group_part_02(self, project_id: str, version_id: str, payload: ImplementationDocument, mark_asset_usage: bool, _split_state):
        for patch in _split_state['patches']:
            try:
                result = _interfaces_api_runtime.apply_provider_edit_patch(_split_state['parent_plan'], patch)
                validator = {'status': 'passed', 'checks': ['provider_edit_patch_schema', 'edit_intent_validation', 'song_plan_validation'], 'checked_at': _interfaces_api_runtime._utc_now()}
                scores = _interfaces_api_runtime.score_provider_edit_candidate(parent_plan=_split_state['parent_plan'], candidate_plan=result.plan, patch=patch, validator_status='passed')
                _split_state['group_store'].add_candidate(_split_state['group'], summary=patch.summary, status='ready', patch=patch.to_dict(), scores=scores.to_dict(), validator=validator, quality=result.plan.quality.to_dict() if result.plan.quality else None, provider_usage={}, candidate_plan=result.plan.to_dict(), now=_interfaces_api_runtime._utc_now())
                current_group = _split_state['group_store'].read_group(_split_state['group'].group_id)
                latest_candidate = current_group.candidates[-1]
                _split_state['group_store'].render_candidate_midi(_split_state['group'].group_id, latest_candidate.candidate_id)
            except Exception as exc:
                _split_state['group_store'].add_candidate(_split_state['group'], summary=patch.summary, status='failed', patch=patch.to_dict(), scores={}, validator={'status': 'failed', 'error': str(exc), 'checked_at': _interfaces_api_runtime._utc_now()}, quality=None, error=str(exc), now=_interfaces_api_runtime._utc_now())
            _split_state['group'] = _split_state['group_store'].read_group(_split_state['group'].group_id)
        if _split_state['asset_snapshot']['asset_refs'] and mark_asset_usage:
            self.asset_store.mark_used(_split_state['asset_snapshot']['asset_refs'], {'usage_type': 'candidate_generation', 'project_id': project_id, 'version_id': _split_state['parent'].version_id, 'candidate_group_id': _split_state['group'].group_id})
        if _split_state['reference_snapshot']['reference_refs'] and mark_asset_usage:
            self.reference_store.mark_used(_split_state['reference_snapshot']['reference_refs'], {'usage_type': 'candidate_generation', 'project_id': project_id, 'version_id': _split_state['parent'].version_id, 'candidate_group_id': _split_state['group'].group_id})
        self.project_store.append_event(project_id, 'provider_edit_candidate_group_created', {'parent_version_id': _split_state['parent'].version_id, 'group_id': _split_state['group'].group_id, 'candidate_count': len(_split_state['group'].candidates), 'template_id': _split_state['template'].template_id, 'status': _split_state['group'].status})
        return (True, _split_state['group'])
        return (False, None)

    def _create_project_candidate_group(self, project_id: str, version_id: str, payload: ImplementationDocument, *, mark_asset_usage: bool=True) -> Any:
        _split_state: ImplementationDocument = {}
        _split_result = self._create_project_candidate_group_part_01(project_id, version_id, payload, mark_asset_usage, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._create_project_candidate_group_part_02(project_id, version_id, payload, mark_asset_usage, _split_state)
        if _split_result[0]:
            return _split_result[1]

    def _handle_project_candidate_groups_list(self, project_id: str) -> None:
        try:
            self.project_store.get_project(project_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            self._send_json({"project_id": project_id, "groups": [group.to_dict() for group in group_store.list_groups()]})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_detail(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            self._send_json({"project_id": project_id, "group": group.to_dict()})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate group not found.")
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_usage(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            _interfaces_api_runtime.CandidateGroupStore(project_dir).read_group(group_id)
            records = _interfaces_api_runtime.collect_candidate_group_provider_usage_records(project_id, group_id, project_dir)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(_interfaces_api_runtime.build_provider_usage_report(scope="candidate_group", project_id=project_id, records=records))

    def _handle_project_candidate_group_apply_part_01(self, method: str, project_id: str, group_id: str, _split_state):
        _split_state['document'] = self.project_store.sync_project(project_id, self.store.get_job)
        _split_state['group_store'] = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
        _split_state['group'] = _split_state['group_store'].read_group(group_id)
        _split_state['parent'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].version_id == _split_state['group'].parent_version_id), None)
        if _split_state['parent'] is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Parent version not found.')
            return (True, None)
        _document, _split_state['parent'], _split_state['parent_job'], _split_state['parent_plan'] = self._project_edit_parent(project_id, _split_state['parent'].version_id)
        if _interfaces_api_runtime.candidate_group_stale(_split_state['group'], _interfaces_api_runtime.song_plan_hash(_split_state['parent_plan'])):
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Provider edit candidate group is stale because the parent song-plan.json has changed.')
            return (True, None)
        if _split_state['group'].status == 'applied':
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Provider edit candidate group has already been applied.')
            return (True, None)
        candidate_id = str(_split_state['payload'].get('candidate_id') or _interfaces_api_runtime._top_ranked_candidate_id(_split_state['group']) or '')
        _split_state['candidate'] = next((item for item in _split_state['group'].candidates if item.candidate_id == candidate_id), None)
        if _split_state['candidate'] is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Candidate not found.')
            return (True, None)
        if _split_state['candidate'].status != 'ready':
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'Only ready candidates can be applied.')
            return (True, None)
        _split_state['patch'] = _interfaces_api_runtime.ProviderEditPatch.from_dict(_split_state['group_store'].read_candidate_patch(_split_state['group'].group_id, _split_state['candidate'].candidate_id))
        candidate_plan = _interfaces_api_runtime.SongPlan.from_dict(_split_state['group_store'].read_candidate_plan(_split_state['group'].group_id, _split_state['candidate'].candidate_id))
        candidate_plan.validate()
        _split_state['intent'] = _interfaces_api_runtime.EditIntent.from_dict({'edit_type': 'section_energy', 'target': {'section_name': _split_state['parent_plan'].sections[0].name}, 'instruction': _split_state['group'].instruction, 'strength': 6, 'provider_mode': 'provider', 'payload': {'candidate_group_id': _split_state['group'].group_id, 'candidate_id': _split_state['candidate'].candidate_id}})
        config, _sources = _interfaces_api_runtime.load_provider_config()
        _split_state['provider_snapshot'] = config.to_snapshot('provider', _interfaces_api_runtime._utc_now())
        _split_state['usage'] = _interfaces_api_runtime._provider_usage_record(config_snapshot=_split_state['provider_snapshot'], operation='provider_edit_candidate_apply', template_id=_split_state['group'].template_id, started_at=_interfaces_api_runtime._utc_now(), status='queued', provider_usage=_split_state['group'].provider_usage, request_id=_split_state['group'].provider_request_id)
        _split_state['name'] = str(_split_state['payload'].get('name') or '') or f"Provider Candidate {len(_split_state['document'].versions) + 1}"
        return (False, None)

    def _handle_project_candidate_group_apply_part_02(self, method: str, project_id: str, group_id: str, _split_state):
        _split_state['job'] = self.store.create_edit_job(project_id=project_id, parent_version_id=_split_state['parent'].version_id, parent_job=_split_state['parent_job'], parent_plan=_split_state['parent_plan'], intent=_split_state['intent'], name=_split_state['name'], start_immediately=bool(_split_state['payload'].get('start_immediately', True)), provider_patch=_split_state['patch'].to_dict(), provider_usage=_split_state['usage'], provider_snapshot=_split_state['provider_snapshot'], template_id=_split_state['group'].template_id, preview_id=_split_state['group'].group_id, candidate_group_id=_split_state['group'].group_id, candidate_id=_split_state['candidate'].candidate_id, candidate=_interfaces_api_runtime._candidate_source_summary({'candidate_group_id': _split_state['group'].group_id, 'candidate_id': _split_state['candidate'].candidate_id, 'rank': _split_state['candidate'].rank, 'score': _split_state['candidate'].scores.get('combined'), 'quality_overall': _split_state['candidate'].scores.get('quality_overall'), 'summary': _split_state['candidate'].summary, 'status': _split_state['candidate'].status, 'created_at': _split_state['candidate'].created_at}), asset_refs=_split_state['group'].source.get('asset_refs') if isinstance(_split_state['group'].source.get('asset_refs'), list) else None, reference_refs=_split_state['group'].source.get('reference_refs') if isinstance(_split_state['group'].source.get('reference_refs'), list) else None, context_pack=_split_state['group'].source.get('context_pack') if isinstance(_split_state['group'].source.get('context_pack'), dict) else None)
        _split_state['document'] = self.project_store.add_version_from_job(project_id, _split_state['job'], name=_split_state['name'], note=str(_split_state['payload'].get('note') or ''), parent_version_id=_split_state['parent'].version_id, variant_type='provider_edit', change_summary=str(_split_state['payload'].get('change_summary') or _split_state['patch'].summary))
        _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].job_id == _split_state['job'].job_id))
        _split_state['group'] = _split_state['group_store'].mark_applied(_split_state['group'].group_id, _split_state['candidate'].candidate_id, version_id=_split_state['version'].version_id, job_id=_split_state['job'].job_id)
        self.project_store.append_event(project_id, 'provider_edit_candidate_applied', {'parent_version_id': _split_state['parent'].version_id, 'group_id': _split_state['group'].group_id, 'candidate_id': _split_state['candidate'].candidate_id, 'version_id': _split_state['version'].version_id, 'job_id': _split_state['job'].job_id})
        return (False, None)

    def _handle_project_candidate_group_apply(self, method: str, project_id: str, group_id: str) -> None:
        _split_state = {}
        if method != 'POST':
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return
        _split_state['payload'] = self._optional_json_body()
        try:
            _split_result = self._handle_project_candidate_group_apply_part_01(method, project_id, group_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_candidate_group_apply_part_02(method, project_id, group_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Candidate group not found.')
            return
        except _interfaces_api_runtime.ProviderError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({'ok': True, **_split_state['document'].to_dict(), 'group': _split_state['group'].to_dict(), 'version': _split_state['version'].to_dict(), 'job': _split_state['job'].to_dict()}, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)

    def _handle_project_candidate_group_delete(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            group_store.delete_group(group_id)
            self.project_store.append_event(project_id, "provider_edit_candidate_group_deleted", {"group_id": group_id})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "group_id": group_id})

    def _handle_project_candidate_group_render(self, method: str, project_id: str, group_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            if action == "render-midi":
                group = group_store.render_group_midi(group.group_id)
            else:
                config, _sources = _interfaces_api_runtime.load_renderer_config()
                config.validate_ready_for_render()
                group = group_store.render_group_audio(group.group_id, config)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()})
