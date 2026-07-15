from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

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

class CreationRoutes(CreationRoutesProvider, CreationRoutesLibraryRecommend, CreationRoutesReference, CreationRoutesProjectFinalExport, CreationRoutesProjectEdit, CreationRoutesProjectSectionTemplateCreate, CreationRoutesProjectMix, CreationRoutesProjectEditorAuditionNextAction, CreationRoutesProjectReviewSprint, CreationRoutesSaveReviewSprintRecommendationContextPack, CreationRoutesProjectReviewTask, CreationRoutesAuditionContextPack, CreationRoutesProjectEditPreview, CreationRoutesProjectCandidateGroupsList, CreationRoutesProjectCandidateArtifact, CreationRoutesBatch, CreationRoutesExpandContextPackPayload):
    def _handle_project_route(self, method: str, project_id: str, tail: str, query_string: str) -> None:
        editor_state_version = _interfaces_api_runtime._match_project_editor_state_tail(tail)
        if editor_state_version is not None:
            self._handle_project_editor_state(method, project_id, editor_state_version)
            return

        editor_view_match = _interfaces_api_runtime._match_project_editor_view_tail(tail)
        if editor_view_match is not None:
            self._handle_project_editor_view(method, project_id, editor_view_match)
            return

        editor_draft_match = _interfaces_api_runtime._match_project_editor_draft_tail(tail)
        if editor_draft_match is not None:
            self._handle_project_editor_draft(method, project_id, editor_draft_match)
            return

        editor_clips_match = _interfaces_api_runtime._match_project_editor_clips_tail(tail)
        if editor_clips_match is not None:
            self._handle_project_editor_clips(method, project_id, editor_clips_match)
            return

        editor_clip_draft_match = _interfaces_api_runtime._match_project_editor_clip_draft_tail(tail)
        if editor_clip_draft_match is not None:
            self._handle_project_editor_clip_draft(method, project_id, editor_clip_draft_match)
            return

        section_template_match = _interfaces_api_runtime._match_project_section_template_tail(tail)
        if section_template_match is not None:
            self._handle_project_section_template_create(method, project_id, section_template_match)
            return

        track_template_match = _interfaces_api_runtime._match_project_track_template_tail(tail)
        if track_template_match is not None:
            self._handle_project_track_template_create(method, project_id, track_template_match)
            return

        template_mapping_match = _interfaces_api_runtime._match_project_editor_template_mapping_tail(tail)
        if template_mapping_match is not None:
            self._handle_project_editor_template_mapping(method, project_id, template_mapping_match)
            return

        multitrack_draft_match = _interfaces_api_runtime._match_project_editor_multitrack_clip_draft_tail(tail)
        if multitrack_draft_match is not None:
            self._handle_project_editor_multitrack_clip_draft(method, project_id, multitrack_draft_match)
            return

        editor_preview_create = _interfaces_api_runtime._match_project_editor_preview_create_tail(tail)
        if editor_preview_create is not None:
            self._handle_project_editor_preview_create(method, project_id, editor_preview_create)
            return

        version_audio_match = _interfaces_api_runtime._match_project_version_audio_tail(tail)
        if version_audio_match is not None:
            version_id, action = version_audio_match
            self._handle_project_version_audio_route(method, project_id, version_id, action)
            return

        mix_match = _interfaces_api_runtime._match_project_mix_tail(tail)
        if mix_match is not None:
            version_id, action, resource_id = mix_match
            self._handle_project_mix_route(method, project_id, version_id, action, resource_id)
            return

        editor_preview_root = _interfaces_api_runtime._match_project_editor_preview_root_tail(tail)
        if editor_preview_root is not None:
            self._handle_project_editor_preview_root(method, project_id, editor_preview_root)
            return

        if tail == "/audition-reviews":
            self._handle_project_audition_reviews(method, project_id, None, query_string)
            return

        editor_review_root = _interfaces_api_runtime._match_project_editor_audition_reviews_tail(tail)
        if editor_review_root is not None:
            self._handle_project_audition_reviews(method, project_id, editor_review_root, query_string)
            return

        editor_auditions_root = _interfaces_api_runtime._match_project_editor_auditions_root_tail(tail)
        if editor_auditions_root is not None:
            preview_id = editor_auditions_root
            self._handle_project_editor_auditions_root(method, project_id, preview_id)
            return

        editor_audition_marker_match = _interfaces_api_runtime._match_project_editor_audition_marker_tail(tail)
        if editor_audition_marker_match is not None:
            preview_id, audition_id, marker_id, action = editor_audition_marker_match
            self._handle_project_editor_audition_marker_route(method, project_id, preview_id, audition_id, marker_id, action)
            return

        editor_audition_match = _interfaces_api_runtime._match_project_editor_audition_tail(tail)
        if editor_audition_match is not None:
            preview_id, audition_id, action = editor_audition_match
            self._handle_project_editor_audition_route(method, project_id, preview_id, audition_id, action)
            return

        review_sprint_match = _interfaces_api_runtime._match_project_review_sprint_tail(tail)
        if review_sprint_match is not None:
            sprint_id, action = review_sprint_match
            self._handle_project_review_sprint_route(method, project_id, sprint_id, action)
            return

        if tail == "/review-sprints":
            self._handle_project_review_sprints_root(method, project_id, query_string)
            return

        review_task_candidate_match = _interfaces_api_runtime._match_project_review_task_candidate_tail(tail)
        if review_task_candidate_match is not None:
            task_id, candidate_id, action = review_task_candidate_match
            self._handle_project_review_task_candidate_route(method, project_id, task_id, candidate_id, action)
            return

        review_task_match = _interfaces_api_runtime._match_project_review_task_tail(tail)
        if review_task_match is not None:
            task_id, action = review_task_match
            self._handle_project_review_task_route(method, project_id, task_id, action)
            return

        if tail == "/review-tasks":
            self._handle_project_review_tasks_root(method, project_id, query_string)
            return

        if tail == "/acceptance-analytics":
            self._handle_project_acceptance_analytics(method, project_id)
            return

        if tail == "/acceptance-analytics/refresh":
            self._handle_project_acceptance_analytics_refresh(method, project_id)
            return

        editor_preview_match = _interfaces_api_runtime._match_project_editor_preview_tail(tail)
        if editor_preview_match is not None:
            preview_id, action = editor_preview_match
            self._handle_project_editor_preview_route(method, project_id, preview_id, action)
            return

        variation_match = _interfaces_api_runtime._match_project_variation_tail(tail)
        if variation_match is not None:
            parent_version_id = variation_match
            self._handle_project_variation(method, project_id, parent_version_id)
            return

        edit_match = _interfaces_api_runtime._match_project_edit_tail(tail)
        if edit_match is not None:
            version_id, edit_tail = edit_match
            if edit_tail == "edit":
                self._handle_project_edit(method, project_id, version_id)
            else:
                self._handle_project_edit_targets(method, project_id, version_id)
            return

        preview_match = _interfaces_api_runtime._match_project_edit_preview_tail(tail)
        if preview_match is not None:
            parent_version_id, preview_id, action = preview_match
            if action == "create":
                self._handle_project_edit_preview(method, project_id, parent_version_id)
            elif action == "apply":
                self._handle_project_edit_preview_apply(method, project_id, parent_version_id, preview_id)
            elif action == "delete":
                self._handle_project_edit_preview_delete(method, project_id, parent_version_id, preview_id)
            return

        candidate_create_match = _interfaces_api_runtime._match_project_edit_candidates_tail(tail)
        if candidate_create_match is not None:
            version_id, action = candidate_create_match
            if action == "create":
                self._handle_project_edit_candidates(method, project_id, version_id)
            else:
                self._handle_project_prompt_ab_create(method, project_id, version_id)
            return

        candidate_group_match = _interfaces_api_runtime._match_project_candidate_group_tail(tail)
        if candidate_group_match is not None:
            group_id, action = candidate_group_match
            if action == "detail":
                self._handle_project_candidate_group_detail(method, project_id, group_id)
            elif action == "apply":
                self._handle_project_candidate_group_apply(method, project_id, group_id)
            elif action == "delete":
                self._handle_project_candidate_group_delete(method, project_id, group_id)
            elif action in {"render-midi", "render-audio"}:
                self._handle_project_candidate_group_render(method, project_id, group_id, action)
            elif action == "usage":
                self._handle_project_candidate_group_usage(method, project_id, group_id)
            return

        candidate_artifact_match = _interfaces_api_runtime._match_project_candidate_artifact_tail(tail)
        if candidate_artifact_match is not None:
            group_id, candidate_id, action = candidate_artifact_match
            self._handle_project_candidate_artifact(method, project_id, group_id, candidate_id, action)
            return

        prompt_ab_match = _interfaces_api_runtime._match_project_prompt_ab_tail(tail)
        if prompt_ab_match is not None:
            ab_id, action = prompt_ab_match
            if action == "list":
                self._handle_project_prompt_ab_list(method, project_id)
            elif action == "detail":
                self._handle_project_prompt_ab_detail(method, project_id, ab_id)
            else:
                self._handle_project_prompt_ab_delete(method, project_id, ab_id)
            return

        if tail == "/candidate-groups":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._handle_project_candidate_groups_list(project_id)
            return

        if tail == "":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json(document.to_dict())
            return

        if tail == "/versions":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            request_data = payload.get("request")
            if not isinstance(request_data, dict):
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "request must be an object.")
                return
            try:
                self.project_store.get_project(project_id)
                request_payload = {
                    **request_data,
                    "generation_mode": payload.get("generation_mode", request_data.get("generation_mode", "local")),
                    "pipeline_mode": payload.get("pipeline_mode", request_data.get("pipeline_mode", "single")),
                }
                if isinstance(payload.get("asset_refs"), list):
                    request_payload["asset_refs"] = payload["asset_refs"]
                if isinstance(payload.get("reference_refs"), list):
                    request_payload["reference_refs"] = payload["reference_refs"]
                if payload.get("context_pack_id"):
                    request_payload["context_pack_id"] = payload["context_pack_id"]
                request_payload = self._expand_context_pack_payload(request_payload)
                job = self.store.create_job(request_payload)
                document = self.project_store.add_version_from_job(
                    project_id,
                    job,
                    name=str(payload.get("name") or ""),
                    note=str(payload.get("note") or ""),
                )
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json(
                {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
                status=_interfaces_api_runtime.HTTPStatus.ACCEPTED,
            )
            return

        evaluate_match = _interfaces_api_runtime._match_project_evaluate_tail(tail)
        if evaluate_match is not None:
            self._handle_project_evaluate(method, project_id, evaluate_match)
            return

        if tail == "/versions/from-job":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            job_id = str(payload.get("job_id") or "")
            job = self.store.get_job(job_id)
            if job is None:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Job not found.")
                return
            try:
                document = self.project_store.add_version_from_job(
                    project_id,
                    job,
                    name=str(payload.get("name") or ""),
                    note=str(payload.get("note") or ""),
                )
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict()})
            return

        if tail in {"/selected", "/final"}:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            version_id = str(payload.get("version_id") or "")
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                if tail == "/selected":
                    document = self.project_store.set_selected_version(project_id, version_id)
                else:
                    document, gate_result = self._set_final_version_with_gate(
                        project_id,
                        version_id,
                        force=bool(payload.get("force", False)),
                    )
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except PermissionError as exc:
                self._send_json(exc.args[0], status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                return
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
                return
            response = {"ok": True, **document.to_dict()}
            if tail == "/final":
                response["quality_gate"] = gate_result.to_dict()
            self._send_json(response)
            return

        if tail == "/quality-gate":
            self._handle_project_quality_gate(method, project_id)
            return

        if tail == "/references":
            self._handle_project_references(method, project_id)
            return

        if tail in {"/references/link", "/references/unlink"}:
            self._handle_project_reference_link(method, project_id, unlink=tail.endswith("/unlink"))
            return

        if tail == "/quality-gate/evaluate-all":
            self._handle_project_evaluate_all(method, project_id)
            return

        if tail == "/final-export":
            self._handle_project_final_export(method, project_id)
            return

        if tail == "/final-export/zip":
            self._handle_project_final_export_zip(method, project_id)
            return

        if tail == "/final-export.zip":
            self._handle_project_final_export_zip_download(method, project_id)
            return

        if tail == "/delivery-qa":
            self._handle_project_delivery_qa(method, project_id, refresh=False)
            return

        if tail == "/delivery-qa/refresh":
            self._handle_project_delivery_qa(method, project_id, refresh=True)
            return

        if tail == "/delivery-signoff":
            self._handle_project_delivery_signoff(method, project_id, action="get")
            return

        if tail == "/delivery-signoff/reset":
            self._handle_project_delivery_signoff(method, project_id, action="reset")
            return

        if tail == "/release-targets":
            self._handle_project_release_targets(method, project_id)
            return

        if tail == "/add-to-release":
            self._handle_project_add_to_release(method, project_id)
            return

        if tail == "/diff":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = _interfaces_api_runtime.parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.diff_versions(project_id, left, right))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/compare":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = _interfaces_api_runtime.parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(_interfaces_api_runtime.compare_project_versions(document, left, right))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/provider-usage":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._handle_project_provider_usage(project_id)
            return

        if tail == "/usage/provider":
            self._handle_project_provider_usage_report(method, project_id)
            return

        if tail == "/review-metrics":
            self._handle_project_review_metrics(method, project_id, refresh=False)
            return

        if tail == "/review-metrics/refresh":
            self._handle_project_review_metrics(method, project_id, refresh=True)
            return

        if tail == "/export":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(_interfaces_api_runtime.sanitize_metadata(self.project_store.export_project(project_id)))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail == "/events":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.get_project(project_id)
                self._send_json({"events": self.project_store.read_events(project_id)})
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.hide_project(project_id, tail == "/hide")
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/delete":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.delete_project(project_id)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, "deleted": True, "project_id": project_id})
            return

        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project route not found.")
