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

    def list_portfolios(self, *, include_archived: bool = False) -> list[DomainDocument]:
        rows: list[ImplementationDocument] = []
        for path in self.root.glob("*/portfolio-audit.json") if self.root.exists() else []:
            try:
                portfolio = self.get_portfolio(path.parent.name)
            except Exception:
                continue
            if not include_archived and portfolio.get("status") == "archived":
                continue
            rows.append(portfolio)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def create(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def get_portfolio(self, portfolio_id: str) -> DomainDocument:
        path = self.portfolio_path(portfolio_id)
        if not path.exists():
            raise ReleasePortfolioAuditNotFoundError("Release Portfolio Audit does not exist.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def save_portfolio(self, portfolio: DomainDocument) -> DomainDocument:
        portfolio_id = _validate_portfolio_id(str(portfolio.get("portfolio_id") or ""))
        _write_json(self.portfolio_path(portfolio_id), portfolio)
        return sanitize_metadata(portfolio, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

    def read_report(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(portfolio_id), default=default)

    def read_trend_report(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.trend_path(portfolio_id), default=default)

    def read_risk_register(self, portfolio_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.risk_path(portfolio_id), default=default)

    def read_export_manifest(self, portfolio_id: str) -> DomainDocument:
        path = self.export_dir(portfolio_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioAuditNotFoundError("Release Portfolio Audit export has not been generated.")
        return _read_json_default(path, default={})

    def report_is_stale(self, portfolio_id: str, report: DomainDocument | None = None, *, now: str | None = None) -> bool:
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

    def refresh(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def export_portfolio(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
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

    def build_zip(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
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

    def archive(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
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


def release_snapshot_integrity_hash(snapshot: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (snapshot or {}).items() if key not in {"integrity_hash", "integrity_ok", "selected_at"}})


def release_snapshot_integrity_ok(snapshot: DomainDocument | None) -> bool:
    data = _as_document(snapshot)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == release_snapshot_integrity_hash(data)





from song_agent.domains.trust import v142_rpa_readiness as _v142_rpa_readiness
from song_agent.domains.trust.v142_rpa_readiness import portfolio_report_integrity_ok as portfolio_report_integrity_ok, portfolio_trend_integrity_ok as portfolio_trend_integrity_ok, portfolio_risk_register_integrity_ok as portfolio_risk_register_integrity_ok, portfolio_manifest_integrity_ok as portfolio_manifest_integrity_ok, portfolio_audit_summary as portfolio_audit_summary, _portfolio_findings as _portfolio_findings, _build_risk_register as _build_risk_register, _portfolio_risk_score as _portfolio_risk_score, _build_recommendations as _build_recommendations, _release_readiness_ranking as _release_readiness_ranking, _portfolio_summary as _portfolio_summary, _build_trend_report as _build_trend_report, _trend_findings as _trend_findings, _portfolio_gates as _portfolio_gates, _release_summary_from_snapshot as _release_summary_from_snapshot, _snapshot_source as _snapshot_source, _selection_from_payload as _selection_from_payload, _selection_patch as _selection_patch, _pick as _pick, _rate as _rate, _portfolio_review_markdown as _portfolio_review_markdown, _portfolio_retrospective_markdown as _portfolio_retrospective_markdown, _risk_register_markdown as _risk_register_markdown, _write_portfolio_readme as _write_portfolio_readme, _file_record as _file_record, _zip_entries as _zip_entries, _validate_relative_path as _validate_relative_path, _ensure_within as _ensure_within, _sha256 as _sha256, _read_optional_json as _read_optional_json, _read_json_default as _read_json_default, _write_json as _write_json, _redaction_summary as _redaction_summary, _event_count as _event_count, _validate_portfolio_id as _validate_portfolio_id, _safe_text as _safe_text, _blocker as _blocker, _warning as _warning

_v142_rpa_readiness.bind_globals(globals())
