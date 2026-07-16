from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import shutil
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.trust.public_trust_center_publication import publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash, hub_manifest_hash




TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_report"
TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_readiness_matrix"
TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_blocker_register"
TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_manual_action_queue"
TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_evidence_binding_index"
TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_verification_summary_index"
TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE = "musicforge_trust_operations_source_state"
TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_evidence_index"
TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_readiness_matrix"
TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_delivery_blocker_register"
TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_delivery_manual_action_queue"

TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_change_request"
TRUST_OPERATIONS_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}







class TrustOperationsHubError(ValueError):
    pass


class TrustOperationsHubNotFoundError(TrustOperationsHubError):
    pass


class TrustOperationsHubStateError(TrustOperationsHubError):
    pass


class TrustOperationsHubStore:
    def __init__(self, root: Path | str = Path(".musicforge") / "trust-operations") -> None:
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def hubs_dir(self) -> Path:
        return self.root / "hubs"

    def hub_dir(self, hub_id: str) -> Path:
        return self.hubs_dir() / _safe_id(hub_id)

    def hub_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "hub.json"

    def events_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "events.jsonl"

    def current_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "current-report.json"

    def reports_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "reports"

    def report_dir(self, hub_id: str, report_id: str) -> Path:
        return self.reports_dir(hub_id) / _safe_id(report_id)

    def report_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "hub-report.json"

    def readiness_matrix_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "readiness-matrix.json"

    def blocker_register_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "blocker-register.json"

    def manual_action_queue_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "manual-action-queue.json"

    def evidence_binding_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "evidence-binding-index.json"

    def verification_summary_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "verification-summary-index.json"

    def source_state_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "source-state.json"

    def delivery_evidence_index_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-evidence-index.json"

    def delivery_readiness_matrix_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-readiness-matrix.json"

    def delivery_blocker_register_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-blocker-register.json"

    def delivery_manual_action_queue_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "delivery-manual-action-queue.json"

    def source_paths_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "source-paths.json"

    def export_dir(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "export"

    def zip_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "trust-operations-hub.zip"

    def verification_report_path(self, hub_id: str, report_id: str) -> Path:
        return self.report_dir(hub_id, report_id) / "trust-operations-hub-verification-report.json"

    def signoff_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff.json"

    def signoff_history_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "signoff-history.jsonl"

    def change_requests_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "change-requests"

    def change_request_path(self, hub_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(hub_id) / (_safe_id(change_request_id) + ".json")

    def create_hub(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            hub_id = _safe_id(str(payload.get("hub_id") or _next_id(self.hubs_dir(), "trust-hub")))
            if self.hub_path(hub_id).exists():
                raise TrustOperationsHubStateError("Trust Operations Hub already exists.")
            requirements = _default_requirements()
            if isinstance(payload.get("requirements"), dict):
                requirements.update({key: bool(value) for key, value in payload["requirements"].items() if key in requirements})
            hub = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_PACKAGE_TYPE,
                "hub_id": hub_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Default Trust Operations Hub")[:160]),
                "created_at": now,
                "updated_at": now,
                "status": "active",
                "scope": _scope(payload),
                "requirements": requirements,
                "policies": {"waived_blockers_default_blocking": True, "allow_warning_signoff": False, "allow_force_signoff": True},
            }
            hub["integrity_hash"] = hub_hash(hub)
            _write_json(self.hub_path(hub_id), hub)
            self._append_event(hub_id, "hub_created", {"hub_hash": hub["integrity_hash"]}, now=now)
            return _sanitize(hub)

    def read_hub(self, hub_id: str) -> dict[str, Any]:
        path = self.hub_path(hub_id)
        if not path.exists():
            raise TrustOperationsHubNotFoundError("Trust Operations Hub not found.")
        return _read_json(path)

    def list_hubs(self) -> list[dict[str, Any]]:
        root = self.hubs_dir()
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/hub.json")):
            rows.append(_sanitize(_read_json(path)))
        return rows

    def refresh_report(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(hub_id)
            hub = self.read_hub(hub_id)
            if hub.get("integrity_hash") != hub_hash(hub):
                raise TrustOperationsHubStateError("Trust Operations Hub integrity failed.")
            report_id = _safe_id(str(payload.get("report_id") or _next_id(self.reports_dir(hub_id), "trust-hub-report")))
            report_dir = self.report_dir(hub_id, report_id)
            _mkdir(report_dir)
            source_state = self._source_state(hub, report_id, payload)
            evidence_index = self._evidence_binding_index(hub, report_id, payload, source_state)
            verification_index = self._verification_summary_index(hub, report_id, evidence_index)
            readiness = self._readiness_matrix(hub, report_id, evidence_index, verification_index, source_state)
            blockers = self._blocker_register(hub, report_id, readiness)
            actions = self._manual_action_queue(hub, report_id, blockers)
            delivery_evidence = self._delivery_evidence_index(hub, report_id, payload)
            delivery_readiness = self._delivery_readiness_matrix(hub, report_id, delivery_evidence)
            delivery_blockers = self._delivery_blocker_register(hub, report_id, delivery_readiness)
            delivery_actions = self._delivery_manual_action_queue(hub, report_id, delivery_blockers)
            total_blockers = int(blockers["summary"]["blocker_count"] or 0) + int(delivery_blockers["summary"]["blocker_count"] or 0)
            total_blocked = int(readiness["summary"]["blocked_count"] or 0) + int(delivery_readiness["summary"]["blocked_count"] or 0)
            total_stale = int(readiness["summary"]["stale_count"] or 0) + int(delivery_readiness["summary"]["stale_count"] or 0)
            total_missing = int(readiness["summary"].get("missing_count") or 0) + int(delivery_readiness["summary"].get("missing_count") or 0)
            overall_ready = total_blockers == 0 and total_blocked == 0 and total_stale == 0 and total_missing == 0
            combined_summary = _combine_readiness_summaries(readiness["summary"], delivery_readiness["summary"])
            report = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": report_id,
                "generated_at": now,
                "status": "ready" if overall_ready else "blocked",
                "readiness": {"overall_status": "ready" if overall_ready else "blocked", **combined_summary},
                "delivery": {
                    "readiness": delivery_readiness.get("summary"),
                    "blockers": delivery_blockers.get("summary"),
                    "actions": delivery_actions.get("summary"),
                },
                "scope": hub.get("scope") or {},
                "source": {
                    "hub_hash": hub.get("integrity_hash"),
                    "source_state_hash": source_state.get("integrity_hash"),
                    "readiness_matrix_hash": readiness.get("integrity_hash"),
                    "blocker_register_hash": blockers.get("integrity_hash"),
                    "manual_action_queue_hash": actions.get("integrity_hash"),
                    "evidence_binding_index_hash": evidence_index.get("integrity_hash"),
                    "verification_summary_index_hash": verification_index.get("integrity_hash"),
                    "delivery_evidence_index_hash": delivery_evidence.get("integrity_hash"),
                    "delivery_readiness_matrix_hash": delivery_readiness.get("integrity_hash"),
                    "delivery_blocker_register_hash": delivery_blockers.get("integrity_hash"),
                    "delivery_manual_action_queue_hash": delivery_actions.get("integrity_hash"),
                },
            }
            report["integrity_hash"] = hub_hash(report)
            _write_json(self.source_state_path(hub_id, report_id), source_state)
            _write_json(self.evidence_binding_index_path(hub_id, report_id), evidence_index)
            _write_json(self.verification_summary_index_path(hub_id, report_id), verification_index)
            _write_json(self.readiness_matrix_path(hub_id, report_id), readiness)
            _write_json(self.blocker_register_path(hub_id, report_id), blockers)
            _write_json(self.manual_action_queue_path(hub_id, report_id), actions)
            _write_json(self.delivery_evidence_index_path(hub_id, report_id), delivery_evidence)
            _write_json(self.delivery_readiness_matrix_path(hub_id, report_id), delivery_readiness)
            _write_json(self.delivery_blocker_register_path(hub_id, report_id), delivery_blockers)
            _write_json(self.delivery_manual_action_queue_path(hub_id, report_id), delivery_actions)
            _write_json(self.report_path(hub_id, report_id), report)
            write_json(self.source_paths_path(hub_id, report_id), _source_paths(payload))
            _write_json(self.current_report_path(hub_id), {"hub_id": hub_id, "report_id": report_id, "report_hash": report["integrity_hash"], "updated_at": now})
            self._append_event(hub_id, "hub_report_refreshed", {"report_id": report_id, "report_hash": report["integrity_hash"]}, now=now)
            return _sanitize({"hub_report": report, "readiness_matrix": readiness, "blocker_register": blockers, "manual_action_queue": actions, "evidence_binding_index": evidence_index, "verification_summary_index": verification_index, "source_state": source_state, "delivery_evidence_index": delivery_evidence, "delivery_readiness_matrix": delivery_readiness, "delivery_blocker_register": delivery_blockers, "delivery_manual_action_queue": delivery_actions})

    def export_report(self, hub_id: str, report_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            self._ensure_unsigned(hub_id)
            docs = self._read_report_docs(hub_id, report_id)
            self._assert_report_docs_current(docs)
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            export_dir = self.export_dir(hub_id, report_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir / "checksum")
            for source_name, target_name in (
                ("hub_report", "hub-report.json"),
                ("readiness_matrix", "readiness-matrix.json"),
                ("blocker_register", "blocker-register.json"),
                ("manual_action_queue", "manual-action-queue.json"),
                ("evidence_binding_index", "evidence-binding-index.json"),
                ("verification_summary_index", "verification-summary-index.json"),
                ("source_state", "source-state.json"),
                ("delivery_evidence_index", "delivery-evidence-index.json"),
                ("delivery_readiness_matrix", "delivery-readiness-matrix.json"),
                ("delivery_blocker_register", "delivery-blocker-register.json"),
                ("delivery_manual_action_queue", "delivery-manual-action-queue.json"),
            ):
                _write_json(export_dir / target_name, docs[source_name])
            signoff_summary = self._signoff_summary(hub_id)
            _write_json(export_dir / "signoff-summary.json", signoff_summary)
            _write_readme(export_dir)
            checksum = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum)
            _write_sha256sums(export_dir, checksum)
            source = {
                "hub_report_hash": docs["hub_report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness_matrix"].get("integrity_hash"),
                "blocker_register_hash": docs["blocker_register"].get("integrity_hash"),
                "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
                "evidence_binding_index_hash": docs["evidence_binding_index"].get("integrity_hash"),
                "verification_summary_index_hash": docs["verification_summary_index"].get("integrity_hash"),
                "source_state_hash": docs["source_state"].get("integrity_hash"),
                "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
                "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
                "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
                "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
                "signoff_summary_hash": signoff_summary.get("integrity_hash"),
            }
            manifest = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Hub", "version": __version__},
                "hub_id": hub_id,
                "report_id": report_id,
                "generated_at": now,
                "status": docs["hub_report"].get("status"),
                "source": source,
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-hub-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = hub_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-hub-manifest.json", manifest)
            self._append_event(hub_id, "hub_exported", {"report_id": report_id, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, report_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            self._ensure_unsigned(hub_id)
            export_dir = self.export_dir(hub_id, report_id)
            manifest = _read_json_default(export_dir / "trust-operations-hub-manifest.json", default={})
            if not manifest:
                raise TrustOperationsHubStateError("Trust Operations Hub export is missing.")
            docs = self._read_report_docs(hub_id, report_id)
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            if manifest.get("source", {}).get("hub_report_hash") != docs["hub_report"].get("integrity_hash"):
                raise TrustOperationsHubStateError("Trust Operations Hub export is stale.")
            zip_path = self.zip_path(hub_id, report_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = hub_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-hub-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "report_id": report_id}
            self._append_event(hub_id, "hub_zip_built", {"report_id": report_id, "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]}, now=now)
            return _sanitize(info)

    def verify_zip(self, hub_id: str, report_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package

        payload = payload or {}
        report = verify_trust_operations_hub_package(
            self.zip_path(hub_id, report_id),
            strict=bool(payload.get("strict", False)),
            require_ready=bool(payload.get("require_ready", False)),
            require_signed=bool(payload.get("require_signed", False)),
            require_current=bool(payload.get("require_current", False)),
            require_no_critical_blockers=bool(payload.get("require_no_critical_blockers", False)),
            require_publication_monitoring_clean=bool(payload.get("require_publication_monitoring_clean", False)),
            require_delivery_ready=bool(payload.get("require_delivery_ready", False)),
            require_incident_closeout=bool(payload.get("require_incident_closeout", False)),
            require_incident_regression_guards=bool(payload.get("require_incident_regression_guards", False)),
            require_trust_controls=bool(payload.get("require_trust_controls", False)),
            require_trust_control_signoff=bool(payload.get("require_trust_control_signoff", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path"),
            public_trust_center_verification_path=payload.get("public_trust_center_verification_path"),
            publication_monitoring_verification_path=payload.get("publication_monitoring_verification_path"),
            release_verification_path=payload.get("release_verification_path"),
            release_verification_paths=payload.get("release_verification_paths"),
            distribution_verification_path=payload.get("distribution_verification_path"),
            distribution_verification_paths=payload.get("distribution_verification_paths"),
            submission_verification_path=payload.get("submission_verification_path"),
            submission_verification_paths=payload.get("submission_verification_paths"),
            submission_evidence_verification_path=payload.get("submission_evidence_verification_path"),
            submission_evidence_verification_paths=payload.get("submission_evidence_verification_paths"),
            release_operations_verification_path=payload.get("release_operations_verification_path"),
            release_operations_verification_paths=payload.get("release_operations_verification_paths"),
            hub_signoff_path=payload.get("hub_signoff_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
            incident_board_package_path=payload.get("incident_board_package_path"),
            incident_board_verification_report_path=payload.get("incident_board_verification_report_path"),
            incident_knowledge_package_path=payload.get("incident_knowledge_package_path"),
            incident_knowledge_verification_report_path=payload.get("incident_knowledge_verification_report_path"),
            trust_control_package_path=payload.get("trust_control_package_path"),
            trust_control_verification_report_path=payload.get("trust_control_verification_report_path"),
            trust_control_signoff_archive_path=payload.get("trust_control_signoff_archive_path"),
            trust_control_signoff_verification_report_path=payload.get("trust_control_signoff_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id, report_id), report)
        return report

    def signoff(self, hub_id: str, report_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if self.signoff_path(hub_id).exists() or self._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is already signed.")
            docs = self._read_report_docs(hub_id, report_id)
            verification = _read_json_default(self.verification_report_path(hub_id, report_id), default={})
            zip_path = self.zip_path(hub_id, report_id)
            if not verification:
                raise TrustOperationsHubStateError("Trust Operations Hub verification report is required before signoff.")
            if verification.get("zip_sha256") != _sha256(zip_path) or verification.get("manifest_hash") != _read_json_default(self.export_dir(hub_id, report_id) / "trust-operations-hub-manifest.json", default={}).get("integrity_hash"):
                raise TrustOperationsHubStateError("Trust Operations Hub verification is stale.")
            if self._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is already signed.")
            self._assert_external_sources_current(docs, self._read_source_paths(hub_id, report_id))
            force = bool(payload.get("force", False))
            if verification.get("status") == "failed":
                raise TrustOperationsHubStateError("Trust Operations Hub verification failed.")
            if docs["blocker_register"].get("summary", {}).get("critical_count", 0) and not force:
                raise TrustOperationsHubStateError("Trust Operations Hub has blocking issues.")
            override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "").strip())
            if force and len(override_reason) < 8:
                raise TrustOperationsHubStateError("Force signoff requires override_reason.")
            signoff = {
                "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": report_id,
                "status": "signed",
                "signed_at": now,
                "signed_by": sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Trust Operations Hub is ready.")[:500]),
                "force": force,
                "override_reason": override_reason if force else None,
                "source": {
                    "hub_report_hash": docs["hub_report"].get("integrity_hash"),
                    "manifest_hash": verification.get("manifest_hash"),
                    "zip_sha256": verification.get("zip_sha256"),
                    "zip_size_bytes": verification.get("zip_size_bytes"),
                    "verification_report_hash": verification_hash(verification),
                    "verification_status": verification.get("status"),
                },
            }
            signoff["integrity_hash"] = hub_hash(signoff)
            _write_json(self.signoff_path(hub_id), signoff)
            self._append_event(hub_id, "hub_signed", {"report_id": report_id, "signoff_hash": signoff["integrity_hash"]}, now=now)
            _append_jsonl(self.signoff_history_path(hub_id), {"event_type": "signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "report_id": report_id})
            return _sanitize(signoff)

    def create_change_request(self, hub_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self.read_hub(hub_id)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsHubStateError("Change request reason must be at least 8 characters.")
            change_request_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(hub_id), "trust-hub-cr")))
            cr = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE, "change_request_id": change_request_id, "hub_id": hub_id, "status": "draft", "reason": reason, "requested_at": now, "approved_at": None, "applied_at": None}
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def approve_change_request(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            cr = self._read_change_request(hub_id, change_request_id)
            if cr.get("integrity_hash") != hub_hash(cr):
                raise TrustOperationsHubStateError("Change request integrity failed.")
            if cr.get("status") != "draft":
                raise TrustOperationsHubStateError("Only draft change requests can be approved.")
            cr["status"] = "approved"
            cr["approved_at"] = now
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            return _sanitize(cr)

    def reset_signoff(self, hub_id: str, change_request_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            state = self._signoff_state(hub_id)
            signoff = _read_json_default(self.signoff_path(hub_id), default={})
            if state["status"] != "signed":
                raise TrustOperationsHubStateError("Trust Operations Hub is not signed.")
            if not signoff:
                signoff = {"integrity_hash": state.get("signoff_hash")}
            cr = self._read_change_request(hub_id, change_request_id)
            if cr.get("integrity_hash") != hub_hash(cr):
                raise TrustOperationsHubStateError("Change request integrity failed.")
            if cr.get("status") != "approved" or cr.get("applied_at"):
                raise TrustOperationsHubStateError("Approved unused change request is required.")
            cr["status"] = "applied"
            cr["applied_at"] = now
            cr["applied_signoff_hash"] = signoff.get("integrity_hash")
            cr["integrity_hash"] = hub_hash(cr)
            _write_json(self.change_request_path(hub_id, change_request_id), cr)
            _append_jsonl(self.signoff_history_path(hub_id), {"event_type": "reset", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]})
            if self.signoff_path(hub_id).exists():
                os.remove(_fs_path(self.signoff_path(hub_id)))
            self._append_event(hub_id, "hub_signoff_reset", {"change_request_id": change_request_id}, now=now)
            return {"status": "reset", "change_request": _sanitize(cr)}

    def _source_state(self, hub: ImplementationDocument, report_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        states: list[dict[str, Any]] = []
        for state_path in _paths(payload.get("publication_channel_state_paths") or payload.get("publication_channel_state_path")):
            state = _read_json_default(state_path, default={})
            if not state:
                continue
            current = state.get("current_publication") if isinstance(state.get("current_publication"), dict) else {}
            states.append({"center_id": state.get("center_id"), "channel_id": state.get("channel_id"), "state_hash": publication_channel_state_hash(state), "latest_event_hash": state.get("latest_event_hash"), "current_publication_id": current.get("publication_id"), "current_status": current.get("status")})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "sources": {"publication_channel_states": states, "release_signoffs": [], "operations_signoffs": [], "acceptance_board_signoffs": []}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _evidence_binding_index(self, hub: ImplementationDocument, report_id: str, payload: ImplementationDocument, source_state: ImplementationDocument) -> ImplementationDocument:
        rows: list[dict[str, Any]] = []
        for report_path in _paths(payload.get("public_trust_center_verification_paths") or payload.get("public_trust_center_verification_path")):
            report = _read_json_default(report_path, default={})
            rows.append(_evidence_from_verification("public_trust_center:ptc-default", "public_trust_center_verification", report, report_path))
        for report_path in _paths(payload.get("publication_monitoring_verification_paths") or payload.get("publication_monitoring_verification_path")):
            report = _read_json_default(report_path, default={})
            rows.append(_evidence_from_verification("publication-monitoring:public-release", "publication_monitoring_verification", report, report_path))
        for state in source_state.get("sources", {}).get("publication_channel_states", []) if isinstance(source_state.get("sources"), dict) else []:
            if isinstance(state, dict):
                rows.append({"evidence_id": "publication-channel-state:" + str(state.get("channel_id") or "unknown"), "component_type": "publication_channel_state", "package_type": "musicforge_public_trust_center_publication_channel_state", "zip_sha256": None, "manifest_hash": None, "verification_report_hash": None, "source_hash": state.get("state_hash"), "status": state.get("current_status") or "missing", "current_state_refs": {"publication_channel_state_hash": state.get("state_hash"), "latest_event_hash": state.get("latest_event_hash"), "current_publication_id": state.get("current_publication_id")}})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "evidence": rows, "summary": {"evidence_count": len(rows), "failed_count": sum(1 for row in rows if row.get("status") == "failed"), "stale_count": sum(1 for row in rows if row.get("status") == "stale")}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _verification_summary_index(self, hub: ImplementationDocument, report_id: str, evidence_index: ImplementationDocument) -> ImplementationDocument:
        rows = []
        for evidence in evidence_index.get("evidence", []) if isinstance(evidence_index.get("evidence"), list) else []:
            if not isinstance(evidence, dict) or not evidence.get("verification_report_hash"):
                continue
            rows.append({"verification_id": evidence.get("evidence_id"), "component_type": evidence.get("component_type"), "status": evidence.get("status"), "verification_report_hash": evidence.get("verification_report_hash"), "package_zip_sha256": evidence.get("zip_sha256"), "manifest_hash": evidence.get("manifest_hash"), "required_by": [_requirement_for_component(str(evidence.get("component_type") or ""))]})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "verifications": rows, "summary": {"verification_count": len(rows), "passed_count": sum(1 for row in rows if row.get("status") == "passed"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _readiness_matrix(self, hub: ImplementationDocument, report_id: str, evidence_index: ImplementationDocument, verification_index: ImplementationDocument, source_state: ImplementationDocument) -> ImplementationDocument:
        requirements = hub.get("requirements") if isinstance(hub.get("requirements"), dict) else {}
        rows: list[dict[str, Any]] = []
        by_type = {str(row.get("component_type") or ""): row for row in evidence_index.get("evidence", []) if isinstance(row, dict)}
        if requirements.get("require_public_trust_center_verified", True):
            rows.append(_readiness_row("public-trust-center:ptc-default", "public_trust_center", "public_trust_center_verified", by_type.get("public_trust_center_verification")))
        if requirements.get("require_publication_current", True):
            state_rows = source_state.get("sources", {}).get("publication_channel_states", []) if isinstance(source_state.get("sources"), dict) else []
            state = state_rows[0] if state_rows else {}
            status = "ready" if state and state.get("current_status") not in {"revoked", "superseded"} else "blocked"
            rows.append({"component_id": "publication-channel:" + str(state.get("channel_id") or "missing"), "component_type": "publication_channel", "requirement": "publication_current", "status": status, "severity": "blocking", "evidence_refs": ["publication-channel-state"], "summary": "Publication channel state is current." if status == "ready" else "Publication channel state is missing or revoked/superseded."})
        if requirements.get("require_publication_monitoring_clean", True):
            evidence = by_type.get("publication_monitoring_verification")
            rows.append(_readiness_row("publication-monitoring:public-release", "publication_monitoring", "publication_monitoring_clean", evidence))
            monitoring_summary = evidence.get("summary") if isinstance(evidence, dict) and isinstance(evidence.get("summary"), dict) else {}
            if requirements.get("require_no_open_critical_incidents", True) and evidence and monitoring_summary.get("critical_incidents", 0):
                rows.append({"component_id": "publication-monitoring:public-release", "component_type": "publication_monitoring", "requirement": "no_open_critical_incidents", "status": "blocked", "severity": "blocking", "evidence_refs": ["publication-monitoring-verification"], "source_check_id": "ptcpm_require_no_open_critical_incidents", "summary": "Publication monitoring has open critical incidents."})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "rows": rows, "summary": _readiness_summary(rows)}
        data["source"] = {"evidence_binding_index_hash": evidence_index.get("integrity_hash"), "verification_summary_index_hash": verification_index.get("integrity_hash"), "source_state_hash": source_state.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _blocker_register(self, hub: ImplementationDocument, report_id: str, readiness: ImplementationDocument) -> ImplementationDocument:
        blockers = []
        for index, row in enumerate([row for row in readiness.get("rows", []) if isinstance(row, dict) and row.get("status") in {"blocked", "stale", "missing", "not_configured"} and row.get("severity") == "blocking"], start=1):
            blockers.append({"blocker_id": f"hub-blocker-{index:06d}", "component_id": row.get("component_id"), "requirement": row.get("requirement"), "severity": "critical" if row.get("status") == "blocked" else "high", "status": "open", "source_check_id": row.get("source_check_id") or row.get("requirement"), "evidence_ref": (row.get("evidence_refs") or [None])[0], "manual_action_id": f"hub-action-{index:06d}", "message": row.get("summary")})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "blockers": blockers, "summary": {"blocker_count": len(blockers), "critical_count": sum(1 for row in blockers if row.get("severity") == "critical"), "high_count": sum(1 for row in blockers if row.get("severity") == "high")}}
        data["source"] = {"readiness_matrix_hash": readiness.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _manual_action_queue(self, hub: ImplementationDocument, report_id: str, blocker_register: ImplementationDocument) -> ImplementationDocument:
        actions = []
        for blocker in blocker_register.get("blockers", []) if isinstance(blocker_register.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            actions.append({"action_id": blocker.get("manual_action_id"), "action_type": _action_type(str(blocker.get("requirement") or "")), "status": "manual_required", "component_id": blocker.get("component_id"), "reason": blocker.get("message"), "allowed_automation": False, "suggested_cli": "python -m song_agent.cli trust-operations-hub --refresh"})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "actions": actions, "summary": {"manual_required_count": len(actions), "safe_action_count": 0}}
        data["source"] = {"blocker_register_hash": blocker_register.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_evidence_index(self, hub: ImplementationDocument, report_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        rows: list[dict[str, Any]] = []
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            paths = _paths(payload.get(spec["payload_keys"]) or payload.get(spec["payload_key"]))
            for index, report_path in enumerate(paths, start=1):
                report = _read_json_default(report_path, default={})
                component_id = _delivery_component_id(spec, report, index)
                rows.append(_delivery_evidence_from_verification(component_id, spec["component_type"], spec["requirement"], report, report_path))
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "evidence": sorted(rows, key=lambda row: (str(row.get("component_type") or ""), str(row.get("component_id") or ""))),
            "summary": _delivery_evidence_summary(rows),
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_readiness_matrix(self, hub: ImplementationDocument, report_id: str, delivery_evidence: ImplementationDocument) -> ImplementationDocument:
        requirements = hub.get("requirements") if isinstance(hub.get("requirements"), dict) else {}
        rows: list[dict[str, Any]] = []
        evidence_rows = [row for row in delivery_evidence.get("evidence", []) if isinstance(row, dict)]
        by_type: dict[str, list[dict[str, Any]]] = {}
        for row in evidence_rows:
            by_type.setdefault(str(row.get("component_type") or ""), []).append(row)
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            requirement = str(spec["requirement"])
            required = bool(requirements.get("require_" + requirement, False))
            typed_rows = by_type.get(str(spec["component_type"]), [])
            if not typed_rows:
                if not required:
                    continue
                rows.append(
                    {
                        "component_id": str(spec["component_id_prefix"]) + ":missing",
                        "component_type": spec["component_type"],
                        "requirement": requirement,
                        "status": "missing",
                        "severity": "blocking",
                        "evidence_refs": [],
                        "source_check_id": requirement,
                        "summary": f"{requirement} evidence is missing.",
                    }
                )
                continue
            for evidence in typed_rows:
                status = _status_from_verification_evidence(evidence)
                rows.append(
                    {
                        "component_id": evidence.get("component_id"),
                        "component_type": evidence.get("component_type"),
                        "requirement": requirement,
                        "status": status,
                        "severity": "blocking",
                        "evidence_refs": [str(evidence.get("evidence_id") or evidence.get("component_id") or "")],
                        "source_check_id": requirement,
                        "summary": f"{requirement} is {status}.",
                    }
                )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "rows": sorted(rows, key=lambda row: (str(row.get("component_type") or ""), str(row.get("component_id") or ""), str(row.get("requirement") or ""))),
            "summary": _readiness_summary(rows),
            "source": {"delivery_evidence_index_hash": delivery_evidence.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_blocker_register(self, hub: ImplementationDocument, report_id: str, delivery_readiness: ImplementationDocument) -> ImplementationDocument:
        blockers = []
        for index, row in enumerate([row for row in delivery_readiness.get("rows", []) if isinstance(row, dict) and row.get("status") in {"blocked", "stale", "missing", "not_configured"} and row.get("severity") == "blocking"], start=1):
            blockers.append(
                {
                    "blocker_id": f"hub-delivery-blocker-{index:06d}",
                    "component_id": row.get("component_id"),
                    "requirement": row.get("requirement"),
                    "severity": "critical" if row.get("status") == "blocked" else "high",
                    "status": "open",
                    "source_check_id": row.get("source_check_id") or row.get("requirement"),
                    "evidence_ref": (row.get("evidence_refs") or [None])[0],
                    "manual_action_id": f"hub-delivery-action-{index:06d}",
                    "message": row.get("summary"),
                }
            )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "blockers": blockers,
            "summary": {"blocker_count": len(blockers), "critical_count": sum(1 for row in blockers if row.get("severity") == "critical"), "high_count": sum(1 for row in blockers if row.get("severity") == "high")},
            "source": {"delivery_readiness_matrix_hash": delivery_readiness.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_manual_action_queue(self, hub: ImplementationDocument, report_id: str, delivery_blockers: ImplementationDocument) -> ImplementationDocument:
        actions = []
        for blocker in delivery_blockers.get("blockers", []) if isinstance(delivery_blockers.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            actions.append(
                {
                    "action_id": blocker.get("manual_action_id"),
                    "action_type": _delivery_action_type(str(blocker.get("requirement") or "")),
                    "status": "manual_required",
                    "component_id": blocker.get("component_id"),
                    "reason": blocker.get("message"),
                    "allowed_automation": False,
                    "suggested_cli": "python -m song_agent.cli trust-operations-hub --refresh --export --zip --verify",
                }
            )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "actions": actions,
            "summary": {"manual_required_count": len(actions), "safe_action_count": 0},
            "source": {"delivery_blocker_register_hash": delivery_blockers.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _read_report_docs(self, hub_id: str, report_id: str) -> dict[str, ImplementationDocument]:
        docs = {
            "hub_report": _read_required(self.report_path(hub_id, report_id)),
            "readiness_matrix": _read_required(self.readiness_matrix_path(hub_id, report_id)),
            "blocker_register": _read_required(self.blocker_register_path(hub_id, report_id)),
            "manual_action_queue": _read_required(self.manual_action_queue_path(hub_id, report_id)),
            "evidence_binding_index": _read_required(self.evidence_binding_index_path(hub_id, report_id)),
            "verification_summary_index": _read_required(self.verification_summary_index_path(hub_id, report_id)),
            "source_state": _read_required(self.source_state_path(hub_id, report_id)),
            "delivery_evidence_index": _read_required(self.delivery_evidence_index_path(hub_id, report_id)),
            "delivery_readiness_matrix": _read_required(self.delivery_readiness_matrix_path(hub_id, report_id)),
            "delivery_blocker_register": _read_required(self.delivery_blocker_register_path(hub_id, report_id)),
            "delivery_manual_action_queue": _read_required(self.delivery_manual_action_queue_path(hub_id, report_id)),
        }
        return docs

    def _read_source_paths(self, hub_id: str, report_id: str) -> ImplementationDocument:
        return _read_json_default(self.source_paths_path(hub_id, report_id), default={})

    def _assert_report_docs_current(self, docs: dict[str, ImplementationDocument]) -> None:
        if docs["hub_report"].get("integrity_hash") != hub_hash(docs["hub_report"]):
            raise TrustOperationsHubStateError("Hub report integrity failed.")
        for key in ("readiness_matrix", "blocker_register", "manual_action_queue", "evidence_binding_index", "verification_summary_index", "source_state", "delivery_evidence_index", "delivery_readiness_matrix", "delivery_blocker_register", "delivery_manual_action_queue"):
            if docs[key].get("integrity_hash") != hub_hash(docs[key]):
                raise TrustOperationsHubStateError(f"{key} integrity failed.")
        source = docs["hub_report"].get("source") if isinstance(docs["hub_report"].get("source"), dict) else {}
        expected = {
            "readiness_matrix_hash": docs["readiness_matrix"].get("integrity_hash"),
            "blocker_register_hash": docs["blocker_register"].get("integrity_hash"),
            "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
            "evidence_binding_index_hash": docs["evidence_binding_index"].get("integrity_hash"),
            "verification_summary_index_hash": docs["verification_summary_index"].get("integrity_hash"),
            "source_state_hash": docs["source_state"].get("integrity_hash"),
            "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
            "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
            "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
            "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
        }
        for key, value in expected.items():
            if source.get(key) != value:
                raise TrustOperationsHubStateError("Hub report source references are stale.")

    def _assert_external_sources_current(self, docs: dict[str, ImplementationDocument], source_paths: ImplementationDocument) -> None:
        state_hashes = {
            str(item.get("state_hash") or "")
            for item in docs["source_state"].get("sources", {}).get("publication_channel_states", [])
            if isinstance(item, dict)
        }
        for state_path in _paths(source_paths.get("publication_channel_state_paths")):
            state = _read_json_default(state_path, default={})
            if not state:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel state is missing.")
            if publication_channel_state_hash(state) not in state_hashes:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel state changed. Refresh before export.")
            current = state.get("current_publication") if isinstance(state.get("current_publication"), dict) else {}
            if not current or current.get("status") in {"revoked", "superseded"}:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel is no longer current. Refresh before export.")
        evidence_rows = [row for row in docs["evidence_binding_index"].get("evidence", []) if isinstance(row, dict)]
        for component_type, key in (
            ("public_trust_center_verification", "public_trust_center_verification_paths"),
            ("publication_monitoring_verification", "publication_monitoring_verification_paths"),
        ):
            expected_rows = [row for row in evidence_rows if row.get("component_type") == component_type]
            expected_hashes = {str(row.get("verification_report_hash") or "") for row in expected_rows}
            for report_path in _paths(source_paths.get(key)):
                report = _read_json_default(report_path, default={})
                if verification_hash(report) not in expected_hashes:
                    raise TrustOperationsHubStateError("Trust Operations Hub external verification report changed. Refresh before export.")
        delivery_rows = [row for row in docs["delivery_evidence_index"].get("evidence", []) if isinstance(row, dict)]
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            expected_rows = [row for row in delivery_rows if row.get("component_type") == spec["component_type"]]
            expected_hashes = {str(row.get("verification_report_hash") or "") for row in expected_rows}
            for report_path in _paths(source_paths.get(spec["payload_keys"])):
                report = _read_json_default(report_path, default={})
                if verification_hash(report) not in expected_hashes:
                    raise TrustOperationsHubStateError("Trust Operations Hub delivery verification report changed. Refresh before export.")

    def _ensure_unsigned(self, hub_id: str) -> None:
        if self._signoff_state(hub_id)["status"] == "signed":
            raise TrustOperationsHubStateError("Signed Trust Operations Hub cannot be modified. Reset signoff with an approved change request first.")

    def _signoff_state(self, hub_id: str) -> ImplementationDocument:
        state: dict[str, Any] = {"status": "unsigned", "signoff_hash": None, "change_request_id": None}
        for row in _read_jsonl(self.signoff_history_path(hub_id)):
            event_type = str(row.get("event_type") or "")
            if event_type == "signed" and row.get("signoff_hash"):
                state = {"status": "signed", "signoff_hash": row.get("signoff_hash"), "report_id": row.get("report_id")}
            elif event_type == "reset" and state.get("status") == "signed":
                if row.get("signoff_hash") != state.get("signoff_hash"):
                    continue
                change_request_id = str(row.get("change_request_id") or "")
                try:
                    cr = self._read_change_request(hub_id, change_request_id)
                except TrustOperationsHubError:
                    continue
                if (
                    cr.get("status") == "applied"
                    and cr.get("applied_at")
                    and cr.get("applied_signoff_hash") == row.get("signoff_hash")
                    and cr.get("integrity_hash") == hub_hash(cr)
                    and cr.get("integrity_hash") == row.get("change_request_hash")
                ):
                    state = {"status": "reset", "signoff_hash": row.get("signoff_hash"), "change_request_id": change_request_id}
        if state.get("status") == "signed":
            signoff = _read_json_default(self.signoff_path(hub_id), default={})
            if signoff and signoff.get("integrity_hash") != state.get("signoff_hash"):
                state["signoff_file_status"] = "mismatch"
            elif signoff:
                state["signoff_file_status"] = "present"
            else:
                state["signoff_file_status"] = "missing"
        return state

    def _signoff_summary(self, hub_id: str) -> ImplementationDocument:
        signoff = _read_json_default(self.signoff_path(hub_id), default={})
        summary = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_trust_operations_hub_signoff_summary", "hub_id": hub_id, "status": signoff.get("status") or "unsigned", "signoff_hash": signoff.get("integrity_hash"), "report_id": signoff.get("report_id")}
        summary["integrity_hash"] = hub_hash(summary)
        return summary

    def _read_change_request(self, hub_id: str, change_request_id: str) -> ImplementationDocument:
        path = self.change_request_path(hub_id, change_request_id)
        if not path.exists():
            raise TrustOperationsHubNotFoundError("Trust Operations Hub change request not found.")
        return _read_json(path)

    def _append_event(self, hub_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        rows = _read_jsonl(self.events_path(hub_id))
        event = {"event_id": f"trust-hub-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_BLOCKED_KEYS), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash(event)
        _append_jsonl(self.events_path(hub_id), event)








def _default_requirements() -> dict[str, bool]:
    return {
        "require_public_trust_center_verified": True,
        "require_publication_current": True,
        "require_publication_monitoring_clean": True,
        "require_no_open_critical_incidents": True,
        "require_release_verified": False,
        "require_distribution_verified": False,
        "require_submission_verified": False,
        "require_submission_evidence_verified": False,
        "require_release_operations_verified": False,
    }


def _scope(payload: ImplementationDocument) -> ImplementationDocument:
    return {"release_ids": _list(payload.get("release_ids") or payload.get("release_id")), "project_ids": _list(payload.get("project_ids") or payload.get("project_id")), "public_trust_center_ids": _list(payload.get("public_trust_center_ids") or payload.get("public_trust_center_id") or "ptc-default"), "publication_channel_ids": _list(payload.get("publication_channel_ids") or payload.get("publication_channel_id") or "public-release")}


def _source_paths(payload: ImplementationDocument) -> ImplementationDocument:
    paths = {
        "publication_channel_state_paths": [str(path) for path in _paths(payload.get("publication_channel_state_paths") or payload.get("publication_channel_state_path"))],
        "public_trust_center_verification_paths": [str(path) for path in _paths(payload.get("public_trust_center_verification_paths") or payload.get("public_trust_center_verification_path"))],
        "publication_monitoring_verification_paths": [str(path) for path in _paths(payload.get("publication_monitoring_verification_paths") or payload.get("publication_monitoring_verification_path"))],
    }
    for spec in DELIVERY_VERIFICATION_COMPONENTS:
        paths[str(spec["payload_keys"])] = [str(path) for path in _paths(payload.get(spec["payload_keys"]) or payload.get(spec["payload_key"]))]
    return paths


def _evidence_from_verification(evidence_id: str, component_type: str, report: ImplementationDocument, path: Path) -> ImplementationDocument:
    return {"evidence_id": evidence_id, "component_type": component_type, "path_hint": str(path.name), "package_type": report.get("package_type"), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash"), "verification_report_hash": verification_hash(report), "source_hash": report.get("source_hash"), "status": report.get("status") or "missing", "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {}, "current_state_refs": {"publication_channel_state_hash": report.get("channel_state_hash")}}


def _delivery_component_id(spec: dict[str, str], report: ImplementationDocument, index: int) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    for key in ("release_id", "target_id", "submission_id", "evidence_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return f"{spec['component_id_prefix']}:{_safe_id(str(value))}"
    return f"{spec['component_id_prefix']}:{index:03d}"


def _delivery_evidence_from_verification(component_id: str, component_type: str, requirement: str, report: ImplementationDocument, path: Path) -> ImplementationDocument:
    return {
        "evidence_id": component_id + ":verification",
        "component_id": component_id,
        "component_type": component_type,
        "requirement": requirement,
        "path_hint": str(path.name),
        "package_type": report.get("package_type"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "verification_report_hash": verification_hash(report),
        "source_hash": report.get("source_hash"),
        "status": report.get("status") or "missing",
        "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
    }


def _delivery_evidence_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "evidence_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("status") == "passed"),
        "failed_count": sum(1 for row in rows if row.get("status") == "failed"),
        "stale_count": sum(1 for row in rows if row.get("status") == "stale"),
        "missing_count": sum(1 for row in rows if not row.get("status") or row.get("status") == "missing"),
    }


def _status_from_verification_evidence(evidence: ImplementationDocument) -> str:
    status = str(evidence.get("status") or "")
    if status == "passed":
        return "ready"
    if status == "failed":
        return "blocked"
    if status == "stale":
        return "stale"
    return "missing"


def _readiness_row(component_id: str, component_type: str, requirement: str, evidence: ImplementationDocument | None) -> ImplementationDocument:
    if not evidence:
        return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": "missing", "severity": "blocking", "evidence_refs": [], "summary": f"{requirement} evidence is missing."}
    status = "ready" if evidence.get("status") == "passed" else "blocked" if evidence.get("status") == "failed" else "stale" if evidence.get("status") == "stale" else "missing"
    return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": status, "severity": "blocking", "evidence_refs": [str(evidence.get("evidence_id") or component_type)], "summary": f"{requirement} is {status}.", "source_check_id": requirement}


def _readiness_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"row_count": len(rows), "ready_count": sum(1 for row in rows if row.get("status") == "ready"), "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"), "warning_count": sum(1 for row in rows if row.get("status") == "warning"), "stale_count": sum(1 for row in rows if row.get("status") == "stale"), "missing_count": sum(1 for row in rows if row.get("status") in {"missing", "not_configured"})}


def _combine_readiness_summaries(*summaries: ImplementationDocument) -> dict[str, int]:
    keys = ("row_count", "ready_count", "blocked_count", "warning_count", "stale_count", "missing_count")
    return {key: sum(int(summary.get(key) or 0) for summary in summaries if isinstance(summary, dict)) for key in keys}


def _requirement_for_component(component_type: str) -> str:
    return {"public_trust_center_verification": "public_trust_center_verified", "publication_monitoring_verification": "publication_monitoring_clean"}.get(component_type, component_type)


def _action_type(requirement: str) -> str:
    if "incident" in requirement or "monitoring" in requirement:
        return "resolve_publication_monitoring_incident"
    if "publication" in requirement:
        return "refresh_publication_channel"
    return "review_trust_operations_evidence"


def _delivery_action_type(requirement: str) -> str:
    return {
        "release_verified": "verify_release_package",
        "distribution_verified": "verify_distribution_package",
        "submission_verified": "verify_submission_package",
        "submission_evidence_verified": "verify_submission_evidence_package",
        "release_operations_verified": "verify_release_operations_package",
    }.get(requirement, "review_delivery_evidence")


def _paths(value: Any) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, list):
        return [Path(item) for item in value if item]
    return []


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _read_required(path: Path) -> ImplementationDocument:
    if not path.exists():
        raise TrustOperationsHubNotFoundError(f"Trust Operations Hub artifact missing: {path.name}")
    return _read_json(path)


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


def _checksum_json(export_dir: Path) -> ImplementationDocument:
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "trust-operations-hub-manifest.json"}]
    data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = hub_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text("MusicForge Trust Operations Hub\n\nThis package contains a local cross-link trust operations readiness report and evidence binding indexes.\n", encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


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


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


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
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
