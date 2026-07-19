from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from song_agent.interfaces.api.route_contexts.core import CoreRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from .creation_parts.provider import CreationRoutesProvider

from .creation_parts.library_recommend import CreationRoutesLibraryRecommend

from .creation_parts.reference import CreationRoutesReference

from .creation_parts.project_final_export import CreationRoutesProjectFinalExport

from .creation_parts.project_edit import CreationRoutesProjectEdit

from .creation_parts.project_section_template_create import CreationRoutesProjectSectionTemplateCreate

from .creation_parts.project_mix import CreationRoutesProjectMix

from .creation_parts.project_editor_audition_next_action import CreationRoutesProjectEditorAuditionNextAction

from .creation_parts.project_review_sprint import CreationRoutesProjectReviewSprint

from .creation_parts.save_review_sprint_recommendation_context_pack import CreationRoutesSaveReviewSprintRecommendationContextPack

from .creation_parts.project_review_task import CreationRoutesProjectReviewTask

from .creation_parts.audition_context_pack import CreationRoutesAuditionContextPack

from .creation_parts.project_edit_preview import CreationRoutesProjectEditPreview

from .creation_parts.project_candidate_groups_list import CreationRoutesProjectCandidateGroupsList

from .creation_parts.project_candidate_artifact import CreationRoutesProjectCandidateArtifact

from .creation_parts.batch import CreationRoutesBatch

from .creation_parts.expand_context_pack_payload import CreationRoutesExpandContextPackPayload

class CreationRoutes(CreationRoutesProvider, CreationRoutesLibraryRecommend, CreationRoutesReference, CreationRoutesProjectFinalExport, CreationRoutesProjectEdit, CreationRoutesProjectSectionTemplateCreate, CreationRoutesProjectMix, CreationRoutesProjectEditorAuditionNextAction, CreationRoutesProjectReviewSprint, CreationRoutesSaveReviewSprintRecommendationContextPack, CreationRoutesProjectReviewTask, CreationRoutesAuditionContextPack, CreationRoutesProjectEditPreview, CreationRoutesProjectCandidateGroupsList, CreationRoutesProjectCandidateArtifact, CreationRoutesBatch, CreationRoutesExpandContextPackPayload, CoreRouteContext):
    def _handle_project_route_part_01(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        editor_state_version = _interfaces_api_runtime._match_project_editor_state_tail(tail)
        if editor_state_version is not None:
            self._handle_project_editor_state(method, project_id, editor_state_version)
            return (True, None)
        editor_view_match = _interfaces_api_runtime._match_project_editor_view_tail(tail)
        if editor_view_match is not None:
            self._handle_project_editor_view(method, project_id, editor_view_match)
            return (True, None)
        editor_draft_match = _interfaces_api_runtime._match_project_editor_draft_tail(tail)
        if editor_draft_match is not None:
            self._handle_project_editor_draft(method, project_id, editor_draft_match)
            return (True, None)
        editor_clips_match = _interfaces_api_runtime._match_project_editor_clips_tail(tail)
        if editor_clips_match is not None:
            self._handle_project_editor_clips(method, project_id, editor_clips_match)
            return (True, None)
        editor_clip_draft_match = _interfaces_api_runtime._match_project_editor_clip_draft_tail(tail)
        if editor_clip_draft_match is not None:
            self._handle_project_editor_clip_draft(method, project_id, editor_clip_draft_match)
            return (True, None)
        section_template_match = _interfaces_api_runtime._match_project_section_template_tail(tail)
        if section_template_match is not None:
            self._handle_project_section_template_create(method, project_id, section_template_match)
            return (True, None)
        track_template_match = _interfaces_api_runtime._match_project_track_template_tail(tail)
        if track_template_match is not None:
            self._handle_project_track_template_create(method, project_id, track_template_match)
            return (True, None)
        template_mapping_match = _interfaces_api_runtime._match_project_editor_template_mapping_tail(tail)
        if template_mapping_match is not None:
            self._handle_project_editor_template_mapping(method, project_id, template_mapping_match)
            return (True, None)
        multitrack_draft_match = _interfaces_api_runtime._match_project_editor_multitrack_clip_draft_tail(tail)
        if multitrack_draft_match is not None:
            self._handle_project_editor_multitrack_clip_draft(method, project_id, multitrack_draft_match)
            return (True, None)
        editor_preview_create = _interfaces_api_runtime._match_project_editor_preview_create_tail(tail)
        if editor_preview_create is not None:
            self._handle_project_editor_preview_create(method, project_id, editor_preview_create)
            return (True, None)
        version_audio_match = _interfaces_api_runtime._match_project_version_audio_tail(tail)
        if version_audio_match is not None:
            _split_state['version_id'], _split_state['action'] = version_audio_match
            self._handle_project_version_audio_route(method, project_id, _split_state['version_id'], _split_state['action'])
            return (True, None)
        mix_match = _interfaces_api_runtime._match_project_mix_tail(tail)
        if mix_match is not None:
            _split_state['version_id'], _split_state['action'], resource_id = mix_match
            self._handle_project_mix_route(method, project_id, _split_state['version_id'], _split_state['action'], resource_id)
            return (True, None)
        editor_preview_root = _interfaces_api_runtime._match_project_editor_preview_root_tail(tail)
        if editor_preview_root is not None:
            self._handle_project_editor_preview_root(method, project_id, editor_preview_root)
            return (True, None)
        if tail == '/audition-reviews':
            self._handle_project_audition_reviews(method, project_id, None, query_string)
            return (True, None)
        editor_review_root = _interfaces_api_runtime._match_project_editor_audition_reviews_tail(tail)
        if editor_review_root is not None:
            self._handle_project_audition_reviews(method, project_id, editor_review_root, query_string)
            return (True, None)
        editor_auditions_root = _interfaces_api_runtime._match_project_editor_auditions_root_tail(tail)
        if editor_auditions_root is not None:
            _split_state['preview_id'] = editor_auditions_root
            self._handle_project_editor_auditions_root(method, project_id, _split_state['preview_id'])
            return (True, None)
        _split_state['editor_audition_marker_match'] = _interfaces_api_runtime._match_project_editor_audition_marker_tail(tail)
        return (False, None)

    def _handle_project_route_part_02(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if _split_state['editor_audition_marker_match'] is not None:
            _split_state['preview_id'], audition_id, marker_id, _split_state['action'] = _split_state['editor_audition_marker_match']
            self._handle_project_editor_audition_marker_route(method, project_id, _split_state['preview_id'], audition_id, marker_id, _split_state['action'])
            return (True, None)
        editor_audition_match = _interfaces_api_runtime._match_project_editor_audition_tail(tail)
        if editor_audition_match is not None:
            _split_state['preview_id'], audition_id, _split_state['action'] = editor_audition_match
            self._handle_project_editor_audition_route(method, project_id, _split_state['preview_id'], audition_id, _split_state['action'])
            return (True, None)
        review_sprint_match = _interfaces_api_runtime._match_project_review_sprint_tail(tail)
        if review_sprint_match is not None:
            sprint_id, _split_state['action'] = review_sprint_match
            self._handle_project_review_sprint_route(method, project_id, sprint_id, _split_state['action'])
            return (True, None)
        if tail == '/review-sprints':
            self._handle_project_review_sprints_root(method, project_id, query_string)
            return (True, None)
        review_task_candidate_match = _interfaces_api_runtime._match_project_review_task_candidate_tail(tail)
        if review_task_candidate_match is not None:
            task_id, _split_state['candidate_id'], _split_state['action'] = review_task_candidate_match
            self._handle_project_review_task_candidate_route(method, project_id, task_id, _split_state['candidate_id'], _split_state['action'])
            return (True, None)
        review_task_match = _interfaces_api_runtime._match_project_review_task_tail(tail)
        if review_task_match is not None:
            task_id, _split_state['action'] = review_task_match
            self._handle_project_review_task_route(method, project_id, task_id, _split_state['action'])
            return (True, None)
        if tail == '/review-tasks':
            self._handle_project_review_tasks_root(method, project_id, query_string)
            return (True, None)
        if tail == '/acceptance-analytics':
            self._handle_project_acceptance_analytics(method, project_id)
            return (True, None)
        if tail == '/acceptance-analytics/refresh':
            self._handle_project_acceptance_analytics_refresh(method, project_id)
            return (True, None)
        editor_preview_match = _interfaces_api_runtime._match_project_editor_preview_tail(tail)
        if editor_preview_match is not None:
            _split_state['preview_id'], _split_state['action'] = editor_preview_match
            self._handle_project_editor_preview_route(method, project_id, _split_state['preview_id'], _split_state['action'])
            return (True, None)
        variation_match = _interfaces_api_runtime._match_project_variation_tail(tail)
        if variation_match is not None:
            parent_version_id = variation_match
            self._handle_project_variation(method, project_id, parent_version_id)
            return (True, None)
        edit_match = _interfaces_api_runtime._match_project_edit_tail(tail)
        if edit_match is not None:
            _split_state['version_id'], edit_tail = edit_match
            if edit_tail == 'edit':
                self._handle_project_edit(method, project_id, _split_state['version_id'])
            else:
                self._handle_project_edit_targets(method, project_id, _split_state['version_id'])
            return (True, None)
        preview_match = _interfaces_api_runtime._match_project_edit_preview_tail(tail)
        if preview_match is not None:
            parent_version_id, _split_state['preview_id'], _split_state['action'] = preview_match
            if _split_state['action'] == 'create':
                self._handle_project_edit_preview(method, project_id, parent_version_id)
            elif _split_state['action'] == 'apply':
                self._handle_project_edit_preview_apply(method, project_id, parent_version_id, _split_state['preview_id'])
            elif _split_state['action'] == 'delete':
                self._handle_project_edit_preview_delete(method, project_id, parent_version_id, _split_state['preview_id'])
            return (True, None)
        _split_state['candidate_create_match'] = _interfaces_api_runtime._match_project_edit_candidates_tail(tail)
        return (False, None)

    def _handle_project_route_part_03(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if _split_state['candidate_create_match'] is not None:
            _split_state['version_id'], _split_state['action'] = _split_state['candidate_create_match']
            if _split_state['action'] == 'create':
                self._handle_project_edit_candidates(method, project_id, _split_state['version_id'])
            else:
                self._handle_project_prompt_ab_create(method, project_id, _split_state['version_id'])
            return (True, None)
        candidate_group_match = _interfaces_api_runtime._match_project_candidate_group_tail(tail)
        if candidate_group_match is not None:
            group_id, _split_state['action'] = candidate_group_match
            if _split_state['action'] == 'detail':
                self._handle_project_candidate_group_detail(method, project_id, group_id)
            elif _split_state['action'] == 'apply':
                self._handle_project_candidate_group_apply(method, project_id, group_id)
            elif _split_state['action'] == 'delete':
                self._handle_project_candidate_group_delete(method, project_id, group_id)
            elif _split_state['action'] in {'render-midi', 'render-audio'}:
                self._handle_project_candidate_group_render(method, project_id, group_id, _split_state['action'])
            elif _split_state['action'] == 'usage':
                self._handle_project_candidate_group_usage(method, project_id, group_id)
            return (True, None)
        candidate_artifact_match = _interfaces_api_runtime._match_project_candidate_artifact_tail(tail)
        if candidate_artifact_match is not None:
            group_id, _split_state['candidate_id'], _split_state['action'] = candidate_artifact_match
            self._handle_project_candidate_artifact(method, project_id, group_id, _split_state['candidate_id'], _split_state['action'])
            return (True, None)
        prompt_ab_match = _interfaces_api_runtime._match_project_prompt_ab_tail(tail)
        if prompt_ab_match is not None:
            ab_id, _split_state['action'] = prompt_ab_match
            if _split_state['action'] == 'list':
                self._handle_project_prompt_ab_list(method, project_id)
            elif _split_state['action'] == 'detail':
                self._handle_project_prompt_ab_detail(method, project_id, ab_id)
            else:
                self._handle_project_prompt_ab_delete(method, project_id, ab_id)
            return (True, None)
        if tail == '/candidate-groups':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._handle_project_candidate_groups_list(project_id)
            return (True, None)
        if tail == '':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                _split_state['document'] = self.project_store.sync_project(project_id, self.store.get_job)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            self._send_json(_split_state['document'].to_dict())
            return (True, None)
        return (False, None)

    def _handle_project_route_part_04(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if tail == '/versions':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            request_data = _split_state['payload'].get('request')
            if not isinstance(request_data, dict):
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'request must be an object.')
                return (True, None)
            try:
                self.project_store.get_project(project_id)
                request_payload = {**request_data, 'generation_mode': _split_state['payload'].get('generation_mode', request_data.get('generation_mode', 'local')), 'pipeline_mode': _split_state['payload'].get('pipeline_mode', request_data.get('pipeline_mode', 'single'))}
                if isinstance(_split_state['payload'].get('asset_refs'), list):
                    request_payload['asset_refs'] = _split_state['payload']['asset_refs']
                if isinstance(_split_state['payload'].get('reference_refs'), list):
                    request_payload['reference_refs'] = _split_state['payload']['reference_refs']
                if _split_state['payload'].get('context_pack_id'):
                    request_payload['context_pack_id'] = _split_state['payload']['context_pack_id']
                request_payload = self._expand_context_pack_payload(request_payload)
                _split_state['job'] = self.store.create_job(request_payload)
                _split_state['document'] = self.project_store.add_version_from_job(project_id, _split_state['job'], name=str(_split_state['payload'].get('name') or ''), note=str(_split_state['payload'].get('note') or ''))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return (True, None)
            _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].job_id == _split_state['job'].job_id))
            self._send_json({'ok': True, **_split_state['document'].to_dict(), 'version': _split_state['version'].to_dict(), 'job': _split_state['job'].to_dict()}, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
            return (True, None)
        evaluate_match = _interfaces_api_runtime._match_project_evaluate_tail(tail)
        if evaluate_match is not None:
            self._handle_project_evaluate(method, project_id, evaluate_match)
            return (True, None)
        return (False, None)

    def _handle_project_route_part_05(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if tail == '/versions/from-job':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            job_id = str(_split_state['payload'].get('job_id') or '')
            _split_state['job'] = self.store.get_job(job_id)
            if _split_state['job'] is None:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Job not found.')
                return (True, None)
            try:
                _split_state['document'] = self.project_store.add_version_from_job(project_id, _split_state['job'], name=str(_split_state['payload'].get('name') or ''), note=str(_split_state['payload'].get('note') or ''))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return (True, None)
            _split_state['version'] = next((_split_state['version'] for _split_state['version'] in _split_state['document'].versions if _split_state['version'].job_id == _split_state['job'].job_id))
            self._send_json({'ok': True, **_split_state['document'].to_dict(), 'version': _split_state['version'].to_dict()})
            return (True, None)
        if tail in {'/selected', '/final'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            _split_state['version_id'] = str(_split_state['payload'].get('version_id') or '')
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                if tail == '/selected':
                    _split_state['document'] = self.project_store.set_selected_version(project_id, _split_state['version_id'])
                else:
                    _split_state['document'], gate_result = self._set_final_version_with_gate(project_id, _split_state['version_id'], force=bool(_split_state['payload'].get('force', False)))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Version not found.')
                return (True, None)
            except PermissionError as exc:
                self._send_json(exc.args[0], status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                return (True, None)
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return (True, None)
            response = {'ok': True, **_split_state['document'].to_dict()}
            if tail == '/final':
                response['quality_gate'] = gate_result.to_dict()
            self._send_json(response)
            return (True, None)
        if tail == '/quality-gate':
            self._handle_project_quality_gate(method, project_id)
            return (True, None)
        if tail == '/references':
            self._handle_project_references(method, project_id)
            return (True, None)
        if tail in {'/references/link', '/references/unlink'}:
            self._handle_project_reference_link(method, project_id, unlink=tail.endswith('/unlink'))
            return (True, None)
        if tail == '/quality-gate/evaluate-all':
            self._handle_project_evaluate_all(method, project_id)
            return (True, None)
        return (False, None)

    def _handle_project_route_part_06(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if tail == '/final-export':
            self._handle_project_final_export(method, project_id)
            return (True, None)
        if tail == '/final-export/zip':
            self._handle_project_final_export_zip(method, project_id)
            return (True, None)
        if tail == '/final-export.zip':
            self._handle_project_final_export_zip_download(method, project_id)
            return (True, None)
        if tail == '/delivery-qa':
            self._handle_project_delivery_qa(method, project_id, refresh=False)
            return (True, None)
        if tail == '/delivery-qa/refresh':
            self._handle_project_delivery_qa(method, project_id, refresh=True)
            return (True, None)
        if tail == '/delivery-signoff':
            self._handle_project_delivery_signoff(method, project_id, action='get')
            return (True, None)
        if tail == '/delivery-signoff/reset':
            self._handle_project_delivery_signoff(method, project_id, action='reset')
            return (True, None)
        if tail == '/release-targets':
            self._handle_project_release_targets(method, project_id)
            return (True, None)
        if tail == '/add-to-release':
            self._handle_project_add_to_release(method, project_id)
            return (True, None)
        if tail == '/diff':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            query = _interfaces_api_runtime.parse_qs(query_string)
            left = str(query.get('left', [''])[0])
            right = str(query.get('right', [''])[0])
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.diff_versions(project_id, left, right))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Version not found.')
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return (True, None)
        if tail == '/compare':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            query = _interfaces_api_runtime.parse_qs(query_string)
            left = str(query.get('left', [''])[0])
            right = str(query.get('right', [''])[0])
            try:
                _split_state['document'] = self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(_interfaces_api_runtime.compare_project_versions(_split_state['document'], left, right))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Version not found.')
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return (True, None)
        if tail == '/provider-usage':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._handle_project_provider_usage(project_id)
            return (True, None)
        if tail == '/usage/provider':
            self._handle_project_provider_usage_report(method, project_id)
            return (True, None)
        if tail == '/review-metrics':
            self._handle_project_review_metrics(method, project_id, refresh=False)
            return (True, None)
        return (False, None)

    def _handle_project_route_part_07(self, method: str, project_id: str, tail: str, query_string: str, _split_state):
        if tail == '/review-metrics/refresh':
            self._handle_project_review_metrics(method, project_id, refresh=True)
            return (True, None)
        if tail == '/export':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(_interfaces_api_runtime.sanitize_metadata(self.project_store.export_project(project_id)))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
            return (True, None)
        if tail == '/events':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                self.project_store.get_project(project_id)
                self._send_json({'events': self.project_store.read_events(project_id)})
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
            return (True, None)
        if tail in {'/hide', '/unhide'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                _split_state['document'] = self.project_store.hide_project(project_id, tail == '/hide')
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            self._send_json({'ok': True, **_split_state['document'].to_dict()})
            return (True, None)
        if tail == '/delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                self.project_store.delete_project(project_id)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project not found.')
                return (True, None)
            self._send_json({'ok': True, 'deleted': True, 'project_id': project_id})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Project route not found.')
        return (False, None)

    def _handle_project_route(self, method: str, project_id: str, tail: str, query_string: str) -> None:
        _split_state: ImplementationDocument = {}
        _split_result = self._handle_project_route_part_01(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_02(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_03(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_04(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_05(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_06(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_project_route_part_07(method, project_id, tail, query_string, _split_state)
        if _split_result[0]:
            return _split_result[1]
