# ruff: noqa: E402,F401
from __future__ import annotations

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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore as ReleasePortfolioGovernanceReviewerPackStore, reviewer_report_integrity_hash as reviewer_report_integrity_hash, reviewer_report_integrity_ok as reviewer_report_integrity_ok, reviewer_pack_summary as reviewer_pack_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_final_board_contracts import FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_BLOCKED_KEYS as FINAL_BOARD_BLOCKED_KEYS, FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS as FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS, FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS as FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS, FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, final_board_archive_manifest_hash as final_board_archive_manifest_hash, final_board_change_request_hash as final_board_change_request_hash, final_board_change_request_integrity_ok as final_board_change_request_integrity_ok, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_response_integrity_hash as final_board_response_integrity_hash, final_board_signoff_hash as final_board_signoff_hash
from song_agent.domains.trust.v142_rpgfb_readiness import ReleasePortfolioGovernanceFinalBoardStoreReadinessMixin
from song_agent.domains.trust import v142_rpgfb_readiness as _v142_rpgfb_readiness
from song_agent.domains.trust.v142_rpgfb_evidence import ReleasePortfolioGovernanceFinalBoardStoreEvidenceMixin
from song_agent.domains.trust import v142_rpgfb_evidence as _v142_rpgfb_evidence



FINAL_BOARD_SCHEMA_VERSION = 1
FINAL_BOARD_ARCHIVE_SCHEMA_VERSION = 1
FINAL_BOARD_CHANGE_REQUEST_SCHEMA_VERSION = 1






SIGNED_STATUSES = {"signed", "force_signed"}
RESPONSE_DECISIONS = {"accepted", "accepted_with_notes", "needs_changes", "rejected"}
RESPONSE_BLOCKED_KEYS = {"source_path", "local_path", "file_path", "raw_file", "token", "api_key", "access_token", "authorization", "secret"}


class ReleasePortfolioGovernanceFinalBoardError(ValueError):
    pass


class ReleasePortfolioGovernanceFinalBoardNotFoundError(ReleasePortfolioGovernanceFinalBoardError):
    pass


class ReleasePortfolioGovernanceFinalBoardStateError(ReleasePortfolioGovernanceFinalBoardError):
    pass


class ReleasePortfolioGovernanceFinalBoardStore(ReleasePortfolioGovernanceFinalBoardStoreReadinessMixin, ReleasePortfolioGovernanceFinalBoardStoreEvidenceMixin):
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        audit_store: ReleasePortfolioGovernanceAuditStore,
        reviewer_pack_store: ReleasePortfolioGovernanceReviewerPackStore,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.audit_store = audit_store
        self.reviewer_pack_store = reviewer_pack_store
        self.lock = threading.RLock()













































def final_board_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_report_integrity_hash(data)





def final_board_response_integrity_ok(response: DomainDocument | None) -> bool:
    data = _as_document(response)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_response_integrity_hash(data)





def final_board_signoff_integrity_ok(signoff: DomainDocument | None) -> bool:
    data = _as_document(signoff)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_signoff_hash(data)


def final_board_signoff_summary(signoff: DomainDocument | None, *, stale: bool = False) -> DomainDocument:
    data = _as_document(signoff)
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    integrity_ok = final_board_signoff_integrity_ok(data)
    return sanitize_metadata({"status": data.get("status") or "missing", "signoff_id": data.get("signoff_id"), "portfolio_id": data.get("portfolio_id"), "signed_at": data.get("signed_at"), "signed_by": data.get("signed_by"), "force": bool(data.get("force")), "integrity_hash": data.get("integrity_hash"), "integrity_ok": integrity_ok, "stale": stale}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)











def final_board_archive_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_archive_manifest_hash(data)


def final_board_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    if not data:
        return {"status": "missing", "integrity_ok": False}
    summary = _as_document(data.get("summary"))
    return sanitize_metadata({"status": data.get("status"), "readiness": data.get("readiness"), "portfolio_id": data.get("portfolio_id"), "source_hash": data.get("source_hash"), "integrity_hash": data.get("integrity_hash"), "integrity_ok": final_board_report_integrity_ok(data), **summary}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _summary_from_source(source: ImplementationDocument, responses: list[ImplementationDocument], blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    return {
        "queue_count": int(source.get("queue_count") or 0),
        "signed_queue_count": int(source.get("signed_queue_count") or 0),
        "archive_verified_count": int(source.get("archive_verified_count") or 0),
        "reviewer_pack_status": source.get("governance_reviewer_report_status"),
        "reviewer_pack_verification_status": source.get("governance_reviewer_pack_verification_status"),
        "audit_status": source.get("governance_audit_report_status"),
        "audit_verification_status": source.get("governance_audit_verification_status"),
        "force_signed_queue_count": int(source.get("force_signed_queue_count") or 0),
        "reset_count": int(source.get("reset_count") or 0),
        "applied_change_request_count": int(source.get("applied_change_request_count") or 0),
        "reviewer_response_status": _reviewer_response_status(responses, source),
        "accepted_reviewer_response_count": sum(1 for item in responses if item.get("decision") in {"accepted", "accepted_with_notes"}),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _reviewer_response_status(responses: list[ImplementationDocument], source: ImplementationDocument) -> str:
    if not responses:
        return "missing"
    valid_current: list[ImplementationDocument] = []
    for item in responses:
        if not final_board_response_integrity_ok(item):
            return "invalid"
        response_source = _as_document(item.get("source"))
        current = (
            response_source.get("reviewer_pack_source_hash") == source.get("governance_reviewer_report_hash")
            and response_source.get("reviewer_pack_zip_sha256") == source.get("governance_reviewer_pack_zip_sha256")
            and response_source.get("reviewer_pack_verification_hash") == source.get("governance_reviewer_pack_verification_hash")
        )
        if current:
            valid_current.append(item)
    if not valid_current:
        return "stale"
    latest = valid_current[0]
    decision = str(latest.get("decision") or "")
    return decision if decision in RESPONSE_DECISIONS else "missing"


def _response_summary(item: ImplementationDocument) -> ImplementationDocument:
    return {"response_id": item.get("response_id"), "decision": item.get("decision"), "reviewer": item.get("reviewer", {}), "integrity_hash": item.get("integrity_hash"), "integrity_ok": final_board_response_integrity_ok(item)}


def _reviewer_response_bundle(portfolio_id: str, responses: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    bundle = {"portfolio_id": portfolio_id, "status": _reviewer_response_status(responses, source), "count": len(responses), "items": [_response_summary(item) for item in responses]}
    bundle["payload_hash"] = stable_hash({key: value for key, value in bundle.items() if key != "payload_hash"})
    return bundle


def _verification_summary(report: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(report.get("summary"))
    return {"status": report.get("status") or "missing", "zip_sha256": report.get("zip_sha256"), "zip_size_bytes": report.get("zip_size_bytes"), "manifest_hash": report.get("manifest_hash"), "summary": summary}


def _sanitize_findings(value: Any) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    if not isinstance(value, list):
        return rows
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        rows.append({"finding_id": _safe_text(item.get("finding_id"), 80) or f"finding-{index:03d}", "severity": _safe_text(item.get("severity"), 40) or "low", "status": _safe_text(item.get("status"), 40) or "closed", "category": _safe_text(item.get("category"), 80) or "general", "message": sanitize_sensitive_text(str(item.get("message") or "").strip())[:1000], "resolution_note": sanitize_sensitive_text(str(item.get("resolution_note") or "").strip())[:1000]})
    return rows


def _scope(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["final_board_signoff_reset"]
    rows = [_safe_text(item, 80) for item in value if _safe_text(item, 80)]
    return rows or ["final_board_signoff_reset"]


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in RESPONSE_BLOCKED_KEYS:
                raise ReleasePortfolioGovernanceFinalBoardStateError(f"Reviewer response field is not allowed: {key}.")
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return default if default is not None else {}
    try:
        value = read_json(path)
    except Exception:
        return default if default is not None else {}
    return sanitize_metadata(_as_document(value), blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _read_zip_json(path: Path, name: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            value = json.loads(archive.read(name).decode("utf-8"))
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=FINAL_BOARD_BLOCKED_KEYS)


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(data, blocked_keys=FINAL_BOARD_BLOCKED_KEYS))


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = _validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        _ensure_within(root.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(root.resolve()).as_posix())
        if entry in seen:
            raise ReleasePortfolioGovernanceFinalBoardStateError(f"Duplicate Final Board Archive ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceFinalBoardStateError("Refusing to operate outside Final Board boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _final_board_markdown(report: ImplementationDocument, signoff: ImplementationDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(["# Portfolio Governance Final Board", "", f"Portfolio: {report.get('portfolio_id')}", f"Report status: {report.get('status')}", f"Signoff status: {signoff.get('status')}", f"Queues: {summary.get('signed_queue_count', 0)}/{summary.get('queue_count', 0)}", f"Archives: {summary.get('archive_verified_count', 0)}", ""])


def _reviewer_response_markdown(responses: list[ImplementationDocument]) -> str:
    lines = ["# Reviewer Responses", ""]
    for item in responses:
        reviewer = _as_document(item.get("reviewer"))
        lines.append(f"- {item.get('response_id')}: {item.get('decision')} by {reviewer.get('name') or 'reviewer'}")
    lines.append("")
    return "\n".join(lines)


def _write_readme(export_dir: Path, report: ImplementationDocument, signoff: ImplementationDocument) -> None:
    lines = ["MusicForge Release Portfolio Governance Final Board Archive", "", f"Portfolio ID: {report.get('portfolio_id')}", f"Report Status: {report.get('status')}", f"Signoff Status: {signoff.get('status')}", "", "Verify with: python -m song_agent.cli verify-release-portfolio-governance-final-board-package portfolio-governance-final-board-archive.zip --strict --require-signed --require-reviewer-pack --require-audit --require-archives"]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(f"{prefix}-") or any(ch in text for ch in "\\/:"):
        raise ReleasePortfolioGovernanceFinalBoardStateError(f"Invalid {prefix} id.")
    return text

_v142_rpgfb_readiness.bind_globals(globals())
_v142_rpgfb_evidence.bind_globals(globals())
