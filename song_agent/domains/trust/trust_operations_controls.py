from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_path as _as_path

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
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore as TrustOperationsIncidentStore
from song_agent.domains.trust.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore as TrustOperationsIncidentKnowledgeStore
from song_agent.domains.trust.trust_operations_controls_contracts import BASELINE_CONTROLS as BASELINE_CONTROLS, CONTROL_EXPORT_ENTRIES as CONTROL_EXPORT_ENTRIES, TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE as TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE, TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION as TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION, _blocker_summary as _blocker_summary, _blockers_from_results as _blockers_from_results, _catalog_summary as _catalog_summary, _evaluate_control as _evaluate_control, _expected_control_status as _expected_control_status, _manual_actions_from_blockers as _manual_actions_from_blockers, _results_summary as _results_summary, _safe_id as _safe_id, control_hash as control_hash, control_manifest_hash as control_manifest_hash












TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}






class TrustOperationsControlError(ValueError):
    pass


class TrustOperationsControlNotFoundError(TrustOperationsControlError):
    pass


class TrustOperationsControlStateError(TrustOperationsControlError):
    pass


class TrustOperationsControlStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-controls",
        *,
        hub_store: TrustOperationsHubStore | None = None,
        incident_store: TrustOperationsIncidentStore | None = None,
        knowledge_store: TrustOperationsIncidentKnowledgeStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.incident_store = incident_store or TrustOperationsIncidentStore(hub_store=self.hub_store)
        self.knowledge_store = knowledge_store or TrustOperationsIncidentKnowledgeStore(hub_store=self.hub_store, incident_store=self.incident_store)
        self.lock = threading.RLock()

    def hub_dir(self, hub_id: str) -> Path:
        return self.root / _safe_id(hub_id)

    def catalog_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "catalog.json"

    def policies_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "policy-bundles"

    def policy_dir(self, hub_id: str, policy_id: str) -> Path:
        return self.policies_dir(hub_id) / _safe_id(policy_id)

    def policy_path(self, hub_id: str, policy_id: str) -> Path:
        return self.policy_dir(hub_id, policy_id) / "policy-bundle.json"

    def assessments_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "assessments"

    def assessment_dir(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessments_dir(hub_id) / _safe_id(assessment_id)

    def assessment_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "control-assessment-report.json"

    def control_results_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "control-results.json"

    def evidence_bindings_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "evidence-bindings.json"

    def blocker_summary_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "blocker-summary.json"

    def manual_actions_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "manual-actions.json"

    def export_dir(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "export"

    def zip_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "trust-operations-controls.zip"

    def verification_report_path(self, hub_id: str, assessment_id: str) -> Path:
        return self.assessment_dir(hub_id, assessment_id) / "trust-operations-controls-verification-report.json"

    def refresh_catalog(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            source = self._catalog_source(hub_id, payload)
            existing = _read_json_default(self.catalog_path(hub_id), default={})
            controls: list[dict[str, Any]] = []
            for spec in BASELINE_CONTROLS:
                controls.append(self._baseline_control(hub_id, spec, source, now, existing))
            entries = self.knowledge_store.list_entries(hub_id, include_hidden=False)
            guards = self.knowledge_store.list_guards(hub_id, include_archived=True)
            for entry in entries:
                if entry.get("status") in {"hidden", "archived"}:
                    continue
                controls.append(self._derived_control(hub_id, entry, guards, source, now, existing))
            catalog = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE,
                "hub_id": hub_id,
                "catalog_id": "toc-catalog-000001",
                "status": "ready" if controls else "empty",
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
                "source": source,
                "controls": sorted(controls, key=lambda item: str(item.get("control_id") or "")),
                "summary": _catalog_summary(controls),
            }
            catalog["integrity_hash"] = control_hash(catalog)
            _write_json(self.catalog_path(hub_id), catalog)
            return _sanitize(catalog)

    def read_catalog(self, hub_id: str) -> dict[str, Any]:
        path = self.catalog_path(hub_id)
        if not path.exists():
            raise TrustOperationsControlNotFoundError("Trust Operations Control Catalog not found.")
        return _read_json(path)

    def list_policies(self, hub_id: str) -> list[dict[str, Any]]:
        root = self.policies_dir(hub_id)
        if not root.exists():
            return []
        return [_sanitize(_read_json(path)) for path in sorted(root.glob("*/policy-bundle.json"))]

    def read_policy(self, hub_id: str, policy_id: str) -> dict[str, Any]:
        path = self.policy_path(hub_id, policy_id)
        if not path.exists():
            raise TrustOperationsControlNotFoundError("Trust Operations Control Policy Bundle not found.")
        return _read_json(path)

    def create_policy_bundle(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            catalog = self.read_catalog(hub_id)
            control_by_id = {str(item.get("control_id") or ""): item for item in catalog.get("controls", []) if isinstance(item, dict)}
            requested_ids = [str(item) for item in payload.get("control_ids", []) if item] if isinstance(payload.get("control_ids"), list) else sorted(control_by_id)
            controls = [control_by_id[control_id] for control_id in requested_ids if control_id in control_by_id]
            if not controls:
                raise TrustOperationsControlStateError("Control Policy Bundle requires at least one control.")
            policy_id = _safe_id(str(payload.get("policy_id") or _next_id(self.policies_dir(hub_id), "toc-policy")))
            requirements = []
            require_all = bool(payload.get("require_all", False))
            for control in controls:
                required = require_all or control.get("source", {}).get("source_type") == "baseline" or control.get("severity") in {"critical", "high"}
                requirements.append({"control_id": control.get("control_id"), "required": bool(required), "minimum_status": "passed"})
            policy = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE,
                "hub_id": hub_id,
                "policy_id": policy_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Default Trust Operations Controls")[:160]),
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "source": {"catalog_hash": catalog.get("integrity_hash"), "control_count": len(controls)},
                "control_ids": [control.get("control_id") for control in controls],
                "requirements": requirements,
                "summary": {"control_count": len(controls), "required_count": sum(1 for item in requirements if item.get("required"))},
            }
            policy["integrity_hash"] = control_hash(policy)
            _write_json(self.policy_path(hub_id, policy_id), policy)
            return _sanitize(policy)

    def assess_policy(self, hub_id: str, policy_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            catalog = self.read_catalog(hub_id)
            policy = self.read_policy(hub_id, policy_id)
            if policy.get("source", {}).get("catalog_hash") != catalog.get("integrity_hash"):
                raise TrustOperationsControlStateError("Trust Operations Control Policy source is stale. Refresh policy.")
            source = self._assessment_source(hub_id, payload)
            controls = {str(item.get("control_id") or ""): item for item in catalog.get("controls", []) if isinstance(item, dict)}
            required = {str(item.get("control_id") or ""): bool(item.get("required")) for item in policy.get("requirements", []) if isinstance(item, dict)}
            results = []
            for control_id in policy.get("control_ids", []) if isinstance(policy.get("control_ids"), list) else []:
                control = controls.get(str(control_id))
                if not control:
                    continue
                results.append(_evaluate_control(control, source, required=required.get(str(control_id), False)))
            results_doc = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE,
                "hub_id": hub_id,
                "policy_id": policy_id,
                "results": results,
                "summary": _results_summary(results),
                "source": {"catalog_hash": catalog.get("integrity_hash"), "policy_hash": policy.get("integrity_hash"), "assessment_source_hash": source.get("source_hash")},
            }
            results_doc["integrity_hash"] = control_hash(results_doc)
            blockers = _blockers_from_results(results, required)
            blocker_doc = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE,
                "hub_id": hub_id,
                "policy_id": policy_id,
                "blockers": blockers,
                "summary": _blocker_summary(blockers),
                "source": {"control_results_hash": results_doc.get("integrity_hash")},
            }
            blocker_doc["integrity_hash"] = control_hash(blocker_doc)
            manual_actions = _manual_actions_from_blockers(blockers)
            actions_doc = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE,
                "hub_id": hub_id,
                "policy_id": policy_id,
                "actions": manual_actions,
                "summary": {"manual_required_count": len(manual_actions), "safe_action_count": 0},
                "source": {"blocker_summary_hash": blocker_doc.get("integrity_hash")},
            }
            actions_doc["integrity_hash"] = control_hash(actions_doc)
            bindings_doc = self._evidence_bindings_doc(hub_id, policy_id, source)
            assessment_id = _safe_id(str(payload.get("assessment_id") or _next_id(self.assessments_dir(hub_id), "toc-assess")))
            status = "passed" if not blockers else "failed"
            report: ImplementationDocument = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE,
                "hub_id": hub_id,
                "policy_id": policy_id,
                "assessment_id": assessment_id,
                "generated_at": now,
                "status": status,
                "readiness": "ready" if status == "passed" else "blocked",
                "source": {
                    **source,
                    "catalog_hash": catalog.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "control_results_hash": results_doc.get("integrity_hash"),
                    "evidence_bindings_hash": bindings_doc.get("integrity_hash"),
                    "blocker_summary_hash": blocker_doc.get("integrity_hash"),
                    "manual_actions_hash": actions_doc.get("integrity_hash"),
                },
                "summary": {
                    **_as_document(results_doc.get("summary")),
                    "blocker_count": len(blockers),
                    "manual_action_count": len(manual_actions),
                },
            }
            report["integrity_hash"] = control_hash(report)
            _write_json(self.assessment_path(hub_id, assessment_id), report)
            _write_json(self.control_results_path(hub_id, assessment_id), results_doc)
            _write_json(self.evidence_bindings_path(hub_id, assessment_id), bindings_doc)
            _write_json(self.blocker_summary_path(hub_id, assessment_id), blocker_doc)
            _write_json(self.manual_actions_path(hub_id, assessment_id), actions_doc)
            return _sanitize({"assessment": report, "control_results": results_doc, "evidence_bindings": bindings_doc, "blocker_summary": blocker_doc, "manual_actions": actions_doc})

    def read_assessment(self, hub_id: str, assessment_id: str) -> dict[str, Any]:
        path = self.assessment_path(hub_id, assessment_id)
        if not path.exists():
            raise TrustOperationsControlNotFoundError("Trust Operations Control Assessment not found.")
        return _read_json(path)

    def export_controls(self, hub_id: str, assessment_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            catalog = self.read_catalog(hub_id)
            assessment = self.read_assessment(hub_id, assessment_id)
            policy = self.read_policy(hub_id, str(assessment.get("policy_id") or ""))
            results = _read_required(self.control_results_path(hub_id, assessment_id))
            bindings = _read_required(self.evidence_bindings_path(hub_id, assessment_id))
            blockers = _read_required(self.blocker_summary_path(hub_id, assessment_id))
            actions = _read_required(self.manual_actions_path(hub_id, assessment_id))
            if assessment.get("source", {}).get("catalog_hash") != catalog.get("integrity_hash") or assessment.get("source", {}).get("policy_hash") != policy.get("integrity_hash"):
                raise TrustOperationsControlStateError("Trust Operations Control Assessment is stale.")
            export_dir = self.export_dir(hub_id, assessment_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            _write_json(export_dir / "control-catalog.json", catalog)
            _write_json(export_dir / "policy-bundle.json", policy)
            _write_json(export_dir / "control-assessment-report.json", assessment)
            _write_json(export_dir / "control-results.json", results)
            _write_json(export_dir / "evidence-bindings.json", bindings)
            _write_json(export_dir / "blocker-summary.json", blockers)
            _write_json(export_dir / "manual-actions.json", actions)
            _write_readme(export_dir)
            manifest = {
                "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Controls", "version": __version__},
                "hub_id": hub_id,
                "assessment_id": assessment_id,
                "generated_at": now,
                "status": assessment.get("status"),
                "source": {
                    "catalog_hash": catalog.get("integrity_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "assessment_hash": assessment.get("integrity_hash"),
                    "control_results_hash": results.get("integrity_hash"),
                    "evidence_bindings_hash": bindings.get("integrity_hash"),
                    "blocker_summary_hash": blockers.get("integrity_hash"),
                    "manual_actions_hash": actions.get("integrity_hash"),
                },
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-controls-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = control_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-controls-manifest.json", manifest)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, assessment_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            export_dir = self.export_dir(hub_id, assessment_id)
            manifest_path = export_dir / "trust-operations-controls-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsControlStateError("Trust Operations Control export is missing.")
            assessment = self.read_assessment(hub_id, assessment_id)
            if manifest.get("source", {}).get("assessment_hash") != assessment.get("integrity_hash"):
                raise TrustOperationsControlStateError("Trust Operations Control export is stale.")
            zip_path = self.zip_path(hub_id, assessment_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = control_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            return {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest.get("integrity_hash"), "assessment_id": assessment_id}

    def verify_zip(self, hub_id: str, assessment_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.trust_operations_controls_verifier import verify_trust_operations_control_package

        payload = payload or {}
        report = verify_trust_operations_control_package(
            self.zip_path(hub_id, assessment_id),
            strict=bool(payload.get("strict", False)),
            require_policy_passed=bool(payload.get("require_policy_passed", False)),
            hub_package_path=payload.get("hub_package_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
            incident_board_package_path=payload.get("incident_board_package_path"),
            incident_board_verification_report_path=payload.get("incident_board_verification_report_path"),
            incident_knowledge_package_path=payload.get("incident_knowledge_package_path"),
            incident_knowledge_verification_report_path=payload.get("incident_knowledge_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id, assessment_id), report)
        return report

    def _catalog_source(self, hub_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        hub_report = _read_json_default(_as_path(payload.get("hub_verification_report_path")) if payload.get("hub_verification_report_path") else _current_hub_verification_path(self.hub_store, hub_id), default={})
        incident_report = _read_json_default(_as_path(payload.get("incident_board_verification_report_path")) if payload.get("incident_board_verification_report_path") else self.incident_store.verification_report_path(hub_id), default={})
        knowledge_report = _read_json_default(_as_path(payload.get("incident_knowledge_verification_report_path")) if payload.get("incident_knowledge_verification_report_path") else self.knowledge_store.verification_report_path(hub_id), default={})
        source = {
            "hub_id": hub_id,
            "hub_verification_status": hub_report.get("status"),
            "hub_verification_report_hash": verification_hash(hub_report) if hub_report else None,
            "hub_zip_sha256": hub_report.get("zip_sha256"),
            "hub_manifest_hash": hub_report.get("manifest_hash"),
            "incident_verification_status": incident_report.get("status"),
            "incident_verification_report_hash": verification_hash(incident_report) if incident_report else None,
            "incident_zip_sha256": incident_report.get("zip_sha256"),
            "incident_manifest_hash": incident_report.get("manifest_hash"),
            "knowledge_verification_status": knowledge_report.get("status"),
            "knowledge_verification_report_hash": verification_hash(knowledge_report) if knowledge_report else None,
            "knowledge_zip_sha256": knowledge_report.get("zip_sha256"),
            "knowledge_manifest_hash": knowledge_report.get("manifest_hash"),
        }
        source["source_hash"] = stable_hash(source)
        return source

    def _assessment_source(self, hub_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        paths: dict[str, Any] = {
            "hub_package_path": _optional_path(payload.get("hub_package_path")),
            "hub_verification_report_path": _optional_path(payload.get("hub_verification_report_path") or _current_hub_verification_path(self.hub_store, hub_id)),
            "incident_board_package_path": _optional_path(payload.get("incident_board_package_path") or self.incident_store.zip_path(hub_id)),
            "incident_board_verification_report_path": _optional_path(payload.get("incident_board_verification_report_path") or self.incident_store.verification_report_path(hub_id)),
            "incident_knowledge_package_path": _optional_path(payload.get("incident_knowledge_package_path") or self.knowledge_store.zip_path(hub_id)),
            "incident_knowledge_verification_report_path": _optional_path(payload.get("incident_knowledge_verification_report_path") or self.knowledge_store.verification_report_path(hub_id)),
        }
        if not paths["hub_package_path"]:
            current = _read_json_default(self.hub_store.current_report_path(hub_id), default={})
            report_id = str(current.get("report_id") or "")
            if report_id:
                paths["hub_package_path"] = self.hub_store.zip_path(hub_id, report_id)
        reports = {
            "hub": _read_json_default(Path(paths["hub_verification_report_path"]) if paths["hub_verification_report_path"] else Path(), default={}),
            "incident": _read_json_default(Path(paths["incident_board_verification_report_path"]) if paths["incident_board_verification_report_path"] else Path(), default={}),
            "knowledge": _read_json_default(Path(paths["incident_knowledge_verification_report_path"]) if paths["incident_knowledge_verification_report_path"] else Path(), default={}),
        }
        source: dict[str, Any] = {"hub_id": hub_id}
        for key, path_value in paths.items():
            source[key] = str(Path(path_value).name) if path_value else None
        for key, report in reports.items():
            source[f"{key}_verification_status"] = report.get("status")
            source[f"{key}_verification_report_hash"] = verification_hash(report) if report else None
            source[f"{key}_zip_sha256"] = report.get("zip_sha256")
            source[f"{key}_zip_size_bytes"] = report.get("zip_size_bytes")
            source[f"{key}_manifest_hash"] = report.get("manifest_hash")
            source[f"{key}_source_hash"] = report.get("source_hash")
            source[f"{key}_summary"] = _as_document(report.get("summary"))
        source["source_hash"] = stable_hash(source)
        return source

    def _baseline_control(self, hub_id: str, spec: dict[str, str], source: ImplementationDocument, now: str, existing: ImplementationDocument) -> ImplementationDocument:
        existing_control = _existing_control(existing, spec["control_id"])
        control = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_control",
            "hub_id": hub_id,
            "control_id": spec["control_id"],
            "status": "active",
            "title": spec["title"],
            "category": spec["category"],
            "severity": spec["severity"],
            "scope": {"component_type": "trust_operations", "component_id": hub_id},
            "source": {"source_type": "baseline", "source_hash": source.get("source_hash")},
            "required_evidence": ["hub_verification", "incident_board_verification", "incident_knowledge_verification"],
            "evaluation": {"method": spec["evaluation_method"], "expected_status": "passed"},
            "recommended_manual_action": "Review and refresh the relevant trust operations evidence.",
            "created_at": existing_control.get("created_at") or now,
            "updated_at": now,
        }
        control["source_hash"] = stable_hash(control["source"])
        control["integrity_hash"] = control_hash(control)
        return control

    def _derived_control(self, hub_id: str, entry: ImplementationDocument, guards: list[ImplementationDocument], source: ImplementationDocument, now: str, existing: ImplementationDocument) -> ImplementationDocument:
        control_id = "toc-derived-" + _safe_id(str(entry.get("entry_id") or "knowledge-entry"))
        existing_control = _existing_control(existing, control_id)
        guard = next((item for item in guards if item.get("source", {}).get("knowledge_entry_hash") == entry.get("integrity_hash") and item.get("status") not in {"archived", "manual_required"}), {})
        recommended = _as_document(entry.get("recommended_guard"))
        control = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_control",
            "hub_id": hub_id,
            "control_id": control_id,
            "status": "active",
            "title": sanitize_sensitive_text(str(recommended.get("title") or entry.get("title") or "Knowledge-derived control")[:200]),
            "category": str(entry.get("category") or "incident_knowledge"),
            "severity": str(entry.get("severity") or "medium"),
            "scope": {"component_type": entry.get("component_type"), "component_id": entry.get("component_id"), "failure_mode": entry.get("failure_mode")},
            "source": {
                "source_type": "knowledge_entry",
                "knowledge_entry_id": entry.get("entry_id"),
                "knowledge_entry_hash": entry.get("integrity_hash"),
                "incident_id": entry.get("incident_id"),
                "incident_hash": entry.get("source", {}).get("incident_hash"),
                "closeout_hash": entry.get("source", {}).get("closeout_hash"),
                "source_fingerprint": entry.get("source", {}).get("source_fingerprint"),
                "knowledge_verification_report_hash": source.get("knowledge_verification_report_hash"),
                "incident_verification_report_hash": source.get("incident_verification_report_hash"),
                "guard_id": guard.get("guard_id"),
                "guard_hash": guard.get("integrity_hash"),
                "recommended_guard_type": recommended.get("guard_type"),
            },
            "required_evidence": ["incident_knowledge_verification", "incident_board_verification", "regression_guard_run"],
            "evaluation": {"method": "knowledge_guard_coverage", "expected_status": "passed"},
            "recommended_manual_action": sanitize_sensitive_text(str(recommended.get("reason") or "Keep the regression guard active and passing.")[:500]),
            "created_at": existing_control.get("created_at") or now,
            "updated_at": now,
        }
        control["source_hash"] = stable_hash(control["source"])
        control["integrity_hash"] = control_hash(control)
        return control

    def _evidence_bindings_doc(self, hub_id: str, policy_id: str, source: ImplementationDocument) -> ImplementationDocument:
        bindings = []
        for kind in ("hub", "incident", "knowledge"):
            bindings.append(
                {
                    "binding_id": f"toc-binding-{kind}",
                    "evidence_type": f"{kind}_verification",
                    "status": source.get(f"{kind}_verification_status") or "missing",
                    "zip_sha256": source.get(f"{kind}_zip_sha256"),
                    "zip_size_bytes": source.get(f"{kind}_zip_size_bytes"),
                    "manifest_hash": source.get(f"{kind}_manifest_hash"),
                    "source_hash": source.get(f"{kind}_source_hash"),
                    "verification_report_hash": source.get(f"{kind}_verification_report_hash"),
                }
            )
        doc = {
            "schema_version": TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE,
            "hub_id": hub_id,
            "policy_id": policy_id,
            "bindings": bindings,
            "summary": {"binding_count": len(bindings), "passed_count": sum(1 for item in bindings if item.get("status") == "passed")},
            "source": {"assessment_source_hash": source.get("source_hash")},
        }
        doc["integrity_hash"] = control_hash(doc)
        return doc





























def _existing_control(catalog: ImplementationDocument, control_id: str) -> ImplementationDocument:
    for control in catalog.get("controls", []) if isinstance(catalog.get("controls"), list) else []:
        if isinstance(control, dict) and control.get("control_id") == control_id:
            return control
    return {}


def _current_hub_verification_path(store: TrustOperationsHubStore, hub_id: str) -> Path:
    current = _read_json_default(store.current_report_path(hub_id), default={})
    report_id = str(current.get("report_id") or "")
    return store.verification_report_path(hub_id, report_id) if report_id else Path()


def _optional_path(value: Any) -> str | None:
    if not value:
        return None
    return str(Path(value))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()





def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _read_required(path: Path) -> ImplementationDocument:
    if not path.exists():
        raise TrustOperationsControlNotFoundError(f"Trust Operations Control artifact missing: {path.name}")
    return _read_json(path)


def _read_json(path: Path) -> ImplementationDocument:
    return read_json(path)


def _read_json_default(path: Path, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        if not path or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, _sanitize(payload))


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text("MusicForge Trust Operations Controls\n\nThis package contains local preventive control catalog and assessment evidence.\n", encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_CONTROL_BLOCKED_KEYS)


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
