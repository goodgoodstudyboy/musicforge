# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import base64 as base64
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore as UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore as UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import BASE_REQUIRED_ENTRIES as BASE_REQUIRED_ENTRIES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION, verify_unified_command_center_release_train_handoff_package as verify_unified_command_center_release_train_handoff_package, write_unified_command_center_release_train_handoff_verification_report as write_unified_command_center_release_train_handoff_verification_report
from song_agent.domains.program.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore as UnifiedCommandCenterReleaseTrainLifecycleStore
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package
from song_agent.domains.program.v142_uccrth_readiness import UnifiedCommandCenterReleaseTrainHandoffStoreReadinessMixin
from song_agent.domains.program import v142_uccrth_readiness as _v142_uccrth_readiness
from song_agent.domains.program.v142_uccrth_evidence import UnifiedCommandCenterReleaseTrainHandoffStoreEvidenceMixin
from song_agent.domains.program import v142_uccrth_evidence as _v142_uccrth_evidence



class UnifiedCommandCenterReleaseTrainHandoffError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainHandoffNotFoundError(UnifiedCommandCenterReleaseTrainHandoffError):
    pass


class UnifiedCommandCenterReleaseTrainHandoffStateError(UnifiedCommandCenterReleaseTrainHandoffError):
    pass


DEFAULT_POLICY = {
    "require_current_train": True,
    "require_change_control_if_resets": True,
    "require_lifecycle_audit": True,
    "require_ga_readiness": False,
    "require_release_check": False,
    "require_external_acceptance": False,
    "quorum": {"min_accepted": 1, "min_organizations": 1, "required_roles": ["release_owner"]},
}


class UnifiedCommandCenterReleaseTrainHandoffStore(UnifiedCommandCenterReleaseTrainHandoffStoreReadinessMixin, UnifiedCommandCenterReleaseTrainHandoffStoreEvidenceMixin):
    def __init__(
        self,
        train_store: UnifiedCommandCenterReleaseTrainStore | None = None,
        change_control_store: UnifiedCommandCenterReleaseTrainChangeControlStore | None = None,
        lifecycle_store: UnifiedCommandCenterReleaseTrainLifecycleStore | None = None,
    ) -> None:
        self.train_store = train_store or UnifiedCommandCenterReleaseTrainStore()
        self.change_control_store = change_control_store or UnifiedCommandCenterReleaseTrainChangeControlStore(self.train_store)
        self.lifecycle_store = lifecycle_store or UnifiedCommandCenterReleaseTrainLifecycleStore(self.train_store, self.change_control_store)
        self.lock = threading.RLock()



















































def _source_inputs(payload: ImplementationDocument) -> ImplementationDocument:
    keys = ["external_evidence_manifest", "train_archive", "train_verification_report", "train_signoff_binding", "change_control_zip", "change_control_verification_report", "lifecycle_zip", "lifecycle_verification_report"]
    doc: ImplementationDocument = {key: str(payload[key]) for key in keys if payload.get(key)}
    if payload.get("train_archive_verification_report") and not doc.get("train_verification_report"):
        doc["train_verification_report"] = str(payload["train_archive_verification_report"])
    proofs = payload.get("reset_proofs") or payload.get("reset_proof_paths") or payload.get("reset_proof") or []
    if isinstance(proofs, (str, Path)):
        proofs = [proofs]
    if proofs:
        doc["reset_proofs"] = [str(item) for item in proofs]
    return doc


def _merge_inputs(saved: ImplementationDocument, incoming: ImplementationDocument) -> ImplementationDocument:
    merged = dict(saved or {})
    for key, value in (incoming or {}).items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def _reset_proof_paths(inputs: ImplementationDocument) -> list[Path]:
    values = inputs.get("reset_proofs") or []
    if isinstance(values, (str, Path)):
        values = [values]
    return [Path(value) for value in values if str(value)]


def _policy(value: Any) -> ImplementationDocument:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "quorum" and isinstance(item, dict):
                policy["quorum"].update(item)
            else:
                policy[key] = item
    return policy


def _inventory_doc(train_id: str, handoff_id: str, source_hash: str, *summaries: ImplementationDocument) -> ImplementationDocument:
    rows = []
    for summary in summaries:
        rows.append({key: value for key, value in summary.items() if key not in {"runtime", "external_report"}})
    failed = len([row for row in rows if row.get("status") == "failed"])
    missing = len([row for row in rows if row.get("status") == "missing"])
    passed = len([row for row in rows if row.get("status") == "passed"])
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_evidence_inventory", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "items": rows, "summary": {"total": len(rows), "passed": passed, "failed": failed, "missing": missing, "stale": 0}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_doc(train_id: str, handoff_id: str, source_hash: str, policy: ImplementationDocument, inventory: ImplementationDocument, accepted: ImplementationDocument) -> ImplementationDocument:
    rows = []
    for row in inventory.get("items", []):
        status = "passed" if row.get("status") in {"passed", "not_required"} else "failed"
        rows.append({"check_id": f"{row.get('evidence_type')}_verified", "status": status, "severity": "critical", "evidence_refs": [row.get("evidence_type")]})
    quorum = policy.get("quorum", {})
    accepted_items = [row for row in accepted.get("items", []) if isinstance(row, dict) and row.get("status") == "passed"]
    roles = {str(row.get("reviewer_role")) for row in accepted_items}
    orgs = {str(row.get("organization")) for row in accepted_items if row.get("organization")}
    required_roles = set(str(role) for role in quorum.get("required_roles", []))
    acceptance_required = bool(policy.get("require_external_acceptance"))
    acceptance_passed = len(accepted_items) >= int(quorum.get("min_accepted", 1)) and len(orgs) >= int(quorum.get("min_organizations", 1)) and required_roles.issubset(roles)
    rows.append({"check_id": "handoff_acceptance_quorum", "status": "passed" if acceptance_passed or not acceptance_required else "failed", "severity": "high" if not acceptance_required else "critical", "evidence_refs": ["accepted_evidence"]})
    critical_failed = len([row for row in rows if row.get("status") == "failed" and row.get("severity") == "critical"])
    manual_required = len([row for row in rows if row.get("status") == "manual_required"])
    overall = "blocked" if critical_failed else "manual_required" if manual_required else "ready"
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_readiness_matrix", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "rows": rows, "summary": {"status": overall, "critical_failed": critical_failed, "manual_required": manual_required, "acceptance_status": "passed" if acceptance_passed else "not_required" if not acceptance_required else "failed"}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _gap_plan_doc(train_id: str, handoff_id: str, source_hash: str, readiness: ImplementationDocument) -> ImplementationDocument:
    actions = []
    for row in readiness.get("rows", []):
        if row.get("status") != "passed":
            actions.append({"check_id": row.get("check_id"), "action": "resolve_or_collect_evidence", "status": "manual_required"})
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_gap_plan", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "items": actions, "summary": {"open_count": len(actions)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _public_external_manifest(train_id: str, handoff_id: str, inputs: ImplementationDocument, train: ImplementationDocument, change: ImplementationDocument, lifecycle: ImplementationDocument) -> ImplementationDocument:
    rows = []
    for item_id, evidence_type, summary in (
        ("train-current", "release_train_archive", train),
        ("change-control-current", "release_train_change_control", change),
        ("lifecycle-current", "release_train_lifecycle_audit", lifecycle),
    ):
        rows.append({"item_id": item_id, "evidence_type": evidence_type, "component_id": train_id, "status": summary.get("status"), "zip_sha256": summary.get("zip_sha256"), "zip_size_bytes": summary.get("zip_size_bytes"), "manifest_hash": summary.get("manifest_hash"), "verification_report_hash": summary.get("verification_report_hash")})
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_external_evidence_manifest", "handoff_id": handoff_id, "train_id": train_id, "items": rows}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _file_index(train_id: str, handoff_id: str, files: list[ImplementationDocument]) -> ImplementationDocument:
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_file_index", "handoff_id": handoff_id, "train_id": train_id, "files": sorted(files, key=lambda row: row.get("path", ""))}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(train_id: str, handoff_id: str, docs: ImplementationDocument, files: list[ImplementationDocument], file_index: ImplementationDocument) -> ImplementationDocument:
    source = {
        "file_index_hash": file_index.get("integrity_hash"),
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "response_summary_hash": docs["response_summary"].get("integrity_hash"),
        "accepted_evidence_summary_hash": docs["accepted_summary"].get("integrity_hash"),
        "handoff_signoff_hash": docs.get("signoff", {}).get("integrity_hash"),
        "handoff_signoff_binding_hash": docs.get("signoff_binding", {}).get("integrity_hash"),
    }
    doc = {"schema_version": 1, "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE, "handoff_id": handoff_id, "train_id": train_id, "source_hash": docs["report"].get("source_hash"), "source": source, "summary": docs["report"].get("summary", {}), "files": sorted(files, key=lambda row: row.get("path", ""))}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _signoff_binding_summary(train_id: str, handoff_id: str, signoff: ImplementationDocument, event: ImplementationDocument, docs: ImplementationDocument) -> ImplementationDocument:
    source = docs["report"].get("source", {})
    doc = {
        "schema_version": 1,
        "package_type": "musicforge_release_train_handoff_signoff_binding_summary",
        "handoff_id": handoff_id,
        "train_id": train_id,
        "signed_by": signoff.get("signed_by"),
        "role": signoff.get("role"),
        "reason": signoff.get("reason"),
        "signed_at": signoff.get("signed_at"),
        "signoff_hash": signoff.get("integrity_hash"),
        "latest_history_event_hash": event.get("event_hash"),
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "current_train_archive_sha256": source.get("current_train_zip_sha256"),
        "lifecycle_audit_zip_sha256": source.get("lifecycle_zip_sha256"),
        "accepted_evidence_summary_hash": docs["accepted_summary"].get("integrity_hash"),
        "accepted_evidence_hashes": [row.get("accepted_evidence_hash") for row in docs["accepted_summary"].get("items", [])],
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _response_from_payload(payload: ImplementationDocument) -> ImplementationDocument:
    if payload.get("response_json_base64"):
        raw = base64.b64decode(str(payload["response_json_base64"]))
        return json.loads(raw.decode("utf-8"))
    if isinstance(payload.get("response"), dict):
        return dict(payload["response"])
    return dict(payload)


def _response_public_summary(response: ImplementationDocument) -> ImplementationDocument:
    reviewer = _as_document(response.get("reviewer"))
    return sanitize_metadata({"reviewer_id": reviewer.get("reviewer_id"), "reviewer_name": reviewer.get("name"), "organization": reviewer.get("organization"), "reviewer_role": reviewer.get("role"), "decision": response.get("decision"), "reviewed_at": response.get("reviewed_at")})


def _response_binding_summary(response: ImplementationDocument, verification: ImplementationDocument) -> ImplementationDocument:
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_response_binding_summary", "response_id": response.get("response_id"), "handoff_id": response.get("handoff_id"), "train_id": response.get("train_id"), "raw_response_sha256": response.get("integrity_hash"), "payload_hash": response.get("payload_hash"), "verification_report_hash": verification.get("integrity_hash"), "handoff_zip_sha256": response.get("handoff_zip_sha256"), "handoff_manifest_hash": response.get("handoff_manifest_hash"), "handoff_source_hash": response.get("handoff_source_hash")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


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


def _assert_signed_docs_current(docs: ImplementationDocument) -> None:
    signoff = docs.get("signoff") or {}
    if signoff.get("handoff_report_hash") != docs["report"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff report hash does not match signoff.")
    if signoff.get("readiness_matrix_hash") != docs["readiness"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff readiness hash does not match signoff.")
    if signoff.get("evidence_inventory_hash") != docs["inventory"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff inventory hash does not match signoff.")
    if signoff.get("accepted_evidence_summary_hash") != docs["accepted_summary"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff accepted evidence hash does not match signoff.")


def _latest_signoff_event(history: list[ImplementationDocument]) -> ImplementationDocument:
    events = [row for row in history if row.get("event_type") == "release_train_handoff_signoff_created"]
    return events[-1] if events else {}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(message), **extra}


def _read_optional_json(path: Path) -> ImplementationDocument:
    return read_json(path) if path.exists() else {}


def _recipient_guide(docs: ImplementationDocument) -> str:
    return "# MusicForge Release Train Final Handoff\n\nReview the handoff report, readiness matrix, and evidence inventory. Use the verifier with external Train, Change Control, and Lifecycle evidence for current validation.\n"


def _history_text(history: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history)


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _zip_manifest_hash(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    return str(manifest.get("integrity_hash") or "")


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": "blocking", "message": message, "details": details or {}}


def _safe_id(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())[:120].strip("-")
    return cleaned or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

_v142_uccrth_readiness.bind_globals(globals())
_v142_uccrth_evidence.bind_globals(globals())
