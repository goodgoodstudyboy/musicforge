from __future__ import annotations

import json
import tempfile
import warnings
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import integrity_hash, sha256_bytes


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


def run_verification_kernel_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        spec = PackageSpec(
            package_type="musicforge_release_check_verification_kernel",
            verification_package_type="musicforge_release_check_verification_kernel_report",
            check_prefix="v1215_kernel",
            required_entries=frozenset({"manifest.json", "data.json", "README.txt"}),
        )
        with tempfile.TemporaryDirectory(prefix="mf-v1215-verification-kernel-") as temp:
            base = Path(temp)
            valid = {"data.json": b'{"ok":true}', "README.txt": b"verification kernel\n"}
            happy_path = _write_package(base / "happy.zip", valid, spec.package_type)
            reports = {
                "happy": _verify(happy_path, spec),
                "missing_file_index": _verify(
                    _write_package_without_file_index(base / "missing-file-index.zip", valid, spec.package_type),
                    spec,
                ),
                "missing": _verify(_write_package(base / "missing.zip", {"README.txt": b"missing data"}, spec.package_type), spec),
                "declared_extra": _verify(_write_package(base / "extra.zip", {**valid, "UNTRUSTED.txt": b"extra"}, spec.package_type), spec),
                "dangerous_path": _verify(_write_package(base / "dangerous.zip", {**valid, "../escape.txt": b"escape"}, spec.package_type), spec),
                "musicforge": _verify(_write_package(base / "musicforge.zip", {**valid, ".MusicForge/private.json": b"{}"}, spec.package_type), spec),
                "nested_zip": _verify(_write_package(base / "nested.zip", {**valid, "unexpected.zip": b"PK"}, spec.package_type), spec),
                "redaction": _verify(_write_package(base / "redaction.zip", {"data.json": b"{}", "README.txt": b"api_key=secret-value"}, spec.package_type), spec),
                "wrong_package_type": _verify(_write_package(base / "wrong-type.zip", valid, "wrong_package"), spec),
            }
            duplicate_path = _write_package(base / "duplicate.zip", valid, spec.package_type)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate_path, "a") as archive:
                    archive.writestr("data.json", b"{}")
            reports["duplicate"] = _verify(duplicate_path, spec)

            raw_backslash_path = _write_package(base / "raw-backslash.zip", valid, spec.package_type)
            raw_backslash_path.write_bytes(raw_backslash_path.read_bytes().replace(b"README.txt", b"README\\txt"))
            reports["raw_backslash"] = _verify(raw_backslash_path, spec)

            trailing_path = _write_package(base / "trailing.zip", valid, spec.package_type)
            trailing_path.write_bytes(trailing_path.read_bytes() + b"tamper")
            reports["trailing_data"] = _verify(trailing_path, spec)

            manifest_spoof_path = _write_package(base / "manifest-spoof.zip", valid, spec.package_type)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(manifest_spoof_path, "a") as archive:
                    archive.writestr("data.json", b'{"forged":true}')
            reports["manifest_spoof"] = _verify(manifest_spoof_path, spec)

        source_root = Path(__file__).resolve().parent
        migrated = all(
            "PackageSpec" in (source_root / filename).read_text(encoding="utf-8")
            and "verify_package_envelope" in (source_root / filename).read_text(encoding="utf-8")
            for filename in ACTIVE_V12_VERIFIERS
        )
        statuses = {name: str(report.get("status")) for name, report in reports.items()}
        ok = statuses["happy"] == "passed" and all(
            status == "failed" for name, status in statuses.items() if name != "happy"
        ) and migrated
        return ok, "v12.15 verification kernel: " + ", ".join(
            [*(f"{name}={status}" for name, status in statuses.items()), f"active_verifiers_migrated={migrated}"]
        )
    except Exception as exc:
        return False, f"v12.15 Verification Kernel smoke failed: {exc}"


def _write_package(path: Path, entries: dict[str, bytes], package_type: str) -> Path:
    manifest = {
        "schema_version": 1,
        "package_type": package_type,
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(entries.items())
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _write_package_without_file_index(path: Path, entries: dict[str, bytes], package_type: str) -> Path:
    manifest = {"schema_version": 1, "package_type": package_type}
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _verify(path: Path, spec: PackageSpec) -> dict[str, Any]:
    return verify_package_envelope(path, spec, strict=True)
