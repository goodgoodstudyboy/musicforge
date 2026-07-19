# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.attestation_store_ports import AttestationPortalStorePort as AttestationPortalStorePort
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_contracts import portal_summary as portal_summary, portal_verification_summary as portal_verification_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal, write_release_portfolio_governance_attestation_portal_verification_report as write_release_portfolio_governance_attestation_portal_verification_report
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review_contracts import PORTAL_REVIEW_BLOCKED_KEYS as PORTAL_REVIEW_BLOCKED_KEYS, PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS as PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS, PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS as PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS, PORTAL_REVIEW_PACK_PACKAGE_TYPE as PORTAL_REVIEW_PACK_PACKAGE_TYPE, PORTAL_REVIEW_RESPONSE_HASH_FIELDS as PORTAL_REVIEW_RESPONSE_HASH_FIELDS, PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE as PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE, response_integrity_hash as response_integrity_hash, response_payload_hash as response_payload_hash, response_summary as response_summary, review_manifest_hash as review_manifest_hash, review_pack_hash as review_pack_hash, review_pack_summary as review_pack_summary, verification_hash as verification_hash

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

ReleasePortfolioGovernanceAttestationPortalReviewStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationPortalReviewStateError')
ch = _make_deferred_global('ch')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationPortalReviewStateError, ch
    ReleasePortfolioGovernanceAttestationPortalReviewStateError = namespace.get('ReleasePortfolioGovernanceAttestationPortalReviewStateError', ReleasePortfolioGovernanceAttestationPortalReviewStateError)
    ch = namespace.get('ch', ch)
    _bind_deferred_defaults(namespace)


PORTAL_REVIEW_SCHEMA_VERSION = 1




def review_pack_integrity_ok(pack: DomainDocument) -> bool:
    return bool(pack) and str(pack.get("integrity_hash") or "") == review_pack_hash(pack)

def _response_status(response: DomainDocument, pack: DomainDocument) -> str:
    if response.get("review_pack_source_hash") and pack.get("source_hash") and response.get("review_pack_source_hash") != pack.get("source_hash"):
        return "stale"
    decision = response.get("decision")
    if decision not in {"accepted", "needs_changes", "rejected"}:
        return "failed"
    if decision == "accepted" and _has_unresolved_high_findings(response):
        return "failed"
    return "accepted" if decision == "accepted" else "action_required"

def _has_unresolved_high_findings(response: DomainDocument) -> bool:
    for finding in response.get("findings", []) if isinstance(response.get("findings"), list) else []:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").lower()
        status = str(finding.get("status") or "open").lower()
        if severity in {"high", "critical"} and status not in {"resolved", "accepted_risk"}:
            return True
    return False

def _response_from_bytes(data: bytes) -> DomainDocument:
    if data.startswith(b"PK"):
        import io

        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            return json.loads(archive.read("review-response.json").decode("utf-8"))
    return json.loads(data.decode("utf-8"))

def _pack_id(portfolio_id: str, profile: str, source: DomainDocument) -> str:
    digest = stable_hash({"portfolio_id": portfolio_id, "profile": profile, "source": source})[:12]
    return f"aprp-{digest}"

def _pack_summary(source: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    return {
        "status": "failed" if blockers else "warning" if warnings else "ready",
        "portfolio_id": source.get("portfolio_id"),
        "current_entry_id": source.get("registry_current_entry_id"),
        "current_certificate_id": source.get("current_certificate_id"),
        "portal_verification_status": source.get("portal_verification_status"),
        "registry_verification_status": source.get("registry_verification_status"),
        "attestation_verification_status": source.get("current_attestation_verification_status"),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }

def _pack_data_documents(pack: DomainDocument) -> dict[str, DomainDocument]:
    source = _as_document(pack.get("source"))
    return {
        "portal-summary.json": {"source_hash": pack.get("source_hash"), "summary": pack.get("summary"), "portal": _portal_binding(source)},
        "registry-verification-summary.json": {"source_hash": pack.get("source_hash"), "status": source.get("registry_verification_status"), "zip_sha256": source.get("registry_zip_sha256"), "manifest_hash": source.get("registry_manifest_hash"), "verification_hash": source.get("registry_verification_hash"), "current_entry_id": source.get("registry_current_entry_id"), "current_entry_hash": source.get("registry_current_entry_hash")},
        "attestation-verification-summary.json": {"source_hash": pack.get("source_hash"), "status": source.get("current_attestation_verification_status"), "zip_sha256": source.get("current_attestation_zip_sha256"), "manifest_hash": source.get("current_attestation_manifest_hash"), "verification_hash": source.get("current_attestation_verification_hash"), "certificate_id": source.get("current_certificate_id"), "evidence_vault_zip_sha256": source.get("evidence_vault_zip_sha256"), "final_board_signoff_hash": source.get("final_board_signoff_hash")},
        "portal-verification-summary.json": {"source_hash": pack.get("source_hash"), "status": source.get("portal_verification_status"), "zip_sha256": source.get("portal_zip_sha256"), "zip_size_bytes": source.get("portal_zip_size_bytes"), "manifest_hash": source.get("portal_manifest_hash"), "verification_hash": source.get("portal_verification_hash"), "portal_source_hash": source.get("portal_source_hash")},
        "response-schema.json": _response_schema(pack),
    }

def _response_schema(pack: DomainDocument) -> DomainDocument:
    return {
        "source_hash": pack.get("source_hash"),
        "package_type": PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE,
        "required_fields": ["reviewer", "decision", "reviewed_at", "rating", "notes"],
        "allowed_decisions": ["accepted", "needs_changes", "rejected"],
        "review_pack_id": pack.get("review_pack_id"),
        "review_pack_source_hash": pack.get("source_hash"),
    }

def _response_form(pack: DomainDocument) -> DomainDocument:
    return {
        "schema_version": PORTAL_REVIEW_SCHEMA_VERSION,
        "package_type": PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE,
        "review_pack_id": pack.get("review_pack_id"),
        "review_pack_source_hash": pack.get("source_hash"),
        "decision": "accepted",
        "reviewer": {"name": "", "organization": ""},
        "reviewed_at": "",
        "rating": None,
        "notes": "",
        "findings": [],
        "attachment_summaries": [],
    }

def _portal_binding(source: DomainDocument) -> DomainDocument:
    return {
        "portal_zip_sha256": source.get("portal_zip_sha256"),
        "portal_zip_size_bytes": source.get("portal_zip_size_bytes"),
        "portal_manifest_hash": source.get("portal_manifest_hash"),
        "portal_verification_hash": source.get("portal_verification_hash"),
        "portal_verification_status": source.get("portal_verification_status"),
        "portal_source_hash": source.get("portal_source_hash"),
        "registry_zip_sha256": source.get("registry_zip_sha256"),
        "registry_manifest_hash": source.get("registry_manifest_hash"),
        "registry_verification_hash": source.get("registry_verification_hash"),
        "current_attestation_zip_sha256": source.get("current_attestation_zip_sha256"),
        "current_attestation_manifest_hash": source.get("current_attestation_manifest_hash"),
        "current_attestation_verification_hash": source.get("current_attestation_verification_hash"),
        "evidence_vault_zip_sha256": source.get("evidence_vault_zip_sha256"),
        "final_board_signoff_hash": source.get("final_board_signoff_hash"),
    }

def _reviewer_guide(pack: DomainDocument) -> str:
    summary = _as_document(pack.get("summary"))
    return "\n".join(
        [
            "# MusicForge Portal Review Pack",
            "",
            f"Portfolio: {pack.get('portfolio_id')}",
            f"Review Pack: {pack.get('review_pack_id')}",
            f"Current Certificate: {summary.get('current_certificate_id') or 'missing'}",
            "",
            "Review the linked Public Attestation Portal evidence offline, then fill portal-review-form.json.",
            "Use accepted only when there are no unresolved high or critical findings.",
            "",
        ]
    )

def _response_form_markdown(pack: DomainDocument) -> str:
    return "\n".join(
        [
            "# Portal Review Response Form",
            "",
            f"review_pack_id: {pack.get('review_pack_id')}",
            f"review_pack_source_hash: {pack.get('source_hash')}",
            "decision: accepted | needs_changes | rejected",
            "rating: 1-5",
            "notes: ",
            "",
        ]
    )

def _pack_readme(pack: DomainDocument) -> str:
    return "\n".join(
        [
            "MusicForge Public Attestation Portal Review Pack",
            "",
            f"Portfolio ID: {pack.get('portfolio_id')}",
            f"Review Pack ID: {pack.get('review_pack_id')}",
            "This package is offline evidence for external review. It does not publish or upload anything.",
            "Run verify-release-portfolio-governance-attestation-portal-review-pack before using it.",
            "",
        ]
    )

def _response_markdown(response: DomainDocument) -> str:
    reviewer = _as_document(response.get("reviewer"))
    return "\n".join(
        [
            "# Portal Review Response",
            "",
            f"response_id: {response.get('response_id')}",
            f"decision: {response.get('decision')}",
            f"reviewer: {reviewer.get('name') or 'unknown'}",
            f"reviewed_at: {response.get('reviewed_at') or 'missing'}",
            "",
            str(response.get("notes") or ""),
            "",
        ]
    )

def redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _state_tuple(pack: DomainDocument) -> dict[str, str]:
    source = _as_document(pack.get("source"))
    return {"source_hash": str(pack.get("source_hash") or ""), "portal_zip_sha256": str(source.get("portal_zip_sha256") or ""), "portal_verification_hash": str(source.get("portal_verification_hash") or "")}

def _file_record(root: Path, path: Path) -> DomainDocument:
    data = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS))

def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Resolved path escapes Portal Review directory.") from exc

def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(profile or "public_summary"))[:80]

def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or ""))[:80]
