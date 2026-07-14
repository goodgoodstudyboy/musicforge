from __future__ import annotations

import io
import json
import stat
import warnings
import zipfile
from pathlib import Path
from typing import Callable

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import integrity_hash, sha256_bytes
from song_agent.platform.verification.registry import VerifierCapability, active_verifier_registry


def run_active_verifier_attack_corpus(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    rows = [_run_capability(root, capability) for capability in active_verifier_registry.all()]
    return {
        "schema_version": 1,
        "status": "passed" if all(row["status"] == "passed" for row in rows) else "failed",
        "capability_count": len(rows),
        "rows": rows,
    }


def _run_capability(root: Path, capability: VerifierCapability) -> dict[str, object]:
    spec = capability.package_spec()
    directory = root / capability.component_type
    directory.mkdir(parents=True, exist_ok=True)
    baseline = directory / "baseline.zip"
    payloads = _baseline_payloads(spec)
    _write_package(baseline, spec, payloads)
    results: dict[str, bool] = {
        "baseline": verify_package_envelope(baseline, spec, strict=True)["status"] == "passed",
    }
    attacks: tuple[tuple[str, Callable[[Path, PackageSpec, dict[str, bytes]], None]], ...] = (
        ("declared_extra", _declared_extra),
        ("duplicate", _duplicate),
        ("dangerous_path", _dangerous_path),
        ("raw_backslash", _raw_backslash),
        ("directory_entry", _directory_entry),
        ("symlink_entry", _symlink_entry),
        ("trailing_data", _trailing_data),
        ("manifest_spoof", _manifest_spoof),
        ("redaction", _redaction),
        ("nested_zip", _nested_zip),
    )
    for name, attack in attacks:
        target = directory / f"{name}.zip"
        attack(target, spec, payloads)
        results[name] = verify_package_envelope(target, spec, strict=True)["status"] == "failed"
    results["wrong_package_type"] = results["manifest_spoof"]
    results["full_resign_external_guard"] = capability.external_proofs_adopted()
    return {
        "component_type": capability.component_type,
        "package_type": spec.package_type,
        "status": "passed" if all(results.values()) else "failed",
        "results": results,
    }


def _baseline_payloads(spec: PackageSpec) -> dict[str, bytes]:
    nested = spec.allowed_nested_entries | {
        entry for entry in spec.required_entries if entry.lower().endswith(".zip")
    }
    return {
        name: _empty_zip() if name in nested else b"{}\n" if name.endswith((".json", ".jsonl")) else b"evidence\n"
        for name in sorted(spec.required_entries - {spec.manifest_entry})
    }


def _write_package(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    manifest = {
        "schema_version": 1,
        "package_type": spec.package_type,
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(payloads.items())
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted({**payloads, spec.manifest_entry: _json_bytes(manifest)}.items()):
            archive.writestr(name, data)


def _declared_extra(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, {**payloads, "UNTRUSTED.txt": b"untrusted\n"})


def _duplicate(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, payloads)
    name = next(iter(payloads))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr(name, b"duplicate\n")


def _dangerous_path(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, {**payloads, "../escape.txt": b"escape\n"})


def _raw_backslash(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, {**payloads, "docs\\unsafe.txt": b"unsafe\n"})


def _directory_entry(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, payloads)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("directory/", b"")


def _symlink_entry(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, payloads)
    info = zipfile.ZipInfo("symlink")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(info, b"target")


def _trailing_data(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, payloads)
    path.write_bytes(path.read_bytes() + b"tamper")


def _manifest_spoof(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    forged = PackageSpec(
        package_type="forged_package_type",
        verification_package_type=spec.verification_package_type,
        check_prefix=spec.check_prefix,
        required_entries=spec.required_entries,
        optional_entries=spec.optional_entries,
        allowed_entry_patterns=spec.allowed_entry_patterns,
        nested_zip_policy=spec.nested_zip_policy,
        allowed_nested_entries=spec.allowed_nested_entries,
        allowed_nested_patterns=spec.allowed_nested_patterns,
        manifest_entry=spec.manifest_entry,
    )
    _write_package(path, forged, payloads)


def _redaction(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    target = next((name for name in payloads if name.endswith((".json", ".jsonl", ".txt", ".md"))), next(iter(payloads)))
    secret_payload = _json_bytes({"api" + "_key": "s" + "k-not-allowed-12345678"})
    _write_package(path, spec, {**payloads, target: secret_payload})


def _nested_zip(path: Path, spec: PackageSpec, payloads: dict[str, bytes]) -> None:
    _write_package(path, spec, {**payloads, "packages/unlisted.zip": _empty_zip()})


def _empty_zip() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "nested\n")
    return stream.getvalue()


def _json_bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
