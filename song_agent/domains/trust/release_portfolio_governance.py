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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations_audit import ReleaseOperationsAuditStore as ReleaseOperationsAuditStore
from song_agent.domains.trust.release_operations_audit_verifier import verify_release_operations_audit_package as verify_release_operations_audit_package, write_release_operations_audit_verification_report as write_release_operations_audit_verification_report
from song_agent.domains.trust.release_operations_archive_verifier import verify_release_operations_archive_package as verify_release_operations_archive_package, write_release_operations_archive_verification_report as write_release_operations_archive_verification_report
from song_agent.domains.trust.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore as ReleaseOperationsReviewerPackStore
from song_agent.domains.trust.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack as verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report as write_release_operations_reviewer_pack_verification_report
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_ok as portfolio_report_integrity_ok, portfolio_risk_register_integrity_ok as portfolio_risk_register_integrity_ok, portfolio_trend_integrity_ok as portfolio_trend_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_contracts import ACTION_PLAN_HASH_EXCLUDE_KEYS as ACTION_PLAN_HASH_EXCLUDE_KEYS, EXECUTION_REPORT_HASH_EXCLUDE_KEYS as EXECUTION_REPORT_HASH_EXCLUDE_KEYS, MANIFEST_HASH_EXCLUDE_KEYS as MANIFEST_HASH_EXCLUDE_KEYS, MANUAL_LIST_HASH_EXCLUDE_KEYS as MANUAL_LIST_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_BLOCKED_KEYS, QUEUE_HASH_EXCLUDE_KEYS as QUEUE_HASH_EXCLUDE_KEYS, action_plan_integrity_hash as action_plan_integrity_hash, execution_report_integrity_hash as execution_report_integrity_hash, governance_manifest_integrity_hash as governance_manifest_integrity_hash, manual_action_list_integrity_hash as manual_action_list_integrity_hash, queue_integrity_hash as queue_integrity_hash
from song_agent.domains.trust.v142_rpg_readiness import ReleasePortfolioGovernanceStoreReadinessMixin
from song_agent.domains.trust import v142_rpg_readiness as _v142_rpg_readiness
from song_agent.domains.trust.v142_rpg_evidence import ReleasePortfolioGovernanceStoreEvidenceMixin
from song_agent.domains.trust import v142_rpg_evidence as _v142_rpg_evidence



PORTFOLIO_GOVERNANCE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_EXPORT_SCHEMA_VERSION = 1

PORTFOLIO_GOVERNANCE_STALE_MESSAGE = "Portfolio Governance Queue source is stale. Refresh Portfolio Audit and create a new queue."





OPEN_QUEUE_STATUSES = {"draft", "planned", "running", "safe_completed", "manual_required", "blocked", "failed"}
SAFE_ACTIONS = {
    "portfolio.refresh",
    "portfolio.export",
    "portfolio.zip",
    "portfolio.verify",
    "reviewer_pack.refresh",
    "reviewer_pack.export",
    "reviewer_pack.zip",
    "reviewer_pack.verify",
    "operations_audit.refresh",
    "operations_audit.export",
    "operations_audit.zip",
    "operations_audit.verify",
    "operations_archive.verify",
    "runbook.refresh_report",
}


class ReleasePortfolioGovernanceError(ValueError):
    pass


class ReleasePortfolioGovernanceNotFoundError(ReleasePortfolioGovernanceError):
    pass


class ReleasePortfolioGovernanceStateError(ReleasePortfolioGovernanceError):
    pass


class ReleasePortfolioGovernanceStore(ReleasePortfolioGovernanceStoreReadinessMixin, ReleasePortfolioGovernanceStoreEvidenceMixin):
    def __init__(
        self,
        *,
        portfolio_store: ReleasePortfolioAuditStore,
        reviewer_pack_store: ReleaseOperationsReviewerPackStore,
        audit_store: ReleaseOperationsAuditStore,
        signoff_store: ReleaseOperationsSignoffStore,
        root: Path | str | None = None,
    ) -> None:
        self.portfolio_store = portfolio_store
        self.reviewer_pack_store = reviewer_pack_store
        self.audit_store = audit_store
        self.signoff_store = signoff_store
        self.root = Path(root).resolve() if root is not None else (portfolio_store.root.parent / "portfolio-governance-queues").resolve()
        self.lock = threading.RLock()



































def queue_integrity_ok(queue: DomainDocument | None) -> bool:
    data = _as_document(queue)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == queue_integrity_hash(data)





def action_plan_integrity_ok(plan: DomainDocument | None) -> bool:
    data = _as_document(plan)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == action_plan_integrity_hash(data)





def execution_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == execution_report_integrity_hash(data)





def manual_action_list_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == manual_action_list_integrity_hash(data)


def item_result_integrity_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "integrity_hash"})





def governance_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_manifest_integrity_hash(data)


def queue_summary(queue: DomainDocument | None, execution: DomainDocument | None = None) -> DomainDocument:
    q = _as_document(queue)
    e = _as_document(execution)
    summary = _document_or(e.get("summary"), _as_document(q.get("execution")))
    return sanitize_metadata(
        {
            "status": q.get("status") or e.get("status") or "missing",
            "queue_id": q.get("queue_id"),
            "portfolio_id": q.get("portfolio_id"),
            "total_items": summary.get("total_items", 0),
            "safe_completed": summary.get("safe_completed", 0),
            "manual_required": summary.get("manual_required", 0),
            "blocked": summary.get("blocked", 0),
            "failed": summary.get("failed", 0),
            "post_portfolio_refresh_required": bool((_as_document(q.get("execution"))).get("post_portfolio_refresh_required")),
            "integrity_ok": queue_integrity_ok(q),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS,
    )


def _build_action_plan(queue_id: str, source: ImplementationDocument, report: ImplementationDocument, trend: ImplementationDocument, risks: ImplementationDocument, payload: ImplementationDocument, *, generated_at: str) -> ImplementationDocument:
    items: list[ImplementationDocument] = []
    risks_by_category = _ids_by_category(risks.get("risks", []) if isinstance(risks.get("risks"), list) else [])
    recs_by_category = _ids_by_category(report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else [], key_name="recommendation_id")
    release_summaries = _as_list(report.get("release_summaries"))
    for release in release_summaries:
        if not isinstance(release, dict):
            continue
        release_id = str(release.get("release_id") or "")
        if not release_id:
            continue
        if release.get("reviewer_pack_verification_status") != "passed":
            for action in ("reviewer_pack.refresh", "reviewer_pack.export", "reviewer_pack.zip", "reviewer_pack.verify"):
                _add_item(items, action, release_id, "reviewer_pack", "high", "Reviewer Pack evidence is missing or not verified.", risks_by_category, recs_by_category)
        audit_summary = _as_document(release.get("audit_summary"))
        if release.get("audit_verification_status") != "passed" or audit_summary.get("status") == "failed":
            for action in ("operations_audit.refresh", "operations_audit.export", "operations_audit.zip", "operations_audit.verify"):
                _add_item(items, action, release_id, "audit", "high", "Operations Audit evidence is missing or not verified.", risks_by_category, recs_by_category)
        archive = _as_document(release.get("archive_summary"))
        if archive.get("verification_status") != "passed":
            if archive.get("manifest_hash"):
                _add_item(items, "operations_archive.verify", release_id, "archive", "medium", "Operations Archive verification is missing or failed.", risks_by_category, recs_by_category)
            else:
                _add_manual(items, "operations_archive.export_or_signoff_review", release_id, "archive", "medium", "Review Operations Signoff and export Archive before verification.", risks_by_category, recs_by_category)
        if int(release.get("applied_change_request_count") or 0) > 0:
            _add_manual(items, "change_request.review", release_id, "change_control", "medium", "Review recurring Change Request cause.", risks_by_category, recs_by_category)
            _add_manual(items, "process_rule_candidate.review", release_id, "change_control", "medium", "Decide whether a process rule should be updated.", risks_by_category, recs_by_category)
        reviewer_summary = _as_document(release.get("reviewer_pack_summary"))
        if int(reviewer_summary.get("manual_required_count") or 0) > 0:
            _add_manual(items, "runbook_policy.review", release_id, "manual_bottleneck", "low", "Review recurring manual-required runbook items.", risks_by_category, recs_by_category)
        if release.get("integrity_ok") is False or (audit_summary.get("status") == "failed"):
            _add_manual(items, "evidence_integrity.rebuild_review", release_id, "integrity", "critical", "Review corrupted evidence manually before rebuild.", risks_by_category, recs_by_category)
            _add_blocked(items, "unsafe_to_auto_fix", release_id, "integrity", "critical", "Unsafe to auto-fix evidence integrity issues.", risks_by_category, recs_by_category)
    if bool(payload.get("include_manual_actions", True)):
        for finding in trend.get("trend_findings", []) if isinstance(trend.get("trend_findings"), list) else []:
            if isinstance(finding, dict) and finding.get("category") == "change_control":
                _add_manual(items, "portfolio_policy.change", "", "change_control", "medium", "Review portfolio-level change-control trend.", risks_by_category, recs_by_category)
    if not bool(payload.get("include_low_risks", True)):
        items = [item for item in items if item.get("severity") != "low"]
    items = _dedupe_items(items)
    for index, item in enumerate(items, start=1):
        item["item_id"] = f"pgqitem-{index:06d}"
        item["status"] = "queued" if item.get("safety") == "safe" else item.get("safety")
    plan = {"schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION, "queue_id": queue_id, "generated_at": generated_at, "source_hash": stable_hash(source), "items": items}
    plan["integrity_hash"] = action_plan_integrity_hash(plan)
    return sanitize_metadata(plan, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _add_item(items: list[ImplementationDocument], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    items.append(_base_item(action, release_id, category, severity, reason, "safe", risks, recs))


def _add_manual(items: list[ImplementationDocument], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    item = _base_item(action, release_id, category, severity, reason, "manual_required", risks, recs)
    item["manual_instruction"] = _manual_instruction(action, category)
    items.append(item)


def _add_blocked(items: list[ImplementationDocument], action: str, release_id: str, category: str, severity: str, reason: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> None:
    items.append(_base_item(action, release_id, category, severity, reason, "blocked", risks, recs))


def _base_item(action: str, release_id: str, category: str, severity: str, reason: str, safety: str, risks: dict[str, list[str]], recs: dict[str, list[str]]) -> ImplementationDocument:
    return {
        "item_id": "",
        "action_type": action,
        "scope": "release" if release_id else "portfolio",
        "release_id": release_id or None,
        "category": category,
        "severity": severity,
        "status": "queued",
        "safety": safety,
        "reason": reason,
        "source_risk_ids": risks.get(category, []),
        "source_recommendation_ids": recs.get(category, []),
        "depends_on": [],
        "expected_outputs": _expected_outputs(action),
        "manual_instruction": None,
    }


def _expected_outputs(action: str) -> list[str]:
    if action.endswith(".verify"):
        return ["verification_report"]
    if action.endswith(".zip"):
        return ["zip"]
    if action.endswith(".export"):
        return ["manifest"]
    if action.endswith(".refresh"):
        return ["report"]
    return []


def _manual_instruction(action: str, category: str) -> str:
    instructions = {
        "operations_archive.export_or_signoff_review": "Open Release Operations Signoff and Archive state, then decide whether archive export is allowed.",
        "change_request.review": "Review Release Operations Change Request history and decide whether a process fix is needed.",
        "process_rule_candidate.review": "Review whether this recurring issue should become a process rule.",
        "runbook_policy.review": "Review manual-required Runbook items and decide whether safe deterministic actions can be added later.",
        "evidence_integrity.rebuild_review": "Inspect corrupted evidence manually before any rebuild.",
        "portfolio_policy.change": "Review portfolio trend and decide whether governance policy needs adjustment.",
    }
    return instructions.get(action, f"Review {category} manually before taking action.")


def _dedupe_items(items: list[ImplementationDocument]) -> list[ImplementationDocument]:
    seen: set[tuple[str, str, str]] = set()
    result: list[ImplementationDocument] = []
    for item in items:
        key = (str(item.get("action_type") or ""), str(item.get("release_id") or ""), str(item.get("safety") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _ids_by_category(items: list[Any], *, key_name: str = "risk_id") -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "")
        identifier = str(item.get(key_name) or "")
        if category and identifier:
            result.setdefault(category, []).append(identifier)
    return result


def _manual_action_list(queue_id: str, plan: ImplementationDocument, *, generated_at: str) -> ImplementationDocument:
    rows: list[ImplementationDocument] = []
    for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
        if not isinstance(item, dict) or item.get("safety") != "manual_required":
            continue
        rows.append(
            {
                "item_id": item.get("item_id"),
                "release_id": item.get("release_id"),
                "action_type": item.get("action_type"),
                "title": item.get("reason"),
                "instruction": item.get("manual_instruction") or _manual_instruction(str(item.get("action_type") or ""), str(item.get("category") or "")),
                "required_role": "owner" if str(item.get("action_type") or "").startswith("change_request") else "reviewer",
                "risk_ids": item.get("source_risk_ids", []),
                "recommendation_ids": item.get("source_recommendation_ids", []),
            }
        )
    report = {"schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION, "queue_id": queue_id, "generated_at": generated_at, "items": rows}
    report["integrity_hash"] = manual_action_list_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _execution_report(queue_id: str, *, source_hash: str, plan: ImplementationDocument, generated_at: str, item_results: list[ImplementationDocument], post_conditions: ImplementationDocument) -> ImplementationDocument:
    items = _as_list(plan.get("items"))
    summary = {
        "total_items": len(items),
        "safe_completed": sum(1 for item in items if isinstance(item, dict) and item.get("safety") == "safe" and item.get("status") == "completed"),
        "manual_required": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "manual_required"),
        "blocked": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "blocked"),
        "failed": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "failed"),
        "skipped": sum(1 for item in items if isinstance(item, dict) and item.get("status") == "skipped"),
    }
    blockers = []
    warnings = []
    if summary["failed"]:
        blockers.append({"check_id": "failed_safe_actions", "message": "One or more safe actions failed."})
    if summary["blocked"]:
        warnings.append({"check_id": "blocked_actions", "message": "One or more actions are blocked."})
    if summary["manual_required"]:
        warnings.append({"check_id": "manual_required_actions", "message": "Manual-required governance actions remain."})
    if post_conditions.get("portfolio_refresh_required"):
        warnings.append({"check_id": "post_portfolio_refresh_required", "message": "Portfolio Audit must be refreshed after safe actions."})
    status = "failed" if summary["failed"] else "blocked" if summary["blocked"] else "manual_required" if summary["manual_required"] else "safe_completed"
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_SCHEMA_VERSION,
        "queue_id": queue_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "status": status,
        "summary": summary,
        "item_results": item_results,
        "post_conditions": {
            "portfolio_refresh_required": bool(post_conditions.get("portfolio_refresh_required", False)),
            "portfolio_refreshed": bool(post_conditions.get("portfolio_refreshed", False)),
            "pre_source_hash": post_conditions.get("pre_source_hash"),
            "post_source_hash": post_conditions.get("post_source_hash"),
            "post_portfolio_report_hash": post_conditions.get("post_portfolio_report_hash"),
        },
        "warnings": warnings,
        "blockers": blockers,
    }
    report["integrity_hash"] = execution_report_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _queue_execution_summary(execution: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(execution.get("summary"))
    post = _as_document(execution.get("post_conditions"))
    return {
        "started_at": None,
        "completed_at": execution.get("generated_at"),
        "run_count": 0,
        "safe_action_count": summary.get("safe_completed", 0),
        "manual_required_count": summary.get("manual_required", 0),
        "blocked_count": summary.get("blocked", 0),
        "failed_count": summary.get("failed", 0),
        "post_portfolio_refresh_required": bool(post.get("portfolio_refresh_required", False)),
        "post_portfolio_report_hash": post.get("post_portfolio_report_hash"),
        "total_items": summary.get("total_items", 0),
    }


def _queue_status_from_plan(plan: ImplementationDocument) -> str:
    items = _as_list(plan.get("items"))
    return "planned" if items else "safe_completed"


def _risk_recommendation_map(plan: ImplementationDocument) -> ImplementationDocument:
    return {
        "queue_id": plan.get("queue_id"),
        "items": [
            {
                "item_id": item.get("item_id"),
                "action_type": item.get("action_type"),
                "release_id": item.get("release_id"),
                "risk_ids": item.get("source_risk_ids", []),
                "recommendation_ids": item.get("source_recommendation_ids", []),
            }
            for item in plan.get("items", [])
            if isinstance(item, dict)
        ],
    }


def _governance_actions_markdown(queue: ImplementationDocument, plan: ImplementationDocument, execution: ImplementationDocument) -> str:
    lines = [
        "# MusicForge Portfolio Governance Queue",
        "",
        f"Queue: {queue.get('queue_id')}",
        f"Portfolio: {queue.get('portfolio_id')}",
        f"Status: {queue.get('status')}",
        f"Execution: {execution.get('status')}",
        "",
        "## Actions",
    ]
    for item in plan.get("items", []) if isinstance(plan.get("items"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('item_id')} | {item.get('action_type')} | {item.get('release_id') or '-'} | {item.get('safety')} | {item.get('status')}")
    return "\n".join(lines) + "\n"


def _manual_actions_markdown(manual: ImplementationDocument) -> str:
    lines = ["# Manual Governance Actions", ""]
    items = _as_list(manual.get("items"))
    if not items:
        lines.append("- None")
    for item in items:
        if isinstance(item, dict):
            lines.append(f"- {item.get('item_id')} | {item.get('action_type')} | {item.get('release_id') or '-'} | {item.get('instruction')}")
    return "\n".join(lines) + "\n"


def _write_readme(export_dir: Path, queue: ImplementationDocument, execution: ImplementationDocument) -> None:
    text = "\n".join(
        [
            "MusicForge Release Portfolio Governance Queue",
            "",
            f"Queue: {queue.get('queue_id')}",
            f"Portfolio: {queue.get('portfolio_id')}",
            f"Status: {execution.get('status')}",
            "",
            "This package contains summary governance actions only. It does not contain Release ZIPs, audio files, credentials, or external submission payloads.",
            "Verify with: python -m song_agent.cli verify-release-portfolio-governance-package governance-queue.zip --strict --json",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(text, encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        entry = path.relative_to(root).as_posix()
        if not _is_safe_entry(entry):
            raise ReleasePortfolioGovernanceStateError(f"Unsafe governance export entry: {entry}")
        entries.append((path, entry))
    return entries


def _is_safe_entry(entry: str) -> bool:
    if "\\" in entry or not entry or entry.startswith("/") or entry.startswith("//"):
        return False
    parts = entry.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return True


def _ensure_within(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved != root_resolved and root_resolved not in target_resolved.parents:
        raise ReleasePortfolioGovernanceStateError("Resolved path escapes the Governance Queue directory.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS)


def _write_json(path: Path, value: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_BLOCKED_KEYS))


def _event_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _validate_queue_id(value: str) -> str:
    if not value.startswith("pgq-") or not value[4:].isdigit():
        raise ReleasePortfolioGovernanceNotFoundError("Invalid Portfolio Governance Queue id.")
    return value


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

_v142_rpg_readiness.bind_globals(globals())
_v142_rpg_evidence.bind_globals(globals())
