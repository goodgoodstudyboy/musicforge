from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart008:
    def _handle_project_editor_audition_next_action(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            if action == "create-context-pack":
                self._handle_audition_context_pack(project_id, preview_id, audition_id, payload)
                return
            document, parent, parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            review_edit = build_review_edit(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_utc_now(),
            )
            result = apply_review_edit(parent_plan, review_edit)
            validator = {"status": "passed", "checks": ["review_edit_intent", "edit_intent_validation", "song_plan_validation"], "checked_at": _utc_now()}
            if action == "review-edit-preview":
                stored = ReviewEditStore(self.project_store.project_dir(project_id)).create_preview(
                    review_edit=review_edit,
                    parent_plan=parent_plan,
                    result=result,
                    validator=validator,
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "audition_review_edit_preview_created", {"preview_id": preview_id, "audition_id": audition_id, "review_edit_id": stored.review_edit_id})
                self._send_json(
                    {
                        "ok": True,
                        "review_edit": stored.to_dict(),
                        "summary": review_edit_summary(stored, result),
                        "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                        "validator": validator,
                    },
                    status=HTTPStatus.CREATED,
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
                variant_type=edit_variant_type(EditIntent.from_dict(review_edit.intents[0]).edit_type),
                change_summary=str(payload.get("change_summary") or f"Review edit from {audition.audition_id}"),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self.project_store.append_event(project_id, "audition_review_edit_created", {"preview_id": preview_id, "audition_id": audition_id, "version_id": version.version_id, "job_id": job.job_id})
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "review_edit": review_edit.to_dict(), "summary": review_edit_summary(review_edit, result)}, status=HTTPStatus.ACCEPTED)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review edit resource not found.")
        except ReviewEditUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewEditError, EditorAuditionError, EditorPatchStaleError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _review_edit_context(self, project_id: str, preview_id: str, audition_id: str) -> tuple[Any, Any, JobState, SongPlan, Any, Any, SongPlan]:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        preview = preview_store.read_preview(preview_id)
        audition = audition_store.read_audition(preview_id, audition_id)
        audition_plan = audition_store.read_plan(preview_id, audition_id)
        document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        if preview.parent_job_id != parent_job.job_id:
            raise EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        return document, parent, parent_job, parent_plan, preview, audition, audition_plan

    def _handle_project_review_task_create(self, method: str, project_id: str, preview_id: str, audition_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            _document, parent, _parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.create_task(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                preview=preview,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "review_task_created", {"task_id": task.task_id, "preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "task": task.to_dict(), "candidates": [], "events": task_store.read_events(task.task_id)}, status=HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review task source not found.")
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewTaskError, EditorAuditionError, EditorPatchStaleError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))

    def _handle_project_review_tasks_root(self, method: str, project_id: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            query = parse_qs(query_string)
            include_archived = _query_value(query, "include_archived").lower() in {"1", "true", "yes"}
            status = _query_value(query, "status") or None
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            tasks = task_store.list_tasks(include_archived=include_archived, status=status)
            self._send_json({"ok": True, "project_id": project_id, "summary": task_list_summary(tasks), "tasks": [task.to_dict() for task in tasks]})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_sprints_root(self, method: str, project_id: str, query_string: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            task_store = ReviewTaskStore(project_dir)
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived").lower() in {"1", "true", "yes"}
                status = _query_value(query, "status") or None
                sprints = sprint_store.list_sprints(include_archived=include_archived, status=status)
                payloads = [self._review_sprint_public_payload(sprint_store, sprint) for sprint in sprints]
                self._send_json({"ok": True, "project_id": project_id, "summary": _review_sprints_list_summary(payloads), "sprints": payloads})
                return
            if method == "POST":
                payload = self._optional_json_body()
                sprint = sprint_store.create_sprint(project_id=project_id, task_store=task_store, payload=payload, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_created", {"sprint_id": sprint.sprint_id, "task_count": len(sprint.task_refs)})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint), status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ReviewSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewSprintError, ReviewTaskError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
