from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report as build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check as archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package


UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_archive"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "continuity-policy.json",
    "recovery-plan.json",
    "recovery-drill-report.json",
    "continuity-readiness.json",
    "continuity-runbook.json",
    "continuity-report.json",
    "external-evidence-manifest.json",
    "continuity-signoff.json",
    "continuity-signoff-binding-summary.json",
    "continuity-history.jsonl",
    "redaction-report.json",
    "README.txt",
}

def verify_unified_release_program_continuity_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep_restore: bool = False,
    require_signed: bool = False,
    require_current_vault_operations: bool = False,
    signoff_binding_path: Path | str | None = None,
    vault_operations_archive_path: Path | str | None = None,
    vault_operations_verification_report_path: Path | str | None = None,
    vault_operations_signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 256,
    max_uncompressed_size_mb: int = 1024,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpc_kernel",
                required_entries=frozenset(REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpc_zip_exists", False, "Continuity Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpc_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpc_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after the end of central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpc_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpc_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpc_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpc_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpc_allowed_entries", not extra, "Continuity Archive contains only fixed entries.", {"extra": extra}),
                    _check("urpc_required_entries", not missing, "Continuity Archive contains required entries.", {"missing": missing}),
                    _check("urpc_no_nested_zip", not nested, "Continuity Archive contains no nested ZIP files.", {"nested": nested}),
                ]
            )
            if _has_blocking_failures(checks):
                if deep_restore:
                    checks.append(_check("urpc_deep_preflight", False, "Deep restore verification is skipped when ZIP structure checks fail."))
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            policy = _read_json_entry(archive, "continuity-policy.json")
            plan = _read_json_entry(archive, "recovery-plan.json")
            drill = _read_json_entry(archive, "recovery-drill-report.json")
            readiness = _read_json_entry(archive, "continuity-readiness.json")
            runbook = _read_json_entry(archive, "continuity-runbook.json")
            report = _read_json_entry(archive, "continuity-report.json")
            evidence_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            signoff = _read_json_entry(archive, "continuity-signoff.json")
            binding = _read_json_entry(archive, "continuity-signoff-binding-summary.json")
            redaction = _read_json_entry(archive, "redaction-report.json")
            history = _parse_jsonl(archive.read("continuity-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "program_id": manifest.get("program_id") or report.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "continuity_status": report.get("status"),
                    "drill_status": drill.get("status"),
                    "readiness_status": readiness.get("status"),
                    "signed": signoff.get("status") == "signed",
                    "source_vault_operations_archive_sha256": (manifest.get("source") or {}).get("vault_operations_archive_sha256"),
                }
            )
            checks.extend(
                [
                    _check("urpc_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpc_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION, "Manifest schema version is supported."),
                    _check("urpc_policy_package_type", policy.get("package_type") == "musicforge_unified_release_program_continuity_policy", "Policy package type is valid."),
                    _check("urpc_plan_package_type", plan.get("package_type") == "musicforge_unified_release_program_recovery_plan", "Recovery plan package type is valid."),
                    _check("urpc_drill_package_type", drill.get("package_type") == "musicforge_unified_release_program_recovery_drill_report", "Recovery drill package type is valid."),
                    _check("urpc_readiness_package_type", readiness.get("package_type") == "musicforge_unified_release_program_continuity_readiness", "Readiness package type is valid."),
                    _check("urpc_runbook_package_type", runbook.get("package_type") == "musicforge_unified_release_program_continuity_runbook", "Runbook package type is valid."),
                    _check("urpc_report_package_type", report.get("package_type") == "musicforge_unified_release_program_continuity_report", "Continuity report package type is valid."),
                    _check("urpc_evidence_manifest_package_type", evidence_manifest.get("package_type") == "musicforge_unified_release_program_continuity_external_evidence_manifest", "External evidence manifest package type is valid."),
                    _check("urpc_signoff_package_type", signoff.get("package_type") == "musicforge_unified_release_program_continuity_signoff", "Signoff package type is valid."),
                    _check("urpc_signoff_binding_package_type", binding.get("package_type") == "musicforge_unified_release_program_continuity_signoff_binding_summary", "Signoff binding package type is valid."),
                    _check("urpc_redaction_package_type", redaction.get("package_type") == "musicforge_unified_release_program_continuity_redaction_report", "Redaction report package type is valid."),
                ]
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            for check_id, doc in (
                ("urpc_manifest_integrity", manifest),
                ("urpc_policy_integrity", policy),
                ("urpc_plan_integrity", plan),
                ("urpc_drill_integrity", drill),
                ("urpc_readiness_integrity", readiness),
                ("urpc_runbook_integrity", runbook),
                ("urpc_report_integrity", report),
                ("urpc_evidence_manifest_integrity", evidence_manifest),
                ("urpc_signoff_integrity", signoff),
                ("urpc_signoff_binding_integrity", binding),
                ("urpc_redaction_integrity", redaction),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_history_checks(history))
            checks.extend(_binding_checks(manifest, policy, plan, drill, readiness, runbook, report, evidence_manifest, signoff, binding, history))
            checks.extend(_external_signoff_binding_checks(signoff_binding_path, binding, require=require_signed))
            checks.extend(
                _external_vault_operations_checks(
                    manifest,
                    evidence_manifest,
                    binding,
                    vault_operations_archive_path,
                    vault_operations_verification_report_path,
                    vault_operations_signoff_binding_path,
                    require=require_current_vault_operations or deep_restore,
                    deep=deep_restore,
                )
            )
            if require_signed:
                checks.append(_check("urpc_require_signed", signoff.get("status") == "signed" and binding.get("status") == "signed", "Continuity Archive is signed."))
            if strict:
                checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpc_zip_readable", False, "Continuity Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_continuity_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, name_set: set[str]) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
    file_paths = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    zip_meta = _as_document(manifest.get("zip"))
    checks = [
        _check("urpc_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed archive entries.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpc_manifest_entries_exact", name_set == REQUIRED_ENTRIES, "ZIP entries match fixed archive entries.", {"missing": sorted(REQUIRED_ENTRIES - name_set), "extra": sorted(name_set - REQUIRED_ENTRIES)}),
        _check("urpc_manifest_zip_filename", zip_meta.get("filename") == "unified-release-program-continuity-archive.zip", "Manifest ZIP filename is canonical."),
        _check("urpc_manifest_zip_entries", sorted(zip_meta.get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory entries."),
        _check("urpc_manifest_zip_entry_count", int(zip_meta.get("entry_count") or -1) == len(name_set), "Manifest ZIP entry count matches central directory."),
        _check("urpc_manifest_zip_no_self_hash", "sha256" not in zip_meta and "size_bytes" not in zip_meta, "Manifest ZIP metadata does not contain an impossible self-hash or self-size."),
    ]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in archive.namelist():
            checks.append(_check(f"urpc_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP."))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpc_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."))
        checks.append(_check(f"urpc_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."))
    return checks


def _history_checks(events: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    previous = ""
    signoff_events = 0
    for index, event in enumerate(events, start=1):
        prefix = f"urpc_history_{index:03d}"
        expected_payload = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({**{key: value for key, value in event.items() if key != "event_hash"}, "payload_hash": expected_payload})
        checks.append(_check(f"{prefix}_previous", event.get("previous_event_hash") == previous, "History previous event hash matches."))
        checks.append(_check(f"{prefix}_payload_hash", event.get("payload_hash") == expected_payload, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_event_hash", event.get("event_hash") == expected_event, "History event hash is valid."))
        if event.get("event_type") == "continuity_signoff_created":
            signoff_events += 1
        previous = str(event.get("event_hash") or "")
    checks.append(_check("urpc_history_has_signoff", signoff_events >= 1, "History contains a continuity signoff event."))
    return checks


def _binding_checks(
    manifest: ImplementationDocument,
    policy: ImplementationDocument,
    plan: ImplementationDocument,
    drill: ImplementationDocument,
    readiness: ImplementationDocument,
    runbook: ImplementationDocument,
    report: ImplementationDocument,
    evidence_manifest: ImplementationDocument,
    signoff: ImplementationDocument,
    binding: ImplementationDocument,
    history: list[ImplementationDocument],
) -> list[ImplementationDocument]:
    latest = next((row for row in reversed(history) if row.get("event_type") == "continuity_signoff_created"), {})
    source = _as_document(manifest.get("source"))
    pairs = {
        "policy_hash": policy.get("integrity_hash"),
        "recovery_plan_hash": plan.get("integrity_hash"),
        "drill_report_hash": drill.get("integrity_hash"),
        "readiness_hash": readiness.get("integrity_hash"),
        "runbook_hash": runbook.get("integrity_hash"),
        "continuity_report_hash": report.get("integrity_hash"),
        "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
        "signoff_hash": signoff.get("integrity_hash"),
        "signoff_binding_hash": binding.get("integrity_hash"),
    }
    checks = [
        _check("urpc_report_passed", report.get("status") == "passed", "Continuity report passed."),
        _check("urpc_drill_passed", drill.get("status") == "passed", "Recovery drill passed."),
        _check("urpc_readiness_passed", readiness.get("status") == "passed", "Continuity readiness passed."),
        _check("urpc_signoff_status", signoff.get("status") == "signed", "Continuity signoff is signed."),
        _check("urpc_signoff_binding_status", binding.get("status") == "signed", "Continuity signoff binding is signed."),
        _check("urpc_signoff_history_binding", binding.get("latest_history_event_hash") == latest.get("event_hash") and signoff.get("integrity_hash") == latest.get("signoff_hash"), "Signoff binding matches latest history signoff event."),
        _check("urpc_binding_signoff_fields", all(binding.get(key) == signoff.get(key) for key in ("signed_by", "role", "reason", "signed_at")), "Signoff binding public fields match signoff document."),
        _check("urpc_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
    ]
    for key, value in pairs.items():
        checks.append(_check(f"urpc_manifest_source_{key}", source.get(key) == value, f"Manifest source {key} matches document."))
        if key not in {"signoff_binding_hash"}:
            checks.append(_check(f"urpc_binding_{key}", binding.get(key) == value, f"Signoff binding {key} matches document."))
    for key in (
        "vault_operations_archive_sha256",
        "vault_operations_archive_size_bytes",
        "vault_operations_manifest_hash",
        "vault_operations_verification_report_hash",
        "vault_operations_signoff_binding_hash",
    ):
        checks.append(_check(f"urpc_manifest_source_{key}", source.get(key) == binding.get(key), f"Manifest and binding source {key} match."))
    return checks


def _external_signoff_binding_checks(path: Path | str | None, binding: ImplementationDocument, *, require: bool) -> list[ImplementationDocument]:
    if not path:
        return [_check("urpc_external_signoff_binding_required", not require, "External continuity signoff binding is present when required.")]
    binding_path = Path(path)
    checks = [_check("urpc_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External continuity signoff binding exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = read_json(binding_path)
    checks.append(_check("urpc_external_signoff_binding_integrity", _integrity_ok(external), "External continuity signoff binding integrity is valid."))
    checks.append(_check("urpc_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External continuity signoff binding matches archive binding."))
    checks.append(_check("urpc_external_signoff_binding_payload", external == binding, "External continuity signoff binding content matches archive binding."))
    return checks


def _external_vault_operations_checks(
    manifest: ImplementationDocument,
    evidence_manifest: ImplementationDocument,
    binding: ImplementationDocument,
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    *,
    require: bool,
    deep: bool,
) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    if not archive_path:
        checks.append(_check("urpc_vault_operations_archive_required", not require, "External Vault Operations archive is present when required."))
        return checks
    if not verification_report_path:
        checks.append(_check("urpc_vault_operations_verification_required", not require, "External Vault Operations verification report is present when required."))
        return checks
    if not signoff_binding_path:
        checks.append(_check("urpc_vault_operations_signoff_binding_required", not require, "External Vault Operations signoff binding is present when required."))
        return checks
    archive_path = Path(archive_path)
    verification_report_path = Path(verification_report_path)
    signoff_binding_path = Path(signoff_binding_path)
    checks.extend(
        [
            _check("urpc_vault_operations_archive_exists", archive_path.exists() and archive_path.is_file(), "External Vault Operations archive exists."),
            _check("urpc_vault_operations_verification_exists", verification_report_path.exists() and verification_report_path.is_file(), "External Vault Operations verification report exists."),
            _check("urpc_vault_operations_signoff_binding_exists", signoff_binding_path.exists() and signoff_binding_path.is_file(), "External Vault Operations signoff binding exists."),
        ]
    )
    if _has_blocking_failures(checks):
        return checks
    with tempfile.TemporaryDirectory(prefix="mf-urpc-vault-ops-") as temp:
        root = Path(temp)
        archive_copy = root / "vault-operations-archive.zip"
        archive_copy.write_bytes(archive_path.read_bytes())
        runtime = verify_unified_release_program_vault_operations_package(
            archive_copy,
            strict=True,
            deep=deep or require,
            require_signed=True,
            require_current_vault=True,
            signoff_binding_path=signoff_binding_path,
        )
    external = read_json(verification_report_path)
    source = _as_document(manifest.get("source"))
    evidence = _evidence_row(evidence_manifest)
    checks.extend(
        [
            _check("urpc_vault_operations_runtime_passed", runtime.get("status") == "passed", "Runtime Vault Operations verifier passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urpc_vault_operations_external_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, "External Vault Operations verification package type is valid."),
            _check("urpc_vault_operations_external_integrity", _integrity_ok(external), "External Vault Operations verification report integrity is valid."),
            _check("urpc_vault_operations_external_passed", external.get("status") == "passed", "External Vault Operations verification report passed."),
            _check("urpc_vault_operations_zip_sha256", _sha256_path(archive_path) == runtime.get("zip_sha256") == external.get("zip_sha256") == binding.get("vault_operations_archive_sha256") == source.get("vault_operations_archive_sha256") == evidence.get("archive_zip_sha256"), "Vault Operations archive hash matches all bindings."),
            _check("urpc_vault_operations_zip_size", archive_path.stat().st_size == int(binding.get("vault_operations_archive_size_bytes") or -1) == int(source.get("vault_operations_archive_size_bytes") or -1) == int(evidence.get("archive_zip_size_bytes") or -1), "Vault Operations archive size matches all bindings."),
            _check("urpc_vault_operations_manifest_hash", runtime.get("manifest_hash") == external.get("manifest_hash") == binding.get("vault_operations_manifest_hash") == source.get("vault_operations_manifest_hash") == evidence.get("manifest_hash"), "Vault Operations manifest hash matches all bindings."),
            _check("urpc_vault_operations_verification_hash", external.get("integrity_hash") == binding.get("vault_operations_verification_report_hash") == source.get("vault_operations_verification_report_hash") == evidence.get("verification_report_hash"), "Vault Operations verification report hash matches all bindings."),
            _check("urpc_vault_operations_signoff_binding_hash", _integrity_ok(read_json(signoff_binding_path)) and read_json(signoff_binding_path).get("integrity_hash") == binding.get("vault_operations_signoff_binding_hash") == source.get("vault_operations_signoff_binding_hash") == evidence.get("signoff_binding_hash"), "Vault Operations signoff binding hash matches all bindings."),
        ]
    )
    return checks


def _evidence_row(evidence_manifest: ImplementationDocument) -> ImplementationDocument:
    for row in evidence_manifest.get("evidence", []) or []:
        if isinstance(row, dict) and row.get("evidence_type") == "vault_operations_archive":
            return row
    return {}


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, first_check: ImplementationDocument | None = None) -> ImplementationDocument:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[ImplementationDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    return archive_redaction_check(archive, names, check_id="urpc_redaction_scan")


def _has_blocking_failures(checks: list[ImplementationDocument]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
