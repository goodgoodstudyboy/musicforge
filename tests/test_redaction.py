from __future__ import annotations

from song_agent.redaction import sanitize_sensitive_text


def test_sensitive_text_redacts_posix_temporary_paths_without_redacting_routes() -> None:
    rendered = sanitize_sensitive_text(
        "failed at /tmp/mf-123/test-case/private.wav; retry /api/releases/release-001"
    )

    assert "/tmp/mf-123" not in rendered
    assert "[REDACTED_LOCAL_PATH]" in rendered
    assert "/api/releases/release-001" in rendered
