"""Compatibility exports for the Verification Kernel redaction helpers."""

from song_agent.platform.verification.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text

__all__ = (
    "DEFAULT_BLOCKED_METADATA_KEYS",
    "SENSITIVE_VALUE_PATTERNS",
    "sanitize_metadata",
    "sanitize_sensitive_text",
)
