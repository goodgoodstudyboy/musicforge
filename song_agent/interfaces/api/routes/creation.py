from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *

class CreationRoutes:
    @property
    def batch_store(self) -> BatchStore:
        return self.server.batch_store  # type: ignore[attr-defined]

    @property
    def batch_runner(self) -> BatchRunner:
        return self.server.batch_runner  # type: ignore[attr-defined]

    @property
    def project_store(self) -> ProjectStore:
        return self.server.project_store  # type: ignore[attr-defined]

    @property
    def prompt_template_store(self) -> PromptTemplateStore:
        return self.server.prompt_template_store  # type: ignore[attr-defined]

    @property
    def editor_template_store(self) -> EditorTemplateStore:
        return self.server.editor_template_store  # type: ignore[attr-defined]

    @property
    def asset_store(self) -> AssetStore:
        return self.server.asset_store  # type: ignore[attr-defined]

    @property
    def reference_store(self) -> ReferenceStore:
        return self.server.reference_store  # type: ignore[attr-defined]

    @property
    def library_index_store(self) -> LibraryIndexStore:
        return self.server.library_index_store  # type: ignore[attr-defined]

    @property
    def context_pack_store(self) -> ContextPackStore:
        return self.server.context_pack_store  # type: ignore[attr-defined]

    def _handle_provider_route(self, method: str) -> None:
        if method == "GET":
            config, sources = load_provider_config()
            self._send_json(
                {
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(sources),
                }
            )
            return
        if method == "POST":
            config = save_provider_config_from_dict(self._read_json_body())
            self._send_json(
                {
                    "ok": True,
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(),
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_provider_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        reset_provider_config()
        config, _sources = load_provider_config()
        self._send_json({"ok": True, "configured": provider_configured(config)})

    def _handle_provider_test(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        config, _sources = load_provider_config()
        self._send_json(test_provider_config(config))

    def _handle_renderer_route(self, method: str) -> None:
        if method == "GET":
            config, sources = load_renderer_config()
            self._send_json(
                {
                    "configured": renderer_configured(config),
                    "config": config.to_public_dict(sources),
                }
            )
            return
        if method == "POST":
            config = save_renderer_config_from_dict(self._read_json_body())
            self._send_json(
                {
                    "ok": True,
                    "configured": renderer_configured(config),
                    "config": config.to_public_dict(),
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_renderer_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        reset_renderer_config()
        config, _sources = load_renderer_config()
        self._send_json({"ok": True, "configured": renderer_configured(config)})

    def _handle_renderer_test(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        config, _sources = load_renderer_config()
        self._send_json(test_renderer_config(config))

    def _handle_prompt_templates_root(self, method: str) -> None:
        if method == "GET":
            self._send_json(self.prompt_template_store.to_response())
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_prompt_templates_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self.prompt_template_store.reset()
        self._send_json({"ok": True, **self.prompt_template_store.to_response()})

    def _handle_prompt_template_route(self, method: str, template_id: str, tail: str) -> None:
        if tail == "":
            if method == "GET":
                try:
                    template = self.prompt_template_store.get_template(template_id)
                except (FileNotFoundError, ValueError):
                    self._send_error(HTTPStatus.NOT_FOUND, "Prompt template not found.")
                    return
                self._send_json({"template": template.to_dict()})
                return
            if method == "POST":
                try:
                    template = self.prompt_template_store.save_template(template_id, self._read_json_body())
                except FileNotFoundError:
                    self._send_error(HTTPStatus.NOT_FOUND, "Prompt template not found.")
                    return
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"ok": True, "template": template.to_dict(), **self.prompt_template_store.to_response()})
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/reset":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.prompt_template_store.reset_template(template_id)
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, **self.prompt_template_store.to_response()})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Prompt template route not found.")

    def _handle_editor_templates_root(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = parse_qs(query_string)
        include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
        self._send_json(self.editor_template_store.to_response(include_hidden=include_hidden, project_store=self.project_store))

    def _handle_editor_template_route(self, method: str, template_type: str, template_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if template_type == "sections":
                    template = self.editor_template_store.read_section_template(template_id)
                    self._send_json({"template": section_template_public_dict(template, project_store=self.project_store)})
                    return
                template = self.editor_template_store.read_track_template(template_id)
                self._send_json({"template": track_template_public_dict(template)})
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.editor_template_store.hide_template("section" if template_type == "sections" else "track", template_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "template": template})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.editor_template_store.delete_template("section" if template_type == "sections" else "track", template_id)
                self._send_json({"ok": True, "deleted": True, "template_id": template_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor template route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor template not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_projects_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
            hidden_filter = _query_value(query, "hidden")
            q = _query_value(query, "q")
            status_filter = _query_value(query, "status")
            variant_type = _query_value(query, "variant_type")
            documents = [
                self.project_store.sync_project(document.state.project_id, self.store.get_job)
                for document in self.project_store.list_projects(include_hidden=include_hidden or hidden_filter == "true")
            ]
            projects = [
                document.state.to_dict()
                for document in documents
                if _project_matches_filters(
                    document,
                    q=q,
                    status=status_filter,
                    variant_type=variant_type,
                    hidden=hidden_filter,
                )
            ]
            self._send_json(
                {
                    "projects": projects,
                    "filters": {
                        "q": q,
                        "status": status_filter,
                        "variant_type": variant_type,
                        "hidden": hidden_filter,
                        "include_hidden": include_hidden,
                    },
                }
            )
            return
        if method == "POST":
            payload = self._read_json_body()
            document = self.project_store.create_project(
                name=str(payload.get("name") or payload.get("title") or "Untitled Project"),
                description=str(payload.get("description") or ""),
                tags=_string_list(payload.get("tags")),
            )
            job = None
            if isinstance(payload.get("request"), dict):
                request_payload = {
                    **payload["request"],
                    "generation_mode": payload.get("generation_mode", payload["request"].get("generation_mode", "local")),
                    "pipeline_mode": payload.get("pipeline_mode", payload["request"].get("pipeline_mode", "single")),
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
                    document.state.project_id,
                    job,
                    name=str(payload.get("version_name") or "Version 1"),
                    note=str(payload.get("version_note") or ""),
                )
            self._send_json(
                {
                    **document.to_dict(),
                    "job": job.to_dict() if job is not None else None,
                },
                status=HTTPStatus.CREATED,
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_assets_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            filters = {key: _query_value(query, key) for key in ("q", "type", "tag", "style", "mood", "min_quality", "favorite")}
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            limit_value = _query_value(query, "limit")
            limit = int(limit_value) if limit_value else 100
            assets = self.asset_store.list_assets(include_hidden=include_hidden, filters=filters)[: max(1, min(limit, 500))]
            self._send_json({"assets": [asset_public_dict(asset) for asset in assets], "count": len(assets), "filters": {**filters, "include_hidden": include_hidden}})
            return
        if method == "POST":
            try:
                asset = self.asset_store.create_asset(self._read_json_body(), now=_utc_now())
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "asset": asset_public_dict(asset)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_library_index(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        self._send_json({"ok": True, "index": index.summary()})

    def _handle_library_rebuild(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        index = self.library_index_store.rebuild(self.asset_store, self.reference_store, now=_utc_now())
        self._send_json({"ok": True, "index": index.summary()})

    def _handle_library_search(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        result = search_library(index, payload)
        self.library_index_store.append_event("library_search_requested", {"result_count": result["count"], "query": result.get("query")}, now=_utc_now())
        self._send_json(result)

    def _handle_library_recommend(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        result = recommend_library_context(index, payload)
        recommendation = result.get("recommendation", {})
        self.library_index_store.append_event(
            "library_recommend_requested",
            {
                "asset_count": len(recommendation.get("asset_results", [])),
                "reference_count": len(recommendation.get("reference_results", [])),
                "goal": payload.get("goal"),
            },
            now=_utc_now(),
        )
        self._send_json(result)

    def _handle_context_packs_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            packs = self.context_pack_store.list_packs(include_hidden=include_hidden)
            self._send_json({"context_packs": [context_pack_public_dict(pack) for pack in packs], "count": len(packs)})
            return
        if method == "POST":
            try:
                pack = self.context_pack_store.create_pack(
                    self._read_json_body(),
                    asset_store=self.asset_store,
                    reference_store=self.reference_store,
                    now=_utc_now(),
                )
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_context_pack_route(self, method: str, pack_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"context_pack": context_pack_public_dict(self.context_pack_store.read_pack(pack_id))})
                return
            if tail == "/apply-preview":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                applied = self.context_pack_store.apply_preview(pack_id, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_utc_now())
                self.context_pack_store.append_event(pack_id, "context_pack_applied", {"mode": "preview"}, now=_utc_now())
                self._send_json(applied)
                return
            if tail == "/hide":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, True)
                self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)})
                return
            if tail == "/unhide":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, False)
                self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.context_pack_store.delete_pack(pack_id)
                self._send_json({"ok": True, "deleted": True, "pack_id": pack_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Context pack route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Context pack not found.")
        except ContextPackStaleError as exc:
            try:
                self.context_pack_store.append_event(pack_id, "context_pack_stale", {"error": str(exc)}, now=_utc_now())
            except (OSError, ValueError):
                pass
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_asset_route(self, method: str, asset_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    self._send_json({"asset": asset_public_dict(self.asset_store.read_asset(asset_id))})
                    return
                if method == "POST":
                    asset = self.asset_store.update_asset(asset_id, self._read_json_body())
                    self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.hide_asset(asset_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail in {"/favorite", "/unfavorite"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.favorite_asset(asset_id, favorite=tail == "/favorite")
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.delete_asset(asset_id)
                self._send_json({"ok": True, "deleted": True, "asset_id": asset_id})
                return
            if tail == "/render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.render_asset_midi(asset_id)
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                asset = self.asset_store.render_asset_audio(asset_id, config)
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(asset_midi_path(self.asset_store.asset_dir(asset_id)), "audio/midi", filename=f"{asset_id}.mid")
                return
            if tail == "/audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(asset_audio_path(self.asset_store.asset_dir(asset_id)), "audio/wav", filename=f"{asset_id}.wav")
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Asset not found.")
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            status = HTTPStatus.CONFLICT if "MIDI preview" in str(exc) or "do not have MIDI" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Asset route not found.")

    def _handle_asset_extract_from_job(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        job_id = str(payload.get("job_id") or "")
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
            return
        plan_path = Path(job.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            assets = self._create_assets_from_plan(plan, {"source_type": "job", "job_id": job.job_id, "style": job.input_payload.get("style")}, payload)
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _handle_asset_extract_from_project_version(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        version_id = str(payload.get("version_id") or "")
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            assets = self._create_assets_from_plan(
                plan,
                {"source_type": "project_version", "project_id": project_id, "version_id": version.version_id, "job_id": version.job_id, "style": version.request.get("style")},
                payload,
            )
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _handle_asset_extract_from_candidate(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        group_id = str(payload.get("candidate_group_id") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            plan = SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate_id))
            assets = self._create_assets_from_plan(
                plan,
                {
                    "source_type": "candidate",
                    "project_id": project_id,
                    "version_id": group.parent_version_id,
                    "job_id": group.parent_job_id,
                    "candidate_group_id": group.group_id,
                    "candidate_id": candidate_id,
                },
                payload,
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _create_assets_from_plan(self, plan: SongPlan, source: dict[str, Any], payload: dict[str, Any]) -> list[Any]:
        assets = []
        for asset_payload in extract_assets_from_song_plan(plan, source, payload):
            assets.append(self.asset_store.create_asset(asset_payload, now=_utc_now()))
        return assets

    def _handle_references_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            filters = {key: _query_value(query, key) for key in ("q", "type", "tag", "favorite", "project_id")}
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            limit_value = _query_value(query, "limit")
            limit = int(limit_value) if limit_value else 100
            references = self.reference_store.list_references(include_hidden=include_hidden, filters=filters)[: max(1, min(limit, 500))]
            self._send_json(
                {
                    "references": [reference_public_dict(reference) for reference in references],
                    "count": len(references),
                    "filters": {**filters, "include_hidden": include_hidden},
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_reference_import(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if not self._content_length_within(REFERENCE_IMPORT_MAX_BODY_BYTES):
            self._send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Reference import request body is too large.")
            return
        try:
            reference, duplicate = self.reference_store.import_reference(self._read_json_body(), now=_utc_now())
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "duplicate": duplicate, "reference": reference_public_dict(reference)},
            status=HTTPStatus.OK if duplicate else HTTPStatus.CREATED,
        )

    def _handle_reference_route(self, method: str, reference_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    self._send_json({"reference": reference_public_dict(self.reference_store.read_reference(reference_id))})
                    return
                if method == "POST":
                    reference = self.reference_store.update_reference(reference_id, self._read_json_body())
                    self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.hide_reference(reference_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail in {"/favorite", "/unfavorite"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.favorite_reference(reference_id, favorite=tail == "/favorite")
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.reference_store.delete_reference(reference_id)
                self._send_json({"ok": True, "deleted": True, "reference_id": reference_id})
                return
            if tail == "/file":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.read_reference(reference_id)
                self._send_file(self.reference_store.file_path(reference_id), reference.media_type, filename=reference.original_filename)
                return
            if tail == "/analysis":
                if method == "GET":
                    self._send_json({"analysis": get_analysis_report(self.reference_store, reference_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    self._send_json({"ok": True, "analysis": analyze_reference(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/analyze":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                self._send_json({"ok": True, "analysis": analyze_reference(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                return
            if tail == "/slices":
                if method == "GET":
                    self._send_json({"manifest": get_slice_manifest(self.reference_store, reference_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    require_fresh_analysis(self.reference_store, reference_id)
                    self._send_json({"ok": True, "manifest": generate_slices(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/slices/"):
                self._handle_reference_slice_route(method, reference_id, tail)
                return
            if tail in {"/link-project", "/unlink-project"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                project_id = str(payload.get("project_id") or "")
                self.project_store.get_project(project_id)
                reference = (
                    self.reference_store.link_project(reference_id, project_id)
                    if tail == "/link-project"
                    else self.reference_store.unlink_project(reference_id, project_id)
                )
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail == "/create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.reference_store.create_asset_from_reference(reference_id, self._read_json_body(), self.asset_store)
                self._send_json({"ok": True, "asset": asset}, status=HTTPStatus.CREATED)
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Reference not found.")
            return
        except ReferenceAnalysisError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            status = HTTPStatus.CONFLICT if "Hidden references" in str(exc) or "cannot be converted" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Reference route not found.")

    def _handle_reference_slice_route(self, method: str, reference_id: str, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "slices":
            self._send_error(HTTPStatus.NOT_FOUND, "Reference slice route not found.")
            return
        slice_id = unquote(parts[1])
        action = parts[2]
        try:
            if action == "render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **render_reference_slice_midi(self.reference_store, reference_id, slice_id, now=_utc_now())})
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                self._send_json({"ok": True, **render_reference_slice_audio(self.reference_store, reference_id, slice_id, config, now=_utc_now())})
                return
            if action == "create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = create_asset_from_slice(self.reference_store, reference_id, slice_id, self._read_json_body(), self.asset_store, now=_utc_now())
                self._send_json({"ok": True, "asset": asset}, status=HTTPStatus.CREATED)
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = require_fresh_slices(self.reference_store, reference_id)
                reference_dir = self.reference_store.reference_dir(reference_id)
                if not any(item.get("slice_id") == slice_id for item in manifest.get("slices", []) if isinstance(item, dict)):
                    raise FileNotFoundError(slice_id)
                self._send_file(slice_midi_path(reference_dir, slice_id), "audio/midi", filename=f"{reference_id}-{slice_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = require_fresh_slices(self.reference_store, reference_id)
                if not any(item.get("slice_id") == slice_id for item in manifest.get("slices", []) if isinstance(item, dict)):
                    raise FileNotFoundError(slice_id)
                reference_dir = self.reference_store.reference_dir(reference_id)
                self._send_file(slice_audio_path(reference_dir, slice_id), "audio/wav", filename=f"{reference_id}-{slice_id}.wav")
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Reference slice not found.")
            return
        except ReferenceAnalysisError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Reference slice route not found.")

    def _handle_provider_usage_root(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        records: list[dict[str, Any]] = []
        for job in self.store.list_jobs(include_hidden=True):
            record = usage_record_from_file(
                Path(job.output_dir) / "data" / "provider-usage.json",
                source_type="job",
                source_id=job.job_id,
                job_id=job.job_id,
            )
            if record is not None:
                records.append(record)
        for document in self.project_store.list_projects(include_hidden=True):
            project_dir = self.project_store.project_dir(document.state.project_id)
            groups_dir = project_dir / "candidate-groups"
            if not groups_dir.exists():
                continue
            for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
                record = usage_record_from_file(
                    usage_path,
                    source_type="candidate_group",
                    source_id=usage_path.parent.name,
                    project_id=document.state.project_id,
                    group_id=usage_path.parent.name,
                )
                if record is not None:
                    records.append(record)
        self._send_json(build_provider_usage_report(scope="global", records=records))

    def _handle_project_route(self, method: str, project_id: str, tail: str, query_string: str) -> None:
        editor_state_version = _match_project_editor_state_tail(tail)
        if editor_state_version is not None:
            self._handle_project_editor_state(method, project_id, editor_state_version)
            return

        editor_view_match = _match_project_editor_view_tail(tail)
        if editor_view_match is not None:
            self._handle_project_editor_view(method, project_id, editor_view_match)
            return

        editor_draft_match = _match_project_editor_draft_tail(tail)
        if editor_draft_match is not None:
            self._handle_project_editor_draft(method, project_id, editor_draft_match)
            return

        editor_clips_match = _match_project_editor_clips_tail(tail)
        if editor_clips_match is not None:
            self._handle_project_editor_clips(method, project_id, editor_clips_match)
            return

        editor_clip_draft_match = _match_project_editor_clip_draft_tail(tail)
        if editor_clip_draft_match is not None:
            self._handle_project_editor_clip_draft(method, project_id, editor_clip_draft_match)
            return

        section_template_match = _match_project_section_template_tail(tail)
        if section_template_match is not None:
            self._handle_project_section_template_create(method, project_id, section_template_match)
            return

        track_template_match = _match_project_track_template_tail(tail)
        if track_template_match is not None:
            self._handle_project_track_template_create(method, project_id, track_template_match)
            return

        template_mapping_match = _match_project_editor_template_mapping_tail(tail)
        if template_mapping_match is not None:
            self._handle_project_editor_template_mapping(method, project_id, template_mapping_match)
            return

        multitrack_draft_match = _match_project_editor_multitrack_clip_draft_tail(tail)
        if multitrack_draft_match is not None:
            self._handle_project_editor_multitrack_clip_draft(method, project_id, multitrack_draft_match)
            return

        editor_preview_create = _match_project_editor_preview_create_tail(tail)
        if editor_preview_create is not None:
            self._handle_project_editor_preview_create(method, project_id, editor_preview_create)
            return

        version_audio_match = _match_project_version_audio_tail(tail)
        if version_audio_match is not None:
            version_id, action = version_audio_match
            self._handle_project_version_audio_route(method, project_id, version_id, action)
            return

        mix_match = _match_project_mix_tail(tail)
        if mix_match is not None:
            version_id, action, resource_id = mix_match
            self._handle_project_mix_route(method, project_id, version_id, action, resource_id)
            return

        editor_preview_root = _match_project_editor_preview_root_tail(tail)
        if editor_preview_root is not None:
            self._handle_project_editor_preview_root(method, project_id, editor_preview_root)
            return

        if tail == "/audition-reviews":
            self._handle_project_audition_reviews(method, project_id, None, query_string)
            return

        editor_review_root = _match_project_editor_audition_reviews_tail(tail)
        if editor_review_root is not None:
            self._handle_project_audition_reviews(method, project_id, editor_review_root, query_string)
            return

        editor_auditions_root = _match_project_editor_auditions_root_tail(tail)
        if editor_auditions_root is not None:
            preview_id = editor_auditions_root
            self._handle_project_editor_auditions_root(method, project_id, preview_id)
            return

        editor_audition_marker_match = _match_project_editor_audition_marker_tail(tail)
        if editor_audition_marker_match is not None:
            preview_id, audition_id, marker_id, action = editor_audition_marker_match
            self._handle_project_editor_audition_marker_route(method, project_id, preview_id, audition_id, marker_id, action)
            return

        editor_audition_match = _match_project_editor_audition_tail(tail)
        if editor_audition_match is not None:
            preview_id, audition_id, action = editor_audition_match
            self._handle_project_editor_audition_route(method, project_id, preview_id, audition_id, action)
            return

        review_sprint_match = _match_project_review_sprint_tail(tail)
        if review_sprint_match is not None:
            sprint_id, action = review_sprint_match
            self._handle_project_review_sprint_route(method, project_id, sprint_id, action)
            return

        if tail == "/review-sprints":
            self._handle_project_review_sprints_root(method, project_id, query_string)
            return

        review_task_candidate_match = _match_project_review_task_candidate_tail(tail)
        if review_task_candidate_match is not None:
            task_id, candidate_id, action = review_task_candidate_match
            self._handle_project_review_task_candidate_route(method, project_id, task_id, candidate_id, action)
            return

        review_task_match = _match_project_review_task_tail(tail)
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

        editor_preview_match = _match_project_editor_preview_tail(tail)
        if editor_preview_match is not None:
            preview_id, action = editor_preview_match
            self._handle_project_editor_preview_route(method, project_id, preview_id, action)
            return

        variation_match = _match_project_variation_tail(tail)
        if variation_match is not None:
            parent_version_id = variation_match
            self._handle_project_variation(method, project_id, parent_version_id)
            return

        edit_match = _match_project_edit_tail(tail)
        if edit_match is not None:
            version_id, edit_tail = edit_match
            if edit_tail == "edit":
                self._handle_project_edit(method, project_id, version_id)
            else:
                self._handle_project_edit_targets(method, project_id, version_id)
            return

        preview_match = _match_project_edit_preview_tail(tail)
        if preview_match is not None:
            parent_version_id, preview_id, action = preview_match
            if action == "create":
                self._handle_project_edit_preview(method, project_id, parent_version_id)
            elif action == "apply":
                self._handle_project_edit_preview_apply(method, project_id, parent_version_id, preview_id)
            elif action == "delete":
                self._handle_project_edit_preview_delete(method, project_id, parent_version_id, preview_id)
            return

        candidate_create_match = _match_project_edit_candidates_tail(tail)
        if candidate_create_match is not None:
            version_id, action = candidate_create_match
            if action == "create":
                self._handle_project_edit_candidates(method, project_id, version_id)
            else:
                self._handle_project_prompt_ab_create(method, project_id, version_id)
            return

        candidate_group_match = _match_project_candidate_group_tail(tail)
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

        candidate_artifact_match = _match_project_candidate_artifact_tail(tail)
        if candidate_artifact_match is not None:
            group_id, candidate_id, action = candidate_artifact_match
            self._handle_project_candidate_artifact(method, project_id, group_id, candidate_id, action)
            return

        prompt_ab_match = _match_project_prompt_ab_tail(tail)
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
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._handle_project_candidate_groups_list(project_id)
            return

        if tail == "":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json(document.to_dict())
            return

        if tail == "/versions":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            request_data = payload.get("request")
            if not isinstance(request_data, dict):
                self._send_error(HTTPStatus.BAD_REQUEST, "request must be an object.")
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
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json(
                {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
                status=HTTPStatus.ACCEPTED,
            )
            return

        evaluate_match = _match_project_evaluate_tail(tail)
        if evaluate_match is not None:
            self._handle_project_evaluate(method, project_id, evaluate_match)
            return

        if tail == "/versions/from-job":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            job_id = str(payload.get("job_id") or "")
            job = self.store.get_job(job_id)
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            try:
                document = self.project_store.add_version_from_job(
                    project_id,
                    job,
                    name=str(payload.get("name") or ""),
                    note=str(payload.get("note") or ""),
                )
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict()})
            return

        if tail in {"/selected", "/final"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
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
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except PermissionError as exc:
                self._send_json(exc.args[0], status=HTTPStatus.CONFLICT)
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
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
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.diff_versions(project_id, left, right))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/compare":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(compare_project_versions(document, left, right))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/provider-usage":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
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
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.export_project(project_id))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail == "/events":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.get_project(project_id)
                self._send_json({"events": self.project_store.read_events(project_id)})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.hide_project(project_id, tail == "/hide")
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.delete_project(project_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, "deleted": True, "project_id": project_id})
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Project route not found.")

    def _handle_project_quality_gate(self, method: str, project_id: str) -> None:
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if method == "GET":
            self._send_json({"config": load_quality_gate_config(project_dir).to_dict()})
            return
        if method == "POST":
            config = QualityGateConfig.from_dict(self._read_json_body())
            save_quality_gate_config(project_dir, config)
            self.project_store.append_event(project_id, "quality_gate_config_saved", {"config": config.to_dict()})
            self._send_json({"ok": True, "config": config.to_dict()})
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_project_references(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            references = self.reference_store.list_references(filters={"project_id": project_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_json({"project_id": project_id, "references": [reference_public_dict(reference) for reference in references]})

    def _handle_project_reference_link(self, method: str, project_id: str, *, unlink: bool) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        reference_id = str(payload.get("reference_id") or "")
        try:
            self.project_store.get_project(project_id)
            reference = (
                self.reference_store.unlink_project(reference_id, project_id)
                if unlink
                else self.reference_store.link_project(reference_id, project_id)
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project or reference not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self.project_store.append_event(project_id, "reference_unlinked" if unlink else "reference_linked", {"reference_id": reference.reference_id})
        self._send_json({"ok": True, "reference": reference_public_dict(reference)})

    def _handle_project_evaluate(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        result = self._evaluate_project_version(project_id, version)
        document = self.project_store.update_version_quality_gate(project_id, version.version_id, result)
        version = next(item for item in document.versions if item.version_id == version_id)
        self._send_json({"ok": True, "version": version.to_dict(), "quality_gate": result.to_dict(), **document.to_dict()})

    def _handle_project_evaluate_all(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        results = []
        for version in document.versions:
            result = self._evaluate_project_version(project_id, version)
            self.project_store.update_version_quality_gate(project_id, version.version_id, result)
            results.append({"version_id": version.version_id, "quality_gate": result.to_dict()})
        document = self.project_store.get_project(project_id)
        self._send_json({"ok": True, "results": results, **document.to_dict()})

    def _handle_project_final_export(self, method: str, project_id: str) -> None:
        if method == "GET":
            try:
                project_dir = self.project_store.project_dir(project_id)
                self.project_store.get_project(project_id)
                manifest = read_final_export_manifest(project_dir)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Final export not found.")
                return
            self._send_json({"final_export": manifest})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        payload = self._optional_json_body()
        options = FinalExportOptions.from_dict(payload)
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        version_id = options.version_id or document.state.final_version_id
        if not version_id:
            self._send_error(HTTPStatus.CONFLICT, "Project has no final version.")
            return
        version = next((item for item in document.versions if item.version_id == version_id), None)
        if version is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        if version.status != "completed":
            self._send_error(HTTPStatus.CONFLICT, "Only completed versions can be exported.")
            return
        if self.store.get_job(version.job_id) is None:
            self._send_error(HTTPStatus.CONFLICT, "Version job is missing.")
            return

        gate_result = self._evaluate_project_version(project_id, version)
        document = self.project_store.update_version_quality_gate(project_id, version.version_id, gate_result)
        version = next(item for item in document.versions if item.version_id == version_id)
        if gate_result.status not in {"passed", "warning"} and not options.force:
            self.project_store.append_event(
                project_id,
                "final_export_gate_failed",
                {"version_id": version.version_id, "status": gate_result.status, "score": gate_result.score},
            )
            self._send_json(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": gate_result.to_dict(),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        project_dir = self.project_store.project_dir(project_id)
        project_export = self.project_store.export_project(project_id)
        document = self.project_store.get_project(project_id)
        version = next(item for item in document.versions if item.version_id == version_id)
        try:
            manifest = build_final_export_bundle(
                project=document.state,
                version=version,
                project_dir=project_dir,
                run_dir=Path(version.output_dir),
                gate=gate_result,
                options=options,
                now=_utc_now(),
                project_export=project_export,
            )
        except FinalExportError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        document = self.project_store.update_version_final_export(
            project_id,
            version.version_id,
            final_export_dir(project_dir),
        )
        version = next(item for item in document.versions if item.version_id == version_id)
        self._send_json(
            {
                "ok": True,
                "version": version.to_dict(),
                "quality_gate": gate_result.to_dict(),
                "final_export": manifest,
                **document.to_dict(),
            }
        )

    def _handle_project_final_export_zip(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_info = build_final_export_zip(project_dir, now=_utc_now())
            self.project_store.append_event(project_id, "final_export_zip_created", zip_info)
        except FileNotFoundError:
            self._send_error(HTTPStatus.CONFLICT, "Final export has not been generated.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "zip": zip_info})

    def _handle_project_final_export_zip_download(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_path = final_export_zip_path(project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_file(zip_path, "application/zip", filename=f"musicforge-{project_id}-final-export.zip")

    def _handle_project_delivery_qa(self, method: str, project_id: str, *, refresh: bool) -> None:
        if refresh and method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if not refresh and method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self._get_or_refresh_delivery_qa(project_id, refresh=refresh)
            if refresh:
                self.project_store.append_event(project_id, "delivery_qa_refreshed", {"status": report.get("status"), "readiness": report.get("readiness")})
            self._send_json({"ok": True, "project_id": project_id, "delivery_qa": report, "summary": delivery_qa_summary(report)})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))

    def _handle_project_delivery_signoff(self, method: str, project_id: str, *, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if action == "get":
            if method == "GET":
                signoff = self.project_store.read_delivery_signoff(project_id, default={})
                self._send_json({"ok": True, "project_id": project_id, "signoff": signoff, "summary": delivery_signoff_summary(signoff)})
                return
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            existing = self.project_store.read_delivery_signoff(project_id, default={})
            if existing:
                self._send_error(HTTPStatus.CONFLICT, "Delivery is already signed off. Reset signoff before signing again.")
                return
            report = self._get_or_refresh_delivery_qa(project_id, refresh=True)
            force = bool(payload.get("force", False))
            if not delivery_qa_allows_signoff(report) and not force:
                self._send_error(HTTPStatus.CONFLICT, "Delivery QA gate failed. Refresh QA or pass force=true with override_reason.")
                return
            if force and not str(payload.get("override_reason") or "").strip():
                self._send_error(HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
                return
            try:
                record = build_delivery_signoff_record(project_id=project_id, report=report, payload={**payload, "force": force}, now=_utc_now())
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            signoff = self.project_store.write_delivery_signoff(project_id, record, now=_utc_now())
            self.project_store.append_event(project_id, "delivery_force_signed" if force else "delivery_signed", {"status": report.get("status"), "final_version_id": signoff.get("final_version_id"), "forced": force})
            self._send_json({"ok": True, "project_id": project_id, "signoff": signoff, "summary": delivery_signoff_summary(signoff)})
            return
        if action == "reset":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            reason = str(payload.get("reason") or "").strip()
            if not reason:
                self._send_error(HTTPStatus.BAD_REQUEST, "reason is required to reset delivery signoff.")
                return
            existing = self.project_store.read_delivery_signoff(project_id, default={})
            if not existing:
                self._send_error(HTTPStatus.CONFLICT, "Delivery signoff does not exist.")
                return
            event = signoff_history_event("delivery_signoff_reset", existing, reason, now=_utc_now())
            self.project_store.reset_delivery_signoff(project_id, event)
            self.project_store.append_event(project_id, "delivery_signoff_reset", {"reason": event.get("reason"), "previous_status": delivery_signoff_summary(existing).get("status")})
            self._send_json({"ok": True, "project_id": project_id, "summary": {"status": "reset"}, "history_event": event})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Delivery signoff route not found.")

    def _renderer_profile_from_payload(self, payload: dict[str, Any] | None) -> Any | None:
        profile_id = str((payload or {}).get("profile_id") or "").strip()
        if not profile_id:
            return None
        return self.audio_profile_store.get_profile(profile_id)

    def _renderer_config_from_payload(self, payload: dict[str, Any] | None) -> Any | None:
        profile = self._renderer_profile_from_payload(payload)
        if profile is None:
            return None
        return profile.to_renderer_config()

    def _evaluate_project_version(self, project_id: str, version: Any) -> Any:
        config = load_quality_gate_config(self.project_store.project_dir(project_id))
        return evaluate_quality_gate(Path(version.output_dir), config, now=_utc_now())

    def _handle_project_variation(self, method: str, project_id: str, parent_version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            parent = next(version for version in document.versions if version.version_id == parent_version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            self._send_error(HTTPStatus.CONFLICT, "Parent version job is missing.")
            return
        request_patch = payload.get("request_patch") or {}
        if not isinstance(request_patch, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "request_patch must be an object.")
            return
        try:
            request_payload = _variation_request_payload(
                parent.request,
                request_patch,
                generation_mode=payload.get("generation_mode"),
                pipeline_mode=payload.get("pipeline_mode"),
            )
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
                parent_version_id=parent.version_id,
                variant_type=str(payload.get("variant_type") or "manual"),
                change_summary=str(payload.get("change_summary") or ""),
            )
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        version = next(version for version in document.versions if version.job_id == job.job_id)
        self.project_store.append_event(
            project_id,
            "variation_created",
            {
                "parent_version_id": parent.version_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
                "variant_type": version.variant_type,
            },
        )
        self._send_json(
            {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
            status=HTTPStatus.ACCEPTED,
        )

    def _handle_project_edit(self, method: str, project_id: str, version_id: str) -> None:
        if method == "GET":
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next(version for version in document.versions if version.version_id == version_id)
            except StopIteration:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            metadata = _read_edit_metadata_for_run(Path(version.output_dir))
            if metadata is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Edit metadata not found.")
                return
            self._send_json({"version_id": version.version_id, "edit": metadata})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            parent = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            self._send_error(HTTPStatus.CONFLICT, "Parent version job is missing.")
            return
        if parent.status != "completed" or parent_job.status != "completed":
            self._send_error(HTTPStatus.CONFLICT, "Parent version must be completed before editing.")
            return
        parent_plan_path = Path(parent.output_dir) / "data" / "song-plan.json"
        if not parent_plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "Parent song-plan.json is missing.")
            return
        preset_ref = None
        try:
            payload = self._expand_context_pack_payload(payload)
            parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
            preset_id = str(payload.get("preset_id") or "").strip()
            intent_payload = payload
            if preset_id:
                preset = self.edit_preset_store.get_preset(preset_id)
                intent_payload = merge_preset_intent(preset, payload, parent_plan)
                preset_ref = preset.public_ref()
            intent = EditIntent.from_dict(intent_payload)
            validate_edit_intent(parent_plan, intent)
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                preset=preset_ref,
                name=str(payload.get("name") or ""),
                start_immediately=bool(payload.get("start_immediately", True)),
                asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
                reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
                context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
            )
            variant_type = edit_variant_type(intent.edit_type)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or "") or f"Edit {len(document.versions) + 1}",
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=variant_type,
                change_summary=str(payload.get("change_summary") or edit_change_summary(intent)),
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
            return
        except NotImplementedError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        version = next(version for version in document.versions if version.job_id == job.job_id)
        self.project_store.append_event(
            project_id,
            "version_edit_created",
            {
                "parent_version_id": parent.version_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
                "edit_type": intent.edit_type,
            },
        )
        self._send_json(
            {
                "ok": True,
                **document.to_dict(),
                "version": version.to_dict(),
                "job": job.to_dict(),
                "edit": job.edit_metadata,
            },
            status=HTTPStatus.ACCEPTED,
        )

    def _handle_project_edit_targets(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is not available for this version.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(build_edit_targets(plan))

    def _handle_project_editor_state(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            state = build_editor_state(plan)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, **state})

    def _handle_project_editor_view(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            view = build_editor_view(plan)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, "view": view})

    def _handle_project_editor_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = apply_editor_patch(parent_plan, patch_data)
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": list(result.warnings),
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response: dict[str, Any] = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(result.patch.operations),
                "summary": summary,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", False)):
                response["view"] = build_editor_view_from_result(result)
            if bool(payload.get("include_diff", False)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_editor_clips(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _parent_job, _parent_plan = self._project_edit_parent(project_id, version_id)
            catalog = list_editor_clips(
                project_id=project_id,
                version_id=version.version_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorClipError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(catalog)

    def _handle_project_editor_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_editor_clip_from_ref(
                payload.get("clip_ref"),
                default_project_id=project_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
            )
            existing_patch_data = payload.get("current_patch")
            existing_result = None
            draft_plan = None
            existing_operations: list[dict[str, Any]] = []
            existing_metadata: dict[str, Any] = {}
            draft_state = None
            if isinstance(existing_patch_data, dict):
                existing_result = apply_editor_patch(parent_plan, existing_patch_data)
                draft_plan = existing_result.plan
                existing_operations = list(existing_result.patch.operations)
                existing_metadata = dict(existing_result.patch.metadata)
                draft_state = build_editor_view_from_result(existing_result)
            patch_data, clip_summary, clip_warnings = build_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = apply_editor_patch(parent_plan, combined_patch)
            warnings = [*clip_warnings, *result.warnings]
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": warnings,
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(patch_data["operations"]),
                "patch": patch_data,
                "combined_patch": result.patch.to_dict(),
                "clip_summary": clip_summary,
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_clip_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Clip or version not found.")
            return
        except EditorClipUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorClipError, EditorPatchError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_section_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_section_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                section_id=str(payload.get("section_id") or ""),
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "section_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": section_template_public_dict(template, project_store=self.project_store)}, status=HTTPStatus.CREATED)

    def _handle_project_track_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_track_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                track_id=str(payload.get("track_id") or ""),
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "track_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": track_template_public_dict(template)}, status=HTTPStatus.CREATED)

    def _handle_project_editor_template_mapping(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            state = build_editor_state(parent_plan)
            suggestions = suggest_lane_mappings(clip, state)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, EditorPatchError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "clip": clip.summary(), "suggestions": suggestions})

    def _handle_project_editor_multitrack_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            existing_patch_data = payload.get("current_patch")
            existing_result = None
            draft_plan = None
            existing_operations: list[dict[str, Any]] = []
            existing_metadata: dict[str, Any] = {}
            draft_state = None
            if isinstance(existing_patch_data, dict):
                existing_result = apply_editor_patch(parent_plan, existing_patch_data)
                draft_plan = existing_result.plan
                existing_operations = list(existing_result.patch.operations)
                existing_metadata = dict(existing_result.patch.metadata)
                draft_state = build_editor_view_from_result(existing_result)
            patch_data, template_summary, template_warnings = build_multitrack_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = apply_editor_patch(parent_plan, combined_patch)
            warnings = [*template_warnings, *result.warnings]
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": warnings,
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(patch_data["operations"]),
                "patch": patch_data,
                "combined_patch": result.patch.to_dict(),
                "template_summary": template_summary,
                "mapping_suggestions": suggest_lane_mappings(clip, build_editor_state(parent_plan)),
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_template_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, EditorPatchError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_editor_preview_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = apply_editor_patch(parent_plan, patch_data)
            project_dir = self.project_store.project_dir(project_id)
            preview, _preview_dir = EditorPreviewStore(project_dir).create_preview(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                parent_plan=parent_plan,
                patch=result.patch,
                result=result,
                render_midi=bool(payload.get("render_midi", True)),
                now=_utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "editor_preview_created",
                {
                    "parent_version_id": parent.version_id,
                    "preview_id": preview.preview_id,
                    "operation_count": preview.operation_count,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_mix_route(self, method: str, project_id: str, version_id: str, action: str, resource_id: str | None = None) -> None:
        mix_store = MixRenderStore(self.project_store, self.store)
        control_store = MixControlStore(self.project_store.project_dir(project_id))
        try:
            if action == "mix-state":
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                run_dir = Path(version.output_dir)
                plan = SongPlan.from_dict(read_json(run_dir / "data" / "song-plan.json"))
                if method == "GET":
                    state = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_utc_now())
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict(), "summary": {"mix_state_hash": mix_state_hash(state)}})
                    return
                if method == "POST":
                    current = control_store.get_or_create_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_utc_now())
                    state = control_store.write_state(type(current).from_dict({**self._read_json_body(), "project_id": project_id, "version_id": version.version_id, "updated_at": _utc_now()}))
                    self.project_store.append_event(project_id, "mix_state_saved", {"version_id": version.version_id, "mix_state_hash": mix_state_hash(state)})
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "mix-state-reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                run_dir = Path(version.output_dir)
                plan = SongPlan.from_dict(read_json(run_dir / "data" / "song-plan.json"))
                state = control_store.reset_state(project_id=project_id, version_id=version.version_id, plan=plan, midi_path=run_dir / "renders" / "song.mid", now=_utc_now())
                self.project_store.append_event(project_id, "mix_state_reset", {"version_id": version.version_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "mix_state": state.to_dict()})
                return
            if action == "mix-preview-create":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview, patch, _preview_dir = mix_store.create_preview(project_id=project_id, version_id=version_id, payload=self._read_json_body(), now=_utc_now())
                self.project_store.append_event(project_id, "mix_preview_created", {"version_id": version_id, "preview_id": preview.preview_id, "patch_id": patch.patch_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "mix-preview-detail" and resource_id:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict(), "integrity_ok": mix_preview_integrity_ok(preview)})
                return
            if action == "mix-preview-midi" and resource_id:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if not mix_preview_integrity_ok(preview):
                    self._send_error(HTTPStatus.CONFLICT, "Mix preview integrity failed.")
                    return
                self._send_file(mix_store.preview_dir(project_id, version_id, resource_id) / "song.mid", "audio/midi", filename=f"{project_id}-{resource_id}.mid")
                return
            if action == "mix-preview-audio" and resource_id:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if not mix_preview_integrity_ok(preview):
                    self._send_error(HTTPStatus.CONFLICT, "Mix preview integrity failed.")
                    return
                audio_path = mix_store.preview_dir(project_id, version_id, resource_id) / "song.wav"
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Mix preview audio is not available.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{resource_id}.wav")
                return
            if action == "mix-preview-render-audio" and resource_id:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.render_preview_audio(project_id=project_id, version_id=version_id, preview_id=resource_id, now=_utc_now())
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview": preview.to_dict()})
                return
            if action == "mix-preview-apply" and resource_id:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                document, version, job = mix_store.apply_preview(project_id=project_id, version_id=version_id, preview_id=resource_id, payload=self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **document, "version": version.to_dict(), "job": job.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "mix-preview-delete" and resource_id:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = mix_store.read_preview(project_id, version_id, resource_id)
                if preview.applied_version_id:
                    self._send_error(HTTPStatus.CONFLICT, "Applied mix previews cannot be deleted.")
                    return
                preview_dir = mix_store.preview_dir(project_id, version_id, resource_id)
                if preview_dir.exists():
                    shutil.rmtree(preview_dir)
                self.project_store.append_event(project_id, "mix_preview_deleted", {"version_id": version_id, "preview_id": resource_id})
                self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "preview_id": resource_id, "deleted": True})
                return
            if action == "mix-stems-render":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_utc_now())
                self.project_store.append_event(project_id, "mix_stems_rendered", {"version_id": version_id, "status": result["summary"].get("status")})
                self._send_json(result)
                return
            if action == "mix-stems-health":
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next((item for item in document.versions if item.version_id == version_id), None)
                if version is None:
                    self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                    return
                if method == "GET":
                    report = read_stem_health_report(Path(version.output_dir))
                    self._send_json({"ok": True, "project_id": project_id, "version_id": version_id, "stem_health": report, "summary": stem_health_summary(report)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    result = mix_store.render_stems(project_id=project_id, version_id=version_id, require_wav=bool(payload.get("require_wav", False)), render_wav=bool(payload.get("render_audio", False)), force=bool(payload.get("force", False)), now=_utc_now())
                    self._send_json(result)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc) or "Mix resource not found.")
            return
        except MixControlStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (MixControlError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Mix route not found.")

    def _handle_project_editor_preview_root(self, method: str, project_id: str, action: str) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "list":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "project_id": project_id, "previews": [preview.to_dict() for preview in store.list_previews()]})
                return
            if action == "cleanup":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = store.cleanup_previews(
                    delete_unapplied_older_than_days=int(payload.get("delete_unapplied_older_than_days", 7) or 7),
                    keep_latest=int(payload.get("keep_latest", 20) or 20),
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "editor_previews_cleanup", result)
                self._send_json({"ok": True, **result})
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _handle_project_editor_auditions_root(self, method: str, project_id: str, preview_id: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview = preview_store.read_preview(preview_id)
            if method == "GET":
                auditions = audition_store.list_auditions(preview_id)
                self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, "auditions": [item.to_dict() for item in auditions]})
                return
            if method == "POST":
                payload = self._read_json_body()
                source = str(payload.get("source") or "preview").strip()
                if source not in {"preview", "parent"}:
                    self._send_error(HTTPStatus.BAD_REQUEST, "source must be parent or preview.")
                    return
                _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
                if preview.parent_job_id != parent_job.job_id:
                    self._send_error(HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
                    return
                if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
                    self._send_error(HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
                    return
                if source == "parent":
                    source_plan = parent_plan
                    source_state = None
                else:
                    patch = preview_store.read_patch(preview_id)
                    result = apply_editor_patch(parent_plan, patch)
                    source_plan = result.plan
                    source_state = build_editor_view_from_result(result)
                payload = {**payload, "source": source}
                audition = audition_store.create_audition(project_id=project_id, preview=preview, source_plan=source_plan, editor_state=source_state, payload=payload, now=_utc_now())
                if bool(payload.get("render_audio", False)):
                    config, _sources = load_renderer_config()
                    config.validate_ready_for_render()
                    audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition.audition_id, config=config, now=_utc_now())
                self.project_store.append_event(
                    project_id,
                    "editor_audition_created",
                    {"parent_version_id": parent.version_id, "preview_id": preview_id, "audition_id": audition.audition_id, "source": audition.source},
                )
                self._send_json({"ok": True, "audition": audition.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor preview not found.")
        except EditorAuditionUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except (EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_audition_route(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "audition": audition_store.read_audition(preview_id, audition_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.midi_path(preview_id, audition_id), "audio/midi", filename=f"{project_id}-{preview_id}-{audition_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.audio_path(preview_id, audition_id), "audio/wav", filename=f"{project_id}-{preview_id}-{audition_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition_id, config=config, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_audio_rendered", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict()})
                return
            if action == "review":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.update_review(preview_id, audition_id, self._read_json_body(), now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_review_updated", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "review": audition.review})
                return
            if action == "markers":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.add_marker(preview_id, audition_id, self._read_json_body(), now=_utc_now())
                marker = (audition.review.get("markers") or [])[-1]
                self.project_store.append_event(project_id, "editor_audition_marker_added", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker.get("marker_id")})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker}, status=HTTPStatus.CREATED)
                return
            if action == "create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = audition_store.read_audition(preview_id, audition_id)
                plan = audition_store.read_plan(preview_id, audition_id)
                asset_payload = audition_asset_payload(plan, manifest, self._read_json_body())
                asset = self.asset_store.create_asset(asset_payload, now=_utc_now())
                audition = audition_store.record_asset_created(preview_id, audition_id, asset.asset_id, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_asset_created", {"preview_id": preview_id, "audition_id": audition_id, "asset_id": asset.asset_id})
                self._send_json({"ok": True, "asset": asset_public_dict(asset), "audition": audition.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "review-task":
                self._handle_project_review_task_create(method, project_id, preview_id, audition_id)
                return
            if action in {"review-edit-preview", "review-edit", "provider-review-edit-preview", "create-context-pack"}:
                self._handle_project_editor_audition_next_action(method, project_id, preview_id, audition_id, action)
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.delete_audition(preview_id, audition_id)
                self.project_store.append_event(project_id, "editor_audition_deleted", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "deleted": True, "audition_id": audition_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition not found.")
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except EditorReviewError as exc:
            status = HTTPStatus.CONFLICT if "no notes" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except (EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

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

    def _handle_project_review_sprint_route(self, method: str, project_id: str, sprint_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            task_store = ReviewTaskStore(project_dir)
            sprint = sprint_store.read_sprint(sprint_id)
            if sprint.project_id != project_id:
                raise FileNotFoundError(sprint_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint, include_events=True))
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_refreshed", {"sprint_id": sprint.sprint_id, "status": sprint.status})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "close":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                closeout_report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=True)
                force = bool(payload.get("force", False))
                if not closeout_allows_close(closeout_report) and not force:
                    self._send_error(HTTPStatus.CONFLICT, "Review Sprint closeout gate failed. Refresh closeout report or pass force=true with override_reason.")
                    return
                if force and not str(payload.get("override_reason") or "").strip():
                    self._send_error(HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
                    return
                if force:
                    closeout_report = sprint_store.write_closeout_report(sprint, mark_closeout_report_forced(closeout_report), now=_utc_now())
                signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
                if not signoff:
                    signoff = sprint_store.write_signoff(sprint, build_signoff_record(project_id=project_id, sprint=sprint, closeout_report=closeout_report, payload={**payload, "force": force}, now=_utc_now()), now=_utc_now())
                elif force and not bool(signoff.get("forced", False)):
                    raise ReviewSprintStateError("Review Sprint is already signed off.")
                event_name = "review_sprint_force_closed" if force else "review_sprint_closed"
                sprint = sprint_store.close_sprint(sprint, now=_utc_now())
                sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, event_name, {"sprint_id": sprint.sprint_id, "forced": force, "closeout_status": closeout_report.get("status")})
                response = self._review_sprint_response(sprint_store, task_store, sprint)
                response.update({"closeout_report": closeout_report, "closeout_summary": closeout_report_summary(closeout_report), "signoff": signoff, "signoff_summary": signoff_summary(signoff)})
                self._send_json(response)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = sprint_store.archive_sprint(sprint, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_archived", {"sprint_id": sprint.sprint_id})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                sprint = sprint_store.add_tasks(
                    sprint,
                    task_store=task_store,
                    task_ids=[str(item) for item in task_ids],
                    lane=str(payload.get("lane") or ""),
                    notes=str(payload.get("notes") or ""),
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "review_sprint_tasks_added", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-remove":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                for task_id in task_ids:
                    sprint = sprint_store.remove_task(sprint, str(task_id), task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_removed", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-reorder":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else []
                sprint = sprint_store.reorder_tasks(sprint, [str(item) for item in task_ids], task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_reordered", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "conflicts":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                if not report:
                    report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=self._review_sprint_parent_plan_hashes(project_id, task_store, sprint), now=_utc_now())
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "conflict_report": report})
                return
            if action == "conflicts-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_conflicts_refreshed", {"sprint_id": sprint.sprint_id, "conflict_count": len(report.get("conflicts", []))})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "recommendations":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                if not report:
                    report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": recommendation_report_summary(report)})
                return
            if action == "recommendations-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_recommendations_refreshed", {"sprint_id": sprint.sprint_id, "recommended_count": len(report.get("recommended_order", []))})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": recommendation_report_summary(report)})
                return
            if action == "metrics":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "metrics_report": report, "summary": sprint_metrics_summary(report)})
                return
            if action == "metrics-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=True)
                sprint_store.append_event(sprint.sprint_id, "review_sprint_metrics_refreshed", {"readiness": (report.get("risk_readiness") or {}).get("readiness") if isinstance(report.get("risk_readiness"), dict) else None}, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_metrics_refreshed", {"sprint_id": sprint.sprint_id, "readiness": (report.get("risk_readiness") or {}).get("readiness") if isinstance(report.get("risk_readiness"), dict) else None})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "metrics_report": report, "summary": sprint_metrics_summary(report)})
                return
            if action == "judge-summary":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                summary = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "judge_summary": summary})
                return
            if action == "judge-summary-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                summary = self._refresh_review_sprint_judge_reports(project_id, sprint_store, task_store, sprint, payload)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "judge_summary": summary})
                return
            if action == "closeout":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "closeout_report": report, "summary": closeout_report_summary(report)})
                return
            if action == "closeout-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=True)
                self.project_store.append_event(project_id, "review_sprint_closeout_refreshed", {"sprint_id": sprint.sprint_id, "status": report.get("status"), "readiness": report.get("readiness")})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "closeout_report": report, "summary": closeout_report_summary(report)})
                return
            if action == "signoff":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                record = sprint_store.read_signoff(sprint.sprint_id, default={})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "signoff": record, "summary": signoff_summary(record)})
                return
            if action == "action-queues":
                queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                if method == "GET":
                    queues = queue_store.list_queues(include_archived=True)
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queues": [queue.to_dict() for queue in queues], "latest_queue": queues[0].to_dict() if queues else {}, "summary": action_queue_collection_summary(queues)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    if bool(payload.get("refresh_recommendations", True)):
                        sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                        report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                    else:
                        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                        if not report:
                            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                    queue = build_action_queue_from_recommendation_report(
                        project_id=project_id,
                        sprint=sprint,
                        recommendation_report=report,
                        name=str(payload.get("name") or "") or None,
                        settings=payload.get("settings") if isinstance(payload.get("settings"), dict) else {},
                        now=_utc_now(),
                    )
                    created = queue_store.create_queue(queue, now=_utc_now())
                    self.project_store.append_event(project_id, "review_sprint_action_queue_created", {"sprint_id": sprint.sprint_id, "queue_id": created.queue_id, "item_count": len(created.items)})
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queue": created.to_dict(), "summary": action_queue_summary(created)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action.startswith("action-queue:"):
                queue_id, queue_action = action.split(":", 2)[1:]
                queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                if queue_action == "detail":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    queue = queue_store.read_queue(queue_id)
                    if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
                        raise FileNotFoundError(queue_id)
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queue": queue.to_dict(), "events": queue_store.read_events(queue.queue_id), "summary": action_queue_summary(queue)})
                    return
                if queue_action == "run":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    result = self._run_review_sprint_action_queue(project_id, sprint_store, task_store, sprint, queue_store, queue_id, payload)
                    self._send_json(result)
                    return
                if queue_action == "archive":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    queue = queue_store.read_queue(queue_id)
                    if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
                        raise FileNotFoundError(queue_id)
                    archived = queue_store.archive_queue(queue.queue_id, now=_utc_now())
                    self.project_store.append_event(project_id, "review_sprint_action_queue_archived", {"sprint_id": sprint.sprint_id, "queue_id": archived.queue_id})
                    self._send_json({"ok": True, "queue": archived.to_dict(), "summary": action_queue_summary(archived)})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Review sprint action queue route not found.")
                return
            if action.startswith("recommendation-context-pack:"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                task_id = action.split(":", 1)[1]
                payload = self._optional_json_body()
                result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, task_id, payload)
                self._send_json(result, status=HTTPStatus.CREATED)
                return
            if action == "generate-local-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self._generate_review_sprint_local_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=HTTPStatus.ACCEPTED)
                return
            if action == "generate-provider-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._expand_context_pack_payload(self._optional_json_body())
                result = self._generate_review_sprint_provider_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=HTTPStatus.ACCEPTED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review sprint route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review sprint not found.")
        except (ReviewSprintStateError, ReviewTaskStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (ReviewSprintError, ReviewTaskError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _get_or_refresh_project_review_metrics(self, project_id: str, *, refresh: bool) -> dict[str, Any]:
        project_dir = self.project_store.project_dir(project_id)
        metrics_store = ReviewMetricsStore(project_dir)
        if not refresh:
            existing = metrics_store.read_project_metrics(default={})
            if existing:
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        sprint_store = ReviewSprintStore(project_dir)
        task_store = ReviewTaskStore(project_dir)
        provider_records = collect_project_provider_usage_records(project_id, project_document.versions, project_dir)
        report = build_project_review_metrics(
            project_id=project_id,
            project_document=project_document,
            sprint_store=sprint_store,
            task_store=task_store,
            provider_usage_records=provider_records,
            now=_utc_now(),
        )
        saved = metrics_store.write_project_metrics(report)
        for summary in saved.get("sprint_summaries", []) if isinstance(saved.get("sprint_summaries"), list) else []:
            sprint_id = str(summary.get("sprint_id") or "")
            if sprint_id:
                try:
                    sprint = sprint_store.read_sprint(sprint_id)
                    sprint_report = build_sprint_metrics_report(
                        project_id=project_id,
                        sprint=sprint,
                        project_document=project_document,
                        task_store=task_store,
                        sprint_store=sprint_store,
                        queue_store=ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
                        provider_usage_records=provider_records,
                        now=saved.get("created_at") or _utc_now(),
                    )
                    metrics_store.write_sprint_metrics(sprint.sprint_id, sprint_report)
                except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
                    continue
        return saved

    def _save_review_sprint_recommendation_context_pack(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task_id not in self._review_sprint_ordered_task_ids(sprint):
            raise FileNotFoundError(task_id)
        task = task_store.read_task(task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(task_id)
        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        if not report:
            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
        action = _recommendation_action_for_task(report, task_id)
        if not action:
            raise ReviewSprintStateError("Recommendation for task is missing.")
        preview = action.get("context_pack_preview") if isinstance(action.get("context_pack_preview"), dict) else {}
        asset_refs = preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else []
        reference_refs = preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else []
        if not asset_refs and not reference_refs:
            raise ReviewSprintStateError("Recommendation has no context refs to save.")
        self._ensure_recommendation_context_refs_current(asset_refs, reference_refs)
        pack_payload = {
            "name": str(payload.get("name") or f"{sprint.name} {task_id} Context Pack")[:160],
            "description": str(payload.get("description") or f"Saved from Review Sprint recommendation {sprint.sprint_id} for {task_id}.")[:1000],
            "created_from": {
                "source_type": "review_sprint_recommendation",
                "project_id": project_id,
                "sprint_id": sprint.sprint_id,
                "task_id": task_id,
                "recommendation_created_at": report.get("created_at"),
                "recommendation_rank": action.get("rank"),
                "recommended_action": action.get("action"),
            },
            "query": preview.get("query") if isinstance(preview.get("query"), dict) else {},
            "asset_refs": asset_refs,
            "reference_refs": reference_refs,
            "selection": {
                "mode": "recommendation",
                "selected_by": str(payload.get("selected_by") or "user")[:80],
                "score_summary": action.get("score_breakdown") if isinstance(action.get("score_breakdown"), dict) else {},
            },
        }
        pack = self.context_pack_store.create_pack(pack_payload, asset_store=self.asset_store, reference_store=self.reference_store, now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_recommendation_context_pack_saved", {"sprint_id": sprint.sprint_id, "task_id": task_id, "pack_id": pack.pack_id})
        return {"ok": True, "context_pack": context_pack_public_dict(pack), "recommendation": action}

    def _ensure_recommendation_context_refs_current(self, asset_refs: list[dict[str, Any]], reference_refs: list[dict[str, Any]]) -> None:
        for ref in asset_refs:
            asset = self.asset_store.read_asset(str(ref.get("asset_id") or ""))
            if asset.hidden or str(ref.get("source_hash") or "") != asset_source_hash(asset):
                raise ReviewSprintStateError("Recommendation context asset is stale. Refresh recommendations before saving.")
        for ref in reference_refs:
            reference = self.reference_store.read_reference(str(ref.get("reference_id") or ""))
            if reference.hidden or str(ref.get("source_hash") or "") != reference.sha256:
                raise ReviewSprintStateError("Recommendation context reference is stale. Refresh recommendations before saving.")

    def _generate_review_sprint_provider_candidates(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise ReviewSprintStateError(f"Cannot generate provider candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise ReviewSprintStateError("Review sprint has blocking conflicts.")
        template_id = str(payload.get("template_id") or sprint.settings.get("provider_template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ReviewSprintStateError("Prompt template is disabled.")
        candidate_count = max(1, min(5, int(payload.get("candidate_count") or sprint.settings.get("provider_candidate_count") or 2)))
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_provider", True))
        include_local_context = bool(payload.get("include_local_context", True))
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        results = []
        created_total = 0
        provider_snapshots = []
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                if skip_existing and any((candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"} for candidate in candidates):
                    results.append({"task_id": task.task_id, "status": "skipped", "reason": "ready provider candidate exists"})
                    continue
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                local_context = candidates if include_local_context else []
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
                        render_midi_file=render_midi,
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
                usage_record = _provider_usage_record(
                    config_snapshot=provider_snapshot,
                    operation="review_sprint_provider_candidates",
                    template_id=template.template_id,
                    started_at=_utc_now(),
                    status="completed",
                    provider_usage=provider_usage,
                    request_id=provider_snapshot.get("request_id"),
                )
                write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or "")), now=_utc_now())
                created_total += len(generated)
                provider_snapshots.append(provider_snapshot)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "instruction": instruction,
                        "decision_report": review_decision_summary(decision_report),
                        "provider_summary": review_candidate_source_breakdown(ranked),
                        "provider_snapshot": provider_snapshot,
                    }
                )
            except (FileNotFoundError, ReviewTaskError, ReviewTaskStateError, ProviderError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        if asset_snapshot["asset_refs"]:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        if reference_snapshot["reference_refs"]:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_provider_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total, "template_id": template.template_id})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": sanitize_metadata(results), "created_count": created_total, "provider_snapshots": sanitize_metadata(provider_snapshots)})
        return response

    def _execute_queue_context_pack_action(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, item: SprintActionItem) -> dict[str, Any]:
        context_pack_id = str((item.result or {}).get("context_pack_id") or "")
        if context_pack_id:
            pack = self.context_pack_store.read_pack(context_pack_id)
            return {"status": "skipped", "reason": "context pack already created", "context_pack_id": pack.pack_id}
        preview = item.input.get("context_pack_preview") if isinstance(item.input.get("context_pack_preview"), dict) else {}
        asset_refs = preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else []
        reference_refs = preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else []
        if not asset_refs and not reference_refs:
            return {"status": "skipped", "reason": "recommendation has no context refs"}
        result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, str(item.task_id), {"name": item.input.get("name") or ""})
        return {"status": "created", "context_pack_id": result["context_pack"]["pack_id"], "asset_count": len(result["context_pack"].get("asset_refs") or []), "reference_count": len(result["context_pack"].get("reference_refs") or [])}

    def _generate_review_task_provider_candidates_for_queue(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any]) -> dict[str, Any]:
        payload = self._expand_context_pack_payload(payload)
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_provider", True)) and any((candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"} for candidate in candidates):
            return {"status": "skipped", "reason": "ready provider candidate exists", "created_count": 0, "created_candidate_ids": []}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        ensure_task_current(task, parent_plan)
        template_id = str(payload.get("template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ReviewSprintStateError("Prompt template is disabled.")
        candidate_count = max(1, min(5, int(payload.get("candidate_count") or 2)))
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        local_context = candidates if bool(payload.get("include_local_context", True)) else []
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
            generated.append(task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=bool(payload.get("render_midi", True)), now=_utc_now()))
        ranked = task_store.rank_candidates(task)
        updated_task = task_store.update_counts(task, now=_utc_now())
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        usage_record = _provider_usage_record(config_snapshot=provider_snapshot, operation="review_sprint_action_provider_candidates", template_id=template.template_id, started_at=_utc_now(), status="completed", provider_usage=provider_usage, request_id=provider_snapshot.get("request_id"))
        write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
        decision_report = task_store.write_decision_report(updated_task, build_review_decision_report(task=updated_task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or "")), now=_utc_now())
        if asset_snapshot["asset_refs"]:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_sprint_action_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
        if reference_snapshot["reference_refs"]:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_sprint_action_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
        self.project_store.append_event(project_id, "review_sprint_action_provider_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated), "template_id": template.template_id})
        return {"status": "generated" if generated else "skipped", "created_count": len(generated), "created_candidate_ids": [candidate.candidate_id for candidate in generated], "instruction": instruction, "decision_report": review_decision_summary(decision_report), "provider_summary": review_candidate_source_breakdown(ranked), "provider_snapshot": provider_snapshot}

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

    def _handle_project_edit_preview(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            payload = self._expand_context_pack_payload(payload)
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                self._send_error(HTTPStatus.BAD_REQUEST, "instruction is required.")
                return
            template_id = str(payload.get("template_id") or "provider-edit-intent").strip()
            template = self.prompt_template_store.get_template(template_id)
            if not template.enabled:
                self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
                return
            config, _sources = load_provider_config()
            asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
            asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
            reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
            reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
            patch, provider_snapshot = generate_provider_edit_patch(
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                config=config,
                asset_references=asset_prompt_refs,
                reference_references=reference_prompt_refs,
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
                asset_refs=asset_snapshot["asset_refs"],
                reference_refs=reference_snapshot["reference_refs"],
                context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
            )
            if asset_snapshot["asset_refs"]:
                self.asset_store.mark_used(
                    asset_snapshot["asset_refs"],
                    {
                        "usage_type": "provider_edit_preview",
                        "project_id": project_id,
                        "version_id": parent.version_id,
                        "preview_id": preview.preview_id,
                    },
                )
            if reference_snapshot["reference_refs"]:
                self.reference_store.mark_used(
                    reference_snapshot["reference_refs"],
                    {
                        "usage_type": "provider_edit_preview",
                        "project_id": project_id,
                        "version_id": parent.version_id,
                        "preview_id": preview.preview_id,
                    },
                )
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_preview",
                template_id=template.template_id,
                started_at=preview.created_at,
                status="completed",
                provider_usage=provider_usage,
                request_id=provider_snapshot.get("request_id"),
            )
            write_interface_document(
                self.project_store.project_dir(project_id) / "edit-previews" / preview.preview_id / "provider-usage.json",
                usage,
            )
            self.project_store.append_event(
                project_id,
                "provider_edit_preview_created",
                {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "template_id": template.template_id},
            )
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_edit_preview_apply(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            preview = read_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            if preview.parent_version_id != parent.version_id:
                self._send_error(HTTPStatus.CONFLICT, "Preview does not belong to this parent version.")
                return
            if preview.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview has already been applied.")
                return
            if preview_stale(preview, parent_plan):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview is stale because the parent song-plan.json has changed.")
                return
            patch = preview_patch(self.project_store.project_dir(project_id), preview_id)
            candidate = preview_candidate_plan(self.project_store.project_dir(project_id), preview_id)
            candidate.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": preview.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"preview_id": preview_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_apply",
                template_id=preview.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=preview.provider_usage,
                request_id=preview.provider_request_id,
            )
            context_pack = preview.source.get("context_pack") if isinstance(preview.source.get("context_pack"), dict) else None
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=preview.template_id,
                preview_id=preview_id,
                asset_refs=preview.source.get("asset_refs") if isinstance(preview.source.get("asset_refs"), list) else None,
                reference_refs=preview.source.get("reference_refs") if isinstance(preview.source.get("reference_refs"), list) else None,
                context_pack=context_pack,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            mark_provider_edit_preview_applied(self.project_store.project_dir(project_id), preview_id, job.job_id, version.version_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_applied",
                {"parent_version_id": parent.version_id, "preview_id": preview_id, "version_id": version.version_id, "job_id": job.job_id},
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "preview": preview.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_edit_preview_delete(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            delete_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            self.project_store.append_event(project_id, "provider_edit_preview_deleted", {"preview_id": preview_id, "parent_version_id": version_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})

    def _handle_project_edit_candidates(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            payload = self._expand_context_pack_payload(payload)
            group = self._create_project_candidate_group(project_id, version_id, payload)
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()}, status=HTTPStatus.CREATED)

    def _create_project_candidate_group(self, project_id: str, version_id: str, payload: dict[str, Any], *, mark_asset_usage: bool = True) -> Any:
        _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
        instruction = str(payload.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("instruction is required.")
        candidate_count = int(payload.get("candidate_count") or 3)
        template_id = str(payload.get("template_id") or "provider-edit-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ValueError("Prompt template is disabled.")
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        patches, provider_snapshot = generate_provider_edit_candidates(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            candidate_count=candidate_count,
            asset_references=asset_prompt_refs,
            reference_references=reference_prompt_refs,
        )
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        project_dir = self.project_store.project_dir(project_id)
        group_store = CandidateGroupStore(project_dir)
        group = group_store.create_group(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job_id=parent_job.job_id,
            instruction=instruction,
            template_id=template.template_id,
            candidate_count=len(patches),
            source={
                "parent_version_id": parent.version_id,
                "parent_job_id": parent_job.job_id,
                "song_plan_sha256": song_plan_hash(parent_plan),
                "asset_refs": list(asset_snapshot["asset_refs"]),
                "reference_refs": list(reference_snapshot["reference_refs"]),
                **({"context_pack": dict(payload["context_pack"])} if isinstance(payload.get("context_pack"), dict) else {}),
            },
            provider_usage=provider_usage,
            provider_request_id=None if provider_snapshot.get("request_id") is None else str(provider_snapshot.get("request_id")),
            now=_utc_now(),
        )
        usage_record = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_edit_candidates",
            template_id=template.template_id,
            started_at=group.created_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(project_dir / "candidate-groups" / group.group_id / "provider-usage.json", usage_record)
        for patch in patches:
            try:
                result = apply_provider_edit_patch(parent_plan, patch)
                validator = {
                    "status": "passed",
                    "checks": ["provider_edit_patch_schema", "edit_intent_validation", "song_plan_validation"],
                    "checked_at": _utc_now(),
                }
                scores = score_provider_edit_candidate(
                    parent_plan=parent_plan,
                    candidate_plan=result.plan,
                    patch=patch,
                    validator_status="passed",
                )
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="ready",
                    patch=patch.to_dict(),
                    scores=scores.to_dict(),
                    validator=validator,
                    quality=result.plan.quality.to_dict() if result.plan.quality else None,
                    provider_usage={},
                    candidate_plan=result.plan.to_dict(),
                    now=_utc_now(),
                )
                current_group = group_store.read_group(group.group_id)
                latest_candidate = current_group.candidates[-1]
                group_store.render_candidate_midi(group.group_id, latest_candidate.candidate_id)
            except Exception as exc:
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="failed",
                    patch=patch.to_dict(),
                    scores={},
                    validator={"status": "failed", "error": str(exc), "checked_at": _utc_now()},
                    quality=None,
                    error=str(exc),
                    now=_utc_now(),
                )
            group = group_store.read_group(group.group_id)
        if asset_snapshot["asset_refs"] and mark_asset_usage:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
        if reference_snapshot["reference_refs"] and mark_asset_usage:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
        self.project_store.append_event(
            project_id,
            "provider_edit_candidate_group_created",
            {
                "parent_version_id": parent.version_id,
                "group_id": group.group_id,
                "candidate_count": len(group.candidates),
                "template_id": template.template_id,
                "status": group.status,
            },
        )
        return group

    def _handle_project_candidate_groups_list(self, project_id: str) -> None:
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            self._send_json({"project_id": project_id, "groups": [group.to_dict() for group in group_store.list_groups()]})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_detail(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            self._send_json({"project_id": project_id, "group": group.to_dict()})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_usage(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            CandidateGroupStore(project_dir).read_group(group_id)
            records = collect_candidate_group_provider_usage_records(project_id, group_id, project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(build_provider_usage_report(scope="candidate_group", project_id=project_id, records=records))

    def _handle_project_candidate_group_apply(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
            if parent is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
                return
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
            if candidate_group_stale(group, song_plan_hash(parent_plan)):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
                return
            if group.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group has already been applied.")
                return
            candidate_id = str(payload.get("candidate_id") or _top_ranked_candidate_id(group) or "")
            candidate = next((item for item in group.candidates if item.candidate_id == candidate_id), None)
            if candidate is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
                return
            if candidate.status != "ready":
                self._send_error(HTTPStatus.CONFLICT, "Only ready candidates can be applied.")
                return
            patch = ProviderEditPatch.from_dict(group_store.read_candidate_patch(group.group_id, candidate.candidate_id))
            candidate_plan = SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate.candidate_id))
            candidate_plan.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": group.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"candidate_group_id": group.group_id, "candidate_id": candidate.candidate_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_candidate_apply",
                template_id=group.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=group.provider_usage,
                request_id=group.provider_request_id,
            )
            name = str(payload.get("name") or "") or f"Provider Candidate {len(document.versions) + 1}"
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=name,
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=group.template_id,
                preview_id=group.group_id,
                candidate_group_id=group.group_id,
                candidate_id=candidate.candidate_id,
                candidate=_candidate_source_summary(
                    {
                        "candidate_group_id": group.group_id,
                        "candidate_id": candidate.candidate_id,
                        "rank": candidate.rank,
                        "score": candidate.scores.get("combined"),
                        "quality_overall": candidate.scores.get("quality_overall"),
                        "summary": candidate.summary,
                        "status": candidate.status,
                        "created_at": candidate.created_at,
                    }
                ),
                asset_refs=group.source.get("asset_refs") if isinstance(group.source.get("asset_refs"), list) else None,
                reference_refs=group.source.get("reference_refs") if isinstance(group.source.get("reference_refs"), list) else None,
                context_pack=group.source.get("context_pack") if isinstance(group.source.get("context_pack"), dict) else None,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=name,
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            group = group_store.mark_applied(group.group_id, candidate.candidate_id, version_id=version.version_id, job_id=job.job_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_candidate_applied",
                {
                    "parent_version_id": parent.version_id,
                    "group_id": group.group_id,
                    "candidate_id": candidate.candidate_id,
                    "version_id": version.version_id,
                    "job_id": job.job_id,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "group": group.to_dict(), "version": version.to_dict(), "job": job.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_candidate_group_delete(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group_store.delete_group(group_id)
            self.project_store.append_event(project_id, "provider_edit_candidate_group_deleted", {"group_id": group_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "group_id": group_id})

    def _handle_project_candidate_group_render(self, method: str, project_id: str, group_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            if action == "render-midi":
                group = group_store.render_group_midi(group.group_id)
            else:
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                group = group_store.render_group_audio(group.group_id, config)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()})

    def _handle_project_candidate_artifact(self, method: str, project_id: str, group_id: str, candidate_id: str, action: str) -> None:
        try:
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            candidate_dir = group_store.candidate_dir(group.group_id, candidate_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "midi":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = candidate_midi_path(candidate_dir)
            if not path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate MIDI preview not found.")
                return
            self._send_file(path, "audio/midi")
            return

        if action == "audio":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = candidate_audio_path(candidate_dir)
            if not path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate WAV preview not found.")
                return
            self._send_file(path, "audio/wav")
            return

        if action == "render-midi":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                candidate = group_store.render_candidate_midi(group.group_id, candidate_id)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "render-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                candidate = group_store.render_candidate_audio(group.group_id, candidate_id, config)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            except RendererError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Candidate artifact route not found.")

    def _project_candidate_group_or_conflict(self, project_id: str, group_store: CandidateGroupStore, group_id: str) -> Any | None:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        group = group_store.read_group(group_id)
        parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
        if parent is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
            return None
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
        if candidate_group_stale(group, song_plan_hash(parent_plan)):
            self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
            return None
        return group

    def _handle_project_prompt_ab_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        created_group_ids: list[str] = []
        try:
            payload = self._expand_context_pack_payload(payload)
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                raise ValueError("instruction is required.")
            candidate_count = int(payload.get("candidate_count") or 2)
            template_ids = _prompt_ab_template_ids(payload.get("template_ids"))
            groups = []
            for template_id in template_ids:
                group = self._create_project_candidate_group(
                    project_id,
                    version_id,
                    {
                        **payload,
                        "instruction": instruction,
                        "candidate_count": candidate_count,
                        "template_id": template_id,
                    },
                    mark_asset_usage=False,
                )
                groups.append(group)
                created_group_ids.append(group.group_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = PromptABStore(project_dir).create_experiment(
                project_id=project_id,
                parent_version_id=version_id,
                instruction=instruction,
                candidate_count=candidate_count,
                template_ids=template_ids,
                group_ids=[group.group_id for group in groups],
                now=_utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "provider_prompt_ab_created",
                {"ab_id": experiment.ab_id, "group_ids": list(experiment.group_ids), "template_ids": list(template_ids)},
            )
            for group in groups:
                refs = group.source.get("asset_refs") if isinstance(group.source, dict) else None
                if isinstance(refs, list) and refs:
                    self.asset_store.mark_used(
                        refs,
                        {
                            "usage_type": "prompt_ab_candidate_generation",
                            "project_id": project_id,
                            "version_id": version_id,
                            "candidate_group_id": group.group_id,
                            "prompt_ab_id": experiment.ab_id,
                        },
                    )
                reference_refs = group.source.get("reference_refs") if isinstance(group.source, dict) else None
                if isinstance(reference_refs, list) and reference_refs:
                    self.reference_store.mark_used(
                        reference_refs,
                        {
                            "usage_type": "prompt_ab_candidate_generation",
                            "project_id": project_id,
                            "version_id": version_id,
                            "candidate_group_id": group.group_id,
                            "prompt_ab_id": experiment.ab_id,
                        },
                    )
        except FileNotFoundError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ContextPackStaleError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except ProviderError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "experiment": experiment.to_dict(), "groups": [group.to_dict() for group in groups]},
            status=HTTPStatus.CREATED,
        )

    def _handle_project_prompt_ab_list(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            experiments = PromptABStore(self.project_store.project_dir(project_id)).list_experiments()
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiments": [experiment.to_dict() for experiment in experiments]})

    def _handle_project_prompt_ab_detail(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = PromptABStore(project_dir).read_experiment(ab_id)
            group_store = CandidateGroupStore(project_dir)
            groups = [group_store.read_group(group_id).to_dict() for group_id in experiment.group_ids]
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiment": experiment.to_dict(), "groups": groups})

    def _handle_project_prompt_ab_delete(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            PromptABStore(self.project_store.project_dir(project_id)).delete_experiment(ab_id)
            self.project_store.append_event(project_id, "provider_prompt_ab_deleted", {"ab_id": ab_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "ab_id": ab_id})

    def _handle_project_provider_usage(self, project_id: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        usage_records = []
        for version in document.versions:
            usage_path = Path(version.output_dir) / "data" / "provider-usage.json"
            if usage_path.exists():
                usage = read_json(usage_path)
                usage_records.append({"version_id": version.version_id, "job_id": version.job_id, "usage": usage})
        group_records = []
        groups_dir = self.project_store.project_dir(project_id) / "candidate-groups"
        if groups_dir.exists():
            for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
                try:
                    usage = read_json(usage_path)
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
                group_records.append({"group_id": usage_path.parent.name, "usage": usage})
        total_tokens = sum(int(record["usage"].get("total_tokens") or 0) for record in usage_records)
        total_tokens += sum(int(record["usage"].get("total_tokens") or 0) for record in group_records)
        self._send_json(
            {
                "project_id": project_id,
                "total_calls": len(usage_records) + len(group_records),
                "total_tokens": total_tokens,
                "records": usage_records,
                "candidate_group_records": group_records,
            }
        )

    def _handle_project_provider_usage_report(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            project_dir = self.project_store.project_dir(project_id)
            records = collect_project_provider_usage_records(project_id, document.versions, project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_json(build_provider_usage_report(scope="project", project_id=project_id, records=records))

    def _handle_project_review_metrics(self, method: str, project_id: str, *, refresh: bool) -> None:
        expected = "POST" if refresh else "GET"
        if method != expected:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self._get_or_refresh_project_review_metrics(project_id, refresh=refresh)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if refresh:
            self.project_store.append_event(project_id, "project_review_metrics_refreshed", {"latest_readiness": report.get("latest_readiness"), "sprint_count": report.get("sprint_count")})
        self._send_json({"ok": True, "project_id": project_id, "review_metrics": report, "summary": project_review_metrics_summary(report)})

    def _project_edit_parent(self, project_id: str, version_id: str) -> tuple[Any, Any, JobState, SongPlan]:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        parent = next((version for version in document.versions if version.version_id == version_id), None)
        if parent is None:
            raise FileNotFoundError(version_id)
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            raise ValueError("Parent version job is missing.")
        if parent.status != "completed" or parent_job.status != "completed":
            raise ValueError("Parent version must be completed before editing.")
        parent_plan_path = Path(parent.output_dir) / "data" / "song-plan.json"
        if not parent_plan_path.exists():
            raise ValueError("Parent song-plan.json is missing.")
        parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
        return document, parent, parent_job, parent_plan

    def _handle_batch_route(self, method: str, batch_id: str, tail: str) -> None:
        if tail == "":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            self._send_json(document.to_dict())
            return

        if tail == "/launch":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, started = self.batch_runner.launch_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json(
                {"ok": True, "started_count": started, **document.to_dict()},
                status=status,
            )
            return

        if tail == "/pause":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error = self.batch_runner.pause_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **document.to_dict()}, status=status)
            return

        if tail == "/resume":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error = self.batch_runner.resume_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **document.to_dict()}, status=status)
            return

        if tail == "/retry-failed":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, reset_count = self.batch_runner.retry_failed(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "reset_count": reset_count, **document.to_dict()}, status=status)
            return

        if tail in {"/render-audio", "/render-failed-audio"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, queued_count = self.batch_runner.render_audio(
                batch_id,
                failed_only=tail == "/render-failed-audio",
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "queued_count": queued_count, **document.to_dict()}, status=status)
            return

        if tail in {
            "/render-stems",
            "/render-stem-audio",
            "/render-failed-stems",
            "/render-failed-stem-audio",
        }:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, queued_count = self.batch_runner.render_stems(
                batch_id,
                audio=tail in {"/render-stem-audio", "/render-failed-stem-audio"},
                failed_only=tail in {"/render-failed-stems", "/render-failed-stem-audio"},
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "queued_count": queued_count, **document.to_dict()}, status=status)
            return

        if tail == "/export":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self._send_json(self.batch_store.export_batch(batch_id))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
            return

        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.batch_store.hide_batch(batch_id, tail == "/hide")
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            deleted, status, error = self.batch_runner.delete_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "deleted": deleted, "batch_id": batch_id})
            return

        if tail == "/open-folder":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                batch_dir = self.batch_store.batch_dir(batch_id)
                if not batch_dir.exists():
                    raise FileNotFoundError(batch_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            open_folder(batch_dir)
            self._send_json({"ok": True, "path": str(batch_dir)})
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Batch route not found.")

    def _handle_job_route(self, method: str, job_id: str, tail: str) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
            return

        run_dir = Path(job.output_dir)
        if tail == "/open-folder":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            open_folder(run_dir)
            self._send_json({"ok": True, "path": str(run_dir)})
            return
        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job = self.store.hide_job(job_id, hidden=tail == "/hide")
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            self._send_json({"ok": True, "job": job.to_dict()})
            return
        if tail == "/cancel":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job, status, error = self.store.cancel_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job": job.to_dict() if job is not None else None})
            return
        if tail == "/retry":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job, status, error = self.store.retry_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job": job.to_dict() if job is not None else None})
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            deleted, status, error = self.store.delete_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "deleted": deleted, "job_id": job_id})
            return
        if tail == "/render-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            profile = self._renderer_profile_from_payload(payload)
            config = profile.to_renderer_config() if profile is not None else None
            audio, status, error = self.store.render_job_audio(job_id, config=config, audio_profile=profile)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job_id": job_id, **audio}, status=status)
            return
        if tail == "/render-stems":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            data, status, error = self.store.render_job_stems(job_id, force=bool(payload.get("force", False)))
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **data}, status=status)
            return
        if tail == "/render-stem-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            stem_ids = payload.get("stem_ids")
            if stem_ids is not None:
                if not isinstance(stem_ids, list):
                    self._send_error(HTTPStatus.BAD_REQUEST, "stem_ids must be a list.")
                    return
                stem_ids = [str(stem_id) for stem_id in stem_ids]
            data, status, error = self.store.render_job_stem_audio(
                job_id,
                stem_ids=stem_ids,
                force=bool(payload.get("force", False)),
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **data}, status=status)
            return
        if tail.startswith("/nodes/") and tail.endswith("/retry"):
            self._send_node_retry(method, job, tail)
            return

        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        if tail == "":
            self._send_json(job.to_dict())
            return
        if tail == "/song-plan":
            plan_path = run_dir / "data" / "song-plan.json"
            if not plan_path.exists():
                self._send_error(
                    HTTPStatus.CONFLICT,
                    "song-plan.json is not available for this job yet.",
                )
                return
            self._send_json(read_json(plan_path))
            return
        if tail == "/timeline":
            self._send_runtime_view(job, "timeline")
            return
        if tail == "/tracks":
            self._send_runtime_view(job, "tracks")
            return
        if tail == "/validator":
            self._send_runtime_view(job, "validator")
            return
        if tail == "/quality":
            self._send_runtime_view(job, "quality")
            return
        if tail == "/edit":
            metadata = _read_edit_metadata_for_run(run_dir)
            if metadata is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Edit metadata not found.")
                return
            self._send_json({"job_id": job.job_id, "edit": metadata})
            return
        if tail == "/provider-usage":
            usage_path = run_dir / "data" / "provider-usage.json"
            if not usage_path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Provider usage not found.")
                return
            self._send_json({"job_id": job.job_id, "usage": read_json(usage_path)})
            return
        if tail == "/events":
            self._send_json({"events": _read_events(run_dir / "logs" / "events.jsonl")})
            return
        if tail == "/artifacts":
            self._send_json({"artifacts": discover_artifacts(run_dir)})
            return
        if tail == "/midi":
            self._send_file(run_dir / "renders" / "song.mid", "audio/midi")
            return
        if tail == "/audio":
            audio_path = run_dir / "renders" / "song.wav"
            if not audio_path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Audio render is not available for this job.")
                return
            stale_reasons = self._job_audio_artifact_stale_reasons(job)
            if stale_reasons:
                self._send_error(HTTPStatus.CONFLICT, f"Audio artifact is stale: {', '.join(stale_reasons)}.")
                return
            self._send_file(audio_path, "audio/wav")
            return
        if tail == "/stems":
            data, status, error = self.store.get_job_stems(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json(data, status=status)
            return
        if tail.startswith("/stems/"):
            self._send_stem_file(job, tail)
            return
        if tail == "/nodes":
            self._send_nodes_list(job)
            return
        if tail.startswith("/nodes/"):
            self._send_node_route(method, job, tail)
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Job route not found.")

    def _expand_context_pack_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        pack_id = str(payload.get("context_pack_id") or "").strip()
        if not pack_id:
            return payload
        pack = self.context_pack_store.read_pack(pack_id)
        applied = apply_context_pack(pack, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_utc_now())
        asset_refs = merge_context_refs(payload.get("asset_refs"), applied["asset_refs"], "asset_id", 5)
        reference_refs = merge_context_refs(payload.get("reference_refs"), applied["reference_refs"], "reference_id", 5)
        return {
            **payload,
            "asset_refs": asset_refs,
            "reference_refs": reference_refs,
            "context_pack": context_pack_snapshot(pack, {"asset_refs": asset_refs, "reference_refs": reference_refs}, captured_at=_utc_now()),
        }
