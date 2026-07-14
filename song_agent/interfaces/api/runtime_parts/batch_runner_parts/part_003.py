from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.part_001 import BatchDocument, HTTPStatus, Path, now_iso, threading

class BatchRunnerPart003:
    def _sync_running_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None
            changed = False
            for item in document.items:
                if item.status != "running" or not item.job_id:
                    continue
                job = self.job_store.get_job(item.job_id)
                if job is None:
                    item.status = "failed"
                    item.error = "Linked job is missing."
                    item.updated_at = now_iso()
                    changed = True
                    continue
                if job.output_dir:
                    item.output_dir = job.output_dir
                if job.status == "completed":
                    item.status = "completed"
                    item.error = None
                    item.updated_at = now_iso()
                    changed = True
                    self.batch_store.append_event(
                        batch_id,
                        "batch_item_completed",
                        {
                            "item_id": item.item_id,
                            "job_id": job.job_id,
                            "project_id": item.project_id,
                            "version_id": item.version_id,
                        },
                    )
                elif job.status == "cancelled":
                    item.status = "cancelled"
                    item.error = job.error or "Job was cancelled."
                    item.updated_at = now_iso()
                    changed = True
                elif job.status in {"failed", "interrupted", "stalled"}:
                    item.status = "failed"
                    item.error = job.error or job.last_error or f"Job ended with status {job.status}."
                    item.updated_at = now_iso()
                    changed = True
            if self._archive_completed_project_items(document):
                changed = True
            if changed:
                self.batch_store.save_batch(document)
                document = self.batch_store.get_batch(batch_id)
            return document

    def _archive_completed_project_items(self, document: BatchDocument) -> bool:
        changed = False
        for item in sorted(document.items, key=lambda batch_item: batch_item.index):
            if item.status != "completed" or not item.project:
                continue
            if item.project_id and item.version_id:
                continue
            if self._has_unarchived_prior_project_item(document, item):
                continue
            if not item.job_id:
                continue
            job = self.job_store.get_job(item.job_id)
            if job is None or job.status != "completed":
                continue
            self._archive_item_to_project(document, item, job)
            changed = True
        return changed

    @staticmethod
    def _has_unarchived_prior_project_item(document: BatchDocument, item: Any) -> bool:
        for prior in document.items:
            if prior.index >= item.index or prior.project != item.project:
                continue
            if prior.status in {"queued", "running"}:
                return True
            if prior.status == "completed" and not prior.version_id:
                return True
        return False

    def _archive_item_to_project(self, document: BatchDocument, item: Any, job: JobState) -> None:
        if self.project_store is None or not item.project:
            return
        if item.project_id and item.version_id:
            return
        project = self.project_store.find_or_create_project(item.project)
        item.project_id = project.state.project_id
        try:
            updated = self.project_store.add_version_from_job(
                project.state.project_id,
                job,
                name=item.version_name or "",
                note=item.version_note or "",
            )
        except ValueError as exc:
            if "already attached" not in str(exc):
                raise
            updated = self.project_store.get_project(project.state.project_id)
        version = next((version for version in updated.versions if version.job_id == job.job_id), None)
        if version is not None:
            item.version_id = version.version_id
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_item_archived_to_project",
            {
                "item_id": item.item_id,
                "job_id": job.job_id,
                "project_id": item.project_id,
                "version_id": item.version_id,
            },
        )

    def _start_available_audio_items(self, batch_id: str) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.audio_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.audio_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.audio_status = "failed"
                    item.audio_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.audio_status = "running"
                item.audio_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_audio_item,
                        args=(batch_id, item.item_id, item.job_id),
                        name=f"musicforge-batch-audio-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_audio_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_audio_item(self, batch_id: str, item_id: str, job_id: str) -> None:
        audio, status, error = self.job_store.render_job_audio(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                if error is None and status == HTTPStatus.OK:
                    item.audio_status = "completed"
                    item.audio_path = audio.get("audio")
                    item.audio_error = None
                    event_type = "batch_audio_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "audio": item.audio_path}
                else:
                    item.audio_status = "failed"
                    item.audio_path = None
                    item.audio_error = error or f"Audio render failed with status {status.value}."
                    event_type = "batch_audio_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.audio_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _start_available_stem_items(self, batch_id: str, *, audio: bool) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.stem_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.stem_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.stem_status = "failed"
                    item.stem_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.stem_status = "running"
                item.stem_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_stem_item,
                        args=(batch_id, item.item_id, item.job_id, audio),
                        name=f"musicforge-batch-stem-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_stem_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id, "audio": audio},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_stem_item(self, batch_id: str, item_id: str, job_id: str, audio: bool) -> None:
        if audio:
            data, status, error = self.job_store.render_job_stem_audio(job_id)
        else:
            data, status, error = self.job_store.render_job_stems(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                job = self.job_store.get_job(job_id)
                if error is None and status == HTTPStatus.OK:
                    manifest = data.get("manifest", {})
                    stems = manifest.get("stems", [])
                    item.stem_manifest_path = str(Path(job.output_dir) / "stems" / "manifest.json") if job else item.stem_manifest_path
                    item.stem_count = len(stems)
                    item.stem_audio_completed_count = sum(1 for stem in stems if stem.get("audio_status") in {"completed", "skipped"})
                    item.stem_status = data.get("status", "completed")
                    item.stem_error = (
                        "One or more stems failed."
                        if item.stem_status in {"partial_failed", "failed"}
                        else None
                    )
                    event_type = "batch_stem_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "status": item.stem_status}
                else:
                    item.stem_status = "failed"
                    item.stem_error = error or f"Stem render failed with status {status.value}."
                    event_type = "batch_stem_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.stem_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _sync_audio_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None

    def _sync_stem_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None
