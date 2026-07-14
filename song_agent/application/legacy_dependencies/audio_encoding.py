"""Single active import boundary for a pre-v13 compatibility module."""

import song_agent.audio_encoding as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith('__')})

__all__ = tuple(name for name in globals() if not name.startswith('__'))
