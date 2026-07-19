# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list, as_text as _as_text
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.domains.program.ports import ProgramReleaseStore as ProgramReleaseStore
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_handoff_verifier import ACCEPTED_EVIDENCE_REQUIRED_ENTRIES as ACCEPTED_EVIDENCE_REQUIRED_ENTRIES, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE, verify_unified_release_program_accepted_evidence_package as verify_unified_release_program_accepted_evidence_package, verify_unified_release_program_handoff_package as verify_unified_release_program_handoff_package, verify_unified_release_program_review_pack_package as verify_unified_release_program_review_pack_package, write_unified_release_program_accepted_evidence_verification_report as write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_handoff_verification_report as write_unified_release_program_handoff_verification_report, write_unified_release_program_review_pack_verification_report as write_unified_release_program_review_pack_verification_report
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

UnifiedReleaseProgramHandoffStateError = _make_deferred_global('UnifiedReleaseProgramHandoffStateError')
_check = _make_deferred_global('_check')
_file_record = _make_deferred_global('_file_record')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_row = _make_deferred_global('_manifest_row')
_path_checks = _make_deferred_global('_path_checks')
_read_optional_json = _make_deferred_global('_read_optional_json')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_source_without_checks = _make_deferred_global('_source_without_checks')
_with_integrity = _make_deferred_global('_with_integrity')
info = _make_deferred_global('info')
item = _make_deferred_global('item')
path = _make_deferred_global('path')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramHandoffStateError, _check, _file_record, _integrity_hash, _integrity_ok, _manifest_row, _path_checks
    global _read_optional_json, _safe_id, _sha256_path, _source_without_checks, _with_integrity, info, item, path
    global read_json, write_json
    UnifiedReleaseProgramHandoffStateError = namespace.get('UnifiedReleaseProgramHandoffStateError', UnifiedReleaseProgramHandoffStateError)
    _check = namespace.get('_check', _check)
    _file_record = namespace.get('_file_record', _file_record)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_row = namespace.get('_manifest_row', _manifest_row)
    _path_checks = namespace.get('_path_checks', _path_checks)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _source_without_checks = namespace.get('_source_without_checks', _source_without_checks)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    info = namespace.get('info', info)
    item = namespace.get('item', item)
    path = namespace.get('path', path)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


DEFAULT_BOARD_POLICY = {
    "minimum_acceptances": 1,
    "minimum_organizations": 1,
    "required_roles": ["release_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_finding": True,
}




class UnifiedReleaseProgramHandoffStoreLifecycleMixin:
    def _current_operations_state(self, external_manifest: DomainDocument) -> DomainDocument:
        row = _manifest_row(external_manifest, "unified_release_program_operations")
        program_row = _manifest_row(external_manifest, "unified_release_program") or {}
        checks: list[DomainDocument] = []
        if not row:
            return {"status": "missing", "checks": [_check("operations_evidence_required", False, "Program Operations evidence is required.")]}
        zip_path = Path(str(row.get("operations_zip") or row.get("operations_archive_zip") or ""))
        report_path = Path(str(row.get("operations_verification_report") or row.get("operations_archive_verification_report") or ""))
        program_zip = Path(str(row.get("program_zip") or program_row.get("program_zip") or ""))
        program_report = Path(str(row.get("program_verification_report") or program_row.get("program_verification_report") or ""))
        program_binding = Path(str(row.get("program_signoff_binding") or program_row.get("program_signoff_binding") or ""))
        program_external = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or program_row.get("program_external_evidence_manifest") or program_row.get("external_evidence_manifest") or ""))
        checks.extend(_path_checks("operations", {"zip": zip_path, "verification": report_path, "program_zip": program_zip, "program_verification": program_report, "program_binding": program_binding, "program_external_manifest": program_external}))
        if any(item["status"] == "failed" for item in checks):
            return {"status": "missing", "checks": checks}
        external = read_json(report_path)
        runtime = verify_unified_release_program_operations_package(zip_path, strict=True, require_current=True, require_signed_program=True, require_continuous_review_clear=True, require_lifecycle_audit=True, program_zip_path=program_zip, program_verification_report_path=program_report, program_signoff_binding_path=program_binding, external_evidence_manifest_path=program_external)
        checks.extend(
            [
                _check("operations_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, "Operations verification package type is valid."),
                _check("operations_verification_integrity", _integrity_ok(external), "Operations verification integrity is valid."),
                _check("operations_runtime_passed", runtime.get("status") == "passed", "Operations runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("operations_external_passed", external.get("status") == "passed", "Operations external verification passed."),
                _check("operations_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Operations ZIP hash is current."),
                _check("operations_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Operations manifest hash is current."),
            ]
        )
        return {
            "status": "ready" if not [item for item in checks if item.get("status") == "failed"] else "failed",
            "checks": checks,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": _integrity_hash(external),
            "verification_status": external.get("status"),
            "runtime_status": runtime.get("status"),
        }

    def _evidence_inventory(self, program_id: str, handoff_id: str, program_state: DomainDocument, operations_state: DomainDocument, participants: list[DomainDocument]) -> DomainDocument:
        items = [
            {"item_id": "evi-program-current", "evidence_type": "unified_release_program", "component_id": program_id, **_source_without_checks(program_state)},
            {"item_id": "evi-program-operations", "evidence_type": "unified_release_program_operations", "component_id": program_id, **_source_without_checks(operations_state)},
        ]
        for participant in participants:
            items.append({"item_id": f"evi-{participant.get('accepted_evidence_id')}", "evidence_type": "program_accepted_evidence", "component_id": handoff_id, "status": "ready", "evidence_id": participant.get("accepted_evidence_id"), "role": participant.get("role"), "organization": participant.get("organization"), "decision": participant.get("decision")})
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_evidence_inventory",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "items": items,
                "summary": {
                    "ready_count": sum(1 for row in items if row.get("status") == "ready"),
                    "failed_count": sum(1 for row in items if row.get("status") == "failed"),
                    "missing_count": sum(1 for row in items if row.get("status") == "missing"),
                    "accepted_evidence_count": len(participants),
                },
            }
        )

    def _accepted_participants(self, program_id: str) -> tuple[list[DomainDocument], list[DomainDocument]]:
        base = self.handoff_dir(program_id) / "accepted-evidence"
        participants: list[DomainDocument] = []
        conflicts: list[DomainDocument] = []
        if not base.exists():
            return participants, conflicts
        for report_path in sorted(base.glob("*/accepted-evidence-report.json")):
            evidence_dir = report_path.parent
            report = read_json(report_path)
            binding_path = evidence_dir / "response-binding-summary.json"
            verification_summary_path = evidence_dir / "response-verification-summary.json"
            evidence_binding_path = evidence_dir / "accepted-evidence-binding-summary.json"
            if not binding_path.exists() or not verification_summary_path.exists() or not evidence_binding_path.exists():
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "missing_response_proof"})
                continue
            binding = read_json(binding_path)
            verification_summary = read_json(verification_summary_path)
            evidence_binding = read_json(evidence_binding_path)
            if not (_integrity_ok(report) and _integrity_ok(binding) and _integrity_ok(verification_summary) and _integrity_ok(evidence_binding)):
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "integrity_failed"})
                continue
            role = binding.get("reviewer_role")
            organization = binding.get("organization")
            decision = binding.get("decision")
            if role != (report.get("reviewer") or {}).get("role") or organization != (report.get("reviewer") or {}).get("organization") or decision != report.get("decision"):
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "accepted_evidence_role_mismatch"})
                continue
            participants.append(
                {
                    "reviewer_id": binding.get("reviewer_id"),
                    "role": role,
                    "organization": organization,
                    "decision": decision,
                    "accepted_evidence_id": report.get("evidence_id"),
                    "response_id": report.get("response_id"),
                    "source_verified": True,
                    "accepted_evidence_zip_sha256": _sha256_path(self.accepted_evidence_zip_path(program_id, str(report.get("evidence_id")))),
                    "accepted_evidence_verification_hash": _integrity_hash(_read_optional_json(self.accepted_evidence_verification_report_path(program_id, str(report.get("evidence_id"))))),
                }
            )
        return participants, conflicts

    def _response_decision_conflicts(self, program_id: str, policy: DomainDocument) -> list[DomainDocument]:
        base = self.handoff_dir(program_id) / "responses"
        conflicts: list[DomainDocument] = []
        if not base.exists():
            return conflicts
        for response_path in sorted(base.glob("*/response.json")):
            try:
                response = read_json(response_path)
            except Exception as exc:
                conflicts.append({"response_id": response_path.parent.name, "reason": "response_unreadable", "message": sanitize_sensitive_text(str(exc))})
                continue
            response_id = str(response.get("response_id") or response_path.parent.name)
            decision = str(response.get("decision") or "")
            base_row = {
                "response_id": response_id,
                "reviewer_id": response.get("reviewer_id"),
                "role": response.get("reviewer_role"),
                "organization": response.get("organization"),
                "decision": decision,
            }
            if not _integrity_ok(response):
                conflicts.append({**base_row, "reason": "response_integrity_failed"})
                continue
            verification = _read_optional_json(self.response_verification_path(program_id, response_id))
            binding = _read_optional_json(self.response_binding_path(program_id, response_id))
            if not verification or not binding or not _integrity_ok(verification) or not _integrity_ok(binding):
                conflicts.append({**base_row, "reason": "response_binding_failed"})
                continue
            if binding.get("decision") != decision or binding.get("reviewer_role") != response.get("reviewer_role") or binding.get("organization") != response.get("organization"):
                conflicts.append({**base_row, "reason": "response_binding_mismatch"})
                continue
            if decision == "rejected" and policy.get("block_on_rejected", True):
                conflicts.append({**base_row, "reason": "rejected_response_present"})
            if decision == "needs_changes" and policy.get("block_on_needs_changes", True):
                conflicts.append({**base_row, "reason": "needs_changes_response_present"})
            if policy.get("block_on_critical_finding", True):
                findings = _as_list(response.get("findings"))
                if any(str(row.get("severity") or "").lower() == "critical" for row in findings if isinstance(row, dict)):
                    conflicts.append({**base_row, "reason": "critical_finding_present"})
        return conflicts

    def _accepted_index_document(self, program_id: str, participants: list[DomainDocument]) -> DomainDocument:
        handoff_id = self._handoff_id(program_id, {})
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_accepted_evidence_index",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "items": [
                    {
                        "evidence_id": row.get("accepted_evidence_id"),
                        "response_id": row.get("response_id"),
                        "role": row.get("role"),
                        "organization": row.get("organization"),
                        "decision": row.get("decision"),
                        "accepted_evidence_zip_sha256": row.get("accepted_evidence_zip_sha256"),
                        "accepted_evidence_verification_hash": row.get("accepted_evidence_verification_hash"),
                    }
                    for row in participants
                ],
                "summary": {"accepted_count": len(participants)},
            }
        )

    def _accepted_verification_summary(self, external_manifest: DomainDocument) -> DomainDocument:
        rows = [row for row in external_manifest.get("items", []) if row.get("evidence_type") == "program_accepted_evidence"]
        summaries = []
        for row in rows:
            report_path = Path(str(row.get("accepted_evidence_verification_report") or row.get("verification_report_path") or ""))
            if report_path.exists():
                report = read_json(report_path)
                summaries.append({"evidence_id": row.get("evidence_id"), "status": report.get("status"), "verification_hash": _integrity_hash(report), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")})
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_accepted_evidence_verification_summaries", "summaries": summaries, "summary": {"accepted_count": len(summaries)}})

    def _signoff_binding(self, signoff: DomainDocument, event: DomainDocument, docs: DomainDocument) -> DomainDocument:
        binding = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_signoff_binding_summary",
                "program_id": signoff.get("program_id"),
                "handoff_id": signoff.get("handoff_id"),
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "latest_history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "handoff_report_hash": docs["report"].get("integrity_hash"),
                "decision_board_hash": docs["decision"].get("integrity_hash"),
                "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                "source_hash": docs["report"].get("source_hash"),
            }
        )
        return binding

    def _append_history(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _handoff_id(self, program_id: str, payload: DomainDocument) -> str:
        if payload.get("handoff_id"):
            return _safe_id(str(payload["handoff_id"]))
        if self.report_path(program_id).exists():
            return _safe_id(str(read_json(self.report_path(program_id)).get("handoff_id") or "uph-000001"))
        return "uph-000001"

    def _next_review_pack_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "review-packs"
        base.mkdir(parents=True, exist_ok=True)
        return f"urprp-{len(list(base.glob('urprp-*'))) + 1:06d}"

    def _next_response_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "responses"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpresp-{len(list(base.glob('urpresp-*'))) + 1:06d}"

    def _next_evidence_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "accepted-evidence"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpae-{len(list(base.glob('urpae-*'))) + 1:06d}"

    def _build_zip(self, export_dir: Path, zip_path: Path, label: str) -> DomainDocument:
        if not (export_dir / "manifest.json").exists():
            raise UnifiedReleaseProgramHandoffStateError(f"{label} export manifest is missing.")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        if zip_path.exists():
            zip_path.unlink()
        ArchiveBuilder.build_directory_zip(export_dir, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            entries = sorted(info.filename for info in archive.infolist())
        manifest = read_json(export_dir / "manifest.json")
        manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
        manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(export_dir / "manifest.json", manifest)
        zip_path.unlink(missing_ok=True)
        ArchiveBuilder.build_directory_zip(export_dir, zip_path)
        return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}
