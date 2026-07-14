from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_hash as _integrity_hash,
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
    sha256_or_integrity as _sha256_or_integrity,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_release_program_vault_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_package,
)


UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE = "musicforge_unified_release_program_vault_operations_archive"
UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_vault_operations_verification"
UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "vault-operations-report.json",
    "registry.json",
    "policy.json",
    "latest-review-report.json",
    "rotation-plan-summary.json",
    "transfer-report.json",
    "vault-operations-signoff.json",
    "vault-operations-signoff-binding-summary.json",
    "vault-operations-history.jsonl",
    "packages/current-vault.zip",
    "proofs/current-vault-anchor.json",
    "proofs/current-vault-verification-report.json",
    "docs/recipient-guide.md",
    "docs/replica-checklist.json",
    "README.txt",
}

def verify_unified_release_program_vault_operations_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_signed: bool = False,
    require_current_vault: bool = False,
    signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 1024,
    max_uncompressed_size_mb: int = 4096,
    max_entry_count: int = 5000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpvo_kernel",
                required_entries=frozenset(REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                nested_zip_policy="allowlisted",
                allowed_nested_entries=frozenset({"packages/current-vault.zip"}),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpvo_zip_exists", False, "Vault Operations Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpvo_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpvo_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after the end of central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.extend(
                [
                    _check("urpvo_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpvo_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpvo_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpvo_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpvo_allowed_entries", not extra, "Vault Operations Archive contains only fixed entries.", {"extra": extra}),
                    _check("urpvo_required_entries", not missing, "Vault Operations Archive contains required entries.", {"missing": missing}),
                ]
            )
            if _has_blocking_failures(checks):
                if deep:
                    checks.append(_check("urpvo_deep_preflight", False, "Deep verification is skipped when ZIP structure checks fail."))
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "vault-operations-report.json")
            registry = _read_json_entry(archive, "registry.json")
            policy = _read_json_entry(archive, "policy.json")
            review = _read_json_entry(archive, "latest-review-report.json")
            rotation = _read_json_entry(archive, "rotation-plan-summary.json")
            transfer = _read_json_entry(archive, "transfer-report.json")
            signoff = _read_json_entry(archive, "vault-operations-signoff.json")
            binding = _read_json_entry(archive, "vault-operations-signoff-binding-summary.json")
            checklist = _read_json_entry(archive, "docs/replica-checklist.json")
            anchor = _read_json_entry(archive, "proofs/current-vault-anchor.json")
            vault_verification = _read_json_entry(archive, "proofs/current-vault-verification-report.json")
            history = _parse_jsonl(archive.read("vault-operations-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "program_id": manifest.get("program_id") or report.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "operations_status": report.get("status"),
                    "registry_status": registry.get("status"),
                    "latest_review_status": review.get("status"),
                    "transfer_status": transfer.get("status"),
                    "signed": signoff.get("status") == "signed",
                }
            )
            checks.extend(
                [
                    _check("urpvo_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpvo_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, "Manifest schema version is supported."),
                    _check("urpvo_registry_package_type", registry.get("package_type") == "musicforge_unified_release_program_vault_registry", "Registry package type is valid."),
                    _check("urpvo_policy_package_type", policy.get("package_type") == "musicforge_unified_release_program_vault_custody_policy", "Policy package type is valid."),
                    _check("urpvo_review_package_type", review.get("package_type") == "musicforge_unified_release_program_vault_custody_review", "Review package type is valid."),
                    _check("urpvo_transfer_package_type", transfer.get("package_type") == "musicforge_unified_release_program_vault_transfer_report", "Transfer report package type is valid."),
                    _check("urpvo_signoff_package_type", signoff.get("package_type") == "musicforge_unified_release_program_vault_operations_signoff", "Signoff package type is valid."),
                    _check("urpvo_signoff_binding_package_type", binding.get("package_type") == "musicforge_unified_release_program_vault_operations_signoff_binding_summary", "Signoff binding package type is valid."),
                    _check("urpvo_vault_anchor_package_type", anchor.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, "Vault anchor package type is valid."),
                    _check("urpvo_vault_verification_package_type", vault_verification.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, "Vault verification package type is valid."),
                ]
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            for check_id, doc in (
                ("urpvo_manifest_integrity", manifest),
                ("urpvo_report_integrity", report),
                ("urpvo_registry_integrity", registry),
                ("urpvo_policy_integrity", policy),
                ("urpvo_review_integrity", review),
                ("urpvo_rotation_integrity", rotation),
                ("urpvo_transfer_integrity", transfer),
                ("urpvo_signoff_integrity", signoff),
                ("urpvo_signoff_binding_integrity", binding),
                ("urpvo_checklist_integrity", checklist),
                ("urpvo_vault_anchor_integrity", anchor),
                ("urpvo_vault_verification_integrity", vault_verification),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_history_checks(history))
            checks.extend(_binding_checks(manifest, report, registry, policy, review, rotation, transfer, signoff, binding, history, anchor, vault_verification))
            checks.extend(_external_binding_checks(signoff_binding_path, binding, require=require_signed))
            checks.extend(_current_vault_checks(archive, registry, binding, anchor, vault_verification, require=require_current_vault or deep))
            if deep:
                if _has_blocking_failures(checks):
                    checks.append(_check("urpvo_deep_preflight", False, "Deep Vault verification is skipped when archive checks fail."))
                else:
                    checks.extend(_deep_vault_checks(archive))
            elif strict:
                checks.append(_check("urpvo_deep_verification_requested", True, "Deep verification was not requested.", severity="warning"))
            if require_signed:
                checks.append(_check("urpvo_require_signed", signoff.get("status") == "signed" and binding.get("status") == "signed", "Vault Operations Archive is signed."))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpvo_zip_readable", False, "Vault Operations Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_vault_operations_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_vault_operations_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    file_paths = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    zip_meta = manifest.get("zip") if isinstance(manifest.get("zip"), dict) else {}
    checks.extend(
        [
            _check("urpvo_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed archive entries.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
            _check("urpvo_manifest_entries_exact", name_set == REQUIRED_ENTRIES, "ZIP entries match fixed archive entries.", {"missing": sorted(REQUIRED_ENTRIES - name_set), "extra": sorted(name_set - REQUIRED_ENTRIES)}),
            _check("urpvo_manifest_zip_filename", zip_meta.get("filename") == "unified-release-program-vault-operations-archive.zip", "Manifest ZIP filename is canonical."),
            _check("urpvo_manifest_zip_entries", sorted(zip_meta.get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory entries."),
            _check("urpvo_manifest_zip_entry_count", int(zip_meta.get("entry_count") or -1) == len(name_set), "Manifest ZIP entry count matches central directory."),
            _check("urpvo_manifest_zip_no_self_hash", "sha256" not in zip_meta and "size_bytes" not in zip_meta, "Manifest ZIP metadata does not contain an impossible self-hash or self-size."),
        ]
    )
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in archive.namelist():
            checks.append(_check(f"urpvo_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP."))
            continue
        data = archive.read(rel)
        checks.extend(
            [
                _check(f"urpvo_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."),
                _check(f"urpvo_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."),
            ]
        )
    return checks


def _history_checks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    signoff_events = 0
    for index, event in enumerate(events, start=1):
        prefix = f"urpvo_history_{index:03d}"
        expected_payload = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({**{key: value for key, value in event.items() if key != "event_hash"}, "payload_hash": expected_payload})
        checks.extend(
            [
                _check(f"{prefix}_previous", event.get("previous_event_hash") == previous, "History previous event hash matches."),
                _check(f"{prefix}_payload_hash", event.get("payload_hash") == expected_payload, "History payload hash is valid."),
                _check(f"{prefix}_event_hash", event.get("event_hash") == expected_event, "History event hash is valid."),
            ]
        )
        if event.get("event_type") == "vault_operations_signoff_created":
            signoff_events += 1
        previous = str(event.get("event_hash") or "")
    checks.append(_check("urpvo_history_has_signoff", signoff_events >= 1, "History contains a signoff event."))
    return checks


def _binding_checks(
    manifest: dict[str, Any],
    report: dict[str, Any],
    registry: dict[str, Any],
    policy: dict[str, Any],
    review: dict[str, Any],
    rotation: dict[str, Any],
    transfer: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
    history: list[dict[str, Any]],
    anchor: dict[str, Any],
    vault_verification: dict[str, Any],
) -> list[dict[str, Any]]:
    latest_signoff_event = next((row for row in reversed(history) if row.get("event_type") == "vault_operations_signoff_created"), {})
    current = _current_generation(registry)
    vault = current.get("vault") if isinstance(current.get("vault"), dict) else {}
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    pairs = {
        "report_hash": report.get("integrity_hash"),
        "registry_hash": registry.get("integrity_hash"),
        "policy_hash": policy.get("integrity_hash"),
        "latest_review_hash": review.get("integrity_hash"),
        "rotation_plan_hash": rotation.get("integrity_hash"),
        "transfer_report_hash": transfer.get("integrity_hash"),
        "signoff_hash": signoff.get("integrity_hash"),
        "signoff_binding_hash": binding.get("integrity_hash"),
        "vault_zip_sha256": _entry_sha256_for_current_vault_hash(vault),
        "vault_anchor_hash": anchor.get("integrity_hash"),
        "vault_verification_report_hash": vault_verification.get("integrity_hash"),
    }
    checks = [
        _check("urpvo_registry_current", registry.get("status") == "current" and current.get("status") == "current", "Registry has a current Vault generation."),
        _check("urpvo_report_passed", report.get("status") == "passed", "Vault Operations report passed."),
        _check("urpvo_review_passed", review.get("status") == "passed", "Latest custody review passed."),
        _check("urpvo_transfer_ready", transfer.get("status") == "ready", "Transfer report is ready."),
        _check("urpvo_signoff_status", signoff.get("status") == "signed", "Vault Operations signoff is signed."),
        _check("urpvo_signoff_binding_status", binding.get("status") == "signed", "Vault Operations signoff binding is signed."),
        _check("urpvo_signoff_history_binding", binding.get("latest_history_event_hash") == latest_signoff_event.get("event_hash") and signoff.get("integrity_hash") == latest_signoff_event.get("signoff_hash"), "Signoff binding matches latest history signoff event."),
        _check("urpvo_binding_signoff_fields", all(binding.get(key) == signoff.get(key) for key in ("signed_by", "role", "reason", "signed_at")), "Signoff binding public fields match signoff document."),
        _check("urpvo_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
    ]
    for key, value in pairs.items():
        if key in {"rotation_plan_hash"}:
            checks.append(_check(f"urpvo_manifest_source_{key}", source.get(key) == value, f"Manifest source {key} matches document."))
            continue
        checks.append(_check(f"urpvo_manifest_source_{key}", source.get(key) == value, f"Manifest source {key} matches document."))
        if key in {"report_hash", "registry_hash", "policy_hash", "latest_review_hash", "transfer_report_hash", "signoff_hash", "vault_anchor_hash", "vault_verification_report_hash", "vault_zip_sha256"}:
            checks.append(_check(f"urpvo_binding_{key}", binding.get(key) == value, f"Signoff binding {key} matches document."))
    checks.extend(
        [
            _check("urpvo_registry_vault_anchor_hash", vault.get("vault_anchor_hash") == anchor.get("integrity_hash"), "Registry binds current Vault anchor hash."),
            _check("urpvo_registry_vault_verification_hash", vault.get("vault_verification_report_hash") == vault_verification.get("integrity_hash"), "Registry binds current Vault verification report."),
            _check("urpvo_vault_anchor_verification_status", vault_verification.get("status") == "passed", "Current Vault verification report passed."),
            _check("urpvo_vault_anchor_zip_sha256", anchor.get("vault_zip_sha256") == vault.get("vault_zip_sha256"), "Vault anchor and registry bind same Vault ZIP hash."),
            _check("urpvo_vault_anchor_manifest_hash", anchor.get("vault_manifest_hash") == vault.get("vault_manifest_hash") == vault_verification.get("manifest_hash"), "Vault anchor, registry, and verification bind same manifest."),
        ]
    )
    return checks


def _external_binding_checks(path: Path | str | None, binding: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not path:
        return [_check("urpvo_external_signoff_binding_required", not require, "External signoff binding is present when required.")]
    binding_path = Path(path)
    checks = [_check("urpvo_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External signoff binding exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = read_json(binding_path)
    checks.extend(
        [
            _check("urpvo_external_signoff_binding_integrity", _integrity_ok(external), "External signoff binding integrity is valid."),
            _check("urpvo_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External signoff binding matches archive binding."),
            _check("urpvo_external_signoff_binding_payload", external == binding, "External signoff binding content matches archive binding."),
        ]
    )
    return checks


def _current_vault_checks(archive: zipfile.ZipFile, registry: dict[str, Any], binding: dict[str, Any], anchor: dict[str, Any], vault_verification: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    data = archive.read("packages/current-vault.zip")
    current = _current_generation(registry)
    vault = current.get("vault") if isinstance(current.get("vault"), dict) else {}
    checks = [
        _check("urpvo_current_vault_zip_sha256", _sha256_bytes(data) == vault.get("vault_zip_sha256") == binding.get("vault_zip_sha256") == anchor.get("vault_zip_sha256") == vault_verification.get("zip_sha256"), "Current Vault ZIP hash matches registry, binding, anchor, and verification."),
        _check("urpvo_current_vault_zip_size", len(data) == int(vault.get("vault_zip_size_bytes") or -1) == int(binding.get("vault_zip_size_bytes") or -1) == int(anchor.get("vault_zip_size_bytes") or -1), "Current Vault ZIP size matches registry, binding, and anchor."),
        _check("urpvo_current_vault_manifest_hash", vault.get("vault_manifest_hash") == binding.get("vault_manifest_hash") == anchor.get("vault_manifest_hash") == vault_verification.get("manifest_hash"), "Current Vault manifest hash matches registry, binding, anchor, and verification."),
        _check("urpvo_current_vault_verification_integrity", _integrity_ok(vault_verification), "Current Vault verification report integrity is valid."),
        _check("urpvo_current_vault_verification_status", vault_verification.get("status") == "passed", "Current Vault verification report passed."),
    ]
    if require:
        checks.append(_check("urpvo_require_current_vault", bool(vault) and registry.get("status") == "current", "A current Vault generation is required."))
    return checks


def _deep_vault_checks(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mf-urpvo-deep-") as temp:
        root = Path(temp)
        root_resolved = root.resolve()
        for rel in ("packages/current-vault.zip", "proofs/current-vault-anchor.json", "proofs/current-vault-verification-report.json"):
            dest = (root / rel).resolve()
            if dest != root_resolved and root_resolved not in dest.parents:
                checks.append(_check("urpvo_deep_extract_containment", False, "Deep extraction target stays inside temp root.", {"entry": rel}))
                return checks
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(rel))
        runtime = verify_unified_release_program_vault_package(root / "packages/current-vault.zip", strict=True, deep=True, require_anchor=True, vault_anchor_path=root / "proofs/current-vault-anchor.json", require_accepted_evidence=True)
        external = read_json(root / "proofs/current-vault-verification-report.json")
        checks.extend(
            [
                _check("urpvo_deep_current_vault_runtime_passed", runtime.get("status") == "passed", "Current Vault runtime verifier passed.", {"blockers": runtime.get("blockers", [])}),
                _check("urpvo_deep_current_vault_external_passed", external.get("status") == "passed", "Current Vault external verifier passed.", {"blockers": external.get("blockers", [])}),
                _check("urpvo_deep_current_vault_external_integrity", _integrity_ok(external), "Current Vault external verification integrity is valid."),
                _check("urpvo_deep_current_vault_external_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, "Current Vault external verification package type is valid."),
                _check("urpvo_deep_current_vault_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(root / "packages/current-vault.zip"), "Current Vault runtime and external ZIP hash match."),
                _check("urpvo_deep_current_vault_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Current Vault runtime and external manifest hash match."),
            ]
        )
    return checks


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], first_check: dict[str, Any] | None = None) -> dict[str, Any]:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _current_generation(registry: dict[str, Any]) -> dict[str, Any]:
    current_id = str(registry.get("current_generation_id") or "")
    return next((row for row in registry.get("generations", []) if isinstance(row, dict) and row.get("generation_id") == current_id), {})


def _entry_sha256_for_current_vault_hash(vault: dict[str, Any]) -> str | None:
    return vault.get("vault_zip_sha256")


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id="urpvo_redaction_scan")


def _has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
