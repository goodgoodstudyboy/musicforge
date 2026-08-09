from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list, _list_or

import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, TrustOperationsHubStore as TrustOperationsHubStore, hub_hash as hub_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import INCIDENT_EXPORT_ENTRIES as INCIDENT_EXPORT_ENTRIES, TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION as TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash




TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_report"


TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
EVIDENCE_PACKAGE_TYPES = {
    "release_verification": "musicforge_release_verification",
    "distribution_verification": "musicforge_distribution_verification",
    "submission_verification": "musicforge_submission_verification",
    "submission_evidence_verification": "musicforge_submission_evidence_verification",
    "release_operations_verification": "musicforge_release_operations_verification",
    "publication_monitoring_verification": "musicforge_public_trust_center_publication_monitoring_verification",
}



BLOCKING_STATUSES = {"open", "triaged", "in_progress", "waiting_verification", "verified"}
SAFE_REMEDIATION_ACTIONS = {
    "refresh_hub_report",
    "export_hub",
    "zip_hub",
    "verify_hub",
    "create_hub_runbook",
    "run_hub_safe_actions",
    "verify_release_package",
    "verify_distribution_package",
    "verify_submission_package",
    "verify_submission_evidence_package",
    "verify_release_operations_package",
    "manual_required",
}
FORBIDDEN_REMEDIATION_ACTIONS = {
    "signoff",
    "reset_signoff",
    "approve_change_request",
    "submit",
    "mark_accepted",
    "provider_call",
    "upload_file",
    "manual_review",
    "delete_artifact",
    "force_close",
}


class TrustOperationsIncidentError(ValueError):
    pass


class TrustOperationsIncidentNotFoundError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStateError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-incidents",
        *,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.lock = threading.RLock()

    def hub_dir(self, hub_id: str) -> Path:
        return self.root / _safe_id(hub_id)

    def board_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-board.json"

    def board_events_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-board-events.jsonl"

    def source_snapshot_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incident-source-snapshot.json"

    def incidents_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "incidents"

    def incident_dir(self, hub_id: str, incident_id: str) -> Path:
        return self.incidents_dir(hub_id) / _safe_id(incident_id)

    def incident_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "incident.json"

    def incident_events_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "incident-events.jsonl"

    def plan_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "remediation-plan.json"

    def result_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "remediation-result.json"

    def evidence_dir(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "evidence"

    def evidence_index_path(self, hub_id: str, incident_id: str) -> Path:
        return self.evidence_dir(hub_id, incident_id) / "evidence-index.json"

    def evidence_path(self, hub_id: str, incident_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(hub_id, incident_id) / (_safe_id(evidence_id) + ".json")

    def closeout_path(self, hub_id: str, incident_id: str) -> Path:
        return self.incident_dir(hub_id, incident_id) / "closeout-report.json"

    def export_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "exports" / "current"

    def zip_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-board.zip"

    def verification_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-verification-report.json"

    def refresh_board(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            report_id = str(payload.get("report_id") or self._current_report_id(hub_id) or "")
            if not report_id:
                raise TrustOperationsIncidentStateError("Trust Operations Hub report is required.")
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
            self.hub_store._assert_external_sources_current(docs, self.hub_store._read_source_paths(hub_id, report_id))
            source = self._source_summary(hub_id, report_id, docs)
            existing_board = _read_json_default(self.board_path(hub_id), default={})
            existing = {
                str(item.get("detected_from", {}).get("source_fingerprint") or ""): item
                for item in self.list_incidents(hub_id, include_archived=True)
            }
            current_fingerprints: set[str] = set()
            created_count = 0
            updated_count = 0
            stale_count = 0
            incident_ids: list[str] = []
            for candidate in self._incident_candidates(hub_id, report_id, source, docs, now):
                fingerprint = str(candidate["detected_from"]["source_fingerprint"])
                current_fingerprints.add(fingerprint)
                if fingerprint in existing and existing[fingerprint].get("status") != "closed":
                    incident = existing[fingerprint]
                    incident.update(
                        {
                            "title": candidate["title"],
                            "description": candidate["description"],
                            "severity": candidate["severity"],
                            "blocking": candidate["blocking"],
                            "last_seen_at": now,
                            "source_resolved": False,
                            "stale": False,
                            "updated_at": now,
                            "detected_from": candidate["detected_from"],
                        }
                    )
                    updated_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_refreshed", now=now)
                else:
                    incident_id = _next_id(self.incidents_dir(hub_id), "inc")
                    incident = {
                        "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                        "hub_id": hub_id,
                        "incident_id": incident_id,
                        "title": candidate["title"],
                        "description": candidate["description"],
                        "category": candidate["category"],
                        "severity": candidate["severity"],
                        "blocking": candidate["blocking"],
                        "status": "open",
                        "created_at": now,
                        "updated_at": now,
                        "last_seen_at": now,
                        "source_resolved": False,
                        "detected_from": candidate["detected_from"],
                        "triage": {"status": "untriaged", "owner": None, "notes": "", "triaged_at": None},
                        "remediation_plan_id": None,
                        "closeout_report_id": None,
                        "stale": False,
                    }
                    created_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_created", now=now)
                incident_ids.append(str(incident["incident_id"]))
            for incident in self.list_incidents(hub_id, include_archived=True):
                if incident.get("status") in {"closed", "archived"}:
                    incident_ids.append(str(incident.get("incident_id") or ""))
                    continue
                fingerprint = str(incident.get("detected_from", {}).get("source_fingerprint") or "")
                if fingerprint and fingerprint not in current_fingerprints:
                    incident["source_resolved"] = True
                    incident["stale"] = False
                    incident["updated_at"] = now
                    updated_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_source_resolved", now=now)
                elif str(incident.get("detected_from", {}).get("hub_report_hash") or "") != str(source.get("hub_report_hash") or ""):
                    incident["stale"] = True
                    incident["updated_at"] = now
                    stale_count += 1
                    self._write_incident(hub_id, incident, event_type="incident_marked_stale", now=now)
                incident_ids.append(str(incident.get("incident_id") or ""))
            board_id = str(existing_board.get("board_id") or "tohi-board-000001")
            board: ImplementationDocument = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE,
                "hub_id": hub_id,
                "board_id": board_id,
                "status": "open",
                "created_at": existing_board.get("created_at") or now,
                "updated_at": now,
                "source": source,
                "incident_ids": sorted(set(item for item in incident_ids if item)),
            }
            board["summary"] = _board_summary(self.list_incidents(hub_id, include_archived=False))
            board_summary = _as_document(board.get("summary"))
            if board_summary.get("open_count") == 0 and board_summary.get("stale_count") == 0:
                board["status"] = "ready_for_closeout"
            board["integrity_hash"] = incident_hash(board)
            _write_json(self.board_path(hub_id), board)
            _write_json(self.source_snapshot_path(hub_id), source)
            self._append_board_event(hub_id, "incident_board_refreshed", {"board_hash": board["integrity_hash"], "created_count": created_count, "updated_count": updated_count}, now=now)
            return _sanitize({"incident_board": board, "created_count": created_count, "updated_count": updated_count, "stale_count": stale_count, "incidents": self.list_incidents(hub_id)})

    def read_board(self, hub_id: str) -> dict[str, Any]:
        if not self.board_path(hub_id).exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident Board not found.")
        return _read_json(self.board_path(hub_id))

    def list_incidents(self, hub_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
        root = self.incidents_dir(hub_id)
        if not root.exists():
            return []
        rows = []
        for path in sorted(root.glob("*/incident.json")):
            incident = _read_json(path)
            if incident.get("status") == "archived" and not include_archived:
                continue
            rows.append(_sanitize(incident))
        return rows

    def read_incident(self, hub_id: str, incident_id: str) -> dict[str, Any]:
        path = self.incident_path(hub_id, incident_id)
        if not path.exists():
            raise TrustOperationsIncidentNotFoundError("Trust Operations Incident not found.")
        return _read_json(path)

    def triage_incident(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            severity = str(payload.get("severity") or incident.get("severity") or "medium")
            if severity not in {"critical", "high", "medium", "low", "info"}:
                raise TrustOperationsIncidentStateError("Invalid incident severity.")
            incident["severity"] = severity
            incident["blocking"] = bool(payload.get("blocking", incident.get("blocking", False)))
            incident["status"] = "triaged" if incident.get("status") == "open" else incident.get("status")
            incident["triage"] = {
                "status": "triaged",
                "owner": sanitize_sensitive_text(str(payload.get("owner") or "local-user")[:120]),
                "notes": sanitize_sensitive_text(str(payload.get("notes") or "")[:1000]),
                "triaged_at": now,
            }
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_triaged", now=now)
            return _sanitize(incident)

    def create_plan(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            plan_id = _safe_id(str(payload.get("plan_id") or "rp-000001"))
            steps = _list_or(payload.get("steps"), _default_plan_steps(incident))
            normalized = []
            for index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                action_type = str(step.get("action_type") or "manual_required")
                if action_type in FORBIDDEN_REMEDIATION_ACTIONS or action_type not in SAFE_REMEDIATION_ACTIONS:
                    raise TrustOperationsIncidentStateError("Unsafe remediation action is not allowed.")
                normalized.append(
                    {
                        "step_id": str(step.get("step_id") or f"step-{index:03d}"),
                        "action_type": action_type,
                        "title": sanitize_sensitive_text(str(step.get("title") or action_type)[:200]),
                        "component_type": step.get("component_type") or incident.get("detected_from", {}).get("component_type"),
                        "component_id": step.get("component_id") or incident.get("detected_from", {}).get("component_id"),
                        "safe_auto": action_type != "manual_required",
                        "status": "pending",
                    }
                )
            plan = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "hub_id": hub_id,
                "incident_id": incident_id,
                "plan_id": plan_id,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "source_hash": incident.get("integrity_hash"),
                "steps": normalized,
            }
            plan["integrity_hash"] = incident_hash(plan)
            _write_json(self.plan_path(hub_id, incident_id), plan)
            incident["remediation_plan_id"] = plan_id
            if incident.get("status") in {"open", "triaged"}:
                incident["status"] = "in_progress"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_plan_created", now=now)
            return _sanitize(plan)

    def add_evidence(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if any(key in payload for key in ("source_path", "local_path", "file_path")):
                raise TrustOperationsIncidentStateError("Evidence import does not accept source_path/local_path/file_path.")
            incident = self._mutable_incident(hub_id, incident_id)
            report = payload.get("report") if isinstance(payload.get("report"), dict) else None
            if report is None and payload.get("content_base64"):
                try:
                    raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
                    report = json.loads(raw.decode("utf-8"))
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise TrustOperationsIncidentStateError(f"Evidence content is not valid JSON: {exc}") from exc
            if report is None and isinstance(payload.get("content"), dict):
                report = payload["content"]
            if report is None:
                raise TrustOperationsIncidentStateError("Evidence JSON content is required.")
            if _contains_sensitive_value(report):
                raise TrustOperationsIncidentStateError("Evidence contains sensitive or local-path content.")
            component_type = str(payload.get("component_type") or incident.get("detected_from", {}).get("component_type") or "")
            component_id = str(payload.get("component_id") or incident.get("detected_from", {}).get("component_id") or "")
            binding = self._bind_evidence_to_hub(hub_id, incident, report, component_type, component_id)
            if binding.get("binding_status") != "passed":
                raise TrustOperationsIncidentStateError("Evidence does not match current Trust Operations Hub verification evidence.")
            evidence_id = _safe_id(str(payload.get("evidence_id") or _next_id(self.evidence_dir(hub_id, incident_id), "ev")))
            evidence = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "evidence_id": evidence_id,
                "incident_id": incident_id,
                "kind": str(payload.get("kind") or "external_verification_report"),
                "component_type": binding.get("component_type") or component_type,
                "component_id": binding.get("component_id") or component_id,
                "requested_component_id": component_id,
                "incident_component_id": incident.get("detected_from", {}).get("component_id"),
                "status": report.get("status") or "missing",
                "package_type": report.get("package_type"),
                "payload_hash": stable_hash(report),
                "verification_report_hash": verification_hash(report),
                "zip_sha256": report.get("zip_sha256"),
                "zip_size_bytes": report.get("zip_size_bytes"),
                "manifest_hash": report.get("manifest_hash"),
                "source_hash": report.get("source_hash"),
                "binding_status": binding.get("binding_status"),
                "binding_checks": binding.get("binding_checks") or [],
                "expected_evidence_id": binding.get("expected_evidence_id"),
                "expected_component_id": binding.get("expected_component_id"),
                "expected_component_type": binding.get("expected_component_type"),
                "expected_package_type": binding.get("expected_package_type"),
                "expected_verification_report_hash": binding.get("expected_verification_report_hash"),
                "expected_zip_sha256": binding.get("expected_zip_sha256"),
                "expected_zip_size_bytes": binding.get("expected_zip_size_bytes"),
                "expected_manifest_hash": binding.get("expected_manifest_hash"),
                "expected_source_hash": binding.get("expected_source_hash"),
                "expected_status": binding.get("expected_status"),
                "created_at": now,
                "redaction_status": "passed",
                "summary": _as_document(report.get("summary")),
            }
            evidence["integrity_hash"] = incident_hash(evidence)
            _write_json(self.evidence_path(hub_id, incident_id, evidence_id), evidence)
            self._write_evidence_index(hub_id, incident_id)
            if incident.get("status") in {"open", "triaged", "in_progress"}:
                incident["status"] = "waiting_verification"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_evidence_added", now=now)
            return _sanitize(evidence)

    def verify_fix(self, hub_id: str, incident_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            incident = self._mutable_incident(hub_id, incident_id)
            evidence_index = self._read_evidence_index(hub_id, incident_id)
            current = self._incident_source_current(hub_id, incident)
            passed_evidence = _valid_passed_evidence_for_incident(evidence_index, incident)
            result = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "hub_id": hub_id,
                "incident_id": incident_id,
                "verified_at": now,
                "status": "passed" if current and passed_evidence else "failed",
                "source": {"incident_hash": incident.get("integrity_hash"), "evidence_index_hash": evidence_index.get("integrity_hash")},
                "checks": [
                    {"check_id": "incident_source_current", "status": "passed" if current else "failed", "severity": "blocking"},
                    {"check_id": "required_external_verification_present", "status": "passed" if passed_evidence else "failed", "severity": "blocking"},
                ],
            }
            result["integrity_hash"] = incident_hash(result)
            _write_json(self.result_path(hub_id, incident_id), result)
            if result["status"] == "passed":
                incident["status"] = "verified"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_fix_verified", now=now)
            return _sanitize(result)

    def close_incident(self, hub_id: str, incident_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            incident = self._mutable_incident(hub_id, incident_id)
            if incident.get("stale"):
                raise TrustOperationsIncidentStateError("Stale Trust Operations Incident cannot be closed.")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsIncidentStateError("Closeout reason must be at least 8 characters.")
            result = _read_json_default(self.result_path(hub_id, incident_id), default={})
            if incident.get("blocking") or incident.get("severity") in {"critical", "high"}:
                if result.get("status") != "passed":
                    result = self.verify_fix(hub_id, incident_id, now=now)
                if result.get("status") != "passed":
                    raise TrustOperationsIncidentStateError("Blocking/high incident requires passed fix verification before closeout.")
            evidence_index = self._read_evidence_index(hub_id, incident_id)
            source = self._current_source_for_closeout(hub_id, incident)
            checks = [
                {"check_id": "incident_source_current", "status": "passed" if self._incident_source_current(hub_id, incident) else "failed", "severity": "blocking"},
                {"check_id": "required_external_verification_present", "status": "passed" if _valid_passed_evidence_for_incident(evidence_index, incident) else "failed", "severity": "blocking"},
            ]
            if any(item["status"] == "failed" for item in checks):
                raise TrustOperationsIncidentStateError("Incident closeout checks failed.")
            closeout = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "closeout_id": "closeout-000001",
                "incident_id": incident_id,
                "status": "passed",
                "closed_by": sanitize_sensitive_text(str(payload.get("closed_by") or "local-user")[:120]),
                "closed_at": now,
                "reason": reason[:500],
                "source": {
                    "incident_hash": incident.get("integrity_hash"),
                    "remediation_plan_hash": _read_json_default(self.plan_path(hub_id, incident_id), default={}).get("integrity_hash"),
                    "evidence_index_hash": evidence_index.get("integrity_hash"),
                    **source,
                },
                "checks": checks,
            }
            closeout["integrity_hash"] = incident_hash(closeout)
            _write_json(self.closeout_path(hub_id, incident_id), closeout)
            incident["status"] = "closed"
            incident["closeout_report_id"] = closeout["closeout_id"]
            incident["closed_at"] = now
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_closed", now=now)
            self._refresh_board_summary(hub_id, now=now)
            return _sanitize(closeout)

    def archive_incident(self, hub_id: str, incident_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            incident = self.read_incident(hub_id, incident_id)
            if incident.get("status") != "closed":
                raise TrustOperationsIncidentStateError("Only closed incidents can be archived.")
            incident["status"] = "archived"
            incident["updated_at"] = now
            self._write_incident(hub_id, incident, event_type="incident_archived", now=now)
            self._refresh_board_summary(hub_id, now=now)
            return _sanitize(incident)

    def export_board(self, hub_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            board = self.read_board(hub_id)
            if board.get("integrity_hash") != incident_hash(board):
                raise TrustOperationsIncidentStateError("Incident Board integrity failed.")
            source = _read_json_default(self.source_snapshot_path(hub_id), default={})
            incidents = self.list_incidents(hub_id, include_archived=True)
            export_dir = self.export_dir(hub_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            events = self._export_events(hub_id)
            plans = self._all_docs(hub_id, "remediation-plan.json")
            results = self._all_docs(hub_id, "remediation-result.json")
            evidence_index = self._aggregate_evidence(hub_id)
            closeout_summary = self._closeout_summary(hub_id)
            report = self._board_report(board, incidents, source, events, evidence_index, closeout_summary, now)
            _write_json(export_dir / "incident-board.json", board)
            _write_json(export_dir / "incident-board-report.json", report)
            _write_json(export_dir / "incident-source-summary.json", source)
            incidents_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incidents": incidents}
            incidents_doc["integrity_hash"] = incident_hash(incidents_doc)
            _write_json(export_dir / "incidents.json", incidents_doc)
            (export_dir / "incident-events.jsonl").write_text("\n".join(json.dumps(_sanitize(event), ensure_ascii=False, sort_keys=True) for event in events) + ("\n" if events else ""), encoding="utf-8")
            plans_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "plans": plans}
            plans_doc["integrity_hash"] = incident_hash(plans_doc)
            results_doc = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "results": results}
            results_doc["integrity_hash"] = incident_hash(results_doc)
            _write_json(export_dir / "remediation-plans.json", plans_doc)
            _write_json(export_dir / "remediation-results.json", results_doc)
            _write_json(export_dir / "evidence-index.json", evidence_index)
            _write_json(export_dir / "closeout-summary.json", closeout_summary)
            _write_readme(export_dir)
            manifest = {
                "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Incident Board", "version": __version__},
                "hub_id": hub_id,
                "board_id": board.get("board_id"),
                "generated_at": now,
                "source_hash": source.get("source_hash"),
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-incident-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "integrity": {
                    "board_hash": board.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "incident_events_hash": stable_hash(events),
                    "evidence_index_hash": evidence_index.get("integrity_hash"),
                    "closeout_summary_hash": closeout_summary.get("integrity_hash"),
                },
            }
            manifest["integrity_hash"] = incident_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-incident-manifest.json", manifest)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            export_dir = self.export_dir(hub_id)
            manifest_path = export_dir / "trust-operations-incident-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsIncidentStateError("Trust Operations Incident export is missing.")
            board = self.read_board(hub_id)
            if manifest.get("integrity", {}).get("board_hash") != board.get("integrity_hash"):
                raise TrustOperationsIncidentStateError("Trust Operations Incident export is stale.")
            zip_path = self.zip_path(hub_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = incident_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            return {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "hub_id": hub_id}

    def verify_zip(self, hub_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.trust_operations_hub_incident_verifier import verify_trust_operations_hub_incident_package

        payload = payload or {}
        report = verify_trust_operations_hub_incident_package(
            self.zip_path(hub_id),
            strict=bool(payload.get("strict", False)),
            require_no_open_critical=bool(payload.get("require_no_open_critical", False)),
            require_no_open_blocking=bool(payload.get("require_no_open_blocking", False)),
            require_current_hub=bool(payload.get("require_current_hub", False)),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id), report)
        return report

    def _current_report_id(self, hub_id: str) -> str:
        current = _read_json_default(self.hub_store.current_report_path(hub_id), default={})
        return str(current.get("report_id") or "")

    def _source_summary(self, hub_id: str, report_id: str, docs: dict[str, ImplementationDocument]) -> ImplementationDocument:
        export_manifest = _read_json_default(self.hub_store.export_dir(hub_id, report_id) / "trust-operations-hub-manifest.json", default={})
        zip_path = self.hub_store.zip_path(hub_id, report_id)
        verification = _read_json_default(self.hub_store.verification_report_path(hub_id, report_id), default={})
        source = {
            "hub_id": hub_id,
            "hub_report_id": report_id,
            "hub_report_hash": docs["hub_report"].get("integrity_hash"),
            "hub_manifest_hash": export_manifest.get("integrity_hash"),
            "hub_zip_sha256": _sha256(zip_path) if zip_path.exists() else None,
            "hub_zip_size_bytes": os.stat(_fs_path(zip_path)).st_size if zip_path.exists() else None,
            "hub_verification_report_hash": verification_hash(verification) if verification else None,
            "hub_verification_status": verification.get("status") if verification else None,
            "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
            "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
            "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
            "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
            "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
        }
        source["source_hash"] = stable_hash(source)
        return source

    def _incident_candidates(self, hub_id: str, report_id: str, source: ImplementationDocument, docs: dict[str, ImplementationDocument], now: str) -> list[ImplementationDocument]:
        del now
        rows: list[dict[str, Any]] = []
        for source_type, register_key in (("trust_operations_hub", "blocker_register"), ("trust_operations_hub_delivery", "delivery_blocker_register")):
            for blocker in docs[register_key].get("blockers", []) if isinstance(docs[register_key].get("blockers"), list) else []:
                if not isinstance(blocker, dict):
                    continue
                component_id = str(blocker.get("component_id") or "unknown")
                requirement = str(blocker.get("requirement") or "unknown")
                component_type = _component_type_from_component_id(component_id)
                check_id = str(blocker.get("source_check_id") or requirement)
                fingerprint_payload = {"source_type": source_type, "check_id": check_id, "component_type": component_type, "component_id": component_id, "requirement": requirement}
                fingerprint = stable_hash(fingerprint_payload)
                severity = str(blocker.get("severity") or "high")
                rows.append(
                    {
                        "title": sanitize_sensitive_text(str(blocker.get("message") or f"{component_id} {requirement} is blocked.")[:200]),
                        "description": sanitize_sensitive_text(str(blocker.get("message") or "")[:1000]),
                        "category": _category(requirement, source_type),
                        "severity": severity if severity in {"critical", "high", "medium", "low", "info"} else "high",
                        "blocking": True,
                        "detected_from": {
                            "source_type": source_type,
                            "check_id": check_id,
                            "component_type": component_type,
                            "component_id": component_id,
                            "requirement": requirement,
                            "source_hash": source.get("source_hash"),
                            "hub_report_hash": source.get("hub_report_hash"),
                            "hub_report_id": report_id,
                            "source_fingerprint": fingerprint,
                        },
                    }
                )
        verification = _read_json_default(self.hub_store.verification_report_path(hub_id, report_id), default={})
        for blocker in verification.get("blockers", []) if isinstance(verification.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            check_id = str(blocker.get("check_id") or "hub_verification_blocker")
            component_type = _component_type_from_check_id(check_id)
            component_id = _component_id_from_check_id(component_type, check_id)
            fingerprint_payload = {"source_type": "trust_operations_hub_verifier", "check_id": check_id, "component_type": component_type, "component_id": component_id}
            fingerprint = stable_hash(fingerprint_payload)
            rows.append(
                {
                    "title": sanitize_sensitive_text(str(blocker.get("message") or check_id)[:200]),
                    "description": sanitize_sensitive_text(str(blocker.get("message") or "")[:1000]),
                    "category": "hub_verification_blocker",
                    "severity": "high",
                    "blocking": True,
                    "detected_from": {
                        "source_type": "trust_operations_hub_verifier",
                        "check_id": check_id,
                        "component_type": component_type,
                        "component_id": component_id,
                        "requirement": check_id,
                        "source_hash": source.get("source_hash"),
                        "hub_report_hash": source.get("hub_report_hash"),
                        "hub_report_id": report_id,
                        "source_fingerprint": fingerprint,
                    },
                }
            )
        return rows

    def _write_incident(self, hub_id: str, incident: ImplementationDocument, *, event_type: str, now: str) -> None:
        incident["integrity_hash"] = incident_hash(incident)
        _write_json(self.incident_path(hub_id, str(incident["incident_id"])), incident)
        self._append_incident_event(hub_id, str(incident["incident_id"]), event_type, {"status": incident.get("status"), "incident_hash": incident["integrity_hash"]}, now=now)

    def _append_incident_event(self, hub_id: str, incident_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        rows = _read_jsonl(self.incident_events_path(hub_id, incident_id))
        event = {"incident_id": incident_id, "event_id": f"{incident_id}-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.incident_events_path(hub_id, incident_id), event)

    def _append_board_event(self, hub_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        rows = _read_jsonl(self.board_events_path(hub_id))
        event = {"event_id": f"tohi-board-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": _sanitize(payload), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        _append_jsonl(self.board_events_path(hub_id), event)

    def _mutable_incident(self, hub_id: str, incident_id: str) -> ImplementationDocument:
        incident = self.read_incident(hub_id, incident_id)
        if incident.get("status") in {"closed", "archived"}:
            raise TrustOperationsIncidentStateError("Closed or archived incidents are read-only.")
        if incident.get("integrity_hash") != incident_hash(incident):
            raise TrustOperationsIncidentStateError("Trust Operations Incident integrity failed.")
        return incident

    def _read_evidence_index(self, hub_id: str, incident_id: str) -> ImplementationDocument:
        return _read_json_default(self.evidence_index_path(hub_id, incident_id), default={"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": [], "summary": _evidence_summary({"evidence": []})})

    def _write_evidence_index(self, hub_id: str, incident_id: str) -> ImplementationDocument:
        rows = []
        for path in sorted(self.evidence_dir(hub_id, incident_id).glob("ev-*.json")):
            rows.append(_read_json(path))
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "incident_id": incident_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        _write_json(self.evidence_index_path(hub_id, incident_id), index)
        return index

    def _bind_evidence_to_hub(self, hub_id: str, incident: ImplementationDocument, report: ImplementationDocument, component_type: str, component_id: str) -> ImplementationDocument:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        if not report_id:
            return _failed_binding(component_type, component_id, "hub_report_id_missing")
        try:
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
        except Exception:
            return _failed_binding(component_type, component_id, "hub_report_not_current")
        rows = _expected_evidence_rows_for_component(docs, component_type)
        if not rows:
            return _failed_binding(component_type, component_id, "expected_evidence_missing")
        requested_component_id = str(component_id or "")
        generic_component = _is_generic_component_id(requested_component_id)
        best_binding: dict[str, Any] | None = None
        best_score = -1
        for row in rows:
            expected_component_id = str(row.get("component_id") or "")
            if requested_component_id and not generic_component and requested_component_id != expected_component_id:
                continue
            binding = _binding_for_expected_row(row, report)
            score = sum(1 for check in binding.get("binding_checks", []) if isinstance(check, dict) and check.get("status") == "passed")
            if score > best_score:
                best_binding = binding
                best_score = score
            if binding.get("binding_status") == "passed":
                return binding
        if best_binding is not None:
            return best_binding
        return _failed_binding(component_type, component_id, "component_id_not_expected")

    def _incident_source_current(self, hub_id: str, incident: ImplementationDocument) -> bool:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        if not report_id:
            return False
        try:
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
        except Exception:
            return False
        source = self._source_summary(hub_id, report_id, docs)
        return source.get("hub_report_hash") == incident.get("detected_from", {}).get("hub_report_hash")

    def _current_source_for_closeout(self, hub_id: str, incident: ImplementationDocument) -> ImplementationDocument:
        report_id = str(incident.get("detected_from", {}).get("hub_report_id") or "")
        docs = self.hub_store._read_report_docs(hub_id, report_id)
        return self._source_summary(hub_id, report_id, docs)

    def _refresh_board_summary(self, hub_id: str, *, now: str) -> None:
        board = self.read_board(hub_id)
        board["summary"] = _board_summary(self.list_incidents(hub_id, include_archived=False))
        board["status"] = "ready_for_closeout" if board["summary"]["open_count"] == 0 and board["summary"]["stale_count"] == 0 else "open"
        board["updated_at"] = now
        board["integrity_hash"] = incident_hash(board)
        _write_json(self.board_path(hub_id), board)

    def _export_events(self, hub_id: str) -> list[ImplementationDocument]:
        rows: list[dict[str, Any]] = []
        for incident in self.list_incidents(hub_id, include_archived=True):
            rows.extend(_read_jsonl(self.incident_events_path(hub_id, str(incident.get("incident_id") or ""))))
        return sorted(rows, key=lambda item: str(item.get("event_id") or ""))

    def _all_docs(self, hub_id: str, filename: str) -> list[ImplementationDocument]:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob(f"*/{filename}")):
            rows.append(_read_json(path))
        return rows

    def _aggregate_evidence(self, hub_id: str) -> ImplementationDocument:
        rows = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/evidence/evidence-index.json")):
            index = _read_json(path)
            rows.extend([item for item in index.get("evidence", []) if isinstance(item, dict)])
        index = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "evidence": rows, "summary": _evidence_summary({"evidence": rows})}
        index["integrity_hash"] = incident_hash(index)
        return index

    def _closeout_summary(self, hub_id: str) -> ImplementationDocument:
        closeouts = []
        for path in sorted(self.incidents_dir(hub_id).glob("*/closeout-report.json")):
            closeouts.append(_read_json(path))
        data = {"schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, "hub_id": hub_id, "closeouts": closeouts, "summary": {"closeout_count": len(closeouts), "passed_count": sum(1 for row in closeouts if row.get("status") == "passed"), "failed_count": sum(1 for row in closeouts if row.get("status") == "failed")}}
        data["integrity_hash"] = incident_hash(data)
        return data

    def _board_report(self, board: ImplementationDocument, incidents: list[ImplementationDocument], source: ImplementationDocument, events: list[ImplementationDocument], evidence_index: ImplementationDocument, closeout_summary: ImplementationDocument, now: str) -> ImplementationDocument:
        summary = _board_summary(incidents)
        report = {
            "schema_version": TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE,
            "hub_id": board.get("hub_id"),
            "board_id": board.get("board_id"),
            "generated_at": now,
            "status": "passed" if summary["open_count"] == 0 and summary["stale_count"] == 0 else "blocked",
            "summary": summary,
            "source": {
                "board_hash": board.get("integrity_hash"),
                "source_hash": source.get("source_hash"),
                "event_chain_hash": events[-1].get("event_hash") if events else None,
                "evidence_index_hash": evidence_index.get("integrity_hash"),
                "closeout_summary_hash": closeout_summary.get("integrity_hash"),
            },
        }
        report["integrity_hash"] = incident_hash(report)
        return report








def _default_plan_steps(incident: ImplementationDocument) -> list[ImplementationDocument]:
    component_type = str(incident.get("detected_from", {}).get("component_type") or "")
    action = {
        "release_verification": "verify_release_package",
        "distribution_verification": "verify_distribution_package",
        "submission_verification": "verify_submission_package",
        "submission_evidence_verification": "verify_submission_evidence_package",
        "release_operations_verification": "verify_release_operations_package",
    }.get(component_type, "manual_required")
    return [
        {"action_type": "manual_required", "title": "Review and repair the underlying Trust Operations blocker."},
        {"action_type": action, "title": f"Verify {component_type or 'component'} evidence."},
    ]


def _board_summary(incidents: list[ImplementationDocument]) -> ImplementationDocument:
    open_rows = [item for item in incidents if item.get("status") in BLOCKING_STATUSES]
    blocking_open = [item for item in open_rows if item.get("blocking")]
    critical = [item for item in open_rows if item.get("severity") == "critical"]
    high = [item for item in open_rows if item.get("severity") == "high"]
    stale = [item for item in incidents if item.get("stale")]
    return {
        "total_incidents": len(incidents),
        "open_count": len(open_rows),
        "closed_count": sum(1 for item in incidents if item.get("status") == "closed"),
        "critical_count": len(critical),
        "high_count": len(high),
        "blocking_open_count": len(blocking_open),
        "stale_count": len(stale),
        "ready_for_hub_signoff": len(open_rows) == 0 and len(stale) == 0,
    }


def _evidence_summary(index: ImplementationDocument) -> dict[str, int]:
    rows = _as_list(index.get("evidence"))
    return {
        "evidence_count": len(rows),
        "passed_count": sum(1 for row in rows if isinstance(row, dict) and _evidence_binding_valid(row) and row.get("status") == "passed"),
        "failed_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "failed"),
        "invalid_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "passed" and not _evidence_binding_valid(row)),
    }


def _expected_evidence_rows_for_component(docs: dict[str, ImplementationDocument], component_type: str) -> list[ImplementationDocument]:
    delivery_types = {str(spec.get("component_type") or "") for spec in DELIVERY_VERIFICATION_COMPONENTS}
    if component_type in delivery_types:
        source = _as_document(docs.get("delivery_evidence_index"))
    else:
        source = _as_document(docs.get("evidence_binding_index"))
    return [row for row in source.get("evidence", []) if isinstance(row, dict) and row.get("component_type") == component_type]


def _binding_for_expected_row(expected: ImplementationDocument, report: ImplementationDocument) -> ImplementationDocument:
    expected_component_id = str(expected.get("component_id") or expected.get("evidence_id") or expected.get("component_type") or "")
    expected_component_type = str(expected.get("component_type") or "")
    report_hash = verification_hash(report)
    checks = [
        _binding_check("known_package_type", report.get("package_type"), EVIDENCE_PACKAGE_TYPES.get(expected_component_type)) if EVIDENCE_PACKAGE_TYPES.get(expected_component_type) else {"name": "known_package_type", "status": "passed", "actual": report.get("package_type"), "expected": report.get("package_type")},
        _binding_check("package_type", report.get("package_type"), expected.get("package_type")),
        _binding_check("status", report.get("status") or "missing", expected.get("status") or "missing"),
        _binding_check("verification_report_hash", report_hash, expected.get("verification_report_hash")),
        _binding_check("zip_sha256", report.get("zip_sha256"), expected.get("zip_sha256")),
        _binding_check("manifest_hash", report.get("manifest_hash"), expected.get("manifest_hash")),
        _binding_check("source_hash", report.get("source_hash"), expected.get("source_hash")),
    ]
    if expected.get("zip_size_bytes") is not None or report.get("zip_size_bytes") is not None:
        checks.append(_binding_check("zip_size_bytes", report.get("zip_size_bytes"), expected.get("zip_size_bytes")))
    passed = all(check["status"] == "passed" for check in checks)
    return {
        "binding_status": "passed" if passed else "failed",
        "binding_checks": checks,
        "component_type": expected_component_type,
        "component_id": expected_component_id,
        "expected_evidence_id": expected.get("evidence_id"),
        "expected_component_id": expected_component_id,
        "expected_component_type": expected_component_type,
        "expected_package_type": expected.get("package_type"),
        "expected_verification_report_hash": expected.get("verification_report_hash"),
        "expected_zip_sha256": expected.get("zip_sha256"),
        "expected_zip_size_bytes": expected.get("zip_size_bytes"),
        "expected_manifest_hash": expected.get("manifest_hash"),
        "expected_source_hash": expected.get("source_hash"),
        "expected_status": expected.get("status"),
    }


def _binding_check(name: str, actual: Any, expected: Any) -> ImplementationDocument:
    return {"name": name, "status": "passed" if actual == expected else "failed", "actual": actual, "expected": expected}


def _failed_binding(component_type: str, component_id: str, reason: str) -> ImplementationDocument:
    return {
        "binding_status": "failed",
        "binding_checks": [{"name": reason, "status": "failed", "actual": component_id, "expected": component_type}],
        "component_type": component_type,
        "component_id": component_id,
    }


def _is_generic_component_id(component_id: str) -> bool:
    return component_id.endswith(":coverage") or component_id.endswith(":verification") or component_id.endswith(":missing")


def _evidence_binding_valid(evidence: ImplementationDocument) -> bool:
    if evidence.get("status") != "passed":
        return False
    if evidence.get("binding_status") != "passed":
        return False
    if evidence.get("package_type") != evidence.get("expected_package_type"):
        return False
    if evidence.get("component_type") != evidence.get("expected_component_type"):
        return False
    if evidence.get("component_id") != evidence.get("expected_component_id"):
        return False
    if evidence.get("verification_report_hash") != evidence.get("expected_verification_report_hash"):
        return False
    for key in ("zip_sha256", "zip_size_bytes", "manifest_hash", "source_hash"):
        expected_key = "expected_" + key
        if evidence.get(expected_key) is not None and evidence.get(key) != evidence.get(expected_key):
            return False
    checks = _as_list(evidence.get("binding_checks"))
    return bool(checks) and all(isinstance(check, dict) and check.get("status") == "passed" for check in checks)


def _valid_passed_evidence_for_incident(index: ImplementationDocument, incident: ImplementationDocument) -> list[ImplementationDocument]:
    detected = _as_document(incident.get("detected_from"))
    incident_component_type = str(detected.get("component_type") or "")
    incident_component_id = str(detected.get("component_id") or "")
    rows = []
    for row in index.get("evidence", []) if isinstance(index.get("evidence"), list) else []:
        if not isinstance(row, dict) or not _evidence_binding_valid(row):
            continue
        if incident_component_type and row.get("component_type") != incident_component_type:
            continue
        if incident_component_id and not _is_generic_component_id(incident_component_id) and row.get("component_id") != incident_component_id:
            continue
        rows.append(row)
    return rows


def _category(requirement: str, source_type: str) -> str:
    if source_type.endswith("delivery"):
        if requirement.endswith("_verified"):
            return "delivery_verification_missing"
        return "delivery_blocker"
    if "monitoring" in requirement:
        return "publication_monitoring_incident"
    return "hub_blocker"


def _component_type_from_component_id(component_id: str) -> str:
    prefix = str(component_id).split(":", 1)[0]
    return {
        "release": "release_verification",
        "distribution": "distribution_verification",
        "submission": "submission_verification",
        "submission-evidence": "submission_evidence_verification",
        "release-operations": "release_operations_verification",
        "publication-monitoring": "publication_monitoring_verification",
    }.get(prefix, prefix)


def _component_type_from_check_id(check_id: str) -> str:
    for marker, component_type in (
        ("release_verification", "release_verification"),
        ("distribution_verification", "distribution_verification"),
        ("submission_evidence_verification", "submission_evidence_verification"),
        ("submission_verification", "submission_verification"),
        ("release_operations_verification", "release_operations_verification"),
        ("monitoring", "publication_monitoring_verification"),
    ):
        if marker in check_id:
            return component_type
    return "trust_operations_hub"


def _component_id_from_check_id(component_type: str, check_id: str) -> str:
    prefix = {
        "release_verification": "release",
        "distribution_verification": "distribution",
        "submission_verification": "submission",
        "submission_evidence_verification": "submission-evidence",
        "release_operations_verification": "release-operations",
        "publication_monitoring_verification": "publication-monitoring",
    }.get(component_type, "hub")
    if check_id.endswith("_component_coverage"):
        return f"{prefix}:coverage"
    match = re.search(r"_(release|distribution|submission|submission_evidence|release_operations)_([A-Za-z0-9_]+)_hash$", check_id)
    if match:
        return f"{prefix}:{match.group(2).replace('_', '-')}"
    return f"{prefix}:verification"


def _contains_sensitive_value(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    markers = (
        "sk-",
        "bearer ",
        "github" + "_pat_",
        "x-access" + "-token",
        "github" + "key",
        "c:" + "\\users\\",
        "\\\\",
    )
    return any(marker in lowered for marker in markers)


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text(
        "MusicForge Trust Operations Incident Board\n\nThis package contains local incident response and remediation closeout evidence for Trust Operations Hub blockers.\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> ImplementationDocument:
    return read_json(path)


def _read_json_default(path: Path, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.tmp")
    _mkdir(zip_path.parent)
    if tmp_path.exists():
        tmp_path.unlink()
    with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)
    tmp_path.replace(zip_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


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


def _from_fs_path(value: str) -> Path:
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if os.name == "nt" and value.startswith("\\\\?\\"):
        return Path(value[4:])
    return Path(value)


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
