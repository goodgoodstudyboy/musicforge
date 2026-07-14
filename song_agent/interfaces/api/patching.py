from __future__ import annotations

import sys


_PATCH_PREFIXES = (
    "song_agent.interfaces.api.routes.",
    "song_agent.interfaces.api.runtime_parts.",
)


def propagate_compatibility_patch(name: str, value: object) -> None:
    for module_name, module in tuple(sys.modules.items()):
        if module_name.startswith(_PATCH_PREFIXES) and hasattr(module, name):
            setattr(module, name, value)
