from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart001:
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
