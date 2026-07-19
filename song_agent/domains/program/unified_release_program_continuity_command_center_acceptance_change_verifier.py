# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
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
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_acceptance_package as verify_unified_release_program_continuity_command_center_acceptance_package


UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION = 1
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_CONTROL_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_archive"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_request"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_APPROVAL_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_approval"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_RESET_PROOF_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_LIFECYCLE_REPORT_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_lifecycle_report"

RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"

FIXED_ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "state.json",
    "request-index.json",
    "reset-index.json",
    "generation.json",
    "lifecycle.json",
    "events.jsonl",
}

def verify_unified_release_program_continuity_command_center_acceptance_change_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current_acceptance: bool = False,
    acceptance_archive_path: Path | str | None = None,
    acceptance_verification_report_path: Path | str | None = None,
    acceptance_signoff_binding_path: Path | str | None = None,
    previous_acceptance_root: Path | str | None = None,
    require_reset_proofs: bool = False,
    max_zip_size_mb: int = 256,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 2000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpcccacc_kernel",
                required_entries=frozenset(FIXED_ARCHIVE_ENTRIES),
                optional_entries=frozenset(),
                allowed_entry_patterns=(
                    r"cr/[A-Za-z0-9_.-]+/(?:request|binding|approval)\.json",
                    r"rp/[A-Za-z0-9_.-]+/(?:proof|binding)\.json",
                    r"gen/g[0-9]{6}/(?:verification|signoff-binding|source)\.json",
                ),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpcccacc_zip_exists", False, "Command Center Receiver Acceptance Change Control Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpcccacc_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpcccacc_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            request_ids = {
                name.split("/")[1]
                for name in name_set
                if name.startswith("cr/") and name.endswith("/request.json")
            }
            reset_ids = {
                name.split("/")[1]
                for name in name_set
                if name.startswith("rp/") and name.endswith("/proof.json")
            }
            generation_ids = {
                int(name.split("/")[1].lstrip("g"))
                for name in name_set
                if name.startswith("gen/g") and name.endswith("/source.json")
            }
            expected = set(FIXED_ARCHIVE_ENTRIES)
            for request_id in request_ids:
                expected.add(f"cr/{request_id}/request.json")
                expected.add(f"cr/{request_id}/binding.json")
                if f"cr/{request_id}/approval.json" in name_set:
                    expected.add(f"cr/{request_id}/approval.json")
            for reset_id in reset_ids:
                expected.add(f"rp/{reset_id}/proof.json")
                expected.add(f"rp/{reset_id}/binding.json")
            for generation in generation_ids:
                prefix = f"gen/g{generation:06d}"
                expected.update(
                    {
                        f"{prefix}/verification.json",
                        f"{prefix}/signoff-binding.json",
                        f"{prefix}/source.json",
                    }
                )
            extra = sorted(name_set - expected)
            missing = sorted(expected - name_set)
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpcccacc_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpcccacc_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpcccacc_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpcccacc_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpcccacc_no_nested_zip", not nested, "Command Center Receiver Acceptance Change Control Archive does not embed ZIP files.", {"nested": nested}),
                    _check("urpcccacc_allowed_entries", not extra, "Archive contains only fixed/patterned entries.", {"extra": extra}),
                    _check("urpcccacc_required_entries", not missing, "Archive contains required entries.", {"missing": missing}),
                ]
            )
            if _has_blocking_failures(checks):
                return _finish(checks, summary)

            manifest = _as_document(_read_json_entry(archive, "manifest.json"))
            state = _as_document(_read_json_entry(archive, "state.json"))
            request_index = _as_document(_read_json_entry(archive, "request-index.json"))
            reset_index = _as_document(_read_json_entry(archive, "reset-index.json"))
            current_generation_doc = _as_document(_read_json_entry(archive, "generation.json"))
            lifecycle = _as_document(_read_json_entry(archive, "lifecycle.json"))
            events = _parse_jsonl(archive.read("events.jsonl").decode("utf-8"))
            requests = {request_id: _request_bundle(archive, request_id) for request_id in request_ids}
            resets = {reset_id: _reset_bundle(archive, reset_id) for reset_id in reset_ids}
            generation_docs = {generation_id: _generation_bundle(archive, generation_id) for generation_id in generation_ids}
            summary.update(
                {
                    "program_id": state.get("program_id") or manifest.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": lifecycle.get("status"),
                    "reset_count": (reset_index.get("summary") or {}).get("reset_count"),
                    "current_generation": current_generation_doc.get("generation"),
                }
            )

            checks.extend(_manifest_checks(archive, manifest, name_set, expected))
            for check_id, doc in (
                ("urpcccacc_manifest_integrity", manifest),
                ("urpcccacc_state_integrity", state),
                ("urpcccacc_request_index_integrity", request_index),
                ("urpcccacc_reset_index_integrity", reset_index),
                ("urpcccacc_current_generation_integrity", current_generation_doc),
                ("urpcccacc_lifecycle_integrity", lifecycle),
            ):
                checks.append(_check(check_id, _integrity_ok(_as_document(doc)), f"{check_id} hash is valid."))
            checks.extend(
                [
                    _check("urpcccacc_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpcccacc_lifecycle_package_type", lifecycle.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_LIFECYCLE_REPORT_PACKAGE_TYPE, "Lifecycle report package type is valid."),
                ]
            )
            checks.extend(_history_checks(events))
            checks.extend(_request_checks(requests))
            checks.extend(_reset_checks(resets, requests, events, reset_index))
            checks.extend(command_center_acceptance_change_lifecycle_semantic_checks(events, resets))
            checks.extend(
                command_center_acceptance_change_previous_evidence_checks(
                    resets,
                    previous_acceptance_root,
                    require=require_reset_proofs,
                )
            )
            checks.extend(_index_checks(request_index, reset_index, requests, resets, lifecycle, events))
            checks.extend(_current_generation_checks(current_generation_doc, state, resets, events))
            checks.extend(_generation_checks(generation_docs, current_generation_doc, state, resets))
            checks.extend(_document_binding_checks(manifest, state, request_index, reset_index, current_generation_doc, lifecycle))
            checks.extend(_current_acceptance_checks(state, acceptance_archive_path, acceptance_verification_report_path, acceptance_signoff_binding_path, require=require_current_acceptance))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpcccacc_zip_readable", False, "Command Center Receiver Acceptance Change Control Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_command_center_acceptance_change_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_continuity_command_center_acceptance_change_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _request_bundle(archive: zipfile.ZipFile, request_id: str) -> ImplementationDocument:
    bundle = {
        "request": _read_json_entry(archive, f"cr/{request_id}/request.json"),
        "binding": _read_json_entry(archive, f"cr/{request_id}/binding.json"),
        "approval": {},
    }
    approval_name = f"cr/{request_id}/approval.json"
    if approval_name in archive.namelist():
        bundle["approval"] = _read_json_entry(archive, approval_name)
    return bundle


def _reset_bundle(archive: zipfile.ZipFile, reset_id: str) -> ImplementationDocument:
    return {
        "proof": _read_json_entry(archive, f"rp/{reset_id}/proof.json"),
        "binding": _read_json_entry(archive, f"rp/{reset_id}/binding.json"),
    }


def _generation_bundle(archive: zipfile.ZipFile, generation: int) -> ImplementationDocument:
    prefix = f"gen/g{generation:06d}"
    return {
        "verification_summary": _read_json_entry(archive, f"{prefix}/verification.json"),
        "signoff_binding_summary": _read_json_entry(archive, f"{prefix}/signoff-binding.json"),
        "source_summary": _read_json_entry(archive, f"{prefix}/source.json"),
    }


def _request_checks(requests: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    for request_id, bundle in sorted(requests.items()):
        request = bundle["request"]
        approval = bundle.get("approval") or {}
        binding = bundle["binding"]
        prefix = f"urpcccacc_request_{_safe_check_key(request_id)}"
        checks.extend(
            [
                _check(f"{prefix}_package_type", request.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, "Change request package type is valid."),
                _check(f"{prefix}_integrity", _integrity_ok(request), "Change request integrity is valid."),
                _check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Change request binding integrity is valid."),
                _check(f"{prefix}_change_type", request.get("change_type") == RESET_CHANGE_TYPE, "Change request is reset-scoped."),
                _check(f"{prefix}_allowed_action", list(request.get("allowed_actions") or []) == [RESET_ACTION], "Change request explicitly and exclusively allows reset."),
                _check(f"{prefix}_binding_request_hash", binding.get("request_hash") in {request.get("integrity_hash"), request.get("approved_request_hash")}, "Binding references the approved change request."),
                _check(f"{prefix}_binding_payload_hash", binding.get("request_payload_hash") == request.get("payload_hash"), "Binding preserves the Change Request payload hash."),
                _check(f"{prefix}_binding_target", binding.get("target") == request.get("target"), "Binding preserves change request target."),
                _check(f"{prefix}_binding_source", binding.get("source") == request.get("source"), "Binding preserves change request source."),
            ]
        )
        if approval:
            checks.extend(
                [
                    _check(f"{prefix}_approval_package_type", approval.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_APPROVAL_PACKAGE_TYPE, "Approval package type is valid."),
                    _check(f"{prefix}_approval_integrity", _integrity_ok(approval), "Approval integrity is valid."),
                    _check(f"{prefix}_approval_status", approval.get("status") == "approved", "Approval status is approved."),
                    _check(f"{prefix}_approval_identity", approval.get("program_id") == request.get("program_id") and approval.get("change_request_id") == request_id, "Approval identity matches request."),
                    _check(f"{prefix}_approval_action", list(approval.get("approved_actions") or []) == [RESET_ACTION], "Approval explicitly and exclusively allows reset."),
                    _check(f"{prefix}_approval_payload_hash", approval.get("request_payload_hash") == request.get("payload_hash"), "Approval preserves the Change Request payload hash."),
                    _check(f"{prefix}_approval_binding", approval.get("target") == request.get("target") and approval.get("source") == request.get("source"), "Approval binds request source and target."),
                    _check(f"{prefix}_binding_approval", binding.get("approval_hash") == approval.get("integrity_hash"), "Change Request binding references approval."),
                ]
            )
    return checks


def _reset_checks(resets: dict[str, ImplementationDocument], requests: dict[str, ImplementationDocument], events: list[ImplementationDocument], reset_index: ImplementationDocument) -> list[ImplementationDocument]:
    return command_center_acceptance_change_reset_semantic_checks(resets, requests, events, reset_index)


def command_center_acceptance_change_reset_semantic_checks(resets: dict[str, DomainDocument], requests: dict[str, DomainDocument], events: list[DomainDocument], reset_index: DomainDocument) -> list[DomainDocument]:
    checks: list[ImplementationDocument] = []
    reset_event_by_hash = {row.get("reset_event_hash"): row for row in events if row.get("event_type") == "receiver_acceptance_signoff_reset_applied"}
    reset_index_rows = {
        str(row.get("reset_id") or ""): row
        for row in (_as_list(reset_index.get("items")))
        if isinstance(row, dict)
    }
    used_requests: set[str] = set()
    for reset_id, bundle in sorted(resets.items()):
        proof = bundle["proof"]
        binding = bundle["binding"]
        request_id = str(proof.get("change_request_id") or "")
        request_bundle = requests.get(request_id) or {}
        request = request_bundle.get("request") or {}
        approval = request_bundle.get("approval") or {}
        request_binding = request_bundle.get("binding") or {}
        target = _as_document(request.get("target"))
        source = _as_document(request.get("source"))
        event = reset_event_by_hash.get(proof.get("reset_event_hash")) or {}
        submitted_event = next(
            (
                row
                for row in events
                if row.get("event_type") == "receiver_acceptance_change_request_submitted"
                and row.get("change_request_id") == request_id
            ),
            {},
        )
        approved_event = next(
            (
                row
                for row in events
                if row.get("event_type") == "receiver_acceptance_change_request_approved"
                and row.get("change_request_id") == request_id
            ),
            {},
        )
        reset_row = reset_index_rows.get(reset_id) or {}
        prefix = f"urpcccacc_reset_{_safe_check_key(reset_id)}"
        duplicate = request_id in used_requests
        used_requests.add(request_id)
        checks.extend(
            [
                _check(f"{prefix}_proof_package_type", proof.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_RESET_PROOF_PACKAGE_TYPE, "Reset proof package type is valid."),
                _check(f"{prefix}_proof_integrity", _integrity_ok(proof), "Reset proof integrity is valid."),
                _check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Reset binding integrity is valid."),
                _check(f"{prefix}_request_exists", bool(request), "Reset proof references an archived request."),
                _check(f"{prefix}_request_single_use", not duplicate, "Change request is used by only one reset proof."),
                _check(f"{prefix}_request_applied", request.get("status") == "applied", "Change request is marked applied."),
                _check(f"{prefix}_request_hash", proof.get("request_hash") in {request.get("integrity_hash"), request.get("approved_request_hash")}, "Reset proof binds approved request."),
                _check(f"{prefix}_approval_hash", proof.get("approval_hash") == approval.get("integrity_hash"), "Reset proof binds approval."),
                _check(f"{prefix}_cr_binding_hash", proof.get("cr_binding_report_hash") == request_binding.get("integrity_hash"), "Reset proof binds immutable Change Request binding report."),
                _check(f"{prefix}_event_hash", proof.get("reset_event_hash") in reset_event_by_hash, "Reset proof is represented in lifecycle event log."),
                _check(f"{prefix}_binding_hash", binding.get("reset_proof_hash") == proof.get("integrity_hash"), "Reset binding references reset proof."),
                _check(f"{prefix}_binding_request_hash", binding.get("request_hash") == proof.get("request_hash"), "Reset binding references approved request hash."),
                _check(f"{prefix}_binding_approval_hash", binding.get("approval_hash") == proof.get("approval_hash"), "Reset binding references approval hash."),
                _check(f"{prefix}_binding_cr_report", binding.get("cr_binding_report_hash") == proof.get("cr_binding_report_hash"), "Reset binding references Change Request binding report."),
                _check(f"{prefix}_binding_event_hash", binding.get("reset_event_hash") == proof.get("reset_event_hash"), "Reset binding references reset event hash."),
                _check(f"{prefix}_binding_previous_signoff", binding.get("previous_signoff_hash") == proof.get("previous_signoff_hash"), "Reset binding references previous signoff hash."),
                _check(f"{prefix}_binding_previous_signoff_binding", binding.get("previous_signoff_binding_hash") == proof.get("previous_signoff_binding_hash"), "Reset binding references previous signoff binding hash."),
                _check(f"{prefix}_binding_previous_archive", binding.get("previous_archive_zip_sha256") == proof.get("previous_archive_zip_sha256"), "Reset binding references previous archive ZIP."),
                _check(f"{prefix}_binding_previous_manifest", binding.get("previous_archive_manifest_hash") == proof.get("previous_archive_manifest_hash"), "Reset binding references previous archive manifest."),
                _check(f"{prefix}_binding_previous_verification", binding.get("previous_verification_report_hash") == proof.get("previous_verification_report_hash"), "Reset binding references previous verification report."),
                _check(f"{prefix}_binding_previous_history", binding.get("previous_signoff_history_event_hash") == proof.get("previous_signoff_history_event_hash"), "Reset binding references previous signoff history event."),
                _check(f"{prefix}_binding_lifecycle_event", binding.get("lifecycle_event_hash") == event.get("event_hash"), "Reset binding references lifecycle event."),
                _check(f"{prefix}_binding_single_use", binding.get("single_use_consumed") is True, "Reset binding records single-use consumption."),
                _check(f"{prefix}_binding_next_generation", _same_number(binding.get("next_generation"), proof.get("next_generation")), "Reset binding references next generation."),
                _check(f"{prefix}_target_previous_signoff", _same_nonempty(proof.get("previous_signoff_hash"), target.get("acceptance_signoff_hash"), source.get("signoff_hash")), "Reset proof previous signoff matches request target and source."),
                _check(f"{prefix}_target_previous_signoff_binding", _same_nonempty(proof.get("previous_signoff_binding_hash"), target.get("acceptance_signoff_binding_hash"), source.get("signoff_binding_hash")), "Reset proof previous signoff binding matches request target and source."),
                _check(f"{prefix}_target_previous_archive_zip", _same_nonempty(proof.get("previous_archive_zip_sha256"), target.get("acceptance_archive_zip_sha256"), source.get("archive_zip_sha256")), "Reset proof previous archive ZIP hash matches request target and source."),
                _check(f"{prefix}_target_previous_archive_manifest", _same_nonempty(proof.get("previous_archive_manifest_hash"), target.get("acceptance_archive_manifest_hash"), source.get("archive_manifest_hash")), "Reset proof previous archive manifest hash matches request target and source."),
                _check(f"{prefix}_target_previous_verification", _same_nonempty(proof.get("previous_verification_report_hash"), target.get("acceptance_verification_report_hash"), source.get("verification_report_hash")), "Reset proof previous verification report hash matches request target and source."),
                _check(f"{prefix}_target_previous_generation", _same_number(proof.get("previous_generation"), target.get("generation"), source.get("generation")), "Reset proof previous generation matches request target and source."),
                _check(f"{prefix}_target_component", target.get("component_type") == "unified_release_program_continuity_command_center_receiver_acceptance" and target.get("program_id") == proof.get("program_id"), "Change Request targets this Receiver Acceptance component."),
                _check(f"{prefix}_next_generation", _next_generation_ok(proof.get("previous_generation"), proof.get("next_generation")), "Reset proof next generation follows previous generation."),
                _check(f"{prefix}_request_reset_proof_hash", request.get("reset_proof_hash") == proof.get("integrity_hash"), "Applied request references reset proof hash."),
                _check(f"{prefix}_request_reset_id", request.get("reset_id") == reset_id, "Applied request references reset id."),
                _check(f"{prefix}_request_reset_event_hash", request.get("reset_event_hash") == proof.get("reset_event_hash"), "Applied request references reset event hash."),
                _check(f"{prefix}_request_approved_hash", request.get("approved_request_hash") == proof.get("request_hash"), "Applied request preserves approved request hash."),
                _check(f"{prefix}_event_request", event.get("change_request_id") == request_id, "Lifecycle reset event references request id."),
                _check(f"{prefix}_submitted_request_hash", submitted_event.get("request_hash") == approval.get("request_hash"), "Submitted lifecycle event binds the request approved by the approval proof."),
                _check(f"{prefix}_approved_request_hash", approved_event.get("request_hash") == proof.get("request_hash"), "Approved lifecycle event binds the reset proof request hash."),
                _check(f"{prefix}_approved_approval_hash", approved_event.get("approval_hash") == approval.get("integrity_hash"), "Approved lifecycle event binds the approval proof."),
                _check(f"{prefix}_submitted_target", submitted_event.get("target_signoff_hash") == proof.get("previous_signoff_hash"), "Submitted lifecycle event targets the prior signoff."),
                _check(f"{prefix}_approved_target", approved_event.get("target_signoff_hash") == proof.get("previous_signoff_hash"), "Approved lifecycle event targets the prior signoff."),
                _check(f"{prefix}_event_reset", event.get("reset_id") == reset_id, "Lifecycle reset event references reset id."),
                _check(f"{prefix}_event_request_hash", event.get("request_hash") == request.get("integrity_hash"), "Lifecycle reset event references applied request hash."),
                _check(f"{prefix}_event_approval_hash", event.get("approval_hash") == approval.get("integrity_hash"), "Lifecycle reset event references approval hash."),
                _check(f"{prefix}_event_reset_proof_hash", event.get("reset_proof_hash") == proof.get("integrity_hash"), "Lifecycle reset event references reset proof hash."),
                _check(f"{prefix}_event_reset_event_hash", event.get("reset_event_hash") == proof.get("reset_event_hash"), "Lifecycle reset event references acceptance reset event hash."),
                _check(f"{prefix}_event_previous_signoff", event.get("previous_signoff_hash") == proof.get("previous_signoff_hash"), "Lifecycle reset event references previous signoff hash."),
                _check(f"{prefix}_event_next_generation", _same_number(event.get("next_generation"), proof.get("next_generation")), "Lifecycle reset event references next generation."),
                _check(f"{prefix}_index_exists", bool(reset_row), "Reset index includes reset proof."),
                _check(f"{prefix}_index_proof_hash", reset_row.get("reset_proof_hash") == proof.get("integrity_hash"), "Reset index references reset proof hash."),
                _check(f"{prefix}_index_binding_hash", reset_row.get("binding_hash") == binding.get("integrity_hash"), "Reset index references reset binding hash."),
                _check(f"{prefix}_index_event_hash", reset_row.get("reset_event_hash") == proof.get("reset_event_hash"), "Reset index references reset event hash."),
                _check(f"{prefix}_index_previous_signoff", reset_row.get("previous_signoff_hash") == proof.get("previous_signoff_hash"), "Reset index references previous signoff hash."),
                _check(f"{prefix}_index_next_generation", _same_number(reset_row.get("next_generation"), proof.get("next_generation")), "Reset index references next generation."),
            ]
        )
    return checks


def _index_checks(request_index: ImplementationDocument, reset_index: ImplementationDocument, requests: dict[str, ImplementationDocument], resets: dict[str, ImplementationDocument], lifecycle: ImplementationDocument, events: list[ImplementationDocument]) -> list[ImplementationDocument]:
    request_rows = _as_list(request_index.get("items"))
    reset_rows = _as_list(reset_index.get("items"))
    event_hashes = [row.get("event_hash") for row in events]
    return [
        _check("urpcccacc_request_index_count", len(request_rows) == len(requests), "Change request index count matches archived requests."),
        _check("urpcccacc_reset_index_count", len(reset_rows) == len(resets), "Reset proof index count matches archived reset proofs."),
        _check("urpcccacc_lifecycle_request_count", int((lifecycle.get("summary") or {}).get("change_request_count") or -1) == len(requests), "Lifecycle request count matches archive."),
        _check("urpcccacc_lifecycle_reset_count", int((lifecycle.get("summary") or {}).get("reset_count") or -1) == len(resets), "Lifecycle reset count matches archive."),
        _check("urpcccacc_lifecycle_event_hashes", (lifecycle.get("source") or {}).get("event_hashes") == event_hashes, "Lifecycle report binds event log."),
    ]


def command_center_acceptance_change_lifecycle_semantic_checks(
    events: list[DomainDocument],
    resets: dict[str, DomainDocument],
) -> list[DomainDocument]:
    initial = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event_type") == "receiver_acceptance_signed"
    ]
    checks = [
        _check(
            "urpcccacc_lifecycle_initial_signoff",
            len(initial) == 1 and _same_number(initial[0][1].get("generation"), 1),
            "Lifecycle starts from exactly one generation-1 Receiver Acceptance signoff.",
        )
    ]
    previous_successor_index = initial[0][0] if initial else -1
    ordered_proofs = sorted(
        (bundle.get("proof") or {} for bundle in resets.values()),
        key=lambda proof: _as_int(proof.get("next_generation")) or -1,
    )
    for expected_previous, proof in enumerate(ordered_proofs, start=1):
        request_id = str(proof.get("change_request_id") or "")
        reset_id = str(proof.get("reset_id") or "")
        next_generation = _as_int(proof.get("next_generation"))
        submitted = _event_indexes(events, "receiver_acceptance_change_request_submitted", "change_request_id", request_id)
        approved = _event_indexes(events, "receiver_acceptance_change_request_approved", "change_request_id", request_id)
        reset = _event_indexes(events, "receiver_acceptance_signoff_reset_applied", "reset_id", reset_id)
        successor = [
            index
            for index, event in enumerate(events)
            if event.get("event_type") == "successor_receiver_acceptance_signed"
            and _same_number(event.get("generation"), next_generation)
            and event.get("reset_proof_hash") == proof.get("integrity_hash")
        ]
        prefix = f"urpcccacc_lifecycle_{_safe_check_key(reset_id)}"
        unique = all(len(rows) == 1 for rows in (submitted, approved, reset, successor))
        ordered = unique and previous_successor_index < submitted[0] < approved[0] < reset[0] < successor[0]
        checks.extend(
            [
                _check(f"{prefix}_events", unique, "Lifecycle contains one submitted, approved, reset, and successor event for this generation."),
                _check(f"{prefix}_order", ordered, "Lifecycle event order is submitted, approved, reset, then successor signoff."),
                _check(f"{prefix}_previous_generation", _same_number(proof.get("previous_generation"), expected_previous), "Reset proof previous generation is contiguous."),
                _check(f"{prefix}_next_generation", _same_number(next_generation, expected_previous + 1), "Reset proof next generation is contiguous."),
            ]
        )
        if successor:
            previous_successor_index = successor[0]
    return checks


def _event_indexes(events: list[ImplementationDocument], event_type: str, field: str, value: str) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if event.get("event_type") == event_type and str(event.get(field) or "") == value
    ]


from song_agent.domains.program import v142_urpcccacv_readiness as _v142_urpcccacv_readiness
from song_agent.domains.program.v142_urpcccacv_readiness import _generation_checks as _generation_checks, _current_generation_checks as _current_generation_checks, _document_binding_checks as _document_binding_checks, _current_acceptance_checks as _current_acceptance_checks, command_center_acceptance_change_previous_evidence_checks as command_center_acceptance_change_previous_evidence_checks, _manifest_checks as _manifest_checks, _history_checks as _history_checks, _redaction_check as _redaction_check, _finish as _finish, _same_nonempty as _same_nonempty, _as_int as _as_int, _same_number as _same_number, _next_generation_ok as _next_generation_ok, _read_json_entry as _read_json_entry, _parse_jsonl as _parse_jsonl, _safe_check_key as _safe_check_key, _has_blocking_failures as _has_blocking_failures

_v142_urpcccacv_readiness.bind_globals(globals())
