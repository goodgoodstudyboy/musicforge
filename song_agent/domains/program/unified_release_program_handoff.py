# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list, as_text as _as_text

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

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
from song_agent.domains.program.v142_urph_readiness import UnifiedReleaseProgramHandoffStoreReadinessMixin
from song_agent.domains.program import v142_urph_readiness as _v142_urph_readiness
from song_agent.domains.program.v142_urph_evidence import UnifiedReleaseProgramHandoffStoreEvidenceMixin
from song_agent.domains.program import v142_urph_evidence as _v142_urph_evidence
from song_agent.domains.program.v142_urph_lifecycle import UnifiedReleaseProgramHandoffStoreLifecycleMixin
from song_agent.domains.program import v142_urph_lifecycle as _v142_urph_lifecycle



DEFAULT_BOARD_POLICY = {
    "minimum_acceptances": 1,
    "minimum_organizations": 1,
    "required_roles": ["release_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_finding": True,
}


class UnifiedReleaseProgramHandoffError(ValueError):
    pass


class UnifiedReleaseProgramHandoffNotFoundError(UnifiedReleaseProgramHandoffError):
    pass


class UnifiedReleaseProgramHandoffStateError(UnifiedReleaseProgramHandoffError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramHandoffStateError)


class UnifiedReleaseProgramHandoffStore(UnifiedReleaseProgramHandoffStoreReadinessMixin, UnifiedReleaseProgramHandoffStoreEvidenceMixin, UnifiedReleaseProgramHandoffStoreLifecycleMixin):
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None, *, release_store: ProgramReleaseStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore(release_store=release_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")








































































def write_handoff_external_evidence_manifest(path: Path | str, *, program_id: str, handoff_id: str, items: list[DomainDocument]) -> DomainDocument:
    manifest = _external_manifest_from_rows(program_id, handoff_id, items)
    write_json(Path(path), manifest)
    return manifest


def _external_manifest_from_rows(program_id: str, handoff_id: str, rows: list[ImplementationDocument]) -> ImplementationDocument:
    normalized = []
    for row in rows:
        evidence_type = str(row.get("evidence_type") or "")
        normalized_row = {"evidence_id": _safe_id(str(row.get("evidence_id") or evidence_type or "evidence")), "evidence_type": evidence_type, "component_id": str(row.get("component_id") or row.get("program_id") or program_id)}
        for key, value in row.items():
            if key not in normalized_row and value is not None:
                normalized_row[key] = str(value) if isinstance(value, Path) else value
        normalized.append(normalized_row)
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "handoff_id": handoff_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _public_external_manifest(manifest: ImplementationDocument) -> ImplementationDocument:
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


def _manifest_row(manifest: ImplementationDocument, evidence_type: str) -> ImplementationDocument | None:
    return next((row for row in manifest.get("items", []) if row.get("evidence_type") == evidence_type), None)


def _package_manifest(package_type: str, program_id: str, handoff_id: str, files: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
            "package_type": package_type,
            "program_id": program_id,
            "handoff_id": handoff_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _archive_source(docs: ImplementationDocument) -> ImplementationDocument:
    return {
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "decision_board_hash": docs["decision"].get("integrity_hash"),
        "conflict_report_hash": docs["conflicts"].get("integrity_hash"),
        "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "gap_plan_hash": docs["gap"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "handoff_signoff_hash": docs["signoff"].get("integrity_hash"),
        "handoff_signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "program_verification_summary_hash": docs["program_summary"].get("integrity_hash"),
        "operations_verification_summary_hash": docs["operations_summary"].get("integrity_hash"),
        "accepted_evidence_verification_summary_hash": docs["accepted_summary"].get("integrity_hash"),
    }


def _verification_summary_from_state(kind: str, state: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
            "package_type": f"musicforge_unified_release_program_handoff_{kind}_verification_summary",
            "status": state.get("status"),
            "zip_sha256": state.get("zip_sha256"),
            "zip_size_bytes": state.get("zip_size_bytes"),
            "manifest_hash": state.get("manifest_hash"),
            "verification_hash": state.get("verification_hash"),
            "verification_status": state.get("verification_status"),
            "runtime_status": state.get("runtime_status"),
        }
    )


def _decision_readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    accepted = [row for row in participants if row.get("decision") in {"accepted", "accepted_with_notes"}]
    roles = {row.get("role") for row in accepted}
    orgs = {row.get("organization") for row in accepted}
    required_roles = set(policy.get("required_roles") or [])
    minimum_acceptances = int(policy.get("minimum_acceptances") or 1)
    minimum_orgs = int(policy.get("minimum_organizations") or 1)
    missing_roles = sorted(required_roles - roles)
    blockers = []
    if len(accepted) < minimum_acceptances:
        blockers.append("minimum_acceptances")
    if len(orgs) < minimum_orgs:
        blockers.append("minimum_organizations")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("accepted_evidence_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(orgs), "missing_roles": missing_roles, "blockers": blockers}


def _board_policy(value: Any) -> ImplementationDocument:
    raw = _as_document(value)
    return {
        "minimum_acceptances": _as_int(raw.get("minimum_acceptances") or DEFAULT_BOARD_POLICY["minimum_acceptances"]),
        "minimum_organizations": _as_int(raw.get("minimum_organizations") or DEFAULT_BOARD_POLICY["minimum_organizations"]),
        "required_roles": [_bounded(role, 80) for role in raw.get("required_roles", DEFAULT_BOARD_POLICY["required_roles"])],
        "block_on_rejected": bool(raw.get("block_on_rejected", DEFAULT_BOARD_POLICY["block_on_rejected"])),
        "block_on_needs_changes": bool(raw.get("block_on_needs_changes", DEFAULT_BOARD_POLICY["block_on_needs_changes"])),
        "block_on_critical_finding": bool(raw.get("block_on_critical_finding", DEFAULT_BOARD_POLICY["block_on_critical_finding"])),
    }


def _readiness_rows(readiness: ImplementationDocument) -> list[ImplementationDocument]:
    blockers = set(readiness.get("blockers") or [])
    return [
        {"check_id": "minimum_acceptances", "status": "failed" if "minimum_acceptances" in blockers else "passed"},
        {"check_id": "minimum_organizations", "status": "failed" if "minimum_organizations" in blockers else "passed"},
        {"check_id": "required_roles", "status": "failed" if "required_roles" in blockers else "passed", "missing_roles": readiness.get("missing_roles", [])},
        {"check_id": "accepted_evidence_conflicts", "status": "failed" if "accepted_evidence_conflicts" in blockers else "passed"},
    ]


def _gap_items(readiness: ImplementationDocument) -> list[ImplementationDocument]:
    return [{"gap_id": f"gap-{index + 1:03d}", "source": blocker, "status": "manual_required"} for index, blocker in enumerate(readiness.get("blockers") or [])]


def _response_payload_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"payload_hash", "integrity_hash", "response_id", "status", "imported_at"}})


def _response_public_projection(response: ImplementationDocument) -> ImplementationDocument:
    return {
        "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": "musicforge_unified_release_program_review_response_public_projection",
        "program_id": response.get("program_id"),
        "handoff_id": response.get("handoff_id"),
        "review_pack_id": response.get("review_pack_id"),
        "response_id": response.get("response_id"),
        "reviewer_id": response.get("reviewer_id"),
        "reviewer_name": _bounded(response.get("reviewer_name") or response.get("reviewer_id"), 120),
        "reviewer_role": response.get("reviewer_role"),
        "organization": response.get("organization"),
        "decision": response.get("decision"),
        "notes": _bounded(response.get("notes") or "", 1000),
    }


def _public_handoff_summary(docs: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_public_summary", "program_id": docs["report"].get("program_id"), "handoff_id": docs["report"].get("handoff_id"), "status": docs["report"].get("status"), "summary": docs["report"].get("summary", {})})


def _public_inventory(inventory: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_public_inventory", "items": inventory.get("items", []), "summary": inventory.get("summary", {})})


def _risk_summary(docs: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_risk_summary", "risk_level": docs["report"].get("summary", {}).get("risk_level"), "blockers": docs["report"].get("blockers", [])})


def _recipient_guide(report: ImplementationDocument, inventory: ImplementationDocument) -> str:
    return "\n".join(
        [
            "# MusicForge Unified Release Program Final Handoff",
            "",
            f"Program: {report.get('program_id')}",
            f"Handoff: {report.get('handoff_id')}",
            f"Status: {report.get('status')}",
            f"Ready evidence: {inventory.get('summary', {}).get('ready_count', 0)}",
            "",
        ]
    )


def _source_without_checks(state: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in state.items() if key != "checks"}


def _path_checks(prefix: str, paths: dict[str, Path]) -> list[ImplementationDocument]:
    return [_check(f"{prefix}_{key}_exists", path.exists() and path.is_file(), f"{key} exists.", {"path": str(path)}) for key, path in paths.items()]


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_hash_from_zip(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        return manifest.get("integrity_hash")
    except Exception:
        return None


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

_v142_urph_readiness.bind_globals(globals())
_v142_urph_evidence.bind_globals(globals())
_v142_urph_lifecycle.bind_globals(globals())
