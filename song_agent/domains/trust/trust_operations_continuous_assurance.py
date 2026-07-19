# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_text as _as_text

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_continuous_assurance_contracts import ASSURANCE_ARCHIVE_ENTRIES as ASSURANCE_ARCHIVE_ENTRIES, CORE_EVIDENCE_SPECS as CORE_EVIDENCE_SPECS, TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION, assurance_hash as assurance_hash, assurance_manifest_hash as assurance_manifest_hash

















from song_agent.domains.trust import v142_toca_readiness as _v142_toca_readiness
from song_agent.domains.trust.v142_toca_readiness import TrustOperationsAssuranceError as TrustOperationsAssuranceError, TrustOperationsAssuranceNotFoundError as TrustOperationsAssuranceNotFoundError, TrustOperationsAssuranceStateError as TrustOperationsAssuranceStateError, _default_policy as _default_policy, _external_row as _external_row, _evidence_row_from_external as _evidence_row_from_external, _public_row as _public_row, _check as _check, _checks_summary as _checks_summary, _fingerprint_projection as _fingerprint_projection, _source_paths as _source_paths, _verifier_kwargs_from_source_paths as _verifier_kwargs_from_source_paths, _delivery_component_id as _delivery_component_id, _paths as _paths, _path_list as _path_list, _first_path as _first_path, _read_json_required as _read_json_required, _read_json_default as _read_json_default, _read_zip_json_optional as _read_zip_json_optional, _write_json as _write_json, _write_internal_json as _write_internal_json, _write_readme as _write_readme, _file_record as _file_record, _walk_files as _walk_files, _zip_entries as _zip_entries, _write_zip as _write_zip, _sha256 as _sha256, _next_id as _next_id, _append_jsonl as _append_jsonl, _read_text as _read_text, _mkdir as _mkdir, _now as _now, _safe_id as _safe_id, _sanitize as _sanitize, _fs_path as _fs_path







class TrustOperationsAssuranceStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations" / "continuous-assurance",
        *,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.lock = threading.RLock()

    def policies_dir(self) -> Path:
        return self.root / "policies"

    def policy_path(self, policy_id: str = "default") -> Path:
        return self.policies_dir() / (_safe_id(policy_id) + ".json")

    def runs_dir(self) -> Path:
        return self.root / "runs"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir() / _safe_id(run_id)

    def run_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "assurance-run.json"

    def report_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "assurance-report.json"

    def policy_snapshot_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "assurance-policy.json"

    def evidence_index_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "evidence-index.json"

    def external_summary_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "external-verification-summary.json"

    def source_paths_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "source-paths.json"

    def history_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "assurance-history.jsonl"

    def export_dir(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "export"

    def archive_zip_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "trust-operations-assurance.zip"

    def verification_report_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "trust-operations-assurance-verification-report.json"

    def read_policy(self, policy_id: str = "default") -> DomainDocument:
        path = self.policy_path(policy_id)
        if not path.exists():
            if policy_id != "default":
                raise TrustOperationsAssuranceNotFoundError(f"Assurance policy not found: {policy_id}")
            return self.write_policy(_default_policy())
        return _read_json_required(path, "Assurance policy cannot be read.")

    def write_policy(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            policy_id = _safe_id(str(payload.get("policy_id") or "default"))
            policy = _default_policy(now)
            policy.update({key: _sanitize(value) for key, value in payload.items() if key not in {"integrity_hash"}})
            policy["policy_id"] = policy_id
            policy["updated_at"] = now
            policy["integrity_hash"] = assurance_hash(policy)
            _write_json(self.policy_path(policy_id), policy)
            return _sanitize(policy)

    def list_runs(self, hub_id: str | None = None) -> list[DomainDocument]:
        if not self.runs_dir().exists():
            return []
        rows: list[ImplementationDocument] = []
        for path in sorted(self.runs_dir().glob("*/assurance-run.json")):
            run = _read_json_default(path, default={})
            if not run:
                continue
            if hub_id and run.get("hub_id") != hub_id:
                continue
            rows.append(_sanitize(run))
        return rows

    def read_run(self, run_id: str) -> DomainDocument:
        run = _read_json_default(self.run_path(run_id), default={})
        if not run:
            raise TrustOperationsAssuranceNotFoundError(f"Assurance run not found: {run_id}")
        return _sanitize(run)

    def summary(self, run_id: str) -> DomainDocument:
        return {
            "run": self.read_run(run_id),
            "report": _read_json_default(self.report_path(run_id), default={}),
            "verification": _read_json_default(self.verification_report_path(run_id), default={}),
        }

    def refresh_run(
        self,
        hub_id: str,
        payload: DomainDocument | None = None,
        *,
        policy_id: str = "default",
        now: str | None = None,
    ) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            policy = self.read_policy(policy_id)
            run_id = _safe_id(str(payload.get("run_id") or _next_id(self.runs_dir(), "toa")))
            source_paths = _source_paths(payload)
            source, external_summary, evidence_index, raw_external_rows = self._build_source(hub_id, source_paths)
            checks = self._build_checks(policy, raw_external_rows, external_summary, now)
            summary = _checks_summary(checks)
            status = "failed" if summary["blocking_failed_count"] else "warning" if summary["warning_count"] else "passed"
            readiness = "blocked" if status == "failed" else "ready_with_warnings" if status == "warning" else "ready"
            run = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE,
                "run_id": run_id,
                "hub_id": hub_id,
                "policy_id": policy.get("policy_id") or policy_id,
                "created_at": now,
                "status": status,
                "readiness": readiness,
                "source": source,
                "source_hash": stable_hash(source),
                "checks": checks,
                "summary": summary,
            }
            run["integrity_hash"] = assurance_hash(run)
            report = self._report_from_run(run, policy, evidence_index, external_summary, now)
            _mkdir(self.run_dir(run_id))
            _write_json(self.run_path(run_id), run)
            _write_json(self.policy_snapshot_path(run_id), policy)
            _write_json(self.evidence_index_path(run_id), evidence_index)
            _write_json(self.external_summary_path(run_id), external_summary)
            _write_json(self.report_path(run_id), report)
            _write_internal_json(self.source_paths_path(run_id), {"run_id": run_id, "hub_id": hub_id, "paths": source_paths})
            self._append_history(run_id, {"event_type": "assurance_run_refreshed", "created_at": now, "run_id": run_id, "source_hash": run["source_hash"], "status": status})
            return {"run": _sanitize(run), "report": _sanitize(report), "evidence_index": _sanitize(evidence_index), "external_verification_summary": _sanitize(external_summary)}

    def export_archive(self, run_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            run = self.read_run(run_id)
            self._ensure_run_current(run, payload)
            export_dir = self.export_dir(run_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            _write_readme(export_dir)
            for source, name in (
                (self.run_path(run_id), "assurance-run.json"),
                (self.report_path(run_id), "assurance-report.json"),
                (self.policy_snapshot_path(run_id), "assurance-policy.json"),
                (self.evidence_index_path(run_id), "evidence-index.json"),
                (self.external_summary_path(run_id), "external-verification-summary.json"),
            ):
                shutil.copy2(_fs_path(source), _fs_path(export_dir / name))
            history_text = _read_text(self.history_path(run_id))
            (export_dir / "assurance-history.jsonl").write_text(history_text, encoding="utf-8")
            report = _read_json_required(self.report_path(run_id), "Assurance report is missing.")
            policy = _read_json_required(self.policy_snapshot_path(run_id), "Assurance policy snapshot is missing.")
            evidence = _read_json_required(self.evidence_index_path(run_id), "Assurance evidence index is missing.")
            external = _read_json_required(self.external_summary_path(run_id), "External verification summary is missing.")
            manifest = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Continuous Assurance", "version": __version__},
                "run_id": run_id,
                "hub_id": run.get("hub_id"),
                "generated_at": now,
                "source_hash": run.get("source_hash"),
                "source": {
                    "run_hash": run.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "evidence_index_hash": evidence.get("integrity_hash"),
                    "external_verification_summary_hash": external.get("integrity_hash"),
                    "history_hash": stable_hash({"events": self._history_events(run_id)}),
                },
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-assurance-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = assurance_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-assurance-manifest.json", manifest)
            self._append_history(run_id, {"event_type": "assurance_archive_exported", "created_at": now, "run_id": run_id, "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_archive_zip(self, run_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            run = self.read_run(run_id)
            self._ensure_run_current(run, payload or {})
            export_dir = self.export_dir(run_id)
            manifest_path = export_dir / "trust-operations-assurance-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsAssuranceStateError("Assurance archive export is missing.")
            if manifest.get("source_hash") != run.get("source_hash"):
                raise TrustOperationsAssuranceStateError("Assurance archive export is stale.")
            zip_path = self.archive_zip_path(run_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {
                "created_at": now,
                "filename": zip_path.name,
                "entry_count": len(entries),
                "entries": [entry for _path, entry in entries],
                "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries),
            }
            manifest["integrity_hash"] = assurance_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "run_id": run_id}
            self._append_history(run_id, {"event_type": "assurance_archive_zip_built", "created_at": now, "run_id": run_id, "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]})
            return _sanitize(info)

    def verify_archive_zip(self, run_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_continuous_assurance_verifier import verify_trust_operations_assurance_package

        payload = payload or {}
        stored = _read_json_default(self.source_paths_path(run_id), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (_as_document(stored))
        report = verify_trust_operations_assurance_package(
            self.archive_zip_path(run_id),
            strict=bool(payload.get("strict", False)),
            require_passed=bool(payload.get("require_passed", True)),
            require_current=bool(payload.get("require_current", True)),
            **_verifier_kwargs_from_source_paths(source_paths),
        )
        _write_json(self.verification_report_path(run_id), report)
        return report

    def _build_source(self, hub_id: str, source_paths: ImplementationDocument) -> tuple[ImplementationDocument, ImplementationDocument, ImplementationDocument, list[ImplementationDocument]]:
        external_rows: list[ImplementationDocument] = []
        evidence_rows: list[ImplementationDocument] = []
        for evidence_type, spec in CORE_EVIDENCE_SPECS.items():
            archive_key = str(spec["archive_key"])
            report_key = str(spec["report_key"])
            archive_path = _first_path(source_paths.get(archive_key))
            report_path = _first_path(source_paths.get(report_key))
            row = _external_row(evidence_type, archive_path, report_path, _as_text(spec["manifest_entry"]), component_id=evidence_type)
            external_rows.append(row)
            evidence_rows.append(_evidence_row_from_external(row, required=bool(spec.get("required"))))
        for delivery_spec in DELIVERY_VERIFICATION_COMPONENTS:
            component_type = str(delivery_spec["component_type"])
            paths = _path_list(source_paths.get(str(delivery_spec["payload_keys"])))
            for index, report_path in enumerate(paths, start=1):
                report = _read_json_default(report_path, default={})
                component_id = _delivery_component_id(delivery_spec, report, index)
                row = _external_row(component_type, None, report_path, "", component_id=component_id)
                external_rows.append(row)
                evidence_rows.append(_evidence_row_from_external(row, required=False))
        public_external_rows = [_public_row(row) for row in external_rows]
        public_evidence_rows = [_public_row(row) for row in evidence_rows]
        external_summary = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE,
            "hub_id": hub_id,
            "external_verifications": sorted(public_external_rows, key=lambda item: (str(item.get("evidence_type") or ""), str(item.get("component_id") or ""))),
            "summary": {
                "evidence_count": len(external_rows),
                "passed_count": sum(1 for row in external_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in external_rows if row.get("status") == "failed"),
                "missing_count": sum(1 for row in external_rows if row.get("status") in {"missing", ""}),
            },
        }
        external_summary["integrity_hash"] = assurance_hash(external_summary)
        evidence_index = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE,
            "hub_id": hub_id,
            "evidence": sorted(public_evidence_rows, key=lambda item: (str(item.get("evidence_type") or ""), str(item.get("component_id") or ""))),
            "summary": {
                "evidence_count": len(evidence_rows),
                "required_count": sum(1 for row in evidence_rows if row.get("required")),
                "passed_count": sum(1 for row in evidence_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in evidence_rows if row.get("status") == "failed"),
                "missing_count": sum(1 for row in evidence_rows if row.get("status") in {"missing", ""}),
            },
        }
        evidence_index["integrity_hash"] = assurance_hash(evidence_index)
        source = {
            "hub_id": hub_id,
            "external_verification_hashes": {
                f"{row.get('evidence_type')}:{row.get('component_id')}": row.get("verification_report_hash")
                for row in external_rows
            },
            "external_package_fingerprints": {
                f"{row.get('evidence_type')}:{row.get('component_id')}": {
                    "zip_sha256": row.get("zip_sha256"),
                    "zip_size_bytes": row.get("zip_size_bytes"),
                    "manifest_hash": row.get("manifest_hash"),
                    "package_type": row.get("package_type"),
                    "status": row.get("status"),
                }
                for row in external_rows
            },
            "external_summary_hash": external_summary["integrity_hash"],
            "evidence_index_hash": evidence_index["integrity_hash"],
        }
        return source, external_summary, evidence_index, external_rows

    def _build_checks(self, policy: ImplementationDocument, rows: list[ImplementationDocument], external_summary: ImplementationDocument, now: str) -> list[ImplementationDocument]:
        by_type = {str(row.get("evidence_type") or ""): row for row in rows if isinstance(row, dict) and str(row.get("component_id") or "") == str(row.get("evidence_type") or "")}
        checks: list[ImplementationDocument] = []
        for evidence_type, spec in CORE_EVIDENCE_SPECS.items():
            row = by_type.get(evidence_type, {})
            required = bool((_as_document(policy.get("requirements"))).get(f"require_{evidence_type}", spec.get("required")))
            status = "passed" if row.get("status") == "passed" else "failed" if required else "warning"
            checks.append(_check(f"toa_{evidence_type}_verification_current", status, "blocking" if required else "warning", f"{evidence_type} external verification is current.", evidence_ref=evidence_type, details=_fingerprint_projection(row)))
            if required:
                checks.append(_check(f"toa_{evidence_type}_package_fingerprint", "passed" if row.get("zip_sha256") and row.get("manifest_hash") else "failed", "blocking", f"{evidence_type} package fingerprint is present.", evidence_ref=evidence_type))
        checks.extend(self._delivery_checks(policy, rows))
        checks.extend(self._control_exception_checks(rows, now))
        checks.extend(self._incident_open_checks(rows))
        checks.extend(self._knowledge_guard_checks(rows))
        # Source hash rows make full-resign attacks visible to the archive verifier.
        checks.append(_check("toa_source_external_summary_integrity", "passed" if external_summary.get("integrity_hash") == assurance_hash(external_summary) else "failed", "blocking", "External verification summary integrity is valid."))
        return checks

    def _delivery_checks(self, policy: ImplementationDocument, rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
        requirements = _as_document(policy.get("requirements"))
        require_delivery = bool(requirements.get("require_delivery_ready", False))
        checks: list[ImplementationDocument] = []
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            component_type = str(spec["component_type"])
            component_rows = [row for row in rows if isinstance(row, dict) and row.get("evidence_type") == component_type]
            if not component_rows and require_delivery:
                check_id = f"toa_delivery_{_safe_id(component_type)}_present"
                checks.append(_check(check_id, "failed", "blocking", f"{component_type} verification report is required by the assurance policy.", evidence_ref=component_type))
                continue
            for row in component_rows:
                component_id = str(row.get("component_id") or component_type)
                check_id = f"toa_delivery_{_safe_id(component_id)}_verification_passed"
                status = "passed" if row.get("status") == "passed" else "failed"
                message = f"{component_id} delivery verification passed." if status == "passed" else f"{component_id} delivery verification is {row.get('status') or 'missing'}."
                checks.append(_check(check_id, status, "blocking", message, evidence_ref=f"{component_type}:{component_id}", details=_fingerprint_projection(row)))
        return checks

    def _control_exception_checks(self, rows: list[Any], now: str) -> list[ImplementationDocument]:
        signoff = next((row for row in rows if isinstance(row, dict) and row.get("evidence_type") == "control_signoff"), {})
        archive_path = signoff.get("_archive_path")
        checks: list[ImplementationDocument] = []
        expired: list[str] = []
        forbidden: list[str] = []
        if archive_path:
            exceptions = _read_zip_json_optional(Path(str(archive_path)), "control-exceptions.json")
            for exception in exceptions.get("exceptions", []) if isinstance(exceptions.get("exceptions"), list) else []:
                if not isinstance(exception, dict) or exception.get("status") != "approved":
                    continue
                risk = _as_document(exception.get("risk"))
                expires_at = risk.get("expires_at")
                if expires_at and str(expires_at) < str(now):
                    expired.append(str(exception.get("exception_id") or "unknown"))
                if risk.get("severity") in {"critical", "high"} or risk.get("required"):
                    forbidden.append(str(exception.get("exception_id") or "unknown"))
        checks.append(_check("toa_control_exception_not_expired", "failed" if expired else "passed", "blocking", "Approved Control exceptions are not expired." if not expired else "Expired Control exceptions: " + ", ".join(expired[:5])))
        checks.append(_check("toa_control_exception_no_forbidden", "failed" if forbidden else "passed", "blocking", "No critical/high/required Control exceptions are approved." if not forbidden else "Forbidden Control exceptions: " + ", ".join(forbidden[:5])))
        return checks

    def _incident_open_checks(self, rows: list[Any]) -> list[ImplementationDocument]:
        incident = next((row for row in rows if isinstance(row, dict) and row.get("evidence_type") == "incident"), {})
        archive_path = incident.get("_archive_path")
        open_blocking: list[str] = []
        if archive_path:
            incidents_doc = _read_zip_json_optional(Path(str(archive_path)), "incidents.json")
            for row in incidents_doc.get("incidents", []) if isinstance(incidents_doc.get("incidents"), list) else []:
                if not isinstance(row, dict):
                    continue
                severity = str(row.get("severity") or row.get("risk") or "")
                if row.get("status") not in {"closed", "passed", "resolved"} and (row.get("blocking") or severity in {"critical", "high"}):
                    open_blocking.append(str(row.get("incident_id") or "unknown"))
        return [_check("toa_incident_no_open_blocking", "failed" if open_blocking else "passed", "blocking", "No open blocking incidents." if not open_blocking else "Open blocking incidents: " + ", ".join(open_blocking[:5]))]

    def _knowledge_guard_checks(self, rows: list[Any]) -> list[ImplementationDocument]:
        knowledge = next((row for row in rows if isinstance(row, dict) and row.get("evidence_type") == "knowledge"), {})
        summary = _as_document(knowledge.get("summary"))
        guards_ok = knowledge.get("status") == "passed" and int(summary.get("guards_passed_count") or 0) > 0 and int(summary.get("guard_failed_count") or 0) == 0
        recurrence_ok = int(summary.get("recurrence_count") or 0) == 0
        return [
            _check("toa_regression_guards_passed", "passed" if guards_ok else "failed", "blocking", "Regression guards passed." if guards_ok else "Regression guards are missing or failed."),
            _check("toa_recurrence_not_open", "passed" if recurrence_ok else "failed", "blocking", "No open recurrence report." if recurrence_ok else "Open recurrence detected."),
        ]

    def _report_from_run(self, run: ImplementationDocument, policy: ImplementationDocument, evidence_index: ImplementationDocument, external_summary: ImplementationDocument, now: str) -> ImplementationDocument:
        report = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE,
            "run_id": run.get("run_id"),
            "hub_id": run.get("hub_id"),
            "created_at": now,
            "status": run.get("status"),
            "readiness": run.get("readiness"),
            "source_hash": run.get("source_hash"),
            "source": {
                "run_hash": run.get("integrity_hash"),
                "policy_hash": policy.get("integrity_hash"),
                "evidence_index_hash": evidence_index.get("integrity_hash"),
                "external_verification_summary_hash": external_summary.get("integrity_hash"),
            },
            "summary": _as_document(run.get("summary")),
            "warnings": [check for check in run.get("checks", []) if isinstance(check, dict) and check.get("severity") != "blocking" and check.get("status") in {"failed", "warning"}],
        }
        report["integrity_hash"] = assurance_hash(report)
        return report

    def _ensure_run_current(self, run: ImplementationDocument, payload: ImplementationDocument) -> None:
        if run.get("integrity_hash") != assurance_hash(run):
            raise TrustOperationsAssuranceStateError("Assurance run integrity failed.")
        stored = _read_json_default(self.source_paths_path(str(run.get("run_id") or "")), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (_as_document(stored))
        current_source, _external, _evidence, _raw = self._build_source(str(run.get("hub_id") or ""), source_paths)
        if stable_hash(current_source) != run.get("source_hash"):
            raise TrustOperationsAssuranceStateError("Assurance run source is stale. Refresh before export.")

    def _history_events(self, run_id: str) -> list[ImplementationDocument]:
        events: list[ImplementationDocument] = []
        for line in _read_text(self.history_path(run_id)).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(_sanitize(item))
        return events

    def _append_history(self, run_id: str, payload: ImplementationDocument) -> None:
        _append_jsonl(self.history_path(run_id), payload)

_v142_toca_readiness.bind_globals(globals())
