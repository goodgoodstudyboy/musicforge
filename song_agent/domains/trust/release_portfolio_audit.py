from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

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
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_summary as operations_report_summary
from song_agent.domains.trust.release_operations import operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_audit import ReleaseOperationsAuditStore as ReleaseOperationsAuditStore, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore as ReleaseOperationsReviewerPackStore, reviewer_report_integrity_ok as reviewer_report_integrity_ok, reviewer_pack_summary as reviewer_pack_summary
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_archive_manifest_integrity_ok as operations_archive_manifest_integrity_ok, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_summary as operations_signoff_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_audit_contracts import PORTFOLIO_AUDIT_BLOCKED_KEYS as PORTFOLIO_AUDIT_BLOCKED_KEYS, PORTFOLIO_AUDIT_HASH_EXCLUDE_KEYS as PORTFOLIO_AUDIT_HASH_EXCLUDE_KEYS, PORTFOLIO_MANIFEST_HASH_EXCLUDE_KEYS as PORTFOLIO_MANIFEST_HASH_EXCLUDE_KEYS, portfolio_manifest_integrity_hash as portfolio_manifest_integrity_hash, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_risk_register_integrity_hash as portfolio_risk_register_integrity_hash, portfolio_trend_integrity_hash as portfolio_trend_integrity_hash


PORTFOLIO_AUDIT_SCHEMA_VERSION = 1
PORTFOLIO_AUDIT_EXPORT_SCHEMA_VERSION = 1





class ReleasePortfolioAuditError(ValueError):
    pass


class ReleasePortfolioAuditNotFoundError(ReleasePortfolioAuditError):
    pass


class ReleasePortfolioAuditStateError(ReleasePortfolioAuditError):
    pass


class ReleasePortfolioAuditStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore,
        operations_store: ReleaseOperationsStore,
        runbook_store: ReleaseOperationsRunbookStore,
        signoff_store: ReleaseOperationsSignoffStore,
        audit_store: ReleaseOperationsAuditStore,
        reviewer_pack_store: ReleaseOperationsReviewerPackStore,
        root: Path | str | None = None,
    ) -> None:
        self.release_store = release_store
        self.operations_store = operations_store
        self.runbook_store = runbook_store
        self.signoff_store = signoff_store
        self.audit_store = audit_store
        self.reviewer_pack_store = reviewer_pack_store
        self.root = Path(root).resolve() if root is not None else (release_store.root.parent / "portfolio-audits").resolve()
        self.lock = threading.RLock()

    def portfolio_dir(self, portfolio_id: str) -> Path:
        return self.root / _validate_portfolio_id(portfolio_id)

    def portfolio_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-audit.json"

    def report_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-audit-report.json"

    def trend_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-trend-report.json"

    def risk_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-risk-register.json"

    def snapshots_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "release-snapshots"

    def events_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-events.jsonl"

    def export_dir(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-export"

    def zip_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "portfolio-audit.zip"

    def verification_report_path(self, portfolio_id: str) -> Path:
        return self.portfolio_dir(portfolio_id) / "verification-report.json"

    def list_portfolios(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("*/portfolio-audit.json") if self.root.exists() else []:
            try:
                portfolio = self.get_portfolio(path.parent.name)
            except Exception:
                continue
            if not include_archived and portfolio.get("status") == "archived":
                continue
            rows.append(portfolio)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def create(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            portfolio_id = self._reserve_portfolio_id()
            selection = _selection_from_payload(payload)
            portfolio = {
                "schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION,
                "portfolio_id": portfolio_id,
                "name": _safe_text(payload.get("name"), 160) or "Default Release Portfolio Audit",
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "selection": selection,
                "source_hash": None,
                "latest_report_hash": None,
                "latest_export_manifest_hash": None,
                "latest_zip_sha256": None,
                "events_count": 0,
            }
            _write_json(self.portfolio_path(portfolio_id), portfolio)
            self._append_event(portfolio_id, "created", {"name": portfolio["name"]}, now=now)
            return sanitize_metadata(portfolio, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def get_portfolio(self, portfolio_id: str) -> dict[str, Any]:
        path = self.portfolio_path(portfolio_id)
        if not path.exists():
            raise ReleasePortfolioAuditNotFoundError("Release Portfolio Audit does not exist.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def save_portfolio(self, portfolio: dict[str, Any]) -> dict[str, Any]:
        portfolio_id = _validate_portfolio_id(str(portfolio.get("portfolio_id") or ""))
        _write_json(self.portfolio_path(portfolio_id), portfolio)
        return sanitize_metadata(portfolio, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def read_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_trend_report(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.trend_path(portfolio_id), default=default)

    def read_risk_register(self, portfolio_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.risk_path(portfolio_id), default=default)

    def read_export_manifest(self, portfolio_id: str) -> dict[str, Any]:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioAuditNotFoundError("Release Portfolio Audit export has not been generated.")
        return _read_json_default(path, default={})

    def report_is_stale(self, portfolio_id: str, report: dict[str, Any] | None = None, *, now: str | None = None) -> bool:
        report_data = _document_or(report, self.read_report(portfolio_id, default={}))
        if not report_data:
            return False
        source = _as_document(report_data.get("source"))
        selection = source.get("selection") if isinstance(source.get("selection"), dict) else None
        if selection is None:
            portfolio = self.get_portfolio(portfolio_id)
            selection = _as_document(portfolio.get("selection"))
        release_ids, duplicate_ids = self._selected_release_ids(_selection_from_payload(selection))
        snapshots = [self._build_release_snapshot(release_id, now=now or now_iso()) for release_id in release_ids]
        current_source = {"selection": _selection_from_payload(selection), "snapshots": [_snapshot_source(item) for item in snapshots]}
        current_hash = stable_hash(current_source)
        return current_hash != str(report_data.get("source_hash") or "") or bool(duplicate_ids)

    def refresh(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            portfolio = self.get_portfolio(portfolio_id)
            if portfolio.get("status") == "archived":
                raise ReleasePortfolioAuditStateError("Archived Portfolio Audit cannot be refreshed.")
            selection = {**_selection_from_payload(_as_document(portfolio.get("selection"))), **_selection_patch(payload)}
            portfolio["selection"] = selection
            release_ids, duplicate_ids = self._selected_release_ids(selection)
            snapshots = [self._build_release_snapshot(release_id, now=now) for release_id in release_ids]
            source = {"selection": selection, "snapshots": [_snapshot_source(item) for item in snapshots]}
            source_hash = stable_hash(source)
            blockers, warnings = _portfolio_findings(snapshots, duplicate_ids, selection)
            risk_register = _build_risk_register(portfolio_id, snapshots, source_hash=source_hash, generated_at=now)
            score = _portfolio_risk_score(risk_register.get("risks", []), snapshots)
            recommendations = _build_recommendations(snapshots, risk_register.get("risks", []))
            ranking = _release_readiness_ranking(snapshots)
            summary = _portfolio_summary(snapshots, blockers, warnings, score)
            report = {
                "schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION,
                "portfolio_id": portfolio_id,
                "generated_at": now,
                "status": "failed" if blockers or score["status"] == "failed" else score["status"],
                "source_hash": source_hash,
                "source": source,
                "summary": summary,
                "risk_score": score,
                "release_summaries": [_release_summary_from_snapshot(item) for item in snapshots],
                "release_readiness_ranking": ranking,
                "gates": _portfolio_gates(selection, snapshots),
                "warnings": warnings,
                "blockers": blockers,
                "recommendations": recommendations,
            }
            report["integrity_hash"] = portfolio_report_integrity_hash(report)
            trend = _build_trend_report(portfolio_id, snapshots, source_hash=source_hash, generated_at=now)
            _write_json(self.report_path(portfolio_id), report)
            _write_json(self.trend_path(portfolio_id), trend)
            _write_json(self.risk_path(portfolio_id), risk_register)
            snapshot_dir = self.snapshots_dir(portfolio_id)
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir)
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            for snapshot in snapshots:
                _write_json(snapshot_dir / f"{snapshot['release_id']}.json", snapshot)
            portfolio.update(
                {
                    "status": "failed" if report["status"] == "failed" else "refreshed",
                    "updated_at": now,
                    "source_hash": source_hash,
                    "latest_report_hash": report["integrity_hash"],
                    "events_count": _event_count(self.events_path(portfolio_id)),
                }
            )
            self.save_portfolio(portfolio)
            self._append_event(portfolio_id, "refreshed", {"status": report.get("status"), "release_count": len(snapshots)}, now=now)
            return sanitize_metadata(report, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def export_portfolio(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            portfolio = self.get_portfolio(portfolio_id)
            report = self.read_report(portfolio_id, default={}) or self.refresh(portfolio_id, now=now)
            trend = self.read_trend_report(portfolio_id, default={})
            risks = self.read_risk_register(portfolio_id, default={})
            if self.report_is_stale(portfolio_id, report, now=now):
                raise ReleasePortfolioAuditStateError("Portfolio Audit Report is stale. Refresh before export.")
            if not portfolio_report_integrity_ok(report):
                raise ReleasePortfolioAuditStateError("Portfolio Audit Report integrity failed. Refresh before export.")
            if not portfolio_trend_integrity_ok(trend):
                raise ReleasePortfolioAuditStateError("Portfolio Trend Report integrity failed. Refresh before export.")
            if not portfolio_risk_register_integrity_ok(risks):
                raise ReleasePortfolioAuditStateError("Portfolio Risk Register integrity failed. Refresh before export.")
            export_dir = self.export_dir(portfolio_id).resolve()
            portfolio_dir = self.portfolio_dir(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            release_summaries = _as_list(report.get("release_summaries"))
            _write_json(export_dir / "portfolio-audit-report.json", report)
            _write_json(export_dir / "portfolio-trend-report.json", trend)
            _write_json(export_dir / "portfolio-risks.json", risks)
            _write_json(export_dir / "release-index.json", {"releases": release_summaries})
            _write_json(export_dir / "reviewer-pack-summary.json", {"releases": [_pick(item, ["release_id", "release_name", "reviewer_pack_summary", "reviewer_pack_verification_status"]) for item in release_summaries]})
            _write_json(export_dir / "change-request-summary.json", {"summary": report.get("summary", {}), "releases": [_pick(item, ["release_id", "change_request_summary"]) for item in release_summaries]})
            _write_json(export_dir / "runbook-summary.json", {"releases": [_pick(item, ["release_id", "runbook_summary"]) for item in release_summaries]})
            _write_json(export_dir / "audit-summary.json", {"releases": [_pick(item, ["release_id", "audit_summary", "audit_verification_status"]) for item in release_summaries]})
            (export_dir / "PORTFOLIO_REVIEW.md").write_text(_portfolio_review_markdown(portfolio, report), encoding="utf-8")
            (export_dir / "PORTFOLIO_RETROSPECTIVE.md").write_text(_portfolio_retrospective_markdown(trend), encoding="utf-8")
            (export_dir / "RISK_REGISTER.md").write_text(_risk_register_markdown(risks), encoding="utf-8")
            _write_portfolio_readme(export_dir, portfolio, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest = {
                "schema_version": PORTFOLIO_AUDIT_EXPORT_SCHEMA_VERSION,
                "package_type": "release_portfolio_audit",
                "tool": {"name": "MusicForge Release Portfolio Audit", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "summary": {
                    "status": report.get("status"),
                    "release_count": report.get("summary", {}).get("release_count") if isinstance(report.get("summary"), dict) else 0,
                    "risk_score": report.get("risk_score", {}).get("score") if isinstance(report.get("risk_score"), dict) else None,
                },
                "sidecars": {
                    "portfolio_audit_report": {"payload_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                    "portfolio_trend_report": {"payload_hash": trend.get("integrity_hash"), "source_hash": trend.get("source_hash")},
                    "portfolio_risk_register": {"payload_hash": risks.get("integrity_hash"), "source_hash": risks.get("source_hash")},
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"portfolio": portfolio, "report": report, "trend": trend, "risks": risks}),
            }
            manifest["integrity_hash"] = portfolio_manifest_integrity_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            portfolio.update({"status": "exported", "updated_at": now, "latest_export_manifest_hash": manifest["integrity_hash"]})
            self.save_portfolio(portfolio)
            self._append_event(portfolio_id, "exported", {"status": report.get("status"), "file_count": len(files)}, now=now)
            return sanitize_metadata(manifest, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            portfolio_dir = self.portfolio_dir(portfolio_id).resolve()
            export_dir = self.export_dir(portfolio_id).resolve()
            zip_path = self.zip_path(portfolio_id).resolve()
            _ensure_within(portfolio_dir, export_dir)
            _ensure_within(portfolio_dir, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_portfolio(portfolio_id, now=now)
            report = self.read_report(portfolio_id, default={})
            if self.report_is_stale(portfolio_id, report, now=now):
                raise ReleasePortfolioAuditStateError("Portfolio Audit Report is stale. Refresh before ZIP export.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = portfolio_manifest_integrity_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
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
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            portfolio = self.get_portfolio(portfolio_id)
            portfolio.update({"status": "exported", "updated_at": now, "latest_zip_sha256": info["sha256"]})
            self.save_portfolio(portfolio)
            self._append_event(portfolio_id, "zip_built", {"sha256": info["sha256"], "entry_count": len(entries)}, now=now)
            return sanitize_metadata(info, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def archive(self, portfolio_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            portfolio = self.get_portfolio(portfolio_id)
            portfolio["status"] = "archived"
            portfolio["updated_at"] = now or now_iso()
            self.save_portfolio(portfolio)
            self._append_event(portfolio_id, "archived", {}, now=portfolio["updated_at"])
            return portfolio

    def _selected_release_ids(self, selection: ImplementationDocument) -> tuple[list[str], list[str]]:
        release_ids = [str(item).strip() for item in selection.get("release_ids", []) if str(item).strip()]
        if not release_ids:
            release_ids = [item.release_id for item in self.release_store.list_releases(include_hidden=bool(selection.get("include_hidden")))]
        if not selection.get("include_archived", True):
            release_ids = [release_id for release_id in release_ids if self.release_store.get_release(release_id).status != "archived"]
        max_releases = selection.get("max_releases")
        if max_releases:
            release_ids = release_ids[: max(1, min(500, int(max_releases)))]
        seen: set[str] = set()
        duplicates: list[str] = []
        unique: list[str] = []
        for release_id in release_ids:
            if release_id in seen:
                duplicates.append(release_id)
                continue
            seen.add(release_id)
            unique.append(release_id)
        return unique, duplicates

    def _build_release_snapshot(self, release_id: str, *, now: str) -> ImplementationDocument:
        release = self.release_store.get_release(release_id)
        operations_report = self.operations_store.read_report(release_id, default={})
        audit_report = self.audit_store.read_report(release_id, default={})
        audit_verification = _read_optional_json(self.audit_store.verification_report_path(release_id))
        reviewer_report = self.reviewer_pack_store.read_report(release_id, default={})
        reviewer_verification = _read_optional_json(self.reviewer_pack_store.verification_report_path(release_id))
        signoff = self.signoff_store.read_signoff(release_id, default={})
        archive_manifest = _read_optional_json(self.signoff_store.archive_export_dir(release_id) / "operations-archive-manifest.json")
        archive_verification = _read_optional_json(self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
        change_requests = self.signoff_store.list_change_requests(release_id)
        runbooks = self.runbook_store.list_runbooks(release_id, include_archived=True)
        latest_runbook = runbooks[0] if runbooks else {}
        snapshot: _InferenceType = {
            "schema_version": 1,
            "release_id": release_id,
            "release_name": release.name,
            "status": release.status,
            "selected_at": now,
            "release_updated_at": release.updated_at,
            "track_count": len(release.tracks),
            "operations_summary": operations_report_summary(operations_report) if operations_report else {"status": "missing"},
            "operations_report_integrity_ok": operations_report_integrity_ok(operations_report) if operations_report else False,
            "operations_report_hash": operations_report.get("integrity_hash"),
            "signoff_summary": operations_signoff_summary(signoff),
            "signoff_hash": signoff.get("payload_hash"),
            "archive_summary": {
                "status": "passed" if archive_manifest and operations_archive_manifest_integrity_ok(archive_manifest) else "missing" if not archive_manifest else "failed",
                "manifest_hash": operations_archive_manifest_hash(archive_manifest) if archive_manifest else None,
                "integrity_ok": operations_archive_manifest_integrity_ok(archive_manifest) if archive_manifest else False,
                "verification_status": archive_verification.get("status") or "missing",
                "verification_hash": stable_hash(archive_verification) if archive_verification else None,
            },
            "audit_summary": audit_summary(audit_report) if audit_report else {"status": "missing"},
            "audit_report_integrity_ok": audit_report_integrity_ok(audit_report) if audit_report else False,
            "audit_report_hash": audit_report.get("integrity_hash"),
            "audit_verification_status": audit_verification.get("status") or "missing",
            "audit_verification_hash": stable_hash(audit_verification) if audit_verification else None,
            "reviewer_pack_summary": reviewer_pack_summary(reviewer_report) if reviewer_report else {"status": "missing"},
            "reviewer_pack_integrity_ok": reviewer_report_integrity_ok(reviewer_report) if reviewer_report else False,
            "reviewer_pack_report_hash": reviewer_report.get("integrity_hash"),
            "reviewer_pack_verification_status": reviewer_verification.get("status") or "missing",
            "reviewer_pack_verification_hash": stable_hash(reviewer_verification) if reviewer_verification else None,
            "runbook_summary": runbook_summary(latest_runbook) if latest_runbook else {"status": "missing"},
            "runbook_count": len(runbooks),
            "runbook_integrity_ok": runbook_integrity_ok(latest_runbook) if latest_runbook else False,
            "change_request_summary": self.signoff_store.change_request_summary(release_id),
            "change_request_count": len(change_requests),
            "applied_change_request_count": sum(1 for item in change_requests if item.get("status") == "applied"),
            "change_request_integrity_ok": all(operations_change_request_integrity_ok(item) for item in change_requests),
            "warnings": [],
            "blockers": [],
            "stale": False,
        }
        snapshot["source_hash"] = stable_hash(_snapshot_source(snapshot))
        snapshot["integrity_hash"] = release_snapshot_integrity_hash(snapshot)
        snapshot["integrity_ok"] = release_snapshot_integrity_ok(snapshot)
        return sanitize_metadata(snapshot, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def _reserve_portfolio_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            portfolio_id = f"pfa-{index:06d}"
            directory = self.root / portfolio_id
            try:
                directory.mkdir(parents=True, exist_ok=False)
                return portfolio_id
            except FileExistsError:
                continue
        raise ReleasePortfolioAuditStateError("Unable to allocate a unique Portfolio Audit id.")

    def _append_event(self, portfolio_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.events_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = _event_count(path)
        event = sanitize_metadata({"event_id": f"pfaevt-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def release_snapshot_integrity_hash(snapshot: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (snapshot or {}).items() if key not in {"integrity_hash", "integrity_ok", "selected_at"}})


def release_snapshot_integrity_ok(snapshot: dict[str, Any] | None) -> bool:
    data = _as_document(snapshot)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == release_snapshot_integrity_hash(data)





def portfolio_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_report_integrity_hash(data)





def portfolio_trend_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_trend_integrity_hash(data)





def portfolio_risk_register_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_risk_register_integrity_hash(data)





def portfolio_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_manifest_integrity_hash(data)


def portfolio_audit_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    score = _as_document(data.get("risk_score"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_count": summary.get("release_count", 0),
            "risk_score": score.get("score"),
            "risk_status": score.get("status"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "recommendation_count": len(data.get("recommendations", []) if isinstance(data.get("recommendations"), list) else []),
            "integrity_ok": portfolio_report_integrity_ok(data),
        },
        blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS,
    )


def _portfolio_findings(snapshots: list[ImplementationDocument], duplicates: list[str], selection: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for release_id in duplicates:
        blockers.append(_blocker("duplicate_release_id", f"Release {release_id} appears more than once in portfolio selection."))
    if not snapshots:
        blockers.append(_blocker("portfolio_empty", "Portfolio Audit has no included releases."))
    for snapshot in snapshots:
        release_id = str(snapshot.get("release_id") or "")
        if not release_snapshot_integrity_ok(snapshot):
            blockers.append(_blocker("release_snapshot_integrity", f"Release snapshot integrity failed for {release_id}."))
        if not snapshot.get("operations_report_integrity_ok") and snapshot.get("operations_summary", {}).get("status") != "missing":
            blockers.append(_blocker("operations_report_integrity", f"Operations Report integrity failed for {release_id}."))
        if not snapshot.get("audit_report_integrity_ok") and snapshot.get("audit_summary", {}).get("status") != "missing":
            blockers.append(_blocker("audit_report_integrity", f"Audit Report integrity failed for {release_id}."))
        if not snapshot.get("change_request_integrity_ok"):
            blockers.append(_blocker("change_request_integrity", f"Change Request integrity failed for {release_id}."))
        if snapshot.get("reviewer_pack_summary", {}).get("status") == "missing":
            warnings.append(_warning("reviewer_pack_missing", f"Reviewer Pack is missing for {release_id}."))
        if snapshot.get("audit_verification_status") == "missing":
            warnings.append(_warning("audit_verification_missing", f"Operations Audit verification is missing for {release_id}."))
        if snapshot.get("archive_summary", {}).get("verification_status") == "missing":
            warnings.append(_warning("archive_verification_missing", f"Operations Archive verification is missing for {release_id}."))
        if selection.get("require_reviewer_packs"):
            if snapshot.get("reviewer_pack_summary", {}).get("status") == "missing" or not snapshot.get("reviewer_pack_integrity_ok") or snapshot.get("reviewer_pack_verification_status") != "passed":
                blockers.append(_blocker("reviewer_pack_required", f"Passed Reviewer Pack verification is required for {release_id}."))
        if selection.get("require_audit"):
            if snapshot.get("audit_summary", {}).get("status") == "failed" or snapshot.get("audit_verification_status") != "passed":
                blockers.append(_blocker("audit_required", f"Passed Audit package verification is required for {release_id}."))
        if selection.get("require_archive"):
            if snapshot.get("status") != "archived" and snapshot.get("signoff_summary", {}).get("status") not in {"signed", "force_signed"}:
                blockers.append(_blocker("archive_required", f"Signed or archived Operations evidence is required for {release_id}."))
            if snapshot.get("archive_summary", {}).get("verification_status") != "passed":
                blockers.append(_blocker("archive_verification_required", f"Passed Operations Archive verification is required for {release_id}."))
    return blockers, warnings


def _build_risk_register(portfolio_id: str, snapshots: list[ImplementationDocument], *, source_hash: str, generated_at: str) -> ImplementationDocument:
    risks: list[dict[str, Any]] = []

    def add(category: str, severity: str, title: str, release_ids: list[str], recommendation: str) -> None:
        if not release_ids:
            return
        risks.append(
            {
                "risk_id": f"risk-{len(risks) + 1:06d}",
                "severity": severity,
                "category": category,
                "status": "open",
                "title": title,
                "description": title,
                "release_ids": sorted(release_ids),
                "evidence_refs": [{"release_id": release_id, "type": category} for release_id in sorted(release_ids)],
                "recommendation": recommendation,
            }
        )

    add("reviewer_pack", "high", "Reviewer Pack verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("reviewer_pack_verification_status") != "passed"], "Generate and verify Reviewer Packs before external portfolio review.")
    add("audit", "high", "Audit package verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("audit_verification_status") != "passed"], "Export and verify Operations Audit packages.")
    add("archive", "medium", "Operations Archive verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("archive_summary", {}).get("verification_status") != "passed"], "Export and verify Operations Archives.")
    add("change_control", "medium", "Applied Change Requests exist in the portfolio.", [s["release_id"] for s in snapshots if int(s.get("applied_change_request_count") or 0) > 0], "Review recurring Change Request causes.")
    add("manual_bottleneck", "low", "Manual-required runbook items recur across releases.", [s["release_id"] for s in snapshots if int(s.get("reviewer_pack_summary", {}).get("manual_required_count") or 0) > 0], "Create deterministic runbook actions for recurring manual bottlenecks.")
    add("integrity", "critical", "One or more evidence integrity checks failed.", [s["release_id"] for s in snapshots if not s.get("change_request_integrity_ok") or (s.get("audit_summary", {}).get("status") != "missing" and not s.get("audit_report_integrity_ok")) or (s.get("reviewer_pack_summary", {}).get("status") != "missing" and not s.get("reviewer_pack_integrity_ok"))], "Refresh or rebuild corrupted evidence before portfolio export.")
    report = {"schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION, "portfolio_id": portfolio_id, "generated_at": generated_at, "source_hash": source_hash, "risks": risks}
    report["integrity_hash"] = portfolio_risk_register_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)


def _portfolio_risk_score(risks: list[ImplementationDocument], snapshots: list[ImplementationDocument]) -> ImplementationDocument:
    points = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    breakdown: list[dict[str, Any]] = []
    total = 0
    for risk in risks:
        base = points.get(str(risk.get("severity") or "low"), 3)
        value = base + max(0, len(risk.get("release_ids", []) if isinstance(risk.get("release_ids"), list) else []) - 1)
        total += value
        breakdown.append({"risk_id": risk.get("risk_id"), "severity": risk.get("severity"), "points": value, "title": risk.get("title")})
    force_count = sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") == "force_signed")
    if force_count:
        value = min(30, force_count * 10)
        total += value
        breakdown.append({"risk_id": "force_signoff", "severity": "medium", "points": value, "title": "Force signoff used."})
    score = min(100, total)
    status = "passed" if score <= 19 else "warning" if score <= 39 else "high_risk" if score <= 69 else "failed"
    return {"score": score, "status": status, "score_breakdown": breakdown}


def _build_recommendations(snapshots: list[ImplementationDocument], risks: list[ImplementationDocument]) -> list[ImplementationDocument]:
    recommendations: list[dict[str, Any]] = []

    def add(category: str, severity: str, release_ids: list[str], reason: str, action: str) -> None:
        if not release_ids:
            return
        recommendations.append({"recommendation_id": f"rec-{len(recommendations) + 1:06d}", "category": category, "severity": severity, "release_ids": sorted(release_ids), "reason": reason, "suggested_action": action, "manual_required": True})

    add("reviewer_pack", "high", [s["release_id"] for s in snapshots if s.get("reviewer_pack_summary", {}).get("status") == "missing"], "Signed or reviewed releases are missing Reviewer Packs.", "Run release-operations-reviewer-pack refresh/export/zip/verify.")
    add("audit", "high", [s["release_id"] for s in snapshots if s.get("audit_verification_status") in {"missing", "failed"}], "Audit package verification is incomplete.", "Run release-operations-audit --export --zip --verify.")
    add("archive", "medium", [s["release_id"] for s in snapshots if s.get("archive_summary", {}).get("verification_status") in {"missing", "failed"}], "Operations Archive verification is incomplete.", "Run release-operations-archive --export --zip --verify.")
    add("change_control", "medium", [s["release_id"] for s in snapshots if int(s.get("applied_change_request_count") or 0) > 0], "Applied Change Requests recur in this portfolio.", "Review reset/change causes and update the process runbook.")
    add("integrity", "critical", [release_id for risk in risks if risk.get("category") == "integrity" for release_id in risk.get("release_ids", [])], "Evidence integrity issue detected.", "Refresh or rebuild affected evidence before external review.")
    return recommendations


def _release_readiness_ranking(snapshots: list[ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    for snapshot in snapshots:
        blocker_count = 0
        warning_count = 0
        coverage = 0
        if snapshot.get("reviewer_pack_verification_status") == "passed":
            coverage += 35
        else:
            warning_count += 1
        if snapshot.get("audit_verification_status") == "passed":
            coverage += 35
        else:
            blocker_count += 1
        if snapshot.get("archive_summary", {}).get("verification_status") == "passed":
            coverage += 30
        else:
            warning_count += 1
        if snapshot.get("signoff_summary", {}).get("status") == "force_signed":
            warning_count += 1
        risk = blocker_count * 30 + warning_count * 8
        rows.append({"release_id": snapshot.get("release_id"), "release_name": snapshot.get("release_name"), "readiness_status": "blocked" if blocker_count else "review_needed" if warning_count else "ready", "risk_score": min(100, risk), "coverage_score": coverage, "blocker_count": blocker_count, "warning_count": warning_count, "recommendation": "ready_for_external_review" if not blocker_count and not warning_count else "review_evidence"})
    rows.sort(key=lambda item: (int(item.get("blocker_count") or 0), int(item.get("risk_score") or 0), -int(item.get("coverage_score") or 0), str(item.get("release_id") or "")))
    for index, row in enumerate(rows, start=1):
        row["readiness_rank"] = index
    return rows


def _portfolio_summary(snapshots: list[ImplementationDocument], blockers: list[ImplementationDocument], warnings: list[ImplementationDocument], score: ImplementationDocument) -> ImplementationDocument:
    return {
        "release_count": len(snapshots),
        "signed_count": sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") in {"signed", "force_signed"}),
        "archived_count": sum(1 for item in snapshots if item.get("status") == "archived"),
        "reviewer_pack_passed_count": sum(1 for item in snapshots if item.get("reviewer_pack_verification_status") == "passed"),
        "audit_passed_count": sum(1 for item in snapshots if item.get("audit_verification_status") == "passed"),
        "archive_verified_count": sum(1 for item in snapshots if item.get("archive_summary", {}).get("verification_status") == "passed"),
        "change_request_count": sum(int(item.get("change_request_count") or 0) for item in snapshots),
        "applied_change_request_count": sum(int(item.get("applied_change_request_count") or 0) for item in snapshots),
        "runbook_count": sum(int(item.get("runbook_count") or 0) for item in snapshots),
        "manual_required_count": sum(int(item.get("reviewer_pack_summary", {}).get("manual_required_count") or 0) for item in snapshots),
        "force_signoff_count": sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") == "force_signed"),
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "stale_release_count": sum(1 for item in snapshots if item.get("stale")),
        "redaction_warning_count": 0,
        "portfolio_risk_score": score.get("score"),
        "portfolio_risk_status": score.get("status"),
    }


def _build_trend_report(portfolio_id: str, snapshots: list[ImplementationDocument], *, source_hash: str, generated_at: str) -> ImplementationDocument:
    ordered = sorted(snapshots, key=lambda item: str(item.get("release_updated_at") or item.get("selected_at") or ""))
    latest = ordered[-3:]
    release_count = len(latest)
    report = {
        "schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "windows": [
            {
                "window_id": "latest_3",
                "release_count": release_count,
                "warning_rate": _rate(sum(1 for item in latest if item.get("reviewer_pack_summary", {}).get("warning_count", 0)), release_count),
                "change_request_rate": _rate(sum(1 for item in latest if int(item.get("change_request_count") or 0) > 0), release_count),
                "force_signoff_rate": _rate(sum(1 for item in latest if item.get("signoff_summary", {}).get("status") == "force_signed"), release_count),
                "audit_failure_rate": _rate(sum(1 for item in latest if item.get("audit_verification_status") not in {"passed"}), release_count),
                "reviewer_pack_failure_rate": _rate(sum(1 for item in latest if item.get("reviewer_pack_verification_status") not in {"passed"}), release_count),
            }
        ],
        "trend_lines": {
            "verifier_warnings": [{"release_id": item.get("release_id"), "value": item.get("reviewer_pack_summary", {}).get("warning_count", 0)} for item in ordered],
            "change_requests": [{"release_id": item.get("release_id"), "value": item.get("change_request_count", 0)} for item in ordered],
            "manual_required": [{"release_id": item.get("release_id"), "value": item.get("reviewer_pack_summary", {}).get("manual_required_count", 0)} for item in ordered],
            "stale_events": [{"release_id": item.get("release_id"), "value": 1 if item.get("stale") else 0} for item in ordered],
            "force_signoff": [{"release_id": item.get("release_id"), "value": 1 if item.get("signoff_summary", {}).get("status") == "force_signed" else 0} for item in ordered],
        },
        "trend_findings": _trend_findings(ordered),
    }
    report["integrity_hash"] = portfolio_trend_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)


def _trend_findings(snapshots: list[ImplementationDocument]) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if sum(1 for item in snapshots if int(item.get("change_request_count") or 0) > 0) >= 2:
        findings.append({"finding_id": "trend-001", "category": "change_control", "severity": "medium", "message": "Multiple releases include Change Requests."})
    if sum(1 for item in snapshots if item.get("audit_verification_status") != "passed"):
        findings.append({"finding_id": "trend-002", "category": "audit", "severity": "high", "message": "At least one release lacks passed Audit package verification."})
    return findings


def _portfolio_gates(selection: ImplementationDocument, snapshots: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {"gate_id": "require_reviewer_packs", "required": bool(selection.get("require_reviewer_packs")), "passed_count": sum(1 for item in snapshots if item.get("reviewer_pack_verification_status") == "passed"), "total_count": len(snapshots)},
        {"gate_id": "require_audit", "required": bool(selection.get("require_audit")), "passed_count": sum(1 for item in snapshots if item.get("audit_verification_status") == "passed"), "total_count": len(snapshots)},
        {"gate_id": "require_archive", "required": bool(selection.get("require_archive")), "passed_count": sum(1 for item in snapshots if item.get("archive_summary", {}).get("verification_status") == "passed"), "total_count": len(snapshots)},
    ]


def _release_summary_from_snapshot(snapshot: ImplementationDocument) -> ImplementationDocument:
    keys = ["release_id", "release_name", "status", "track_count", "operations_summary", "signoff_summary", "archive_summary", "audit_summary", "audit_verification_status", "reviewer_pack_summary", "reviewer_pack_verification_status", "runbook_summary", "change_request_summary", "change_request_count", "applied_change_request_count", "source_hash", "integrity_ok"]
    return _pick(snapshot, keys)


def _snapshot_source(snapshot: ImplementationDocument) -> ImplementationDocument:
    return _pick(
        snapshot,
        [
            "release_id",
            "status",
            "release_updated_at",
            "operations_report_hash",
            "signoff_hash",
            "archive_summary",
            "audit_report_hash",
            "audit_verification_status",
            "audit_verification_hash",
            "reviewer_pack_report_hash",
            "reviewer_pack_verification_status",
            "reviewer_pack_verification_hash",
            "change_request_summary",
            "runbook_summary",
        ],
    )


def _selection_from_payload(payload: ImplementationDocument) -> ImplementationDocument:
    data = _as_document(payload)
    return {
        "release_ids": [str(item).strip() for item in data.get("release_ids", []) if str(item).strip()] if isinstance(data.get("release_ids"), list) else [],
        "include_hidden": bool(data.get("include_hidden", False)),
        "include_archived": bool(data.get("include_archived", True)),
        "require_reviewer_packs": bool(data.get("require_reviewer_packs", False)),
        "require_audit": bool(data.get("require_audit", False)),
        "require_archive": bool(data.get("require_archive", False)),
        "max_releases": data.get("max_releases") if data.get("max_releases") is not None else None,
    }


def _selection_patch(payload: ImplementationDocument) -> ImplementationDocument:
    allowed = {"release_ids", "include_hidden", "include_archived", "require_reviewer_packs", "require_audit", "require_archive", "max_releases"}
    patch: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "release_ids":
            patch[key] = [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
        elif key in {"include_hidden", "include_archived", "require_reviewer_packs", "require_audit", "require_archive"}:
            patch[key] = bool(value)
        elif key == "max_releases":
            patch[key] = value if value is not None else None
    return patch


def _pick(value: ImplementationDocument, keys: list[str]) -> ImplementationDocument:
    return {key: value.get(key) for key in keys if key in value}


def _rate(value: int, total: int) -> float:
    return round(float(value) / float(total), 4) if total else 0.0


def _portfolio_review_markdown(portfolio: ImplementationDocument, report: ImplementationDocument) -> str:
    summary = _as_document(report.get("summary"))
    lines = [
        "# MusicForge Release Portfolio Audit",
        "",
        f"Portfolio: {portfolio.get('name')}",
        f"Status: {report.get('status')}",
        f"Release count: {summary.get('release_count', 0)}",
        f"Risk score: {summary.get('portfolio_risk_score')}",
        "",
        "## Release Matrix",
    ]
    for item in report.get("release_summaries", []) if isinstance(report.get("release_summaries"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('release_id')} | {item.get('release_name')} | audit={item.get('audit_verification_status')} | reviewer={item.get('reviewer_pack_verification_status')} | archive={item.get('archive_summary', {}).get('verification_status')}")
    lines.append("")
    lines.append("## Recommendations")
    recommendations = _as_list(report.get("recommendations"))
    lines.extend([f"- {item.get('recommendation_id')}: {item.get('suggested_action')}" for item in recommendations if isinstance(item, dict)] or ["- None"])
    return "\n".join(lines) + "\n"


def _portfolio_retrospective_markdown(report: ImplementationDocument) -> str:
    lines = ["# MusicForge Release Portfolio Retrospective", "", "## Trend Windows"]
    for item in report.get("windows", []) if isinstance(report.get("windows"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('window_id')}: releases={item.get('release_count')}, change_request_rate={item.get('change_request_rate')}, audit_failure_rate={item.get('audit_failure_rate')}")
    lines.append("")
    lines.append("## Findings")
    findings = _as_list(report.get("trend_findings"))
    lines.extend([f"- {item.get('category')}: {item.get('message')}" for item in findings if isinstance(item, dict)] or ["- None"])
    return "\n".join(lines) + "\n"


def _risk_register_markdown(report: ImplementationDocument) -> str:
    lines = ["# MusicForge Portfolio Risk Register", ""]
    risks = _as_list(report.get("risks"))
    for item in risks:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk_id')} | {item.get('severity')} | {item.get('category')} | {item.get('title')} | releases={', '.join(item.get('release_ids', []))}")
    if not risks:
        lines.append("- No open deterministic risks.")
    return "\n".join(lines) + "\n"


def _write_portfolio_readme(export_dir: Path, portfolio: ImplementationDocument, report: ImplementationDocument) -> None:
    lines = [
        "MusicForge Release Portfolio Audit Package",
        "",
        f"Portfolio ID: {portfolio.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        "",
        "Open PORTFOLIO_REVIEW.md for the release matrix and RISK_REGISTER.md for deterministic risks.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
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
            raise ReleasePortfolioAuditStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioAuditStateError("Refusing to operate outside release portfolio audit boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return default if default is not None else {}
    try:
        value = read_json(path)
    except Exception:
        return default if default is not None else {}
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS))


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _event_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def _validate_portfolio_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("pfa-") or not text[4:].isdigit():
        raise ReleasePortfolioAuditNotFoundError("Invalid Portfolio Audit id.")
    return text


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
