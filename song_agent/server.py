from __future__ import annotations
import sys
from types import ModuleType
from song_agent.interfaces.api.patching import propagate_compatibility_patch
from song_agent.interfaces.api import runtime as _runtime
from song_agent.interfaces.api.runtime import *
from song_agent.interfaces.api.server import MusicForgeHTTPServer, MusicForgeHandler, api_inventory, create_server, serve
from song_agent.interfaces.api.routes import creation as _routes_creation
from song_agent.interfaces.api.routes import studio as _routes_studio
from song_agent.interfaces.api.routes import quality as _routes_quality
from song_agent.interfaces.api.routes import delivery as _routes_delivery
from song_agent.interfaces.api.routes import trust as _routes_trust
from song_agent.interfaces.api.routes import program as _routes_program
from song_agent.interfaces.api.routes import maintenance as _routes_maintenance


_PATCH_TARGETS = (_runtime, _routes_creation, _routes_studio, _routes_quality, _routes_delivery, _routes_trust, _routes_program, _routes_maintenance)


class _CompatibilityModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for module in _PATCH_TARGETS:
            if hasattr(module, name):
                setattr(module, name, value)
        propagate_compatibility_patch(name, value)


sys.modules[__name__].__class__ = _CompatibilityModule
__all__ = [name for name in globals() if not name.startswith("__")]
