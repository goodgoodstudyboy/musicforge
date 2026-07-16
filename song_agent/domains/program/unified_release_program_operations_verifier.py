from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
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
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program_verifier import (
    UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_package,
)


UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE = "musicforge_unified_release_program_operations_archive"
UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_operations_archive_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUOUS_REVIEW_PACKAGE_TYPE = "musicforge_unified_release_program_continuous_review"
UNIFIED_RELEASE_PROGRAM_LIFECYCLE_AUDIT_PACKAGE_TYPE = "musicforge_unified_release_program_lifecycle_audit"
UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "program-summary.json",
    "program-verification-summary.json",
    "program-signoff-summary.json",
    "program-signoff-binding-summary.json",
    "external-evidence-manifest-summary.json",
    "change-control-summary.json",
    "continuous-review-summary.json",
    "lifecycle-audit-summary.json",
    "evidence-index.json",
    "history/program-history.jsonl",
    "history/change-control-history.jsonl",
}

def verify_unified_release_program_operations_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_signed_program: bool = False,
    require_continuous_review_clear: bool = False,
    require_lifecycle_audit: bool = False,
    program_zip_path: Path | str | None = None,
    program_verification_report_path: Path | str | None = None,
    program_signoff_binding_path: Path | str | None = None,
    external_evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urp_ops_kernel",
                required_entries=frozenset(REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                allowed_entry_patterns=(),
                nested_zip_policy="deny",
                allowed_nested_entries=frozenset(),
                allowed_nested_patterns=(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urp_ops_zip_exists", False, "Operations Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urp_ops_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.extend(
                [
                    _check("urp_ops_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urp_ops_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urp_ops_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urp_ops_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urp_ops_no_nested_zip", not nested, "Operations Archive does not embed ZIP packages.", {"nested": nested}),
                    _check("urp_ops_allowed_entries", not extra, "Operations Archive contains only fixed entries.", {"extra": extra}),
                    _check("urp_ops_required_entries", not missing, "Operations Archive contains required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            program = _read_json_entry(archive, "program-summary.json")
            program_verification = _read_json_entry(archive, "program-verification-summary.json")
            signoff = _read_json_entry(archive, "program-signoff-summary.json")
            binding = _read_json_entry(archive, "program-signoff-binding-summary.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest-summary.json")
            change_control = _read_json_entry(archive, "change-control-summary.json")
            review = _read_json_entry(archive, "continuous-review-summary.json")
            lifecycle = _read_json_entry(archive, "lifecycle-audit-summary.json")
            evidence = _read_json_entry(archive, "evidence-index.json")
            program_history = _parse_jsonl(archive.read("history/program-history.jsonl").decode("utf-8"))
            change_history = _parse_jsonl(archive.read("history/change-control-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "program_id": manifest.get("program_id") or program.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "program_status": program.get("status"),
                    "continuous_review_status": review.get("status"),
                    "lifecycle_status": lifecycle.get("status"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.extend(
                [
                    _check("urp_ops_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urp_ops_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("urp_ops_manifest_integrity", manifest),
                ("urp_ops_program_summary_integrity", program),
                ("urp_ops_program_verification_summary_integrity", program_verification),
                ("urp_ops_program_signoff_summary_integrity", signoff),
                ("urp_ops_signoff_binding_summary_integrity", binding),
                ("urp_ops_external_manifest_summary_integrity", external_manifest),
                ("urp_ops_change_control_summary_integrity", change_control),
                ("urp_ops_continuous_review_summary_integrity", review),
                ("urp_ops_lifecycle_summary_integrity", lifecycle),
                ("urp_ops_evidence_index_integrity", evidence),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, program, program_verification, signoff, binding, external_manifest, change_control, review, lifecycle, evidence))
            checks.extend(_history_checks(program_history, change_history, lifecycle))
            external_state = _external_program_state(
                require=require_current or require_signed_program,
                program_zip_path=program_zip_path,
                program_verification_report_path=program_verification_report_path,
                program_signoff_binding_path=program_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
            )
            checks.extend(external_state.pop("checks"))
            checks.extend(_semantic_checks(program, program_verification, signoff, binding, external_manifest, review, lifecycle, evidence, external_state, require_signed_program=require_signed_program, require_continuous_review_clear=require_continuous_review_clear, require_lifecycle_audit=require_lifecycle_audit))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urp_ops_zip_readable", False, "Operations Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_operations_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_operations_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_program_state(
    *,
    require: bool,
    program_zip_path: Path | str | None,
    program_verification_report_path: Path | str | None,
    program_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> ImplementationDocument:
    checks: list[dict[str, Any]] = []
    state: dict[str, Any] = {"checks": checks, "runtime": {}, "external_report": {}, "binding": {}, "external_manifest": {}, "history": []}
    if not require:
        return state
    if not program_zip_path or not program_verification_report_path or not program_signoff_binding_path or not external_evidence_manifest_path:
        checks.append(_check("urp_ops_current_program_external_required", False, "Program ZIP, verification report, signoff binding, and external evidence manifest are required."))
        return state
    zip_path = Path(program_zip_path)
    report_path = Path(program_verification_report_path)
    binding_path = Path(program_signoff_binding_path)
    evidence_path = Path(external_evidence_manifest_path)
    checks.extend(
        [
            _check("urp_ops_current_program_zip_exists", zip_path.exists(), "Current Program ZIP exists."),
            _check("urp_ops_current_program_verification_exists", report_path.exists(), "Current Program verification report exists."),
            _check("urp_ops_current_program_binding_exists", binding_path.exists(), "Current Program signoff binding exists."),
            _check("urp_ops_current_program_external_manifest_exists", evidence_path.exists(), "Current Program external evidence manifest exists."),
        ]
    )
    if not zip_path.exists() or not report_path.exists() or not binding_path.exists() or not evidence_path.exists():
        return state
    external = read_json(report_path)
    binding = read_json(binding_path)
    evidence_manifest = read_json(evidence_path)
    runtime = verify_unified_release_program_package(zip_path, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=evidence_path, program_signoff_binding_path=binding_path)
    checks.extend(
        [
            _check("urp_ops_current_program_verification_integrity", _integrity_ok(external), "Program verification report integrity is valid."),
            _check("urp_ops_current_program_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program verification report package type is valid."),
            _check("urp_ops_current_program_runtime_passed", runtime.get("status") == "passed", "Current Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urp_ops_current_program_external_passed", external.get("status") == "passed", "Current Program external verification passed."),
            _check("urp_ops_current_program_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Current Program ZIP hash matches runtime and report."),
            _check("urp_ops_current_program_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Current Program manifest hash matches runtime and report."),
            _check("urp_ops_current_program_binding_integrity", _integrity_ok(binding), "Current Program signoff binding integrity is valid."),
            _check("urp_ops_current_program_external_manifest_integrity", _integrity_ok(evidence_manifest), "External evidence manifest integrity is valid."),
        ]
    )
    state.update(
        {
            "runtime": runtime,
            "external_report": external,
            "binding": binding,
            "external_manifest": evidence_manifest,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": _integrity_hash(external),
            "binding_hash": binding.get("integrity_hash"),
            "external_manifest_hash": evidence_manifest.get("integrity_hash"),
            "history": _program_history_from_zip(zip_path),
        }
    )
    return state


def _semantic_checks(
    program: ImplementationDocument,
    program_verification: ImplementationDocument,
    signoff: ImplementationDocument,
    binding: ImplementationDocument,
    external_manifest: ImplementationDocument,
    review: ImplementationDocument,
    lifecycle: ImplementationDocument,
    evidence: ImplementationDocument,
    external: ImplementationDocument,
    *,
    require_signed_program: bool,
    require_continuous_review_clear: bool,
    require_lifecycle_audit: bool,
) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    runtime = external.get("runtime") or {}
    external_report = external.get("external_report") or {}
    if external:
        checks.extend(
            [
                _check("urp_ops_program_summary_runtime_binding", not runtime or program.get("program_zip_sha256") == runtime.get("zip_sha256"), "Program summary ZIP hash matches runtime."),
                _check("urp_ops_program_verification_runtime_binding", not external_report or program_verification.get("verification_report_hash") == _integrity_hash(external_report), "Program verification summary binds external report."),
                _check("urp_ops_signoff_binding_runtime_binding", not external.get("binding") or binding.get("integrity_hash") == external.get("binding_hash") == signoff.get("signoff_binding_hash"), "Signoff binding summary matches external binding."),
                _check("urp_ops_external_manifest_runtime_binding", not external.get("external_manifest") or external_manifest.get("external_manifest_hash") == external.get("external_manifest_hash"), "External evidence manifest summary matches external manifest."),
            ]
        )
    expected_review_status = review.get("status") if not runtime and not external_report else "passed" if runtime.get("status") == "passed" and external_report.get("status") == "passed" else "failed"
    checks.append(_check("urp_ops_continuous_review_semantics", review.get("status") == expected_review_status, "Continuous Review status is derived from current Program evidence.", {"expected": expected_review_status, "actual": review.get("status")}))
    signoff_events = [row for row in external.get("history", []) if row.get("event_type") == "unified_release_program_signoff_created"]
    reset_events = [row for row in external.get("history", []) if row.get("event_type") == "unified_release_program_signoff_reset"]
    if signoff_events or reset_events:
        checks.extend(
            [
                _check("urp_ops_lifecycle_signoff_count", int(lifecycle.get("summary", {}).get("signoff_count") or 0) == len(signoff_events), "Lifecycle signoff count matches Program history."),
                _check("urp_ops_lifecycle_reset_count", int(lifecycle.get("summary", {}).get("reset_count") or 0) == len(reset_events), "Lifecycle reset count matches Program history."),
            ]
        )
    evidence_items = [row for row in evidence.get("items", []) if isinstance(row, dict)]
    evidence_types = {row.get("evidence_type") for row in evidence_items}
    checks.extend(
        [
            _check("urp_ops_evidence_index_has_program", "program" in evidence_types, "Evidence index includes Program evidence."),
            _check("urp_ops_evidence_index_has_review", "continuous_review" in evidence_types, "Evidence index includes Continuous Review evidence."),
            _check("urp_ops_evidence_index_has_lifecycle", "lifecycle_audit" in evidence_types, "Evidence index includes Lifecycle Audit evidence."),
        ]
    )
    if require_signed_program:
        checks.append(_check("urp_ops_require_signed_program", signoff.get("status") == "signed" and runtime.get("summary", {}).get("signed") is True, "Program is signed."))
    if require_continuous_review_clear:
        checks.append(_check("urp_ops_require_continuous_review_clear", review.get("status") == "passed" and int(review.get("summary", {}).get("critical_drift_count") or 0) == 0, "Continuous Review is clear."))
    if require_lifecycle_audit:
        checks.append(_check("urp_ops_require_lifecycle_audit", lifecycle.get("status") == "passed", "Lifecycle Audit passed."))
    return checks


def _document_binding_checks(
    manifest: ImplementationDocument,
    program: ImplementationDocument,
    program_verification: ImplementationDocument,
    signoff: ImplementationDocument,
    binding: ImplementationDocument,
    external_manifest: ImplementationDocument,
    change_control: ImplementationDocument,
    review: ImplementationDocument,
    lifecycle: ImplementationDocument,
    evidence: ImplementationDocument,
) -> list[ImplementationDocument]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return [
        _check("urp_ops_manifest_program_hash", source.get("program_summary_hash") == program.get("integrity_hash"), "Manifest binds Program summary."),
        _check("urp_ops_manifest_program_verification_hash", source.get("program_verification_summary_hash") == program_verification.get("integrity_hash"), "Manifest binds Program verification summary."),
        _check("urp_ops_manifest_signoff_hash", source.get("program_signoff_summary_hash") == signoff.get("integrity_hash"), "Manifest binds signoff summary."),
        _check("urp_ops_manifest_binding_hash", source.get("program_signoff_binding_summary_hash") == binding.get("integrity_hash"), "Manifest binds signoff binding summary."),
        _check("urp_ops_manifest_external_manifest_hash", source.get("external_evidence_manifest_summary_hash") == external_manifest.get("integrity_hash"), "Manifest binds external evidence manifest summary."),
        _check("urp_ops_manifest_change_control_hash", source.get("change_control_summary_hash") == change_control.get("integrity_hash"), "Manifest binds change-control summary."),
        _check("urp_ops_manifest_review_hash", source.get("continuous_review_summary_hash") == review.get("integrity_hash"), "Manifest binds continuous review summary."),
        _check("urp_ops_manifest_lifecycle_hash", source.get("lifecycle_audit_summary_hash") == lifecycle.get("integrity_hash"), "Manifest binds lifecycle summary."),
        _check("urp_ops_manifest_evidence_index_hash", source.get("evidence_index_hash") == evidence.get("integrity_hash"), "Manifest binds evidence index."),
    ]


def _history_checks(program_history: list[ImplementationDocument], change_history: list[ImplementationDocument], lifecycle: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    checks.extend(_hash_chain_checks("urp_ops_program_history", program_history))
    checks.extend(_hash_chain_checks("urp_ops_change_history", change_history))
    signoff_count = sum(1 for row in program_history if row.get("event_type") == "unified_release_program_signoff_created")
    reset_count = sum(1 for row in program_history if row.get("event_type") == "unified_release_program_signoff_reset")
    checks.extend(
        [
            _check("urp_ops_lifecycle_summary_program_signoffs", int(lifecycle.get("summary", {}).get("signoff_count") or 0) == signoff_count, "Lifecycle summary signoff count matches archived history."),
            _check("urp_ops_lifecycle_summary_program_resets", int(lifecycle.get("summary", {}).get("reset_count") or 0) == reset_count, "Lifecycle summary reset count matches archived history."),
        ]
    )
    return checks


def _hash_chain_checks(prefix: str, rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, event in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"{prefix}_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    declared = {str(row.get("path") or "") for row in files}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    checks = [_check("urp_ops_manifest_files_fixed", declared == expected_files, "Manifest files match fixed Operations Archive layout.", {"missing": sorted(expected_files - declared), "extra": sorted(declared - expected_files)})]
    mismatches = []
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in names:
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        data = archive.read(rel)
        if row.get("size_bytes") != len(data) or row.get("sha256") != _sha256_bytes(data):
            mismatches.append({"path": rel, "reason": "hash_or_size"})
    checks.append(_check("urp_ops_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
        checks=[*checks, *extra],
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_OPERATIONS_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[ImplementationDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    return archive_redaction_check(archive, names, check_id="urp_ops_redaction_scan")


def _program_history_from_zip(path: Path) -> list[ImplementationDocument]:
    try:
        with zipfile.ZipFile(path) as archive:
            return _parse_jsonl(archive.read("program-history.jsonl").decode("utf-8"))
    except Exception:
        return []
