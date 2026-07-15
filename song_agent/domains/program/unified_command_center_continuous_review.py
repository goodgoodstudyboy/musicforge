from __future__ import annotations

import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_continuous_review_verifier import UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package


class UnifiedCommandCenterContinuousReviewError(ValueError):
    pass


class UnifiedCommandCenterContinuousReviewNotFoundError(UnifiedCommandCenterContinuousReviewError):
    pass


class UnifiedCommandCenterContinuousReviewStateError(UnifiedCommandCenterContinuousReviewError):
    pass


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

    def list_reviews(self, center_id: str) -> list[dict[str, Any]]:
        if not self.reviews_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.reviews_dir(center_id).glob("uccrv-*")):
            plan = path / "review-plan.json"
            if plan.exists():
                rows.append(read_json(plan))
        return rows

    def read_plan(self, center_id: str, review_id: str) -> dict[str, Any]:
        path = self.plan_path(center_id, review_id)
        if not path.exists():
            raise UnifiedCommandCenterContinuousReviewNotFoundError(f"Unified Command Center Continuous Review not found: {review_id}.")
        return read_json(path)

    def read_review(self, center_id: str, review_id: str) -> dict[str, Any]:
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

    def create_plan(self, center_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def run_review(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_package(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            docs = self._read_required_docs(center_id, review_id)
            current = self._collect_source(center_id, review_id, scope=docs["plan"].get("scope", {}), payload=payload, write_reports=False)
            if current.get("source_hash") != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterContinuousReviewStateError("Continuous review source is stale. Run review again.")
            payload_projection = _review_payload_projection(payload)
            latest_payload = docs["plan"].get("latest_payload") if isinstance(docs["plan"].get("latest_payload"), dict) else {}
            if payload_projection != latest_payload:
                raise UnifiedCommandCenterContinuousReviewStateError("Continuous review evidence inputs changed. Run review again.")
            self._write_export_manifest(center_id, review_id, docs)
            return {"status": docs["drift_report"].get("status"), "center_id": center_id, "review_id": review_id, "export_dir": str(self.review_dir(center_id, review_id)), "manifest": read_json(self.manifest_path(center_id, review_id))}

    def build_zip(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_package(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    def _assert_external_baseline(self, center_id: str, payload: dict[str, Any]) -> None:
        source = self._collect_source(center_id, "preflight", scope={"include_handoff": bool(payload.get("include_handoff", True))}, payload=payload, write_reports=False)
        archive = source.get("inputs", {}).get("archive", {})
        handoff = source.get("inputs", {}).get("handoff", {})
        if archive.get("status") != "passed":
            raise UnifiedCommandCenterContinuousReviewStateError("Unified Command Center Archive verification must pass before creating a Continuous Review plan.")
        if handoff.get("required", True) and handoff.get("status") != "passed":
            raise UnifiedCommandCenterContinuousReviewStateError("Unified Command Center Handoff verification must pass before creating a Continuous Review plan.")

    def _collect_source(self, center_id: str, review_id: str, *, scope: dict[str, Any], payload: dict[str, Any], write_reports: bool) -> dict[str, Any]:
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
        handoff_external: dict[str, Any] = {}
        handoff_runtime: dict[str, Any] = {"status": "not_required"}
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
        plan: dict[str, Any],
        source: dict[str, Any],
        drift: dict[str, Any],
        incidents: dict[str, Any],
        drill: dict[str, Any],
        runbook: dict[str, Any],
        runbook_result: dict[str, Any],
        cr_drafts: dict[str, Any],
        fingerprints: dict[str, Any],
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

    def _read_required_docs(self, center_id: str, review_id: str) -> dict[str, Any]:
        docs = self.read_review(center_id, review_id)
        required = ["source", "drift_report", "incident_board", "recovery_drill", "runbook", "runbook_result", "change_request_drafts", "package_fingerprints"]
        missing = [key for key in required if not docs.get(key)]
        if missing:
            raise UnifiedCommandCenterContinuousReviewStateError(f"Continuous Review has not been run: missing {', '.join(missing)}.")
        return docs

    def _write_export_manifest(self, center_id: str, review_id: str, docs: dict[str, Any]) -> None:
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


def _input_binding(component: str, zip_path: Path, external: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": component,
        "status": "passed" if external.get("status") == "passed" and runtime.get("status") == "passed" else "failed",
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
        "manifest_hash": runtime.get("manifest_hash") or external.get("manifest_hash"),
        "verification_hash": external.get("integrity_hash"),
        "verification_status": external.get("status"),
        "runtime_status": runtime.get("status"),
        "blockers": sorted(set((external.get("blockers") or []) + (runtime.get("blockers") or []))),
    }


def _external_evidence_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for value in payload.get("external_evidence", []) if isinstance(payload.get("external_evidence"), list) else []:
        if isinstance(value, dict):
            rows.append(sanitize_metadata(value))
    return rows


PASSING_EVIDENCE_STATUSES = {"passed", "ready", "clear", "signed", "accepted", "ok"}


def _evidence_status(value: Any) -> str:
    raw = value
    if isinstance(value, dict):
        raw = value.get("status")
        if raw is None and value.get("ok") is True:
            raw = "passed"
    normalized = str(raw or "unknown").strip().lower()
    return "passed" if normalized in PASSING_EVIDENCE_STATUSES else normalized


def _evidence_is_blocking(status: Any) -> bool:
    normalized = _evidence_status(status)
    return normalized not in {"passed", "not_configured", "not_required", "skipped"}


def _report_binding(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {"status": "not_configured", "report_hash": None}
    path = Path(path_value)
    if not path.exists():
        return {"status": "missing", "report_hash": None}
    try:
        payload = read_json(path)
        return {"status": _evidence_status(payload), "report_hash": _integrity_hash(payload) if "integrity_hash" not in payload else payload.get("integrity_hash"), "path_hash": _sha256_path(path)}
    except Exception as exc:
        return {"status": "failed", "error": sanitize_sensitive_text(str(exc)), "report_hash": None}


def _review_payload_projection(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "archive_zip",
        "archive_zip_path",
        "archive_verification_report",
        "archive_verification_report_path",
        "handoff_zip",
        "handoff_zip_path",
        "handoff_verification_report",
        "handoff_verification_report_path",
        "command_center_zip",
        "command_center_zip_path",
        "unified_command_center_zip",
        "command_center_verification_report",
        "command_center_verification_report_path",
        "unified_command_center_verification_report",
        "signoff_binding",
        "signoff_binding_path",
        "ga_report",
        "ga_readiness_report",
        "ga_readiness_report_path",
        "release_check_report",
        "release_check_report_path",
    )
    projection: dict[str, Any] = {}
    for key in keys:
        if key in payload and payload.get(key) is not None:
            projection[key] = str(payload.get(key))
    if isinstance(payload.get("external_evidence"), list):
        projection["external_evidence"] = sanitize_metadata(payload.get("external_evidence"))
    return projection


def _drift_report(center_id: str, review_id: str, plan: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    drifts: list[dict[str, Any]] = []
    baseline = plan.get("source") if isinstance(plan.get("source"), dict) else {}
    inputs = source.get("inputs", {})
    comparisons = (
        ("archive", "archive_zip_sha256", inputs.get("archive", {}).get("zip_sha256")),
        ("archive", "archive_verification_hash", inputs.get("archive", {}).get("verification_hash")),
        ("handoff", "handoff_zip_sha256", inputs.get("handoff", {}).get("zip_sha256")),
        ("handoff", "handoff_verification_hash", inputs.get("handoff", {}).get("verification_hash")),
        ("ga", "ga_report_hash", inputs.get("ga", {}).get("report_hash")),
        ("ga", "ga_path_hash", inputs.get("ga", {}).get("path_hash")),
        ("release_check", "release_check_report_hash", inputs.get("release_check", {}).get("report_hash")),
        ("release_check", "release_check_path_hash", inputs.get("release_check", {}).get("path_hash")),
        ("external_evidence", "external_evidence_hash", _external_evidence_hash(inputs.get("external_evidence", []))),
    )
    for component, key, actual in comparisons:
        expected = baseline.get(key)
        if expected and actual and expected != actual:
            drifts.append(_drift_row(len(drifts) + 1, component, "verification_mismatch", key, expected, actual, "critical"))
    for component in ("archive", "handoff", "ucc"):
        item = inputs.get(component, {})
        if item.get("status") == "failed":
            drifts.append(_drift_row(len(drifts) + 1, component, "verification_failed", "status", "passed", item.get("status"), "critical" if component in {"archive", "handoff"} else "high"))
    ga = inputs.get("ga") if isinstance(inputs.get("ga"), dict) else {}
    if _evidence_is_blocking(ga.get("status")):
        drifts.append(_drift_row(len(drifts) + 1, "ga", "external_evidence_failed", "status", "passed", ga.get("status"), "high"))
    release_check = inputs.get("release_check") if isinstance(inputs.get("release_check"), dict) else {}
    if _evidence_is_blocking(release_check.get("status")):
        drifts.append(_drift_row(len(drifts) + 1, "release_check", "external_evidence_failed", "status", "passed", release_check.get("status"), "high"))
    external_rows = inputs.get("external_evidence") if isinstance(inputs.get("external_evidence"), list) else []
    for index, row in enumerate([item for item in external_rows if isinstance(item, dict)], start=1):
        if _evidence_is_blocking(row.get("status")):
            component = str(row.get("component") or row.get("component_type") or row.get("evidence_type") or f"external_evidence_{index}")
            drift = _drift_row(len(drifts) + 1, component, "external_evidence_failed", "status", "passed", row.get("status"), "high")
            drift["component_id"] = str(row.get("component_id") or row.get("evidence_id") or component)
            drifts.append(drift)
    blocking = sum(1 for row in drifts if row.get("severity") in {"critical", "high"} and row.get("status") == "open")
    checked_count = 6 + 2 + len(external_rows)
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_report",
            "review_id": review_id,
            "center_id": center_id,
            "generated_at": now_iso(),
            "status": "failed" if blocking else "passed",
            "summary": {"checked_count": checked_count, "drift_count": len(drifts), "blocking_drift_count": blocking, "warning_count": 0},
            "drifts": drifts,
            "source_hash": source.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _drift_row(index: int, component: str, kind: str, field: str, expected: Any, actual: Any, severity: str) -> dict[str, Any]:
    return {
        "drift_id": f"drift-{index:06d}",
        "component_type": component,
        "component_id": component,
        "severity": severity,
        "status": "open",
        "kind": kind,
        "message": f"{component} {field} changed or failed.",
        "expected": {field: expected},
        "actual": {field: actual},
        "recommended_action": "create_change_request",
    }


def _external_evidence_hash(rows: Any) -> str | None:
    if not isinstance(rows, list):
        return None
    return stable_hash(sanitize_metadata(rows))


def _incident_board(center_id: str, review_id: str, drift: dict[str, Any]) -> dict[str, Any]:
    incidents = []
    for index, row in enumerate([item for item in drift.get("drifts", []) if item.get("severity") in {"critical", "high"}], start=1):
        incidents.append(
            {
                "incident_id": f"uccinc-{index:06d}",
                "source_drift_id": row.get("drift_id"),
                "severity": row.get("severity"),
                "status": "open",
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "created_at": now_iso(),
                "recommended_action": row.get("recommended_action"),
                "change_request_draft_id": f"ucccr-draft-{index:06d}",
            }
        )
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_incident_board",
            "review_id": review_id,
            "center_id": center_id,
            "status": "clear" if not incidents else "open",
            "summary": {"open_count": len(incidents), "critical_count": sum(1 for row in incidents if row.get("severity") == "critical"), "change_request_draft_count": len(incidents)},
            "incidents": incidents,
            "source_hash": drift.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _recovery_drill_report(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    inputs = source.get("inputs", {})
    steps = []
    for component, step_id in (("archive", "verify_archive"), ("handoff", "verify_handoff"), ("ucc", "verify_ucc")):
        item = inputs.get(component, {})
        if component == "handoff" and item.get("required") is False:
            steps.append({"step_id": step_id, "status": "skipped", "details": {"reason": "handoff not required"}})
        else:
            steps.append({"step_id": step_id, "status": "passed" if item.get("status") == "passed" else "failed", "details": {"zip_sha256": item.get("zip_sha256"), "manifest_hash": item.get("manifest_hash"), "verification_hash": item.get("verification_hash")}})
    failed = sum(1 for row in steps if row.get("status") == "failed")
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_recovery_drill_report",
            "review_id": review_id,
            "center_id": center_id,
            "status": "failed" if failed else "passed",
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "steps": steps,
            "summary": {"step_count": len(steps), "failed_count": failed},
            "source_hash": source.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook(center_id: str, review_id: str, source: dict[str, Any], drift: dict[str, Any], incidents: dict[str, Any]) -> dict[str, Any]:
    items = [
        {"item_id": "uccrv-safe-001", "action": "continuous_review.run", "safe": True, "status": "completed"},
        {"item_id": "uccrv-safe-002", "action": "continuous_review.verify", "safe": True, "status": "pending"},
    ]
    for index, row in enumerate(incidents.get("incidents", []), start=1):
        items.append({"item_id": f"uccrv-manual-{index:03d}", "action": "create_change_request_draft", "safe": False, "status": "manual_required", "source_incident_id": row.get("incident_id")})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_runbook",
            "review_id": review_id,
            "center_id": center_id,
            "created_at": now_iso(),
            "source_hash": source.get("source_hash"),
            "items": items,
            "summary": {"action_count": len(items), "safe_action_count": sum(1 for row in items if row.get("safe")), "manual_action_count": sum(1 for row in items if not row.get("safe"))},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_result(center_id: str, review_id: str, source_hash: str | None, results: list[dict[str, Any]]) -> dict[str, Any]:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_runbook_result",
            "review_id": review_id,
            "center_id": center_id,
            "created_at": now_iso(),
            "source_hash": source_hash,
            "results": results,
            "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required")},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _change_request_drafts(center_id: str, review_id: str, incidents: dict[str, Any]) -> dict[str, Any]:
    drafts = []
    for row in incidents.get("incidents", []):
        drafts.append(
            {
                "draft_id": row.get("change_request_draft_id"),
                "title": f"Resolve {row.get('component_type')} drift",
                "reason": f"Continuous Review incident {row.get('incident_id')} requires human change control.",
                "source_drift_id": row.get("source_drift_id"),
                "source_incident_id": row.get("incident_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "status": "draft",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_continuous_review_change_request_drafts", "review_id": review_id, "center_id": center_id, "items": drafts, "summary": {"draft_count": len(drafts)}, "source_hash": incidents.get("source_hash")})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _package_fingerprints(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    inputs = source.get("inputs", {})
    items = []
    for component in ("archive", "handoff", "ucc"):
        item = inputs.get(component, {})
        items.append({"component": component, "zip_sha256": item.get("zip_sha256"), "manifest_hash": item.get("manifest_hash"), "verification_hash": item.get("verification_hash"), "status": item.get("status"), "required": item.get("required", True)})
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_continuous_review_package_fingerprints", "review_id": review_id, "center_id": center_id, "source_hash": source.get("source_hash"), "items": items})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readme(drift: dict[str, Any], incidents: dict[str, Any]) -> str:
    return "\n".join(
        [
            "MusicForge Unified Command Center Continuous Review",
            "",
            f"Status: {drift.get('status')}",
            f"Open incidents: {(incidents.get('summary') or {}).get('open_count', 0)}",
            "",
            "Verify with verify-unified-command-center-continuous-review-package and the current UCC Archive/Handoff evidence.",
            "",
        ]
    )


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing"}
    return read_json(path)


def _ucc_zip_summary(zip_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            manifest = read_json_from_zip(archive, "manifest.json")
            return {
                "status": "passed" if _integrity_ok(manifest) else "failed",
                "zip_sha256": _sha256_path(zip_path),
                "manifest_hash": manifest.get("integrity_hash"),
                "blockers": [] if _integrity_ok(manifest) else ["ucc_manifest_integrity"],
            }
    except Exception:
        return {"status": "failed", "zip_sha256": _sha256_path(zip_path), "manifest_hash": None, "blockers": ["ucc_zip_readable"]}


def read_json_from_zip(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    import json

    return json.loads(archive.read(name).decode("utf-8"))


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
