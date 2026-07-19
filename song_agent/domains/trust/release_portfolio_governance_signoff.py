# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance import PORTFOLIO_GOVERNANCE_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_BLOCKED_KEYS, ReleasePortfolioGovernanceStore as ReleasePortfolioGovernanceStore, action_plan_integrity_ok as action_plan_integrity_ok, execution_report_integrity_ok as execution_report_integrity_ok, governance_manifest_integrity_hash as governance_manifest_integrity_hash, governance_manifest_integrity_ok as governance_manifest_integrity_ok, manual_action_list_integrity_ok as manual_action_list_integrity_ok, queue_integrity_ok as queue_integrity_ok, queue_summary as queue_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_signoff_contracts import ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS as ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, CHANGE_REQUEST_HASH_EXCLUDE_KEYS as CHANGE_REQUEST_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS, SIGNOFF_HASH_EXCLUDE_KEYS as SIGNOFF_HASH_EXCLUDE_KEYS, governance_archive_manifest_hash as governance_archive_manifest_hash, governance_change_request_hash as governance_change_request_hash, governance_change_request_integrity_ok as governance_change_request_integrity_ok, governance_signoff_hash as governance_signoff_hash
from song_agent.domains.trust.v142_rpgs_readiness import ReleasePortfolioGovernanceSignoffStoreReadinessMixin
from song_agent.domains.trust import v142_rpgs_readiness as _v142_rpgs_readiness
from song_agent.domains.trust.v142_rpgs_evidence import ReleasePortfolioGovernanceSignoffStoreEvidenceMixin
from song_agent.domains.trust import v142_rpgs_evidence as _v142_rpgs_evidence



PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_ARCHIVE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_CHANGE_REQUEST_SCHEMA_VERSION = 1




SIGNED_STATUSES = {"signed", "force_signed"}
ACK_RESOLUTIONS = {"accepted_for_followup", "waived", "already_handled"}


class ReleasePortfolioGovernanceSignoffError(ValueError):
    pass


class ReleasePortfolioGovernanceSignoffNotFoundError(ReleasePortfolioGovernanceSignoffError):
    pass


class ReleasePortfolioGovernanceSignoffStateError(ReleasePortfolioGovernanceSignoffError):
    pass


class ReleasePortfolioGovernanceSignoffStore(ReleasePortfolioGovernanceSignoffStoreReadinessMixin, ReleasePortfolioGovernanceSignoffStoreEvidenceMixin):
    def __init__(self, *, governance_store: ReleasePortfolioGovernanceStore) -> None:
        self.governance_store = governance_store
        self.lock = threading.RLock()





































def governance_signoff_integrity_ok(signoff: DomainDocument | None) -> bool:
    data = _as_document(signoff)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_signoff_hash(data)


def governance_signoff_summary(signoff: DomainDocument | None, *, current_source_hash: str | None = None, stale: bool = False) -> DomainDocument:
    data = _as_document(signoff)
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    integrity_ok = governance_signoff_integrity_ok(data)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "queue_id": data.get("queue_id"),
            "portfolio_id": data.get("portfolio_id"),
            "signoff_id": data.get("signoff_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "force": bool(data.get("force")),
            "integrity_hash": data.get("integrity_hash"),
            "integrity_ok": integrity_ok,
            "payload_hash_ok": integrity_ok,
            "stale": stale,
            "current_source_hash": current_source_hash,
            "safe_completed": data.get("summary", {}).get("safe_completed") if isinstance(data.get("summary"), dict) else None,
            "manual_required": data.get("summary", {}).get("manual_required") if isinstance(data.get("summary"), dict) else None,
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS,
    )











def governance_archive_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_archive_manifest_hash(data)


def _requirements(payload: ImplementationDocument) -> dict[str, bool]:
    raw = _as_document(payload.get("requirements"))
    return {
        "require_queue_verified": bool(raw.get("require_queue_verified", True)),
        "require_no_failed_actions": bool(raw.get("require_no_failed_actions", True)),
        "require_manual_acknowledgement": bool(raw.get("require_manual_acknowledgement", True)),
        "require_after_refresh_when_needed": bool(raw.get("require_after_refresh_when_needed", True)),
        "require_current_source": bool(raw.get("require_current_source", True)),
    }


def _manual_acknowledgements(value: Any) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if not isinstance(item, dict):
            continue
        resolution = _safe_text(item.get("resolution"), 80)
        if resolution not in ACK_RESOLUTIONS:
            resolution = "accepted_for_followup"
        rows.append(
            {
                "item_id": _safe_text(item.get("item_id"), 80),
                "action_type": _safe_text(item.get("action_type"), 120),
                "resolution": resolution,
                "owner": _safe_text(item.get("owner"), 120) or "local-user",
                "due_note": sanitize_sensitive_text(str(item.get("due_note") or "").strip())[:200],
                "note": sanitize_sensitive_text(str(item.get("note") or "").strip())[:500],
            }
        )
    return rows


def _manual_required_ids(plan: ImplementationDocument) -> set[str]:
    return {str(item.get("item_id") or "") for item in plan.get("items", []) if isinstance(item, dict) and item.get("status") == "manual_required" and str(item.get("item_id") or "")}


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)


def _write_json(path: Path, value: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS))


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
            raise ReleasePortfolioGovernanceSignoffStateError(f"Duplicate Governance Archive ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceSignoffStateError("Refusing to operate outside Portfolio Governance Queue boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_change_request_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("pgcr-") or not text.replace("pgcr-", "", 1).isdigit():
        raise ReleasePortfolioGovernanceSignoffNotFoundError("Invalid Portfolio Governance Change Request id.")
    return text


def _maybe_block(blockers: list[ImplementationDocument], check_id: str, condition: bool, message: str) -> None:
    if condition:
        blockers.append(_blocker(check_id, message))


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _write_closeout(export_dir: Path, signoff: ImplementationDocument, execution: ImplementationDocument, change_requests: ImplementationDocument) -> None:
    summary = _as_document(execution.get("summary"))
    lines = [
        "MusicForge Portfolio Governance Closeout",
        "",
        f"Queue ID: {signoff.get('queue_id')}",
        f"Signoff Status: {signoff.get('status')}",
        f"Signed By: {signoff.get('signed_by') or '-'}",
        f"Signed At: {signoff.get('signed_at') or '-'}",
        f"Safe Completed: {summary.get('safe_completed', 0)}",
        f"Manual Required: {summary.get('manual_required', 0)}",
        f"Change Requests: {change_requests.get('summary', {}).get('count', 0) if isinstance(change_requests.get('summary'), dict) else 0}",
        "",
        "This package contains governance evidence only. It does not include credentials, provider secrets, audio assets, or platform account data.",
    ]
    (export_dir / "GOVERNANCE_CLOSEOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(export_dir: Path, signoff: ImplementationDocument) -> None:
    text = "\n".join(
        [
            "MusicForge Release Portfolio Governance Archive",
            "",
            f"Queue ID: {signoff.get('queue_id')}",
            f"Signoff Status: {signoff.get('status')}",
            "Verify with: python -m song_agent.cli verify-release-portfolio-governance-archive-package governance-archive.zip --strict --require-signed --json",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(text, encoding="utf-8")

_v142_rpgs_readiness.bind_globals(globals())
_v142_rpgs_evidence.bind_globals(globals())
