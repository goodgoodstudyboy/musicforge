from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart012:
    def _handle_audition_context_pack(self, project_id: str, preview_id: str, audition_id: str, payload: dict[str, Any]) -> None:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        audition = EditorAuditionStore(project_dir).read_audition(preview_id, audition_id)
        review = audition.review if isinstance(audition.review, dict) else {}
        asset_id = str(payload.get("asset_id") or review.get("last_asset_id") or "").strip()
        if not asset_id:
            raise ReviewEditUnavailableError("No audition asset is available for context pack creation.")
        pack = self.context_pack_store.create_pack(
            {
                "name": payload.get("name") or f"Context from {audition_id}",
                "description": payload.get("description") or "Created from audition review.",
                "created_from": {
                    "source_type": "audition_review",
                    "project_id": project_id,
                    "preview_id": preview_id,
                    "audition_id": audition_id,
                    "rating": review.get("rating", 0),
                    "status": review.get("status", "unreviewed"),
                },
                "asset_refs": [{"asset_id": asset_id, "role": "audition_review_favorite", "strength": 0.9}],
                "selection": {
                    "mode": "audition_review",
                    "selected_by": "user",
                    "score_summary": [{"asset_id": asset_id, "rating": review.get("rating", 0), "favorite": bool(review.get("favorite", False))}],
                },
            },
            asset_store=self.asset_store,
            reference_store=self.reference_store,
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "audition_review_context_pack_created", {"preview_id": preview_id, "audition_id": audition_id, "pack_id": pack.pack_id, "asset_id": asset_id})
        self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)}, status=HTTPStatus.CREATED)

    def _handle_project_editor_audition_marker_route(self, method: str, project_id: str, preview_id: str, audition_id: str, marker_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            audition_store.read_audition(preview_id, audition_id)
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "update":
                audition = audition_store.update_marker(preview_id, audition_id, marker_id, self._read_json_body(), now=_utc_now())
                marker = next((item for item in audition.review.get("markers", []) if item.get("marker_id") == marker_id), None)
                self.project_store.append_event(project_id, "editor_audition_marker_updated", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker})
                return
            if action == "delete":
                audition = audition_store.delete_marker(preview_id, audition_id, marker_id, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_marker_deleted", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "deleted": True, "marker_id": marker_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition marker route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition marker not found.")
        except (EditorReviewError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_audition_reviews(self, method: str, project_id: str, preview_id: str | None, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            if preview_id is not None:
                EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(preview_id)
            query = parse_qs(query_string)
            filters = {
                key: _query_value(query, key)
                for key in ("source", "status", "favorite", "min_rating", "track_mode", "range_mode", "sort", "order", "limit")
                if _query_value(query, key)
            }
            board = EditorAuditionStore(self.project_store.project_dir(project_id)).review_board(preview_id=preview_id, filters=filters)
            self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, **board})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project or editor preview not found.")
        except (EditorReviewError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_preview_route(self, method: str, project_id: str, preview_id: str, action: str) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = store.read_preview(preview_id)
                self._send_json({"ok": True, "preview": preview.to_dict()})
                return
            if action == "patch":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                include_operations = "include_operations=true" in self.path or "include_operations=1" in self.path
                self._send_json({"ok": True, "patch": store.read_patch_summary(preview_id, include_operations=include_operations)})
                return
            if action == "song-plan":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "song_plan": store.read_plan(preview_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                self._send_file(store.preview_dir(preview_id) / "song.mid", "audio/midi", filename=f"{project_id}-{preview_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                audio_path = store.preview_dir(preview_id) / "song.wav"
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Preview audio render is not available.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{preview_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "preview": self._render_editor_preview_audio(project_id, preview_id).to_dict()})
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.delete_preview(preview_id)
                self.project_store.append_event(project_id, "editor_preview_deleted", {"preview_id": preview_id})
                self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})
                return
            if action == "apply":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                self._handle_project_editor_preview_apply(project_id, preview_id, payload)
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor preview not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _handle_project_editor_preview_apply(self, project_id: str, preview_id: str, payload: dict[str, Any]) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        with self.project_store.lock, store.lock:
            preview = store.read_preview(preview_id)
            if preview.applied_version_id:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview has already been applied.")
                return
            try:
                document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
                return
            if preview.parent_job_id != parent_job.job_id:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
                return
            if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
                return
            patch = store.read_patch(preview_id)
            result = apply_editor_patch(parent_plan, patch)
            result.plan.validate()
            preview_plan_mismatch = False
            try:
                preview_plan = store.read_plan(preview_id)
                preview_plan_mismatch = editor_song_plan_hash(preview_plan) != editor_song_plan_hash(result.plan)
            except (OSError, ValueError, TypeError, KeyError):
                preview_plan_mismatch = True
            run_title = str(payload.get("version_name") or payload.get("name") or preview.label or "Editor Version")
            run_dir = self.store._reserve_run_dir(run_title)
            job_id = run_dir.name
            now = _utc_now()
            metadata = editor_edit_metadata(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                preview_id=preview.preview_id,
                patch=patch,
                result=result,
                created_at=now,
            )
            audition_summary = audition_summary_for_preview(self.project_store.project_dir(project_id), preview.preview_id)
            if audition_summary.get("audition_count"):
                metadata["audition_summary"] = audition_summary
                if isinstance(metadata.get("summary"), dict):
                    metadata["summary"]["audition_count"] = audition_summary.get("audition_count", 0)
                    metadata["summary"]["audition_sources"] = audition_summary.get("sources", [])
            if preview_plan_mismatch:
                metadata["warnings"] = [
                    *metadata.get("warnings", []),
                    "Preview song-plan.json differed from recomputed editor patch result; applied recomputed plan.",
                ]
                metadata["preview_plan_mismatch"] = True
            paths = ProjectPaths.create(run_dir)
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            request_payload = {
                **parent.request,
                "project_id": project_id,
                "parent_version_id": parent.version_id,
                "parent_job_id": parent_job.job_id,
                "editor_preview_id": preview.preview_id,
                "edit_type": "manual_editor_edit",
            }
            write_interface_document(paths.data / "request.json", request_payload)
            write_interface_document(paths.data / "editor-patch.json", patch.to_dict())
            write_interface_document(paths.data / "edit-metadata.json", metadata)
            write_interface_document(plan_path, result.plan.to_dict())
            render_midi(result.plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_interface_document(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            summary["edit"] = metadata["summary"]
            write_interface_document(paths.data / "run-summary.json", summary)
            append_event(paths, {"event": "editor_preview_applied", "preview_id": preview.preview_id, "parent_version_id": parent.version_id})
            job = JobState(
                job_id=job_id,
                title=run_title,
                output_dir=str(run_dir),
                status="completed",
                created_at=now,
                updated_at=now,
                step="completed",
                message="Editor patch applied.",
                summary=summary,
                input_payload=request_payload,
                provider_snapshot={"mode": "local", "summary": "Visual editor patch"},
                artifacts={**_job_artifacts(run_dir, plan_path, midi_path, validator_report_path), "editor_patch": str(paths.data / "editor-patch.json")},
                finished_at=now,
                heartbeat_at=now,
                generation_mode="local",
                pipeline_mode=parent.pipeline_mode,
                job_type="edit",
                edit_metadata=metadata,
            )
            self.store.jobs[job.job_id] = job
            persist_interface_job(self.store, job)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=run_title,
                note=str(payload.get("version_note") or payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="manual_editor_edit",
                change_summary=str(payload.get("change_summary") or preview.label or "Visual editor patch"),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            updated_preview = store.mark_applied(preview_id, version_id=version.version_id, job_id=job.job_id, now=_utc_now())
            self.project_store.append_event(
                project_id,
                "editor_preview_applied",
                {"parent_version_id": parent.version_id, "preview_id": preview_id, "version_id": version.version_id, "job_id": job.job_id},
            )
        self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "preview": updated_preview.to_dict()}, status=HTTPStatus.CREATED)
