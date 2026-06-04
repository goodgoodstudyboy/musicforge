from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_operations_audit import (
    ReleaseOperationsAuditStore,
    audit_ledger_hash,
    audit_ledger_integrity_ok,
    audit_report_integrity_hash,
    audit_report_integrity_ok,
    audit_summary,
)
from song_agent.release_operations_retrospective import (
    build_operations_retrospective_report,
    operations_retrospective_integrity_hash,
    operations_retrospective_integrity_ok,
    retrospective_summary,
)
from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore, operations_signoff_summary
from song_agent.releases import ReleaseStore, stable_hash


REVIEWER_PACK_SCHEMA_VERSION = 1
REVIEWER_PACK_EXPORT_SCHEMA_VERSION = 1
REVIEWER_PACK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
REVIEWER_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}
REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


class ReleaseOperationsReviewerPackError(ValueError):
    pass


class ReleaseOperationsReviewerPackNotFoundError(ReleaseOperationsReviewerPackError):
    pass


class ReleaseOperationsReviewerPackStateError(ReleaseOperationsReviewerPackError):
    pass


class ReleaseOperationsReviewerPackStore:
    def __init__(
        self,
        *,
        audit_store: ReleaseOperationsAuditStore,
        signoff_store: ReleaseOperationsSignoffStore,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.audit_store = audit_store
        self.signoff_store = signoff_store
        self.release_store = release_store or audit_store.release_store
        self.lock = threading.RLock()

    def root_dir(self, release_id: str) -> Path:
        return self.signoff_store.operations_dir(release_id) / "reviewer-pack"

    def report_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "reviewer-report.json"

    def retrospective_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "retrospective-report.json"

    def export_dir(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "reviewer-export"

    def zip_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "operations-reviewer-pack.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "reviewer-pack-verification-report.json"

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)

    def read_retrospective(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.retrospective_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)

    def refresh(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            release = self.release_store.get_release(release_id)
            audit_report = self.audit_store.read_report(release_id, default={})
            ledger_entries = self.audit_store.read_ledger(release_id)
            blockers, warnings = self._reviewer_findings(release_id, audit_report, ledger_entries)
            audit_verification = _read_optional_json(self.audit_store.verification_report_path(release_id))
            retrospective = build_operations_retrospective_report(
                release_id=release_id,
                audit_report=audit_report,
                ledger_entries=ledger_entries,
                generated_at=now,
            )
            signoff = self.signoff_store.read_signoff(release_id, default={})
            archive_verification = _read_optional_json(self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
            source = {
                "release_hash": stable_hash(release.to_dict()),
                "audit_report_hash": audit_report_integrity_hash(audit_report) if audit_report else None,
                "audit_report_integrity_hash": audit_report.get("integrity_hash") if audit_report else None,
                "ledger_hash": audit_ledger_hash(ledger_entries) if ledger_entries else None,
                "signoff_hash": signoff.get("payload_hash") if signoff else None,
                "archive_verification_hash": stable_hash(archive_verification) if archive_verification else None,
                "audit_verification_hash": stable_hash(audit_verification) if audit_verification else None,
                "retrospective_hash": operations_retrospective_integrity_hash(retrospective),
            }
            report = {
                "schema_version": REVIEWER_PACK_SCHEMA_VERSION,
                "release_id": release_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "reviewable",
                "source_hash": stable_hash(source),
                "source": source,
                "summary": {
                    "release_name": release.name,
                    "current_stage": self._current_stage(audit_report),
                    "audit_status": audit_report.get("status") if audit_report else "missing",
                    "audit_package_verification_status": audit_verification.get("status") or "missing",
                    "operations_signoff_status": signoff.get("status") or "missing",
                    "archive_verified": bool(archive_verification and archive_verification.get("status") != "failed"),
                    "change_request_count": _count_events(ledger_entries, "operations_change_request"),
                    "applied_change_request_count": sum(1 for item in ledger_entries if item.get("event_type") == "operations_change_request_applied"),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "override_count": _override_count(ledger_entries),
                    "manual_required_count": sum(1 for item in ledger_entries if item.get("risk") == "manual_required"),
                },
                "reviewer_findings": warnings,
                "evidence_index": _evidence_index(audit_report, ledger_entries, archive_verification),
                "change_control": retrospective.get("change_request_summary", {}),
                "risk_summary": {"hotspots": retrospective.get("risk_hotspots", []), "warnings": warnings, "blockers": blockers},
                "verification_instructions": {
                    "command": "python -m song_agent.cli verify-release-operations-reviewer-pack operations-reviewer-pack.zip --json --strict --require-audit --require-signed --require-archive",
                    "requires_audit": True,
                    "requires_signed": True,
                    "requires_archive": True,
                },
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = reviewer_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)
            retrospective = sanitize_metadata(retrospective, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)
            root = self.root_dir(release_id)
            root.mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(release_id), report)
            _write_json(self.retrospective_path(release_id), retrospective)
            return report

    def summary(self, release_id: str) -> dict[str, Any]:
        report = self.read_report(release_id, default={})
        return reviewer_pack_summary(report)

    def export_pack(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(release_id, default={}) or self.refresh(release_id, now=now)
            retrospective = self.read_retrospective(release_id, default={})
            if not reviewer_report_integrity_ok(report):
                raise ReleaseOperationsReviewerPackStateError("Reviewer Report integrity failed. Refresh before export.")
            if not operations_retrospective_integrity_ok(retrospective):
                raise ReleaseOperationsReviewerPackStateError("Retrospective Report integrity failed. Refresh before export.")
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            audit_report = self.audit_store.read_report(release_id, default={})
            ledger_entries = self.audit_store.read_ledger(release_id)
            audit_verification = _read_optional_json(self.audit_store.verification_report_path(release_id))
            _write_json(export_dir / "reviewer-report.json", report)
            _write_json(export_dir / "retrospective-report.json", retrospective)
            _write_json(export_dir / "evidence-index.json", {"items": report.get("evidence_index", [])})
            _write_json(export_dir / "audit-summary.json", {"summary": audit_summary(audit_report), "ledger_hash": audit_report.get("ledger_hash")})
            _write_json(export_dir / "ledger-timeline.json", {"timeline": retrospective.get("timeline", [])})
            _write_json(export_dir / "change-control-summary.json", {"summary": retrospective.get("change_request_summary", {})})
            _write_json(export_dir / "verifier-summary.json", {"summary": retrospective.get("verifier_outcomes", {}), "audit_verification": _verification_summary(audit_verification)})
            _write_json(export_dir / "package-summary.json", {"audit_package": _verification_summary(audit_verification), "source_ledger_hash": audit_report.get("ledger_hash")})
            _write_json(export_dir / "risk-summary.json", report.get("risk_summary", {}))
            (export_dir / "REVIEWER_GUIDE.md").write_text(_reviewer_guide(report), encoding="utf-8")
            (export_dir / "RETROSPECTIVE.md").write_text(_retrospective_markdown(retrospective), encoding="utf-8")
            (export_dir / "evidence-index.md").write_text(_evidence_index_markdown(report.get("evidence_index", [])), encoding="utf-8")
            _write_readme(export_dir, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "reviewer-pack-manifest.json"]
            manifest = {
                "schema_version": REVIEWER_PACK_EXPORT_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Release Operations Reviewer Pack", "version": __version__},
                "release_id": release_id,
                "generated_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "summary": {"status": report.get("status"), "readiness": report.get("readiness")},
                "reviewer_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "retrospective_report": {"integrity_hash": retrospective.get("integrity_hash"), "source_hash": retrospective.get("source_hash")},
                "audit_summary": {
                    "ledger_hash": audit_report.get("ledger_hash"),
                    "audit_report_integrity_hash": audit_report.get("integrity_hash"),
                    "audit_package_verification_status": audit_verification.get("status") or "missing",
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "retrospective": retrospective, "ledger": ledger_entries}),
            }
            manifest["integrity_hash"] = reviewer_pack_manifest_integrity_hash(manifest)
            _write_json(export_dir / "reviewer-pack-manifest.json", manifest)
            return sanitize_metadata(manifest, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)

    def build_zip(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            zip_path = self.zip_path(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            _ensure_within(release_dir, zip_path)
            if not (export_dir / "reviewer-pack-manifest.json").exists():
                self.export_pack(release_id, now=now)
            manifest = read_json(export_dir / "reviewer-pack-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = reviewer_pack_manifest_integrity_hash(manifest)
            _write_json(export_dir / "reviewer-pack-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            return sanitize_metadata({"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)

    def read_export_manifest(self, release_id: str) -> dict[str, Any]:
        path = self.export_dir(release_id) / "reviewer-pack-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Operations Reviewer Pack export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)

    def _reviewer_findings(self, release_id: str, audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if not audit_report:
            blockers.append(_blocker("audit_report_missing", "Operations Audit Report is missing."))
        elif not audit_report_integrity_ok(audit_report):
            blockers.append(_blocker("audit_report_integrity", "Operations Audit Report integrity failed."))
        elif audit_report.get("status") == "failed":
            blockers.append(_blocker("audit_report_failed", "Operations Audit Report is failed."))
        elif audit_report.get("status") == "warning":
            warnings.append(_warning("audit_report_warning", "Operations Audit Report has warnings."))
        if not ledger_entries:
            blockers.append(_blocker("audit_ledger_missing", "Operations Audit Ledger is missing."))
        elif not audit_ledger_integrity_ok(ledger_entries):
            blockers.append(_blocker("audit_ledger_chain", "Operations Audit Ledger hash chain failed."))
        signoff = self.signoff_store.read_signoff(release_id, default={})
        signoff_summary = operations_signoff_summary(signoff, current_report=None)
        status = str(signoff_summary.get("status") or signoff.get("status") or "")
        if status not in {"signed", "force_signed", "reset"} and not any(item.get("event_type") == "operations_signoff_signed" for item in ledger_entries):
            blockers.append(_blocker("operations_signoff_missing", "Operations Signoff evidence is missing."))
        if status == "force_signed":
            warnings.append(_warning("operations_signoff_force_signed", "Operations Signoff was force signed."))
        archive_verification = _read_optional_json(self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
        audit_verification = _read_optional_json(self.audit_store.verification_report_path(release_id))
        if not audit_verification:
            blockers.append(_blocker("operations_audit_verification_missing", "Operations Audit package verification report is missing."))
        elif audit_verification.get("status") != "passed":
            blockers.append(_blocker("operations_audit_verification_failed", "Operations Audit package verification failed."))
        if not archive_verification:
            blockers.append(_blocker("operations_archive_verification_missing", "Operations Archive verification report is missing."))
        elif archive_verification.get("status") == "failed":
            blockers.append(_blocker("operations_archive_verification_failed", "Operations Archive verification failed."))
        if audit_report.get("blockers"):
            for item in audit_report.get("blockers", [])[:10]:
                if isinstance(item, dict):
                    blockers.append(_blocker(f"audit_{item.get('check_id') or 'blocker'}", str(item.get("message") or "Audit blocker.")))
        if any(item.get("event_type") == "operations_change_request_applied" for item in ledger_entries):
            warnings.append(_warning("operations_change_request_applied", "Applied Operations Change Request exists."))
        if _redaction_summary({"audit_report": audit_report, "ledger": ledger_entries}).get("status") == "failed":
            blockers.append(_blocker("reviewer_report_redaction", "Reviewer source evidence contains sensitive values."))
        return blockers, warnings

    def _current_stage(self, audit_report: dict[str, Any]) -> str:
        operations = audit_report.get("stage_timeline") if isinstance(audit_report.get("stage_timeline"), list) else []
        if operations:
            return str(operations[-1].get("event_type") or audit_report.get("status") or "unknown")
        return str(audit_report.get("status") or "missing")


def reviewer_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in REVIEWER_REPORT_HASH_EXCLUDE_KEYS})


def reviewer_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_report_integrity_hash(data)


def reviewer_pack_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS})


def reviewer_pack_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_pack_manifest_integrity_hash(data)


def reviewer_pack_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness"),
            "source_hash": data.get("source_hash"),
            "integrity_ok": reviewer_report_integrity_ok(data),
            "audit_status": summary.get("audit_status"),
            "archive_verified": summary.get("archive_verified"),
            "warning_count": summary.get("warning_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "change_request_count": summary.get("change_request_count", 0),
        },
        blocked_keys=REVIEWER_PACK_BLOCKED_KEYS,
    )


def _evidence_index(audit_report: dict[str, Any], ledger_entries: list[dict[str, Any]], archive_verification: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        {"name": "Operations Audit Report", "type": "json", "status": audit_report.get("status") or "missing", "hash": audit_report.get("integrity_hash")},
        {"name": "Operations Audit Ledger", "type": "jsonl", "status": "passed" if ledger_entries and audit_ledger_integrity_ok(ledger_entries) else "failed", "hash": audit_report.get("ledger_hash")},
        {"name": "Operations Archive Verification", "type": "json", "status": archive_verification.get("status") or "missing", "hash": stable_hash(archive_verification) if archive_verification else None},
    ]
    for item in ledger_entries[:30]:
        items.append({"name": str(item.get("event_type") or "ledger_entry"), "type": str(item.get("domain") or "ledger"), "status": "passed" if (item.get("evidence_ref") or {}).get("integrity_ok", True) else "failed", "hash": (item.get("evidence_ref") or {}).get("payload_hash")})
    return items


def _reviewer_guide(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# MusicForge Release Operations Reviewer Guide",
        "",
        f"Release: {summary.get('release_name') or report.get('release_id')}",
        f"Status: {report.get('status')}",
        f"Readiness: {report.get('readiness')}",
        "",
        "## Scope",
        "This pack summarizes Release Operations evidence for external review. It does not include audio, artwork, platform credentials, provider raw responses, or large delivery packages.",
        "",
        "## Key Evidence",
        f"- Audit status: {summary.get('audit_status')}",
        f"- Operations signoff: {summary.get('operations_signoff_status')}",
        f"- Archive verified: {summary.get('archive_verified')}",
        f"- Applied Change Requests: {summary.get('applied_change_request_count', 0)}",
        f"- Warnings: {summary.get('warning_count', 0)}",
        "",
        "## Offline Verification",
        str((report.get("verification_instructions") or {}).get("command") or "verify-release-operations-reviewer-pack operations-reviewer-pack.zip"),
        "",
        "## Blockers",
    ]
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in blockers] or ["- None"])
    lines.append("")
    lines.append("## Warnings")
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in warnings] or ["- None"])
    lines.append("")
    lines.append("## Evidence Files")
    for item in report.get("evidence_index", [])[:20] if isinstance(report.get("evidence_index"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('name')} ({item.get('status')})")
    return "\n".join(lines) + "\n"


def _retrospective_markdown(report: dict[str, Any]) -> str:
    lines = ["# MusicForge Release Operations Retrospective", "", f"Status: {report.get('status')}", "", "## Timeline"]
    for item in report.get("timeline", [])[:40] if isinstance(report.get("timeline"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('occurred_at')} | {item.get('domain')} | {item.get('event_type')}")
    lines.append("")
    lines.append("## Stage Durations")
    for item in report.get("stage_durations", []) if isinstance(report.get("stage_durations"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('stage')}: {item.get('duration_seconds')} seconds ({item.get('duration_status')})")
    lines.append("")
    lines.append("## Risk Hotspots")
    for item in report.get("risk_hotspots", []) if isinstance(report.get("risk_hotspots"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk')}: {item.get('count')} ({item.get('severity')})")
    lines.append("")
    lines.append("## Recommendations")
    recommendations = report.get("recommendations") if isinstance(report.get("recommendations"), list) else []
    lines.extend([f"- {item.get('recommendation')}" for item in recommendations if isinstance(item, dict)] or ["- No deterministic recommendations."])
    return "\n".join(lines) + "\n"


def _evidence_index_markdown(items: Any) -> str:
    lines = ["# Evidence Index", ""]
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('name')} | {item.get('type')} | {item.get('status')} | {item.get('hash') or '-'}")
    return "\n".join(lines) + "\n"


def _write_readme(export_dir: Path, report: dict[str, Any]) -> None:
    lines = [
        "MusicForge Release Operations Reviewer Pack",
        "",
        f"Release ID: {report.get('release_id')}",
        f"Status: {report.get('status')}",
        "",
        "Open REVIEWER_GUIDE.md for external review instructions and RETROSPECTIVE.md for internal process notes.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"status": report.get("status") or "missing", "summary": summary}


def _count_events(entries: list[dict[str, Any]], domain: str) -> int:
    return sum(1 for item in entries if item.get("domain") == domain)


def _override_count(entries: list[dict[str, Any]]) -> int:
    return sum(1 for item in entries if "override" in json.dumps(item, ensure_ascii=False).lower() or "force" in str(item.get("event_type") or "").lower())


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS)


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=REVIEWER_PACK_BLOCKED_KEYS))


def _file_record(export_dir: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleaseOperationsReviewerPackStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsReviewerPackStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsReviewerPackStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsReviewerPackStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsReviewerPackStateError("Refusing to operate outside release operations reviewer pack boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _blocker(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "warning", "message": message}
