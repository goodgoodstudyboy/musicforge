from __future__ import annotations

import json
import stat
import zipfile
from pathlib import Path

import pytest

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.external_bindings import evidence_identity_checks
from song_agent.platform.verification.hashing import integrity_hash, sha256_bytes
from song_agent.platform.verification.history import history_chain_checks


ACTIVE_V12_VERIFIERS = (
    "unified_release_program_verifier.py",
    "unified_release_program_operations_verifier.py",
    "unified_release_program_handoff_verifier.py",
    "unified_release_program_vault_verifier.py",
    "unified_release_program_vault_operations_verifier.py",
    "unified_release_program_continuity_verifier.py",
    "unified_release_program_continuity_distribution_verifier.py",
    "unified_release_program_continuity_acceptance_verifier.py",
    "unified_release_program_continuity_acceptance_change_verifier.py",
    "unified_release_program_continuity_command_center_verifier.py",
    "unified_release_program_continuity_command_center_signoff_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_change_verifier.py",
)


def _spec(*, nested: bool = False) -> PackageSpec:
    return PackageSpec(
        package_type="musicforge_test_kernel_package",
        verification_package_type="musicforge_test_kernel_verification",
        check_prefix="kernel_test",
        required_entries=frozenset({"manifest.json", "data.json", "README.txt"}),
        optional_entries=frozenset({"packages/allowed.zip"}) if nested else frozenset(),
        nested_zip_policy="allowlisted" if nested else "deny",
        allowed_nested_entries=frozenset({"packages/allowed.zip"}) if nested else frozenset(),
    )


def _write_package(path: Path, entries: dict[str, bytes] | None = None, *, package_type: str = "musicforge_test_kernel_package") -> Path:
    payload = entries or {"data.json": b'{"ok":true}', "README.txt": b"kernel fixture\n"}
    manifest = {
        "schema_version": 1,
        "package_type": package_type,
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(payload.items())
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in payload.items():
            archive.writestr(name, data)
    return path


def _status(path: Path, spec: PackageSpec | None = None) -> tuple[str, set[str]]:
    report = verify_package_envelope(path, spec or _spec(), strict=True)
    assert report["integrity_hash"] == integrity_hash(report)
    return str(report["status"]), set(report["blockers"])


def test_verification_kernel_happy_package_and_report_envelope(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "happy.zip")

    status, blockers = _status(package)

    assert status == "passed"
    assert blockers == set()


def test_verification_kernel_missing_or_directory_path_fails_closed(tmp_path: Path) -> None:
    missing_status, missing_blockers = _status(tmp_path / "missing.zip")
    directory = tmp_path / "directory.zip"
    directory.mkdir()
    directory_status, directory_blockers = _status(directory)

    assert missing_status == "failed"
    assert directory_status == "failed"
    assert "kernel_test_zip_exists" in missing_blockers
    assert "kernel_test_zip_exists" in directory_blockers


@pytest.mark.parametrize(
    ("name", "entries", "expected_check"),
    [
        ("missing", {"README.txt": b"readme"}, "kernel_test_required_entries"),
        ("declared-extra", {"data.json": b"{}", "README.txt": b"readme", "UNTRUSTED.txt": b"bad"}, "kernel_test_allowed_entries"),
        ("dangerous", {"data.json": b"{}", "README.txt": b"readme", "../escape.txt": b"bad"}, "kernel_test_raw_entry_paths_safe"),
        ("musicforge", {"data.json": b"{}", "README.txt": b"readme", ".MusicForge/private.json": b"{}"}, "kernel_test_raw_entry_paths_safe"),
        ("nested", {"data.json": b"{}", "README.txt": b"readme", "extra.zip": b"PK"}, "kernel_test_nested_zip_policy"),
        ("redaction", {"data.json": b"{}", "README.txt": b"api_key=secret-value"}, "kernel_test_redaction_scan"),
    ],
)
def test_verification_kernel_attack_matrix(
    tmp_path: Path,
    name: str,
    entries: dict[str, bytes],
    expected_check: str,
) -> None:
    package = _write_package(tmp_path / f"{name}.zip", entries)

    status, blockers = _status(package)

    assert status == "failed"
    assert expected_check in blockers


def test_verification_kernel_rejects_duplicate_raw_backslash_trailing_and_spoof(tmp_path: Path) -> None:
    missing_file_index = tmp_path / "missing-file-index.zip"
    manifest_without_files = {
        "schema_version": 1,
        "package_type": "musicforge_test_kernel_package",
    }
    manifest_without_files["integrity_hash"] = integrity_hash(manifest_without_files)
    with zipfile.ZipFile(missing_file_index, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest_without_files, sort_keys=True))
        archive.writestr("data.json", b"{}")
        archive.writestr("README.txt", b"readme")
    assert "kernel_test_manifest_files_required" in _status(missing_file_index)[1]

    duplicate_manifest_rows = tmp_path / "duplicate-manifest-rows.zip"
    data = b"{}"
    readme = b"readme"
    manifest = {
        "schema_version": 1,
        "package_type": "musicforge_test_kernel_package",
        "files": [
            {"path": "data.json", "sha256": sha256_bytes(data)},
            {"path": "data.json", "sha256": sha256_bytes(data)},
            {"path": "README.txt", "sha256": sha256_bytes(readme)},
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(duplicate_manifest_rows, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("data.json", data)
        archive.writestr("README.txt", readme)
    assert "kernel_test_manifest_files_unique" in _status(duplicate_manifest_rows)[1]

    duplicate = _write_package(tmp_path / "duplicate.zip")
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(duplicate, "a") as archive:
            archive.writestr("data.json", b"{}")
    assert "kernel_test_no_duplicate_entries" in _status(duplicate)[1]

    raw_backslash = _write_package(tmp_path / "backslash.zip")
    raw_backslash.write_bytes(raw_backslash.read_bytes().replace(b"README.txt", b"README\\txt"))
    assert "kernel_test_raw_entry_paths_safe" in _status(raw_backslash)[1]

    trailing = _write_package(tmp_path / "trailing.zip")
    with trailing.open("ab") as stream:
        stream.write(b"tamper")
    assert "kernel_test_no_trailing_data" in _status(trailing)[1]

    spoof = _write_package(tmp_path / "spoof.zip")
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(spoof, "a") as archive:
            archive.writestr("data.json", b'{"forged":true}')
    status, blockers = _status(spoof)
    assert status == "failed"
    assert {"kernel_test_no_duplicate_entries", "kernel_test_manifest_file_data_json_hash"} & blockers

    wrong_type = _write_package(tmp_path / "wrong-type.zip", package_type="wrong_package")
    assert "kernel_test_package_type" in _status(wrong_type)[1]


@pytest.mark.parametrize("file_type", [stat.S_IFDIR, stat.S_IFLNK, stat.S_IFIFO])
def test_verification_kernel_rejects_non_regular_entries_in_all_modes(tmp_path: Path, file_type: int) -> None:
    package = tmp_path / f"non-regular-{file_type}.zip"
    data = b'{}'
    readme = b"kernel fixture\n"
    manifest = {
        "schema_version": 1,
        "package_type": "musicforge_test_kernel_package",
        "files": [
            {"path": "data.json", "sha256": sha256_bytes(data), "size_bytes": len(data)},
            {"path": "README.txt", "sha256": sha256_bytes(readme), "size_bytes": len(readme)},
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        info = zipfile.ZipInfo("data.json")
        info.create_system = 3
        info.external_attr = (file_type | 0o644) << 16
        archive.writestr(info, data)
        archive.writestr("README.txt", readme)

    strict = verify_package_envelope(package, _spec(), strict=True)
    relaxed = verify_package_envelope(package, _spec(), strict=False)

    assert strict["status"] == "failed"
    assert relaxed["status"] == "failed"
    assert "kernel_test_entry_types_regular" in strict["blockers"]
    assert "kernel_test_entry_types_regular" in relaxed["blockers"]


def test_verification_kernel_requires_and_checks_manifest_size(tmp_path: Path) -> None:
    package = tmp_path / "wrong-size.zip"
    data = b'{}'
    readme = b"readme"
    manifest = {
        "schema_version": 1,
        "package_type": "musicforge_test_kernel_package",
        "files": [
            {"path": "data.json", "sha256": sha256_bytes(data), "size_bytes": len(data) + 1},
            {"path": "README.txt", "sha256": sha256_bytes(readme)},
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("data.json", data)
        archive.writestr("README.txt", readme)

    status, blockers = _status(package)

    assert status == "failed"
    assert "kernel_test_manifest_file_data_json_size" in blockers
    assert "kernel_test_manifest_file_README_txt_fields" in blockers


def test_verification_kernel_nested_allowlist_history_and_evidence_identity(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path / "nested.zip",
        {
            "data.json": b"{}",
            "README.txt": b"readme",
            "packages/allowed.zip": b"PK fixture",
        },
    )
    assert _status(package, _spec(nested=True))[0] == "passed"

    first = {"event_type": "created", "previous_event_hash": ""}
    first["payload_hash"] = integrity_hash(first)
    first["event_hash"] = integrity_hash({key: value for key, value in first.items() if key != "event_hash"})
    assert all(row["status"] == "passed" for row in history_chain_checks([first], check_prefix="history"))

    expected = EvidenceRef(component_type="vault", component_id="vault-1", evidence_type="archive", generation=1, zip_sha256="a" * 64)
    actual = EvidenceRef.from_dict(expected.to_dict())
    assert all(row["status"] == "passed" for row in evidence_identity_checks([expected], [actual], check_prefix="evidence"))
    forged = EvidenceRef.from_dict({**expected.to_dict(), "zip_sha256": "b" * 64})
    assert any(row["status"] == "failed" for row in evidence_identity_checks([expected], [forged], check_prefix="evidence"))
    duplicate_checks = evidence_identity_checks([expected], [actual, actual], check_prefix="evidence")
    assert next(row for row in duplicate_checks if row["check_id"] == "evidence_actual_identity_unique")["status"] == "failed"


def test_all_active_v12_verifiers_use_kernel_without_duplicate_security_helpers() -> None:
    root = Path(__file__).resolve().parents[1] / "song_agent" / "domains" / "program"
    forbidden = (
        "def _raw_zip_entry_names(",
        "def _is_safe_entry(",
        "def _is_safe_zip_entry(",
        "def _zip_has_no_trailing_data(",
        "def _sha256_path(",
        "def _sha256_file(",
    )
    for filename in ACTIVE_V12_VERIFIERS:
        source = (root / filename).read_text(encoding="utf-8")
        assert "PackageSpec" in source, filename
        assert "verify_package_envelope" in source, filename
        assert "build_verification_report" in source, filename
        assert not any(definition in source for definition in forbidden), filename
