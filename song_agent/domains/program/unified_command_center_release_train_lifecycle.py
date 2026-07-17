from __future__ import annotations

from song_agent.platform.contracts.coercion import as_list as _as_list

from typing import Any as _InferenceType

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore as UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore as UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package, write_unified_command_center_release_train_lifecycle_verification_report as write_unified_command_center_release_train_lifecycle_verification_report
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package


class UnifiedCommandCenterReleaseTrainLifecycleError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainLifecycleNotFoundError(UnifiedCommandCenterReleaseTrainLifecycleError):
    pass


class UnifiedCommandCenterReleaseTrainLifecycleStateError(UnifiedCommandCenterReleaseTrainLifecycleError):
    pass


class UnifiedCommandCenterReleaseTrainLifecycleStore:
    def __init__(
        self,
        train_store: UnifiedCommandCenterReleaseTrainStore | None = None,
        change_control_store: UnifiedCommandCenterReleaseTrainChangeControlStore | None = None,
    ) -> None:
        self.train_store = train_store or UnifiedCommandCenterReleaseTrainStore()
        self.change_control_store = change_control_store or UnifiedCommandCenterReleaseTrainChangeControlStore(self.train_store)
        self.lock = threading.RLock()

    def lifecycle_dir(self, train_id: str) -> Path:
        return self.train_store.train_dir(train_id) / "lifecycle"

    def source_inputs_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "lifecycle-source-inputs.json"

    def report_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "lifecycle-report.json"

    def ledger_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "lifecycle-ledger.jsonl"

    def succession_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "signoff-succession-map.json"

    def coverage_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "change-reset-coverage.json"

    def archive_history_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "archive-history-ledger.json"

    def readiness_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "current-readiness-assertion.json"

    def gap_plan_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "gap-plan.json"

    def evidence_index_path(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "evidence-fingerprint-index.json"

    def export_dir(self, train_id: str) -> Path:
        return self.lifecycle_dir(train_id) / "export"

    def manifest_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "manifest.json"

    def zip_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "unified-command-center-release-train-lifecycle.zip"

    def verification_report_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "unified-command-center-release-train-lifecycle-verification-report.json"

    def refresh_report(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            docs = self._build_documents(train_id, payload)
            self.lifecycle_dir(train_id).mkdir(parents=True, exist_ok=True)
            write_json(self.source_inputs_path(train_id), _source_inputs(payload))
            self._write_docs(train_id, docs)
            return docs["report"]

    def read_report(self, train_id: str) -> dict[str, Any]:
        if not self.report_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainLifecycleNotFoundError(f"Release Train Lifecycle report not found: {train_id}")
        return read_json(self.report_path(train_id))

    def export_package(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            docs = self._current_docs_for_export(train_id, payload or {})
            export_dir = self.export_dir(train_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("lifecycle-report.json", docs["report"])
            write_entry("lifecycle-ledger.jsonl", docs["ledger_text"])
            write_entry("signoff-succession-map.json", docs["succession"])
            write_entry("change-reset-coverage.json", docs["coverage"])
            write_entry("archive-history-ledger.json", docs["archive_history"])
            write_entry("current-readiness-assertion.json", docs["readiness"])
            write_entry("gap-plan.json", docs["gap_plan"])
            write_entry("evidence-fingerprint-index.json", docs["evidence_index"])
            write_entry("REVIEWER_GUIDE.md", _reviewer_guide(docs))
            write_entry("README.txt", "MusicForge Unified Command Center Release Train Lifecycle Audit\n")
            manifest = _manifest_document(train_id, docs, files)
            write_json(self.manifest_path(train_id), manifest)
            return manifest

    def build_zip(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            if not self.manifest_path(train_id).exists():
                self.export_package(train_id, payload or {})
            else:
                self._assert_export_current(train_id, payload or {})
            export_dir = self.export_dir(train_id)
            zip_path = self.zip_path(train_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(train_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(train_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": "passed", "train_id": train_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_package(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_command_center_release_train_lifecycle_package(
            self.zip_path(train_id),
            strict=bool(payload.get("strict", True)),
            require_current_train=bool(payload.get("require_current_train", True)),
            require_change_control=bool(payload.get("require_change_control", False)),
            train_archive_path=payload.get("train_archive") or payload.get("train_archive_path") or self.train_store.zip_path(train_id),
            train_archive_verification_report_path=payload.get("train_archive_verification_report") or payload.get("train_archive_verification_report_path") or self.train_store.verification_report_path(train_id),
            train_signoff_binding_path=payload.get("train_signoff_binding") or payload.get("train_signoff_binding_path") or self.train_store.signoff_binding_path(train_id),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self._saved_input(train_id, "external_evidence_manifest"),
            change_control_zip_path=payload.get("change_control_zip") or payload.get("change_control_zip_path") or self.change_control_store.zip_path(train_id),
            change_control_verification_report_path=payload.get("change_control_verification_report") or payload.get("change_control_verification_report_path") or self.change_control_store.verification_report_path(train_id),
            reset_proof_paths=_as_list(_reset_proof_paths(payload) or _reset_proof_paths(self._saved_inputs(train_id))),
        )
        write_unified_command_center_release_train_lifecycle_verification_report(report, self.verification_report_path(train_id))
        return report

    def gate(
        self,
        train_id: str,
        *,
        required: bool = False,
        lifecycle_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(lifecycle_zip_path) if lifecycle_zip_path else self.zip_path(train_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(train_id)
        if not zip_path.exists():
            return _gate_failed("Release Train Lifecycle ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Release Train Lifecycle verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_command_center_release_train_lifecycle_package(
                zip_path,
                strict=True,
                require_current_train=True,
                require_change_control=bool(payload.get("require_change_control", False)),
                train_archive_path=payload.get("train_archive_path") or payload.get("train_archive") or self.train_store.zip_path(train_id),
                train_archive_verification_report_path=payload.get("train_archive_verification_report_path") or payload.get("train_archive_verification_report") or self.train_store.verification_report_path(train_id),
                train_signoff_binding_path=payload.get("train_signoff_binding_path") or payload.get("train_signoff_binding") or self.train_store.signoff_binding_path(train_id),
                external_evidence_manifest_path=payload.get("external_evidence_manifest_path") or payload.get("external_evidence_manifest") or self._saved_input(train_id, "external_evidence_manifest"),
                change_control_zip_path=payload.get("change_control_zip_path") or payload.get("change_control_zip") or self.change_control_store.zip_path(train_id),
                change_control_verification_report_path=payload.get("change_control_verification_report_path") or payload.get("change_control_verification_report") or self.change_control_store.verification_report_path(train_id),
                reset_proof_paths=_as_list(_reset_proof_paths(payload) or _reset_proof_paths(self._saved_inputs(train_id))),
            )
            if not _integrity_ok(external):
                return _gate_failed("Release Train Lifecycle verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Release Train Lifecycle verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Release Train Lifecycle verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Release Train Lifecycle gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _current_docs_for_export(self, train_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        if not self.report_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainLifecycleStateError("Release Train Lifecycle report is missing. Refresh before export.")
        saved = self._saved_inputs(train_id)
        merged = _merge_inputs(saved, _source_inputs(payload))
        docs = self._build_documents(train_id, merged)
        report = read_json(self.report_path(train_id))
        if docs["report"].get("source_hash") != report.get("source_hash"):
            raise UnifiedCommandCenterReleaseTrainLifecycleStateError("Release Train Lifecycle source is stale. Refresh before export.")
        return docs

    def _assert_export_current(self, train_id: str, payload: ImplementationDocument) -> None:
        docs = self._current_docs_for_export(train_id, payload)
        manifest = read_json(self.manifest_path(train_id))
        if manifest.get("source_hash") != docs["report"].get("source_hash"):
            raise UnifiedCommandCenterReleaseTrainLifecycleStateError("Release Train Lifecycle export is stale. Re-export before ZIP.")

    def _build_documents(self, train_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        now = now_iso()
        train = self.train_store.read_train(train_id)
        history = self.train_store.read_history(train_id)
        reset_events = [row for row in history if row.get("event_type") == "ucc_release_train_signoff_reset"]
        signoff_events = [row for row in history if row.get("event_type") == "ucc_release_train_signoff_created"]
        train_summary = self._current_train_summary(train_id, payload)
        reset_proofs = self._reset_proof_summaries(payload)
        change_summary = self._change_control_summary(train_id, payload, require=bool(reset_events))
        archive_history_items = self._archive_history_items(train_id)
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_lifecycle_source",
                "train_id": train_id,
                "created_at": now,
                "train_hash": train.get("integrity_hash"),
                "train_history_tip_hash": history[-1].get("event_hash") if history else "",
                "current_signoff_state": self.train_store.latest_signoff_state(train_id),
                "current_train_archive": {
                    key: train_summary.get(key)
                    for key in ("zip_sha256", "zip_size_bytes", "manifest_hash", "verification_report_hash", "signoff_binding_hash", "external_evidence_manifest_hash", "verification_status", "runtime_status")
                },
                "change_control": change_summary,
                "reset_proofs": reset_proofs,
                "archive_history_hashes": [row.get("entry_hash") for row in archive_history_items if row.get("entry_hash")],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash", "created_at"}})
        source["integrity_hash"] = _integrity_hash(source)
        ledger = self._lifecycle_ledger(train_id, history)
        ledger_text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger)
        succession = _with_integrity(_succession_map(train_id, source["source_hash"], signoff_events, reset_events, archive_history_items, train_summary))
        coverage = _with_integrity(_coverage_doc(train_id, source["source_hash"], reset_events, reset_proofs, change_summary, archive_history_items))
        archive_history = _with_integrity({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_archive_history_ledger", "train_id": train_id, "source_hash": source["source_hash"], "items": archive_history_items, "summary": {"archive_history_count": len(archive_history_items)}})
        readiness = _with_integrity(_readiness_doc(train_id, source["source_hash"], self.train_store.latest_signoff_state(train_id), train_summary, change_summary, coverage))
        gaps = _gap_items(readiness, coverage, bool(reset_events), change_summary)
        gap_plan = _with_integrity({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_lifecycle_gap_plan", "train_id": train_id, "source_hash": source["source_hash"], "items": gaps, "summary": {"gap_count": len(gaps), "blocking_gap_count": sum(1 for row in gaps if row.get("severity") == "blocking")}})
        evidence_index = _with_integrity(_evidence_index_doc(train_id, source["source_hash"], train_summary, change_summary, reset_proofs))
        blockers = [row["check_id"] for row in readiness.get("checks", []) if row.get("status") == "failed"]
        blockers.extend(row.get("gap_id") for row in gaps if row.get("severity") == "blocking")
        blockers = [str(row) for row in blockers if row]
        status = "failed" if blockers else "passed"
        report = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_lifecycle_report",
                "train_id": train_id,
                "created_at": now,
                "source_hash": source["source_hash"],
                "status": status,
                "summary": {
                    "current_state": self.train_store.latest_signoff_state(train_id).get("status"),
                    "current_release_ready": status == "passed",
                    "signoff_count": len(signoff_events),
                    "reset_count": len(reset_events),
                    "applied_change_request_count": int(change_summary.get("applied_reset_count") or 0),
                    "archive_history_count": len(archive_history_items),
                    "current_train_verification_status": train_summary.get("runtime_status"),
                    "change_control_verification_status": change_summary.get("runtime_status") if change_summary.get("configured") else "not_configured",
                    "blocking_gap_count": len(blockers),
                    "manual_action_count": len(gaps),
                },
                "blockers": blockers,
                "warnings": [],
            }
        )
        report["integrity_hash"] = _integrity_hash(report)
        return {"source": source, "report": report, "ledger": ledger, "ledger_text": ledger_text, "succession": succession, "coverage": coverage, "archive_history": archive_history, "readiness": readiness, "gap_plan": gap_plan, "evidence_index": evidence_index}

    def _write_docs(self, train_id: str, docs: ImplementationDocument) -> None:
        write_json(self.report_path(train_id), docs["report"])
        self.ledger_path(train_id).write_text(docs["ledger_text"], encoding="utf-8")
        write_json(self.succession_path(train_id), docs["succession"])
        write_json(self.coverage_path(train_id), docs["coverage"])
        write_json(self.archive_history_path(train_id), docs["archive_history"])
        write_json(self.readiness_path(train_id), docs["readiness"])
        write_json(self.gap_plan_path(train_id), docs["gap_plan"])
        write_json(self.evidence_index_path(train_id), docs["evidence_index"])

    def _current_train_summary(self, train_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        archive_path = Path(payload.get("train_archive") or payload.get("train_archive_path") or self.train_store.zip_path(train_id))
        verification_path = Path(payload.get("train_archive_verification_report") or payload.get("train_archive_verification_report_path") or self.train_store.verification_report_path(train_id))
        signoff_binding_path = Path(payload.get("train_signoff_binding") or payload.get("train_signoff_binding_path") or self.train_store.signoff_binding_path(train_id))
        external_manifest_path = payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path")
        external_report = read_json(verification_path) if verification_path.exists() else {}
        signoff_binding = read_json(signoff_binding_path) if signoff_binding_path.exists() else {}
        external_manifest = read_json(Path(external_manifest_path)) if external_manifest_path and Path(external_manifest_path).exists() else {}
        runtime = verify_unified_command_center_release_train_package(
            archive_path,
            strict=True,
            require_go=True,
            require_signed=True,
            external_evidence_manifest_path=external_manifest_path,
            signoff_binding_path=signoff_binding_path,
        )
        return {
            "zip_sha256": _sha256_path(archive_path),
            "zip_size_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": _integrity_hash(external_report) if external_report else None,
            "verification_status": external_report.get("status"),
            "runtime_status": runtime.get("status"),
            "runtime_blockers": runtime.get("blockers", []),
            "signoff_binding_hash": signoff_binding.get("integrity_hash"),
            "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
            "external_report_zip_sha256": external_report.get("zip_sha256"),
            "external_report_manifest_hash": external_report.get("manifest_hash"),
        }

    def _change_control_summary(self, train_id: str, payload: ImplementationDocument, *, require: bool) -> ImplementationDocument:
        zip_path = Path(payload.get("change_control_zip") or payload.get("change_control_zip_path") or self.change_control_store.zip_path(train_id))
        report_path = Path(payload.get("change_control_verification_report") or payload.get("change_control_verification_report_path") or self.change_control_store.verification_report_path(train_id))
        external = read_json(report_path) if report_path.exists() else {}
        if not zip_path.exists() and not report_path.exists() and not require:
            return {"configured": False, "runtime_status": "not_configured", "applied_reset_count": 0}
        reset_proof_paths = _reset_proof_paths(payload)
        runtime = verify_unified_command_center_release_train_change_control_package(
            zip_path,
            strict=True,
            require_reset_applied=require,
            require_current_train=bool(payload.get("require_current_train_for_change_control", True)),
            train_archive_path=payload.get("train_archive") or payload.get("train_archive_path") or self.train_store.zip_path(train_id),
            train_archive_verification_report_path=payload.get("train_archive_verification_report") or payload.get("train_archive_verification_report_path") or self.train_store.verification_report_path(train_id),
            train_signoff_binding_path=payload.get("train_signoff_binding") or payload.get("train_signoff_binding_path") or self.train_store.signoff_binding_path(train_id),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"),
            reset_proof_path=reset_proof_paths[-1] if reset_proof_paths else None,
        )
        return {
            "configured": True,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": _integrity_hash(external) if external else None,
            "verification_status": external.get("status"),
            "runtime_status": runtime.get("status"),
            "runtime_blockers": runtime.get("blockers", []),
            "applied_reset_count": runtime.get("summary", {}).get("applied_reset_count", 0),
        }

    def _reset_proof_summaries(self, payload: ImplementationDocument) -> list[ImplementationDocument]:
        rows = []
        for path_value in _reset_proof_paths(payload):
            path = Path(path_value)
            proof = read_json(path) if path.exists() else {}
            rows.append({"path": str(path), "exists": path.exists(), "change_request_id": proof.get("change_request_id"), "reset_proof_hash": proof.get("integrity_hash"), "previous_signoff_hash": proof.get("previous_signoff_hash"), "reset_event_hash": proof.get("reset_event_hash"), "status": proof.get("status"), "integrity_ok": _integrity_ok(proof)})
        return rows

    def _archive_history_items(self, train_id: str) -> list[ImplementationDocument]:
        items = []
        base = self.train_store.archive_history_dir(train_id)
        if not base.exists():
            return []
        for path in sorted(base.iterdir()):
            if not path.is_dir():
                continue
            entry_path = path / "archive-history-entry.json"
            entry = read_json(entry_path) if entry_path.exists() else {}
            archive_zip = path / "archive" / "unified-command-center-release-train.zip"
            manifest_path = path / "archive" / "manifest.json"
            manifest = read_json(manifest_path) if manifest_path.exists() else {}
            row = {"previous_signoff_hash": entry.get("previous_signoff_hash") or "", "entry_hash": entry.get("integrity_hash"), "archive_zip_sha256": _sha256_path(archive_zip), "archive_manifest_hash": manifest.get("integrity_hash"), "path_hint": path.name}
            items.append(sanitize_metadata(row))
        return items

    def _lifecycle_ledger(self, train_id: str, train_history: list[ImplementationDocument]) -> list[ImplementationDocument]:
        source_rows: list[ImplementationDocument] = []
        for event in train_history:
            source_rows.append({"source": "release_train_history", "event": event})
        base = self.change_control_store.change_dir(train_id) / "change-requests"
        if base.exists():
            for path in sorted(base.glob("*/change-request-history.jsonl")):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        source_rows.append({"source": "change_request_history", "event": json.loads(line)})
        rows: list[ImplementationDocument] = []
        previous = ""
        for index, source in enumerate(source_rows, start=1):
            raw = source["event"]
            event = sanitize_metadata(
                {
                    "event_id": f"tle-{index:06d}",
                    "event_type": _lifecycle_event_type(str(raw.get("event_type") or "")),
                    "created_at": raw.get("created_at") or raw.get("at"),
                    "source": source["source"],
                    "train_id": train_id,
                    "signoff_hash": raw.get("signoff_hash") or raw.get("previous_signoff_hash"),
                    "change_request_id": raw.get("change_request_id"),
                    "source_event_hash": raw.get("event_hash"),
                    "source_payload_hash": raw.get("payload_hash"),
                    "previous_event_hash": previous,
                }
            )
            event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
            event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
            previous = str(event["event_hash"])
            rows.append(event)
        return rows

    def _saved_inputs(self, train_id: str) -> ImplementationDocument:
        return read_json(self.source_inputs_path(train_id)) if self.source_inputs_path(train_id).exists() else {}

    def _saved_input(self, train_id: str, key: str) -> Any:
        return self._saved_inputs(train_id).get(key)


def _source_inputs(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "external_evidence_manifest": _path_text(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path")),
        "train_archive": _path_text(payload.get("train_archive") or payload.get("train_archive_path")),
        "train_archive_verification_report": _path_text(payload.get("train_archive_verification_report") or payload.get("train_archive_verification_report_path")),
        "train_signoff_binding": _path_text(payload.get("train_signoff_binding") or payload.get("train_signoff_binding_path")),
        "change_control_zip": _path_text(payload.get("change_control_zip") or payload.get("change_control_zip_path")),
        "change_control_verification_report": _path_text(payload.get("change_control_verification_report") or payload.get("change_control_verification_report_path")),
        "reset_proofs": [_path_text(path) for path in _reset_proof_paths(payload)],
    }


def _merge_inputs(saved: ImplementationDocument, incoming: ImplementationDocument) -> ImplementationDocument:
    merged = dict(saved)
    for key, value in incoming.items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def _path_text(value: Any) -> str | None:
    return str(value) if value else None


def _reset_proof_paths(payload: ImplementationDocument) -> list[str]:
    value = payload.get("reset_proofs") or payload.get("reset_proof_paths")
    rows: list[_InferenceType] = []
    if isinstance(value, list):
        rows.extend(str(item) for item in value if item)
    elif value:
        rows.append(str(value))
    single = payload.get("reset_proof") or payload.get("reset_proof_path")
    if single:
        rows.append(str(single))
    return rows


def _succession_map(train_id: str, source_hash: str, signoff_events: list[ImplementationDocument], reset_events: list[ImplementationDocument], archive_history_items: list[ImplementationDocument], current_train: ImplementationDocument) -> ImplementationDocument:
    reset_by_hash = {event.get("previous_signoff_hash"): event for event in reset_events}
    archive_by_hash = {row.get("previous_signoff_hash"): row for row in archive_history_items}
    items = []
    for index, event in enumerate(signoff_events, start=1):
        signoff_hash = event.get("signoff_hash")
        reset = reset_by_hash.get(signoff_hash)
        row = {"generation": index, "signoff_hash": signoff_hash, "status": "reset" if reset else "current", "signed_by": event.get("signed_by"), "signed_at": event.get("created_at"), "archive_zip_sha256": current_train.get("zip_sha256") if not reset else archive_by_hash.get(signoff_hash, {}).get("archive_zip_sha256"), "verification_report_hash": current_train.get("verification_report_hash") if not reset else None}
        if reset:
            row.update({"reset_by_change_request_id": reset.get("change_request_id"), "reset_event_hash": reset.get("event_hash"), "archive_history_entry_hash": archive_by_hash.get(signoff_hash, {}).get("entry_hash")})
        items.append(sanitize_metadata(row))
    return {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_signoff_succession_map", "train_id": train_id, "source_hash": source_hash, "items": items, "summary": {"generation_count": len(items), "current_generation": len(items), "reset_count": len(reset_events)}}


def _coverage_doc(train_id: str, source_hash: str, reset_events: list[ImplementationDocument], reset_proofs: list[ImplementationDocument], change_summary: ImplementationDocument, archive_history_items: list[ImplementationDocument]) -> ImplementationDocument:
    proofs_by_event = {row.get("reset_event_hash"): row for row in reset_proofs}
    history_hashes = {row.get("previous_signoff_hash") for row in archive_history_items}
    items = []
    for event in reset_events:
        proof = proofs_by_event.get(event.get("event_hash"), {})
        archive_ok = event.get("previous_signoff_hash") in history_hashes
        passed = bool(proof.get("integrity_ok") and archive_ok and change_summary.get("runtime_status") == "passed")
        items.append({"change_request_id": event.get("change_request_id"), "request_status": "applied", "approval_status": "approved", "reset_proof_status": "passed" if proof.get("integrity_ok") else "failed", "binding_report_status": "passed" if change_summary.get("runtime_status") == "passed" else "failed", "single_use_status": "passed", "current_binding_at_approval": "passed", "archive_history_status": "passed" if archive_ok else "failed", "status": "passed" if passed else "failed", "reset_event_hash": event.get("event_hash"), "previous_signoff_hash": event.get("previous_signoff_hash")})
    return {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_change_reset_coverage", "train_id": train_id, "source_hash": source_hash, "items": items, "summary": {"request_count": len(items), "applied_count": len(items), "failed_count": sum(1 for row in items if row.get("status") != "passed")}}


def _readiness_doc(train_id: str, source_hash: str, state: ImplementationDocument, train_summary: ImplementationDocument, change_summary: ImplementationDocument, coverage: ImplementationDocument) -> ImplementationDocument:
    checks = [
        {"check_id": "current_train_signed", "status": "passed" if state.get("status") == "signed" else "failed"},
        {"check_id": "current_train_archive_verified", "status": "passed" if train_summary.get("runtime_status") == "passed" and train_summary.get("verification_status") == "passed" and train_summary.get("zip_sha256") == train_summary.get("external_report_zip_sha256") and train_summary.get("manifest_hash") == train_summary.get("external_report_manifest_hash") else "failed"},
        {"check_id": "no_open_approved_change_request", "status": "passed" if change_summary.get("runtime_status") != "pending_reset" else "failed"},
        {"check_id": "reset_history_covered", "status": "passed" if int(coverage.get("summary", {}).get("failed_count") or 0) == 0 else "failed"},
    ]
    return {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_current_readiness_assertion", "train_id": train_id, "source_hash": source_hash, "status": "passed" if all(row["status"] == "passed" for row in checks) else "failed", "checks": checks}


def _gap_items(readiness: ImplementationDocument, coverage: ImplementationDocument, has_reset: bool, change_summary: ImplementationDocument) -> list[ImplementationDocument]:
    gaps = []
    for index, check in enumerate(readiness.get("checks", []), start=1):
        if check.get("status") != "passed":
            gaps.append({"gap_id": f"gap-{index:03d}", "severity": "blocking", "category": check.get("check_id"), "message": f"{check.get('check_id')} failed.", "recommended_action": "Refresh required train lifecycle evidence and rebuild lifecycle audit."})
    if has_reset and not change_summary.get("configured"):
        gaps.append({"gap_id": "gap-change-control", "severity": "blocking", "category": "change_control", "message": "Release Train has reset history but Change Control evidence is missing.", "recommended_action": "Export and verify Change Control package with reset proof."})
    for row in coverage.get("items", []):
        if row.get("status") != "passed":
            gaps.append({"gap_id": f"gap-reset-{row.get('change_request_id')}", "severity": "blocking", "category": "reset_coverage", "message": "Reset coverage is incomplete.", "recommended_action": "Provide reset proof and archive-history evidence."})
    return gaps


def _evidence_index_doc(train_id: str, source_hash: str, train_summary: ImplementationDocument, change_summary: ImplementationDocument, reset_proofs: list[ImplementationDocument]) -> ImplementationDocument:
    items = [
        {"evidence_type": "current_train", **{key: train_summary.get(key) for key in ("zip_sha256", "manifest_hash", "verification_report_hash", "signoff_binding_hash", "external_evidence_manifest_hash", "runtime_status")}},
    ]
    if change_summary.get("configured"):
        items.append({"evidence_type": "change_control", **{key: change_summary.get(key) for key in ("zip_sha256", "manifest_hash", "verification_report_hash", "runtime_status", "applied_reset_count")}})
    for proof in reset_proofs:
        items.append({"evidence_type": "reset_proof", "change_request_id": proof.get("change_request_id"), "reset_proof_hash": proof.get("reset_proof_hash"), "reset_event_hash": proof.get("reset_event_hash")})
    return {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_lifecycle_evidence_fingerprint_index", "train_id": train_id, "source_hash": source_hash, "items": sanitize_metadata(items), "summary": {"item_count": len(items)}}


def _lifecycle_event_type(event_type: str) -> str:
    mapping = {
        "ucc_release_train_signoff_created": "train_signoff_created",
        "ucc_release_train_archive_exported": "train_archive_exported",
        "ucc_release_train_archive_built": "train_archive_built",
        "ucc_release_train_signoff_reset": "train_signoff_reset",
        "train_change_request_submitted": "train_change_request_submitted",
        "train_change_request_approved": "train_change_request_approved",
        "train_change_request_reset_applied": "train_change_request_reset_applied",
    }
    return mapping.get(event_type, event_type or "unknown")


def _manifest_document(train_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_LIFECYCLE_PACKAGE_TYPE,
            "train_id": train_id,
            "created_at": now_iso(),
            "source_hash": docs["report"].get("source_hash"),
            "source": {
                "report_hash": docs["report"].get("integrity_hash"),
                "succession_hash": docs["succession"].get("integrity_hash"),
                "coverage_hash": docs["coverage"].get("integrity_hash"),
                "archive_history_hash": docs["archive_history"].get("integrity_hash"),
                "readiness_hash": docs["readiness"].get("integrity_hash"),
                "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
                "evidence_index_hash": docs["evidence_index"].get("integrity_hash"),
                "ledger_hash": stable_hash(docs["ledger"]),
            },
            "summary": docs["report"].get("summary", {}),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _reviewer_guide(docs: ImplementationDocument) -> str:
    summary = docs["report"].get("summary", {})
    return "\n".join(
        [
            "# Release Train Lifecycle Audit",
            "",
            f"Status: {docs['report'].get('status')}",
            f"Signoffs: {summary.get('signoff_count')}",
            f"Resets: {summary.get('reset_count')}",
            "",
            "Use the offline verifier with the current Release Train archive, Change Control package, signoff binding, external evidence manifest, and reset proof files.",
            "",
        ]
    )


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    doc = sanitize_metadata(doc)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
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
