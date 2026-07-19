from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.persistence.file_artifacts import read_json_document as read_json, write_json_atomic as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package


UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_lifecycle"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_lifecycle_verification"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "lifecycle-report.json",
    "lifecycle-ledger.jsonl",
    "signoff-succession-map.json",
    "change-reset-coverage.json",
    "archive-history-ledger.json",
    "current-readiness-assertion.json",
    "gap-plan.json",
    "evidence-fingerprint-index.json",
    "REVIEWER_GUIDE.md",
    "README.txt",
}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_unified_command_center_release_train_lifecycle_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current_train: bool = False,
    require_change_control: bool = False,
    train_archive_path: Path | str | None = None,
    train_archive_verification_report_path: Path | str | None = None,
    train_signoff_binding_path: Path | str | None = None,
    external_evidence_manifest_path: Path | str | None = None,
    change_control_zip_path: Path | str | None = None,
    change_control_verification_report_path: Path | str | None = None,
    reset_proof_paths: list[Path | str] | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_train_lifecycle_zip_exists", False, "Lifecycle ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_train_lifecycle_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
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
                    _check("ucc_train_lifecycle_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("ucc_train_lifecycle_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("ucc_train_lifecycle_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("ucc_train_lifecycle_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("ucc_train_lifecycle_no_nested_zip", not nested, "Lifecycle ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("ucc_train_lifecycle_allowed_entries", not extra, "Lifecycle ZIP contains only fixed entries.", {"extra": extra}),
                    _check("ucc_train_lifecycle_required_entries", not missing, "Lifecycle ZIP contains all required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "lifecycle-report.json")
            succession = _read_json_entry(archive, "signoff-succession-map.json")
            coverage = _read_json_entry(archive, "change-reset-coverage.json")
            archive_history = _read_json_entry(archive, "archive-history-ledger.json")
            readiness = _read_json_entry(archive, "current-readiness-assertion.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            evidence_index = _read_json_entry(archive, "evidence-fingerprint-index.json")
            ledger = _parse_jsonl(archive.read("lifecycle-ledger.jsonl").decode("utf-8"))
            summary.update({"train_id": report.get("train_id"), "manifest_hash": manifest.get("integrity_hash"), "status": report.get("status"), **(report.get("summary") or {})})

            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.extend(
                [
                    _check("ucc_train_lifecycle_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("ucc_train_lifecycle_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("ucc_train_lifecycle_manifest_integrity", manifest),
                ("ucc_train_lifecycle_report_integrity", report),
                ("ucc_train_lifecycle_succession_integrity", succession),
                ("ucc_train_lifecycle_coverage_integrity", coverage),
                ("ucc_train_lifecycle_archive_history_integrity", archive_history),
                ("ucc_train_lifecycle_readiness_integrity", readiness),
                ("ucc_train_lifecycle_gap_plan_integrity", gap_plan),
                ("ucc_train_lifecycle_evidence_index_integrity", evidence_index),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, succession, coverage, archive_history, readiness, gap_plan, evidence_index, ledger))
            checks.extend(_ledger_chain_checks(ledger))

            external_train = _external_train_state(
                require=require_current_train,
                train_archive_path=train_archive_path,
                train_archive_verification_report_path=train_archive_verification_report_path,
                train_signoff_binding_path=train_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
            )
            checks.extend(external_train.pop("checks"))
            reset_count = len(external_train.get("reset_events", []))
            change_required = require_change_control or reset_count > 0
            external_change = _external_change_control_state(
                require=change_required,
                change_control_zip_path=change_control_zip_path,
                change_control_verification_report_path=change_control_verification_report_path,
                train_archive_path=train_archive_path,
                train_archive_verification_report_path=train_archive_verification_report_path,
                train_signoff_binding_path=train_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
                reset_proof_paths=reset_proof_paths or [],
            )
            checks.extend(external_change.pop("checks"))
            reset_proofs = _reset_proof_state(reset_proof_paths or [])
            checks.extend(reset_proofs.pop("checks"))
            checks.extend(_semantic_checks(report, succession, coverage, archive_history, readiness, evidence_index, external_train, external_change, reset_proofs))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_train_lifecycle_zip_readable", False, "Lifecycle ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_release_train_lifecycle_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_release_train_lifecycle_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_train_state(
    *,
    require: bool,
    train_archive_path: Path | str | None,
    train_archive_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks, "signoff_events": [], "reset_events": [], "history": [], "runtime": {}, "external_report": {}, "signoff_binding": {}, "external_evidence_manifest": {}}
    if not require:
        return state
    if not train_archive_path or not train_archive_verification_report_path or not train_signoff_binding_path or not external_evidence_manifest_path:
        checks.append(_check("ucc_train_lifecycle_current_train_external_required", False, "Current train archive, verification report, signoff binding, and evidence manifest are required."))
        return state
    archive_path = Path(train_archive_path)
    report_path = Path(train_archive_verification_report_path)
    binding_path = Path(train_signoff_binding_path)
    manifest_path = Path(external_evidence_manifest_path)
    checks.extend(
        [
            _check("ucc_train_lifecycle_current_train_archive_exists", archive_path.exists(), "Current train archive exists."),
            _check("ucc_train_lifecycle_current_train_verification_exists", report_path.exists(), "Current train verification report exists."),
            _check("ucc_train_lifecycle_current_train_signoff_binding_exists", binding_path.exists(), "Current train signoff binding exists."),
            _check("ucc_train_lifecycle_current_train_external_manifest_exists", manifest_path.exists(), "External evidence manifest exists."),
        ]
    )
    if not archive_path.exists() or not report_path.exists() or not binding_path.exists() or not manifest_path.exists():
        return state
    external = read_json(report_path)
    binding = read_json(binding_path)
    evidence_manifest = read_json(manifest_path)
    runtime = verify_unified_command_center_release_train_package(archive_path, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=binding_path)
    history = _train_history_from_zip(archive_path)
    signoffs = [row for row in history if row.get("event_type") == "ucc_release_train_signoff_created"]
    resets = [row for row in history if row.get("event_type") == "ucc_release_train_signoff_reset"]
    checks.extend(
        [
            _check("ucc_train_lifecycle_current_train_external_integrity", _integrity_ok(external), "Current train verification report integrity is valid."),
            _check("ucc_train_lifecycle_current_train_runtime_passed", runtime.get("status") == "passed", "Current train runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_lifecycle_current_train_external_passed", external.get("status") == "passed", "Current train external verification passed."),
            _check("ucc_train_lifecycle_current_train_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(archive_path), "Current train ZIP hash matches runtime and report."),
            _check("ucc_train_lifecycle_current_train_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Current train manifest hash matches runtime and report."),
        ]
    )
    state.update({"runtime": runtime, "external_report": external, "signoff_binding": binding, "external_evidence_manifest": evidence_manifest, "history": history, "signoff_events": signoffs, "reset_events": resets, "archive_zip_sha256": _sha256_path(archive_path), "archive_size_bytes": archive_path.stat().st_size})
    return state


def _external_change_control_state(
    *,
    require: bool,
    change_control_zip_path: Path | str | None,
    change_control_verification_report_path: Path | str | None,
    train_archive_path: Path | str | None,
    train_archive_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
    reset_proof_paths: list[Path | str],
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks, "runtime": {}, "external_report": {}, "configured": False}
    if not require:
        return state
    if not change_control_zip_path or not change_control_verification_report_path:
        checks.append(_check("ucc_train_lifecycle_change_control_external_required", False, "Change Control ZIP and verification report are required when reset history exists."))
        return state
    zip_path = Path(change_control_zip_path)
    report_path = Path(change_control_verification_report_path)
    checks.extend(
        [
            _check("ucc_train_lifecycle_change_control_zip_exists", zip_path.exists(), "Change Control ZIP exists."),
            _check("ucc_train_lifecycle_change_control_verification_exists", report_path.exists(), "Change Control verification report exists."),
        ]
    )
    if not zip_path.exists() or not report_path.exists():
        return state
    external = read_json(report_path)
    latest_proof = reset_proof_paths[-1] if reset_proof_paths else None
    runtime = verify_unified_command_center_release_train_change_control_package(
        zip_path,
        strict=True,
        require_reset_applied=True,
        require_current_train=True,
        train_archive_path=train_archive_path,
        train_archive_verification_report_path=train_archive_verification_report_path,
        train_signoff_binding_path=train_signoff_binding_path,
        external_evidence_manifest_path=external_evidence_manifest_path,
        reset_proof_path=latest_proof,
    )
    checks.extend(
        [
            _check("ucc_train_lifecycle_change_control_external_integrity", _integrity_ok(external), "Change Control verification report integrity is valid."),
            _check("ucc_train_lifecycle_change_control_runtime_passed", runtime.get("status") == "passed", "Change Control runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_lifecycle_change_control_external_passed", external.get("status") == "passed", "Change Control external verification passed."),
            _check("ucc_train_lifecycle_change_control_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Change Control ZIP hash matches runtime and report."),
            _check("ucc_train_lifecycle_change_control_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Change Control manifest hash matches runtime and report."),
        ]
    )
    state.update({"configured": True, "runtime": runtime, "external_report": external, "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    return state


def _reset_proof_state(paths: list[Path | str]) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    proofs = []
    for index, value in enumerate(paths):
        path = Path(value)
        checks.append(_check(f"ucc_train_lifecycle_reset_proof_{index:03d}_exists", path.exists(), "Reset proof exists."))
        proof = read_json(path) if path.exists() else {}
        if path.exists():
            checks.append(_check(f"ucc_train_lifecycle_reset_proof_{index:03d}_integrity", _integrity_ok(proof), "Reset proof integrity is valid."))
        proofs.append(proof)
    return {"checks": checks, "proofs": proofs}


def _semantic_checks(
    report: ImplementationDocument,
    succession: ImplementationDocument,
    coverage: ImplementationDocument,
    archive_history: ImplementationDocument,
    readiness: ImplementationDocument,
    evidence_index: ImplementationDocument,
    external_train: ImplementationDocument,
    external_change: ImplementationDocument,
    reset_proofs: ImplementationDocument,
) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    signoffs = external_train.get("signoff_events", [])
    resets = external_train.get("reset_events", [])
    summary = _as_document(report.get("summary"))
    checks.extend(
        [
            _check("ucc_train_lifecycle_report_signoff_count", int(summary.get("signoff_count") or 0) == len(signoffs), "Report signoff count matches external train history."),
            _check("ucc_train_lifecycle_report_reset_count", int(summary.get("reset_count") or 0) == len(resets), "Report reset count matches external train history."),
            _check("ucc_train_lifecycle_report_status", report.get("status") == ("passed" if not (resets and external_change.get("runtime", {}).get("status") != "passed") else "failed"), "Lifecycle report status matches external reset state."),
        ]
    )
    succession_items = [row for row in succession.get("items", []) if isinstance(row, dict)]
    checks.append(_check("ucc_train_lifecycle_signoff_succession_count", len(succession_items) == len(signoffs), "Succession map covers every signoff."))
    for index, event in enumerate(signoffs):
        row = succession_items[index] if index < len(succession_items) else {}
        prefix = f"ucc_train_lifecycle_signoff_succession_{index + 1:03d}"
        checks.extend(
            [
                _check(f"{prefix}_hash", row.get("signoff_hash") == event.get("signoff_hash"), "Succession signoff hash matches train history."),
                _check(f"{prefix}_signed_by", row.get("signed_by") == event.get("signed_by"), "Succession signer matches train history."),
            ]
        )
    coverage_items = [row for row in coverage.get("items", []) if isinstance(row, dict)]
    proof_by_event = {proof.get("reset_event_hash"): proof for proof in reset_proofs.get("proofs", []) if isinstance(proof, dict)}
    archive_history_hashes = {row.get("previous_signoff_hash") for row in archive_history.get("items", []) if isinstance(row, dict)}
    checks.append(_check("ucc_train_lifecycle_reset_coverage_count", len(coverage_items) == len(resets), "Reset coverage covers every reset event."))
    for index, event in enumerate(resets):
        row = next((item for item in coverage_items if item.get("reset_event_hash") == event.get("event_hash")), {})
        proof = proof_by_event.get(event.get("event_hash"), {})
        prefix = f"ucc_train_lifecycle_reset_semantics_{index + 1:03d}"
        checks.extend(
            [
                _check(f"{prefix}_coverage_row", bool(row), "Reset has coverage row."),
                _check(f"{prefix}_proof", bool(proof) and _integrity_ok(proof), "Reset has matching external proof."),
                _check(f"{prefix}_archive_history", event.get("previous_signoff_hash") in archive_history_hashes, "Reset previous signoff has archive-history entry."),
            ]
        )
    readiness_checks = {row.get("check_id"): row.get("status") for row in readiness.get("checks", []) if isinstance(row, dict)}
    checks.extend(
        [
            _check("ucc_train_lifecycle_readiness_current_train_signed", readiness_checks.get("current_train_signed") == ("passed" if signoffs and (not resets or signoffs[-1].get("created_at") >= resets[-1].get("created_at", "")) else "failed"), "Readiness signed check matches external history."),
            _check("ucc_train_lifecycle_readiness_archive_verified", readiness_checks.get("current_train_archive_verified") == ("passed" if external_train.get("runtime", {}).get("status") == "passed" and external_train.get("external_report", {}).get("status") == "passed" else "failed"), "Readiness archive verification check matches runtime."),
        ]
    )
    evidence_items = [row for row in evidence_index.get("items", []) if isinstance(row, dict)]
    current = next((row for row in evidence_items if row.get("evidence_type") == "current_train"), {})
    runtime = external_train.get("runtime", {})
    external_report = external_train.get("external_report", {})
    checks.extend(
        [
            _check("ucc_train_lifecycle_evidence_current_train_zip", current.get("zip_sha256") == runtime.get("zip_sha256"), "Evidence index current train ZIP hash matches runtime."),
            _check("ucc_train_lifecycle_evidence_current_train_manifest", current.get("manifest_hash") == runtime.get("manifest_hash"), "Evidence index current train manifest hash matches runtime."),
            _check("ucc_train_lifecycle_evidence_current_train_report", current.get("verification_report_hash") == _integrity_hash(external_report) if external_report else False, "Evidence index current train verification hash matches external report."),
        ]
    )
    if resets:
        change = next((row for row in evidence_items if row.get("evidence_type") == "change_control"), {})
        checks.extend(
            [
                _check("ucc_train_lifecycle_change_control_required_by_reset", bool(change), "Change Control evidence exists when reset history exists."),
                _check("ucc_train_lifecycle_change_control_runtime_binding", change.get("zip_sha256") == external_change.get("runtime", {}).get("zip_sha256") and external_change.get("runtime", {}).get("status") == "passed", "Change Control evidence matches runtime verification."),
            ]
        )
    return checks


def _document_binding_checks(
    manifest: ImplementationDocument,
    report: ImplementationDocument,
    succession: ImplementationDocument,
    coverage: ImplementationDocument,
    archive_history: ImplementationDocument,
    readiness: ImplementationDocument,
    gap_plan: ImplementationDocument,
    evidence_index: ImplementationDocument,
    ledger: list[ImplementationDocument],
) -> list[ImplementationDocument]:
    source = _as_document(manifest.get("source"))
    return [
        _check("ucc_train_lifecycle_report_hash_binding", source.get("report_hash") == report.get("integrity_hash"), "Manifest binds report."),
        _check("ucc_train_lifecycle_succession_hash_binding", source.get("succession_hash") == succession.get("integrity_hash"), "Manifest binds succession map."),
        _check("ucc_train_lifecycle_coverage_hash_binding", source.get("coverage_hash") == coverage.get("integrity_hash"), "Manifest binds reset coverage."),
        _check("ucc_train_lifecycle_archive_history_hash_binding", source.get("archive_history_hash") == archive_history.get("integrity_hash"), "Manifest binds archive history ledger."),
        _check("ucc_train_lifecycle_readiness_hash_binding", source.get("readiness_hash") == readiness.get("integrity_hash"), "Manifest binds readiness assertion."),
        _check("ucc_train_lifecycle_gap_plan_hash_binding", source.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Manifest binds gap plan."),
        _check("ucc_train_lifecycle_evidence_index_hash_binding", source.get("evidence_index_hash") == evidence_index.get("integrity_hash"), "Manifest binds evidence index."),
        _check("ucc_train_lifecycle_ledger_hash_binding", source.get("ledger_hash") == stable_hash(ledger), "Manifest binds lifecycle ledger."),
        _check("ucc_train_lifecycle_source_hash_binding", manifest.get("source_hash") == report.get("source_hash") == succession.get("source_hash") == coverage.get("source_hash") == archive_history.get("source_hash") == readiness.get("source_hash") == gap_plan.get("source_hash") == evidence_index.get("source_hash"), "Source hash is consistent across lifecycle documents."),
    ]


def _ledger_chain_checks(ledger: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks = []
    previous = ""
    for index, event in enumerate(ledger):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"ucc_train_lifecycle_ledger_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "Ledger event payload hash is valid."))
        checks.append(_check(f"ucc_train_lifecycle_ledger_{index:03d}_event_hash", event.get("event_hash") == event_hash, "Ledger event hash is valid."))
        checks.append(_check(f"ucc_train_lifecycle_ledger_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "Ledger hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    declared = {str(row.get("path") or "") for row in files}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    checks.append(_check("ucc_train_lifecycle_manifest_files_fixed", declared == expected_files, "Manifest files match fixed Lifecycle layout.", {"missing": sorted(expected_files - declared), "extra": sorted(declared - expected_files)}))
    mismatches = []
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in names:
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        data = archive.read(rel)
        if row.get("size_bytes") != len(data) or row.get("sha256") != _sha256_bytes(data):
            mismatches.append({"path": rel, "reason": "hash_or_size"})
    checks.append(_check("ucc_train_lifecycle_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".jsonl", ".txt", ".md")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                leaks.append(name)
                break
    return _check("ucc_train_lifecycle_redaction_scan", not leaks, "Lifecycle text files do not contain obvious secrets or local paths.", {"leaks": sorted(set(leaks))})


def _train_history_from_zip(path: Path) -> list[ImplementationDocument]:
    try:
        with zipfile.ZipFile(path) as archive:
            text = archive.read("train-history.jsonl").decode("utf-8")
    except Exception:
        return []
    return _parse_jsonl(text)


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    all_checks = [*checks, *extra]
    blockers = [check["check_id"] for check in all_checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in all_checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION,
        "status": status,
        "summary": summary,
        "checks": all_checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, severity: str = "blocking") -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[ImplementationDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    path = Path(name)
    lowered = name.lower()
    return bool(name and not path.is_absolute() and ".." not in path.parts and not lowered.startswith(".musicforge/") and "/.musicforge/" not in lowered)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
