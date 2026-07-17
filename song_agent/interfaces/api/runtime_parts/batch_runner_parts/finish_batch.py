from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.batch_runner_context import BatchRunnerContext

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import BatchDocument
from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProviderError, RendererError, load_provider_config, load_renderer_config

class BatchRunnerFinishBatch(BatchRunnerContext):
    def _finish_batch(self, document: BatchDocument) -> None:
        if document.state.failed_count or document.state.cancelled_count:
            document.state.status = "completed_with_errors"
            document.state.error = "One or more batch items failed."
        else:
            document.state.status = "completed"
            document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_finished",
            {"status": document.state.status},
        )

    @staticmethod
    def _provider_readiness_error(document: BatchDocument) -> str | None:
        if not any(
            item.status == "queued" and item.request.get("generation_mode") == "provider"
            for item in document.items
        ):
            return None
        provider_config, _sources = load_provider_config()
        try:
            provider_config.validate_ready_for_provider()
        except ProviderError as exc:
            return str(exc)
        return None

    @staticmethod
    def _renderer_readiness_error() -> str | None:
        config, _sources = load_renderer_config()
        try:
            config.validate_ready_for_render()
        except RendererError as exc:
            return str(exc)
        return None

    @staticmethod
    def _audio_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.audio_status] = counts.get(item.audio_status, 0) + 1
        return counts

    @staticmethod
    def _stem_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "partial_completed": 0,
            "partial_failed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.stem_status] = counts.get(item.stem_status, 0) + 1
        return counts
