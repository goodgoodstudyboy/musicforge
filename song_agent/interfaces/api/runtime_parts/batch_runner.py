from __future__ import annotations

from .batch_runner_parts.part_001 import BatchRunnerPart001

from .batch_runner_parts.part_002 import BatchRunnerPart002

from .batch_runner_parts.part_003 import BatchRunnerPart003

from .batch_runner_parts.part_004 import BatchRunnerPart004

class BatchRunner(BatchRunnerPart001, BatchRunnerPart002, BatchRunnerPart003, BatchRunnerPart004):
    pass

__all__ = ['BatchRunner']
