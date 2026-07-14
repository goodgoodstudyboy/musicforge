from __future__ import annotations

from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_verification_text
from song_agent.redaction import sanitize_sensitive_text


def test_sensitive_text_redacts_posix_temporary_paths_without_redacting_routes() -> None:
    rendered = sanitize_sensitive_text(
        "failed at /tmp/mf-123/test-case/private.wav; retry /api/releases/release-001"
    )

    assert "/tmp/mf-123" not in rendered
    assert "[REDACTED_LOCAL_PATH]" in rendered
    assert "/api/releases/release-001" in rendered
    assert sanitize_verification_text(
        "failed at /tmp/mf-123/test-case/private.wav; retry /api/releases/release-001"
    ) == rendered


def test_verification_integrity_is_stable_when_posix_temp_root_is_relocated() -> None:
    source = {"package_type": "example", "local_file": "/tmp/source/evidence.zip"}
    source["integrity_hash"] = integrity_hash(source)
    relocated = {**source, "local_file": "/tmp/checkout/evidence.zip"}

    assert integrity_ok(relocated)
