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
from song_agent.unified_release_program_continuity_distribution_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_distribution_package,
)


UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION = 1
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_archive"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_response"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_response_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_EVIDENCE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_evidence"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_acceptance_signoff"

FIXED_ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "board-report.json",
    "decision-matrix.json",
    "receiver-index.json",
    "accepted-evidence-index.json",
    "external-evidence-manifest.json",
    "source-binding-summary.json",
    "signoff/continuity-acceptance-signoff.json",
    "signoff/continuity-acceptance-signoff-binding-summary.json",
    "signoff/continuity-acceptance-history.jsonl",
}

def verify_unified_release_program_continuity_acceptance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current_kit: bool = False,
    require_signed: bool = False,
    require_quorum: bool = False,
    continuity_kit_path: Path | str | None = None,
    continuity_kit_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
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
                package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpca_kernel",
                required_entries=frozenset(FIXED_ARCHIVE_ENTRIES),
                optional_entries=frozenset(),
                allowed_entry_patterns=(
                    r"responses/[A-Za-z0-9_.-]+\.json",
                    r"responses/[A-Za-z0-9_.-]+-(?:binding-summary|verification-report)\.json",
                    r"accepted-evidence/[A-Za-z0-9_.-]+/(?:accepted-evidence|evidence-report|original-response-public|response-binding-summary|response-verification-summary)\.json",
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
        return _finish(checks, summary, _check("urpca_zip_exists", False, "Continuity Acceptance Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpca_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpca_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            response_ids = {
                name[len("responses/") : -len(".json")]
                for name in name_set
                if name.startswith("responses/")
                and name.endswith(".json")
                and not name.endswith("-verification-report.json")
                and not name.endswith("-binding-summary.json")
            }
            evidence_ids = {
                name[len("accepted-evidence/") : -len("/accepted-evidence.json")]
                for name in name_set
                if name.startswith("accepted-evidence/") and name.endswith("/accepted-evidence.json")
            }
            expected = set(FIXED_ARCHIVE_ENTRIES)
            for response_id in response_ids:
                expected.update(
                    {
                        f"responses/{response_id}.json",
                        f"responses/{response_id}-verification-report.json",
                        f"responses/{response_id}-binding-summary.json",
                    }
                )
            for evidence_id in evidence_ids:
                expected.update(
                    {
                        f"accepted-evidence/{evidence_id}/accepted-evidence.json",
                        f"accepted-evidence/{evidence_id}/original-response-public.json",
                        f"accepted-evidence/{evidence_id}/response-verification-summary.json",
                        f"accepted-evidence/{evidence_id}/response-binding-summary.json",
                        f"accepted-evidence/{evidence_id}/evidence-report.json",
                    }
                )
            extra = sorted(name_set - expected)
            missing = sorted(expected - name_set)
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpca_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpca_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpca_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpca_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpca_no_nested_zip", not nested, "Continuity Acceptance Archive does not embed ZIP files.", {"nested": nested}),
                    _check("urpca_allowed_entries", not extra, "Archive contains only fixed/patterned entries.", {"extra": extra}),
                    _check("urpca_required_entries", not missing, "Archive contains required entries.", {"missing": missing}),
                ]
            )
            if _has_blocking_failures(checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "board-report.json")
            matrix = _read_json_entry(archive, "decision-matrix.json")
            receiver_index = _read_json_entry(archive, "receiver-index.json")
            accepted_index = _read_json_entry(archive, "accepted-evidence-index.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            source = _read_json_entry(archive, "source-binding-summary.json")
            signoff = _read_json_entry(archive, "signoff/continuity-acceptance-signoff.json")
            binding = _read_json_entry(archive, "signoff/continuity-acceptance-signoff-binding-summary.json")
            history = _parse_jsonl(archive.read("signoff/continuity-acceptance-history.jsonl").decode("utf-8"))
            responses = {response_id: _response_bundle(archive, response_id) for response_id in response_ids}
            evidences = {evidence_id: _evidence_bundle(archive, evidence_id) for evidence_id in evidence_ids}
            summary.update(
                {
                    "program_id": report.get("program_id") or manifest.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "signed": signoff.get("status") == "signed",
                    "accepted_count": (report.get("summary") or {}).get("accepted_count"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set, expected))
            for check_id, doc in (
                ("urpca_manifest_integrity", manifest),
                ("urpca_report_integrity", report),
                ("urpca_matrix_integrity", matrix),
                ("urpca_receiver_index_integrity", receiver_index),
                ("urpca_accepted_index_integrity", accepted_index),
                ("urpca_external_manifest_integrity", external_manifest),
                ("urpca_source_integrity", source),
                ("urpca_signoff_integrity", signoff),
                ("urpca_signoff_binding_integrity", binding),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(
                [
                    _check("urpca_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpca_report_package_type", report.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_PACKAGE_TYPE, "Board report package type is valid."),
                    _check("urpca_signoff_package_type", signoff.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SIGNOFF_PACKAGE_TYPE, "Signoff package type is valid."),
                ]
            )
            checks.extend(_document_binding_checks(manifest, report, matrix, receiver_index, accepted_index, external_manifest, source, signoff, binding))
            checks.extend(_response_checks(responses, source))
            participants, conflicts = _participants_from_evidence(evidences, responses)
            checks.extend(conflicts)
            rebuilt_matrix = _matrix_rows(participants)
            checks.append(_check("urpca_decision_matrix_semantics", matrix.get("rows") == rebuilt_matrix, "Decision matrix can be rebuilt from accepted evidence proofs."))
            readiness = _decision_readiness(report.get("policy") or {}, participants, _negative_response_conflicts(responses, report.get("policy") or {}))
            checks.extend(_board_semantic_checks(report, receiver_index, accepted_index, participants, readiness, require_quorum=require_quorum))
            checks.extend(_history_checks(history))
            checks.extend(_signoff_binding_checks(binding, signoff, history, report, matrix, receiver_index, accepted_index, source, require=require_signed))
            checks.extend(_external_signoff_binding_checks(signoff_binding_path, binding, signoff, history, report, matrix, receiver_index, accepted_index, source, require=require_signed))
            checks.extend(_current_kit_checks(source, continuity_kit_path, continuity_kit_verification_report_path, require=require_current_kit))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpca_zip_readable", False, "Continuity Acceptance Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_acceptance_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_continuity_acceptance_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _response_bundle(archive: zipfile.ZipFile, response_id: str) -> dict[str, Any]:
    return {
        "response": _read_json_entry(archive, f"responses/{response_id}.json"),
        "verification": _read_json_entry(archive, f"responses/{response_id}-verification-report.json"),
        "binding": _read_json_entry(archive, f"responses/{response_id}-binding-summary.json"),
    }


def _evidence_bundle(archive: zipfile.ZipFile, evidence_id: str) -> dict[str, Any]:
    prefix = f"accepted-evidence/{evidence_id}"
    return {
        "accepted": _read_json_entry(archive, f"{prefix}/accepted-evidence.json"),
        "public": _read_json_entry(archive, f"{prefix}/original-response-public.json"),
        "verification_summary": _read_json_entry(archive, f"{prefix}/response-verification-summary.json"),
        "binding": _read_json_entry(archive, f"{prefix}/response-binding-summary.json"),
        "report": _read_json_entry(archive, f"{prefix}/evidence-report.json"),
    }


def _response_checks(responses: dict[str, dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for response_id, bundle in sorted(responses.items()):
        response = bundle["response"]
        verification = bundle["verification"]
        binding = bundle["binding"]
        prefix = f"urpca_response_{_safe_check_key(response_id)}"
        checks.extend(
            [
                _check(f"{prefix}_package_type", response.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_PACKAGE_TYPE, "Response package type is valid."),
                _check(f"{prefix}_integrity", _integrity_ok(response), "Response integrity is valid."),
                _check(f"{prefix}_verification_package_type", verification.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_RESPONSE_VERIFICATION_PACKAGE_TYPE, "Response verification package type is valid."),
                _check(f"{prefix}_verification_integrity", _integrity_ok(verification), "Response verification integrity is valid."),
                _check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Response binding integrity is valid."),
                _check(f"{prefix}_payload_hash", response.get("payload_hash") == binding.get("payload_hash") == verification.get("payload_hash"), "Response payload hash is bound."),
                _check(f"{prefix}_kit_sha256", response.get("kit_sha256") == binding.get("kit_sha256") == source.get("kit_sha256"), "Response binds current kit hash."),
                _check(f"{prefix}_kit_manifest", response.get("kit_manifest_hash") == binding.get("kit_manifest_hash") == source.get("kit_manifest_hash"), "Response binds current kit manifest."),
                _check(f"{prefix}_kit_verification", response.get("kit_verification_report_hash") == binding.get("kit_verification_report_hash") == source.get("kit_verification_report_hash"), "Response binds current kit verification report."),
                _check(f"{prefix}_role", response.get("receiver_role") == binding.get("receiver_role"), "Response role matches binding."),
                _check(f"{prefix}_organization", response.get("organization") == binding.get("organization"), "Response organization matches binding."),
                _check(f"{prefix}_decision", response.get("decision") == binding.get("decision"), "Response decision matches binding."),
            ]
        )
    return checks


def _participants_from_evidence(evidences: dict[str, dict[str, Any]], responses: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    participants: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for evidence_id, bundle in sorted(evidences.items()):
        accepted = bundle["accepted"]
        public = bundle["public"]
        verification_summary = bundle["verification_summary"]
        binding = bundle["binding"]
        report = bundle["report"]
        response_id = str(accepted.get("response_id") or report.get("response_id") or "")
        response_bundle = responses.get(response_id)
        response_binding = response_bundle.get("binding") if response_bundle else {}
        response_verification = response_bundle.get("verification") if response_bundle else {}
        prefix = f"urpca_evidence_{_safe_check_key(evidence_id)}"
        for check_id, passed, message in (
            (f"{prefix}_accepted_integrity", _integrity_ok(accepted), "Accepted evidence integrity is valid."),
            (f"{prefix}_public_integrity", _integrity_ok(public), "Accepted public response integrity is valid."),
            (f"{prefix}_verification_summary_integrity", _integrity_ok(verification_summary), "Accepted response verification summary integrity is valid."),
            (f"{prefix}_binding_integrity", _integrity_ok(binding), "Accepted response binding integrity is valid."),
            (f"{prefix}_report_integrity", _integrity_ok(report), "Accepted evidence report integrity is valid."),
            (f"{prefix}_response_exists", bool(response_bundle), "Accepted evidence response exists in archive."),
            (f"{prefix}_role_binding", accepted.get("receiver_role") == binding.get("receiver_role") == response_binding.get("receiver_role"), "Accepted role matches response binding."),
            (f"{prefix}_org_binding", accepted.get("organization") == binding.get("organization") == response_binding.get("organization"), "Accepted organization matches response binding."),
            (f"{prefix}_decision_binding", accepted.get("decision") == binding.get("decision") == response_binding.get("decision") == "accepted", "Accepted decision matches response binding."),
            (f"{prefix}_verification_hash", verification_summary.get("verification_report_hash") == response_verification.get("integrity_hash"), "Accepted evidence summary matches response verification."),
        ):
            if not passed:
                conflicts.append(_check(check_id, False, message))
        participants.append(
            {
                "response_id": response_id,
                "evidence_id": evidence_id,
                "receiver_id": binding.get("receiver_id"),
                "role": binding.get("receiver_role"),
                "organization": binding.get("organization"),
                "decision": binding.get("decision"),
                "payload_hash": binding.get("payload_hash"),
                "binding_hash": binding.get("integrity_hash"),
                "verification_hash": verification_summary.get("verification_report_hash"),
                "source": "accepted_evidence_proof",
            }
        )
    return participants, conflicts


def _matrix_rows(participants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "response_id": row.get("response_id"),
            "evidence_id": row.get("evidence_id"),
            "receiver_id": row.get("receiver_id"),
            "role": row.get("role"),
            "organization": row.get("organization"),
            "decision": row.get("decision"),
            "source": row.get("source"),
            "payload_hash": row.get("payload_hash"),
            "binding_hash": row.get("binding_hash"),
        }
        for row in sorted(participants, key=lambda item: str(item.get("evidence_id") or ""))
    ]


def _negative_response_conflicts(responses: dict[str, dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for response_id, bundle in responses.items():
        binding = bundle["binding"]
        decision = binding.get("decision")
        if decision == "rejected" and bool(policy.get("block_on_rejected", True)):
            conflicts.append({"check_id": f"urpca_rejected_{_safe_check_key(response_id)}", "status": "failed", "reason": "rejected_response_present"})
        if decision == "needs_changes" and bool(policy.get("block_on_needs_changes", True)):
            conflicts.append({"check_id": f"urpca_needs_changes_{_safe_check_key(response_id)}", "status": "failed", "reason": "needs_changes_response_present"})
    return conflicts


def _decision_readiness(policy: dict[str, Any], participants: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {row.get("role") for row in accepted}
    orgs = {row.get("organization") for row in accepted}
    required_roles = set(policy.get("required_roles") or ["recovery_owner", "external_custodian"])
    min_count = int(policy.get("min_accepted_receipts") or policy.get("minimum_acceptances") or 2)
    min_orgs = int(policy.get("min_organizations") or policy.get("minimum_organizations") or 2)
    missing_roles = sorted(required_roles - roles)
    blockers: list[str] = []
    if len(accepted) < min_count:
        blockers.append("min_accepted_receipts")
    if len(orgs) < min_orgs:
        blockers.append("min_organizations")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("receiver_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(orgs), "missing_roles": missing_roles, "blockers": blockers}


def _board_semantic_checks(report: dict[str, Any], receiver_index: dict[str, Any], accepted_index: dict[str, Any], participants: list[dict[str, Any]], readiness: dict[str, Any], *, require_quorum: bool) -> list[dict[str, Any]]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return [
        _check("urpca_report_accepted_count", int(summary.get("accepted_count") or -1) == int(readiness.get("accepted_count") or 0), "Report accepted count matches rebuilt participants."),
        _check("urpca_report_organization_count", int(summary.get("organization_count") or -1) == int(readiness.get("organization_count") or 0), "Report organization count matches rebuilt participants."),
        _check("urpca_receiver_index_count", len(receiver_index.get("receivers") or []) == len(participants), "Receiver index count matches rebuilt participants."),
        _check("urpca_accepted_index_count", len(accepted_index.get("items") or []) == len(participants), "Accepted evidence index count matches rebuilt participants."),
        _check("urpca_require_quorum_ready", (not require_quorum) or report.get("status") in {"ready_for_signoff", "signed"} and readiness.get("status") == "ready_for_signoff", "Board quorum is ready when required.", {"rebuilt": readiness}),
    ]


def _document_binding_checks(manifest: dict[str, Any], report: dict[str, Any], matrix: dict[str, Any], receiver_index: dict[str, Any], accepted_index: dict[str, Any], external_manifest: dict[str, Any], source: dict[str, Any], signoff: dict[str, Any], binding: dict[str, Any]) -> list[dict[str, Any]]:
    docs = {
        "board_report_hash": report,
        "decision_matrix_hash": matrix,
        "receiver_index_hash": receiver_index,
        "accepted_evidence_index_hash": accepted_index,
        "external_evidence_manifest_hash": external_manifest,
        "source_binding_hash": source,
        "signoff_hash": signoff,
        "signoff_binding_hash": binding,
    }
    source_doc = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return [_check(f"urpca_manifest_{key}", source_doc.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}.") for key, doc in docs.items()]


def _signoff_binding_checks(binding: dict[str, Any], signoff: dict[str, Any], history: list[dict[str, Any]], report: dict[str, Any], matrix: dict[str, Any], receiver_index: dict[str, Any], accepted_index: dict[str, Any], source: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not binding:
        return [_check("urpca_signoff_binding_required", not require, "Signoff binding exists when required.")]
    event = next((row for row in reversed(history) if row.get("event_type") == "continuity_acceptance_signoff_created"), {})
    return [
        _check("urpca_signoff_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("urpca_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("urpca_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("urpca_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("urpca_signoff_binding_history", binding.get("history_event_hash") == event.get("event_hash"), "Signoff binding matches history event."),
        _check("urpca_signoff_binding_report", binding.get("board_report_hash") == report.get("integrity_hash") == signoff.get("board_report_hash"), "Signoff binds board report."),
        _check("urpca_signoff_binding_matrix", binding.get("decision_matrix_hash") == matrix.get("integrity_hash") == signoff.get("decision_matrix_hash"), "Signoff binds decision matrix."),
        _check("urpca_signoff_binding_receiver", binding.get("receiver_index_hash") == receiver_index.get("integrity_hash") == signoff.get("receiver_index_hash"), "Signoff binds receiver index."),
        _check("urpca_signoff_binding_accepted", binding.get("accepted_evidence_index_hash") == accepted_index.get("integrity_hash") == signoff.get("accepted_evidence_index_hash"), "Signoff binds accepted evidence index."),
        _check("urpca_signoff_binding_source", binding.get("source_binding_hash") == source.get("integrity_hash") == signoff.get("source_binding_hash"), "Signoff binds source summary."),
    ]


def _external_signoff_binding_checks(path: Path | str | None, binding: dict[str, Any], signoff: dict[str, Any], history: list[dict[str, Any]], report: dict[str, Any], matrix: dict[str, Any], receiver_index: dict[str, Any], accepted_index: dict[str, Any], source: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not path:
        if require:
            return [_check("urpca_external_signoff_binding_required", False, "External signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    if not binding_path.exists():
        return [_check("urpca_external_signoff_binding_exists", False, "External signoff binding proof exists.")]
    external = read_json(binding_path)
    checks = [
        _check("urpca_external_signoff_binding_integrity", _integrity_ok(external), "External signoff binding integrity is valid."),
        _check("urpca_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External signoff binding matches ZIP sidecar."),
    ]
    checks.extend(_signoff_binding_checks(external, signoff, history, report, matrix, receiver_index, accepted_index, source, require=require))
    return checks


def _current_kit_checks(source: dict[str, Any], kit_path: Path | str | None, verification_report_path: Path | str | None, *, require: bool) -> list[dict[str, Any]]:
    if not require:
        return []
    if not kit_path:
        return [_check("urpca_current_kit_required", False, "Current Continuity Kit ZIP is required.")]
    if not verification_report_path:
        return [_check("urpca_current_kit_verification_required", False, "Current Continuity Kit verification report is required.")]
    kit = Path(kit_path)
    report_path = Path(verification_report_path)
    checks = [
        _check("urpca_current_kit_exists", kit.exists() and kit.is_file(), "Current Continuity Kit ZIP exists."),
        _check("urpca_current_kit_report_exists", report_path.exists() and report_path.is_file(), "Current Continuity Kit verification report exists."),
    ]
    if any(row["status"] == "failed" for row in checks):
        return checks
    external = read_json(report_path)
    runtime = verify_unified_release_program_continuity_distribution_package(kit, strict=True, deep=True)
    checks.extend(
        [
            _check("urpca_current_kit_report_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, "Continuity Kit verification package type is valid."),
            _check("urpca_current_kit_report_integrity", _integrity_ok(external), "Continuity Kit verification report integrity is valid."),
            _check("urpca_current_kit_runtime_passed", runtime.get("status") == "passed", "Continuity Kit runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urpca_current_kit_report_passed", external.get("status") == "passed", "Continuity Kit external verification passed."),
            _check("urpca_current_kit_zip_sha256", source.get("kit_sha256") == external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(kit), "Continuity Kit ZIP hash matches source, report, and runtime."),
            _check("urpca_current_kit_manifest_hash", source.get("kit_manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Continuity Kit manifest hash matches source, report, and runtime."),
            _check("urpca_current_kit_verification_hash", source.get("kit_verification_report_hash") == external.get("integrity_hash"), "Continuity Kit verification hash matches source."),
        ]
    )
    return checks


def _history_checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, row in enumerate(rows, start=1):
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in {**row, "payload_hash": expected_payload}.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpca_history_{index:03d}_previous", row.get("previous_event_hash") == previous, "History previous hash matches."),
                _check(f"urpca_history_{index:03d}_payload", row.get("payload_hash") == expected_payload, "History payload hash matches."),
                _check(f"urpca_history_{index:03d}_event", row.get("event_hash") == expected_event, "History event hash matches."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str], expected_entries: set[str]) -> list[dict[str, Any]]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path") or "") for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check("urpca_manifest_files_exact", file_paths == expected_files, "Manifest files match archive layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpca_manifest_entries_exact", name_set == expected_entries, "Manifest entries match fixed/patterned layout.", {"missing": sorted(expected_entries - name_set), "extra": sorted(name_set - expected_entries)}),
        _check("urpca_manifest_zip_filename", (manifest.get("zip") or {}).get("filename") == "unified-release-program-continuity-acceptance-archive.zip", "Manifest ZIP filename is canonical."),
        _check("urpca_manifest_zip_entries", sorted((manifest.get("zip") or {}).get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"urpca_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists."))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpca_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."))
        checks.append(_check(f"urpca_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id="urpca_redaction_scan")


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], first_check: dict[str, Any] | None = None) -> dict[str, Any]:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)
