"""MusicForge bounded contexts exposed to the application layer."""

from song_agent.domains.registry import BOUNDED_CONTEXTS, BoundedContextSpec

__all__ = ["BOUNDED_CONTEXTS", "BoundedContextSpec"]
