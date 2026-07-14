from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class CreationRoutesPart016:
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
