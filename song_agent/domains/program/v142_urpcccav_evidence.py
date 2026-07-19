# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path
import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_hash as _integrity_hash,
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
from song_agent.platform.persistence.program import ProgramPersistenceError as ProgramPersistenceError, read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

SIGNOFF_BINDING_PACKAGE_TYPE = _make_deferred_global('SIGNOFF_BINDING_PACKAGE_TYPE')
field = _make_deferred_global('field')
line = _make_deferred_global('line')

def bind_globals(namespace: dict[str, object]) -> None:
    global SIGNOFF_BINDING_PACKAGE_TYPE, field, line
    SIGNOFF_BINDING_PACKAGE_TYPE = namespace.get('SIGNOFF_BINDING_PACKAGE_TYPE', SIGNOFF_BINDING_PACKAGE_TYPE)
    field = namespace.get('field', field)
    line = namespace.get('line', line)
    _bind_deferred_defaults(namespace)


SCHEMA_VERSION = 1
REVIEW_PACK_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_review_pack"
RESPONSE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_response"
ACCEPTED_EVIDENCE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_accepted_evidence"
BOARD_REPORT_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_board"
SIGNOFF_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_signoff"
ARCHIVE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_archive"
REVIEW_PACK_ENTRIES = {
    "manifest.json",
    "README.txt",
    "review-pack-report.json",
    "package-index.json",
    "verification-summary.json",
    "packages/command-center-signoff-archive.zip",
    "packages/command-center-final-handoff.zip",
}
ACCEPTED_EVIDENCE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "accepted-evidence.json",
    "original-response-public.json",
    "response-verification-summary.json",
    "response-binding-summary.json",
}
ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "receiver-acceptance-signoff.json",
    "receiver-acceptance-signoff-binding-summary.json",
    "receiver-acceptance-history.jsonl",
    "receiver-acceptance-state.json",
    "receiver-acceptance-policy.json",
    "receiver-acceptance-board-report.json",
    "receiver-decision-matrix.json",
    "receiver-quorum-report.json",
    "receiver-findings-register.json",
    "accepted-evidence-index.json",
    "response-proof-index.json",
    "source-handoff-summary.json",
    "source-signoff-archive-summary.json",
}
SOURCE_FIELDS = (
    "program_id",
    "command_center_signoff_archive_zip_sha256",
    "command_center_signoff_archive_zip_size_bytes",
    "command_center_signoff_archive_manifest_hash",
    "command_center_signoff_archive_verification_report_hash",
    "command_center_final_handoff_zip_sha256",
    "command_center_final_handoff_zip_size_bytes",
    "command_center_final_handoff_manifest_hash",
    "command_center_final_handoff_verification_report_hash",
    "command_center_signoff_binding_hash",
    "command_center_zip_sha256",
    "command_center_manifest_hash",
    "command_center_verification_report_hash",
    "external_evidence_manifest_hash",
)




def _source_package_summary_checks(
    handoff_summary: DomainDocument,
    archive_summary: DomainDocument,
    archive_path_value: Path | str | None,
    archive_report_value: Path | str | None,
    handoff_path_value: Path | str | None,
    handoff_report_value: Path | str | None,
    binding_path_value: Path | str | None,
) -> list[DomainDocument]:
    values = (archive_path_value, archive_report_value, handoff_path_value, handoff_report_value, binding_path_value)
    if not all(values) or not all(Path(value).is_file() for value in values if value):
        return [_check("urpccca_source_packages_required", False, "Current source packages and reports exist.")]
    archive_path = _as_path(archive_path_value)
    handoff_path = _as_path(handoff_path_value)
    archive_report = read_json(_as_path(archive_report_value))
    handoff_report = read_json(_as_path(handoff_report_value))
    binding = read_json(_as_path(binding_path_value))
    return [
        _check("urpccca_source_archive_zip", archive_summary.get("zip_sha256") == _sha256_path(archive_path) == archive_report.get("zip_sha256"), "Source Archive summary binds current ZIP."),
        _check("urpccca_source_archive_manifest", archive_summary.get("manifest_hash") == archive_report.get("manifest_hash"), "Source Archive summary binds manifest."),
        _check("urpccca_source_archive_verification", archive_summary.get("verification_report_hash") == archive_report.get("integrity_hash"), "Source Archive summary binds verification report."),
        _check("urpccca_source_handoff_zip", handoff_summary.get("zip_sha256") == _sha256_path(handoff_path) == handoff_report.get("zip_sha256"), "Source Handoff summary binds current ZIP."),
        _check("urpccca_source_handoff_manifest", handoff_summary.get("manifest_hash") == handoff_report.get("manifest_hash"), "Source Handoff summary binds manifest."),
        _check("urpccca_source_handoff_verification", handoff_summary.get("verification_report_hash") == handoff_report.get("integrity_hash"), "Source Handoff summary binds verification report."),
        _check("urpccca_source_signoff_binding", handoff_summary.get("signoff_binding_hash") == archive_summary.get("signoff_binding_hash") == binding.get("integrity_hash"), "Source summaries bind independent v12.10 signoff binding."),
    ]

def _archive_internal_checks(
    manifest: DomainDocument,
    signoff: DomainDocument,
    binding: DomainDocument,
    state: DomainDocument,
    policy: DomainDocument,
    report: DomainDocument,
    matrix: DomainDocument,
    quorum: DomainDocument,
    findings: DomainDocument,
    accepted_index: DomainDocument,
    response_index: DomainDocument,
    handoff_summary: DomainDocument,
    archive_summary: DomainDocument,
    history: list[DomainDocument],
    *,
    require_signed: bool,
) -> list[DomainDocument]:
    event = next((row for row in reversed(history) if row.get("event_type") == "receiver_acceptance_signoff_created"), {})
    source = _as_document(manifest.get("source"))
    docs = {
        "signoff_hash": signoff,
        "signoff_binding_hash": binding,
        "state_hash": state,
        "policy_hash": policy,
        "board_report_hash": report,
        "decision_matrix_hash": matrix,
        "quorum_report_hash": quorum,
        "findings_register_hash": findings,
        "accepted_evidence_index_hash": accepted_index,
        "response_proof_index_hash": response_index,
        "source_handoff_summary_hash": handoff_summary,
        "source_signoff_archive_summary_hash": archive_summary,
    }
    checks = [
        _check("urpccca_manifest_type", manifest.get("package_type") == ARCHIVE_PACKAGE_TYPE, "Archive manifest package type is valid."),
        _check("urpccca_signoff_type", signoff.get("package_type") == SIGNOFF_PACKAGE_TYPE, "Signoff package type is valid."),
        _check("urpccca_binding_type", binding.get("package_type") == SIGNOFF_BINDING_PACKAGE_TYPE, "Signoff binding package type is valid."),
        _check("urpccca_signoff_status", (not require_signed) or signoff.get("status") == "signed" and report.get("status") == "signed" and state.get("status") == "signed", "Archive is signed when required."),
        _check("urpccca_signoff_payload", signoff.get("payload_hash") == stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}}), "Signoff payload hash is valid."),
        _check("urpccca_binding_signoff", binding.get("signoff_hash") == signoff.get("integrity_hash") == state.get("signoff_hash"), "Binding and state match signoff."),
        _check("urpccca_binding_signer", binding.get("signed_by") == signoff.get("signed_by") and binding.get("role") == signoff.get("role") and binding.get("signed_at") == signoff.get("signed_at"), "Binding matches signoff public fields."),
        _check("urpccca_binding_history", binding.get("history_event_hash") == event.get("event_hash") == state.get("signoff_event_hash"), "Binding and state match signoff history event."),
        _check("urpccca_event_signoff", event.get("signoff_hash") == signoff.get("integrity_hash") and event.get("signoff_payload_hash") == signoff.get("payload_hash"), "History event binds signoff."),
        _check("urpccca_report_policy", report.get("policy_hash") == quorum.get("policy_hash") == stable_hash(report.get("policy") or {}), "Board report and quorum bind policy."),
        _check("urpccca_policy_document", all(policy.get(key) == (report.get("policy") or {}).get(key) for key in ("min_accepted_count", "min_organization_count", "required_roles", "block_on_rejected", "block_on_needs_changes", "block_on_critical_findings")), "Archived policy document matches the signed Board policy."),
    ]
    for key, doc in docs.items():
        checks.append(_check(f"urpccca_manifest_{_safe_key(key)}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}."))
    signoff_docs = {
        "board_report_hash": report,
        "decision_matrix_hash": matrix,
        "quorum_report_hash": quorum,
        "findings_register_hash": findings,
        "accepted_evidence_index_hash": accepted_index,
        "response_proof_index_hash": response_index,
    }
    for key, doc in signoff_docs.items():
        checks.append(_check(f"urpccca_signoff_{_safe_key(key)}", signoff.get(key) == binding.get(key) == doc.get("integrity_hash"), f"Signoff and binding bind {key}."))
    return checks

def _package_index_matches(index: DomainDocument, archive: zipfile.ZipFile, source: DomainDocument) -> bool:
    rows = _as_list(index.get("packages"))
    expected = [
        {
            "component_type": "command_center_signoff_archive",
            "path": "packages/command-center-signoff-archive.zip",
            "package_type": COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
            "zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
            "zip_size_bytes": source.get("command_center_signoff_archive_zip_size_bytes"),
            "manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
            "verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
        },
        {
            "component_type": "command_center_final_handoff",
            "path": "packages/command-center-final-handoff.zip",
            "package_type": COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE,
            "zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
            "zip_size_bytes": source.get("command_center_final_handoff_zip_size_bytes"),
            "manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
            "verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
        },
    ]
    if rows != expected:
        return False
    return all(
        row.get("zip_sha256") == _sha256_bytes(archive.read(str(row.get("path") or "")))
        and int(row.get("zip_size_bytes") or -1) == len(archive.read(str(row.get("path") or "")))
        for row in expected
    )

def _participant_from_binding(evidence_id: str, response_id: str, binding: DomainDocument, index_row: DomainDocument) -> DomainDocument:
    return {
        "evidence_id": evidence_id,
        "response_id": response_id,
        "reviewer": binding.get("reviewer"),
        "organization": binding.get("organization"),
        "role": binding.get("role"),
        "decision": binding.get("decision"),
        "reviewer_identity_hash": binding.get("reviewer_identity_hash"),
        "decision_hash": binding.get("decision_hash"),
        "response_binding_hash": binding.get("integrity_hash"),
        "accepted_evidence_verification_hash": index_row.get("verification_report_hash"),
    }

def _matrix_rows(participants: list[DomainDocument]) -> list[DomainDocument]:
    return sorted(participants, key=lambda row: (str(row.get("role") or ""), str(row.get("response_id") or "")))

def _findings_rows(responses: dict[str, DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for response_id, bundle in sorted(responses.items()):
        for index, finding in enumerate(bundle["response"].get("findings") or [], start=1):
            if not isinstance(finding, dict):
                continue
            rows.append(
                {
                    "response_id": response_id,
                    "finding_id": str(finding.get("finding_id") or f"finding-{index:03d}"),
                    "severity": str(finding.get("severity") or "info").lower(),
                    "category": str(finding.get("category") or "general"),
                    "summary": str(finding.get("summary") or "")[:500],
                    "finding_hash": stable_hash(finding),
                }
            )
    return rows

def _quorum_result(policy: DomainDocument, participants: list[DomainDocument], responses: dict[str, DomainDocument]) -> DomainDocument:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {str(row.get("role") or "") for row in accepted}
    organizations = {str(row.get("organization") or "") for row in accepted}
    required_roles = set(policy.get("required_roles") or ["continuity_owner", "operations_owner"])
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_count") or 2):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 2):
        blockers.append("min_organization_count")
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        blockers.append("required_roles")
    decisions = [bundle["binding"].get("decision") for bundle in responses.values()]
    if policy.get("block_on_rejected", True) and "rejected" in decisions:
        blockers.append("rejected_response")
    if policy.get("block_on_needs_changes", True) and "needs_changes" in decisions:
        blockers.append("needs_changes_response")
    critical = any(str(finding.get("severity") or "").lower() == "critical" for bundle in responses.values() for finding in bundle["response"].get("findings") or [] if isinstance(finding, dict))
    if policy.get("block_on_critical_findings", True) and critical:
        blockers.append("critical_finding")
    return {
        "status": "blocked" if blockers else "ready_for_signoff",
        "accepted_count": len(accepted),
        "organization_count": len(organizations),
        "required_roles": sorted(required_roles),
        "missing_roles": missing_roles,
        "blockers": blockers,
    }

def _response_public_projection(response: DomainDocument) -> DomainDocument:
    return {
        "schema_version": SCHEMA_VERSION,
        "package_type": f"{RESPONSE_PACKAGE_TYPE}_public_projection",
        "program_id": response.get("program_id"),
        "response_id": response.get("response_id"),
        "reviewer": response.get("reviewer"),
        "organization": response.get("organization"),
        "role": response.get("role"),
        "decision": response.get("decision"),
        "findings": response.get("findings") or [],
        "created_at": response.get("created_at"),
    }

def _reviewer_identity(response: DomainDocument) -> DomainDocument:
    return {"reviewer": response.get("reviewer"), "organization": response.get("organization"), "role": response.get("role")}

def _source_projection(source: DomainDocument) -> DomainDocument:
    return {field: source.get(field) for field in SOURCE_FIELDS}

def _response_payload_hash(response: DomainDocument) -> str:
    return stable_hash({key: value for key, value in response.items() if key not in {"payload_hash", "integrity_hash"}})

def _with_integrity(doc: DomainDocument) -> DomainDocument:
    output = dict(doc)
    output["integrity_hash"] = _integrity_hash(output)
    return output

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, required: set[str], prefix: str) -> list[DomainDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = required - {"manifest.json"}
    checks = [
        _check(f"{prefix}_manifest_integrity", _integrity_ok(manifest), "Manifest integrity is valid."),
        _check(f"{prefix}_manifest_files_exact", declared == expected, "Manifest files match fixed entries.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
    ]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in expected:
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_key(rel)}", row.get("sha256") == _sha256_bytes(data) and int(row.get("size_bytes") or -1) == len(data), "Manifest file hash and size match ZIP entry."))
    return checks

def _history_checks(rows: list[DomainDocument]) -> list[DomainDocument]:
    if not rows:
        return [_check("urpccca_history_required", False, "Signoff history exists.")]
    checks: list[DomainDocument] = []
    previous = ""
    for index, row in enumerate(rows, start=1):
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in {**row, "payload_hash": expected_payload}.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpccca_history_{index:03d}_previous", str(row.get("previous_event_hash") or "") == previous, "History previous hash matches."),
                _check(f"urpccca_history_{index:03d}_payload", row.get("payload_hash") == expected_payload, "History payload hash matches."),
                _check(f"urpccca_history_{index:03d}_event", row.get("event_hash") == expected_event, "History event hash matches."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks

def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> DomainDocument:
    return archive_redaction_check(archive, names, check_id=check_id)

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _parse_jsonl(value: str) -> list[DomainDocument]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]

def _json_bytes(value: DomainDocument) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower() or "item"

def _prefix_checks(checks: list[DomainDocument], prefix: str) -> list[DomainDocument]:
    return [{**row, "check_id": f"{prefix}_{row.get('check_id')}"} for row in checks]

def _has_blockers(checks: list[DomainDocument]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)

def _finish(checks: list[DomainDocument], summary: DomainDocument, package_type: str, *extra: DomainDocument) -> DomainDocument:
    checks.extend(extra)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=SCHEMA_VERSION,
    )
