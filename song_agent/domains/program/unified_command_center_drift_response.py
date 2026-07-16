from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore as UnifiedCommandCenterContinuousReviewStore
from song_agent.domains.program.unified_command_center_drift_response_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package, write_unified_command_center_drift_response_verification_report as write_unified_command_center_drift_response_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore


class UnifiedCommandCenterDriftResponseError(ValueError):
    pass


class UnifiedCommandCenterDriftResponseNotFoundError(UnifiedCommandCenterDriftResponseError):
    pass


class UnifiedCommandCenterDriftResponseStateError(UnifiedCommandCenterDriftResponseError):
    pass


class UnifiedCommandCenterDriftResponseStore:
    def __init__(
        self,
        center_store: UnifiedCommandCenterStore | None = None,
        *,
        signoff_store: UnifiedCommandCenterSignoffStore | None = None,
        handoff_store: UnifiedCommandCenterHandoffStore | None = None,
        review_store: UnifiedCommandCenterContinuousReviewStore | None = None,
    ) -> None:
        self.center_store = center_store or UnifiedCommandCenterStore()
        self.signoff_store = signoff_store or UnifiedCommandCenterSignoffStore(self.center_store)
        self.handoff_store = handoff_store or UnifiedCommandCenterHandoffStore(self.signoff_store)
        self.review_store = review_store or UnifiedCommandCenterContinuousReviewStore(self.center_store, signoff_store=self.signoff_store, handoff_store=self.handoff_store)
        self.lock = threading.RLock()

    def responses_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "drift-responses"

    def response_dir(self, center_id: str, response_id: str) -> Path:
        return self.responses_dir(center_id) / _safe_id(response_id)

    def case_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-case.json"

    def source_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-source.json"

    def plan_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-plan.json"

    def queue_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "action-queue.json"

    def results_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "action-results.json"

    def cr_bindings_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "change-request-bindings.json"

    def cr_binding_report_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "change-request-binding-report.json"

    def recheck_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "recheck-summary.json"

    def closeout_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "closeout-report.json"

    def fingerprints_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "package-fingerprints.json"

    def events_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "events.jsonl"

    def manifest_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "manifest.json"

    def zip_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "musicforge-unified-command-center-drift-response.zip"

    def verification_report_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "drift-response-verification-report.json"

    def list_responses(self, center_id: str) -> list[dict[str, Any]]:
        if not self.responses_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.responses_dir(center_id).glob("uccdr-*")):
            case_path = path / "response-case.json"
            if case_path.exists():
                rows.append(read_json(case_path))
        return rows

    def read_response(self, center_id: str, response_id: str) -> dict[str, Any]:
        case = self.read_case(center_id, response_id)
        docs = {"case": case}
        for key, func in (
            ("source", self.source_path),
            ("plan", self.plan_path),
            ("queue", self.queue_path),
            ("results", self.results_path),
            ("change_request_bindings", self.cr_bindings_path),
            ("change_request_binding_report", self.cr_binding_report_path),
            ("recheck", self.recheck_path),
            ("closeout", self.closeout_path),
            ("package_fingerprints", self.fingerprints_path),
            ("manifest", self.manifest_path),
        ):
            path = func(center_id, response_id)
            docs[key] = read_json(path) if path.exists() else {}
        return docs

    def read_case(self, center_id: str, response_id: str) -> dict[str, Any]:
        path = self.case_path(center_id, response_id)
        if not path.exists():
            raise UnifiedCommandCenterDriftResponseNotFoundError(f"Unified Command Center Drift Response not found: {response_id}.")
        return read_json(path)

    def create_response(self, center_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            review_id = str(payload.get("source_review_id") or payload.get("review_id") or "")
            if not review_id:
                raise UnifiedCommandCenterDriftResponseStateError("source_review_id is required.")
            source_docs = self.review_store.read_review(center_id, review_id)
            drift = source_docs.get("drift_report") if isinstance(source_docs.get("drift_report"), dict) else {}
            incidents = source_docs.get("incident_board") if isinstance(source_docs.get("incident_board"), dict) else {}
            if drift.get("status") != "failed" or int((drift.get("summary") or {}).get("blocking_drift_count") or 0) <= 0:
                raise UnifiedCommandCenterDriftResponseStateError("Drift Response requires a failed Continuous Review with blocking drift.")
            response_id = str(payload.get("response_id") or self._next_response_id(center_id))
            if self.case_path(center_id, response_id).exists():
                raise UnifiedCommandCenterDriftResponseStateError(f"Drift Response already exists: {response_id}.")
            response_dir = self.response_dir(center_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            now = now_iso()
            source = _source_document(center_id, response_id, source_docs, self.review_store.zip_path(center_id, review_id), self.review_store.verification_report_path(center_id, review_id))
            plan = _plan_document(center_id, response_id, drift, incidents, source)
            queue = _queue_document(center_id, response_id, plan, source)
            results = _results_document(center_id, response_id, source.get("source_hash"), [])
            cr_bindings = _cr_bindings_document(center_id, response_id, source.get("source_hash"), [])
            recheck = _recheck_document(center_id, response_id, source.get("source_hash"), None)
            closeout = _closeout_document(center_id, response_id, source.get("source_hash"), queue, results, cr_bindings, recheck, status="open")
            fingerprints = _fingerprints_document(center_id, response_id, source)
            case = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_drift_response_case",
                    "center_id": center_id,
                    "response_id": response_id,
                    "source_review_id": review_id,
                    "status": "open",
                    "created_at": now,
                    "created_by": _bounded(payload.get("created_by") or "release-owner", 120),
                    "severity": _highest_severity(drift),
                    "source": {
                        "source_hash": source.get("source_hash"),
                        "continuous_review_zip_sha256": source.get("source_review", {}).get("zip_sha256"),
                        "continuous_review_manifest_hash": source.get("source_review", {}).get("manifest_hash"),
                        "continuous_review_verification_hash": source.get("source_review", {}).get("verification_hash"),
                        "drift_report_hash": source.get("drift_report_hash"),
                        "incident_board_hash": source.get("incident_board_hash"),
                    },
                }
            )
            case["integrity_hash"] = _integrity_hash(case)
            self._write_all(center_id, response_id, case, source, plan, queue, results, cr_bindings, recheck, closeout, fingerprints)
            self._append_event(center_id, response_id, "response_created", {"response_id": response_id, "source_review_id": review_id, "source_hash": source.get("source_hash")})
            return {"case": case, "source": source, "plan": plan, "queue": queue, "closeout": closeout}

    def run_safe(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            docs = self._required_docs(center_id, response_id)
            self._ensure_open(docs)
            results = []
            for item in docs["queue"].get("items", []):
                if not isinstance(item, dict):
                    continue
                if item.get("safe"):
                    results.append({"item_id": item.get("item_id"), "action": item.get("action"), "status": "completed", "message": "Safe preparation action completed."})
                else:
                    results.append({"item_id": item.get("item_id"), "action": item.get("action"), "status": "manual_required", "message": "Manual Change Request evidence is required."})
            result_doc = _results_document(center_id, response_id, docs["source"].get("source_hash"), results)
            write_json(self.results_path(center_id, response_id), result_doc)
            self._append_event(center_id, response_id, "safe_actions_run", {"result_hash": result_doc.get("integrity_hash")})
            return result_doc

    def bind_change_request(self, center_id: str, response_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            docs = self._required_docs(center_id, response_id)
            self._ensure_open(docs)
            item_id = str(payload.get("item_id") or "")
            if not item_id:
                raise UnifiedCommandCenterDriftResponseStateError("item_id is required.")
            manual_ids = {str(row.get("item_id")) for row in docs["queue"].get("items", []) if isinstance(row, dict) and not row.get("safe")}
            if item_id not in manual_ids:
                raise UnifiedCommandCenterDriftResponseStateError("Change Request binding must target a manual action item.")
            existing_rows = [row for row in docs["change_request_bindings"].get("items", []) if isinstance(row, dict)]
            if any(row.get("item_id") == item_id for row in existing_rows):
                raise UnifiedCommandCenterDriftResponseStateError("Change Request binding already exists for this item.")
            item = next((row for row in docs["queue"].get("items", []) if isinstance(row, dict) and str(row.get("item_id")) == item_id), {})
            change_request_id = _bounded(payload.get("change_request_id") or f"cr-{item_id}", 160)
            if any(row.get("change_request_id") == change_request_id for row in existing_rows):
                raise UnifiedCommandCenterDriftResponseStateError("Change Request id is already bound to this Drift Response.")
            status = str(payload.get("status") or payload.get("change_request_status") or "").strip().lower()
            if status != "approved":
                raise UnifiedCommandCenterDriftResponseStateError("Change Request binding must be approved.")
            approval = {
                "change_request_id": change_request_id,
                "status": "approved",
                "approved_by": _bounded(payload.get("approved_by") or "reviewer", 120),
                "approved_at": _bounded(payload.get("approved_at") or now_iso(), 80),
                "reason": _bounded(payload.get("reason") or "Approved drift response manual action.", 1000),
                "evidence_hash": stable_hash(sanitize_metadata(payload.get("evidence") or {})) if isinstance(payload.get("evidence"), dict) else None,
            }
            binding = sanitize_metadata(
                {
                    "item_id": item_id,
                    "source_drift_id": item.get("source_drift_id"),
                    "component_type": item.get("component_type"),
                    "component_id": item.get("component_id"),
                    "severity": item.get("severity"),
                    "action": item.get("action"),
                    **approval,
                    "approval_hash": stable_hash(approval),
                }
            )
            binding["binding_hash"] = stable_hash({key: value for key, value in binding.items() if key != "binding_hash"})
            existing_rows.append(binding)
            doc = _cr_bindings_document(center_id, response_id, docs["source"].get("source_hash"), existing_rows)
            write_json(self.cr_bindings_path(center_id, response_id), doc)
            proof_report = _cr_binding_report_document(center_id, response_id, docs["source"].get("source_hash"), docs["queue"], doc)
            write_json(self.cr_binding_report_path(center_id, response_id), proof_report)
            self._append_event(center_id, response_id, "change_request_bound", {"item_id": item_id, "change_request_id": binding.get("change_request_id"), "bindings_hash": doc.get("integrity_hash"), "proof_report_hash": proof_report.get("integrity_hash")})
            return doc

    def bind_recheck(self, center_id: str, response_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            docs = self._required_docs(center_id, response_id)
            self._ensure_open(docs)
            review_id = str(payload.get("recheck_review_id") or payload.get("review_id") or "")
            if not review_id:
                raise UnifiedCommandCenterDriftResponseStateError("recheck_review_id is required.")
            recheck_docs = self.review_store.read_review(center_id, review_id)
            drift = recheck_docs.get("drift_report") if isinstance(recheck_docs.get("drift_report"), dict) else {}
            incidents = recheck_docs.get("incident_board") if isinstance(recheck_docs.get("incident_board"), dict) else {}
            if drift.get("status") != "passed" or incidents.get("status") not in {"clear", None}:
                raise UnifiedCommandCenterDriftResponseStateError("Recheck Continuous Review must be clear before binding.")
            review_zip = Path(payload.get("recheck_review_zip") or self.review_store.zip_path(center_id, review_id))
            verification_path = Path(payload.get("recheck_review_verification_report") or self.review_store.verification_report_path(center_id, review_id))
            verification = read_json(verification_path) if verification_path.exists() else {}
            if verification.get("status") != "passed" or not _integrity_ok(verification):
                raise UnifiedCommandCenterDriftResponseStateError("Recheck Continuous Review verification must be passed.")
            binding = _review_binding(review_id, review_zip, verification_path, verification, drift, incidents)
            doc = _recheck_document(center_id, response_id, docs["source"].get("source_hash"), binding)
            write_json(self.recheck_path(center_id, response_id), doc)
            self._append_event(center_id, response_id, "recheck_bound", {"recheck_review_id": review_id, "recheck_hash": doc.get("integrity_hash")})
            return doc

    def closeout(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            docs = self._required_docs(center_id, response_id)
            self._ensure_open(docs)
            proof_report = _cr_binding_report_document(center_id, response_id, docs["source"].get("source_hash"), docs["queue"], docs["change_request_bindings"])
            write_json(self.cr_binding_report_path(center_id, response_id), proof_report)
            closeout = _closeout_document(
                center_id,
                response_id,
                docs["source"].get("source_hash"),
                docs["queue"],
                docs["results"],
                docs["change_request_bindings"],
                docs["recheck"],
                status="closed",
                closed_by=_bounded(payload.get("closed_by") or "release-owner", 120),
                reason=_bounded(payload.get("reason") or "Drift response closed after clear recheck.", 1000),
            )
            if closeout.get("status") != "closed":
                blocker_ids = [str(row.get("blocker_id") if isinstance(row, dict) else row) for row in closeout.get("blockers", [])]
                raise UnifiedCommandCenterDriftResponseStateError("Drift Response closeout is blocked: " + ", ".join(blocker_ids))
            write_json(self.closeout_path(center_id, response_id), closeout)
            case = docs["case"]
            case["status"] = "closed"
            case["closed_at"] = closeout.get("closed_at")
            case["closeout_hash"] = closeout.get("integrity_hash")
            case["integrity_hash"] = _integrity_hash(case)
            write_json(self.case_path(center_id, response_id), case)
            self._append_event(center_id, response_id, "response_closed", {"closeout_hash": closeout.get("integrity_hash")})
            return closeout

    def export_package(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            docs = self._required_docs(center_id, response_id)
            if docs["closeout"].get("status") != "closed":
                raise UnifiedCommandCenterDriftResponseStateError("Drift Response must be closed before export.")
            self._write_manifest(center_id, response_id, docs)
            return {"status": docs["closeout"].get("status"), "center_id": center_id, "response_id": response_id, "export_dir": str(self.response_dir(center_id, response_id)), "manifest": read_json(self.manifest_path(center_id, response_id))}

    def build_zip(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            exported = self.export_package(center_id, response_id, payload or {})
            response_dir = self.response_dir(center_id, response_id)
            zip_path = self.zip_path(center_id, response_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for entry in sorted(REQUIRED_ENTRIES):
                    if entry == "manifest.json":
                        continue
                    path = response_dir / entry
                    if path.exists():
                        archive.write(path, entry)
                archive.write(self.manifest_path(center_id, response_id), "manifest.json")
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(center_id, response_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(center_id, response_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for entry in sorted(REQUIRED_ENTRIES):
                    archive.write(response_dir / entry, entry)
            return {"status": exported.get("status"), "center_id": center_id, "response_id": response_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_package(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        source = read_json(self.source_path(center_id, response_id)) if self.source_path(center_id, response_id).exists() else {}
        recheck = read_json(self.recheck_path(center_id, response_id)) if self.recheck_path(center_id, response_id).exists() else {}
        source_review_id = str(source.get("source_review_id") or "")
        recheck_review_id = str((recheck.get("review") or {}).get("review_id") or "")
        report = verify_unified_command_center_drift_response_package(
            self.zip_path(center_id, response_id),
            strict=bool(payload.get("strict", True)),
            require_closed=bool(payload.get("require_closed", True)),
            require_recheck_clear=bool(payload.get("require_recheck_clear", True)),
            require_current_review=bool(payload.get("require_current_review", True)),
            source_review_zip_path=payload.get("source_review_zip") or payload.get("source_review_zip_path") or (self.review_store.zip_path(center_id, source_review_id) if source_review_id else None),
            source_review_verification_report_path=payload.get("source_review_verification_report") or payload.get("source_review_verification_report_path") or (self.review_store.verification_report_path(center_id, source_review_id) if source_review_id else None),
            recheck_review_zip_path=payload.get("recheck_review_zip") or payload.get("recheck_review_zip_path") or (self.review_store.zip_path(center_id, recheck_review_id) if recheck_review_id else None),
            recheck_review_verification_report_path=payload.get("recheck_review_verification_report") or payload.get("recheck_review_verification_report_path") or (self.review_store.verification_report_path(center_id, recheck_review_id) if recheck_review_id else None),
            archive_zip_path=payload.get("archive_zip") or payload.get("archive_zip_path") or self.signoff_store.archive_zip_path(center_id),
            archive_verification_report_path=payload.get("archive_verification_report") or payload.get("archive_verification_report_path") or self.signoff_store.archive_verification_report_path(center_id),
            handoff_zip_path=payload.get("handoff_zip") or payload.get("handoff_zip_path") or self.handoff_store.zip_path(center_id),
            handoff_verification_report_path=payload.get("handoff_verification_report") or payload.get("handoff_verification_report_path") or self.handoff_store.verification_report_path(center_id),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.center_store.zip_path(center_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.center_store.verification_report_path(center_id),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_store.signoff_binding_path(center_id),
            change_request_binding_report_path=payload.get("change_request_binding_report") or payload.get("change_request_binding_report_path") or self.cr_binding_report_path(center_id, response_id),
        )
        write_unified_command_center_drift_response_verification_report(report, self.verification_report_path(center_id, response_id))
        return report

    def gate(
        self,
        center_id: str,
        *,
        required: bool = True,
        response_id: str | None = None,
        response_zip_path: Path | str | None = None,
        response_verification_report_path: Path | str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        rid = response_id or self._latest_response_id(center_id)
        zip_path = Path(response_zip_path) if response_zip_path else self.zip_path(center_id, rid)
        report_path = Path(response_verification_report_path) if response_verification_report_path else self.verification_report_path(center_id, rid)
        if not zip_path.exists():
            return _gate_failed("Unified Command Center Drift Response ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Command Center Drift Response verification report is missing.")
        try:
            source = read_json(self.source_path(center_id, rid)) if self.source_path(center_id, rid).exists() else {}
            recheck = read_json(self.recheck_path(center_id, rid)) if self.recheck_path(center_id, rid).exists() else {}
            source_review_id = str(source.get("source_review_id") or "")
            recheck_review_id = str((recheck.get("review") or {}).get("review_id") or "")
            external = read_json(report_path)
            runtime = verify_unified_command_center_drift_response_package(
                zip_path,
                strict=True,
                require_closed=True,
                require_recheck_clear=True,
                require_current_review=True,
                source_review_zip_path=payload.get("source_review_zip_path") or payload.get("source_review_zip") or (self.review_store.zip_path(center_id, source_review_id) if source_review_id else None),
                source_review_verification_report_path=payload.get("source_review_verification_report_path") or payload.get("source_review_verification_report") or (self.review_store.verification_report_path(center_id, source_review_id) if source_review_id else None),
                recheck_review_zip_path=payload.get("recheck_review_zip_path") or payload.get("recheck_review_zip") or (self.review_store.zip_path(center_id, recheck_review_id) if recheck_review_id else None),
                recheck_review_verification_report_path=payload.get("recheck_review_verification_report_path") or payload.get("recheck_review_verification_report") or (self.review_store.verification_report_path(center_id, recheck_review_id) if recheck_review_id else None),
                archive_zip_path=payload.get("archive_zip_path") or self.signoff_store.archive_zip_path(center_id),
                archive_verification_report_path=payload.get("archive_verification_report_path") or self.signoff_store.archive_verification_report_path(center_id),
                handoff_zip_path=payload.get("handoff_zip_path") or self.handoff_store.zip_path(center_id),
                handoff_verification_report_path=payload.get("handoff_verification_report_path") or self.handoff_store.verification_report_path(center_id),
                command_center_zip_path=payload.get("command_center_zip_path") or self.center_store.zip_path(center_id),
                command_center_verification_report_path=payload.get("command_center_verification_report_path") or self.center_store.verification_report_path(center_id),
                signoff_binding_path=payload.get("signoff_binding_path") or self.signoff_store.signoff_binding_path(center_id),
                change_request_binding_report_path=payload.get("change_request_binding_report_path") or payload.get("change_request_binding_report") or self.cr_binding_report_path(center_id, rid),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Command Center Drift Response verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Drift Response verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Drift Response verification does not match current ZIP.", verification=runtime)
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Drift Response gate passed.", "response_id": rid, "zip_sha256": runtime.get("zip_sha256"), "manifest_hash": runtime.get("manifest_hash"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(f"Unified Command Center Drift Response gate failed: {sanitize_sensitive_text(str(exc))}")

    def _required_docs(self, center_id: str, response_id: str) -> ImplementationDocument:
        docs = {
            "case": self.read_case(center_id, response_id),
            "source": _read_json_required(self.source_path(center_id, response_id)),
            "plan": _read_json_required(self.plan_path(center_id, response_id)),
            "queue": _read_json_required(self.queue_path(center_id, response_id)),
            "results": _read_json_required(self.results_path(center_id, response_id)),
            "change_request_bindings": _read_json_required(self.cr_bindings_path(center_id, response_id)),
            "recheck": _read_json_required(self.recheck_path(center_id, response_id)),
            "closeout": _read_json_required(self.closeout_path(center_id, response_id)),
            "package_fingerprints": _read_json_required(self.fingerprints_path(center_id, response_id)),
        }
        for key, doc in docs.items():
            if not _integrity_ok(doc):
                raise UnifiedCommandCenterDriftResponseStateError(f"Drift Response {key} integrity failed.")
        return docs

    def _write_all(self, center_id: str, response_id: str, case: ImplementationDocument, source: ImplementationDocument, plan: ImplementationDocument, queue: ImplementationDocument, results: ImplementationDocument, cr_bindings: ImplementationDocument, recheck: ImplementationDocument, closeout: ImplementationDocument, fingerprints: ImplementationDocument) -> None:
        write_json(self.case_path(center_id, response_id), case)
        write_json(self.source_path(center_id, response_id), source)
        write_json(self.plan_path(center_id, response_id), plan)
        write_json(self.queue_path(center_id, response_id), queue)
        write_json(self.results_path(center_id, response_id), results)
        write_json(self.cr_bindings_path(center_id, response_id), cr_bindings)
        write_json(self.cr_binding_report_path(center_id, response_id), _cr_binding_report_document(center_id, response_id, source.get("source_hash"), queue, cr_bindings))
        write_json(self.recheck_path(center_id, response_id), recheck)
        write_json(self.closeout_path(center_id, response_id), closeout)
        write_json(self.fingerprints_path(center_id, response_id), fingerprints)
        self._write_readme(center_id, response_id, closeout)

    def _write_readme(self, center_id: str, response_id: str, closeout: ImplementationDocument) -> None:
        text = "\n".join(
            [
                "MusicForge Unified Command Center Drift Response",
                "",
                f"Center: {center_id}",
                f"Response: {response_id}",
                f"Status: {closeout.get('status')}",
                "",
                "Verify with verify-unified-command-center-drift-response-package and the current Continuous Review evidence.",
                "",
            ]
        )
        (self.response_dir(center_id, response_id) / "README.txt").write_text(text, encoding="utf-8")

    def _write_manifest(self, center_id: str, response_id: str, docs: ImplementationDocument) -> None:
        self._write_readme(center_id, response_id, docs["closeout"])
        response_dir = self.response_dir(center_id, response_id)
        files = []
        for entry in sorted(REQUIRED_ENTRIES - {"manifest.json"}):
            files.append(_file_record(response_dir / entry, entry))
        manifest = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
                "package_type": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE,
                "center_id": center_id,
                "response_id": response_id,
                "created_at": now_iso(),
                "status": docs["closeout"].get("status"),
                "source": {
                    "response_case_hash": docs["case"].get("integrity_hash"),
                    "response_source_hash": docs["source"].get("integrity_hash"),
                    "response_plan_hash": docs["plan"].get("integrity_hash"),
                    "action_queue_hash": docs["queue"].get("integrity_hash"),
                    "action_results_hash": docs["results"].get("integrity_hash"),
                    "change_request_bindings_hash": docs["change_request_bindings"].get("integrity_hash"),
                    "recheck_summary_hash": docs["recheck"].get("integrity_hash"),
                    "closeout_report_hash": docs["closeout"].get("integrity_hash"),
                    "package_fingerprints_hash": docs["package_fingerprints"].get("integrity_hash"),
                    "source_hash": docs["source"].get("source_hash"),
                },
                "summary": docs["closeout"].get("summary", {}),
                "files": files,
                "zip": {},
            }
        )
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(self.manifest_path(center_id, response_id), manifest)

    def _append_event(self, center_id: str, response_id: str, event_type: str, payload: ImplementationDocument) -> None:
        path = self.events_path(center_id, response_id)
        previous = ""
        if path.exists():
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous = str(json.loads(lines[-1]).get("event_hash") or "")
        event = sanitize_metadata({"event_type": event_type, "created_at": now_iso(), "response_id": response_id, "center_id": center_id, "previous_event_hash": previous, "payload": payload})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _ensure_open(self, docs: ImplementationDocument) -> None:
        if docs["case"].get("status") == "closed" or docs["closeout"].get("status") == "closed":
            raise UnifiedCommandCenterDriftResponseStateError("Drift Response is closed.")

    def _next_response_id(self, center_id: str) -> str:
        existing = []
        if self.responses_dir(center_id).exists():
            for path in self.responses_dir(center_id).glob("uccdr-*"):
                try:
                    existing.append(int(path.name.rsplit("-", 1)[-1]))
                except ValueError:
                    continue
        return f"uccdr-{(max(existing) + 1) if existing else 1:06d}"

    def _latest_response_id(self, center_id: str) -> str:
        rows = self.list_responses(center_id)
        if not rows:
            raise UnifiedCommandCenterDriftResponseNotFoundError("Unified Command Center Drift Response not found.")
        return str(rows[-1].get("response_id"))


def _source_document(center_id: str, response_id: str, source_docs: ImplementationDocument, review_zip_path: Path, verification_path: Path) -> ImplementationDocument:
    review_id = str(source_docs.get("plan", {}).get("review_id") or source_docs.get("drift_report", {}).get("review_id") or "")
    drift = source_docs.get("drift_report") if isinstance(source_docs.get("drift_report"), dict) else {}
    incidents = source_docs.get("incident_board") if isinstance(source_docs.get("incident_board"), dict) else {}
    verification = read_json(verification_path) if verification_path.exists() else {}
    review_binding = _review_binding(review_id, review_zip_path, verification_path, verification, drift, incidents)
    source_hash = stable_hash({"center_id": center_id, "response_id": response_id, "source_review": review_binding, "drift_report_hash": drift.get("integrity_hash"), "incident_board_hash": incidents.get("integrity_hash")})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_response_source",
            "center_id": center_id,
            "response_id": response_id,
            "source_review_id": review_id,
            "source_review": review_binding,
            "drift_report_hash": drift.get("integrity_hash"),
            "incident_board_hash": incidents.get("integrity_hash"),
            "source_hash": source_hash,
            "tool": {"name": "MusicForge Unified Command Center Drift Response", "version": __version__},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _review_binding(review_id: str, review_zip_path: Path, verification_path: Path, verification: ImplementationDocument, drift: ImplementationDocument, incidents: ImplementationDocument) -> ImplementationDocument:
    return {
        "review_id": review_id,
        "zip_sha256": _sha256_path(review_zip_path),
        "zip_size_bytes": review_zip_path.stat().st_size if review_zip_path.exists() else None,
        "manifest_hash": verification.get("manifest_hash"),
        "verification_hash": verification.get("integrity_hash"),
        "verification_status": verification.get("status"),
        "drift_report_hash": drift.get("integrity_hash"),
        "incident_board_hash": incidents.get("integrity_hash"),
        "drift_status": drift.get("status"),
        "incident_status": incidents.get("status"),
    }


def _plan_document(center_id: str, response_id: str, drift: ImplementationDocument, incidents: ImplementationDocument, source: ImplementationDocument) -> ImplementationDocument:
    items = []
    for index, row in enumerate([item for item in drift.get("drifts", []) if isinstance(item, dict) and item.get("status") == "open"], start=1):
        action_type = "manual_change_request" if row.get("severity") in {"critical", "high"} else "safe_recheck_prepare"
        items.append(
            {
                "plan_item_id": f"plan-{index:06d}",
                "source_drift_id": row.get("drift_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "severity": row.get("severity"),
                "action_type": action_type,
                "requires_change_request": action_type == "manual_change_request",
                "status": "planned",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_plan", "center_id": center_id, "response_id": response_id, "source_review_id": source.get("source_review_id"), "source_hash": source.get("source_hash"), "items": items, "summary": {"item_count": len(items), "manual_required_count": sum(1 for row in items if row.get("requires_change_request")), "incident_count": int((incidents.get("summary") or {}).get("open_count") or 0)}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _queue_document(center_id: str, response_id: str, plan: ImplementationDocument, source: ImplementationDocument) -> ImplementationDocument:
    items = []
    for index, row in enumerate(plan.get("items", []), start=1):
        manual = bool(row.get("requires_change_request"))
        items.append(
            {
                "item_id": f"item-{index:06d}",
                "plan_item_id": row.get("plan_item_id"),
                "source_drift_id": row.get("source_drift_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "severity": row.get("severity"),
                "action": "prepare_recheck" if not manual else "bind_approved_change_request",
                "safe": not manual,
                "status": "pending" if not manual else "manual_required",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_action_queue", "center_id": center_id, "response_id": response_id, "source_hash": source.get("source_hash"), "items": items, "summary": {"action_count": len(items), "safe_action_count": sum(1 for row in items if row.get("safe")), "manual_required_count": sum(1 for row in items if not row.get("safe"))}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _results_document(center_id: str, response_id: str, source_hash: str | None, rows: list[ImplementationDocument]) -> ImplementationDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_action_results", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "results": rows, "summary": {"completed_count": sum(1 for row in rows if row.get("status") == "completed"), "manual_required_count": sum(1 for row in rows if row.get("status") == "manual_required"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _cr_bindings_document(center_id: str, response_id: str, source_hash: str | None, rows: list[ImplementationDocument]) -> ImplementationDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_change_request_bindings", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "items": rows, "summary": {"binding_count": len(rows), "approved_count": sum(1 for row in rows if row.get("status") == "approved")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _cr_binding_report_document(center_id: str, response_id: str, source_hash: str | None, queue: ImplementationDocument, cr_bindings: ImplementationDocument) -> ImplementationDocument:
    queue_items = {str(row.get("item_id")): row for row in queue.get("items", []) if isinstance(row, dict)}
    rows = []
    for binding in [row for row in cr_bindings.get("items", []) if isinstance(row, dict)]:
        item_id = str(binding.get("item_id") or "")
        item = queue_items.get(item_id, {})
        proof = sanitize_metadata(
            {
                "item_id": item_id,
                "source_drift_id": binding.get("source_drift_id") or item.get("source_drift_id"),
                "component_type": binding.get("component_type") or item.get("component_type"),
                "component_id": binding.get("component_id") or item.get("component_id"),
                "severity": binding.get("severity") or item.get("severity"),
                "action": binding.get("action") or item.get("action"),
                "change_request_id": binding.get("change_request_id"),
                "status": binding.get("status"),
                "approved_by": binding.get("approved_by"),
                "approved_at": binding.get("approved_at"),
                "approval_hash": binding.get("approval_hash") or _approval_hash(binding),
                "binding_hash": binding.get("binding_hash"),
            }
        )
        proof["proof_hash"] = stable_hash({key: value for key, value in proof.items() if key != "proof_hash"})
        rows.append(proof)
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE,
            "center_id": center_id,
            "response_id": response_id,
            "source_hash": source_hash,
            "action_queue_hash": queue.get("integrity_hash"),
            "change_request_bindings_hash": cr_bindings.get("integrity_hash"),
            "items": rows,
            "summary": {
                "binding_count": len(rows),
                "approved_count": sum(1 for row in rows if row.get("status") == "approved"),
                "manual_required_count": sum(1 for row in queue.get("items", []) if isinstance(row, dict) and not row.get("safe")),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _recheck_document(center_id: str, response_id: str, source_hash: str | None, binding: ImplementationDocument | None) -> ImplementationDocument:
    status = "passed" if binding and binding.get("verification_status") == "passed" and binding.get("drift_status") == "passed" else "missing"
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_recheck_summary", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "status": status, "review": binding or {}, "summary": {"recheck_bound": bool(binding), "status": status}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _closeout_document(center_id: str, response_id: str, source_hash: str | None, queue: ImplementationDocument, results: ImplementationDocument, cr_bindings: ImplementationDocument, recheck: ImplementationDocument, *, status: str, closed_by: str | None = None, reason: str | None = None) -> ImplementationDocument:
    blockers = []
    manual_ids = {str(row.get("item_id")) for row in queue.get("items", []) if isinstance(row, dict) and not row.get("safe")}
    bound_ids = {str(row.get("item_id")) for row in cr_bindings.get("items", []) if isinstance(row, dict) and row.get("status") == "approved"}
    completed_safe = {str(row.get("item_id")) for row in results.get("results", []) if isinstance(row, dict) and row.get("status") == "completed"}
    safe_ids = {str(row.get("item_id")) for row in queue.get("items", []) if isinstance(row, dict) and row.get("safe")}
    missing_safe = sorted(safe_ids - completed_safe)
    missing_manual = sorted(manual_ids - bound_ids)
    if missing_safe:
        blockers.append({"blocker_id": "safe_actions_incomplete", "item_ids": missing_safe})
    if missing_manual:
        blockers.append({"blocker_id": "change_request_missing", "item_ids": missing_manual})
    if recheck.get("status") != "passed":
        blockers.append({"blocker_id": "recheck_missing_or_failed", "status": recheck.get("status")})
    final_status = "closed" if status == "closed" and not blockers else "blocked" if status == "closed" else status
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_response_closeout",
            "center_id": center_id,
            "response_id": response_id,
            "source_hash": source_hash,
            "status": final_status,
            "closed_at": now_iso() if final_status == "closed" else None,
            "closed_by": closed_by,
            "reason": reason,
            "recheck_status": recheck.get("status"),
            "blockers": blockers,
            "summary": {"blocker_count": len(blockers), "manual_required_count": len(manual_ids), "approved_cr_count": len(bound_ids), "safe_action_count": len(safe_ids), "completed_safe_count": len(completed_safe)},
            "bindings": {
                "action_queue_hash": queue.get("integrity_hash"),
                "action_results_hash": results.get("integrity_hash"),
                "change_request_bindings_hash": cr_bindings.get("integrity_hash"),
                "recheck_summary_hash": recheck.get("integrity_hash"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _fingerprints_document(center_id: str, response_id: str, source: ImplementationDocument) -> ImplementationDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_package_fingerprints", "center_id": center_id, "response_id": response_id, "source_hash": source.get("source_hash"), "items": [{"component": "source_review", **(source.get("source_review") or {})}]})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _highest_severity(drift: ImplementationDocument) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    severities = [str(row.get("severity") or "low") for row in drift.get("drifts", []) if isinstance(row, dict)]
    return max(severities or ["low"], key=lambda value: order.get(value, 0))


def _read_json_required(path: Path) -> ImplementationDocument:
    if not path.exists():
        raise UnifiedCommandCenterDriftResponseNotFoundError(f"Required Drift Response document is missing: {path.name}.")
    return read_json(path)


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"entry": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _approval_hash(binding: ImplementationDocument) -> str:
    return stable_hash(
        {
            "change_request_id": binding.get("change_request_id"),
            "status": binding.get("status"),
            "approved_by": binding.get("approved_by"),
            "approved_at": binding.get("approved_at"),
            "reason": binding.get("reason"),
            "evidence_hash": binding.get("evidence_hash"),
        }
    )


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
