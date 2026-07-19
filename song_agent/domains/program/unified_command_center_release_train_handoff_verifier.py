# ruff: noqa: E402,F401
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
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package


UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_handoff"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_handoff_verification"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION = 1

BASE_REQUIRED_ENTRIES = {
    "manifest.json",
    "file-index.json",
    "README.txt",
    "handoff-report.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "recipient-guide.md",
    "gap-plan.json",
    "external-evidence-manifest.json",
    "response-summary.json",
    "accepted-evidence-summary.json",
    "handoff-history.jsonl",
}
SIGNED_ENTRIES = {"handoff-signoff.json", "handoff-signoff-binding-summary.json"}
REQUIRED_ENTRIES = BASE_REQUIRED_ENTRIES | SIGNED_ENTRIES

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


def verify_unified_command_center_release_train_handoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_lifecycle: bool = False,
    require_signed: bool = False,
    require_accepted: bool = False,
    external_evidence_manifest_path: Path | str | None = None,
    train_archive_path: Path | str | None = None,
    train_verification_report_path: Path | str | None = None,
    train_archive_verification_report_path: Path | str | None = None,
    train_signoff_binding_path: Path | str | None = None,
    change_control_zip_path: Path | str | None = None,
    change_control_verification_report_path: Path | str | None = None,
    reset_proof_paths: list[Path | str] | None = None,
    lifecycle_zip_path: Path | str | None = None,
    lifecycle_verification_report_path: Path | str | None = None,
    handoff_signoff_binding_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    train_verification_report_path = train_verification_report_path or train_archive_verification_report_path
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_train_handoff_zip_exists", False, "Handoff ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_train_handoff_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            signed_present = bool(SIGNED_ENTRIES & name_set)
            expected_entries = REQUIRED_ENTRIES if (require_signed or signed_present) else BASE_REQUIRED_ENTRIES
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - expected_entries)
            missing = sorted(expected_entries - name_set)
            checks.extend(
                [
                    _check("ucc_train_handoff_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("ucc_train_handoff_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("ucc_train_handoff_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("ucc_train_handoff_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("ucc_train_handoff_no_nested_zip", not nested, "Handoff ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("ucc_train_handoff_allowed_entries", not extra, "Handoff ZIP contains only fixed entries.", {"extra": extra}),
                    _check("ucc_train_handoff_required_entries", not missing, "Handoff ZIP contains required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            file_index = _read_json_entry(archive, "file-index.json")
            report = _read_json_entry(archive, "handoff-report.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            response_summary = _read_json_entry(archive, "response-summary.json")
            accepted_summary = _read_json_entry(archive, "accepted-evidence-summary.json")
            history = _parse_jsonl(archive.read("handoff-history.jsonl").decode("utf-8"))
            signoff = _read_json_entry(archive, "handoff-signoff.json") if "handoff-signoff.json" in name_set else {}
            binding = _read_json_entry(archive, "handoff-signoff-binding-summary.json") if "handoff-signoff-binding-summary.json" in name_set else {}
            summary.update({"handoff_id": report.get("handoff_id"), "train_id": report.get("train_id"), "manifest_hash": manifest.get("integrity_hash"), "status": report.get("status"), "readiness": report.get("summary", {}).get("readiness"), "signed": signoff.get("status") == "signed"})

            checks.extend(_manifest_checks(archive, manifest, name_set, expected_entries))
            checks.extend(_file_index_checks(file_index, expected_entries - {"manifest.json", "file-index.json"}))
            checks.extend(
                [
                    _check("ucc_train_handoff_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("ucc_train_handoff_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("ucc_train_handoff_manifest_integrity", manifest),
                ("ucc_train_handoff_file_index_integrity", file_index),
                ("ucc_train_handoff_report_integrity", report),
                ("ucc_train_handoff_inventory_integrity", inventory),
                ("ucc_train_handoff_readiness_integrity", readiness),
                ("ucc_train_handoff_gap_plan_integrity", gap_plan),
                ("ucc_train_handoff_external_manifest_integrity", external_manifest),
                ("ucc_train_handoff_response_summary_integrity", response_summary),
                ("ucc_train_handoff_accepted_summary_integrity", accepted_summary),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            if signoff:
                checks.append(_check("ucc_train_handoff_signoff_integrity", _integrity_ok(signoff), "Handoff signoff integrity hash is valid."))
            if binding:
                checks.append(_check("ucc_train_handoff_signoff_binding_integrity", _integrity_ok(binding), "Handoff signoff binding integrity hash is valid."))
            checks.extend(_document_binding_checks(manifest, file_index, report, inventory, readiness, gap_plan, external_manifest, response_summary, accepted_summary, signoff, binding))
            checks.extend(_history_checks(history, signoff))
            checks.extend(_signoff_binding_checks(binding, signoff, history, report, inventory, readiness, external_manifest, accepted_summary, require=require_signed))
            checks.extend(_external_signoff_binding_checks(handoff_signoff_binding_path, binding, signoff, history, report, inventory, readiness, external_manifest, accepted_summary, require=require_signed))

            external_train = _external_train_state(
                require=require_current,
                train_archive_path=train_archive_path,
                train_verification_report_path=train_verification_report_path,
                train_signoff_binding_path=train_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
            )
            checks.extend(external_train.pop("checks"))
            reset_count = int(report.get("summary", {}).get("reset_count") or 0)
            change_required = reset_count > 0
            external_change = _external_change_state(
                require=change_required,
                change_control_zip_path=change_control_zip_path,
                change_control_verification_report_path=change_control_verification_report_path,
                train_archive_path=train_archive_path,
                train_verification_report_path=train_verification_report_path,
                train_signoff_binding_path=train_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
                reset_proof_paths=reset_proof_paths or [],
            )
            checks.extend(external_change.pop("checks"))
            external_lifecycle = _external_lifecycle_state(
                require=require_lifecycle or require_current,
                lifecycle_zip_path=lifecycle_zip_path,
                lifecycle_verification_report_path=lifecycle_verification_report_path,
                train_archive_path=train_archive_path,
                train_verification_report_path=train_verification_report_path,
                train_signoff_binding_path=train_signoff_binding_path,
                external_evidence_manifest_path=external_evidence_manifest_path,
                change_control_zip_path=change_control_zip_path,
                change_control_verification_report_path=change_control_verification_report_path,
                reset_proof_paths=reset_proof_paths or [],
            )
            checks.extend(external_lifecycle.pop("checks"))
            checks.extend(_external_semantic_checks(report, inventory, readiness, external_manifest, external_train, external_change, external_lifecycle))
            accepted_external = _accepted_evidence_state(accepted_evidence_dir, require=require_accepted)
            checks.extend(accepted_external.pop("checks"))
            checks.extend(_accepted_semantic_checks(accepted_summary, readiness, accepted_external, require=require_accepted))
            checks.append(_redaction_check(archive, names))
            if require_signed:
                checks.append(_check("ucc_train_handoff_require_signed", signoff.get("status") == "signed", "Handoff is signed."))
            if require_accepted:
                checks.append(_check("ucc_train_handoff_require_accepted", readiness.get("summary", {}).get("acceptance_status") == "passed", "Handoff acceptance quorum passed."))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_train_handoff_zip_readable", False, "Handoff ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def _external_train_state(
    *,
    require: bool,
    train_archive_path: Path | str | None,
    train_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks}
    if not require:
        return state
    if not train_archive_path or not train_verification_report_path or not train_signoff_binding_path or not external_evidence_manifest_path:
        checks.append(_check("ucc_train_handoff_current_train_external_required", False, "Current Train archive, verification report, signoff binding, and evidence manifest are required."))
        return state
    zip_path = Path(train_archive_path)
    report_path = Path(train_verification_report_path)
    binding_path = Path(train_signoff_binding_path)
    manifest_path = Path(external_evidence_manifest_path)
    checks.extend(
        [
            _check("ucc_train_handoff_current_train_zip_exists", zip_path.exists(), "Current Train archive exists."),
            _check("ucc_train_handoff_current_train_verification_exists", report_path.exists(), "Current Train verification report exists."),
            _check("ucc_train_handoff_current_train_binding_exists", binding_path.exists(), "Current Train signoff binding exists."),
            _check("ucc_train_handoff_current_train_evidence_manifest_exists", manifest_path.exists(), "External evidence manifest exists."),
        ]
    )
    if not zip_path.exists() or not report_path.exists() or not binding_path.exists() or not manifest_path.exists():
        return state
    external = read_json(report_path)
    runtime = verify_unified_command_center_release_train_package(zip_path, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=binding_path)
    checks.extend(
        [
            _check("ucc_train_handoff_current_train_external_integrity", _integrity_ok(external), "Current Train verification report integrity is valid."),
            _check("ucc_train_handoff_current_train_runtime_passed", runtime.get("status") == "passed", "Current Train runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_handoff_current_train_external_passed", external.get("status") == "passed", "Current Train external verification passed."),
            _check("ucc_train_handoff_current_train_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Current Train ZIP hash matches runtime and report."),
            _check("ucc_train_handoff_current_train_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Current Train manifest hash matches runtime and report."),
        ]
    )
    state.update({"runtime": runtime, "external_report": external, "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external)})
    return state


def _external_change_state(
    *,
    require: bool,
    change_control_zip_path: Path | str | None,
    change_control_verification_report_path: Path | str | None,
    train_archive_path: Path | str | None,
    train_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
    reset_proof_paths: list[Path | str],
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks}
    if not require:
        return state
    if not change_control_zip_path or not change_control_verification_report_path:
        checks.append(_check("ucc_train_handoff_change_control_external_required", False, "Change Control ZIP and verification report are required when reset history exists."))
        return state
    zip_path = Path(change_control_zip_path)
    report_path = Path(change_control_verification_report_path)
    checks.extend([_check("ucc_train_handoff_change_control_zip_exists", zip_path.exists(), "Change Control ZIP exists."), _check("ucc_train_handoff_change_control_verification_exists", report_path.exists(), "Change Control verification report exists.")])
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
        train_archive_verification_report_path=train_verification_report_path,
        train_signoff_binding_path=train_signoff_binding_path,
        external_evidence_manifest_path=external_evidence_manifest_path,
        reset_proof_path=latest_proof,
    )
    checks.extend(
        [
            _check("ucc_train_handoff_change_control_external_integrity", _integrity_ok(external), "Change Control verification report integrity is valid."),
            _check("ucc_train_handoff_change_control_runtime_passed", runtime.get("status") == "passed", "Change Control runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_handoff_change_control_external_passed", external.get("status") == "passed", "Change Control external verification passed."),
            _check("ucc_train_handoff_change_control_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Change Control ZIP hash matches runtime and report."),
            _check("ucc_train_handoff_change_control_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Change Control manifest hash matches runtime and report."),
        ]
    )
    state.update({"runtime": runtime, "external_report": external, "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external)})
    return state


def _external_lifecycle_state(
    *,
    require: bool,
    lifecycle_zip_path: Path | str | None,
    lifecycle_verification_report_path: Path | str | None,
    train_archive_path: Path | str | None,
    train_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
    change_control_zip_path: Path | str | None,
    change_control_verification_report_path: Path | str | None,
    reset_proof_paths: list[Path | str],
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks}
    if not require:
        return state
    if not lifecycle_zip_path or not lifecycle_verification_report_path:
        checks.append(_check("ucc_train_handoff_lifecycle_external_required", False, "Lifecycle ZIP and verification report are required."))
        return state
    zip_path = Path(lifecycle_zip_path)
    report_path = Path(lifecycle_verification_report_path)
    checks.extend([_check("ucc_train_handoff_lifecycle_zip_exists", zip_path.exists(), "Lifecycle ZIP exists."), _check("ucc_train_handoff_lifecycle_verification_exists", report_path.exists(), "Lifecycle verification report exists.")])
    if not zip_path.exists() or not report_path.exists():
        return state
    external = read_json(report_path)
    runtime = verify_unified_command_center_release_train_lifecycle_package(
        zip_path,
        strict=True,
        require_current_train=True,
        require_change_control=bool(change_control_zip_path),
        train_archive_path=train_archive_path,
        train_archive_verification_report_path=train_verification_report_path,
        train_signoff_binding_path=train_signoff_binding_path,
        external_evidence_manifest_path=external_evidence_manifest_path,
        change_control_zip_path=change_control_zip_path,
        change_control_verification_report_path=change_control_verification_report_path,
        reset_proof_paths=reset_proof_paths,
    )
    checks.extend(
        [
            _check("ucc_train_handoff_lifecycle_external_integrity", _integrity_ok(external), "Lifecycle verification report integrity is valid."),
            _check("ucc_train_handoff_lifecycle_runtime_passed", runtime.get("status") == "passed", "Lifecycle runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_handoff_lifecycle_external_passed", external.get("status") == "passed", "Lifecycle external verification passed."),
            _check("ucc_train_handoff_lifecycle_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Lifecycle ZIP hash matches runtime and report."),
            _check("ucc_train_handoff_lifecycle_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Lifecycle manifest hash matches runtime and report."),
        ]
    )
    state.update({"runtime": runtime, "external_report": external, "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external)})
    return state


def _accepted_evidence_state(path: Path | str | None, *, require: bool) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks, "items": []}
    if not path:
        if require:
            checks.append(_check("ucc_train_handoff_accepted_evidence_external_required", False, "Accepted evidence directory is required."))
        return state
    root = Path(path)
    checks.append(_check("ucc_train_handoff_accepted_evidence_dir_exists", root.exists() and root.is_dir(), "Accepted evidence directory exists."))
    if not root.exists() or not root.is_dir():
        return state
    files = sorted(root.glob("*/accepted-evidence.json"))
    if not files and (root / "accepted-evidence.json").exists():
        files = [root / "accepted-evidence.json"]
    checks.append(_check("ucc_train_handoff_accepted_evidence_present", bool(files) or not require, "Accepted evidence is present."))
    rows = []
    for index, file_path in enumerate(files):
        row = _accepted_evidence_row_from_dir(file_path.parent)
        ok = row.get("status") == "passed"
        checks.append(_check(f"ucc_train_handoff_accepted_evidence_{index:03d}_integrity", ok, "Accepted evidence integrity and package type are valid."))
        if row.get("failures"):
            checks.append(_check(f"ucc_train_handoff_accepted_evidence_{index:03d}_sidecar_binding", False, "Accepted evidence matches response, verification, and binding sidecars.", {"failures": row.get("failures")}))
        rows.append(row)
    state["items"] = rows
    return state


def _accepted_semantic_checks(accepted_summary: ImplementationDocument, readiness: ImplementationDocument, external: ImplementationDocument, *, require: bool) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    items = [row for row in accepted_summary.get("items", []) if isinstance(row, dict)]
    external_items = [row for row in external.get("items", []) if isinstance(row, dict)]
    summary_rows = sorted((_accepted_row_projection(row) for row in items), key=lambda row: str(row.get("response_id") or ""))
    external_rows = sorted((_accepted_row_projection(row) for row in external_items), key=lambda row: str(row.get("response_id") or ""))
    checks.append(_check("ucc_train_handoff_accepted_evidence_external_match", (not require and not external_rows) or summary_rows == external_rows, "Accepted evidence summary matches external response-bound accepted evidence.", {"summary": summary_rows, "external": external_rows}))
    failed_external = [row for row in external_rows if row.get("status") != "passed"]
    checks.append(_check("ucc_train_handoff_accepted_evidence_external_sidecars_valid", (not require) or not failed_external, "External accepted evidence sidecars are valid.", {"failed": failed_external}))
    accepted_count = len([row for row in external_rows if row.get("status") == "passed"]) if external_rows else len([row for row in summary_rows if row.get("status") == "passed"])
    checks.append(_check("ucc_train_handoff_accepted_evidence_quorum_count", (not require) or accepted_count >= 1, "Accepted evidence quorum count is satisfied.", {"accepted_count": accepted_count}))
    if require:
        checks.append(_check("ucc_train_handoff_accepted_readiness_status", readiness.get("summary", {}).get("acceptance_status") == "passed", "Readiness matrix records accepted quorum."))
    return checks


def _accepted_evidence_row_from_dir(response_dir: Path) -> ImplementationDocument:
    accepted = _read_optional_json(response_dir / "accepted-evidence.json")
    response = _read_optional_json(response_dir / "response.json")
    verification = _read_optional_json(response_dir / "response-verification-report.json")
    binding = _read_optional_json(response_dir / "response-binding-summary.json")
    response_public = _response_public_summary(response) if response else {}
    expected_binding = _response_binding_summary(response, verification) if response and verification else {}
    evidence_binding = _as_document(accepted.get("response_binding"))
    failures: list[str] = []

    def require(check_id: str, passed: bool) -> None:
        if not passed:
            failures.append(check_id)

    require("accepted_evidence_integrity", _integrity_ok(accepted) and accepted.get("package_type") == "musicforge_release_train_handoff_accepted_evidence")
    require("accepted_evidence_response_integrity", _integrity_ok(response) and response.get("package_type") == "musicforge_release_train_handoff_response")
    require("accepted_evidence_response_verification_integrity", _integrity_ok(verification) and verification.get("package_type") == "musicforge_release_train_handoff_response_verification")
    require("accepted_evidence_response_verification_passed", verification.get("status") == "passed")
    require("accepted_evidence_response_decision", response.get("decision") == "accepted")
    require("accepted_evidence_binding_integrity", _integrity_ok(binding) and binding.get("package_type") == "musicforge_release_train_handoff_response_binding_summary")
    require("accepted_evidence_binding_matches_response", bool(expected_binding) and binding == expected_binding)
    require("accepted_evidence_public_summary_matches_response", accepted.get("public_summary") == response_public)
    require("accepted_evidence_embedded_binding_matches_sidecar", evidence_binding == binding)
    require("accepted_evidence_response_id", accepted.get("response_id") == response.get("response_id") == verification.get("response_id") == binding.get("response_id"))
    require("accepted_evidence_handoff_id", accepted.get("handoff_id") == response.get("handoff_id") == binding.get("handoff_id"))
    require("accepted_evidence_train_id", accepted.get("train_id") == response.get("train_id") == binding.get("train_id"))

    return {
        "response_id": accepted.get("response_id") or response.get("response_id") or response_dir.name,
        "accepted_evidence_hash": accepted.get("integrity_hash"),
        "response_hash": response.get("integrity_hash"),
        "response_verification_report_hash": verification.get("integrity_hash"),
        "response_binding_hash": binding.get("integrity_hash"),
        "reviewer_role": response_public.get("reviewer_role"),
        "organization": response_public.get("organization"),
        "decision": response_public.get("decision"),
        "reviewed_at": response_public.get("reviewed_at"),
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def _accepted_row_projection(row: ImplementationDocument) -> ImplementationDocument:
    return {
        "response_id": row.get("response_id"),
        "accepted_evidence_hash": row.get("accepted_evidence_hash"),
        "response_hash": row.get("response_hash"),
        "response_verification_report_hash": row.get("response_verification_report_hash"),
        "response_binding_hash": row.get("response_binding_hash"),
        "reviewer_role": row.get("reviewer_role"),
        "organization": row.get("organization"),
        "decision": row.get("decision"),
        "reviewed_at": row.get("reviewed_at"),
        "status": row.get("status"),
    }


def _response_public_summary(response: ImplementationDocument) -> ImplementationDocument:
    reviewer = _as_document(response.get("reviewer"))
    return {
        "reviewer_id": reviewer.get("reviewer_id"),
        "reviewer_name": sanitize_sensitive_text(str(reviewer.get("name") or "")) or None,
        "organization": sanitize_sensitive_text(str(reviewer.get("organization") or "")) or None,
        "reviewer_role": sanitize_sensitive_text(str(reviewer.get("role") or "")) or None,
        "decision": response.get("decision"),
        "reviewed_at": response.get("reviewed_at"),
    }


def _response_binding_summary(response: ImplementationDocument, verification: ImplementationDocument) -> ImplementationDocument:
    doc = {
        "schema_version": 1,
        "package_type": "musicforge_release_train_handoff_response_binding_summary",
        "response_id": response.get("response_id"),
        "handoff_id": response.get("handoff_id"),
        "train_id": response.get("train_id"),
        "raw_response_sha256": response.get("integrity_hash"),
        "payload_hash": response.get("payload_hash"),
        "verification_report_hash": verification.get("integrity_hash"),
        "handoff_zip_sha256": response.get("handoff_zip_sha256"),
        "handoff_manifest_hash": response.get("handoff_manifest_hash"),
        "handoff_source_hash": response.get("handoff_source_hash"),
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _external_semantic_checks(report: ImplementationDocument, inventory: ImplementationDocument, readiness: ImplementationDocument, external_manifest: ImplementationDocument, train: ImplementationDocument, change: ImplementationDocument, lifecycle: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    source = _as_document(report.get("source"))
    checks.extend(
        [
            _check("ucc_train_handoff_source_train_zip_sha256", not train.get("zip_sha256") or source.get("current_train_zip_sha256") == train.get("zip_sha256"), "Report source binds current train ZIP."),
            _check("ucc_train_handoff_source_lifecycle_zip_sha256", not lifecycle.get("zip_sha256") or source.get("lifecycle_zip_sha256") == lifecycle.get("zip_sha256"), "Report source binds lifecycle ZIP."),
            _check("ucc_train_handoff_source_external_manifest_hash", source.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Report source binds external evidence manifest."),
            _check("ucc_train_handoff_inventory_status", inventory.get("summary", {}).get("failed") == 0 and inventory.get("summary", {}).get("missing") == 0, "Evidence inventory has no failed or missing required evidence."),
            _check("ucc_train_handoff_readiness_status", readiness.get("summary", {}).get("status") in {"ready", "manual_required"}, "Readiness matrix is ready or waiting for external acceptance."),
        ]
    )
    if int(report.get("summary", {}).get("reset_count") or 0) > 0:
        checks.append(_check("ucc_train_handoff_change_control_required_passed", change.get("runtime", {}).get("status") == "passed", "Change Control is verified when resets exist."))
    return checks


from song_agent.domains.program import v142_uccrthv_readiness as _v142_uccrthv_readiness
from song_agent.domains.program.v142_uccrthv_readiness import (
    _document_binding_checks,
    _signoff_binding_checks,
    _external_signoff_binding_checks,
    _history_checks,
    _manifest_checks,
    _file_index_checks,
    _finish,
    write_unified_command_center_release_train_handoff_verification_report,
    unified_command_center_release_train_handoff_verification_exit_code,
    _check,
    _read_json_entry,
    _read_optional_json,
    _parse_jsonl,
    _integrity_hash,
    _integrity_ok,
    _sha256_path,
    _sha256_bytes,
    _is_safe_entry,
    _redaction_check,
    _safe_check_key,
    _report_manifest_hash,
)

_v142_uccrthv_readiness.bind_globals(globals())
