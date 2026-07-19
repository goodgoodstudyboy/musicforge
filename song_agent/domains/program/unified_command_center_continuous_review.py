# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import shutil as shutil
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
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package as verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_continuous_review_verifier import UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report as write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package as verify_unified_command_center_package


class UnifiedCommandCenterContinuousReviewError(ValueError):
    pass


class UnifiedCommandCenterContinuousReviewNotFoundError(UnifiedCommandCenterContinuousReviewError):
    pass


from song_agent.domains.program import v142_ucccr_readiness as _v142_ucccr_readiness
from song_agent.domains.program.v142_ucccr_readiness import UnifiedCommandCenterContinuousReviewStateError as UnifiedCommandCenterContinuousReviewStateError, _input_binding as _input_binding, _external_evidence_rows as _external_evidence_rows, _evidence_status as _evidence_status, _evidence_is_blocking as _evidence_is_blocking, _report_binding as _report_binding, _review_payload_projection as _review_payload_projection, _drift_report as _drift_report, _drift_row as _drift_row, _external_evidence_hash as _external_evidence_hash, _incident_board as _incident_board, _recovery_drill_report as _recovery_drill_report, _runbook as _runbook, _runbook_result as _runbook_result, _change_request_drafts as _change_request_drafts, _package_fingerprints as _package_fingerprints, _readme as _readme, _gate_failed as _gate_failed, _read_json_if_exists as _read_json_if_exists, _ucc_zip_summary as _ucc_zip_summary, read_json_from_zip as read_json_from_zip, _bounded as _bounded, _safe_id as _safe_id, _file_record as _file_record, _integrity_ok as _integrity_ok, _integrity_hash as _integrity_hash, _sha256_path as _sha256_path



class UnifiedCommandCenterContinuousReviewStore:
    def __init__(
        self,
        center_store: UnifiedCommandCenterStore | None = None,
        *,
        signoff_store: UnifiedCommandCenterSignoffStore | None = None,
        handoff_store: UnifiedCommandCenterHandoffStore | None = None,
    ) -> None:
        self.center_store = center_store or UnifiedCommandCenterStore()
        self.signoff_store = signoff_store or UnifiedCommandCenterSignoffStore(self.center_store)
        self.handoff_store = handoff_store or UnifiedCommandCenterHandoffStore(self.signoff_store)
        self.lock = threading.RLock()

    def reviews_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "continuous-reviews"

    def review_dir(self, center_id: str, review_id: str) -> Path:
        return self.reviews_dir(center_id) / _safe_id(review_id)

    def plan_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-plan.json"

    def source_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-source.json"

    def drift_report_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "drift-report.json"

    def incident_board_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "incident-board.json"

    def recovery_drill_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "recovery-drill-report.json"

    def runbook_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-runbook.json"

    def runbook_result_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-runbook-result.json"

    def change_request_drafts_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "change-request-drafts.json"

    def fingerprints_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "package-fingerprints.json"

    def manifest_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "manifest.json"

    def zip_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "musicforge-unified-command-center-continuous-review.zip"

    def verification_report_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "continuous-review-verification-report.json"

    def list_reviews(self, center_id: str) -> list[DomainDocument]:
        if not self.reviews_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.reviews_dir(center_id).glob("uccrv-*")):
            plan = path / "review-plan.json"
            if plan.exists():
                rows.append(read_json(plan))
        return rows

    def read_plan(self, center_id: str, review_id: str) -> DomainDocument:
        path = self.plan_path(center_id, review_id)
        if not path.exists():
            raise UnifiedCommandCenterContinuousReviewNotFoundError(f"Unified Command Center Continuous Review not found: {review_id}.")
        return read_json(path)

    def read_review(self, center_id: str, review_id: str) -> DomainDocument:
        plan = self.read_plan(center_id, review_id)
        docs = {"plan": plan}
        for key, path_func in (
            ("source", self.source_path),
            ("drift_report", self.drift_report_path),
            ("incident_board", self.incident_board_path),
            ("recovery_drill", self.recovery_drill_path),
            ("runbook", self.runbook_path),
            ("runbook_result", self.runbook_result_path),
            ("change_request_drafts", self.change_request_drafts_path),
            ("package_fingerprints", self.fingerprints_path),
            ("manifest", self.manifest_path),
        ):
            path = path_func(center_id, review_id)
            docs[key] = read_json(path) if path.exists() else {}
        return docs

    def create_plan(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            state = self.center_store.latest_signoff_state(center_id)
            if state.get("status") != "signed":
                raise UnifiedCommandCenterContinuousReviewStateError("Unified Command Center must be signed before creating a Continuous Review plan.")
            review_id = str(payload.get("review_id") or self._next_review_id(center_id))
            if self.plan_path(center_id, review_id).exists():
                raise UnifiedCommandCenterContinuousReviewStateError(f"Continuous Review already exists: {review_id}.")
            self._assert_external_baseline(center_id, payload)
            now = now_iso()
            scope = {
                "include_archive": True,
                "include_handoff": bool(payload.get("include_handoff", True)),
                "include_ucc_zip": True,
                "include_external_evidence": bool(payload.get("include_external_evidence", True)),
                "include_ga": bool(payload.get("include_ga", True)),
                "include_release_check": bool(payload.get("include_release_check", True)),
                "include_maintenance": bool(payload.get("include_maintenance", True)),
            }
            requirements = {
                "archive_must_pass": True,
                "handoff_must_pass": bool(scope["include_handoff"]),
                "no_blocking_drift": True,
                "no_open_critical_incident": True,
                "recovery_drill_required": True,
            }
            source = self._collect_source(center_id, review_id, scope=scope, payload=payload, write_reports=False)
            plan = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_continuous_review_plan",
                    "review_id": review_id,
                    "center_id": center_id,
                    "status": "planned",
                    "created_at": now,
                    "created_by": _bounded(payload.get("created_by") or "release-owner", 120),
                    "scope": scope,
                    "requirements": requirements,
                    "source": {
                        "signoff_hash": source.get("signoff_hash"),
                        "source_hash": source.get("source_hash"),
                        "archive_zip_sha256": source.get("inputs", {}).get("archive", {}).get("zip_sha256"),
                        "archive_manifest_hash": source.get("inputs", {}).get("archive", {}).get("manifest_hash"),
                        "archive_verification_hash": source.get("inputs", {}).get("archive", {}).get("verification_hash"),
                        "handoff_zip_sha256": source.get("inputs", {}).get("handoff", {}).get("zip_sha256"),
                        "handoff_manifest_hash": source.get("inputs", {}).get("handoff", {}).get("manifest_hash"),
                        "handoff_verification_hash": source.get("inputs", {}).get("handoff", {}).get("verification_hash"),
                        "ga_status": source.get("inputs", {}).get("ga", {}).get("status"),
                        "ga_report_hash": source.get("inputs", {}).get("ga", {}).get("report_hash"),
                        "ga_path_hash": source.get("inputs", {}).get("ga", {}).get("path_hash"),
                        "release_check_status": source.get("inputs", {}).get("release_check", {}).get("status"),
                        "release_check_report_hash": source.get("inputs", {}).get("release_check", {}).get("report_hash"),
                        "release_check_path_hash": source.get("inputs", {}).get("release_check", {}).get("path_hash"),
                        "external_evidence_hash": _external_evidence_hash(source.get("inputs", {}).get("external_evidence", [])),
                    },
                }
            )
            plan["integrity_hash"] = _integrity_hash(plan)
            self.review_dir(center_id, review_id).mkdir(parents=True, exist_ok=True)
            write_json(self.plan_path(center_id, review_id), plan)
            return plan

    def run_review(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            plan = self.read_plan(center_id, review_id)
            if not _integrity_ok(plan):
                raise UnifiedCommandCenterContinuousReviewStateError("Continuous Review plan integrity failed.")
            source = self._collect_source(center_id, review_id, scope=plan.get("scope", {}), payload=payload, write_reports=True)
            drift = _drift_report(center_id, review_id, plan, source)
            incidents = _incident_board(center_id, review_id, drift)
            drill = _recovery_drill_report(center_id, review_id, source)
            runbook = _runbook(center_id, review_id, source, drift, incidents)
            runbook_result = _runbook_result(center_id, review_id, source.get("source_hash"), [])
            cr_drafts = _change_request_drafts(center_id, review_id, incidents)
            fingerprints = _package_fingerprints(center_id, review_id, source)
            self._write_docs(center_id, review_id, plan, source, drift, incidents, drill, runbook, runbook_result, cr_drafts, fingerprints)
            plan["status"] = "reviewed"
            plan["latest_source_hash"] = source.get("source_hash")
            plan["latest_payload"] = _review_payload_projection(payload)
            plan["latest_status"] = drift.get("status")
            plan["updated_at"] = now_iso()
            plan["integrity_hash"] = _integrity_hash(plan)
            write_json(self.plan_path(center_id, review_id), plan)
            return {"status": drift.get("status"), "review_id": review_id, "source": source, "drift_report": drift, "incident_board": incidents, "recovery_drill": drill, "summary": drift.get("summary", {})}

    def export_package(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            docs = self._read_required_docs(center_id, review_id)
            current = self._collect_source(center_id, review_id, scope=docs["plan"].get("scope", {}), payload=payload, write_reports=False)
            if current.get("source_hash") != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterContinuousReviewStateError("Continuous review source is stale. Run review again.")
            payload_projection = _review_payload_projection(payload)
            latest_payload = _as_document(docs["plan"].get("latest_payload"))
            if payload_projection != latest_payload:
                raise UnifiedCommandCenterContinuousReviewStateError("Continuous review evidence inputs changed. Run review again.")
            self._write_export_manifest(center_id, review_id, docs)
            return {"status": docs["drift_report"].get("status"), "center_id": center_id, "review_id": review_id, "export_dir": str(self.review_dir(center_id, review_id)), "manifest": read_json(self.manifest_path(center_id, review_id))}

    def build_zip(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            exported = self.export_package(center_id, review_id, payload or {})
            review_dir = self.review_dir(center_id, review_id)
            zip_path = self.zip_path(center_id, review_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(review_dir.iterdir()):
                    if path.is_file() and path != zip_path and path.name != "continuous-review-verification-report.json":
                        archive.write(path, path.name)
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(center_id, review_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.name) for path in sorted(review_dir.iterdir()) if path.is_file() and path != zip_path and path.name not in {"manifest.json", "continuous-review-verification-report.json"}]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(center_id, review_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(review_dir.iterdir()):
                    if path.is_file() and path != zip_path and path.name != "continuous-review-verification-report.json":
                        archive.write(path, path.name)
            return {"status": exported.get("status"), "center_id": center_id, "review_id": review_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_package(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_command_center_continuous_review_package(
            self.zip_path(center_id, review_id),
            strict=bool(payload.get("strict", True)),
            require_clear=bool(payload.get("require_clear", True)),
            require_recovery_drill=bool(payload.get("require_recovery_drill", True)),
            require_current_review=bool(payload.get("require_current_review", True)),
            archive_zip_path=payload.get("archive_zip") or payload.get("archive_zip_path") or self.signoff_store.archive_zip_path(center_id),
            archive_verification_report_path=payload.get("archive_verification_report") or payload.get("archive_verification_report_path") or self.signoff_store.archive_verification_report_path(center_id),
            handoff_zip_path=payload.get("handoff_zip") or payload.get("handoff_zip_path") or self.handoff_store.zip_path(center_id),
            handoff_verification_report_path=payload.get("handoff_verification_report") or payload.get("handoff_verification_report_path") or self.handoff_store.verification_report_path(center_id),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.center_store.zip_path(center_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.center_store.verification_report_path(center_id),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_store.signoff_binding_path(center_id),
            ga_readiness_report_path=payload.get("ga_report") or payload.get("ga_readiness_report") or payload.get("ga_readiness_report_path"),
            release_check_report_path=payload.get("release_check_report") or payload.get("release_check_report_path"),
        )
        write_unified_command_center_continuous_review_verification_report(report, self.verification_report_path(center_id, review_id))
        return report

    def gate(
        self,
        center_id: str,
        *,
        required: bool = True,
        review_id: str | None = None,
        review_zip_path: Path | str | None = None,
        review_verification_report_path: Path | str | None = None,
        archive_zip_path: Path | str | None = None,
        archive_verification_report_path: Path | str | None = None,
        handoff_zip_path: Path | str | None = None,
        handoff_verification_report_path: Path | str | None = None,
        command_center_zip_path: Path | str | None = None,
        command_center_verification_report_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        rid = review_id or self._latest_review_id(center_id)
        zip_path = Path(review_zip_path) if review_zip_path else self.zip_path(center_id, rid)
        report_path = Path(review_verification_report_path) if review_verification_report_path else self.verification_report_path(center_id, rid)
        if not zip_path.exists():
            return _gate_failed("Unified Command Center Continuous Review ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Command Center Continuous Review verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_command_center_continuous_review_package(
                zip_path,
                strict=True,
                require_clear=True,
                require_recovery_drill=True,
                require_current_review=True,
                archive_zip_path=archive_zip_path or self.signoff_store.archive_zip_path(center_id),
                archive_verification_report_path=archive_verification_report_path or self.signoff_store.archive_verification_report_path(center_id),
                handoff_zip_path=handoff_zip_path or self.handoff_store.zip_path(center_id),
                handoff_verification_report_path=handoff_verification_report_path or self.handoff_store.verification_report_path(center_id),
                command_center_zip_path=command_center_zip_path or self.center_store.zip_path(center_id),
                command_center_verification_report_path=command_center_verification_report_path or self.center_store.verification_report_path(center_id),
                signoff_binding_path=signoff_binding_path or self.signoff_store.signoff_binding_path(center_id),
            )
            if external.get("integrity_hash") != _integrity_hash(external):
                return _gate_failed("Unified Command Center Continuous Review verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Continuous Review verification failed.", verification=runtime)
            if external.get("zip_sha256") != _sha256_path(zip_path) or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Continuous Review verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Continuous Review gate passed.", "review_id": rid, "zip_sha256": runtime.get("zip_sha256"), "manifest_hash": runtime.get("manifest_hash"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _next_review_id(self, center_id: str) -> str:
        self.reviews_dir(center_id).mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.reviews_dir(center_id).glob("uccrv-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"uccrv-{max_seen + 1:06d}"

    def _latest_review_id(self, center_id: str) -> str:
        reviews = self.list_reviews(center_id)
        if not reviews:
            raise UnifiedCommandCenterContinuousReviewNotFoundError("Unified Command Center Continuous Review not found.")
        return str(sorted(reviews, key=lambda row: str(row.get("review_id") or ""))[-1].get("review_id"))

    def _assert_external_baseline(self, center_id: str, payload: ImplementationDocument) -> None:
        source = self._collect_source(center_id, "preflight", scope={"include_handoff": bool(payload.get("include_handoff", True))}, payload=payload, write_reports=False)
        archive = source.get("inputs", {}).get("archive", {})
        handoff = source.get("inputs", {}).get("handoff", {})
        if archive.get("status") != "passed":
            raise UnifiedCommandCenterContinuousReviewStateError("Unified Command Center Archive verification must pass before creating a Continuous Review plan.")
        if handoff.get("required", True) and handoff.get("status") != "passed":
            raise UnifiedCommandCenterContinuousReviewStateError("Unified Command Center Handoff verification must pass before creating a Continuous Review plan.")

    def _collect_source(self, center_id: str, review_id: str, *, scope: ImplementationDocument, payload: ImplementationDocument, write_reports: bool) -> ImplementationDocument:
        now = now_iso()
        archive_zip_override = payload.get("archive_zip") or payload.get("archive_zip_path")
        archive_report_override = payload.get("archive_verification_report") or payload.get("archive_verification_report_path")
        handoff_zip_override = payload.get("handoff_zip") or payload.get("handoff_zip_path")
        handoff_report_override = payload.get("handoff_verification_report") or payload.get("handoff_verification_report_path")
        archive_zip = Path(archive_zip_override or self.signoff_store.archive_zip_path(center_id))
        archive_report_path = Path(archive_report_override or self.signoff_store.archive_verification_report_path(center_id))
        handoff_zip = Path(handoff_zip_override or self.handoff_store.zip_path(center_id))
        handoff_report_path = Path(handoff_report_override or self.handoff_store.verification_report_path(center_id))
        ucc_zip = Path(payload.get("command_center_zip") or payload.get("command_center_zip_path") or payload.get("unified_command_center_zip") or self.center_store.zip_path(center_id))
        ucc_report_path = Path(payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or payload.get("unified_command_center_verification_report") or self.center_store.verification_report_path(center_id))
        signoff_binding = Path(payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_store.signoff_binding_path(center_id))
        signoff = self.signoff_store.read_signoff(center_id)

        archive_external = _read_json_if_exists(archive_report_path)
        archive_runtime = verify_unified_command_center_archive_package(
            archive_zip,
            strict=True,
            require_signed=True,
            require_current_ucc=True,
            command_center_zip_path=ucc_zip,
            command_center_verification_report_path=ucc_report_path,
            signoff_binding_path=signoff_binding,
        )
        if write_reports and (not archive_zip_override or archive_report_override):
            write_json(archive_report_path, archive_runtime)
            archive_external = archive_runtime
        ucc_external = _read_json_if_exists(ucc_report_path)
        ucc_runtime = _ucc_zip_summary(ucc_zip)
        include_handoff = bool(scope.get("include_handoff", True))
        handoff_external: ImplementationDocument = {}
        handoff_runtime: ImplementationDocument = {"status": "not_required"}
        if include_handoff:
            handoff_external = _read_json_if_exists(handoff_report_path)
            handoff_runtime = verify_unified_command_center_handoff_package(
                handoff_zip,
                strict=True,
                require_archive=True,
                archive_zip_path=archive_zip,
                archive_verification_report_path=archive_report_path,
            )
            if write_reports and (handoff_report_override or (not handoff_zip_override and not archive_zip_override and not archive_report_override)):
                write_json(handoff_report_path, handoff_runtime)
                handoff_external = handoff_runtime

        inputs = {
            "archive": _input_binding("archive", archive_zip, archive_external, archive_runtime),
            "handoff": {**_input_binding("handoff", handoff_zip, handoff_external, handoff_runtime), "required": include_handoff},
            "ucc": _input_binding("ucc", ucc_zip, ucc_external, ucc_runtime),
            "external_evidence": _external_evidence_rows(payload),
            "ga": _report_binding(payload.get("ga_report") or payload.get("ga_readiness_report") or payload.get("ga_readiness_report_path")),
            "release_check": _report_binding(payload.get("release_check_report") or payload.get("release_check_report_path")),
        }
        doc = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_continuous_review_source",
                "review_id": review_id,
                "center_id": center_id,
                "collected_at": now,
                "signoff_hash": signoff.get("integrity_hash"),
                "inputs": inputs,
                "tool": {"name": "MusicForge Unified Command Center Continuous Review", "version": __version__},
            }
        )
        doc["source_hash"] = stable_hash({key: value for key, value in doc.items() if key not in {"source_hash", "integrity_hash", "collected_at"}})
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _write_docs(
        self,
        center_id: str,
        review_id: str,
        plan: ImplementationDocument,
        source: ImplementationDocument,
        drift: ImplementationDocument,
        incidents: ImplementationDocument,
        drill: ImplementationDocument,
        runbook: ImplementationDocument,
        runbook_result: ImplementationDocument,
        cr_drafts: ImplementationDocument,
        fingerprints: ImplementationDocument,
    ) -> None:
        review_dir = self.review_dir(center_id, review_id)
        review_dir.mkdir(parents=True, exist_ok=True)
        for path, doc in (
            (self.plan_path(center_id, review_id), plan),
            (self.source_path(center_id, review_id), source),
            (self.drift_report_path(center_id, review_id), drift),
            (self.incident_board_path(center_id, review_id), incidents),
            (self.recovery_drill_path(center_id, review_id), drill),
            (self.runbook_path(center_id, review_id), runbook),
            (self.runbook_result_path(center_id, review_id), runbook_result),
            (self.change_request_drafts_path(center_id, review_id), cr_drafts),
            (self.fingerprints_path(center_id, review_id), fingerprints),
        ):
            write_json(path, doc)

    def _read_required_docs(self, center_id: str, review_id: str) -> ImplementationDocument:
        docs = self.read_review(center_id, review_id)
        required = ["source", "drift_report", "incident_board", "recovery_drill", "runbook", "runbook_result", "change_request_drafts", "package_fingerprints"]
        missing = [key for key in required if not docs.get(key)]
        if missing:
            raise UnifiedCommandCenterContinuousReviewStateError(f"Continuous Review has not been run: missing {', '.join(missing)}.")
        return docs

    def _write_export_manifest(self, center_id: str, review_id: str, docs: ImplementationDocument) -> None:
        review_dir = self.review_dir(center_id, review_id)
        (review_dir / "README.txt").write_text(_readme(docs["drift_report"], docs["incident_board"]), encoding="utf-8")
        files = [_file_record(path, path.name) for path in sorted(review_dir.iterdir()) if path.is_file() and path.name not in {"manifest.json", "musicforge-unified-command-center-continuous-review.zip", "continuous-review-verification-report.json"}]
        manifest = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
                "package_type": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE,
                "review_id": review_id,
                "center_id": center_id,
                "created_at": now_iso(),
                "status": docs["drift_report"].get("status"),
                "source": {
                    "review_source_hash": docs["source"].get("integrity_hash"),
                    "drift_report_hash": docs["drift_report"].get("integrity_hash"),
                    "incident_board_hash": docs["incident_board"].get("integrity_hash"),
                    "recovery_drill_hash": docs["recovery_drill"].get("integrity_hash"),
                    "runbook_hash": docs["runbook"].get("integrity_hash"),
                    "runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                    "change_request_drafts_hash": docs["change_request_drafts"].get("integrity_hash"),
                    "package_fingerprints_hash": docs["package_fingerprints"].get("integrity_hash"),
                    "signoff_hash": docs["source"].get("signoff_hash"),
                    "archive_zip_sha256": docs["source"].get("inputs", {}).get("archive", {}).get("zip_sha256"),
                    "handoff_zip_sha256": docs["source"].get("inputs", {}).get("handoff", {}).get("zip_sha256"),
                },
                "summary": docs["drift_report"].get("summary", {}),
                "files": files,
                "zip": {},
            }
        )
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(self.manifest_path(center_id, review_id), manifest)






PASSING_EVIDENCE_STATUSES = {"passed", "ready", "clear", "signed", "accepted", "ok"}

_v142_ucccr_readiness.bind_globals(globals())
