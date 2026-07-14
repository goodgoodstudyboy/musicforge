"""Application import boundary for the quality acceptance-diff domain."""

import song_agent.domains.quality.acceptance_diff as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith('__')})

__all__ = tuple(name for name in globals() if not name.startswith('__'))
