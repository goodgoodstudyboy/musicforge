# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import base64 as base64
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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore as ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency, write_release_portfolio_governance_attestation_transparency_verification_report as write_release_portfolio_governance_attestation_transparency_verification_report
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_contracts import ACK_BLOCKED_KEYS as ACK_BLOCKED_KEYS, ACK_EVIDENCE_HASH_EXCLUDE_KEYS as ACK_EVIDENCE_HASH_EXCLUDE_KEYS, ACK_EVIDENCE_PACKAGE_TYPE as ACK_EVIDENCE_PACKAGE_TYPE, ACK_MANIFEST_HASH_EXCLUDE_KEYS as ACK_MANIFEST_HASH_EXCLUDE_KEYS, ACK_PACK_HASH_EXCLUDE_KEYS as ACK_PACK_HASH_EXCLUDE_KEYS, ACK_PACK_PACKAGE_TYPE as ACK_PACK_PACKAGE_TYPE, ACK_RESPONSE_PACKAGE_TYPE as ACK_RESPONSE_PACKAGE_TYPE, ACK_SCHEMA_VERSION as ACK_SCHEMA_VERSION, ack_evidence_hash as ack_evidence_hash, ack_manifest_hash as ack_manifest_hash, ack_pack_hash as ack_pack_hash, acknowledgement_summary as acknowledgement_summary, response_template as response_template
from song_agent.domains.trust.v142_rpgata_readiness import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreReadinessMixin
from song_agent.domains.trust import v142_rpgata_readiness as _v142_rpgata_readiness
from song_agent.domains.trust.v142_rpgata_evidence import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreEvidenceMixin
from song_agent.domains.trust import v142_rpgata_evidence as _v142_rpgata_evidence










ACK_RESPONSE_HASH_FIELDS = (
    "response_id",
    "review_pack_id",
    "review_pack_source_hash",
    "portfolio_id",
    "profile",
    "transparency_zip_sha256",
    "transparency_manifest_hash",
    "transparency_feed_source_hash",
    "reviewer",
    "review_status",
    "reviewed_notice_ids",
    "reviewed_event_ids",
    "comments",
    "concerns",
    "submitted_at",
)

ACK_ALLOWED_RESPONSE_STATUSES = {"accepted", "needs_changes", "rejected"}


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreReadinessMixin, ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStoreEvidenceMixin):
    def __init__(self, *, transparency_store: ReleasePortfolioGovernanceAttestationTransparencyStore) -> None:
        self.transparency_store = transparency_store
        self.lock = threading.RLock()















































def response_payload_hash(response: DomainDocument) -> str:
    return stable_hash({key: (response or {}).get(key) for key in ACK_RESPONSE_HASH_FIELDS})


def response_record_hash(response: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in {"integrity_hash", "imported_at"}})








def response_summary(response: DomainDocument) -> DomainDocument:
    return {
        "response_id": response.get("response_id"),
        "external_response_id": response.get("external_response_id"),
        "status": response.get("status"),
        "verification_status": response.get("verification_status"),
        "stale": bool(response.get("stale")),
        "imported_at": response.get("imported_at"),
    }





def verify_response_document(response: DomainDocument, pack: DomainDocument, *, now: str | None = None) -> DomainDocument:
    del now
    checks: list[ImplementationDocument] = []
    required = ["review_pack_id", "review_pack_source_hash", "transparency_zip_sha256", "transparency_manifest_hash", "transparency_feed_source_hash"]
    missing = [key for key in required if not response.get(key)]
    checks.append(_check("ack_response_required_source_binding", not missing, "Response source binding fields are present." if not missing else "Missing response source binding: " + ", ".join(missing)))
    status = str(response.get("review_status") or "")
    checks.append(_check("ack_response_status_allowed", status in ACK_ALLOWED_RESPONSE_STATUSES, "Response status is allowed."))
    source = _as_document(pack.get("source"))
    checks.append(_check("ack_response_pack_binding", response.get("review_pack_id") == pack.get("pack_id") and response.get("review_pack_source_hash") == pack.get("source_hash"), "Response binds to the acknowledgement pack."))
    checks.append(
        _check(
            "ack_response_transparency_binding",
            response.get("transparency_zip_sha256") == source.get("transparency_zip_sha256")
            and response.get("transparency_manifest_hash") == source.get("transparency_manifest_hash")
            and response.get("transparency_feed_source_hash") == source.get("transparency_feed_source_hash"),
            "Response binds to current Transparency package.",
        )
    )
    notice_ids = set(str(item) for item in source.get("notice_ids", []) if item)
    event_ids = set(str(item) for item in source.get("event_ids", []) if item)
    reviewed_notices = set(str(item) for item in response.get("reviewed_notice_ids", []) if item) if isinstance(response.get("reviewed_notice_ids"), list) else set()
    reviewed_events = set(str(item) for item in response.get("reviewed_event_ids", []) if item) if isinstance(response.get("reviewed_event_ids"), list) else set()
    checks.append(_check("ack_response_notice_subset", reviewed_notices.issubset(notice_ids), "Reviewed notices belong to pack."))
    checks.append(_check("ack_response_event_subset", reviewed_events.issubset(event_ids), "Reviewed events belong to pack."))
    warning_notices = set(str(item) for item in source.get("warning_notice_ids", []) if item)
    checks.append(_check("ack_response_warning_notices_reviewed", status != "accepted" or warning_notices.issubset(reviewed_notices), "Accepted response reviewed all warning notices."))
    concerns = _as_list(response.get("concerns"))
    checks.append(_check("ack_response_concerns_required", status == "accepted" or bool(concerns), "Needs changes/rejected response includes concerns."))
    expected_hash = response_payload_hash(response)
    checks.append(_check("ack_response_payload_hash", not response.get("response_hash") or response.get("response_hash") == expected_hash, "Response hash matches payload."))
    findings = _redaction_findings("response", json.dumps(response, ensure_ascii=False))
    checks.append({"scope": "response", "check_id": "ack_response_redaction_scan", "status": "failed" if findings else "passed", "severity": "blocking", "message": f"Found {len(findings)} sensitive issue(s)." if findings else "No sensitive values found."})
    blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
    return sanitize_metadata(
        {
            "schema_version": ACK_SCHEMA_VERSION,
            "package_kind": "acknowledgement_response",
            "generated_at": now_iso(),
            "status": "failed" if blockers else "passed",
            "summary": {"review_status": status, "blocker_count": len(blockers)},
            "checks": checks,
            "blockers": blockers,
        },
        blocked_keys=ACK_BLOCKED_KEYS,
    )


def verification_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})


def redaction_summary(value: Any) -> DomainDocument:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _pack_id(portfolio_id: str, profile: str, source: ImplementationDocument) -> str:
    return "att-trans-ack-pack-" + stable_hash({"portfolio_id": portfolio_id, "profile": profile, "source": source})[:12]


def _evidence_id(portfolio_id: str, profile: str, source: ImplementationDocument) -> str:
    return "att-trans-ack-" + stable_hash({"portfolio_id": portfolio_id, "profile": profile, "source": source})[:12]


def _pack_data_documents(pack: ImplementationDocument, feed: ImplementationDocument) -> ImplementationDocument:
    source = _as_document(pack.get("source"))
    events = _as_list(feed.get("events"))
    notices = _as_list(feed.get("notices"))
    return sanitize_metadata(
        {
            "transparency-verification-summary.json": {"source_hash": pack.get("source_hash"), "status": source.get("transparency_verification_status"), "verification_hash": source.get("transparency_verification_hash"), "event_semantics": source.get("transparency_event_semantics_status"), "notice_semantics": source.get("transparency_notice_semantics_status")},
            "transparency-feed-summary.json": {"source_hash": pack.get("source_hash"), "feed_source_hash": source.get("transparency_feed_source_hash"), "event_count": len(events), "notice_count": len(notices)},
            "current-public-state-summary.json": {"source_hash": pack.get("source_hash"), "current_public_state_hash": source.get("current_public_state_hash"), "current_entry_id": source.get("current_entry_id"), "current_certificate_id": source.get("current_certificate_id")},
            "events-summary.json": {"source_hash": pack.get("source_hash"), "events": [{"event_id": item.get("event_id"), "event_type": item.get("event_type"), "severity": item.get("severity")} for item in events if isinstance(item, dict)]},
            "notices-summary.json": {"source_hash": pack.get("source_hash"), "notices": [{"notice_id": item.get("notice_id"), "notice_type": item.get("notice_type"), "severity": item.get("severity")} for item in notices if isinstance(item, dict)]},
            "package-fingerprints.json": {"source_hash": pack.get("source_hash"), **source},
        },
        blocked_keys=ACK_BLOCKED_KEYS,
    )


def _evidence_data_documents(evidence: ImplementationDocument) -> ImplementationDocument:
    source = _as_document(evidence.get("source"))
    public = _as_document(evidence.get("public_summary"))
    return {
        "response-binding-summary.json": {"source_hash": evidence.get("source_hash"), **source},
        "response-verification-summary.json": {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "status": source.get("response_verification_status"),
            "verification_hash": source.get("response_verification_hash"),
            "response_payload_hash": source.get("response_payload_hash"),
            "response_integrity_hash": source.get("response_integrity_hash"),
            "review_pack_id": source.get("review_pack_id"),
            "review_pack_source_hash": source.get("review_pack_source_hash"),
            "transparency_zip_sha256": source.get("transparency_zip_sha256"),
            "transparency_manifest_hash": source.get("transparency_manifest_hash"),
            "transparency_feed_source_hash": source.get("transparency_feed_source_hash"),
        },
        "original-response-binding-summary.json": {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "response_payload_hash": source.get("response_payload_hash"),
            "response_integrity_hash": source.get("response_integrity_hash"),
            "review_pack_id": source.get("response_review_pack_id"),
            "review_pack_source_hash": source.get("response_review_pack_source_hash"),
            "transparency_zip_sha256": source.get("transparency_zip_sha256"),
            "transparency_manifest_hash": source.get("transparency_manifest_hash"),
            "transparency_feed_source_hash": source.get("transparency_feed_source_hash"),
            "public_summary": public,
            "response_public_summary_hash": source.get("response_public_summary_hash"),
        },
        "public-summary.json": {"source_hash": evidence.get("source_hash"), "public_summary": public},
    }


def _response_schema(pack: ImplementationDocument) -> ImplementationDocument:
    return {"package_type": ACK_RESPONSE_PACKAGE_TYPE, "required": pack.get("response_requirements", {}).get("required_fields", []), "allowed_status": sorted(ACK_ALLOWED_RESPONSE_STATUSES)}


def _evidence_public_summary(response: ImplementationDocument) -> ImplementationDocument:
    payload = _as_document(response.get("response_payload"))
    reviewer = _as_document(payload.get("reviewer"))
    return {
        "reviewer_name": reviewer.get("name"),
        "reviewer_organization": reviewer.get("organization"),
        "reviewed_notice_count": len(payload.get("reviewed_notice_ids", []) if isinstance(payload.get("reviewed_notice_ids"), list) else []),
        "reviewed_event_count": len(payload.get("reviewed_event_ids", []) if isinstance(payload.get("reviewed_event_ids"), list) else []),
        "accepted_at": payload.get("submitted_at"),
    }


def _response_payload_from_bytes(raw: bytes) -> ImplementationDocument:
    try:
        if raw[:4] == b"PK\x03\x04":
            import io

            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                if "acknowledgement-response.json" in archive.namelist():
                    raw = archive.read("acknowledgement-response.json")
                elif "review-response.json" in archive.namelist():
                    raw = archive.read("review-response.json")
                else:
                    json_entries = [name for name in archive.namelist() if name.endswith(".json")]
                    if not json_entries:
                        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response ZIP does not contain a JSON response.")
                    raw = archive.read(json_entries[0])
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Acknowledgement response could not be parsed: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response must be a JSON object.")
    return sanitize_metadata(value, blocked_keys=ACK_BLOCKED_KEYS)


def _require_response_source_binding(response: ImplementationDocument) -> None:
    required = ["review_pack_id", "review_pack_source_hash", "transparency_zip_sha256", "transparency_manifest_hash", "transparency_feed_source_hash"]
    missing = [key for key in required if not response.get(key)]
    if missing:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response is missing required source binding fields: " + ", ".join(missing))
    if response.get("package_type") != ACK_RESPONSE_PACKAGE_TYPE:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response package_type is invalid.")
    if response.get("review_status") not in ACK_ALLOWED_RESPONSE_STATUSES:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response review_status is invalid.")


def _response_stale(response: ImplementationDocument, pack: ImplementationDocument) -> bool:
    source = _as_document(pack.get("source"))
    return not (
        response.get("review_pack_id") == pack.get("pack_id")
        and response.get("review_pack_source_hash") == pack.get("source_hash")
        and response.get("transparency_zip_sha256") == source.get("transparency_zip_sha256")
        and response.get("transparency_manifest_hash") == source.get("transparency_manifest_hash")
        and response.get("transparency_feed_source_hash") == source.get("transparency_feed_source_hash")
    )


def _change_request_actions(response: ImplementationDocument) -> list[ImplementationDocument]:
    concerns = _as_list(response.get("concerns"))
    actions: list[ImplementationDocument] = []
    for concern in concerns:
        if isinstance(concern, dict):
            actions.append({"action_type": "review_transparency_acknowledgement_concern", "notice_id": concern.get("notice_id"), "event_id": concern.get("event_id"), "severity": concern.get("severity") or "warning"})
    return actions or [{"action_type": "review_transparency_acknowledgement_response", "severity": "warning"}]


def _payload_bytes(payload: ImplementationDocument, *, max_size: int) -> bytes:
    if payload.get("content_base64"):
        try:
            raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Invalid content_base64: {exc}") from exc
    elif payload.get("data_base64"):
        try:
            raw = base64.b64decode(str(payload.get("data_base64")), validate=True)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Invalid data_base64: {exc}") from exc
    elif payload.get("content"):
        raw = json.dumps(payload.get("content"), ensure_ascii=False).encode("utf-8") if isinstance(payload.get("content"), dict) else str(payload.get("content")).encode("utf-8")
    else:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response content is required.")
    if len(raw) > max_size:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response content is too large.")
    return raw


def _pack_readme(pack: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Transparency Acknowledgement Pack", "", f"Portfolio ID: {pack.get('portfolio_id')}", f"Pack ID: {pack.get('pack_id')}", f"Status: {pack.get('status')}", ""])


def _evidence_readme(evidence: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Transparency Acknowledgement Evidence", "", f"Portfolio ID: {evidence.get('portfolio_id')}", f"Acknowledgement ID: {evidence.get('acknowledgement_id')}", f"Status: {evidence.get('status')}", ""])


def _check(check_id: str, ok: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message if ok else message.replace(" is ", " is not ")}


def _state_tuple(doc: ImplementationDocument) -> dict[str, str]:
    return {"source_hash": str(doc.get("source_hash") or ""), "integrity_hash": str(doc.get("integrity_hash") or "")}


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except Exception:
        return dict(default or {})
    return sanitize_metadata(_as_document(value), blocked_keys=ACK_BLOCKED_KEYS)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(payload, blocked_keys=ACK_BLOCKED_KEYS))


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append((path, path.relative_to(root).as_posix()))
    return entries


def _write_zip(zip_path: Path, export_dir: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(export_dir):
                archive.write(resolved, entry)
        tmp_path.replace(zip_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_within(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if root_resolved != target_resolved and root_resolved not in target_resolved.parents:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Path escapes acknowledgement root: {target}")


def _safe_profile(value: str) -> str:
    return _safe_id(value or "public_summary")


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"


def _next_id(root: Path, prefix: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    max_seen = 0
    for path in root.glob(f"{prefix}-*.json"):
        try:
            max_seen = max(max_seen, int(path.stem.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{max_seen + 1:06d}"


def _redaction_findings(scope: str, text: str) -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
    sanitized = sanitize_sensitive_text(text)
    if sanitized != text:
        findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    lowered = text.lower()
    blocked_markers = (
        "github" + "key",
        "x-access-" + "token",
        "api_" + "key",
        "access_" + "token",
        "tok" + "en",
        "sec" + "ret",
        "pass" + "word",
        "source_" + "path",
        "local_" + "path",
        "file_" + "path",
    )
    for marker in blocked_markers:
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    return findings

_v142_rpgata_readiness.bind_globals(globals())
_v142_rpgata_evidence.bind_globals(globals())
