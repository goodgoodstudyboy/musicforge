"""Compatibility facade for the shared redaction implementation."""

from song_agent.platform.verification.redaction import Any, DEFAULT_BLOCKED_METADATA_KEYS, Iterable, SENSITIVE_BYTE_PATTERNS, SENSITIVE_VALUE_PATTERNS, _strip_unsafe_control_chars, annotations, archive_redaction_check, build_check, re, sanitize_metadata, sanitize_sensitive_text, zipfile

__all__ = ('Any', 'DEFAULT_BLOCKED_METADATA_KEYS', 'Iterable', 'SENSITIVE_BYTE_PATTERNS', 'SENSITIVE_VALUE_PATTERNS', '_strip_unsafe_control_chars', 'annotations', 'archive_redaction_check', 'build_check', 're', 'sanitize_metadata', 'sanitize_sensitive_text', 'zipfile')
