from __future__ import annotations

import io
import zipfile

from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.platform.verification.redaction import archive_redaction_check
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


def test_sensitive_text_redacts_posix_paths_embedded_in_json() -> None:
    source = (
        '{"zip_path":"/tmp/mf-123/evidence.zip",'
        '"home":"/home/runner/work/report.json",'
        '"wsl":"/mnt/c/Users/demo/work/evidence.zip"}'
    )

    for sanitizer in (sanitize_sensitive_text, sanitize_verification_text):
        rendered = sanitizer(source)
        assert "/tmp/mf-123" not in rendered
        assert "/home/runner" not in rendered
        assert "/mnt/c/Users/demo" not in rendered
        assert rendered.count("[REDACTED_LOCAL_PATH]") == 3


def test_archive_redaction_rejects_posix_paths_embedded_in_json() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("report.json", b'{"zip_path":"/tmp/mf-123/evidence.zip"}')
    buffer.seek(0)

    with zipfile.ZipFile(buffer) as archive:
        check = archive_redaction_check(archive, archive.namelist(), check_id="test_redaction")

    assert check["status"] == "failed"
    assert check["details"]["offenders"] == ["report.json"]


def test_archive_redaction_rejects_wsl_mount_paths() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("report.json", b'{"zip_path":"/mnt/c/Users/demo/work/evidence.zip"}')
    buffer.seek(0)

    with zipfile.ZipFile(buffer) as archive:
        check = archive_redaction_check(archive, archive.namelist(), check_id="test_redaction")

    assert check["status"] == "failed"
    assert check["details"]["offenders"] == ["report.json"]


def test_verification_integrity_is_stable_when_posix_temp_root_is_relocated() -> None:
    source = {"package_type": "example", "local_file": "/tmp/source/evidence.zip"}
    source["integrity_hash"] = integrity_hash(source)
    relocated = {**source, "local_file": "/tmp/checkout/evidence.zip"}

    assert integrity_ok(relocated)
