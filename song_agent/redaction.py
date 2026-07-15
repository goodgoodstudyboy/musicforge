"""Compatibility facade for song_agent.domains.creation.redaction."""

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text

__all__ = ('DEFAULT_BLOCKED_METADATA_KEYS', 'SENSITIVE_VALUE_PATTERNS', 'sanitize_metadata', 'sanitize_sensitive_text')
