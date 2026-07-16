from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
from typing import Any as Any

from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_qa import scan_release_payload_for_sensitive_values as scan_release_payload_for_sensitive_values
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submissions import SIGNED_SUBMISSION_STATUSES as SIGNED_SUBMISSION_STATUSES, SubmissionBatch as SubmissionBatch, SubmissionStore as SubmissionStore, submission_item_current_snapshot as submission_item_current_snapshot


SUBMISSION_QA_SCHEMA_VERSION = 1


def build_submission_qa_report(
    *,
    store: SubmissionStore,
    release_id: str,
    submission: SubmissionBatch,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    source = submission_source_state(store=store, release_id=release_id, submission=submission)
    checks = _checks(store, release_id, submission, source)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    source_hash = stable_hash(source)
    report = {
        "schema_version": SUBMISSION_QA_SCHEMA_VERSION,
        "release_id": release_id,
        "submission_id": submission.submission_id,
        "generated_at": now,
        "status": status,
        "source_hash": source_hash,
        "source": source,
        "checks": checks,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
        "summary": {
            "status": status,
            "release_id": release_id,
            "submission_id": submission.submission_id,
            "item_count": len(submission.items),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "source_hash": source_hash,
            "generated_at": now,
            "export_allowed": status in {"passed", "warning"},
        },
    }
    return sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def submission_source_state(*, store: SubmissionStore, release_id: str, submission: SubmissionBatch) -> dict[str, Any]:
    release = store.release_store.get_release(release_id)
    release_signoff = store.release_store.read_signoff(release_id, default={})
    items = []
    for item in submission.items:
        current = submission_item_current_snapshot(store, item)
        items.append(
            {
                "item_id": item.item_id,
                "target_id": item.target_id,
                "status": item.status,
                "package_id": item.package_id,
                "package_zip_sha256": item.package_zip_sha256,
                "distribution_manifest_hash": item.distribution_manifest_hash,
                "distribution_signoff_hash": item.distribution_signoff_hash,
                "current": current,
            }
        )
    return sanitize_metadata(
        {
            "release": {
                "release_id": release.release_id,
                "name": release.name,
                "status": release.status,
                "track_count": len(release.tracks),
                "updated_at": release.updated_at,
                "signoff_status": release_signoff.get("status"),
                "signoff_hash": stable_hash(release_signoff) if release_signoff else None,
            },
            "submission": {
                "submission_id": submission.submission_id,
                "name": submission.name,
                "platform_group": submission.platform_group,
                "item_count": len(submission.items),
            },
            "items": items,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def submission_qa_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "release_id": data.get("release_id") or summary.get("release_id"),
            "submission_id": data.get("submission_id") or summary.get("submission_id"),
            "item_count": summary.get("item_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "source_hash": data.get("source_hash") or summary.get("source_hash"),
            "generated_at": data.get("generated_at") or summary.get("generated_at"),
            "export_allowed": bool(summary.get("export_allowed", False)),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def submission_qa_allows_export(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("status") not in {"passed", "warning"}:
        return False
    if current_source_hash and report.get("source_hash") != current_source_hash:
        return False
    return True


def mark_submission_qa_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    data["status"] = "stale"
    data["stale"] = True
    if current_source_hash:
        data["current_source_hash"] = current_source_hash
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    summary["status"] = "stale"
    if current_source_hash:
        summary["current_source_hash"] = current_source_hash
    data["summary"] = summary
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _checks(store: SubmissionStore, release_id: str, submission: SubmissionBatch, source: ImplementationDocument) -> list[ImplementationDocument]:
    release = store.release_store.get_release(release_id)
    release_signoff = store.release_store.read_signoff(release_id, default={})
    checks = [
        _check("release_exists", False, "blocking", "Release exists."),
        _check("release_signed", not (release.status == "signed" and release_signoff.get("status") in {"signed", "force_signed"}), "blocking", "Release must be signed before submission."),
        _check("submission_has_items", not submission.items, "blocking", "Submission batch must include at least one Distribution Target."),
        _check("source_hash_computable", not bool(source), "blocking", "Submission source hash can be computed."),
    ]
    duplicate_targets = _duplicates([item.target_id for item in submission.items if item.status != "withdrawn"])
    checks.append(_check("target_unique", bool(duplicate_targets), "blocking", "Submission targets must be unique.", count=len(duplicate_targets), extra={"duplicates": duplicate_targets[:20]}))
    for item in submission.items:
        current = submission_item_current_snapshot(store, item)
        exists = bool(current.get("exists"))
        stale = bool(current.get("stale"))
        verify = current.get("distribution_verify_summary") if isinstance(current.get("distribution_verify_summary"), dict) else {}
        checks.append(_check("target_exists", not exists, "blocking", f"Distribution target {item.target_id} exists.", extra={"item_id": item.item_id, "target_id": item.target_id}))
        checks.append(_check("target_snapshot_current", stale, "blocking", f"Distribution target {item.target_id} snapshot is current.", extra={"item_id": item.item_id, "target_id": item.target_id}))
        checks.append(_check("target_signed", item.status == "pending" and "signoff" in " ".join(item.warnings).lower(), "blocking", f"Distribution target {item.target_id} is signed.", extra={"item_id": item.item_id, "target_id": item.target_id}))
        checks.append(_check("target_package_zip_exists", not bool(current.get("package_zip_sha256")), "blocking", f"Distribution target {item.target_id} package ZIP exists.", extra={"item_id": item.item_id, "target_id": item.target_id}))
        checks.append(_check("target_distribution_verify", verify.get("status") not in {"passed", "warning"}, "blocking", f"Distribution package verifier status is {verify.get('status') or 'missing'}.", extra={"item_id": item.item_id, "target_id": item.target_id, "verification_summary": verify}))
    sensitive = scan_release_payload_for_sensitive_values({"submission": submission.to_dict(), "source": source})
    checks.append(_check("redaction_scan", bool(sensitive), "blocking", f"Found {len(sensitive)} sensitive issue(s)." if sensitive else "No sensitive values found.", count=len(sensitive), extra={"findings": sensitive[:20]}))
    payload_text = json.dumps({"submission": submission.to_dict(), "source": source}, ensure_ascii=False)
    checks.append(_check("absolute_path_scan", "C:\\Users" in payload_text or "/Users/" in payload_text or "/home/" in payload_text, "blocking", "Submission QA payload must not contain local absolute paths."))
    return [sanitize_metadata(check, blocked_keys=DISTRIBUTION_BLOCKED_KEYS) for check in checks]


def _check(check_id: str, failed: bool, severity: str, message: str, *, count: int | None = None, extra: ImplementationDocument | None = None) -> ImplementationDocument:
    item: dict[str, Any] = {
        "check_id": check_id,
        "status": "failed" if failed else "passed",
        "severity": severity,
        "message": message,
    }
    if count is not None:
        item["count"] = count
    if extra:
        item.update(extra)
    return item


def _check_message(check: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "check_id": check.get("check_id"),
            "message": check.get("message"),
            "severity": check.get("severity"),
            "count": check.get("count"),
            "item_id": check.get("item_id"),
            "target_id": check.get("target_id"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes
