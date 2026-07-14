from __future__ import annotations

import sys as _sys
from types import ModuleType as _ModuleType

from .runtime_parts.dependencies.part_001 import *

from .runtime_parts.dependencies.part_002 import *

from .runtime_parts.dependencies.part_003 import *

from .runtime_parts.dependencies.part_004 import *

from .runtime_parts.dependencies.part_005 import *

from .runtime_parts.core import *

from .runtime_parts.helpers.part_001 import *

from .runtime_parts.helpers.part_002 import *

from .runtime_parts.helpers.part_003 import *

from .runtime_parts.helpers.part_004 import *

from .runtime_parts.helpers.part_005 import *

from .runtime_parts.job_store import JobStore

from .runtime_parts.batch_runner import BatchRunner

class _RuntimeModule(_ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        prefix = __name__ + ".runtime_parts."
        for module_name, module in tuple(_sys.modules.items()):
            if module_name.startswith(prefix) and hasattr(module, name):
                setattr(module, name, value)


_sys.modules[__name__].__class__ = _RuntimeModule

__all__ = [name for name in globals() if not name.startswith('__')]
