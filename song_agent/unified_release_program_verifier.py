"""Compatibility import for the canonical Program implementation."""

from song_agent.domains.program import unified_release_program_verifier as _implementation

globals().update(
    {
        name: getattr(_implementation, name)
        for name in dir(_implementation)
        if not name.startswith("__")
    }
)
__all__ = tuple(name for name in globals() if not name.startswith("__"))
