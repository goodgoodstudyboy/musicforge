"""MusicForge bounded contexts exposed to the application layer."""

from typing import Any, TypeAlias

from song_agent.domains.registry import BOUNDED_CONTEXTS, BoundedContextSpec


# Private migration types for bounded contexts scheduled after Wave 1. They
# preserve the pre-v14.4 domain contract without leaking dynamic JSON back into
# platform, application, or interface APIs.
_ImplementationValue: TypeAlias = Any
_ImplementationDocument: TypeAlias = dict[str, _ImplementationValue]

__all__ = ["BOUNDED_CONTEXTS", "BoundedContextSpec"]
