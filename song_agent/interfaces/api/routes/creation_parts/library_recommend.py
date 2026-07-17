from __future__ import annotations

from typing import Any as _InterfaceType

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesLibraryRecommend(CreationRouteContext):
    def _handle_library_recommend(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        result = _interfaces_api_runtime.recommend_library_context(index, payload)
        recommendation = result.get("recommendation", {})
        self.library_index_store.append_event(
            "library_recommend_requested",
            {
                "asset_count": len(recommendation.get("asset_results", [])),
                "reference_count": len(recommendation.get("reference_results", [])),
                "goal": payload.get("goal"),
            },
            now=_interfaces_api_runtime._utc_now(),
        )
        self._send_json(result)

    def _handle_context_packs_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_hidden = _interfaces_api_runtime._query_value(query, "include_hidden") in {"1", "true", "yes"}
            packs = self.context_pack_store.list_packs(include_hidden=include_hidden)
            self._send_json({"context_packs": [_interfaces_api_runtime.context_pack_public_dict(pack) for pack in packs], "count": len(packs)})
            return
        if method == "POST":
            try:
                pack = self.context_pack_store.create_pack(
                    self._read_json_body(),
                    asset_store=self.asset_store,
                    reference_store=self.reference_store,
                    now=_interfaces_api_runtime._utc_now(),
                )
            except ValueError as exc:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_context_pack_route(self, method: str, pack_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"context_pack": _interfaces_api_runtime.context_pack_public_dict(self.context_pack_store.read_pack(pack_id))})
                return
            if tail == "/apply-preview":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                applied = self.context_pack_store.apply_preview(pack_id, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_interfaces_api_runtime._utc_now())
                self.context_pack_store.append_event(pack_id, "context_pack_applied", {"mode": "preview"}, now=_interfaces_api_runtime._utc_now())
                self._send_json(applied)
                return
            if tail == "/hide":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, True)
                self._send_json({"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack)})
                return
            if tail == "/unhide":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, False)
                self._send_json({"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.context_pack_store.delete_pack(pack_id)
                self._send_json({"ok": True, "deleted": True, "pack_id": pack_id})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Context pack route not found.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Context pack not found.")
        except _interfaces_api_runtime.ContextPackStaleError as exc:
            try:
                self.context_pack_store.append_event(pack_id, "context_pack_stale", {"error": str(exc)}, now=_interfaces_api_runtime._utc_now())
            except (OSError, ValueError):
                pass
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_asset_route(self, method: str, asset_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    self._send_json({"asset": _interfaces_api_runtime.asset_public_dict(self.asset_store.read_asset(asset_id))})
                    return
                if method == "POST":
                    asset = self.asset_store.update_asset(asset_id, self._read_json_body())
                    self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.hide_asset(asset_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset)})
                return
            if tail in {"/favorite", "/unfavorite"}:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.favorite_asset(asset_id, favorite=tail == "/favorite")
                self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.delete_asset(asset_id)
                self._send_json({"ok": True, "deleted": True, "asset_id": asset_id})
                return
            if tail == "/render-midi":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.render_asset_midi(asset_id)
                self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset)})
                return
            if tail == "/render-audio":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = _interfaces_api_runtime.load_renderer_config()
                config.validate_ready_for_render()
                asset = self.asset_store.render_asset_audio(asset_id, config)
                self._send_json({"ok": True, "asset": _interfaces_api_runtime.asset_public_dict(asset)})
                return
            if tail == "/midi":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(_interfaces_api_runtime.asset_midi_path(self.asset_store.asset_dir(asset_id)), "audio/midi", filename=f"{asset_id}.mid")
                return
            if tail == "/audio":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(_interfaces_api_runtime.asset_audio_path(self.asset_store.asset_dir(asset_id)), "audio/wav", filename=f"{asset_id}.wav")
                return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Asset not found.")
            return
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            status = _interfaces_api_runtime.HTTPStatus.CONFLICT if "MIDI preview" in str(exc) or "do not have MIDI" in str(exc) else _interfaces_api_runtime.HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Asset route not found.")

    def _handle_asset_extract_from_job(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        job_id = str(payload.get("job_id") or "")
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Job not found.")
            return
        plan_path = _interfaces_api_runtime.Path(job.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(plan_path))
            assets = self._create_assets_from_plan(plan, {"source_type": "job", "job_id": job.job_id, "style": job.input_payload.get("style")}, payload)
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [_interfaces_api_runtime.asset_public_dict(asset) for asset in assets]}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _handle_asset_extract_from_project_version(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        version_id = str(payload.get("version_id") or "")
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = _interfaces_api_runtime.Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = _interfaces_api_runtime.SongPlan.from_dict(_interfaces_api_runtime.read_json(plan_path))
            assets = self._create_assets_from_plan(
                plan,
                {"source_type": "project_version", "project_id": project_id, "version_id": version.version_id, "job_id": version.job_id, "style": version.request.get("style")},
                payload,
            )
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [_interfaces_api_runtime.asset_public_dict(asset) for asset in assets]}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _handle_asset_extract_from_candidate(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        group_id = str(payload.get("candidate_group_id") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        try:
            self.project_store.get_project(project_id)
            group_store = _interfaces_api_runtime.CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            plan = _interfaces_api_runtime.SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate_id))
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
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Candidate not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [_interfaces_api_runtime.asset_public_dict(asset) for asset in assets]}, status=_interfaces_api_runtime.HTTPStatus.CREATED)

    def _create_assets_from_plan(self, plan: _InterfaceType, source: ImplementationDocument, payload: ImplementationDocument) -> list[Any]:
        assets = []
        for asset_payload in _interfaces_api_runtime.extract_assets_from_song_plan(plan, source, payload):
            assets.append(self.asset_store.create_asset(asset_payload, now=_interfaces_api_runtime._utc_now()))
        return assets

    def _handle_references_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = _interfaces_api_runtime.parse_qs(query_string)
            filters = {key: _interfaces_api_runtime._query_value(query, key) for key in ("q", "type", "tag", "favorite", "project_id")}
            include_hidden = _interfaces_api_runtime._query_value(query, "include_hidden") in {"1", "true", "yes"}
            limit_value = _interfaces_api_runtime._query_value(query, "limit")
            limit = int(limit_value) if limit_value else 100
            references = self.reference_store.list_references(include_hidden=include_hidden, filters=filters)[: max(1, min(limit, 500))]
            self._send_json(
                {
                    "references": [_interfaces_api_runtime.reference_public_dict(reference) for reference in references],
                    "count": len(references),
                    "filters": {**filters, "include_hidden": include_hidden},
                }
            )
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_reference_import(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if not self._content_length_within(_interfaces_api_runtime.REFERENCE_IMPORT_MAX_BODY_BYTES):
            self._send_error(_interfaces_api_runtime.HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Reference import request body is too large.")
            return
        try:
            reference, duplicate = self.reference_store.import_reference(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "duplicate": duplicate, "reference": _interfaces_api_runtime.reference_public_dict(reference)},
            status=_interfaces_api_runtime.HTTPStatus.OK if duplicate else _interfaces_api_runtime.HTTPStatus.CREATED,
        )
