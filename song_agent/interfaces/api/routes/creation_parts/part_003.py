from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart003:
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
