from __future__ import annotations

import hashlib
import json
import re
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

from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_command_center_acceptance_verifier import (
    ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_command_center_acceptance_package,
)


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
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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

            manifest = _read_json_entry(archive, "manifest.json")
            state = _read_json_entry(archive, "state.json")
            request_index = _read_json_entry(archive, "request-index.json")
            reset_index = _read_json_entry(archive, "reset-index.json")
            generation = _read_json_entry(archive, "generation.json")
            lifecycle = _read_json_entry(archive, "lifecycle.json")
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
                    "current_generation": generation.get("generation"),
                }
            )

            checks.extend(_manifest_checks(archive, manifest, name_set, expected))
            for check_id, doc in (
                ("urpcccacc_manifest_integrity", manifest),
                ("urpcccacc_state_integrity", state),
                ("urpcccacc_request_index_integrity", request_index),
                ("urpcccacc_reset_index_integrity", reset_index),
                ("urpcccacc_current_generation_integrity", generation),
                ("urpcccacc_lifecycle_integrity", lifecycle),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
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
            checks.extend(_current_generation_checks(generation, state, resets, events))
            checks.extend(_generation_checks(generation_docs, generation, state, resets))
            checks.extend(_document_binding_checks(manifest, state, request_index, reset_index, generation, lifecycle))
            checks.extend(_current_acceptance_checks(state, acceptance_archive_path, acceptance_verification_report_path, acceptance_signoff_binding_path, require=require_current_acceptance))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpcccacc_zip_readable", False, "Command Center Receiver Acceptance Change Control Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_command_center_acceptance_change_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_continuity_command_center_acceptance_change_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _request_bundle(archive: zipfile.ZipFile, request_id: str) -> dict[str, Any]:
    bundle = {
        "request": _read_json_entry(archive, f"cr/{request_id}/request.json"),
        "binding": _read_json_entry(archive, f"cr/{request_id}/binding.json"),
        "approval": {},
    }
    approval_name = f"cr/{request_id}/approval.json"
    if approval_name in archive.namelist():
        bundle["approval"] = _read_json_entry(archive, approval_name)
    return bundle


def _reset_bundle(archive: zipfile.ZipFile, reset_id: str) -> dict[str, Any]:
    return {
        "proof": _read_json_entry(archive, f"rp/{reset_id}/proof.json"),
        "binding": _read_json_entry(archive, f"rp/{reset_id}/binding.json"),
    }


def _generation_bundle(archive: zipfile.ZipFile, generation: int) -> dict[str, Any]:
    prefix = f"gen/g{generation:06d}"
    return {
        "verification_summary": _read_json_entry(archive, f"{prefix}/verification.json"),
        "signoff_binding_summary": _read_json_entry(archive, f"{prefix}/signoff-binding.json"),
        "source_summary": _read_json_entry(archive, f"{prefix}/source.json"),
    }


def _request_checks(requests: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
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


def _reset_checks(resets: dict[str, dict[str, Any]], requests: dict[str, dict[str, Any]], events: list[dict[str, Any]], reset_index: dict[str, Any]) -> list[dict[str, Any]]:
    return command_center_acceptance_change_reset_semantic_checks(resets, requests, events, reset_index)


def command_center_acceptance_change_reset_semantic_checks(resets: dict[str, dict[str, Any]], requests: dict[str, dict[str, Any]], events: list[dict[str, Any]], reset_index: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    reset_event_by_hash = {row.get("reset_event_hash"): row for row in events if row.get("event_type") == "receiver_acceptance_signoff_reset_applied"}
    reset_index_rows = {
        str(row.get("reset_id") or ""): row
        for row in (reset_index.get("items") if isinstance(reset_index.get("items"), list) else [])
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
        target = request.get("target") if isinstance(request.get("target"), dict) else {}
        source = request.get("source") if isinstance(request.get("source"), dict) else {}
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


def _index_checks(request_index: dict[str, Any], reset_index: dict[str, Any], requests: dict[str, dict[str, Any]], resets: dict[str, dict[str, Any]], lifecycle: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    request_rows = request_index.get("items") if isinstance(request_index.get("items"), list) else []
    reset_rows = reset_index.get("items") if isinstance(reset_index.get("items"), list) else []
    event_hashes = [row.get("event_hash") for row in events]
    return [
        _check("urpcccacc_request_index_count", len(request_rows) == len(requests), "Change request index count matches archived requests."),
        _check("urpcccacc_reset_index_count", len(reset_rows) == len(resets), "Reset proof index count matches archived reset proofs."),
        _check("urpcccacc_lifecycle_request_count", int((lifecycle.get("summary") or {}).get("change_request_count") or -1) == len(requests), "Lifecycle request count matches archive."),
        _check("urpcccacc_lifecycle_reset_count", int((lifecycle.get("summary") or {}).get("reset_count") or -1) == len(resets), "Lifecycle reset count matches archive."),
        _check("urpcccacc_lifecycle_event_hashes", (lifecycle.get("source") or {}).get("event_hashes") == event_hashes, "Lifecycle report binds event log."),
    ]


def command_center_acceptance_change_lifecycle_semantic_checks(
    events: list[dict[str, Any]],
    resets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
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


def _event_indexes(events: list[dict[str, Any]], event_type: str, field: str, value: str) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if event.get("event_type") == event_type and str(event.get(field) or "") == value
    ]


def _generation_checks(
    generations: dict[int, dict[str, Any]],
    current_generation: dict[str, Any],
    state: dict[str, Any],
    resets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    current_number = _as_int(current_generation.get("generation"))
    proofs_by_previous = {
        int(proof.get("previous_generation")): proof
        for proof in (bundle.get("proof") or {} for bundle in resets.values())
        if _as_int(proof.get("previous_generation")) is not None
    }
    expected = set(proofs_by_previous)
    if current_number is not None:
        expected.add(current_number)
    checks: list[dict[str, Any]] = [
        _check(
            "urpcccacc_generation_set",
            set(generations) == expected,
            "Generation sidecars cover every historical reset generation and the current generation.",
            {"expected": sorted(expected), "actual": sorted(generations)},
        )
    ]
    current_acceptance = state.get("current_acceptance") if isinstance(state.get("current_acceptance"), dict) else {}
    for generation, bundle in sorted(generations.items()):
        for key, doc in bundle.items():
            checks.append(_check(f"urpcccacc_generation_{generation:06d}_{key}_integrity", _integrity_ok(doc), "Generation sidecar integrity is valid."))
            checks.append(_check(f"urpcccacc_generation_{generation:06d}_{key}_identity", _same_number(doc.get("generation"), generation), "Generation sidecar identity matches its path."))
        verification = bundle.get("verification_summary") or {}
        signoff = bundle.get("signoff_binding_summary") or {}
        source_doc = bundle.get("source_summary") or {}
        source = source_doc.get("source") if isinstance(source_doc.get("source"), dict) else {}
        expected_source = current_acceptance if generation == current_number else (proofs_by_previous.get(generation) or {}).get("source") or {}
        checks.extend(
            [
                _check(f"urpcccacc_generation_{generation:06d}_source", source == expected_source, "Generation source matches current or reset-time Receiver Acceptance evidence."),
                _check(f"urpcccacc_generation_{generation:06d}_signoff", _same_nonempty(signoff.get("signoff_hash"), expected_source.get("signoff_hash")), "Generation summary binds Receiver Acceptance signoff."),
                _check(f"urpcccacc_generation_{generation:06d}_signoff_binding", _same_nonempty(signoff.get("signoff_binding_hash"), expected_source.get("signoff_binding_hash")), "Generation summary binds Receiver Acceptance signoff proof."),
                _check(f"urpcccacc_generation_{generation:06d}_archive", _same_nonempty(verification.get("archive_zip_sha256"), expected_source.get("archive_zip_sha256")), "Generation summary binds Receiver Acceptance Archive."),
                _check(f"urpcccacc_generation_{generation:06d}_manifest", _same_nonempty(verification.get("archive_manifest_hash"), expected_source.get("archive_manifest_hash")), "Generation summary binds Receiver Acceptance manifest."),
                _check(f"urpcccacc_generation_{generation:06d}_verification", _same_nonempty(verification.get("verification_report_hash"), expected_source.get("verification_report_hash")), "Generation summary binds Receiver Acceptance verification report."),
            ]
        )
    return checks


def _current_generation_checks(
    generation: dict[str, Any],
    state: dict[str, Any],
    resets: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_number = _as_int(generation.get("generation"))
    current_acceptance = state.get("current_acceptance") if isinstance(state.get("current_acceptance"), dict) else {}
    signed_event = next(
        (
            row
            for row in reversed(events)
            if row.get("event_type") in {"receiver_acceptance_signed", "successor_receiver_acceptance_signed"}
        ),
        {},
    )
    checks = [
        _check("urpcccacc_current_generation_package_type", generation.get("package_type") == "musicforge_unified_release_program_continuity_command_center_acceptance_generation", "Current generation package type is valid."),
        _check("urpcccacc_current_generation_status", generation.get("status") == "current_signed", "Current generation is signed."),
        _check("urpcccacc_current_generation_state", _same_number(current_number, current_acceptance.get("generation")), "Current generation matches current Receiver Acceptance state."),
        _check("urpcccacc_current_generation_event", _same_number(current_number, signed_event.get("generation")), "Current generation matches the latest signed lifecycle event."),
    ]
    if resets:
        latest = max(
            (bundle.get("proof") or {} for bundle in resets.values()),
            key=lambda proof: _as_int(proof.get("next_generation")) or -1,
        )
        checks.extend(
            [
                _check("urpcccacc_current_generation_reset_proof", generation.get("reset_proof_hash") == latest.get("integrity_hash"), "Current generation binds the latest reset proof."),
                _check("urpcccacc_current_generation_previous", _same_number(generation.get("previous_generation"), latest.get("previous_generation")), "Current generation preserves the previous generation."),
                _check("urpcccacc_current_generation_next", _same_number(current_number, latest.get("next_generation")), "Current generation follows the latest reset proof."),
                _check("urpcccacc_current_generation_successor_event", signed_event.get("event_type") == "successor_receiver_acceptance_signed" and signed_event.get("reset_proof_hash") == latest.get("integrity_hash"), "Successor lifecycle event binds the latest reset proof."),
            ]
        )
    return checks


def _document_binding_checks(manifest: dict[str, Any], state: dict[str, Any], request_index: dict[str, Any], reset_index: dict[str, Any], generation: dict[str, Any], lifecycle: dict[str, Any]) -> list[dict[str, Any]]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    docs = {
        "change_control_state_hash": state,
        "change_request_index_hash": request_index,
        "reset_proof_index_hash": reset_index,
        "current_generation_hash": generation,
        "lifecycle_report_hash": lifecycle,
    }
    return [_check(f"urpcccacc_manifest_{key}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}.") for key, doc in docs.items()]


def _current_acceptance_checks(state: dict[str, Any], archive_path: Path | str | None, verification_report_path: Path | str | None, signoff_binding_path: Path | str | None, *, require: bool) -> list[dict[str, Any]]:
    if not require:
        return []
    if not archive_path:
        return [_check("urpcccacc_current_acceptance_required", False, "Current Command Center Receiver Acceptance Archive is required.")]
    if not verification_report_path:
        return [_check("urpcccacc_current_acceptance_report_required", False, "Current Command Center Receiver Acceptance verification report is required.")]
    if not signoff_binding_path:
        return [_check("urpcccacc_current_acceptance_binding_required", False, "Current Command Center Receiver Acceptance signoff binding is required.")]
    archive = Path(archive_path)
    report_path = Path(verification_report_path)
    binding_path = Path(signoff_binding_path)
    checks = [
        _check("urpcccacc_current_acceptance_exists", archive.exists() and archive.is_file(), "Current Command Center Receiver Acceptance Archive exists."),
        _check("urpcccacc_current_acceptance_report_exists", report_path.exists() and report_path.is_file(), "Current Command Center Receiver Acceptance verification report exists."),
        _check("urpcccacc_current_acceptance_binding_exists", binding_path.exists() and binding_path.is_file(), "Current Command Center Receiver Acceptance signoff binding exists."),
    ]
    if _has_blocking_failures(checks):
        return checks
    external = read_json(report_path)
    external_binding = read_json(binding_path)
    runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
        archive,
        strict=True,
        require_signed=False,
    )
    current = state.get("current_acceptance") if isinstance(state.get("current_acceptance"), dict) else {}
    checks.extend(
        [
            _check("urpcccacc_current_acceptance_report_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, "Current Acceptance verification package type is valid."),
            _check("urpcccacc_current_acceptance_report_integrity", _integrity_ok(external), "Current Acceptance verification report integrity is valid."),
            _check("urpcccacc_current_acceptance_binding_integrity", _integrity_ok(external_binding), "Current Acceptance signoff binding integrity is valid."),
            _check("urpcccacc_current_acceptance_runtime_passed", runtime.get("status") == "passed", "Current Acceptance runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urpcccacc_current_acceptance_report_passed", external.get("status") == "passed", "Current Acceptance external verification passed."),
            _check("urpcccacc_current_acceptance_zip_sha256", current.get("archive_zip_sha256") == external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(archive), "Current Acceptance ZIP hash matches state, report, and runtime."),
            _check("urpcccacc_current_acceptance_manifest_hash", current.get("archive_manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Current Acceptance manifest hash matches state, report, and runtime."),
            _check("urpcccacc_current_acceptance_verification_hash", current.get("verification_report_hash") == external.get("integrity_hash"), "Current Acceptance verification hash matches state."),
            _check("urpcccacc_current_acceptance_signoff_binding", current.get("signoff_binding_hash") == external_binding.get("integrity_hash"), "Current Acceptance state binds external signoff proof."),
            _check("urpcccacc_current_acceptance_signoff", current.get("signoff_hash") == external_binding.get("signoff_hash"), "Current Acceptance state binds current signoff."),
        ]
    )
    return checks


def command_center_acceptance_change_previous_evidence_checks(
    resets: dict[str, dict[str, Any]],
    root_value: Path | str | None,
    *,
    require: bool,
) -> list[dict[str, Any]]:
    if not resets:
        return []
    if not root_value:
        return [_check("urpcccacc_previous_acceptance_root_required", not require, "Historical Receiver Acceptance evidence root is required for reset proof verification.")]
    root = Path(root_value)
    checks: list[dict[str, Any]] = [
        _check("urpcccacc_previous_acceptance_root_exists", root.is_dir(), "Historical Receiver Acceptance evidence root exists.")
    ]
    if not root.is_dir():
        return checks
    for reset_id, bundle in sorted(resets.items()):
        proof = bundle.get("proof") or {}
        generation = int(proof.get("previous_generation") or 0)
        snapshot = root / f"gen-{generation:06d}" / "acceptance-snapshot"
        archive_path = snapshot / "receiver-acceptance-archive.zip"
        report_path = snapshot / "receiver-acceptance-verification-report.json"
        binding_path = snapshot / "receiver-acceptance-signoff-binding-summary.json"
        signoff_path = snapshot / "receiver-acceptance-signoff.json"
        history_path = snapshot / "receiver-acceptance-history.jsonl"
        prefix = f"urpcccacc_previous_{_safe_check_key(reset_id)}"
        required_paths = (archive_path, report_path, binding_path, signoff_path, history_path)
        checks.append(_check(f"{prefix}_files", all(path.is_file() for path in required_paths), "Historical Receiver Acceptance snapshot is complete."))
        if not all(path.is_file() for path in required_paths):
            continue
        report = read_json(report_path)
        binding = read_json(binding_path)
        signoff = read_json(signoff_path)
        runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
            archive_path,
            strict=True,
            require_signed=False,
        )
        try:
            history = _parse_jsonl(history_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            history = []
        history_event = next(
            (
                row
                for row in reversed(history)
                if row.get("event_type") == "receiver_acceptance_signoff_created"
                and row.get("signoff_hash") == signoff.get("integrity_hash")
            ),
            {},
        )
        checks.extend(
            [
                _check(f"{prefix}_runtime", runtime.get("status") == "passed", "Historical Receiver Acceptance archive runtime verification passed.", {"blockers": runtime.get("blockers") or []}),
                _check(f"{prefix}_report_type", report.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, "Historical verification package type is valid."),
                _check(f"{prefix}_report_integrity", _integrity_ok(report) and report.get("status") == "passed", "Historical verification report is valid and passed."),
                _check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Historical signoff binding integrity is valid."),
                _check(f"{prefix}_signoff_integrity", _integrity_ok(signoff), "Historical signoff integrity is valid."),
                _check(f"{prefix}_archive_hash", proof.get("previous_archive_zip_sha256") == _sha256_path(archive_path) == report.get("zip_sha256") == runtime.get("zip_sha256"), "Reset proof binds historical archive ZIP."),
                _check(f"{prefix}_manifest_hash", proof.get("previous_archive_manifest_hash") == report.get("manifest_hash") == runtime.get("manifest_hash"), "Reset proof binds historical archive manifest."),
                _check(f"{prefix}_verification_hash", proof.get("previous_verification_report_hash") == report.get("integrity_hash"), "Reset proof binds historical verification report."),
                _check(f"{prefix}_signoff_hash", proof.get("previous_signoff_hash") == signoff.get("integrity_hash") == binding.get("signoff_hash"), "Reset proof binds historical signoff."),
                _check(f"{prefix}_binding_hash", proof.get("previous_signoff_binding_hash") == binding.get("integrity_hash"), "Reset proof binds historical signoff binding."),
                _check(f"{prefix}_history_event", proof.get("previous_signoff_history_event_hash") == history_event.get("event_hash") == binding.get("history_event_hash"), "Reset proof binds historical signoff history event."),
            ]
        )
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str], expected_entries: set[str]) -> list[dict[str, Any]]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path") or "") for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check("urpcccacc_manifest_files_exact", file_paths == expected_files, "Manifest files match archive layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpcccacc_manifest_entries_exact", name_set == expected_entries, "Manifest entries match fixed/patterned layout.", {"missing": sorted(expected_entries - name_set), "extra": sorted(name_set - expected_entries)}),
        _check("urpcccacc_manifest_zip_filename", (manifest.get("zip") or {}).get("filename") == "cc-archive.zip", "Manifest ZIP filename is canonical."),
        _check("urpcccacc_manifest_zip_entries", sorted((manifest.get("zip") or {}).get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists."))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."))
        checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."))
    return checks


def _history_checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, row in enumerate(rows, start=1):
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in {**row, "payload_hash": expected_payload}.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpcccacc_history_{index:03d}_previous", row.get("previous_event_hash") == previous, "History previous hash matches."),
                _check(f"urpcccacc_history_{index:03d}_payload", row.get("payload_hash") == expected_payload, "History payload hash matches."),
                _check(f"urpcccacc_history_{index:03d}_event", row.get("event_hash") == expected_event, "History event hash matches."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id="urpcccacc_redaction_scan")


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if extra:
        checks.append(extra)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
    )


def _same_nonempty(*values: Any) -> bool:
    normalized = [str(value) for value in values if value not in {None, ""}]
    return len(normalized) == len(values) and len(set(normalized)) == 1


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _same_number(*values: Any) -> bool:
    normalized = [_as_int(value) for value in values]
    return all(value is not None for value in normalized) and len(set(normalized)) == 1


def _next_generation_ok(previous: Any, next_generation: Any) -> bool:
    previous_int = _as_int(previous)
    next_int = _as_int(next_generation)
    return previous_int is not None and next_int == previous_int + 1


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)
