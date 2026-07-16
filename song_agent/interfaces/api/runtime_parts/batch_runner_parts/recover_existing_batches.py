from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import Any, BatchDocument, HTTPStatus, now_iso, threading


class BatchRunnerRecoverExistingBatches:
    def __init__(self, batch_store: Any, job_store: Any, project_store: Any | None = None) -> None:
        self.batch_store = batch_store
        self.job_store = job_store
        self.project_store = project_store
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.threads: dict[str, threading.Thread] = {}
        self.audio_threads: dict[str, threading.Thread] = {}
        self.stem_threads: dict[str, threading.Thread] = {}
        self.recover_existing_batches()

    def recover_existing_batches(self) -> None:
        for document in self.batch_store.list_batches(include_hidden=True):
            recovered_audio = self._recover_interrupted_audio(document)
            if recovered_audio:
                self.batch_store.save_batch(document)
                self.batch_store.append_event(
                    document.state.batch_id,
                    "batch_audio_recovered_failed",
                    {"failed_count": recovered_audio},
                )
            if document.state.status not in {"queued", "running", "paused"}:
                continue
            synced = self._sync_running_items(document.state.batch_id)
            if synced is None:
                continue
            if synced.state.queued_count == 0 and synced.state.running_count == 0:
                self._finish_batch(synced)
                continue
            if synced.state.status in {"queued", "running"}:
                synced.state.status = "paused"
                synced.state.error = "Batch was interrupted by a previous server shutdown."
                self.batch_store.save_batch(synced)
                self.batch_store.append_event(
                    synced.state.batch_id,
                    "batch_recovered_paused",
                    {"queued_count": synced.state.queued_count},
                )

    @staticmethod
    def _recover_interrupted_audio(document: BatchDocument) -> int:
        recovered = 0
        for item in document.items:
            if item.audio_status in {"queued", "running"}:
                item.audio_status = "failed"
                item.audio_error = "Audio render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
            if item.stem_status in {"queued", "running"}:
                item.stem_status = "failed"
                item.stem_error = "Stem render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
        return recovered

    def launch_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Batch is already running.", 0
        if not any(item.status == "queued" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch has no queued items to launch.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0

        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_launched", {"started_count": started})
        return document, HTTPStatus.ACCEPTED, None, started

    def pause_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status not in {"running", "queued"}:
            return document, HTTPStatus.CONFLICT, "Only a running batch can be paused."
        document.state.status = "paused"
        document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(batch_id, "batch_paused", {})
        return document, HTTPStatus.OK, None

    def resume_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status != "paused":
            return document, HTTPStatus.CONFLICT, "Only a paused batch can be resumed."
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        self._start_available_items(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_resumed", {})
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None

    def retry_failed(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Cannot retry failed items while the batch is running.", 0
        reset_count = 0
        for item in document.items:
            if item.status in {"failed", "cancelled"}:
                item.status = "queued"
                item.error = None
                item.job_id = None
                item.output_dir = None
                item.audio_status = "not_started"
                item.audio_path = None
                item.audio_error = None
                item.stem_status = "not_started"
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
                item.stem_error = None
                item.updated_at = now_iso()
                reset_count += 1
        if reset_count == 0:
            return document, HTTPStatus.CONFLICT, "Batch has no failed items to retry.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(
            batch_id,
            "batch_retry_failed",
            {"reset_count": reset_count, "started_count": started},
        )
        return document, HTTPStatus.ACCEPTED, None, reset_count

    def render_audio(
        self,
        batch_id: str,
        *,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch audio while batch generation is running.", 0
        if any(item.audio_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch audio render is already running.", 0
        renderer_error = self._renderer_readiness_error()
        if renderer_error is not None:
            return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.audio_status != "failed":
                continue
            if item.status != "completed":
                if not failed_only and item.audio_status == "not_started":
                    item.audio_status = "skipped"
                    item.audio_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if not failed_only and item.audio_status == "completed" and item.audio_path:
                continue
            item.audio_status = "queued"
            item.audio_path = None
            item.audio_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            message = (
                "Batch has no failed audio renders to retry."
                if failed_only
                else "Batch has no completed items that need audio render."
            )
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_audio_render_requested",
            {"queued_count": queued_count, "failed_only": failed_only},
        )
        self._start_available_audio_items(batch_id)
        self._ensure_audio_thread(batch_id)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count
