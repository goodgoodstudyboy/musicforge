# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_distribution_kit import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, PublicTrustCenterDistributionKitAcceptanceError as PublicTrustCenterDistributionKitAcceptanceError, PublicTrustCenterDistributionKitAcceptanceStore as PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_summary as accepted_evidence_summary, verification_hash as verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report as write_public_trust_center_distribution_kit_accepted_evidence_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE as ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_PACKAGE_TYPE as ACCEPTANCE_BOARD_PACKAGE_TYPE, ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE, SIGNOFF_ARCHIVE_ENTRIES as SIGNOFF_ARCHIVE_ENTRIES, acceptance_board_conflict_hash as acceptance_board_conflict_hash, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_policy_hash as acceptance_board_policy_hash, acceptance_board_report_hash as acceptance_board_report_hash, acceptance_board_signoff_archive_hash as acceptance_board_signoff_archive_hash, acceptance_board_signoff_hash as acceptance_board_signoff_hash, acceptance_board_verification_hash as acceptance_board_verification_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.v142_ptcab_readiness import PublicTrustCenterAcceptanceBoardStoreReadinessMixin
from song_agent.domains.trust import v142_ptcab_readiness as _v142_ptcab_readiness
from song_agent.domains.trust.v142_ptcab_evidence import PublicTrustCenterAcceptanceBoardStoreEvidenceMixin
from song_agent.domains.trust import v142_ptcab_evidence as _v142_ptcab_evidence
from song_agent.domains.trust.v142_ptcab_lifecycle import PublicTrustCenterAcceptanceBoardStoreLifecycleMixin
from song_agent.domains.trust import v142_ptcab_lifecycle as _v142_ptcab_lifecycle



ACCEPTANCE_BOARD_SCHEMA_VERSION = 1



ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"

ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_change_request"






ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}



DEFAULT_POLICY_ID = "ptcab-policy-default"



class PublicTrustCenterAcceptanceBoardError(ValueError):
    pass


class PublicTrustCenterAcceptanceBoardNotFoundError(PublicTrustCenterAcceptanceBoardError):
    pass


class PublicTrustCenterAcceptanceBoardStateError(PublicTrustCenterAcceptanceBoardError):
    pass


class PublicTrustCenterAcceptanceBoardStore(PublicTrustCenterAcceptanceBoardStoreReadinessMixin, PublicTrustCenterAcceptanceBoardStoreEvidenceMixin, PublicTrustCenterAcceptanceBoardStoreLifecycleMixin):
    def __init__(self, *, acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore) -> None:
        self.acceptance_store = acceptance_store
        self.distribution_kit_store = acceptance_store.distribution_kit_store
        self.lock = threading.RLock()







































































def acceptance_board_change_request_hash(change_request: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (change_request or {}).items() if key not in ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS})











def redaction_summary(value: Any) -> DomainDocument:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _default_policy(center_id: str, now: str) -> ImplementationDocument:
    policy = {
        "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
        "package_type": ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE,
        "policy_id": DEFAULT_POLICY_ID,
        "center_id": center_id,
        "created_at": now,
        "updated_at": now,
        "status": "active",
        "requirements": _normalize_requirements({}),
        "role_rules": [],
    }
    policy["integrity_hash"] = acceptance_board_policy_hash(policy)
    return policy


def _normalize_requirements(payload: ImplementationDocument) -> ImplementationDocument:
    payload = _as_document(payload)
    roles = []
    for role in payload.get("required_roles", []) if isinstance(payload.get("required_roles"), list) else []:
        safe = _safe_id(str(role or "")).lower()
        if safe and safe not in roles:
            roles.append(safe)
    return {
        "min_accepted_count": max(1, min(50, int(payload.get("min_accepted_count") or 1))),
        "min_accepted_organizations": max(0, min(50, int(payload.get("min_accepted_organizations") or 1))),
        "required_roles": roles,
        "allow_needs_changes": bool(payload.get("allow_needs_changes", False)),
        "allow_rejected": bool(payload.get("allow_rejected", False)),
        "block_on_critical_findings": bool(payload.get("block_on_critical_findings", True)),
        "require_current_distribution_kit": bool(payload.get("require_current_distribution_kit", True)),
        "require_current_accepted_evidence": bool(payload.get("require_current_accepted_evidence", True)),
    }


def _role_rules(requirements: ImplementationDocument) -> list[ImplementationDocument]:
    return [{"role": role, "min_accepted_count": 1} for role in requirements.get("required_roles", []) if role]


def _distribution_kit_state(distribution_kit_store: Any, center_id: str) -> ImplementationDocument:
    zip_path = distribution_kit_store.zip_path(center_id)
    report = distribution_kit_store.read_report(center_id, default={})
    verification = _read_json_default(distribution_kit_store.verification_report_path(center_id), default={})
    manifest = _read_zip_json(zip_path, "distribution-kit-manifest.json")
    return _sanitize(
        {
            "zip_sha256": _sha256(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "manifest_hash": manifest.get("integrity_hash"),
            "report_hash": report.get("integrity_hash"),
            "source_hash": report.get("source_hash"),
            "verification_report_hash": verification_hash(verification),
            "verification_status": verification.get("status"),
        }
    )


def _public_response_from_record(response: ImplementationDocument) -> ImplementationDocument:
    payload = _as_document(response.get("response_payload"))
    reviewer = _as_document(payload.get("reviewer"))
    findings = []
    for item in payload.get("findings", []) if isinstance(payload.get("findings"), list) else []:
        if isinstance(item, dict):
            findings.append({"severity": item.get("severity"), "code": item.get("code"), "public_message": sanitize_sensitive_text(str(item.get("public_message") or item.get("message") or ""))[:500]})
    return _sanitize({"response_id": payload.get("response_id"), "result": payload.get("result"), "review_mode": payload.get("review_mode"), "reviewed_at": payload.get("reviewed_at"), "reviewer": {"name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")}, "verification_status": (_as_document(payload.get("verification"))).get("status"), "comments_excerpt": sanitize_sensitive_text(str(payload.get("comments") or ""))[:500], "findings": findings})


def _critical_findings(response: ImplementationDocument) -> list[ImplementationDocument]:
    payload = _as_document(response.get("response_payload"))
    return [item for item in payload.get("findings", []) if isinstance(item, dict) and str(item.get("severity") or "").lower() == "critical"]


def _participant_warnings(response: ImplementationDocument, response_stale: bool, evidence_id: str, evidence_current: bool, evidence_verification_status: str) -> list[str]:
    warnings: list[str] = []
    if response_stale:
        warnings.append("response_stale")
    if response.get("verification_status") != "passed":
        warnings.append("response_verification_not_passed")
    if response.get("review_mode") != "external_manual":
        warnings.append("review_mode_not_external_manual")
    if not evidence_id:
        warnings.append("accepted_evidence_missing")
    elif not evidence_current:
        warnings.append("accepted_evidence_stale")
    if evidence_id and evidence_verification_status != "passed":
        warnings.append("accepted_evidence_verification_not_passed")
    return warnings


def _evaluate_board(policy: ImplementationDocument, participants: list[ImplementationDocument]) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
    requirements = _as_document(policy.get("requirements"))
    counted = [item for item in participants if item.get("counts_for_quorum")]
    organizations = {str(item.get("organization") or "").strip().lower() for item in counted if str(item.get("organization") or "").strip()}
    roles = {str(item.get("role") or "").strip().lower() for item in counted if str(item.get("role") or "").strip()}
    needs_changes = [item for item in participants if item.get("current") and item.get("result") == "needs_changes"]
    rejected = [item for item in participants if item.get("current") and item.get("result") == "rejected"]
    critical = [item for item in participants if item.get("current") and item.get("critical_findings")]
    stale = [item for item in participants if item.get("warnings")]
    required_roles = [str(role).lower() for role in requirements.get("required_roles", [])]
    missing_roles = [role for role in required_roles if role not in roles]
    checks = [
        _check("ptcab_quorum", len(counted) >= int(requirements.get("min_accepted_count") or 1), f"Accepted quorum {len(counted)}/{requirements.get('min_accepted_count')}."),
        _check("ptcab_organization_quorum", len(organizations) >= int(requirements.get("min_accepted_organizations") or 0), f"Accepted organization quorum {len(organizations)}/{requirements.get('min_accepted_organizations')}."),
        _check("ptcab_required_roles", not missing_roles, "Required roles satisfied." if not missing_roles else "Missing required roles: " + ", ".join(missing_roles)),
        _check("ptcab_needs_changes_allowed", bool(requirements.get("allow_needs_changes", False)) or not needs_changes, "Needs changes responses are allowed or absent."),
        _check("ptcab_rejected_allowed", bool(requirements.get("allow_rejected", False)) or not rejected, "Rejected responses are allowed or absent."),
        _check("ptcab_no_critical_findings", not bool(requirements.get("block_on_critical_findings", True)) or not critical, "No blocking critical findings."),
        _check("ptcab_no_stale_participants", not stale, "No stale or incomplete participants."),
    ]
    conflicts: list[ImplementationDocument] = []
    if missing_roles:
        conflicts.append(_conflict("missing_required_role", "blocking", [], "Missing required roles: " + ", ".join(missing_roles)))
    if needs_changes and not bool(requirements.get("allow_needs_changes", False)):
        conflicts.append(_conflict("accepted_and_needs_changes", "blocking", [str(item.get("response_id") or "") for item in needs_changes], "At least one current needs_changes response exists."))
    if rejected and not bool(requirements.get("allow_rejected", False)):
        conflicts.append(_conflict("accepted_and_rejected", "blocking", [str(item.get("response_id") or "") for item in rejected], "At least one current rejected response exists."))
    if critical and bool(requirements.get("block_on_critical_findings", True)):
        conflicts.append(_conflict("critical_finding", "blocking", [str(item.get("response_id") or "") for item in critical], "At least one current critical finding exists."))
    for item in stale:
        for warning in item.get("warnings", []):
            conflicts.append(_conflict(warning if warning in {"response_stale", "accepted_evidence_stale"} else "stale_evidence", "warning", [str(item.get("response_id") or "")], f"Participant has warning: {warning}"))
    for index, item in enumerate(conflicts, start=1):
        item["conflict_id"] = f"ptcabc-{index:06d}"
    return checks, conflicts


def _readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], blockers: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> str:
    if blockers or any(item.get("severity") == "blocking" for item in conflicts):
        if any(item.get("result") == "rejected" and item.get("current") for item in participants) and not bool((policy.get("requirements") or {}).get("allow_rejected", False)):
            return "rejected"
        if any(item.get("result") == "needs_changes" and item.get("current") for item in participants) and not bool((policy.get("requirements") or {}).get("allow_needs_changes", False)):
            return "needs_changes"
        if any("stale" in ",".join(item.get("warnings", [])) for item in participants):
            return "stale"
        if any("accepted_evidence_missing" in item.get("warnings", []) for item in participants):
            return "missing_evidence"
        return "blocked"
    return "ready"


def _board_summary(policy: ImplementationDocument, participants: list[ImplementationDocument], checks: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    counted = [item for item in participants if item.get("counts_for_quorum")]
    organizations = {str(item.get("organization") or "").strip().lower() for item in counted if str(item.get("organization") or "").strip()}
    return {
        "accepted_count": len(counted),
        "accepted_organization_count": len(organizations),
        "needs_changes_count": len([item for item in participants if item.get("current") and item.get("result") == "needs_changes"]),
        "rejected_count": len([item for item in participants if item.get("current") and item.get("result") == "rejected"]),
        "stale_count": len([item for item in participants if item.get("warnings")]),
        "required_roles_status": _check_status(checks, "ptcab_required_roles"),
        "quorum_status": _check_status(checks, "ptcab_quorum"),
        "conflict_status": "failed" if any(item.get("severity") == "blocking" for item in conflicts) else "passed",
        "policy_hash": policy.get("integrity_hash"),
    }


def _response_index(source: ImplementationDocument, rows: list[ImplementationDocument]) -> ImplementationDocument:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _accepted_evidence_index(source: ImplementationDocument, rows: list[ImplementationDocument]) -> ImplementationDocument:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _quorum_evidence(report: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(report.get("summary"))
    policy = _as_document(report.get("policy"))
    participants = _as_list(report.get("participants"))
    counted = [str(item.get("response_id") or "") for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")]
    roles = {str(item.get("role") or "").lower(): "passed" for item in participants if isinstance(item, dict) and item.get("counts_for_quorum") and item.get("role")}
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": report.get("source_hash"), "policy_hash": policy.get("policy_hash"), "decision": {"readiness": report.get("readiness"), "quorum_status": summary.get("quorum_status"), "required_roles_status": summary.get("required_roles_status"), "conflict_status": summary.get("conflict_status")}, "counted_response_ids": counted, "required_roles": roles}


def _check_status(checks: list[ImplementationDocument], check_id: str) -> str:
    for item in checks:
        if item.get("check_id") == check_id:
            return "passed" if item.get("status") == "passed" else "failed"
    return "missing"


def _check(check_id: str, ok: bool, message: str) -> ImplementationDocument:
    return {"scope": "board", "check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message}


def _conflict(conflict_type: str, severity: str, participants: list[str], message: str) -> ImplementationDocument:
    return {"conflict_id": "", "type": conflict_type, "severity": severity, "participants": [item for item in participants if item], "message": message}


def _readme(report: ImplementationDocument) -> str:
    return sanitize_sensitive_text("\n".join(["MusicForge Public Trust Center Acceptance Board", "", f"Center ID: {report.get('center_id')}", f"Readiness: {report.get('readiness')}", f"Status: {report.get('status')}", ""]))


def _verify_text() -> str:
    return "Verify this board package:\npython -m song_agent.cli verify-public-trust-center-acceptance-board-package public-trust-center-acceptance-board.zip --strict --require-ready --json\n"


def _signoff_archive_readme(signoff: ImplementationDocument) -> str:
    return sanitize_sensitive_text(
        "\n".join(
            [
                "MusicForge Public Trust Center Acceptance Board Signoff Archive",
                "",
                f"Center ID: {signoff.get('center_id')}",
                f"Signoff ID: {signoff.get('signoff_id')}",
                f"Status: {signoff.get('status')}",
                "",
            ]
        )
    )


def _signoff_archive_verify_text() -> str:
    return "Verify this signoff archive:\npython -m song_agent.cli verify-public-trust-center-acceptance-board-signoff-archive-package public-trust-center-acceptance-board-signoff-archive.zip --strict --require-signed --json\n"


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return _as_document(value)


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = json.loads(_read_text(path))
    except Exception:
        return dict(default or {})
    return _sanitize(_document_or(value, dict(default or {})))


def _next_change_request_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    max_index = 0
    for path in root.glob("bcr-*.json"):
        stem = path.stem
        try:
            max_index = max(max_index, int(stem.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"bcr-{max_index + 1:06d}"


def _latest_applied_change_request(root: Path, signoff_hash: Any) -> ImplementationDocument | None:
    if not root.exists():
        return None
    rows: list[ImplementationDocument] = []
    for path in sorted(root.glob("*.json")):
        item = _read_json_default(path, default={})
        if item.get("status") == "applied" and item.get("applied_signoff_hash") == signoff_hash:
            rows.append(item)
    if not rows:
        return None
    latest = rows[-1]
    return {
        "change_request_id": latest.get("change_request_id"),
        "status": latest.get("status"),
        "applied_at": latest.get("applied_at"),
        "integrity_hash": latest.get("integrity_hash"),
    }


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, _sanitize(payload))
    return path


def _write_text(path: Path, text: str) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_text(path: Path) -> str:
    with open(_fs_path(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if _is_file(path)]


def _is_file(path: Path) -> bool:
    try:
        return os.path.isfile(_fs_path(path))
    except OSError:
        return False


def _write_zip(zip_path: Path, export_dir: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(export_dir):
                archive.write(_fs_path(resolved), entry)
        os.replace(_fs_path(tmp_path), _fs_path(zip_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _sha256(path: Path) -> str | None:
    try:
        if not os.path.isfile(_fs_path(path)):
            return None
    except OSError:
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterAcceptanceBoardStateError("Resolved path escapes Acceptance Board root.")


def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"


def _redaction_findings(scope: str, text: str) -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
    sanitized = sanitize_sensitive_text(text)
    if sanitized != text:
        findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    for marker in ("github" + "key", "x-access-" + "token", "api_" + "key", "access_" + "token", "source_" + "path", "local_" + "path", "file_" + "path"):
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)

_v142_ptcab_readiness.bind_globals(globals())
_v142_ptcab_evidence.bind_globals(globals())
_v142_ptcab_lifecycle.bind_globals(globals())
