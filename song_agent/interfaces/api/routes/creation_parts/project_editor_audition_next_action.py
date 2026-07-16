from __future__ import annotations

from typing import Any


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectEditorAuditionNextAction:
    def _handle_project_editor_audition_next_action(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            if action == "create-context-pack":
                self._handle_audition_context_pack(project_id, preview_id, audition_id, payload)
                return
            document, parent, parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            review_edit = _interfaces_api_runtime.build_review_edit(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_interfaces_api_runtime._utc_now(),
            )
            result = _interfaces_api_runtime.apply_review_edit(parent_plan, review_edit)
            validator = {"status": "passed", "checks": ["review_edit_intent", "edit_intent_validation", "song_plan_validation"], "checked_at": _interfaces_api_runtime._utc_now()}
            if action == "review-edit-preview":
                stored = _interfaces_api_runtime.ReviewEditStore(self.project_store.project_dir(project_id)).create_preview(
                    review_edit=review_edit,
                    parent_plan=parent_plan,
                    result=result,
                    validator=validator,
                    now=_interfaces_api_runtime._utc_now(),
                )
                self.project_store.append_event(project_id, "audition_review_edit_preview_created", {"preview_id": preview_id, "audition_id": audition_id, "review_edit_id": stored.review_edit_id})
                self._send_json(
                    {
                        "ok": True,
                        "review_edit": stored.to_dict(),
                        "summary": _interfaces_api_runtime.review_edit_summary(stored, result),
                        "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                        "validator": validator,
                    },
                    status=_interfaces_api_runtime.HTTPStatus.CREATED,
                )
                return
            if action == "provider-review-edit-preview":
                self._handle_provider_review_edit_preview(project_id, parent, parent_job, parent_plan, review_edit, payload)
                return
            job = self._create_review_edit_job(
                project_id=project_id,
                parent=parent,
                parent_job=parent_job,
                parent_plan=parent_plan,
                review_edit=review_edit,
                result=result,
                payload=payload,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("version_name") or payload.get("name") or "Review Edit"),
                note=str(payload.get("version_note") or payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=_interfaces_api_runtime.edit_variant_type(_interfaces_api_runtime.EditIntent.from_dict(review_edit.intents[0]).edit_type),
                change_summary=str(payload.get("change_summary") or f"Review edit from {audition.audition_id}"),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self.project_store.append_event(project_id, "audition_review_edit_created", {"preview_id": preview_id, "audition_id": audition_id, "version_id": version.version_id, "job_id": job.job_id})
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "review_edit": review_edit.to_dict(), "summary": _interfaces_api_runtime.review_edit_summary(review_edit, result)}, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review edit resource not found.")
        except _interfaces_api_runtime.ReviewEditUnavailableError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.ReviewEditError, _interfaces_api_runtime.EditorAuditionError, _interfaces_api_runtime.EditorPatchStaleError, ValueError) as exc:
            status = _interfaces_api_runtime.HTTPStatus.CONFLICT if "stale" in str(exc).lower() else _interfaces_api_runtime.HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except _interfaces_api_runtime.ProviderError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _review_edit_context(self, project_id: str, preview_id: str, audition_id: str) -> tuple[Any, Any, _interfaces_api_runtime.JobState, _interfaces_api_runtime.SongPlan, Any, Any, _interfaces_api_runtime.SongPlan]:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        preview_store = _interfaces_api_runtime.EditorPreviewStore(project_dir)
        audition_store = _interfaces_api_runtime.EditorAuditionStore(project_dir)
        preview = preview_store.read_preview(preview_id)
        audition = audition_store.read_audition(preview_id, audition_id)
        audition_plan = audition_store.read_plan(preview_id, audition_id)
        document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        if preview.parent_job_id != parent_job.job_id:
            raise _interfaces_api_runtime.EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if _interfaces_api_runtime.editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise _interfaces_api_runtime.EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        return document, parent, parent_job, parent_plan, preview, audition, audition_plan

    def _handle_project_review_task_create(self, method: str, project_id: str, preview_id: str, audition_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            _document, parent, _parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            task_store = _interfaces_api_runtime.ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.create_task(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                preview=preview,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "review_task_created", {"task_id": task.task_id, "preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "task": task.to_dict(), "candidates": [], "events": task_store.read_events(task.task_id)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review task source not found.")
        except _interfaces_api_runtime.ReviewTaskStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.EditorAuditionError, _interfaces_api_runtime.EditorPatchStaleError, ValueError) as exc:
            status = _interfaces_api_runtime.HTTPStatus.CONFLICT if "stale" in str(exc).lower() else _interfaces_api_runtime.HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))

    def _handle_project_review_tasks_root(self, method: str, project_id: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_archived = _interfaces_api_runtime._query_value(query, "include_archived").lower() in {"1", "true", "yes"}
            status = _interfaces_api_runtime._query_value(query, "status") or None
            task_store = _interfaces_api_runtime.ReviewTaskStore(self.project_store.project_dir(project_id))
            tasks = task_store.list_tasks(include_archived=include_archived, status=status)
            self._send_json({"ok": True, "project_id": project_id, "summary": _interfaces_api_runtime.task_list_summary(tasks), "tasks": [task.to_dict() for task in tasks]})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_sprints_root(self, method: str, project_id: str, query_string: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
            task_store = _interfaces_api_runtime.ReviewTaskStore(project_dir)
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived").lower() in {"1", "true", "yes"}
                status = _interfaces_api_runtime._query_value(query, "status") or None
                sprints = sprint_store.list_sprints(include_archived=include_archived, status=status)
                payloads = [self._review_sprint_public_payload(sprint_store, sprint) for sprint in sprints]
                self._send_json({"ok": True, "project_id": project_id, "summary": _interfaces_api_runtime._review_sprints_list_summary(payloads), "sprints": payloads})
                return
            if method == "POST":
                payload = self._optional_json_body()
                sprint = sprint_store.create_sprint(project_id=project_id, task_store=task_store, payload=payload, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "review_sprint_created", {"sprint_id": sprint.sprint_id, "task_count": len(sprint.task_refs)})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint), status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except _interfaces_api_runtime.ReviewSprintStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.ReviewSprintError, _interfaces_api_runtime.ReviewTaskError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
