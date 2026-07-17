from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.job_store_context import JobStoreContext

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import Path, apply_asset_refs_to_plan, generate_request, write_asset_refs_snapshot

from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProjectPaths, SongPlan, SongRequest, append_event, clear_stem_artifacts, load_provider_config, read_json, render_midi, write_json, write_reference_refs_snapshot

from song_agent.interfaces.api.runtime_parts.helpers.api_info import _build_summary, _build_validator_report, _utc_now

from song_agent.interfaces.api.runtime_parts.core import JobCancelled

class JobStoreJob(JobStoreContext):
    def _run_job_part_01(self, job_id: str, _split_state):
        append_event(ProjectPaths.create(Path(_split_state['job'].output_dir)), {'event': 'attempt_started', 'attempt_count': _split_state['job'].attempt_count})
        _split_state['job'] = self.get_job(job_id)
        if _split_state['job'] is None or _split_state['job'].cancel_requested:
            if _split_state['job'] is not None:
                self._update_job(_split_state['job'], status='cancelled', step='cancelled', message='Job was cancelled before generation started.')
            return (True, None)
        self._heartbeat(_split_state['job'])
        _context_snapshot = self._prepare_context_pack_for_job(_split_state['job'])
        asset_snapshot = self._prepare_asset_refs_for_job(_split_state['job'])
        reference_snapshot = self._prepare_reference_refs_for_job(_split_state['job'])
        plan_path, midi_path = generate_request(_split_state['request'], out_dir=Path(_split_state['job'].output_dir), force=False, provider_config=_split_state['provider_config'], provider_snapshot=_split_state['provider_snapshot'] if _split_state['provider_config'] is not None else None, control=self._control_callback(job_id), pipeline_mode=_split_state['job'].pipeline_mode)
        if asset_snapshot['asset_refs']:
            plan = SongPlan.from_dict(read_json(plan_path))
            plan = apply_asset_refs_to_plan(plan, self.asset_store, asset_snapshot['asset_refs'])
            write_json(plan_path, plan.to_dict())
            render_midi(plan, midi_path)
            write_asset_refs_snapshot(Path(_split_state['job'].output_dir), asset_snapshot)
            self.asset_store.mark_used(asset_snapshot['asset_refs'], {'usage_type': 'job_generation', 'job_id': _split_state['job'].job_id})
        if reference_snapshot['reference_refs']:
            write_reference_refs_snapshot(Path(_split_state['job'].output_dir), reference_snapshot)
            self.reference_store.mark_used(reference_snapshot['reference_refs'], {'usage_type': 'job_generation', 'job_id': _split_state['job'].job_id})
        clear_stem_artifacts(Path(_split_state['job'].output_dir))
        _split_state['job'] = self.get_job(job_id)
        if _split_state['job'] is None:
            return (True, None)
        if _split_state['job'].cancel_requested:
            self._update_job(_split_state['job'], status='cancelled', step='cancelled', message='Job was cancelled after the generation stage.', finished_at=_utc_now())
            return (True, None)
        self._heartbeat(_split_state['job'])
        validator_report_path = Path(_split_state['job'].output_dir) / 'data' / 'validator-report.json'
        write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
        _split_state['summary'] = _build_summary(plan_path, midi_path)
        _split_state['artifacts'] = {'request': str(Path(_split_state['job'].output_dir) / 'data' / 'request.json'), 'song_plan': str(plan_path), 'run_summary': str(Path(_split_state['job'].output_dir) / 'data' / 'run-summary.json'), 'validator_report': str(validator_report_path), 'job_state': str(Path(_split_state['job'].output_dir) / 'data' / 'job-state.json'), 'events': str(Path(_split_state['job'].output_dir) / 'logs' / 'events.jsonl'), 'midi': str(midi_path)}
        provider_snapshot_path = Path(_split_state['job'].output_dir) / 'data' / 'provider-snapshot.json'
        if provider_snapshot_path.exists():
            _split_state['artifacts']['provider_snapshot'] = str(provider_snapshot_path)
        nodes_dir = Path(_split_state['job'].output_dir) / 'data' / 'nodes'
        if nodes_dir.exists():
            _split_state['artifacts']['nodes'] = str(nodes_dir)
        return (False, None)

    def _run_job_part_02(self, job_id: str, _split_state):
        if (Path(_split_state['job'].output_dir) / 'data' / 'asset-refs.json').exists():
            _split_state['artifacts']['asset_refs'] = str(Path(_split_state['job'].output_dir) / 'data' / 'asset-refs.json')
        if (Path(_split_state['job'].output_dir) / 'data' / 'reference-refs.json').exists():
            _split_state['artifacts']['reference_refs'] = str(Path(_split_state['job'].output_dir) / 'data' / 'reference-refs.json')
        if (Path(_split_state['job'].output_dir) / 'data' / 'context-pack.json').exists():
            _split_state['artifacts']['context_pack'] = str(Path(_split_state['job'].output_dir) / 'data' / 'context-pack.json')
        self._update_job(_split_state['job'], status='completed', step='completed', message='Song generation completed.', summary=_split_state['summary'], error=None, last_error=None, finished_at=_utc_now(), artifacts=_split_state['artifacts'])
        return (False, None)

    def _run_job(self, job_id: str) -> None:
        _split_state = {}
        _split_state['job'] = self.get_job(job_id)
        if _split_state['job'] is None:
            return
        _split_state['request'] = SongRequest.from_dict(_split_state['job'].input_payload)
        _split_state['provider_config'] = None
        _split_state['provider_snapshot'] = _split_state['job'].provider_snapshot
        if _split_state['provider_snapshot'].get('mode') == 'provider':
            _split_state['provider_config'], _sources = load_provider_config()
            _split_state['provider_config'].validate_ready_for_provider()
            ProjectPaths.create(Path(_split_state['job'].output_dir))
            write_json(Path(_split_state['job'].output_dir) / 'data' / 'provider-snapshot.json', _split_state['provider_snapshot'])
        if _split_state['job'].cancel_requested:
            self._update_job(_split_state['job'], status='cancelled', step='cancelled', message='Job was cancelled before generation started.')
            return
        self._update_job(_split_state['job'], status='running', step='generate', message='Generating song plan and MIDI.', attempt_count=_split_state['job'].attempt_count + 1, started_at=_split_state['job'].started_at or _utc_now(), heartbeat_at=_utc_now(), stalled=False)
        try:
            _split_result = self._run_job_part_01(job_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._run_job_part_02(job_id, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except JobCancelled:
            _split_state['job'] = self.get_job(job_id)
            if _split_state['job'] is not None:
                self._update_job(_split_state['job'], status='cancelled', step='cancelled', message='Job was cancelled at a stage boundary.', finished_at=_utc_now())
        except Exception as exc:
            self._update_job(_split_state['job'], status='failed', step='failed', message='Song generation failed.', error=str(exc), last_error=str(exc), finished_at=_utc_now())
