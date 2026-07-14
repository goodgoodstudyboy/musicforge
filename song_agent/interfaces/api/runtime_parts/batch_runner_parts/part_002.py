from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.part_001 import BatchDocument, HTTPStatus, now_iso, threading, time

class BatchRunnerPart002:
    def render_stems(
        self,
        batch_id: str,
        *,
        audio: bool = False,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch stems while batch generation is running.", 0
        if any(item.stem_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch stem render is already running.", 0
        if audio:
            renderer_error = self._renderer_readiness_error()
            if renderer_error is not None:
                return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if item.status != "completed":
                if not failed_only and item.stem_status == "not_started":
                    item.stem_status = "skipped"
                    item.stem_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if (
                not audio
                and not failed_only
                and item.stem_status == "completed"
                and item.stem_manifest_path
            ):
                continue
            if (
                audio
                and item.stem_status == "completed"
                and item.stem_count
                and item.stem_audio_completed_count >= item.stem_count
            ):
                continue
            if audio and not item.stem_manifest_path and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if not audio:
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
            item.stem_status = "queued"
            item.stem_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            if failed_only:
                message = "Batch has no failed stem renders to retry."
            elif audio:
                message = "Batch has no completed items that need stem audio render."
            else:
                message = "Batch has no completed items that need stem render."
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_stem_render_requested",
            {"queued_count": queued_count, "audio": audio, "failed_only": failed_only},
        )
        self._start_available_stem_items(batch_id, audio=audio)
        self._ensure_stem_thread(batch_id, audio=audio)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count

    def delete_batch(self, batch_id: str) -> tuple[bool, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return False, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return False, HTTPStatus.CONFLICT, "Cannot delete a running batch. Pause it first."
        self.batch_store.delete_batch(batch_id)
        return True, HTTPStatus.OK, None

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            threads = [*self.threads.values(), *self.audio_threads.values(), *self.stem_threads.values()]
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)

    def _run_batch(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "paused":
                    if document.state.running_count == 0:
                        return
                    time.sleep(0.1)
                    continue
                if document.state.status != "running":
                    return
                self._start_available_items(batch_id)
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "running" and document.state.queued_count == 0 and document.state.running_count == 0:
                    self._finish_batch(document)
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.threads.pop(batch_id, None)

    def _run_batch_audio(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_audio_items(batch_id)
                document = self._sync_audio_items(batch_id)
                if document is None:
                    return
                if not any(item.audio_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_audio_render_finished",
                        self._audio_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.audio_threads.pop(batch_id, None)

    def _run_batch_stems(self, batch_id: str, audio: bool) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_stem_items(batch_id, audio=audio)
                document = self._sync_stem_items(batch_id)
                if document is None:
                    return
                if not any(item.stem_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_stem_render_finished",
                        self._stem_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.stem_threads.pop(batch_id, None)

    def _ensure_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch,
                args=(batch_id,),
                name=f"musicforge-batch-{batch_id}",
                daemon=True,
            )
            self.threads[batch_id] = thread
            thread.start()

    def _ensure_audio_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.audio_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_audio,
                args=(batch_id,),
                name=f"musicforge-batch-audio-{batch_id}",
                daemon=True,
            )
            self.audio_threads[batch_id] = thread
            thread.start()

    def _ensure_stem_thread(self, batch_id: str, *, audio: bool) -> None:
        with self.lock:
            existing = self.stem_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_stems,
                args=(batch_id, audio),
                name=f"musicforge-batch-stems-{batch_id}",
                daemon=True,
            )
            self.stem_threads[batch_id] = thread
            thread.start()

    def _start_available_items(self, batch_id: str) -> int:
        with self.lock:
            document = self.batch_store.get_batch(batch_id)
            if document.state.status != "running":
                return 0
            running_count = sum(1 for item in document.items if item.status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            for item in document.items:
                if item.status != "queued" or started >= available:
                    continue
                try:
                    job = self.job_store.create_job(item.request, start_immediately=True)
                except Exception as exc:
                    item.status = "failed"
                    item.error = str(exc)
                    item.updated_at = now_iso()
                    document.state.error = str(exc)
                    continue
                item.status = "running"
                item.job_id = job.job_id
                item.output_dir = job.output_dir
                item.error = None
                item.attempt_count += 1
                item.updated_at = now_iso()
                started += 1
                self.batch_store.append_event(
                    batch_id,
                    "batch_item_started",
                    {
                        "item_id": item.item_id,
                        "job_id": job.job_id,
                        "attempt_count": item.attempt_count,
                    },
                )
            self.batch_store.save_batch(document)
            return started
