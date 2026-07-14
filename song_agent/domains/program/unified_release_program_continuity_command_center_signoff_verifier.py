from __future__ import annotations

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
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_command_center_package,
)


COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_signoff_archive"
)
COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_signoff_archive_verification"
)
COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_final_handoff"
)
COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_final_handoff_verification"
)
COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION = 1

ARCHIVE_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "command-center-signoff.json",
    "command-center-signoff-binding-summary.json",
    "command-center-signoff-history.jsonl",
    "command-center-signoff-policy.json",
    "command-center-signoff-state.json",
    "command-center-fingerprint-summary.json",
    "command-center-verification-summary.json",
    "external-evidence-manifest-summary.json",
    "final-handoff-checklist.json",
}

HANDOFF_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "final-handoff-summary.json",
    "receiver-checklist.json",
    "archive-verification-summary.json",
    "signoff-binding-summary.json",
}

def verify_unified_release_program_continuity_command_center_signoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    signoff_binding_path: Path | str | None = None,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    command_center_external_evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
    }
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
                verification_package_type=COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpcccs_kernel",
                required_entries=frozenset(ARCHIVE_REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.is_file():
        return _finish_archive(checks, summary, _check("urpcccs_zip_exists", False, "Signoff Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.extend(
        [
            _check("urpcccs_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."),
            _check("urpcccs_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data."),
        ]
    )
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpcccs_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpcccs_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit."),
                    _check("urpcccs_uncompressed_size", sum(item.file_size for item in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpcccs_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpcccs_allowed_entries", name_set == ARCHIVE_REQUIRED_ENTRIES, "Archive has the fixed entry set.", {"extra": sorted(name_set - ARCHIVE_REQUIRED_ENTRIES), "missing": sorted(ARCHIVE_REQUIRED_ENTRIES - name_set)}),
                    _check("urpcccs_no_nested_zip", not nested, "Archive contains no nested ZIP.", {"nested": nested}),
                ]
            )
            if _has_blockers(checks):
                return _finish_archive(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            signoff = _read_json_entry(archive, "command-center-signoff.json")
            binding = _read_json_entry(archive, "command-center-signoff-binding-summary.json")
            policy = _read_json_entry(archive, "command-center-signoff-policy.json")
            state = _read_json_entry(archive, "command-center-signoff-state.json")
            fingerprint = _read_json_entry(archive, "command-center-fingerprint-summary.json")
            verification_summary = _read_json_entry(archive, "command-center-verification-summary.json")
            evidence_summary = _read_json_entry(archive, "external-evidence-manifest-summary.json")
            checklist = _read_json_entry(archive, "final-handoff-checklist.json")
            history = _parse_jsonl(archive.read("command-center-signoff-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "program_id": signoff.get("program_id") or manifest.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signed_by": signoff.get("signed_by"),
                    "status": signoff.get("status"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, ARCHIVE_REQUIRED_ENTRIES, "urpcccs"))
            checks.extend(
                [
                    _check("urpcccs_manifest_package_type", manifest.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpcccs_signoff_package_type", signoff.get("package_type") == "musicforge_unified_release_program_continuity_command_center_signoff", "Signoff package type is valid."),
                    _check("urpcccs_binding_package_type", binding.get("package_type") == "musicforge_unified_release_program_continuity_command_center_signoff_binding", "Binding package type is valid."),
                    _check("urpcccs_policy_package_type", policy.get("package_type") == "musicforge_unified_release_program_continuity_command_center_signoff_policy", "Policy package type is valid."),
                    _check("urpcccs_state_package_type", state.get("package_type") == "musicforge_unified_release_program_continuity_command_center_signoff_state", "State package type is valid."),
                ]
            )
            for check_id, doc in (
                ("urpcccs_manifest_integrity", manifest),
                ("urpcccs_signoff_integrity", signoff),
                ("urpcccs_binding_integrity", binding),
                ("urpcccs_policy_integrity", policy),
                ("urpcccs_state_integrity", state),
                ("urpcccs_fingerprint_integrity", fingerprint),
                ("urpcccs_verification_summary_integrity", verification_summary),
                ("urpcccs_evidence_summary_integrity", evidence_summary),
                ("urpcccs_checklist_integrity", checklist),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} is valid."))
            history_checks, latest_state_event, signoff_event = _history_checks(history)
            checks.extend(history_checks)
            checks.extend(_internal_binding_checks(manifest, signoff, binding, state, fingerprint, verification_summary, evidence_summary, checklist, latest_state_event, signoff_event))
            if require_signed:
                checks.extend(
                    [
                        _check("urpcccs_require_signed", signoff.get("status") == "signed", "Signoff is signed."),
                        _check("urpcccs_latest_state_signed", bool(latest_state_event) and latest_state_event.get("event_type") == "command_center_signoff_created", "Latest signoff state is signed."),
                    ]
                )
                checks.extend(_external_binding_checks(signoff_binding_path, binding, require=True))
                checks.extend(
                    _current_command_center_checks(
                        command_center_zip_path,
                        command_center_verification_report_path,
                        command_center_external_evidence_manifest_path,
                        signoff,
                        binding,
                        fingerprint,
                        verification_summary,
                        evidence_summary,
                        require=True,
                    )
                )
            elif signoff_binding_path:
                checks.extend(_external_binding_checks(signoff_binding_path, binding, require=False))
            checks.append(_redaction_check(archive, names, "urpcccs_redaction"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, ValueError, KeyError) as exc:
        checks.append(_check("urpcccs_zip_readable", False, "Signoff Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish_archive(checks, summary)


def write_unified_release_program_continuity_command_center_signoff_verification_report(
    report: dict[str, Any], path: Path | str
) -> dict[str, Any]:
    output = dict(report)
    output["package_type"] = COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE
    output["integrity_hash"] = _integrity_hash(output)
    write_json(Path(path), output)
    return output


def verify_unified_release_program_continuity_command_center_final_handoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_archive: bool = False,
    archive_zip_path: Path | str | None = None,
    archive_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    command_center_external_evidence_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE,
                verification_package_type=COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpccfh_kernel",
                required_entries=frozenset(HANDOFF_REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.is_file():
        return _finish_handoff(checks, summary, _check("urpccch_zip_exists", False, "Final Handoff ZIP exists."))
    summary.update({"zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    checks.append(_check("urpccch_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            checks.extend(
                [
                    _check("urpccch_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpccch_entry_paths_safe", not unsafe, "ZIP entries are safe.", {"unsafe": unsafe}),
                    _check("urpccch_allowed_entries", name_set == HANDOFF_REQUIRED_ENTRIES, "Handoff has the fixed entry set.", {"extra": sorted(name_set - HANDOFF_REQUIRED_ENTRIES), "missing": sorted(HANDOFF_REQUIRED_ENTRIES - name_set)}),
                ]
            )
            if _has_blockers(checks):
                return _finish_handoff(checks, summary)
            manifest = _read_json_entry(archive, "manifest.json")
            handoff = _read_json_entry(archive, "final-handoff-summary.json")
            receiver = _read_json_entry(archive, "receiver-checklist.json")
            archive_summary = _read_json_entry(archive, "archive-verification-summary.json")
            binding = _read_json_entry(archive, "signoff-binding-summary.json")
            manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            summary.update({"program_id": handoff.get("program_id"), "manifest_hash": manifest.get("integrity_hash"), "status": handoff.get("status")})
            checks.extend(_manifest_checks(archive, manifest, HANDOFF_REQUIRED_ENTRIES, "urpccch"))
            checks.extend(
                [
                    _check("urpccch_manifest_package_type", manifest.get("package_type") == COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpccch_summary_package_type", handoff.get("package_type") == "musicforge_unified_release_program_continuity_command_center_final_handoff_summary", "Handoff summary package type is valid."),
                    _check("urpccch_receiver_package_type", receiver.get("package_type") == "musicforge_unified_release_program_continuity_command_center_receiver_checklist", "Receiver checklist package type is valid."),
                    _check("urpccch_archive_summary_package_type", archive_summary.get("package_type") == "musicforge_unified_release_program_continuity_command_center_archive_verification_summary", "Archive summary package type is valid."),
                    _check("urpccch_binding_package_type", binding.get("package_type") == "musicforge_unified_release_program_continuity_command_center_signoff_binding", "Signoff binding package type is valid."),
                    _check("urpccch_manifest_integrity", _integrity_ok(manifest), "Manifest integrity is valid."),
                    _check("urpccch_summary_integrity", _integrity_ok(handoff), "Handoff summary integrity is valid."),
                    _check("urpccch_receiver_integrity", _integrity_ok(receiver), "Receiver checklist integrity is valid."),
                    _check("urpccch_archive_summary_integrity", _integrity_ok(archive_summary), "Archive verification summary integrity is valid."),
                    _check("urpccch_binding_integrity", _integrity_ok(binding), "Signoff binding integrity is valid."),
                    _check("urpccch_status_ready", handoff.get("status") == "ready", "Final Handoff is ready."),
                    _check("urpccch_summary_binding", handoff.get("signoff_binding_hash") == binding.get("integrity_hash"), "Handoff summary binds signoff binding."),
                    _check("urpccch_signer_binding", handoff.get("signed_by") == binding.get("signed_by") and handoff.get("signoff_hash") == binding.get("signoff_hash"), "Handoff signer and signoff hash match independent binding."),
                    _check("urpccch_archive_binding", handoff.get("archive_zip_sha256") == archive_summary.get("zip_sha256") and handoff.get("archive_manifest_hash") == archive_summary.get("manifest_hash") and handoff.get("archive_verification_report_hash") == archive_summary.get("verification_report_hash"), "Handoff summary binds Archive verification summary."),
                    _check("urpccch_manifest_summary_binding", manifest_source.get("final_handoff_summary_hash") == handoff.get("integrity_hash"), "Manifest binds Handoff summary."),
                    _check("urpccch_manifest_archive_binding", manifest_source.get("archive_verification_summary_hash") == archive_summary.get("integrity_hash"), "Manifest binds Archive verification summary."),
                    _check("urpccch_manifest_signoff_binding", manifest_source.get("signoff_binding_hash") == binding.get("integrity_hash"), "Manifest binds signoff binding summary."),
                ]
            )
            checks.extend(_external_binding_checks(signoff_binding_path, binding, require=require_archive))
            if require_archive:
                checks.extend(
                    _external_archive_checks(
                        archive_zip_path,
                        archive_verification_report_path,
                        signoff_binding_path,
                        command_center_zip_path,
                        command_center_verification_report_path,
                        command_center_external_evidence_manifest_path,
                        archive_summary,
                    )
                )
            checks.append(_redaction_check(archive, names, "urpccch_redaction"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, ValueError, KeyError) as exc:
        checks.append(_check("urpccch_zip_readable", False, "Final Handoff ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish_handoff(checks, summary)


def write_unified_release_program_continuity_command_center_final_handoff_verification_report(
    report: dict[str, Any], path: Path | str
) -> dict[str, Any]:
    output = dict(report)
    output["package_type"] = COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE
    output["integrity_hash"] = _integrity_hash(output)
    write_json(Path(path), output)
    return output


def command_center_signoff_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _internal_binding_checks(
    manifest: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
    state: dict[str, Any],
    fingerprint: dict[str, Any],
    verification: dict[str, Any],
    evidence: dict[str, Any],
    checklist: dict[str, Any],
    latest_state_event: dict[str, Any] | None,
    signoff_event: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
    manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    reason_hash = stable_hash({"reason": signoff.get("reason")})
    checks = [
        _check("urpcccs_signoff_payload_hash", signoff.get("payload_hash") == stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}}), "Signoff payload hash is valid."),
        _check("urpcccs_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Binding matches signoff hash."),
        _check("urpcccs_binding_signoff_payload_hash", binding.get("signoff_payload_hash") == signoff.get("payload_hash"), "Binding matches signoff payload hash."),
        _check("urpcccs_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Binding matches signer."),
        _check("urpcccs_binding_role", binding.get("role") == signoff.get("role"), "Binding matches signer role."),
        _check("urpcccs_binding_reason", binding.get("reason_hash") == reason_hash, "Binding matches signoff reason."),
        _check("urpcccs_binding_signed_at", binding.get("signed_at") == signoff.get("signed_at"), "Binding matches signoff time."),
        _check("urpcccs_state_signed", state.get("status") == "signed" and state.get("signoff_hash") == signoff.get("integrity_hash"), "State binds current signed signoff."),
        _check("urpcccs_state_binding", state.get("signoff_binding_hash") == binding.get("integrity_hash"), "State binds the independent signoff binding."),
        _check("urpcccs_fingerprint_source", _source_projection(source) == _source_projection(fingerprint), "Fingerprint summary matches signed source."),
        _check("urpcccs_verification_source", verification.get("verification_report_hash") == source.get("command_center_verification_report_hash") and verification.get("zip_sha256") == source.get("command_center_zip_sha256") and verification.get("manifest_hash") == source.get("command_center_manifest_hash"), "Verification summary matches signed source."),
        _check("urpcccs_evidence_source", evidence.get("external_evidence_manifest_hash") == source.get("external_evidence_manifest_hash") and evidence.get("current_generation") == source.get("current_generation") and evidence.get("current_generation_hash") == source.get("current_generation_hash"), "Evidence summary matches signed source."),
        _check("urpcccs_checklist_ready", checklist.get("status") == "ready" and not (checklist.get("blockers") or []), "Final Handoff checklist is ready."),
        _check("urpcccs_manifest_signoff", manifest_source.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds signoff."),
        _check("urpcccs_manifest_binding", manifest_source.get("signoff_binding_hash") == binding.get("integrity_hash"), "Manifest binds signoff binding."),
    ]
    for field in _SOURCE_FIELDS:
        checks.append(_check(f"urpcccs_binding_source_{field}", binding.get(field) == source.get(field), f"Binding source field {field} matches signoff."))
    if signoff_event:
        checks.extend(
            [
                _check("urpcccs_state_signoff_event", state.get("signoff_event_hash") == signoff_event.get("event_hash"), "State binds the signoff history event."),
                _check("urpcccs_history_signoff_hash", signoff_event.get("signoff_hash") == signoff.get("integrity_hash"), "History signoff hash matches."),
                _check("urpcccs_history_signed_by", signoff_event.get("signed_by") == signoff.get("signed_by"), "History signer matches."),
                _check("urpcccs_history_role", signoff_event.get("role") == signoff.get("role"), "History role matches."),
                _check("urpcccs_history_source_hash", signoff_event.get("source_hash") == stable_hash(source), "History source hash matches."),
                _check("urpcccs_binding_history_event", binding.get("history_event_hash") == signoff_event.get("event_hash"), "Binding matches signoff history event."),
            ]
        )
    else:
        checks.append(_check("urpcccs_history_signoff_event", False, "History contains current signoff event."))
    checks.append(_check("urpcccs_latest_signoff_hash", bool(latest_state_event) and latest_state_event.get("signoff_hash") == signoff.get("integrity_hash"), "Latest signed state matches signoff."))
    for field in ("command_center_zip_sha256", "command_center_manifest_hash", "command_center_verification_report_hash", "external_evidence_manifest_hash"):
        checks.append(_check(f"urpcccs_manifest_source_{field}", manifest_source.get(field) == source.get(field), f"Manifest source field {field} matches signoff."))
    return checks


def _history_checks(history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    checks: list[dict[str, Any]] = []
    previous = ""
    latest_state: dict[str, Any] | None = None
    latest_signoff: dict[str, Any] | None = None
    for index, event in enumerate(history):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpcccs_history_{index:03d}_payload", event.get("payload_hash") == payload_hash, "History payload hash is valid."),
                _check(f"urpcccs_history_{index:03d}_event", event.get("event_hash") == event_hash, "History event hash is valid."),
                _check(f"urpcccs_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History chain is contiguous."),
            ]
        )
        previous = str(event.get("event_hash") or "")
        if event.get("event_type") in {"command_center_signoff_created", "command_center_signoff_reset"}:
            latest_state = event
        if event.get("event_type") == "command_center_signoff_created":
            latest_signoff = event
    checks.append(_check("urpcccs_history_not_empty", bool(history), "Signoff history exists."))
    return checks, latest_state, latest_signoff


def _external_binding_checks(path_value: Path | str | None, packaged: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not path_value:
        return [_check("urpcccs_external_signoff_binding_required", not require, "External signoff binding is provided.")]
    path = Path(path_value)
    checks = [_check("urpcccs_external_signoff_binding_exists", path.is_file(), "External signoff binding exists.")]
    if not path.is_file():
        return checks
    external = read_json(path)
    checks.extend(
        [
            _check("urpcccs_external_signoff_binding_integrity", _integrity_ok(external), "External signoff binding integrity is valid."),
            _check("urpcccs_external_signoff_binding_match", external == packaged and external.get("integrity_hash") == packaged.get("integrity_hash"), "Packaged binding exactly matches independent external binding."),
        ]
    )
    return checks


def _current_command_center_checks(
    zip_value: Path | str | None,
    report_value: Path | str | None,
    evidence_value: Path | str | None,
    signoff: dict[str, Any],
    binding: dict[str, Any],
    fingerprint: dict[str, Any],
    verification_summary: dict[str, Any],
    evidence_summary: dict[str, Any],
    *,
    require: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not zip_value or not report_value or not evidence_value:
        return [_check("urpcccs_current_command_center_evidence_required", not require, "Current Command Center ZIP, verification report, and evidence manifest are provided.")]
    zip_path, report_path, evidence_path = Path(zip_value), Path(report_value), Path(evidence_value)
    checks.extend(
        [
            _check("urpcccs_current_command_center_exists", zip_path.is_file(), "Current Command Center ZIP exists."),
            _check("urpcccs_current_verification_exists", report_path.is_file(), "Current Command Center verification report exists."),
            _check("urpcccs_current_evidence_manifest_exists", evidence_path.is_file(), "Current external evidence manifest exists."),
        ]
    )
    if _has_blockers(checks):
        return checks
    external = read_json(report_path)
    evidence = read_json(evidence_path)
    runtime = verify_unified_release_program_continuity_command_center_package(
        zip_path,
        strict=True,
        deep=True,
        require_ready=True,
        evidence_manifest_path=evidence_path,
    )
    source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
    current_state = evidence.get("current_state") if isinstance(evidence.get("current_state"), dict) else {}
    actual = {
        "command_center_zip_sha256": _sha256_path(zip_path),
        "command_center_zip_size_bytes": zip_path.stat().st_size,
        "command_center_manifest_hash": runtime.get("manifest_hash"),
        "command_center_verification_report_hash": external.get("integrity_hash"),
        "external_evidence_manifest_hash": evidence.get("integrity_hash"),
        "current_generation": current_state.get("generation"),
        "current_generation_hash": current_state.get("generation_hash"),
        "acceptance_signoff_hash": current_state.get("acceptance_signoff_hash"),
        "acceptance_history_event_hash": current_state.get("acceptance_history_event_hash"),
    }
    checks.extend(
        [
            _check("urpcccs_current_verification_integrity", _integrity_ok(external), "Current verification report integrity is valid."),
            _check("urpcccs_current_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, "Current verification report package type is valid."),
            _check("urpcccs_current_verification_status", external.get("status") == "passed", "Current verification report passed."),
            _check("urpcccs_current_runtime_status", runtime.get("status") == "passed", "Current Command Center runtime verification passed.", {"blockers": runtime.get("blockers") or []}),
            _check("urpcccs_current_external_report_binding", external.get("zip_sha256") == runtime.get("zip_sha256") == actual["command_center_zip_sha256"] and int(external.get("zip_size_bytes") or -1) == actual["command_center_zip_size_bytes"] and external.get("manifest_hash") == runtime.get("manifest_hash"), "External verification report binds the current Command Center ZIP."),
            _check("urpcccs_current_evidence_integrity", _integrity_ok(evidence), "Current evidence manifest integrity is valid."),
            _check("urpcccs_current_generation_signed", current_state.get("current") is True and current_state.get("acceptance_status") == "signed", "Current generation is signed."),
        ]
    )
    for field in _SOURCE_FIELDS:
        checks.append(_check(f"urpcccs_current_source_{field}", source.get(field) == actual.get(field) == binding.get(field) == fingerprint.get(field), f"Current source field {field} matches signed evidence."))
    checks.extend(
        [
            _check("urpcccs_current_verification_summary", verification_summary.get("verification_report_hash") == external.get("integrity_hash") and verification_summary.get("runtime_status") == runtime.get("status"), "Verification summary matches current runtime verification."),
            _check("urpcccs_current_evidence_summary", evidence_summary.get("external_evidence_manifest_hash") == evidence.get("integrity_hash"), "Evidence summary matches current evidence manifest."),
        ]
    )
    return checks


def _external_archive_checks(
    archive_zip_value: Path | str | None,
    report_value: Path | str | None,
    binding_value: Path | str | None,
    command_center_zip_value: Path | str | None,
    command_center_report_value: Path | str | None,
    evidence_value: Path | str | None,
    packaged_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    if not archive_zip_value or not report_value or not binding_value:
        return [_check("urpccch_external_archive_required", False, "External Archive ZIP, verification report, and signoff binding are required.")]
    archive_path, report_path = Path(archive_zip_value), Path(report_value)
    checks = [
        _check("urpccch_external_archive_exists", archive_path.is_file(), "External Archive ZIP exists."),
        _check("urpccch_external_archive_report_exists", report_path.is_file(), "External Archive verification report exists."),
    ]
    if _has_blockers(checks):
        return checks
    external = read_json(report_path)
    runtime = verify_unified_release_program_continuity_command_center_signoff_package(
        archive_path,
        strict=True,
        require_signed=True,
        signoff_binding_path=binding_value,
        command_center_zip_path=command_center_zip_value,
        command_center_verification_report_path=command_center_report_value,
        command_center_external_evidence_manifest_path=evidence_value,
    )
    checks.extend(
        [
            _check("urpccch_external_archive_report_integrity", _integrity_ok(external), "External Archive verification report integrity is valid."),
            _check("urpccch_external_archive_report_package_type", external.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "External Archive verification report package type is valid."),
            _check("urpccch_external_archive_report_status", external.get("status") == "passed", "External Archive verification report passed."),
            _check("urpccch_external_archive_runtime", runtime.get("status") == "passed", "External Archive runtime verification passed.", {"blockers": runtime.get("blockers") or []}),
            _check("urpccch_external_archive_zip_binding", packaged_summary.get("zip_sha256") == external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(archive_path), "Handoff binds current Archive ZIP."),
            _check("urpccch_external_archive_manifest_binding", packaged_summary.get("manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Handoff binds current Archive manifest."),
            _check("urpccch_external_archive_verification_binding", packaged_summary.get("verification_report_hash") == external.get("integrity_hash"), "Handoff binds external Archive verification report."),
        ]
    )
    return checks


_SOURCE_FIELDS = (
    "command_center_zip_sha256",
    "command_center_zip_size_bytes",
    "command_center_manifest_hash",
    "command_center_verification_report_hash",
    "external_evidence_manifest_hash",
    "current_generation",
    "current_generation_hash",
    "acceptance_signoff_hash",
    "acceptance_history_event_hash",
)


def _source_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {field: value.get(field) for field in _SOURCE_FIELDS}


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], required: set[str], prefix: str) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = required - {"manifest.json"}
    checks = [_check(f"{prefix}_manifest_files_exact", declared == expected, "Manifest files match fixed package entries.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)})]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in expected:
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}", row.get("sha256") == _sha256_bytes(data) and int(row.get("size_bytes") or -1) == len(data), "Manifest file hash and size match ZIP entry."))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id=check_id)


def _finish_archive(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    return _finish(checks, summary, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, *extra)


def _finish_handoff(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    return _finish(checks, summary, COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, *extra)


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], package_type: str, *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(value: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _has_blockers(checks: list[dict[str, Any]]) -> bool:
    return any(row.get("status") == "failed" for row in checks)
