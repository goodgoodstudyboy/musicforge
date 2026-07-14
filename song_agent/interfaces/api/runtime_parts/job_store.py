from __future__ import annotations

from .job_store_parts.part_001 import JobStorePart001

from .job_store_parts.part_002 import JobStorePart002

from .job_store_parts.part_003 import JobStorePart003

from .job_store_parts.part_004 import JobStorePart004

from .job_store_parts.part_005 import JobStorePart005

class JobStore(JobStorePart001, JobStorePart002, JobStorePart003, JobStorePart004, JobStorePart005):
    pass

__all__ = ['JobStore']
