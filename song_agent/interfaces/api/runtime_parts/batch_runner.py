from __future__ import annotations

from .batch_runner_parts.recover_existing_batches import BatchRunnerRecoverExistingBatches

from .batch_runner_parts.render_stems import BatchRunnerRenderStems

from .batch_runner_parts.sync_running_items import BatchRunnerSyncRunningItems

from .batch_runner_parts.finish_batch import BatchRunnerFinishBatch

class BatchRunner(BatchRunnerRecoverExistingBatches, BatchRunnerRenderStems, BatchRunnerSyncRunningItems, BatchRunnerFinishBatch):
    pass

__all__ = ['BatchRunner']
