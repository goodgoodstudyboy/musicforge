# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import re as re
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
)
from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package

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

check = _make_deferred_global('check')
doc = _make_deferred_global('doc')
line = _make_deferred_global('line')
verify_unified_release_program_accepted_evidence_package = _make_deferred_global('verify_unified_release_program_accepted_evidence_package')

def bind_globals(namespace: dict[str, object]) -> None:
    global check, doc, line, verify_unified_release_program_accepted_evidence_package
    check = namespace.get('check', check)
    doc = namespace.get('doc', doc)
    line = namespace.get('line', line)
    verify_unified_release_program_accepted_evidence_package = namespace.get('verify_unified_release_program_accepted_evidence_package', verify_unified_release_program_accepted_evidence_package)
    _bind_deferred_defaults(namespace)


UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_archive"
UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_verification"
UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_external_evidence_manifest"
UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE = "musicforge_unified_release_program_review_pack"
UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_review_pack_verification"
UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE = "musicforge_unified_release_program_accepted_evidence"
UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_accepted_evidence_verification"
UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_review_response_verification"
UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION = 1
HANDOFF_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "program-handoff-report.json",
    "evidence-inventory.json",
    "recipient-guide.md",
    "decision-board.json",
    "conflict-report.json",
    "accepted-evidence-index.json",
    "handoff-readiness-matrix.json",
    "handoff-gap-plan.json",
    "external-evidence-manifest.json",
    "program-handoff-signoff.json",
    "program-handoff-signoff-binding-summary.json",
    "program-handoff-history.jsonl",
    "verification-summaries/program-verification-summary.json",
    "verification-summaries/operations-verification-summary.json",
    "verification-summaries/accepted-evidence-verification-summaries.json",
}
REVIEW_PACK_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "review-pack-report.json",
    "review-pack-binding-summary.json",
    "recipient-guide.md",
    "data/handoff-summary.json",
    "data/evidence-inventory-public.json",
    "data/risk-summary-public.json",
    "data/reviewer-form-template.json",
}
ACCEPTED_EVIDENCE_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "original-response-public.json",
    "response-verification-summary.json",
    "response-binding-summary.json",
    "accepted-evidence-report.json",
    "accepted-evidence-binding-summary.json",
}




def _external_operations_checks(row: DomainDocument | None, program_row: DomainDocument | None, *, require: bool, state: DomainDocument) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    if not row:
        if require:
            checks.append(_check("urph_external_operations_required", False, "External Program Operations evidence is required."))
        return checks
    zip_path = Path(str(row.get("operations_zip") or row.get("operations_archive_zip") or row.get("zip_path") or ""))
    report_path = Path(str(row.get("operations_verification_report") or row.get("operations_archive_verification_report") or row.get("verification_report_path") or ""))
    program_zip = Path(str(row.get("program_zip") or (program_row or {}).get("program_zip") or ""))
    program_report = Path(str(row.get("program_verification_report") or (program_row or {}).get("program_verification_report") or ""))
    program_binding = Path(str(row.get("program_signoff_binding") or (program_row or {}).get("program_signoff_binding") or ""))
    external_manifest = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or (program_row or {}).get("program_external_evidence_manifest") or (program_row or {}).get("external_evidence_manifest") or ""))
    checks.extend(_path_checks("urph_external_operations", {"zip": zip_path, "verification": report_path, "program_zip": program_zip, "program_verification": program_report, "program_binding": program_binding, "program_external_manifest": external_manifest}))
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = read_json(report_path)
    runtime = verify_unified_release_program_operations_package(
        zip_path,
        strict=True,
        require_current=True,
        require_signed_program=True,
        require_continuous_review_clear=True,
        require_lifecycle_audit=True,
        program_zip_path=program_zip,
        program_verification_report_path=program_report,
        program_signoff_binding_path=program_binding,
        external_evidence_manifest_path=external_manifest,
    )
    state["operations"] = {
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_hash": runtime.get("manifest_hash"),
        "verification_hash": _integrity_hash(external_report),
        "verification_status": external_report.get("status"),
        "runtime_status": runtime.get("status"),
    }
    checks.extend(
        [
            _check("urph_external_operations_verification_package_type", external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, "Operations verification package type is valid."),
            _check("urph_external_operations_verification_integrity", _integrity_ok(external_report), "Operations verification report integrity is valid."),
            _check("urph_external_operations_runtime_passed", runtime.get("status") == "passed", "Current Operations runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urph_external_operations_report_passed", external_report.get("status") == "passed", "Operations verification report passed."),
            _check("urph_external_operations_zip_sha256", external_report.get("zip_sha256") == runtime.get("zip_sha256") == state["operations"]["zip_sha256"], "Operations ZIP hash matches runtime and report."),
            _check("urph_external_operations_manifest_hash", external_report.get("manifest_hash") == runtime.get("manifest_hash"), "Operations manifest hash matches runtime and report."),
        ]
    )
    return checks

def _external_accepted_evidence_checks(row: DomainDocument, *, state: DomainDocument, index: int, require: bool) -> list[DomainDocument]:
    prefix = f"urph_external_accepted_{index:03d}"
    zip_path = Path(str(row.get("accepted_evidence_zip") or row.get("zip_path") or ""))
    report_path = Path(str(row.get("accepted_evidence_verification_report") or row.get("verification_report_path") or ""))
    response_verification = Path(str(row.get("response_verification_report") or row.get("response_verification_report_path") or ""))
    response_binding = Path(str(row.get("response_binding_summary") or row.get("response_binding_summary_path") or ""))
    checks = _path_checks(prefix, {"zip": zip_path, "verification": report_path, "response_verification": response_verification, "response_binding": response_binding})
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = read_json(report_path)
    runtime = verify_unified_release_program_accepted_evidence_package(
        zip_path,
        strict=True,
        require_accepted=require,
        response_verification_report_path=response_verification,
        response_binding_summary_path=response_binding,
    )
    item = {
        "evidence_id": runtime.get("summary", {}).get("evidence_id") or row.get("evidence_id"),
        "response_id": runtime.get("summary", {}).get("response_id") or row.get("response_id"),
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_hash": runtime.get("manifest_hash"),
        "verification_hash": _integrity_hash(external_report),
        "verification_status": external_report.get("status"),
        "runtime_status": runtime.get("status"),
        "reviewer_role": (runtime.get("summary") or {}).get("reviewer_role"),
        "organization": (runtime.get("summary") or {}).get("organization"),
        "decision": (runtime.get("summary") or {}).get("decision"),
    }
    state.setdefault("accepted", []).append(item)
    checks.extend(
        [
            _check(f"{prefix}_verification_package_type", external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, "Accepted Evidence verification package type is valid."),
            _check(f"{prefix}_verification_integrity", _integrity_ok(external_report), "Accepted Evidence verification report integrity is valid."),
            _check(f"{prefix}_runtime_passed", runtime.get("status") == "passed", "Accepted Evidence runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check(f"{prefix}_report_passed", external_report.get("status") == "passed", "Accepted Evidence verification report passed."),
            _check(f"{prefix}_zip_sha256", external_report.get("zip_sha256") == runtime.get("zip_sha256") == item["zip_sha256"], "Accepted Evidence ZIP hash matches runtime and report."),
            _check(f"{prefix}_manifest_hash", external_report.get("manifest_hash") == runtime.get("manifest_hash"), "Accepted Evidence manifest hash matches runtime and report."),
        ]
    )
    return checks

def _path_checks(prefix: str, paths: dict[str, Path]) -> list[DomainDocument]:
    return [_check(f"{prefix}_{key}_exists", path.exists() and path.is_file(), f"{key} exists.", {"path": str(path)}) for key, path in paths.items()]

def _handoff_semantic_checks(
    report: DomainDocument,
    inventory: DomainDocument,
    decision: DomainDocument,
    accepted_index: DomainDocument,
    program_summary: DomainDocument,
    operations_summary: DomainDocument,
    accepted_summary: DomainDocument,
    external: DomainDocument,
    *,
    require_current: bool,
    require_accepted: bool,
    require_signed: bool,
) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    program = external.get("program") or {}
    operations = external.get("operations") or {}
    accepted = external.get("accepted") or []
    if external.get("external_manifest"):
        checks.extend(
            [
                _check("urph_program_summary_runtime_binding", not program or program_summary.get("zip_sha256") == program.get("zip_sha256"), "Program summary binds runtime Program ZIP."),
                _check("urph_program_summary_verification_binding", not program or program_summary.get("verification_hash") == program.get("verification_hash"), "Program summary binds runtime Program verification report."),
                _check("urph_operations_summary_runtime_binding", not operations or operations_summary.get("zip_sha256") == operations.get("zip_sha256"), "Operations summary binds runtime Operations ZIP."),
                _check("urph_operations_summary_verification_binding", not operations or operations_summary.get("verification_hash") == operations.get("verification_hash"), "Operations summary binds runtime Operations verification report."),
            ]
        )
    inventory_items = [row for row in inventory.get("items", []) if isinstance(row, dict)]
    inventory_by_type = {row.get("evidence_type"): row for row in inventory_items}
    checks.extend(
        [
            _check("urph_inventory_has_program", "unified_release_program" in inventory_by_type, "Evidence inventory includes Program."),
            _check("urph_inventory_has_operations", "unified_release_program_operations" in inventory_by_type, "Evidence inventory includes Operations."),
        ]
    )
    accepted_rows = [row for row in accepted_index.get("items", []) if isinstance(row, dict)]
    accepted_external_by_id = {row.get("evidence_id"): row for row in accepted}
    for row in accepted_rows:
        ext = accepted_external_by_id.get(row.get("evidence_id"))
        if require_accepted:
            checks.append(_check(f"urph_accepted_external_{_safe_check_key(str(row.get('evidence_id')))}", bool(ext), "Accepted evidence has external verification proof."))
        if ext:
            checks.extend(
                [
                    _check(f"urph_accepted_role_{_safe_check_key(str(row.get('evidence_id')))}", row.get("role") == ext.get("reviewer_role"), "Accepted evidence role matches external proof."),
                    _check(f"urph_accepted_org_{_safe_check_key(str(row.get('evidence_id')))}", row.get("organization") == ext.get("organization"), "Accepted evidence organization matches external proof."),
                    _check(f"urph_accepted_decision_{_safe_check_key(str(row.get('evidence_id')))}", row.get("decision") == ext.get("decision"), "Accepted evidence decision matches external proof."),
                ]
            )
    required_roles = set((decision.get("policy") or {}).get("required_roles") or [])
    roles = {(row.get("reviewer_role") or row.get("role")) for row in accepted if row.get("decision") in {"accepted", "accepted_with_notes"}}
    if require_accepted:
        checks.append(_check("urph_require_accepted_count", len(accepted) >= int((decision.get("policy") or {}).get("minimum_acceptances") or 1), "Required accepted evidence count is met."))
        checks.append(_check("urph_require_accepted_roles", required_roles <= roles, "Required accepted evidence roles are met.", {"missing_roles": sorted(required_roles - roles)}))
        checks.append(_check("urph_require_decision_ready", (decision.get("readiness") or {}).get("status") == "ready_for_signoff", "Decision Board is ready for signoff."))
    if require_current:
        checks.append(_check("urph_require_current_program", program.get("runtime_status") == "passed" and program.get("verification_status") == "passed", "Current Program evidence passed."))
        checks.append(_check("urph_require_current_operations", operations.get("runtime_status") == "passed" and operations.get("verification_status") == "passed", "Current Operations evidence passed."))
    if require_signed:
        checks.append(_check("urph_require_signed_status", report.get("status") == "signed", "Program Handoff report is signed."))
    checks.append(_check("urph_accepted_summary_count", int(accepted_summary.get("summary", {}).get("accepted_count") or 0) == len(accepted_rows), "Accepted evidence verification summary count matches index."))
    return checks

def _accepted_evidence_semantic_checks(
    public_response: DomainDocument,
    response_summary: DomainDocument,
    response_binding: DomainDocument,
    report: DomainDocument,
    evidence_binding: DomainDocument,
    *,
    require_accepted: bool,
) -> list[DomainDocument]:
    reviewer = _as_document(report.get("reviewer"))
    return [
        _check("urpae_public_role_binding", public_response.get("reviewer_role") == reviewer.get("role") == response_binding.get("reviewer_role"), "Reviewer role is derived from original response binding."),
        _check("urpae_public_org_binding", public_response.get("organization") == reviewer.get("organization") == response_binding.get("organization"), "Reviewer organization is derived from original response binding."),
        _check("urpae_decision_binding", public_response.get("decision") == report.get("decision") == response_binding.get("decision"), "Decision is derived from original response binding."),
        _check("urpae_response_payload_hash", response_summary.get("response_payload_hash") == response_binding.get("response_payload_hash") == report.get("source", {}).get("response_payload_hash"), "Response payload hash is bound."),
        _check("urpae_binding_response_hash", evidence_binding.get("response_binding_hash") == response_binding.get("integrity_hash"), "Accepted evidence binding matches response binding."),
        _check("urpae_binding_report_hash", evidence_binding.get("accepted_evidence_report_hash") == report.get("integrity_hash"), "Accepted evidence binding matches report."),
        _check("urpae_require_accepted", (not require_accepted) or report.get("decision") in {"accepted", "accepted_with_notes"}, "Accepted evidence decision is accepted."),
    ]

def _external_response_binding_checks(
    response_verification_report_path: Path | str | None,
    response_binding_summary_path: Path | str | None,
    response_summary: DomainDocument,
    response_binding: DomainDocument,
    public_response: DomainDocument,
    report: DomainDocument,
    *,
    require: bool,
) -> list[DomainDocument]:
    if not response_verification_report_path or not response_binding_summary_path:
        if require:
            return [_check("urpae_external_response_proof_required", False, "External response verification and binding proof are required.")]
        return []
    verification_path = Path(response_verification_report_path)
    binding_path = Path(response_binding_summary_path)
    checks = _path_checks("urpae_external_response", {"verification": verification_path, "binding": binding_path})
    if any(row["status"] == "failed" for row in checks):
        return checks
    external_verification = read_json(verification_path)
    external_binding = read_json(binding_path)
    checks.extend(
        [
            _check("urpae_external_response_verification_package_type", external_verification.get("package_type") == UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE, "Response verification package type is valid."),
            _check("urpae_external_response_verification_integrity", _integrity_ok(external_verification), "Response verification integrity is valid."),
            _check("urpae_external_response_binding_integrity", _integrity_ok(external_binding), "Response binding integrity is valid."),
            _check("urpae_external_response_verification_hash", external_verification.get("integrity_hash") == response_summary.get("response_verification_hash"), "Response verification summary matches external report."),
            _check("urpae_external_response_binding_hash", external_binding.get("integrity_hash") == response_binding.get("integrity_hash"), "Response binding summary matches external binding."),
            _check("urpae_external_response_role", external_binding.get("reviewer_role") == public_response.get("reviewer_role") == (report.get("reviewer") or {}).get("role"), "Reviewer role matches external response binding."),
            _check("urpae_external_response_decision", external_binding.get("decision") == public_response.get("decision") == report.get("decision"), "Decision matches external response binding."),
        ]
    )
    return checks

def _handoff_document_binding_checks(
    manifest: DomainDocument,
    report: DomainDocument,
    inventory: DomainDocument,
    decision: DomainDocument,
    conflicts: DomainDocument,
    accepted_index: DomainDocument,
    readiness: DomainDocument,
    gap: DomainDocument,
    external_manifest: DomainDocument,
    signoff: DomainDocument,
    binding: DomainDocument,
    program_summary: DomainDocument,
    operations_summary: DomainDocument,
    accepted_summary: DomainDocument,
) -> list[DomainDocument]:
    source = _as_document(manifest.get("source"))
    docs = {
        "handoff_report_hash": report,
        "evidence_inventory_hash": inventory,
        "decision_board_hash": decision,
        "conflict_report_hash": conflicts,
        "accepted_evidence_index_hash": accepted_index,
        "readiness_matrix_hash": readiness,
        "gap_plan_hash": gap,
        "external_evidence_manifest_hash": external_manifest,
        "handoff_signoff_hash": signoff,
        "handoff_signoff_binding_hash": binding,
        "program_verification_summary_hash": program_summary,
        "operations_verification_summary_hash": operations_summary,
        "accepted_evidence_verification_summary_hash": accepted_summary,
    }
    return [_check(f"urph_manifest_{key}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}.") for key, doc in docs.items()]

def _handoff_signoff_binding_checks(binding: DomainDocument, signoff: DomainDocument, history: list[DomainDocument], report: DomainDocument, decision: DomainDocument, accepted_index: DomainDocument, external_manifest: DomainDocument, *, require: bool) -> list[DomainDocument]:
    if not binding:
        return [_check("urph_signoff_binding_required", not require, "Handoff signoff binding is present when required.")]
    signoff_event = next((row for row in reversed(history) if row.get("event_type") == "unified_release_program_handoff_signoff_created"), {})
    return [
        _check("urph_signoff_binding_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("urph_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("urph_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("urph_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("urph_signoff_binding_history_event", binding.get("latest_history_event_hash") == signoff_event.get("event_hash"), "Signoff binding matches latest signoff history event."),
        _check("urph_signoff_binding_report_hash", binding.get("handoff_report_hash") == report.get("integrity_hash") == signoff.get("handoff_report_hash"), "Binding report hash matches."),
        _check("urph_signoff_binding_decision_hash", binding.get("decision_board_hash") == decision.get("integrity_hash") == signoff.get("decision_board_hash"), "Binding decision board hash matches."),
        _check("urph_signoff_binding_accepted_index_hash", binding.get("accepted_evidence_index_hash") == accepted_index.get("integrity_hash") == signoff.get("accepted_evidence_index_hash"), "Binding accepted index hash matches."),
        _check("urph_signoff_binding_external_manifest_hash", binding.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash") == signoff.get("external_evidence_manifest_hash"), "Binding external evidence manifest hash matches."),
    ]

def _public_external_manifest(manifest: DomainDocument) -> DomainDocument:
    public_items = []
    allowed_exact = {
        "evidence_id",
        "evidence_type",
        "component_id",
        "program_id",
        "handoff_id",
        "response_id",
        "role",
        "organization",
        "decision",
    }
    allowed_suffixes = ("_hash", "_sha256", "_size_bytes", "_status")
    for row in manifest.get("items", []):
        if not isinstance(row, dict):
            continue
        public_row = {}
        for key, value in row.items():
            if key in allowed_exact or key.endswith(allowed_suffixes):
                public_row[key] = value
        if "evidence_id" not in public_row and row.get("evidence_id"):
            public_row["evidence_id"] = row.get("evidence_id")
        if "evidence_type" not in public_row and row.get("evidence_type"):
            public_row["evidence_type"] = row.get("evidence_type")
        if "component_id" not in public_row and row.get("component_id"):
            public_row["component_id"] = row.get("component_id")
        public_items.append(public_row)
    public = {
        "schema_version": manifest.get("schema_version") or UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": manifest.get("package_type") or UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": manifest.get("program_id"),
        "handoff_id": manifest.get("handoff_id"),
        "created_at": manifest.get("created_at"),
        "items": public_items,
        "summary": {"item_count": len(public_items)},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public

def _external_handoff_binding_checks(path: Path | str | None, binding: DomainDocument, signoff: DomainDocument, history: list[DomainDocument], report: DomainDocument, decision: DomainDocument, accepted_index: DomainDocument, external_manifest: DomainDocument, *, require: bool) -> list[DomainDocument]:
    if not path:
        if require:
            return [_check("urph_external_signoff_binding_required", False, "External Handoff signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    checks = [_check("urph_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External Handoff signoff binding proof exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = read_json(binding_path)
    checks.extend(
        [
            _check("urph_external_signoff_binding_integrity", _integrity_ok(external), "External Handoff signoff binding integrity is valid."),
            _check("urph_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External Handoff signoff binding matches ZIP sidecar hash."),
            _check("urph_external_signoff_binding_signed_by", external.get("signed_by") == binding.get("signed_by") == signoff.get("signed_by"), "External Handoff signoff binding matches signed_by."),
            _check("urph_external_signoff_binding_role", external.get("role") == binding.get("role") == signoff.get("role"), "External Handoff signoff binding matches role."),
            _check("urph_external_signoff_binding_reason", external.get("reason") == binding.get("reason") == signoff.get("reason"), "External Handoff signoff binding matches reason."),
        ]
    )
    checks.extend(_handoff_signoff_binding_checks(external, signoff, history, report, decision, accepted_index, external_manifest, require=require))
    return checks

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, name_set: set[str], expected_entries: set[str], prefix: str) -> list[DomainDocument]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path")) for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check(f"{prefix}_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check(f"{prefix}_manifest_no_zip_entry_spoof", set(manifest.get("zip", {}).get("entries") or []) <= name_set, "Manifest ZIP entries do not spoof extra paths."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}_hash", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks

def _history_checks(prefix: str, rows: list[DomainDocument]) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    previous = ""
    for index, event in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"{prefix}_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks

def _finish(checks: list[DomainDocument], summary: DomainDocument, package_type: str, first_check: DomainDocument | None = None) -> DomainDocument:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
    )

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _parse_jsonl(text: str) -> list[DomainDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]

def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> DomainDocument:
    return archive_redaction_check(archive, names, check_id=check_id)

def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
