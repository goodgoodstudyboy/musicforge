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

ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE = _make_deferred_global('ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE')
ARCHIVE_VERIFICATION_PACKAGE_TYPE = _make_deferred_global('ARCHIVE_VERIFICATION_PACKAGE_TYPE')
RESPONSE_BINDING_PACKAGE_TYPE = _make_deferred_global('RESPONSE_BINDING_PACKAGE_TYPE')
RESPONSE_VERIFICATION_PACKAGE_TYPE = _make_deferred_global('RESPONSE_VERIFICATION_PACKAGE_TYPE')
REVIEW_PACK_VERIFICATION_PACKAGE_TYPE = _make_deferred_global('REVIEW_PACK_VERIFICATION_PACKAGE_TYPE')
_archive_internal_checks = _make_deferred_global('_archive_internal_checks')
_findings_rows = _make_deferred_global('_findings_rows')
_finish = _make_deferred_global('_finish')
_has_blockers = _make_deferred_global('_has_blockers')
_history_checks = _make_deferred_global('_history_checks')
_json_bytes = _make_deferred_global('_json_bytes')
_manifest_checks = _make_deferred_global('_manifest_checks')
_matrix_rows = _make_deferred_global('_matrix_rows')
_parse_jsonl = _make_deferred_global('_parse_jsonl')
_participant_from_binding = _make_deferred_global('_participant_from_binding')
_prefix_checks = _make_deferred_global('_prefix_checks')
_quorum_result = _make_deferred_global('_quorum_result')
_read_json_entry = _make_deferred_global('_read_json_entry')
_redaction_check = _make_deferred_global('_redaction_check')
_response_payload_hash = _make_deferred_global('_response_payload_hash')
_response_public_projection = _make_deferred_global('_response_public_projection')
_reviewer_identity = _make_deferred_global('_reviewer_identity')
_safe_key = _make_deferred_global('_safe_key')
_source_package_summary_checks = _make_deferred_global('_source_package_summary_checks')
item = _make_deferred_global('item')
verify_accepted_evidence = _make_deferred_global('verify_accepted_evidence')
verify_review_pack = _make_deferred_global('verify_review_pack')

def bind_globals(namespace: dict[str, object]) -> None:
    global ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, ARCHIVE_VERIFICATION_PACKAGE_TYPE, RESPONSE_BINDING_PACKAGE_TYPE, RESPONSE_VERIFICATION_PACKAGE_TYPE, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, _archive_internal_checks, _findings_rows, _finish
    global _has_blockers, _history_checks, _json_bytes, _manifest_checks, _matrix_rows, _parse_jsonl, _participant_from_binding
    global _prefix_checks, _quorum_result, _read_json_entry, _redaction_check, _response_payload_hash, _response_public_projection, _reviewer_identity, _safe_key
    global _source_package_summary_checks, item, verify_accepted_evidence, verify_review_pack
    ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE = namespace.get('ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE', ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)
    ARCHIVE_VERIFICATION_PACKAGE_TYPE = namespace.get('ARCHIVE_VERIFICATION_PACKAGE_TYPE', ARCHIVE_VERIFICATION_PACKAGE_TYPE)
    RESPONSE_BINDING_PACKAGE_TYPE = namespace.get('RESPONSE_BINDING_PACKAGE_TYPE', RESPONSE_BINDING_PACKAGE_TYPE)
    RESPONSE_VERIFICATION_PACKAGE_TYPE = namespace.get('RESPONSE_VERIFICATION_PACKAGE_TYPE', RESPONSE_VERIFICATION_PACKAGE_TYPE)
    REVIEW_PACK_VERIFICATION_PACKAGE_TYPE = namespace.get('REVIEW_PACK_VERIFICATION_PACKAGE_TYPE', REVIEW_PACK_VERIFICATION_PACKAGE_TYPE)
    _archive_internal_checks = namespace.get('_archive_internal_checks', _archive_internal_checks)
    _findings_rows = namespace.get('_findings_rows', _findings_rows)
    _finish = namespace.get('_finish', _finish)
    _has_blockers = namespace.get('_has_blockers', _has_blockers)
    _history_checks = namespace.get('_history_checks', _history_checks)
    _json_bytes = namespace.get('_json_bytes', _json_bytes)
    _manifest_checks = namespace.get('_manifest_checks', _manifest_checks)
    _matrix_rows = namespace.get('_matrix_rows', _matrix_rows)
    _parse_jsonl = namespace.get('_parse_jsonl', _parse_jsonl)
    _participant_from_binding = namespace.get('_participant_from_binding', _participant_from_binding)
    _prefix_checks = namespace.get('_prefix_checks', _prefix_checks)
    _quorum_result = namespace.get('_quorum_result', _quorum_result)
    _read_json_entry = namespace.get('_read_json_entry', _read_json_entry)
    _redaction_check = namespace.get('_redaction_check', _redaction_check)
    _response_payload_hash = namespace.get('_response_payload_hash', _response_payload_hash)
    _response_public_projection = namespace.get('_response_public_projection', _response_public_projection)
    _reviewer_identity = namespace.get('_reviewer_identity', _reviewer_identity)
    _safe_key = namespace.get('_safe_key', _safe_key)
    _source_package_summary_checks = namespace.get('_source_package_summary_checks', _source_package_summary_checks)
    item = namespace.get('item', item)
    verify_accepted_evidence = namespace.get('verify_accepted_evidence', verify_accepted_evidence)
    verify_review_pack = namespace.get('verify_review_pack', verify_review_pack)
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




def verify_unified_release_program_continuity_command_center_acceptance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    signoff_binding_path: Path | str | None = None,
    review_pack_path: Path | str | None = None,
    review_pack_verification_report_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    response_proof_dir: Path | str | None = None,
    command_center_signoff_archive_path: Path | str | None = None,
    command_center_signoff_archive_verification_report_path: Path | str | None = None,
    command_center_final_handoff_path: Path | str | None = None,
    command_center_final_handoff_verification_report_path: Path | str | None = None,
    command_center_signoff_binding_path: Path | str | None = None,
    command_center_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    command_center_evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 256,
    max_entry_count: int = 100,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[DomainDocument] = []
    summary: DomainDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=ARCHIVE_PACKAGE_TYPE,
                verification_package_type=ARCHIVE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpccca_kernel",
                required_entries=frozenset(ARCHIVE_ENTRIES),
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
        return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE, _check("urpccca_zip_exists", False, "Receiver Acceptance Archive ZIP exists."))
    summary.update({"zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    checks.extend(
        [
            _check("urpccca_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "Archive ZIP size is within limit."),
            _check("urpccca_no_trailing_data", _zip_has_no_trailing_data(zip_path), "Archive ZIP has no trailing data."),
        ]
    )
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            checks.extend(
                [
                    _check("urpccca_no_duplicates", not duplicates, "Archive contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpccca_entry_count", len(infos) <= max_entry_count, "Archive entry count is within limit."),
                    _check("urpccca_uncompressed_size", sum(item.file_size for item in infos) <= max_uncompressed_size_mb * 1024 * 1024, "Archive uncompressed size is within limit."),
                    _check("urpccca_paths_safe", not unsafe, "Archive paths are safe.", {"unsafe": unsafe}),
                    _check("urpccca_allowed_entries", name_set == ARCHIVE_ENTRIES, "Archive has the fixed entry set.", {"extra": sorted(name_set - ARCHIVE_ENTRIES), "missing": sorted(ARCHIVE_ENTRIES - name_set)}),
                ]
            )
            if _has_blockers(checks):
                return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE)
            docs = {name: _read_json_entry(archive, name) for name in ARCHIVE_ENTRIES if name.endswith(".json")}
            manifest = docs["manifest.json"]
            signoff = docs["receiver-acceptance-signoff.json"]
            binding = docs["receiver-acceptance-signoff-binding-summary.json"]
            state = docs["receiver-acceptance-state.json"]
            policy = docs["receiver-acceptance-policy.json"]
            report = docs["receiver-acceptance-board-report.json"]
            matrix = docs["receiver-decision-matrix.json"]
            quorum = docs["receiver-quorum-report.json"]
            findings = docs["receiver-findings-register.json"]
            accepted_index = docs["accepted-evidence-index.json"]
            response_index = docs["response-proof-index.json"]
            handoff_summary = docs["source-handoff-summary.json"]
            archive_summary = docs["source-signoff-archive-summary.json"]
            history = _parse_jsonl(archive.read("receiver-acceptance-history.jsonl").decode("utf-8"))
            summary.update({"program_id": report.get("program_id"), "manifest_hash": manifest.get("integrity_hash"), "status": report.get("status"), "accepted_count": (quorum.get("summary") or {}).get("accepted_count")})
            checks.extend(_manifest_checks(archive, manifest, ARCHIVE_ENTRIES, "urpccca"))
            for name, doc in docs.items():
                checks.append(_check(f"urpccca_{_safe_key(name)}_integrity", _integrity_ok(doc), f"{name} integrity is valid."))
            checks.extend(_history_checks(history))
            checks.extend(_archive_internal_checks(manifest, signoff, binding, state, policy, report, matrix, quorum, findings, accepted_index, response_index, handoff_summary, archive_summary, history, require_signed=require_signed))
            if require_signed:
                if not signoff_binding_path or not Path(signoff_binding_path).is_file():
                    checks.append(_check("urpccca_external_signoff_binding_required", False, "External signoff binding is required."))
                else:
                    external_binding = read_json(Path(signoff_binding_path))
                    checks.extend(
                        [
                            _check("urpccca_external_signoff_binding_integrity", _integrity_ok(external_binding), "External signoff binding integrity is valid."),
                            _check("urpccca_external_signoff_binding_hash", external_binding.get("integrity_hash") == binding.get("integrity_hash"), "External signoff binding matches Archive binding."),
                        ]
                    )
            external_required = require_signed
            external_paths = (
                review_pack_path,
                review_pack_verification_report_path,
                accepted_evidence_dir,
                command_center_signoff_archive_verification_report_path,
                command_center_final_handoff_verification_report_path,
                command_center_signoff_binding_path,
                command_center_path,
                command_center_verification_report_path,
                command_center_evidence_manifest_path,
            )
            if external_required and not all(external_paths):
                checks.append(_check("urpccca_external_evidence_required", False, "Current Review Pack, response proofs, accepted evidence, and v12.10 evidence are required."))
            elif all(external_paths):
                checks.extend(
                    _archive_external_checks(
                        report,
                        matrix,
                        quorum,
                        findings,
                        accepted_index,
                        response_index,
                        handoff_summary,
                        archive_summary,
                        review_pack_path,
                        review_pack_verification_report_path,
                        accepted_evidence_dir,
                        response_proof_dir,
                        command_center_signoff_archive_path,
                        command_center_signoff_archive_verification_report_path,
                        command_center_final_handoff_path,
                        command_center_final_handoff_verification_report_path,
                        command_center_signoff_binding_path,
                        command_center_path,
                        command_center_verification_report_path,
                        command_center_evidence_manifest_path,
                    )
                )
            checks.append(_redaction_check(archive, names, "urpccca_redaction"))
    except (
        OSError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        ProgramPersistenceError,
    ) as exc:
        checks.append(_check("urpccca_zip_readable", False, "Receiver Acceptance Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE)

def validate_response_proof(
    response: DomainDocument,
    verification: DomainDocument,
    binding: DomainDocument,
    source: DomainDocument,
) -> list[DomainDocument]:
    projection = _response_public_projection(response)
    response_bytes = _json_bytes(response)
    required_source = {
        "review_pack_id": source.get("review_pack_id"),
        "review_pack_source_hash": source.get("review_pack_source_hash"),
        "review_pack_zip_sha256": source.get("review_pack_zip_sha256"),
        "review_pack_manifest_hash": source.get("review_pack_manifest_hash"),
        "review_pack_verification_report_hash": source.get("review_pack_verification_report_hash"),
        "command_center_signoff_archive_zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
        "command_center_signoff_archive_manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
        "command_center_signoff_archive_verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
        "command_center_final_handoff_zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
        "command_center_final_handoff_manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
        "command_center_final_handoff_verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
        "command_center_signoff_binding_hash": source.get("command_center_signoff_binding_hash"),
    }
    checks = [
        _check("urpcccar_response_type", response.get("package_type") == RESPONSE_PACKAGE_TYPE, "Response package type is valid."),
        _check("urpcccar_response_integrity", _integrity_ok(response), "Response integrity is valid."),
        _check("urpcccar_response_payload", response.get("payload_hash") == _response_payload_hash(response), "Response payload hash is valid."),
        _check("urpcccar_verification_type", verification.get("package_type") == RESPONSE_VERIFICATION_PACKAGE_TYPE, "Response verification package type is valid."),
        _check("urpcccar_verification_integrity", _integrity_ok(verification), "Response verification integrity is valid."),
        _check("urpcccar_verification_status", verification.get("status") == "passed", "Response verification passed."),
        _check("urpcccar_binding_type", binding.get("package_type") == RESPONSE_BINDING_PACKAGE_TYPE, "Response binding package type is valid."),
        _check("urpcccar_binding_integrity", _integrity_ok(binding), "Response binding integrity is valid."),
        _check("urpcccar_response_sha", verification.get("response_sha256") == binding.get("response_sha256") == _sha256_bytes(response_bytes), "Response byte hash is bound."),
        _check("urpcccar_payload_hash", verification.get("response_payload_hash") == binding.get("response_payload_hash") == response.get("payload_hash"), "Response payload hash is bound."),
        _check("urpcccar_verification_binding", binding.get("response_verification_report_hash") == verification.get("integrity_hash"), "Binding references response verification report."),
        _check("urpcccar_identity", verification.get("reviewer_identity_hash") == binding.get("reviewer_identity_hash") == stable_hash(_reviewer_identity(response)), "Reviewer identity is bound."),
        _check("urpcccar_decision", verification.get("decision_hash") == binding.get("decision_hash") == stable_hash({"decision": response.get("decision")}), "Decision is bound."),
        _check("urpcccar_findings", verification.get("findings_hash") == binding.get("findings_hash") == stable_hash({"findings": response.get("findings") or []}), "Findings are bound."),
        _check("urpcccar_public_projection", verification.get("response_public_projection_hash") == binding.get("response_public_projection_hash") == stable_hash(projection), "Public response projection is bound."),
        _check("urpcccar_decision_allowed", response.get("decision") in {"accepted", "needs_changes", "rejected"}, "Response decision is allowed."),
        _check("urpcccar_role_binding", verification.get("role") == binding.get("role") == response.get("role"), "Reviewer role comes from external proof."),
        _check("urpcccar_org_binding", verification.get("organization") == binding.get("organization") == response.get("organization"), "Reviewer organization comes from external proof."),
        _check("urpcccar_name_binding", verification.get("reviewer") == binding.get("reviewer") == response.get("reviewer"), "Reviewer name comes from external proof."),
        _check("urpcccar_decision_binding", verification.get("decision") == binding.get("decision") == response.get("decision"), "Decision comes from external proof."),
    ]
    for field, expected in required_source.items():
        checks.append(_check(f"urpcccar_source_{_safe_key(field)}", response.get(field) == verification.get(field) == binding.get(field) == expected, f"Response proof binds current {field}."))
    return checks

def write_verification_report(report: DomainDocument, path: Path | str) -> DomainDocument:
    write_json(Path(path), report)
    return report

def verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1

def _current_v1210_checks(
    source: DomainDocument,
    archive_path: Path,
    handoff_path: Path,
    archive_report_path: Path | str | None,
    handoff_report_path: Path | str | None,
    binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_report_path: Path | str | None,
    command_center_evidence_path: Path | str | None,
) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    paths = [archive_report_path, handoff_report_path, binding_path, command_center_path, command_center_report_path, command_center_evidence_path]
    if not all(paths) or not all(Path(path).is_file() for path in paths if path):
        return [_check("urpcccarp_v1210_paths", False, "All v12.10 external evidence paths exist.")]
    archive_external = read_json(_as_path(archive_report_path))
    handoff_external = read_json(_as_path(handoff_report_path))
    binding = read_json(_as_path(binding_path))
    archive_runtime = verify_unified_release_program_continuity_command_center_signoff_package(
        archive_path,
        strict=True,
        require_signed=True,
        signoff_binding_path=binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    handoff_runtime = verify_unified_release_program_continuity_command_center_final_handoff_package(
        handoff_path,
        strict=True,
        require_archive=True,
        archive_zip_path=archive_path,
        archive_verification_report_path=archive_report_path,
        signoff_binding_path=binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    expected = {
        "command_center_signoff_archive_zip_sha256": _sha256_path(archive_path),
        "command_center_signoff_archive_zip_size_bytes": archive_path.stat().st_size,
        "command_center_signoff_archive_manifest_hash": archive_runtime.get("manifest_hash"),
        "command_center_signoff_archive_verification_report_hash": archive_external.get("integrity_hash"),
        "command_center_final_handoff_zip_sha256": _sha256_path(handoff_path),
        "command_center_final_handoff_zip_size_bytes": handoff_path.stat().st_size,
        "command_center_final_handoff_manifest_hash": handoff_runtime.get("manifest_hash"),
        "command_center_final_handoff_verification_report_hash": handoff_external.get("integrity_hash"),
        "command_center_signoff_binding_hash": binding.get("integrity_hash"),
    }
    checks.extend(
        [
            _check("urpcccarp_archive_external_type", archive_external.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "Signoff Archive verification package type is valid."),
            _check("urpcccarp_handoff_external_type", handoff_external.get("package_type") == COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, "Final Handoff verification package type is valid."),
            _check("urpcccarp_archive_external_integrity", _integrity_ok(archive_external), "Signoff Archive external report integrity is valid."),
            _check("urpcccarp_handoff_external_integrity", _integrity_ok(handoff_external), "Final Handoff external report integrity is valid."),
            _check("urpcccarp_archive_runtime", archive_runtime.get("status") == "passed" and archive_external.get("status") == "passed", "Signoff Archive runtime and external verification passed.", {"blockers": archive_runtime.get("blockers") or []}),
            _check("urpcccarp_handoff_runtime", handoff_runtime.get("status") == "passed" and handoff_external.get("status") == "passed", "Final Handoff runtime and external verification passed.", {"blockers": handoff_runtime.get("blockers") or []}),
            _check("urpcccarp_archive_external_binding", archive_external.get("zip_sha256") == archive_runtime.get("zip_sha256") and archive_external.get("manifest_hash") == archive_runtime.get("manifest_hash"), "Signoff Archive external report matches nested ZIP."),
            _check("urpcccarp_handoff_external_binding", handoff_external.get("zip_sha256") == handoff_runtime.get("zip_sha256") and handoff_external.get("manifest_hash") == handoff_runtime.get("manifest_hash"), "Final Handoff external report matches nested ZIP."),
        ]
    )
    for field, value in expected.items():
        checks.append(_check(f"urpcccarp_source_{_safe_key(field)}", source.get(field) == value, f"Review Pack source binds {field}."))
    return checks

def _archive_external_checks(
    report: DomainDocument,
    matrix: DomainDocument,
    quorum: DomainDocument,
    findings: DomainDocument,
    accepted_index: DomainDocument,
    response_index: DomainDocument,
    handoff_summary: DomainDocument,
    archive_summary: DomainDocument,
    review_pack_path: Path | str | None,
    review_pack_report_path: Path | str | None,
    accepted_dir_value: Path | str | None,
    response_dir_value: Path | str | None,
    signoff_archive_path: Path | str | None,
    signoff_archive_report_path: Path | str | None,
    handoff_path: Path | str | None,
    handoff_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_report_path: Path | str | None,
    command_center_evidence_path: Path | str | None,
) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    review_pack = Path(review_pack_path) if review_pack_path else Path()
    review_report_path = Path(review_pack_report_path) if review_pack_report_path else Path()
    if not review_pack.is_file() or not review_report_path.is_file():
        return [_check("urpccca_review_pack_required", False, "Current Review Pack and verification report exist.")]
    review_external = read_json(review_report_path)
    review_runtime = verify_review_pack(
        review_pack,
        strict=True,
        require_current=True,
        signoff_archive_verification_report_path=signoff_archive_report_path,
        final_handoff_verification_report_path=handoff_report_path,
        signoff_binding_path=signoff_binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    checks.extend(
        [
            _check("urpccca_review_pack_external_type", review_external.get("package_type") == REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, "Review Pack verification package type is valid."),
            _check("urpccca_review_pack_external_integrity", _integrity_ok(review_external), "Review Pack verification report integrity is valid."),
            _check("urpccca_review_pack_runtime", review_runtime.get("status") == "passed" and review_external.get("status") == "passed", "Review Pack runtime and external verification passed.", {"blockers": review_runtime.get("blockers") or []}),
            _check("urpccca_review_pack_binding", review_external.get("zip_sha256") == review_runtime.get("zip_sha256") == _sha256_path(review_pack) and review_external.get("manifest_hash") == review_runtime.get("manifest_hash"), "Review Pack verification report matches current ZIP."),
        ]
    )
    source = _as_document(report.get("source"))
    checks.extend(
        [
            _check("urpccca_review_pack_source_hash", source.get("review_pack_source_hash") == review_runtime.get("source_hash"), "Board source binds Review Pack source."),
            _check("urpccca_review_pack_zip_hash", source.get("review_pack_zip_sha256") == review_runtime.get("zip_sha256"), "Board source binds Review Pack ZIP."),
            _check("urpccca_review_pack_manifest_hash", source.get("review_pack_manifest_hash") == review_runtime.get("manifest_hash"), "Board source binds Review Pack manifest."),
            _check("urpccca_review_pack_verification_hash", source.get("review_pack_verification_report_hash") == review_external.get("integrity_hash"), "Board source binds Review Pack verification report."),
        ]
    )
    accepted_dir = Path(accepted_dir_value) if accepted_dir_value else Path()
    response_dir = Path(response_dir_value) if response_dir_value else accepted_dir.parent / "responses"
    indexed_response_ids = {str(row.get("response_id") or "") for row in response_index.get("items") or [] if isinstance(row, dict)}
    external_response_ids = {path.name for path in response_dir.iterdir() if path.is_dir()} if response_dir.is_dir() else set()
    indexed_evidence_ids = {str(row.get("evidence_id") or "") for row in accepted_index.get("items") or [] if isinstance(row, dict)}
    external_evidence_ids = {path.name for path in accepted_dir.iterdir() if path.is_dir()} if accepted_dir.is_dir() else set()
    checks.extend(
        [
            _check("urpccca_external_response_set", external_response_ids == indexed_response_ids, "External response proof set exactly matches the signed index.", {"extra": sorted(external_response_ids - indexed_response_ids), "missing": sorted(indexed_response_ids - external_response_ids)}),
            _check("urpccca_external_evidence_set", external_evidence_ids == indexed_evidence_ids, "External Accepted Evidence set exactly matches the signed index.", {"extra": sorted(external_evidence_ids - indexed_evidence_ids), "missing": sorted(indexed_evidence_ids - external_evidence_ids)}),
        ]
    )
    participants: list[DomainDocument] = []
    external_responses: dict[str, DomainDocument] = {}
    for row in response_index.get("items") or []:
        if not isinstance(row, dict):
            continue
        response_id = str(row.get("response_id") or "")
        response_path = response_dir / response_id / "response.json"
        verification_path = response_dir / response_id / "response-verification-report.json"
        binding_path = response_dir / response_id / "response-binding-summary.json"
        if not all(path.is_file() for path in (response_path, verification_path, binding_path)):
            checks.append(_check(f"urpccca_response_{_safe_key(response_id)}_external", False, "External response proof exists."))
            continue
        response = read_json(response_path)
        verification = read_json(verification_path)
        binding = read_json(binding_path)
        checks.extend(_prefix_checks(validate_response_proof(response, verification, binding, source), f"urpccca_response_{_safe_key(response_id)}"))
        checks.extend(
            [
                _check(f"urpccca_response_{_safe_key(response_id)}_index_binding", row.get("response_integrity_hash") == response.get("integrity_hash") and row.get("verification_report_hash") == verification.get("integrity_hash") and row.get("binding_hash") == binding.get("integrity_hash"), "Response proof index binds external response proof."),
                _check(f"urpccca_response_{_safe_key(response_id)}_decision", row.get("decision") == binding.get("decision"), "Response proof index decision matches external proof."),
            ]
        )
        external_responses[response_id] = {"response": response, "verification": verification, "binding": binding}
    for row in accepted_index.get("items") or []:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        response_id = str(row.get("response_id") or "")
        evidence_zip = accepted_dir / evidence_id / "accepted-evidence.zip"
        evidence_report_path = accepted_dir / evidence_id / "verification-report.json"
        response_bundle = external_responses.get(response_id) or {}
        response_path = response_dir / response_id / "response.json"
        response_verification_path = response_dir / response_id / "response-verification-report.json"
        response_binding_path = response_dir / response_id / "response-binding-summary.json"
        if not evidence_zip.is_file() or not evidence_report_path.is_file():
            checks.append(_check(f"urpccca_evidence_{_safe_key(evidence_id)}_external", False, "External Accepted Evidence exists."))
            continue
        evidence_external = read_json(evidence_report_path)
        evidence_runtime = verify_accepted_evidence(
            evidence_zip,
            strict=True,
            require_response=True,
            response_path=response_path,
            response_verification_report_path=response_verification_path,
            response_binding_summary_path=response_binding_path,
        )
        checks.extend(
            [
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_report_type", evidence_external.get("package_type") == ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, "Accepted Evidence verification package type is valid."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_report_integrity", _integrity_ok(evidence_external), "Accepted Evidence verification report integrity is valid."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_runtime", evidence_runtime.get("status") == "passed" and evidence_external.get("status") == "passed", "Accepted Evidence runtime and external verification passed.", {"blockers": evidence_runtime.get("blockers") or []}),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_zip", row.get("zip_sha256") == evidence_runtime.get("zip_sha256") == evidence_external.get("zip_sha256") == _sha256_path(evidence_zip), "Accepted Evidence index binds current ZIP."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_manifest", row.get("manifest_hash") == evidence_runtime.get("manifest_hash") == evidence_external.get("manifest_hash"), "Accepted Evidence index binds manifest."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_verification", row.get("verification_report_hash") == evidence_external.get("integrity_hash"), "Accepted Evidence index binds verification report."),
            ]
        )
        binding = response_bundle.get("binding") or {}
        participants.append(_participant_from_binding(evidence_id, response_id, binding, row))
    policy = _as_document(report.get("policy"))
    rebuilt_findings = _findings_rows(external_responses)
    rebuilt_matrix = _matrix_rows(participants)
    rebuilt_quorum = _quorum_result(policy, participants, external_responses)
    checks.extend(
        [
            _check("urpccca_external_matrix", matrix.get("rows") == rebuilt_matrix, "Decision matrix is rebuilt from external proofs."),
            _check("urpccca_external_findings", findings.get("items") == rebuilt_findings, "Findings register is rebuilt from external proofs."),
            _check("urpccca_external_quorum", quorum.get("summary") == rebuilt_quorum, "Quorum is rebuilt from external proofs."),
            _check("urpccca_external_status", report.get("status") == "signed" and rebuilt_quorum.get("status") == "ready_for_signoff", "Signed Board is externally ready."),
        ]
    )
    checks.extend(
        _source_package_summary_checks(
            handoff_summary,
            archive_summary,
            signoff_archive_path,
            signoff_archive_report_path,
            handoff_path,
            handoff_report_path,
            signoff_binding_path,
        )
    )
    return checks
