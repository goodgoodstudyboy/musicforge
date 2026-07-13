from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.hashing import integrity_ok, sha256_file
from song_agent.platform.verification.manifest import manifest_file_checks
from song_agent.platform.verification.model import build_check, build_verification_report, has_blocking_failures
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import is_safe_zip_entry, raw_unsafe_entry_names, zip_has_no_trailing_data


def verify_package_envelope(
    zip_path: Path | str,
    spec: PackageSpec,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    del strict
    target = Path(zip_path)
    checks: list[dict[str, Any]] = []
    target_is_file = target.is_file()
    summary: dict[str, Any] = {
        "zip_sha256": sha256_file(target) if target_is_file else "",
        "zip_size_bytes": target.stat().st_size if target_is_file else 0,
        "manifest_hash": None,
    }
    checks.append(build_check(f"{spec.check_prefix}_zip_exists", target_is_file, "Package ZIP exists."))
    if not target_is_file:
        return build_verification_report(package_type=spec.verification_package_type, checks=checks, summary=summary)
    checks.extend(_outer_archive_checks(target, spec))
    if has_blocking_failures(checks):
        return build_verification_report(package_type=spec.verification_package_type, checks=checks, summary=summary)
    try:
        with zipfile.ZipFile(target) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            checks.extend(_entry_structure_checks(infos, names, spec))
            manifest, manifest_checks = _read_and_check_manifest(archive, set(names), spec)
            checks.extend(manifest_checks)
            summary["manifest_hash"] = manifest.get("integrity_hash")
            checks.append(archive_redaction_check(archive, names, check_id=f"{spec.check_prefix}_redaction_scan", suffixes=spec.redaction_suffixes))
            if spec.semantic_verifier and not has_blocking_failures(checks):
                checks.extend(spec.semantic_verifier({"archive": archive, "manifest": manifest, "names": names, "summary": summary}))
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        checks.append(build_check(f"{spec.check_prefix}_zip_readable", False, "Package ZIP is readable.", {"error_type": type(exc).__name__}))
    return build_verification_report(
        package_type=spec.verification_package_type,
        checks=checks,
        summary=summary,
        schema_version=spec.schema_version,
    )


def _outer_archive_checks(target: Path, spec: PackageSpec) -> list[dict[str, Any]]:
    raw_unsafe = raw_unsafe_entry_names(target)
    return [
        build_check(f"{spec.check_prefix}_zip_size", target.stat().st_size <= spec.max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."),
        build_check(f"{spec.check_prefix}_raw_entry_paths_safe", not raw_unsafe, "Raw central-directory entry paths are safe.", {"unsafe": raw_unsafe}),
        build_check(f"{spec.check_prefix}_no_trailing_data", zip_has_no_trailing_data(target), "ZIP has no trailing data."),
    ]


def _entry_structure_checks(infos: list[zipfile.ZipInfo], names: list[str], spec: PackageSpec) -> list[dict[str, Any]]:
    name_set = set(names)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    unsafe = sorted(name for name in names if not is_safe_zip_entry(name))
    nested = sorted(name for name in names if name.lower().endswith(".zip"))
    allowed_nested = {
        name for name in nested
        if name in spec.allowed_nested_entries or any(re.fullmatch(pattern, name) for pattern in spec.allowed_nested_patterns)
    }
    disallowed_nested = nested if spec.nested_zip_policy == "deny" else sorted(set(nested) - allowed_nested)
    pattern_matches = {name for name in names if any(re.fullmatch(pattern, name) for pattern in spec.allowed_entry_patterns)}
    extra = sorted(name_set - set(spec.allowed_entries) - pattern_matches) if spec.allowed_entries or spec.allowed_entry_patterns else []
    missing = list(set(spec.required_entries) - name_set)
    for group in spec.co_required_entry_groups:
        if name_set & set(group):
            missing.extend(set(group) - name_set)
    return [
        build_check(f"{spec.check_prefix}_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
        build_check(f"{spec.check_prefix}_entry_count", len(infos) <= spec.max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
        build_check(f"{spec.check_prefix}_uncompressed_size", sum(info.file_size for info in infos) <= spec.max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
        build_check(f"{spec.check_prefix}_entry_paths_safe", not unsafe, "ZIP entry paths are safe.", {"unsafe": unsafe}),
        build_check(f"{spec.check_prefix}_nested_zip_policy", not disallowed_nested, "Nested ZIP policy is satisfied.", {"disallowed": disallowed_nested}),
        build_check(f"{spec.check_prefix}_allowed_entries", not extra, "ZIP contains only PackageSpec entries.", {"extra": extra}),
        build_check(f"{spec.check_prefix}_required_entries", not missing, "ZIP contains required PackageSpec entries.", {"missing": sorted(set(missing))}),
    ]


def _read_and_check_manifest(
    archive: zipfile.ZipFile,
    name_set: set[str],
    spec: PackageSpec,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []
    if spec.manifest_entry not in name_set:
        if spec.manifest_entry:
            checks.append(build_check(f"{spec.check_prefix}_manifest_required", False, "Manifest entry exists."))
        return manifest, checks
    try:
        value = json.loads(archive.read(spec.manifest_entry).decode("utf-8"))
        manifest = value if isinstance(value, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        checks.append(build_check(f"{spec.check_prefix}_manifest_json", False, "Manifest is valid JSON.", {"error_type": type(exc).__name__}))
    checks.extend([
        build_check(f"{spec.check_prefix}_manifest_integrity", integrity_ok(manifest), "Manifest integrity hash is valid."),
        build_check(f"{spec.check_prefix}_package_type", manifest.get("package_type") == spec.package_type, "Manifest package type matches PackageSpec."),
    ])
    files = manifest.get("files")
    checks.append(
        build_check(
            f"{spec.check_prefix}_manifest_files_required",
            isinstance(files, list),
            "Manifest contains a files array that binds every package entry.",
        )
    )
    if isinstance(files, list):
        checks.extend(manifest_file_checks(
            archive,
            manifest,
            expected_files=name_set - {spec.manifest_entry},
            check_prefix=f"{spec.check_prefix}_manifest",
        ))
    return manifest, checks
