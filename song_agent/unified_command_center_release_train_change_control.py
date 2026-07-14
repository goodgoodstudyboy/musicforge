from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStateError, UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import (
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_PACKAGE_TYPE,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
    verify_unified_command_center_release_train_change_control_package,
    write_unified_command_center_release_train_change_control_verification_report,
)
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package


class UnifiedCommandCenterReleaseTrainChangeControlError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainChangeControlNotFoundError(UnifiedCommandCenterReleaseTrainChangeControlError):
    pass


class UnifiedCommandCenterReleaseTrainChangeControlStateError(UnifiedCommandCenterReleaseTrainChangeControlError):
    pass


class UnifiedCommandCenterReleaseTrainChangeControlStore:
    def __init__(self, train_store: UnifiedCommandCenterReleaseTrainStore | None = None) -> None:
        self.train_store = train_store or UnifiedCommandCenterReleaseTrainStore()
        self.lock = threading.RLock()

    def change_dir(self, train_id: str) -> Path:
        return self.train_store.train_dir(train_id) / "change-control"

    def request_dir(self, train_id: str, request_id: str) -> Path:
        return self.change_dir(train_id) / "change-requests" / _safe_id(request_id)

    def request_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "train-change-request.json"

    def impact_report_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "change-impact-report.json"

    def approval_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "change-approval.json"

    def reset_proof_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "reset-proof.json"

    def binding_report_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "change-request-binding-report.json"

    def request_history_path(self, train_id: str, request_id: str) -> Path:
        return self.request_dir(train_id, request_id) / "change-request-history.jsonl"

    def report_path(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "change-control-report.json"

    def index_path(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "change-control-index.json"

    def summaries_path(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "change-request-summaries.json"

    def history_export_path(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "change-request-history.jsonl"

    def archive_history_index_path(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "archive-history-index.json"

    def export_dir(self, train_id: str) -> Path:
        return self.change_dir(train_id) / "export"

    def manifest_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "manifest.json"

    def zip_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "unified-command-center-release-train-change-control.zip"

    def verification_report_path(self, train_id: str) -> Path:
        return self.export_dir(train_id) / "unified-command-center-release-train-change-control-verification-report.json"

    def create_request(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._require_signed_train(train_id)
            request_id = _safe_id(str(payload.get("change_request_id") or payload.get("request_id") or self._next_request_id(train_id)))
            if self.request_path(train_id, request_id).exists():
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError(f"Train Change Request already exists: {request_id}")
            binding = self._current_train_binding(train_id, payload)
            now = now_iso()
            change_set = _change_set(payload.get("change_set") or payload.get("changes") or payload.get("change") or [])
            request = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_change_request",
                    "train_id": train_id,
                    "change_request_id": request_id,
                    "status": "submitted",
                    "requested_by": _bounded(payload.get("requested_by") or "release-train-operator", 120),
                    "reason": _bounded(payload.get("reason") or "Release Train evidence changed after signoff.", 1000),
                    "change_type": _bounded(payload.get("change_type") or "evidence_refresh", 120),
                    "change_set": change_set,
                    "change_set_hash": stable_hash(change_set),
                    "created_at": now,
                    "updated_at": now,
                    "current_train_binding": binding,
                    "tool": {"name": "MusicForge Unified Command Center Release Train Change Request", "version": __version__},
                }
            )
            request["integrity_hash"] = _integrity_hash(request)
            impact = self._impact_report(train_id, request)
            write_json(self.request_path(train_id, request_id), request)
            write_json(self.impact_report_path(train_id, request_id), impact)
            self._append_request_history(train_id, request_id, {"event_type": "train_change_request_submitted", "created_at": now, "train_id": train_id, "change_request_id": request_id, "request_hash": request.get("integrity_hash"), "impact_report_hash": impact.get("integrity_hash")})
            self.refresh_report(train_id)
            return request

    def approve_request(self, train_id: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            request = self.read_request(train_id, request_id)
            if request.get("status") not in {"submitted", "draft"}:
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Only submitted Train Change Requests can be approved.")
            self._assert_binding_current(train_id, request, payload)
            now = now_iso()
            approval = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_change_approval",
                    "train_id": train_id,
                    "change_request_id": request_id,
                    "status": "approved",
                    "approved_by": _bounded(payload.get("approved_by") or "release-train-owner", 120),
                    "role": _bounded(payload.get("role") or "release_train_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Approved controlled Release Train reset.", 1000),
                    "approved_at": now,
                    "request_hash": request.get("integrity_hash"),
                    "current_train_binding": request.get("current_train_binding"),
                }
            )
            approval["payload_hash"] = stable_hash({key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}})
            approval["integrity_hash"] = _integrity_hash(approval)
            request["status"] = "approved"
            request["approved_at"] = now
            request["approval_hash"] = approval.get("integrity_hash")
            request["updated_at"] = now
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.request_path(train_id, request_id), request)
            write_json(self.approval_path(train_id, request_id), approval)
            self._append_request_history(train_id, request_id, {"event_type": "train_change_request_approved", "created_at": now, "train_id": train_id, "change_request_id": request_id, "request_hash": request.get("integrity_hash"), "approval_hash": approval.get("integrity_hash")})
            self.refresh_report(train_id)
            return approval

    def reset_train_signoff(self, train_id: str, request_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            request = self.read_request(train_id, request_id)
            if request.get("status") != "approved" or request.get("applied_at"):
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Train Change Request must be approved and unused before reset.")
            if not self.approval_path(train_id, request_id).exists():
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Approved Train Change Request is missing approval proof.")
            approval = read_json(self.approval_path(train_id, request_id))
            if not _integrity_ok(approval) or approval.get("status") != "approved":
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Train Change Request approval integrity failed.")
            self._assert_binding_current(train_id, request, payload)
            current = request.get("current_train_binding") or {}
            previous_signoff_hash = str(current.get("signoff_hash") or "")
            if not previous_signoff_hash:
                raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Train Change Request does not bind a signed train.")
            self._copy_archive_history(train_id, previous_signoff_hash)
            archive_dir = self.train_store.archive_dir(train_id)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            now = now_iso()
            reset_event = self.train_store._append_history(
                train_id,
                {
                    "event_type": "ucc_release_train_signoff_reset",
                    "created_at": now,
                    "train_id": train_id,
                    "change_request_id": request_id,
                    "approval_hash": approval.get("integrity_hash"),
                    "previous_signoff_hash": previous_signoff_hash,
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "previous_archive_zip_sha256": current.get("archive_zip_sha256"),
                    "previous_archive_manifest_hash": current.get("archive_manifest_hash"),
                    "previous_verification_report_hash": current.get("verification_report_hash"),
                    "external_evidence_manifest_hash": current.get("external_evidence_manifest_hash"),
                    "reset_by": _bounded(payload.get("reset_by") or approval.get("approved_by") or "release-train-owner", 120),
                    "reason": _bounded(payload.get("reason") or approval.get("reason") or "Approved Release Train reset.", 1000),
                },
            )
            reset_proof = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_reset_proof",
                    "train_id": train_id,
                    "change_request_id": request_id,
                    "status": "applied",
                    "applied_at": now,
                    "approval_hash": approval.get("integrity_hash"),
                    "request_hash": request.get("integrity_hash"),
                    "previous_signoff_hash": previous_signoff_hash,
                    "previous_signoff_binding_hash": current.get("signoff_binding_hash"),
                    "reset_event_hash": reset_event.get("event_hash"),
                    "reset_event_payload_hash": reset_event.get("payload_hash"),
                    "current_train_binding": current,
                }
            )
            reset_proof["integrity_hash"] = _integrity_hash(reset_proof)
            binding_report = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_change_request_binding_report",
                    "train_id": train_id,
                    "change_request_id": request_id,
                    "status": "applied",
                    "request_hash": request.get("integrity_hash"),
                    "approval_hash": approval.get("integrity_hash"),
                    "reset_proof_hash": reset_proof.get("integrity_hash"),
                    "current_train_binding": current,
                }
            )
            binding_report["integrity_hash"] = _integrity_hash(binding_report)
            request["status"] = "applied"
            request["applied_at"] = now
            request["reset_event_hash"] = reset_event.get("event_hash")
            request["reset_proof_hash"] = reset_proof.get("integrity_hash")
            request["binding_report_hash"] = binding_report.get("integrity_hash")
            request["updated_at"] = now
            request["integrity_hash"] = _integrity_hash(request)
            write_json(self.request_path(train_id, request_id), request)
            write_json(self.reset_proof_path(train_id, request_id), reset_proof)
            write_json(self.binding_report_path(train_id, request_id), binding_report)
            self._append_request_history(train_id, request_id, {"event_type": "train_change_request_reset_applied", "created_at": now, "train_id": train_id, "change_request_id": request_id, "request_hash": request.get("integrity_hash"), "approval_hash": approval.get("integrity_hash"), "reset_proof_hash": reset_proof.get("integrity_hash"), "reset_event_hash": reset_event.get("event_hash")})
            train = self.train_store.read_train(train_id)
            train["status"] = "reset"
            train["previous_signoff_hash"] = previous_signoff_hash
            train["reset_at"] = now
            train["updated_at"] = now
            train["integrity_hash"] = _integrity_hash(train)
            write_json(self.train_store.train_path(train_id), train)
            self.refresh_report(train_id)
            return reset_proof

    def list_requests(self, train_id: str) -> list[dict[str, Any]]:
        base = self.change_dir(train_id) / "change-requests"
        if not base.exists():
            return []
        rows = []
        for path in sorted(base.glob("*/train-change-request.json")):
            rows.append(read_json(path))
        return rows

    def read_request(self, train_id: str, request_id: str) -> dict[str, Any]:
        path = self.request_path(train_id, request_id)
        if not path.exists():
            raise UnifiedCommandCenterReleaseTrainChangeControlNotFoundError(f"Train Change Request not found: {request_id}")
        return read_json(path)

    def refresh_report(self, train_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._build_documents(train_id)
            self.change_dir(train_id).mkdir(parents=True, exist_ok=True)
            write_json(self.report_path(train_id), docs["report"])
            write_json(self.index_path(train_id), docs["index"])
            write_json(self.summaries_path(train_id), docs["summaries"])
            write_json(self.archive_history_index_path(train_id), docs["archive_history"])
            self.history_export_path(train_id).write_text(docs["history_text"], encoding="utf-8")
            return docs["report"]

    def export_package(self, train_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._build_documents(train_id)
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

            write_entry("change-control-report.json", docs["report"])
            write_entry("change-control-index.json", docs["index"])
            write_entry("change-request-summaries.json", docs["summaries"])
            write_entry("change-request-history.jsonl", docs["history_text"])
            write_entry("archive-history-index.json", docs["archive_history"])
            write_entry("README.txt", "MusicForge Unified Command Center Release Train Change Control\n")
            manifest = _manifest_document(train_id, docs, files)
            write_json(self.manifest_path(train_id), manifest)
            return manifest

    def build_zip(self, train_id: str) -> dict[str, Any]:
        with self.lock:
            if not self.manifest_path(train_id).exists():
                self.export_package(train_id)
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
        report = verify_unified_command_center_release_train_change_control_package(
            self.zip_path(train_id),
            strict=bool(payload.get("strict", True)),
            require_reset_applied=bool(payload.get("require_reset_applied", False)),
            require_current_train=bool(payload.get("require_current_train", False)),
            train_archive_path=payload.get("train_archive") or payload.get("train_archive_path") or self.train_store.zip_path(train_id),
            train_archive_verification_report_path=payload.get("train_archive_verification_report") or payload.get("train_archive_verification_report_path") or self.train_store.verification_report_path(train_id),
            train_signoff_binding_path=payload.get("train_signoff_binding") or payload.get("train_signoff_binding_path") or self.train_store.signoff_binding_path(train_id),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"),
            reset_proof_path=payload.get("reset_proof") or payload.get("reset_proof_path"),
        )
        write_unified_command_center_release_train_change_control_verification_report(report, self.verification_report_path(train_id))
        return report

    def gate(self, train_id: str, *, required: bool = False, package_zip_path: Path | str | None = None, verification_report_path: Path | str | None = None, **payload: Any) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(package_zip_path) if package_zip_path else self.zip_path(train_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(train_id)
        if not zip_path.exists():
            return _gate_failed("Release Train Change Control ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Release Train Change Control verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_command_center_release_train_change_control_package(
                zip_path,
                strict=True,
                require_current_train=True,
                train_archive_path=payload.get("train_archive_path") or self.train_store.zip_path(train_id),
                train_archive_verification_report_path=payload.get("train_archive_verification_report_path") or self.train_store.verification_report_path(train_id),
                train_signoff_binding_path=payload.get("train_signoff_binding_path") or self.train_store.signoff_binding_path(train_id),
                external_evidence_manifest_path=payload.get("external_evidence_manifest_path"),
                reset_proof_path=payload.get("reset_proof_path"),
            )
            if not _integrity_ok(external):
                return _gate_failed("Release Train Change Control verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Release Train Change Control verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Release Train Change Control verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Release Train Change Control gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _require_signed_train(self, train_id: str) -> None:
        if self.train_store.latest_signoff_state(train_id).get("status") != "signed":
            raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Release Train must be currently signed.")

    def _current_train_binding(self, train_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_signed_train(train_id)
        signoff = read_json(self.train_store.signoff_path(train_id))
        binding = read_json(self.train_store.signoff_binding_path(train_id))
        verification = read_json(self.train_store.verification_report_path(train_id)) if self.train_store.verification_report_path(train_id).exists() else {}
        evidence_manifest_path = payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path")
        if not evidence_manifest_path:
            raise UnifiedCommandCenterReleaseTrainChangeControlStateError("external_evidence_manifest is required for Train Change Control.")
        evidence_manifest = read_json(Path(evidence_manifest_path))
        archive_zip = self.train_store.zip_path(train_id)
        archive_manifest = read_json(self.train_store.archive_manifest_path(train_id)) if self.train_store.archive_manifest_path(train_id).exists() else {}
        runtime = verify_unified_command_center_release_train_package(
            archive_zip,
            strict=True,
            require_go=True,
            require_signed=True,
            external_evidence_manifest_path=evidence_manifest_path,
            signoff_binding_path=self.train_store.signoff_binding_path(train_id),
        )
        if runtime.get("status") != "passed" or verification.get("status") != "passed":
            raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Current Release Train archive verification must be passed before Change Control.")
        if verification.get("zip_sha256") != runtime.get("zip_sha256") or verification.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedCommandCenterReleaseTrainChangeControlStateError("Current Release Train verification report is stale.")
        return sanitize_metadata(
            {
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "signoff_binding_hash": binding.get("integrity_hash"),
                "archive_zip_sha256": _sha256_path(archive_zip),
                "archive_manifest_hash": archive_manifest.get("integrity_hash"),
                "verification_report_hash": _integrity_hash(verification),
                "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
                "source_hash": signoff.get("source_hash"),
                "go_no_go_report_hash": signoff.get("go_no_go_report_hash"),
            }
        )

    def _assert_binding_current(self, train_id: str, request: dict[str, Any], payload: dict[str, Any]) -> None:
        current = self._current_train_binding(train_id, payload)
        expected = request.get("current_train_binding") or {}
        keys = ("signoff_hash", "signoff_binding_hash", "archive_zip_sha256", "archive_manifest_hash", "verification_report_hash", "external_evidence_manifest_hash", "source_hash")
        mismatched = [key for key in keys if current.get(key) != expected.get(key)]
        if mismatched:
            raise UnifiedCommandCenterReleaseTrainChangeControlStateError(f"Train Change Request binding is stale: {', '.join(mismatched)}")

    def _copy_archive_history(self, train_id: str, signoff_hash: str) -> None:
        target = self.train_store.archive_history_signoff_dir(train_id, signoff_hash)
        if target.exists():
            return
        target.mkdir(parents=True, exist_ok=True)
        entry = {"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_archive_history_entry", "train_id": train_id, "previous_signoff_hash": signoff_hash, "created_at": now_iso()}
        entry["integrity_hash"] = _integrity_hash(entry)
        write_json(target / "archive-history-entry.json", entry)
        archive_dir = self.train_store.archive_dir(train_id)
        if archive_dir.exists():
            shutil.copytree(archive_dir, target / "archive", dirs_exist_ok=True)
        for rel, path in (
            ("train-signoff.json", self.train_store.signoff_path(train_id)),
            ("train-signoff-binding-summary.json", self.train_store.signoff_binding_path(train_id)),
            ("train-history.jsonl", self.train_store.history_path(train_id)),
        ):
            if path.exists():
                shutil.copy2(path, target / rel)

    def _build_documents(self, train_id: str) -> dict[str, Any]:
        requests = self.list_requests(train_id)
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_change_control_source",
                "train_id": train_id,
                "created_at": now_iso(),
                "train_hash": self.train_store.read_train(train_id).get("integrity_hash"),
                "train_signoff_state": self.train_store.latest_signoff_state(train_id),
                "request_hashes": [row.get("integrity_hash") for row in requests],
                "archive_history_hashes": self._archive_history_hashes(train_id),
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        rows = [self._request_summary(train_id, row) for row in requests]
        summaries = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_change_request_summaries", "train_id": train_id, "source_hash": source["source_hash"], "requests": rows, "summary": {"request_count": len(rows), "approved_count": sum(1 for row in rows if row.get("status") == "approved"), "applied_reset_count": sum(1 for row in rows if row.get("status") == "applied")}})
        summaries["integrity_hash"] = _integrity_hash(summaries)
        index = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_change_control_index", "train_id": train_id, "source_hash": source["source_hash"], "items": rows, "summary": summaries["summary"]})
        index["integrity_hash"] = _integrity_hash(index)
        archive_history = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_archive_history_index", "train_id": train_id, "source_hash": source["source_hash"], "items": self._archive_history_items(train_id), "summary": {"history_count": len(self._archive_history_items(train_id))}})
        archive_history["integrity_hash"] = _integrity_hash(archive_history)
        status = "passed" if not any(row.get("status") == "approved" for row in rows) else "pending_reset"
        report = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_change_control_report", "train_id": train_id, "created_at": now_iso(), "source_hash": source["source_hash"], "status": status, "summary": summaries["summary"], "current_train": self._current_train_summary(train_id)})
        report["integrity_hash"] = _integrity_hash(report)
        return {"source": source, "report": report, "index": index, "summaries": summaries, "archive_history": archive_history, "history_text": self._combined_history_text(train_id)}

    def _current_train_summary(self, train_id: str) -> dict[str, Any]:
        archive_zip = self.train_store.zip_path(train_id)
        manifest = read_json(self.train_store.archive_manifest_path(train_id)) if self.train_store.archive_manifest_path(train_id).exists() else {}
        verification = read_json(self.train_store.verification_report_path(train_id)) if self.train_store.verification_report_path(train_id).exists() else {}
        return {"signoff_state": self.train_store.latest_signoff_state(train_id), "archive_zip_sha256": _sha256_path(archive_zip), "archive_manifest_hash": manifest.get("integrity_hash"), "verification_report_hash": _integrity_hash(verification) if verification else None, "verification_status": verification.get("status")}

    def _request_summary(self, train_id: str, request: dict[str, Any]) -> dict[str, Any]:
        request_id = str(request.get("change_request_id") or "")
        approval = read_json(self.approval_path(train_id, request_id)) if self.approval_path(train_id, request_id).exists() else {}
        reset_proof = read_json(self.reset_proof_path(train_id, request_id)) if self.reset_proof_path(train_id, request_id).exists() else {}
        binding_report = read_json(self.binding_report_path(train_id, request_id)) if self.binding_report_path(train_id, request_id).exists() else {}
        return sanitize_metadata({"change_request_id": request_id, "status": request.get("status"), "reason": request.get("reason"), "change_type": request.get("change_type"), "change_set_hash": request.get("change_set_hash"), "request_hash": request.get("integrity_hash"), "approval_hash": approval.get("integrity_hash") or request.get("approval_hash"), "reset_proof_hash": reset_proof.get("integrity_hash") or request.get("reset_proof_hash"), "binding_report_hash": binding_report.get("integrity_hash") or request.get("binding_report_hash"), "reset_event_hash": request.get("reset_event_hash"), "previous_signoff_hash": (request.get("current_train_binding") or {}).get("signoff_hash")})

    def _archive_history_items(self, train_id: str) -> list[dict[str, Any]]:
        items = []
        base = self.train_store.archive_history_dir(train_id)
        if not base.exists():
            return []
        for path in sorted(base.iterdir()):
            if path.is_dir():
                entry_path = path / "archive-history-entry.json"
                entry = read_json(entry_path) if entry_path.exists() else {}
                archive_zip = path / "archive" / "unified-command-center-release-train.zip"
                manifest = path / "archive" / "manifest.json"
                items.append({"previous_signoff_hash": entry.get("previous_signoff_hash") or path.name, "archive_zip_sha256": _sha256_path(archive_zip), "archive_manifest_hash": read_json(manifest).get("integrity_hash") if manifest.exists() else None, "entry_hash": entry.get("integrity_hash")})
        return items

    def _archive_history_hashes(self, train_id: str) -> list[str]:
        return [stable_hash(item) for item in self._archive_history_items(train_id)]

    def _combined_history_text(self, train_id: str) -> str:
        rows = []
        base = self.change_dir(train_id) / "change-requests"
        if base.exists():
            for path in sorted(base.glob("*/change-request-history.jsonl")):
                rows.extend(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return "\n".join(rows) + ("\n" if rows else "")

    def _impact_report(self, train_id: str, request: dict[str, Any]) -> dict[str, Any]:
        report = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_change_impact_report", "train_id": train_id, "change_request_id": request.get("change_request_id"), "status": "requires_approval", "source_hash": (request.get("current_train_binding") or {}).get("source_hash"), "summary": {"change_type": request.get("change_type"), "change_count": len(request.get("change_set") or []), "previous_signoff_hash": (request.get("current_train_binding") or {}).get("signoff_hash")}})
        report["integrity_hash"] = _integrity_hash(report)
        return report

    def _append_request_history(self, train_id: str, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self.request_history_path(train_id, request_id)
        history = []
        if path.exists():
            history = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        previous = str(history[-1].get("event_hash") or "") if history else ""
        event = sanitize_metadata({**payload, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _next_request_id(self, train_id: str) -> str:
        base = self.change_dir(train_id) / "change-requests"
        base.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in base.glob("tcr-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"tcr-{max_seen + 1:06d}"


def _manifest_document(train_id: str, docs: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_PACKAGE_TYPE, "train_id": train_id, "created_at": now_iso(), "source_hash": docs["report"].get("source_hash"), "source": {"report_hash": docs["report"].get("integrity_hash"), "index_hash": docs["index"].get("integrity_hash"), "summaries_hash": docs["summaries"].get("integrity_hash"), "archive_history_hash": docs["archive_history"].get("integrity_hash")}, "summary": docs["report"].get("summary", {}), "files": sorted(files, key=lambda row: row.get("path") or ""), "zip": {}})
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _change_set(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = value
    else:
        rows = [value] if value else []
    result = []
    for index, item in enumerate(rows, start=1):
        if isinstance(item, dict):
            result.append(sanitize_metadata({"change_id": _safe_id(str(item.get("change_id") or f"change-{index:03d}")), "description": _bounded(item.get("description") or item.get("text") or item, 500), "risk": _bounded(item.get("risk") or "medium", 80)}))
        else:
            result.append(sanitize_metadata({"change_id": f"change-{index:03d}", "description": _bounded(item, 500), "risk": "medium"}))
    return result


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


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
