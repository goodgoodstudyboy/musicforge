from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document, as_list as _as_list

from song_agent.interfaces.api.runtime_parts.job_store_context import JobStoreContext

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import EditIntent, EditedSongPlanResult, JobState, Path, apply_asset_refs_to_plan, apply_edit_intent, asset_refs_snapshot, build_edit_metadata, write_asset_refs_snapshot

from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProjectPaths, ProviderEditPatch, SongPlan, append_event, apply_candidate_intents, apply_provider_edit_patch, apply_review_edit, clear_stem_artifacts, context_pack_snapshot, read_json, reference_refs_snapshot, render_midi, write_context_pack_snapshot, write_json, write_reference_refs_snapshot

from song_agent.interfaces.api.runtime_parts.helpers.api_info import _build_summary, _build_validator_report, _utc_now

from song_agent.interfaces.api.runtime_parts.helpers.job_artifacts import _candidate_source_summary, _job_artifacts

from song_agent.interfaces.api.runtime_parts.core import JobCancelled

class JobStoreEditJob(JobStoreContext):
    def _run_edit_job_part_01(self, job_id: str, _split_state):
        _split_state['metadata'] = dict(_split_state['job'].edit_metadata)
        intent = EditIntent.from_dict(_split_state['metadata'])
        parent_job_id = str(_split_state['metadata'].get('parent_job_id') or '')
        parent_job = self.get_job(parent_job_id)
        if parent_job is None:
            raise FileNotFoundError('Parent version job is missing.')
        parent_plan_path = Path(parent_job.output_dir) / 'data' / 'song-plan.json'
        if not parent_plan_path.exists():
            raise FileNotFoundError('Parent song-plan.json is missing.')
        parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
        append_event(_split_state['paths'], {'event': 'edit_started', 'edit_type': intent.edit_type, 'target': intent.target.to_dict()})
        self._heartbeat(_split_state['job'])
        _split_state['context_snapshot'] = self._prepare_context_pack_for_job(_split_state['job'])
        _split_state['asset_snapshot'] = self._prepare_asset_refs_for_job(_split_state['job'])
        _split_state['reference_snapshot'] = self._prepare_reference_refs_for_job(_split_state['job'])
        provider_patch_data = _split_state['metadata'].get('provider_patch')
        if provider_patch_data:
            patch = ProviderEditPatch.from_dict(provider_patch_data)
            _split_state['result'] = apply_provider_edit_patch(parent_plan, patch)
        else:
            _split_state['result'] = apply_edit_intent(parent_plan, intent)
        if _split_state['asset_snapshot']['asset_refs']:
            result_plan = apply_asset_refs_to_plan(_split_state['result'].plan, self.asset_store, _split_state['asset_snapshot']['asset_refs'])
            _split_state['result'] = EditedSongPlanResult(plan=result_plan, summary=_split_state['result'].summary, warnings=_split_state['result'].warnings)
        if _split_state['metadata'].get('edit_source') == 'audition_review' and isinstance(_split_state['metadata'].get('review_edit'), dict):
            from song_agent.domains.quality.review_edits import ReviewEditIntent
            review_edit_result = apply_review_edit(parent_plan, ReviewEditIntent.from_dict(_split_state['metadata']['review_edit']))
            _split_state['result'] = review_edit_result
            if _split_state['asset_snapshot']['asset_refs']:
                result_plan = apply_asset_refs_to_plan(_split_state['result'].plan, self.asset_store, _split_state['asset_snapshot']['asset_refs'])
                _split_state['result'] = EditedSongPlanResult(plan=result_plan, summary=_split_state['result'].summary, warnings=_split_state['result'].warnings)
        if _split_state['metadata'].get('edit_source') == 'review_task_candidate' and isinstance(_split_state['metadata'].get('review_candidate_intents'), list):
            intents = [EditIntent.from_dict(dict(item)) for item in _split_state['metadata']['review_candidate_intents'] if isinstance(item, dict)]
            _split_state['result'] = apply_candidate_intents(parent_plan, intents)
            if _split_state['asset_snapshot']['asset_refs']:
                result_plan = apply_asset_refs_to_plan(_split_state['result'].plan, self.asset_store, _split_state['asset_snapshot']['asset_refs'])
                _split_state['result'] = EditedSongPlanResult(plan=result_plan, summary=_split_state['result'].summary, warnings=_split_state['result'].warnings)
        if _split_state['job'].cancel_requested:
            raise JobCancelled()
        _split_state['plan_path'] = _split_state['paths'].data / 'song-plan.json'
        _split_state['midi_path'] = _split_state['paths'].renders / 'song.mid'
        _split_state['validator_report_path'] = _split_state['paths'].data / 'validator-report.json'
        request_path = _split_state['paths'].data / 'request.json'
        write_json(request_path, _split_state['job'].input_payload)
        _split_state['edit_metadata'] = build_edit_metadata(project_id=str(_split_state['metadata'].get('project_id') or ''), parent_version_id=str(_split_state['metadata'].get('parent_version_id') or ''), parent_job_id=parent_job.job_id, intent=intent, created_at=str(_split_state['metadata'].get('created_at') or _split_state['job'].created_at), summary=_split_state['result'].summary, warnings=_split_state['result'].warnings)
        _split_state['edit_metadata']['preset'] = _split_state['metadata'].get('preset')
        if provider_patch_data:
            _split_state['edit_metadata']['provider_mode'] = 'provider'
            _split_state['edit_metadata']['provider_patch'] = provider_patch_data
            _split_state['edit_metadata']['provider'] = _split_state['metadata'].get('provider') or {}
            _split_state['edit_metadata']['template_id'] = _split_state['metadata'].get('template_id')
            _split_state['edit_metadata']['preview_id'] = _split_state['metadata'].get('preview_id')
            if _split_state['metadata'].get('candidate_group_id'):
                _split_state['edit_metadata']['candidate_group_id'] = _split_state['metadata'].get('candidate_group_id')
            if _split_state['metadata'].get('candidate_id'):
                _split_state['edit_metadata']['candidate_id'] = _split_state['metadata'].get('candidate_id')
            if _split_state['metadata'].get('candidate'):
                _split_state['edit_metadata']['candidate'] = _candidate_source_summary(_split_state['metadata'].get('candidate'))
        if _split_state['asset_snapshot']['asset_refs']:
            _split_state['edit_metadata']['asset_refs'] = list(_split_state['asset_snapshot']['asset_refs'])
        return (False, None)

    def _run_edit_job_part_02(self, job_id: str, _split_state):
        if _split_state['reference_snapshot']['reference_refs']:
            _split_state['edit_metadata']['reference_refs'] = list(_split_state['reference_snapshot']['reference_refs'])
        if _split_state['context_snapshot']:
            _split_state['edit_metadata']['context_pack'] = _split_state['context_snapshot']
        if _split_state['metadata'].get('edit_source') == 'audition_review':
            _split_state['edit_metadata'].update({'edit_source': 'audition_review', 'review_edit': _split_state['metadata'].get('review_edit'), 'review_summary': _split_state['metadata'].get('review_summary') or {}})
        if _split_state['metadata'].get('edit_source') == 'review_task_candidate':
            _split_state['edit_metadata'].update({'edit_source': 'review_task_candidate', 'operation_count': len(_split_state['metadata'].get('review_candidate_intents') or []), 'review_task': _as_document(_split_state['metadata'].get('review_task')), 'review_candidate': _as_document(_split_state['metadata'].get('review_candidate')), 'review_candidate_source': _as_document(_split_state['metadata'].get('review_candidate_source')), 'review_provider_patch': _as_document(_split_state['metadata'].get('review_provider_patch')), 'review_decision': _as_document(_split_state['metadata'].get('review_decision')), 'review_judge': _as_document(_split_state['metadata'].get('review_judge')), 'review_sprint': _as_document(_split_state['metadata'].get('review_sprint')), 'review_sprint_recommendation': _as_document(_split_state['metadata'].get('review_sprint_recommendation')), 'review_sprint_action_queue': _as_document(_split_state['metadata'].get('review_sprint_action_queue')), 'review_edit': _as_document(_split_state['metadata'].get('review_edit')), 'review_candidate_intents': _as_list(_split_state['metadata'].get('review_candidate_intents'))})
        write_json(_split_state['paths'].data / 'edit-metadata.json', _split_state['edit_metadata'])
        if _split_state['asset_snapshot']['asset_refs']:
            write_asset_refs_snapshot(_split_state['run_dir'], _split_state['asset_snapshot'])
            self.asset_store.mark_used(_split_state['asset_snapshot']['asset_refs'], {'usage_type': 'edit', 'job_id': _split_state['job'].job_id, 'project_id': _split_state['metadata'].get('project_id'), 'version_id': _split_state['metadata'].get('parent_version_id')})
        if _split_state['reference_snapshot']['reference_refs']:
            write_reference_refs_snapshot(_split_state['run_dir'], _split_state['reference_snapshot'])
            self.reference_store.mark_used(_split_state['reference_snapshot']['reference_refs'], {'usage_type': 'edit', 'job_id': _split_state['job'].job_id, 'project_id': _split_state['metadata'].get('project_id'), 'version_id': _split_state['metadata'].get('parent_version_id')})
        if _split_state['metadata'].get('provider_usage'):
            usage = dict(_split_state['metadata']['provider_usage'])
            usage['completed_at'] = _utc_now()
            usage['status'] = 'completed'
            write_json(_split_state['paths'].data / 'provider-usage.json', usage)
        write_json(_split_state['plan_path'], _split_state['result'].plan.to_dict())
        render_midi(_split_state['result'].plan, _split_state['midi_path'])
        clear_stem_artifacts(_split_state['run_dir'])
        write_json(_split_state['validator_report_path'], _build_validator_report(_split_state['plan_path'], _split_state['midi_path']))
        _split_state['summary'] = _build_summary(_split_state['plan_path'], _split_state['midi_path'])
        _split_state['summary']['edit'] = _split_state['result'].summary
        write_json(_split_state['paths'].data / 'run-summary.json', _split_state['summary'])
        _split_state['artifacts'] = _job_artifacts(_split_state['run_dir'], _split_state['plan_path'], _split_state['midi_path'], _split_state['validator_report_path'])
        _split_state['artifacts']['edit_metadata'] = str(_split_state['paths'].data / 'edit-metadata.json')
        if (_split_state['paths'].data / 'asset-refs.json').exists():
            _split_state['artifacts']['asset_refs'] = str(_split_state['paths'].data / 'asset-refs.json')
        if (_split_state['paths'].data / 'reference-refs.json').exists():
            _split_state['artifacts']['reference_refs'] = str(_split_state['paths'].data / 'reference-refs.json')
        if (_split_state['paths'].data / 'context-pack.json').exists():
            _split_state['artifacts']['context_pack'] = str(_split_state['paths'].data / 'context-pack.json')
        if (_split_state['paths'].data / 'provider-usage.json').exists():
            _split_state['artifacts']['provider_usage'] = str(_split_state['paths'].data / 'provider-usage.json')
        return (False, None)

    def _run_edit_job_part_03(self, job_id: str, _split_state):
        self._update_job(_split_state['job'], status='completed', step='completed', message='Edit job completed.', summary=_split_state['summary'], error=None, last_error=None, finished_at=_utc_now(), artifacts=_split_state['artifacts'], edit_metadata=_split_state['edit_metadata'])
        append_event(_split_state['paths'], {'event': 'edit_completed', 'summary': _split_state['result'].summary})
        return (False, None)

    def _run_edit_job(self, job_id: str) -> None:
        _split_state = {}
        _split_state['job'] = self.get_job(job_id)
        if _split_state['job'] is None:
            return
        _split_state['run_dir'] = Path(_split_state['job'].output_dir)
        _split_state['paths'] = ProjectPaths.create(_split_state['run_dir'])
        if _split_state['job'].cancel_requested:
            self._update_job(_split_state['job'], status='cancelled', step='cancelled', message='Edit job was cancelled before generation started.')
            return
        self._update_job(_split_state['job'], status='running', step='edit', message='Applying local edit intent.', attempt_count=_split_state['job'].attempt_count + 1, started_at=_split_state['job'].started_at or _utc_now(), heartbeat_at=_utc_now(), stalled=False)
        try:
            _split_result = self._run_edit_job_part_01(job_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._run_edit_job_part_02(job_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._run_edit_job_part_03(job_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except JobCancelled:
            latest = self.get_job(job_id)
            if latest is not None:
                self._update_job(latest, status='cancelled', step='cancelled', message='Edit job was cancelled at a stage boundary.', finished_at=_utc_now())
        except Exception as exc:
            latest = self.get_job(job_id) or _split_state['job']
            self._update_job(latest, status='failed', step='failed', message='Edit job failed.', error=str(exc), last_error=str(exc), finished_at=_utc_now())

    def _prepare_asset_refs_for_job(self, job: JobState) -> ImplementationDocument:
        snapshot = asset_refs_snapshot(self.asset_store, job.input_payload.get("asset_refs"), captured_at=_utc_now())
        if snapshot["asset_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_asset_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _prepare_reference_refs_for_job(self, job: JobState) -> ImplementationDocument:
        snapshot = reference_refs_snapshot(self.reference_store, job.input_payload.get("reference_refs"), captured_at=_utc_now())
        if snapshot["reference_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_reference_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _prepare_context_pack_for_job(self, job: JobState) -> ImplementationDocument | None:
        context_pack = job.input_payload.get("context_pack")
        if not isinstance(context_pack, dict) or not context_pack.get("pack_id"):
            return None
        pack = self.context_pack_store.read_pack(str(context_pack["pack_id"]))
        applied = {
            "asset_refs": _as_list(job.input_payload.get("asset_refs")),
            "reference_refs": _as_list(job.input_payload.get("reference_refs")),
        }
        snapshot = context_pack_snapshot(pack, applied, captured_at=_utc_now())
        ProjectPaths.create(Path(job.output_dir))
        write_context_pack_snapshot(Path(job.output_dir), snapshot)
        return snapshot
