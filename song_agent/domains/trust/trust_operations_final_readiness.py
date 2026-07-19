from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

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
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS
from song_agent.domains.trust.trust_operations_final_readiness_contracts import FINAL_READINESS_EXPORT_ENTRIES as FINAL_READINESS_EXPORT_ENTRIES, FINAL_READINESS_SINGLE_SPECS as FINAL_READINESS_SINGLE_SPECS, TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS as TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS, TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION as TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION, final_readiness_hash as final_readiness_hash, final_readiness_history_event_hash as final_readiness_history_event_hash, final_readiness_history_event_payload_hash as final_readiness_history_event_payload_hash, final_readiness_history_hash as final_readiness_history_hash, final_readiness_manifest_hash as final_readiness_manifest_hash







TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_change_request"










class TrustOperationsFinalReadinessError(ValueError):
    pass


class TrustOperationsFinalReadinessNotFoundError(TrustOperationsFinalReadinessError):
    pass


class TrustOperationsFinalReadinessStateError(TrustOperationsFinalReadinessError):
    pass


class TrustOperationsFinalReadinessStore:
    def __init__(self, root: Path | str = Path(".musicforge") / "trust-operations" / "final-readiness") -> None:
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def report_path(self) -> Path:
        return self.root / "final-readiness-report.json"

    def certificate_path(self) -> Path:
        return self.root / "final-readiness-certificate.json"

    def evidence_index_path(self) -> Path:
        return self.root / "final-evidence-index.json"

    def signoff_path(self) -> Path:
        return self.root / "final-handoff-signoff.json"

    def history_path(self) -> Path:
        return self.root / "final-handoff-history.jsonl"

    def change_requests_dir(self) -> Path:
        return self.root / "change-requests"

    def change_request_path(self, change_request_id: str) -> Path:
        return self.change_requests_dir() / (_safe_id(change_request_id) + ".json")

    def export_dir(self) -> Path:
        return self.root / "export"

    def handoff_zip_path(self) -> Path:
        return self.root / "trust-operations-final-handoff.zip"

    def verification_report_path(self) -> Path:
        return self.root / "trust-operations-final-handoff-verification-report.json"

    def read_report(self, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.report_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Readiness report not found.")
        return value

    def read_certificate(self, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.certificate_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Readiness certificate not found.")
        return value

    def read_evidence_index(self, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.evidence_index_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final evidence index not found.")
        return value

    def read_signoff(self, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.signoff_path(), default=default or {})
        if not value and default is None:
            raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
        return value

    def list_change_requests(self) -> list[dict[str, Any]]:
        root = self.change_requests_dir()
        if not root.exists():
            return []
        return [_sanitize(row) for row in (_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))) if row]

    def summary(self) -> dict[str, Any]:
        state = self._signoff_state()
        return {
            "status": state.get("status") or "unsigned",
            "report": self.read_report(default={}),
            "certificate": self.read_certificate(default={}),
            "evidence_index": self.read_evidence_index(default={}),
            "signoff": self.read_signoff(default={}),
            "change_requests": self.list_change_requests(),
            "verification": _read_json_default(self.verification_report_path(), default={}),
        }

    def refresh_report(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = _verifier_payload(payload or {})
            self._ensure_unsigned("refresh final readiness")
            evidence_index, summaries = self._build_evidence_index(payload, now)
            rows = evidence_index.get("items", []) if isinstance(evidence_index.get("items"), list) else []
            blockers = []
            warnings: list[_InferenceType] = []
            for row in rows:
                if row.get("required") and row.get("status") != "passed":
                    blockers.append(_blocker(str(row.get("component_type") or "evidence"), f"Required evidence is not passed: {row.get('component_type')} {row.get('component_id')}"))
            summary = {
                "required_evidence_count": sum(1 for row in rows if row.get("required")),
                "passed_evidence_count": sum(1 for row in rows if row.get("status") == "passed"),
                "failed_evidence_count": sum(1 for row in rows if row.get("status") == "failed"),
                "missing_evidence_count": sum(1 for row in rows if row.get("status") == "missing"),
                "stale_evidence_count": sum(1 for row in rows if row.get("status") == "stale"),
                "manual_required_count": 0,
                "ready_for_signoff": not blockers,
            }
            source = self._report_source(rows)
            report = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE,
                "report_id": _safe_id(str(payload.get("report_id") or _next_id(self.root, "tofr"))),
                "generated_at": now,
                "status": "ready" if not blockers else "blocked",
                "source": source,
                "summary": summary,
                "rows": rows,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = final_readiness_hash(report)
            _write_json(self.evidence_index_path(), evidence_index)
            _write_json(self.report_path(), report)
            _write_json(self.root / "verification-summaries.json", {"summaries": summaries, "integrity_hash": stable_hash({"summaries": summaries})})
            self._append_history("final_readiness_refreshed", {"report_hash": report["integrity_hash"], "evidence_index_hash": evidence_index["integrity_hash"], "status": report["status"]}, now=now)
            return {"report": _sanitize(report), "evidence_index": _sanitize(evidence_index), "verification_summaries": _sanitize(summaries)}

    def create_certificate(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned("create final readiness certificate")
            report = self.read_report()
            index = self.read_evidence_index()
            self._ensure_report_ready(report, index)
            certificate = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE,
                "certificate_id": _safe_id(str(payload.get("certificate_id") or _next_id(self.root, "tofc"))),
                "created_at": now,
                "status": "ready",
                "readiness_level": "final_ready",
                "source": {
                    "report_hash": report.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                    "hub_verification_report_hash": report.get("source", {}).get("hub_verification_report_hash") if isinstance(report.get("source"), dict) else None,
                    "assurance_watch_signoff_verification_report_hash": report.get("source", {}).get("assurance_watch_signoff_verification_report_hash") if isinstance(report.get("source"), dict) else None,
                },
                "summary": {
                    "ready": True,
                    "required_evidence_count": report.get("summary", {}).get("required_evidence_count") if isinstance(report.get("summary"), dict) else None,
                    "passed_evidence_count": report.get("summary", {}).get("passed_evidence_count") if isinstance(report.get("summary"), dict) else None,
                    "blocking_findings": len(_as_list(report.get("blockers"))),
                },
                "public_summary": {
                    "statement": "Trust Operations evidence is final-ready for handoff.",
                    "generated_by": "MusicForge",
                    "version": __version__,
                },
            }
            certificate["integrity_hash"] = final_readiness_hash(certificate)
            _write_json(self.certificate_path(), certificate)
            self._append_history("final_certificate_created", {"certificate_hash": certificate["integrity_hash"], "report_hash": report.get("integrity_hash"), "evidence_index_hash": index.get("integrity_hash")}, now=now)
            return _sanitize(certificate)

    def sign(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned("sign final handoff")
            report = self.read_report()
            certificate = self.read_certificate()
            index = self.read_evidence_index()
            self._ensure_report_ready(report, index)
            self._ensure_certificate_current(certificate, report, index)
            if bool(payload.get("force")):
                raise TrustOperationsFinalReadinessStateError("Final Handoff force signoff is not supported.")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsFinalReadinessStateError("Final Handoff signoff reason must be at least 8 characters.")
            signed_by = sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120])
            role = sanitize_sensitive_text(str(payload.get("role") or "owner")[:80])
            signoff_id = _safe_id(str(payload.get("signoff_id") or _next_id(self.root, "tofsg")))
            source = self._signoff_source(report, certificate, index)
            decision = {"approved": True, "force": False, "exceptions": []}
            payload_hash = stable_hash({"signoff_id": signoff_id, "signed_by": signed_by, "role": role, "reason": reason, "source": source, "decision": decision})
            signoff = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE,
                "signoff_id": signoff_id,
                "status": "signed",
                "signed_at": now,
                "signed_by": signed_by,
                "role": role,
                "reason": reason,
                "source": source,
                "decision": decision,
                "payload_hash": payload_hash,
            }
            signoff["integrity_hash"] = final_readiness_hash(signoff)
            _write_json(self.signoff_path(), signoff)
            self._append_history(
                "final_handoff_signed",
                {
                    "signoff_id": signoff_id,
                    "signoff_hash": signoff["integrity_hash"],
                    "signed_by": signed_by,
                    "role": role,
                    "reason": reason,
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "certificate_hash": certificate.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                },
                now=now,
            )
            return _sanitize(signoff)

    def create_change_request(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsFinalReadinessStateError("Final Handoff change request reason must be at least 8 characters.")
            state = self._signoff_state()
            cr_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(), "tofcr")))
            cr = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": cr_id,
                "status": "draft",
                "created_at": now,
                "created_by": sanitize_sensitive_text(str(payload.get("created_by") or "local-operator")[:120]),
                "reason": reason,
                "source": {"target_signoff_hash": state.get("signoff_hash")},
                "approval": None,
                "applied": {"applied_at": None, "applied_reset_hash": None},
            }
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(cr_id), cr)
            self._append_history("change_request_created", {"change_request_id": cr_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            return _sanitize(cr)

    def approve_change_request(self, change_request_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            cr = self._read_change_request(change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "draft":
                raise TrustOperationsFinalReadinessStateError("Only draft Final Handoff change requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Final Handoff reset approved.")[:500]),
            }
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(change_request_id), cr)
            self._append_history("change_request_approved", {"change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            return _sanitize(cr)

    def reset_signoff(self, change_request_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            state = self._signoff_state()
            if state.get("status") != "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is not signed.")
            cr = self._read_change_request(change_request_id)
            self._ensure_change_request_integrity(cr)
            applied = _as_document(cr.get("applied"))
            if cr.get("status") != "approved" or applied.get("applied_at"):
                raise TrustOperationsFinalReadinessStateError("Approved unused Final Handoff change request is required.")
            source = _as_document(cr.get("source"))
            if source.get("target_signoff_hash") and source.get("target_signoff_hash") != state.get("signoff_hash"):
                raise TrustOperationsFinalReadinessStateError("Final Handoff change request does not target the current signoff.")
            applied["applied_at"] = now
            applied["applied_reset_hash"] = state.get("signoff_hash")
            cr["applied"] = applied
            cr["status"] = "applied"
            cr["integrity_hash"] = final_readiness_hash(cr)
            _write_json(self.change_request_path(change_request_id), cr)
            self._append_history("final_handoff_reset", {"signoff_hash": state.get("signoff_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]}, now=now)
            if self.signoff_path().exists():
                os.remove(_fs_path(self.signoff_path()))
            return {"status": "reset", "change_request": _sanitize(cr)}

    def export_handoff(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            signoff = self.read_signoff(default={})
            if not signoff and self._signoff_state().get("status") == "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is signed but signoff file is missing. Reset with an approved Change Request before export.")
            if not signoff:
                raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
            self._ensure_signoff_current(signoff)
            self._ensure_not_exported(str(signoff.get("integrity_hash") or ""))
            export_dir = self.export_dir()
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir / "verification-summaries")
            report = self.read_report()
            certificate = self.read_certificate()
            index = self.read_evidence_index()
            summaries = self._read_verification_summaries()
            _write_readme(export_dir)
            _write_json(export_dir / "final-readiness-report.json", report)
            _write_json(export_dir / "final-readiness-certificate.json", certificate)
            _write_json(export_dir / "final-evidence-index.json", index)
            _write_json(export_dir / "final-handoff-signoff.json", signoff)
            (export_dir / "final-handoff-history.jsonl").write_text(_read_text(self.history_path()), encoding="utf-8")
            change_requests_doc = self._change_requests_doc(signoff)
            _write_json(export_dir / "change-requests.json", change_requests_doc)
            for summary_path, summary in summaries.items():
                _write_json(export_dir / summary_path, summary)
            manifest = {
                "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Final Readiness", "version": __version__},
                "generated_at": now,
                "source": {
                    "report_hash": report.get("integrity_hash"),
                    "certificate_hash": certificate.get("integrity_hash"),
                    "evidence_index_hash": index.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "change_requests_hash": change_requests_doc.get("integrity_hash"),
                    "history_hash": final_readiness_history_hash(self._history_events()),
                    "verification_summaries_hash": stable_hash({"summaries": summaries}),
                },
                "summary": {"status": signoff.get("status"), "ready": report.get("status") == "ready"},
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-final-readiness-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = final_readiness_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-final-readiness-manifest.json", manifest)
            self._append_history("final_handoff_exported", {"signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_handoff_zip(self, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            signoff = self.read_signoff(default={})
            if not signoff and self._signoff_state().get("status") == "signed":
                raise TrustOperationsFinalReadinessStateError("Final Handoff is signed but signoff file is missing. Reset with an approved Change Request before building ZIP.")
            if not signoff:
                raise TrustOperationsFinalReadinessNotFoundError("Final Handoff signoff not found.")
            self._ensure_not_zipped(str(signoff.get("integrity_hash") or ""))
            export_dir = self.export_dir()
            manifest_path = export_dir / "trust-operations-final-readiness-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsFinalReadinessStateError("Final Handoff export is missing.")
            if manifest.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise TrustOperationsFinalReadinessStateError("Final Handoff export is stale.")
            zip_path = self.handoff_zip_path()
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = final_readiness_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "signoff_hash": signoff.get("integrity_hash")}
            self._append_history("final_handoff_zip_built", {"signoff_hash": signoff.get("integrity_hash"), "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]}, now=now)
            return _sanitize(info)

    def verify_handoff_zip(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.trust_operations_final_readiness_verifier import verify_trust_operations_final_handoff_package

        payload = payload or {}
        report = verify_trust_operations_final_handoff_package(self.handoff_zip_path(), strict=bool(payload.get("strict", False)), require_signed=bool(payload.get("require_signed", True)), require_current=bool(payload.get("require_current", True)), **_verifier_payload(payload))
        _write_json(self.verification_report_path(), report)
        return report

    def _build_evidence_index(self, payload: ImplementationDocument, now: str) -> tuple[ImplementationDocument, dict[str, ImplementationDocument]]:
        items: list[dict[str, Any]] = []
        summaries: dict[str, dict[str, Any]] = {}
        delivery_summary_rows: list[dict[str, Any]] = []
        for spec in FINAL_READINESS_SINGLE_SPECS:
            row, summary = self._single_evidence_row(spec, payload)
            items.append(row)
            summaries[str(spec["summary_path"])] = summary
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            for index, report_path in enumerate(_payload_paths(payload, str(spec["payload_keys"]), str(spec["payload_key"]))):
                report = _read_json_default(report_path, default={})
                component_id = _component_id_from_report(report, str(spec["component_id_prefix"]), index)
                row = _row_from_verification_report(str(spec["component_type"]), component_id, report, None, required=True)
                items.append(row)
                delivery_summary_rows.append(row)
        delivery_summary = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_final_delivery_verification_summary",
            "component_type": "delivery",
            "status": "passed" if delivery_summary_rows and all(row.get("status") == "passed" for row in delivery_summary_rows) else "failed",
            "items": delivery_summary_rows,
            "summary": {
                "item_count": len(delivery_summary_rows),
                "passed_count": sum(1 for row in delivery_summary_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in delivery_summary_rows if row.get("status") == "failed"),
            },
        }
        delivery_summary["integrity_hash"] = final_readiness_hash(delivery_summary)
        summaries["verification-summaries/delivery-verification-summary.json"] = delivery_summary
        evidence_index = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE,
            "created_at": now,
            "items": items,
            "summary": {
                "item_count": len(items),
                "required_count": sum(1 for row in items if row.get("required")),
                "passed_count": sum(1 for row in items if row.get("status") == "passed"),
            },
        }
        evidence_index["integrity_hash"] = final_readiness_hash(evidence_index)
        return evidence_index, summaries

    def _single_evidence_row(self, spec: dict[str, str], payload: ImplementationDocument) -> tuple[ImplementationDocument, ImplementationDocument]:
        package_path = _path_or_none(payload.get(spec["payload_path"]))
        report_path = _path_or_none(payload.get(spec["payload_report"]))
        report = _read_json_default(report_path, default={}) if report_path else {}
        manifest = _read_zip_json(package_path, spec["manifest_entry"]) if package_path else {}
        row = _row_from_verification_report(
            spec["component_type"],
            spec["component_id"],
            report,
            package_path,
            required=True,
            manifest_hash=manifest.get("integrity_hash"),
            expected_verification_package_type=spec["verification_package_type"],
            require_package=True,
        )
        summary = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_final_verification_summary",
            "component_type": spec["component_type"],
            "component_id": spec["component_id"],
            "expected_package_type": spec["package_type"],
            "expected_verification_package_type": spec["verification_package_type"],
            "status": row.get("status"),
            "package_sha256": row.get("package_sha256"),
            "package_size_bytes": row.get("package_size_bytes"),
            "manifest_hash": row.get("manifest_hash"),
            "verification_package_type": report.get("package_type"),
            "verification_report_hash": row.get("verification_report_hash"),
            "verification_status": row.get("verification_status"),
            "source_hash": report.get("source_hash"),
            "component_summary": _as_document(report.get("summary")),
        }
        summary["integrity_hash"] = final_readiness_hash(summary)
        return row, summary

    def _report_source(self, rows: list[ImplementationDocument]) -> ImplementationDocument:
        source: dict[str, Any] = {}
        delivery_rows = []
        for row in rows:
            component_type = str(row.get("component_type") or "")
            if component_type in {str(spec["component_type"]) for spec in DELIVERY_VERIFICATION_COMPONENTS}:
                delivery_rows.append({"component_type": component_type, "component_id": row.get("component_id"), "verification_report_hash": row.get("verification_report_hash")})
                continue
            source[f"{component_type}_verification_report_hash"] = row.get("verification_report_hash")
            source[f"{component_type}_zip_sha256"] = row.get("package_sha256")
            source[f"{component_type}_manifest_hash"] = row.get("manifest_hash")
        source["delivery_verification_set_hash"] = stable_hash({"delivery": sorted(delivery_rows, key=lambda row: (str(row.get("component_type")), str(row.get("component_id"))))})
        return source

    def _signoff_source(self, report: ImplementationDocument, certificate: ImplementationDocument, index: ImplementationDocument) -> ImplementationDocument:
        source = _as_document(report.get("source"))
        return {
            "final_readiness_report_hash": report.get("integrity_hash"),
            "final_readiness_certificate_hash": certificate.get("integrity_hash"),
            "final_evidence_index_hash": index.get("integrity_hash"),
            "hub_verification_report_hash": source.get("hub_verification_report_hash"),
            "assurance_watch_signoff_verification_report_hash": source.get("assurance_watch_signoff_verification_report_hash"),
            "delivery_verification_set_hash": source.get("delivery_verification_set_hash"),
        }

    def _ensure_report_ready(self, report: ImplementationDocument, index: ImplementationDocument) -> None:
        if report.get("integrity_hash") != final_readiness_hash(report):
            raise TrustOperationsFinalReadinessStateError("Final Readiness report integrity failed.")
        if index.get("integrity_hash") != final_readiness_hash(index):
            raise TrustOperationsFinalReadinessStateError("Final evidence index integrity failed.")
        if report.get("status") != "ready" or report.get("summary", {}).get("ready_for_signoff") is not True:
            raise TrustOperationsFinalReadinessStateError("Final Readiness report is not ready.")
        if report.get("rows") != index.get("items"):
            raise TrustOperationsFinalReadinessStateError("Final Readiness report does not match evidence index.")

    def _ensure_certificate_current(self, certificate: ImplementationDocument, report: ImplementationDocument, index: ImplementationDocument) -> None:
        if certificate.get("integrity_hash") != final_readiness_hash(certificate):
            raise TrustOperationsFinalReadinessStateError("Final Readiness certificate integrity failed.")
        source = _as_document(certificate.get("source"))
        if source.get("report_hash") != report.get("integrity_hash") or source.get("evidence_index_hash") != index.get("integrity_hash"):
            raise TrustOperationsFinalReadinessStateError("Final Readiness certificate is stale.")

    def _ensure_signoff_current(self, signoff: ImplementationDocument) -> None:
        if signoff.get("integrity_hash") != final_readiness_hash(signoff):
            raise TrustOperationsFinalReadinessStateError("Final Handoff signoff integrity failed.")
        report = self.read_report()
        certificate = self.read_certificate()
        index = self.read_evidence_index()
        self._ensure_report_ready(report, index)
        self._ensure_certificate_current(certificate, report, index)
        if signoff.get("source") != self._signoff_source(report, certificate, index):
            raise TrustOperationsFinalReadinessStateError("Final Handoff signoff source is stale. Reset before export.")

    def _change_requests_doc(self, signoff: ImplementationDocument) -> ImplementationDocument:
        rows = self.list_change_requests()
        doc = {
            "schema_version": TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE,
            "signoff_hash": signoff.get("integrity_hash"),
            "change_requests": rows,
            "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")},
        }
        doc["integrity_hash"] = final_readiness_hash(doc)
        return doc

    def _read_verification_summaries(self) -> dict[str, ImplementationDocument]:
        doc = _read_json_default(self.root / "verification-summaries.json", default={})
        summaries = _as_document(doc.get("summaries"))
        return {str(key): value for key, value in summaries.items() if isinstance(value, dict)}

    def _read_change_request(self, change_request_id: str) -> ImplementationDocument:
        request = _read_json_default(self.change_request_path(change_request_id), default={})
        if not request:
            raise TrustOperationsFinalReadinessNotFoundError(f"Final Handoff change request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: ImplementationDocument) -> None:
        if request.get("integrity_hash") != final_readiness_hash(request):
            raise TrustOperationsFinalReadinessStateError("Final Handoff change request integrity failed.")

    def _history_events(self) -> list[ImplementationDocument]:
        if not self.history_path().exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in _read_text(self.history_path()).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(_sanitize(item))
        return rows

    def _signoff_state(self) -> ImplementationDocument:
        active_hash: str | None = None
        active_id: str | None = None
        for event in self._history_events():
            event_type = event.get("event_type")
            payload = _as_document(event.get("payload"))
            signoff_hash = str(payload.get("signoff_hash") or "")
            if event_type == "final_handoff_signed" and signoff_hash:
                active_hash = signoff_hash
                active_id = str(payload.get("signoff_id") or "")
            elif event_type == "final_handoff_reset" and signoff_hash and signoff_hash == active_hash:
                active_hash = None
                active_id = None
        return {"status": "signed" if active_hash else "unsigned", "signoff_hash": active_hash, "signoff_id": active_id}

    def _ensure_unsigned(self, action: str) -> None:
        if self._signoff_state().get("status") == "signed":
            raise TrustOperationsFinalReadinessStateError(f"Final Handoff is signed. Reset with an approved Change Request before attempting to {action}.")

    def _history_has_event(self, event_type: str, signoff_hash: str) -> bool:
        for event in self._history_events():
            payload = _as_document(event.get("payload"))
            if event.get("event_type") == event_type and payload.get("signoff_hash") == signoff_hash:
                return True
        return False

    def _ensure_not_exported(self, signoff_hash: str) -> None:
        if self._history_has_event("final_handoff_exported", signoff_hash):
            raise TrustOperationsFinalReadinessStateError("Final Handoff was already exported for this signoff. Reset before rebuilding export.")

    def _ensure_not_zipped(self, signoff_hash: str) -> None:
        if self._history_has_event("final_handoff_zip_built", signoff_hash):
            raise TrustOperationsFinalReadinessStateError("Final Handoff ZIP was already built for this signoff. Reset before rebuilding ZIP.")

    def _append_history(self, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        events = self._history_events()
        event = {
            "event_id": _safe_id(_next_id(self.root, "tofh")),
            "event_type": event_type,
            "created_at": now,
            "payload": _sanitize(payload),
            "previous_event_hash": events[-1].get("event_hash") if events else None,
        }
        event["payload_hash"] = final_readiness_history_event_payload_hash(event)
        event["event_hash"] = final_readiness_history_event_hash(event)
        _append_jsonl(self.history_path(), event)

















def _verifier_payload(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "hub_package_path": payload.get("hub_package_path"),
        "hub_verification_report_path": payload.get("hub_verification_report_path"),
        "release_verification_paths": payload.get("release_verification_paths") or ([payload["release_verification_path"]] if payload.get("release_verification_path") else []),
        "distribution_verification_paths": payload.get("distribution_verification_paths") or ([payload["distribution_verification_path"]] if payload.get("distribution_verification_path") else []),
        "submission_verification_paths": payload.get("submission_verification_paths") or ([payload["submission_verification_path"]] if payload.get("submission_verification_path") else []),
        "submission_evidence_verification_paths": payload.get("submission_evidence_verification_paths") or ([payload["submission_evidence_verification_path"]] if payload.get("submission_evidence_verification_path") else []),
        "release_operations_verification_paths": payload.get("release_operations_verification_paths") or ([payload["release_operations_verification_path"]] if payload.get("release_operations_verification_path") else []),
        "incident_board_package_path": payload.get("incident_board_package_path"),
        "incident_board_verification_report_path": payload.get("incident_board_verification_report_path"),
        "incident_knowledge_package_path": payload.get("incident_knowledge_package_path"),
        "incident_knowledge_verification_report_path": payload.get("incident_knowledge_verification_report_path"),
        "control_assessment_package_path": payload.get("control_assessment_package_path") or payload.get("control_package_path") or payload.get("trust_control_package_path"),
        "control_verification_report_path": payload.get("control_verification_report_path") or payload.get("trust_control_verification_report_path"),
        "control_signoff_archive_path": payload.get("control_signoff_archive_path") or payload.get("trust_control_signoff_archive_path"),
        "control_signoff_verification_report_path": payload.get("control_signoff_verification_report_path") or payload.get("trust_control_signoff_verification_report_path"),
        "continuous_assurance_archive_path": payload.get("continuous_assurance_archive_path") or payload.get("assurance_archive_path"),
        "continuous_assurance_verification_report_path": payload.get("continuous_assurance_verification_report_path") or payload.get("assurance_verification_report_path"),
        "assurance_watch_package_path": payload.get("assurance_watch_package_path") or payload.get("watch_package_path"),
        "assurance_watch_verification_report_path": payload.get("assurance_watch_verification_report_path") or payload.get("watch_verification_report_path"),
        "assurance_watch_signoff_archive_path": payload.get("assurance_watch_signoff_archive_path"),
        "assurance_watch_signoff_verification_report_path": payload.get("assurance_watch_signoff_verification_report_path"),
    }


def _row_from_verification_report(
    component_type: str,
    component_id: str,
    report: ImplementationDocument,
    package_path: Path | None,
    *,
    required: bool,
    manifest_hash: Any | None = None,
    expected_verification_package_type: str | None = None,
    require_package: bool = False,
) -> ImplementationDocument:
    package_sha = _sha256(package_path) if package_path else report.get("zip_sha256")
    package_size = os.stat(_fs_path(package_path)).st_size if package_path and package_path.exists() else report.get("zip_size_bytes")
    report_hash = verification_hash(report) if report else None
    mismatch_reasons: list[str] = []
    if not report:
        status = "missing"
    elif require_package and (package_path is None or not package_path.exists()):
        status = "missing"
        mismatch_reasons.append("package_missing")
    elif expected_verification_package_type and report.get("package_type") != expected_verification_package_type:
        status = "failed"
        mismatch_reasons.append("verification_package_type")
    elif report.get("status") != "passed":
        status = "failed"
        mismatch_reasons.append("verification_status")
    else:
        status = "passed"
    if report and package_path is not None and package_path.exists():
        if report.get("zip_sha256") and report.get("zip_sha256") != package_sha:
            status = "stale"
            mismatch_reasons.append("zip_sha256")
        if report.get("zip_size_bytes") and report.get("zip_size_bytes") != package_size:
            status = "stale"
            mismatch_reasons.append("zip_size_bytes")
        if report.get("manifest_hash") and manifest_hash and report.get("manifest_hash") != manifest_hash:
            status = "stale"
            mismatch_reasons.append("manifest_hash")
    return {
        "evidence_id": f"{component_type}:{component_id}",
        "component_type": component_type,
        "component_id": component_id,
        "required": required,
        "status": status,
        "package_type": report.get("package_type") if report else None,
        "package_sha256": package_sha,
        "package_size_bytes": package_size,
        "manifest_hash": manifest_hash or report.get("manifest_hash"),
        "verification_package_type": report.get("package_type") if report else None,
        "verification_report_hash": report_hash,
        "verification_status": report.get("status") if report else None,
        "blocker_count": len(_as_list(report.get("blockers"))),
        "mismatch_reasons": sorted(set(mismatch_reasons)),
    }


def _payload_paths(payload: ImplementationDocument, plural_key: str, singular_key: str) -> list[Path]:
    values = payload.get(plural_key)
    paths: list[Path] = []
    if isinstance(values, (list, tuple)):
        paths.extend(path for item in values if (path := _path_or_none(item)) is not None)
    elif values:
        path = _path_or_none(values)
        if path is not None:
            paths.append(path)
    if payload.get(singular_key):
        path = _path_or_none(payload.get(singular_key))
        if path is not None:
            paths.append(path)
    return paths


def _component_id_from_report(report: ImplementationDocument, prefix: str, index: int) -> str:
    summary = _as_document(report.get("summary"))
    for key in ("component_id", "target_id", "submission_id", "release_id", "operations_id", "package_id"):
        if report.get(key):
            return _safe_id(str(report.get(key)))
        if summary.get(key):
            return _safe_id(str(summary.get(key)))
    return f"{prefix}-{index + 1:03d}"


def _path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(value)


def _blocker(code: str, message: str) -> ImplementationDocument:
    item = {"code": code, "message": message, "severity": "blocking"}
    item["integrity_hash"] = stable_hash(item)
    return item


def _read_json_default(path: Path | None, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        if path is None or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path or not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "MusicForge Trust Operations Final Readiness Handoff Pack\n"
        "This package contains final signed Trust Operations readiness evidence summaries.\n",
        encoding="utf-8",
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


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


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes: list[int] = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fs_path(path: Path) -> str:
    return str(path)
