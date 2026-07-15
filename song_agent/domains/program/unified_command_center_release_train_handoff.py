from __future__ import annotations

import base64
import json
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
from song_agent.domains.program.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import (
    BASE_REQUIRED_ENTRIES,
    REQUIRED_ENTRIES,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION,
    verify_unified_command_center_release_train_handoff_package,
    write_unified_command_center_release_train_handoff_verification_report,
)
from song_agent.domains.program.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package


class UnifiedCommandCenterReleaseTrainHandoffError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainHandoffNotFoundError(UnifiedCommandCenterReleaseTrainHandoffError):
    pass


class UnifiedCommandCenterReleaseTrainHandoffStateError(UnifiedCommandCenterReleaseTrainHandoffError):
    pass


DEFAULT_POLICY = {
    "require_current_train": True,
    "require_change_control_if_resets": True,
    "require_lifecycle_audit": True,
    "require_ga_readiness": False,
    "require_release_check": False,
    "require_external_acceptance": False,
    "quorum": {"min_accepted": 1, "min_organizations": 1, "required_roles": ["release_owner"]},
}


class UnifiedCommandCenterReleaseTrainHandoffStore:
    def __init__(
        self,
        train_store: UnifiedCommandCenterReleaseTrainStore | None = None,
        change_control_store: UnifiedCommandCenterReleaseTrainChangeControlStore | None = None,
        lifecycle_store: UnifiedCommandCenterReleaseTrainLifecycleStore | None = None,
    ) -> None:
        self.train_store = train_store or UnifiedCommandCenterReleaseTrainStore()
        self.change_control_store = change_control_store or UnifiedCommandCenterReleaseTrainChangeControlStore(self.train_store)
        self.lifecycle_store = lifecycle_store or UnifiedCommandCenterReleaseTrainLifecycleStore(self.train_store, self.change_control_store)
        self.lock = threading.RLock()

    def handoffs_dir(self, train_id: str) -> Path:
        return self.train_store.train_dir(train_id) / "handoff"

    def handoff_dir(self, train_id: str, handoff_id: str) -> Path:
        return self.handoffs_dir(train_id) / _safe_id(handoff_id)

    def handoff_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff.json"

    def source_inputs_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff-source-inputs.json"

    def report_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff-report.json"

    def inventory_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "evidence-inventory.json"

    def readiness_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "readiness-matrix.json"

    def gap_plan_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "gap-plan.json"

    def external_manifest_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "external-evidence-manifest.json"

    def response_summary_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "response-summary.json"

    def accepted_summary_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "accepted-evidence-summary.json"

    def history_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff-history.jsonl"

    def signoff_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff-signoff.json"

    def signoff_binding_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "handoff-signoff-binding-summary.json"

    def responses_dir(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "responses"

    def response_dir(self, train_id: str, handoff_id: str, response_id: str) -> Path:
        return self.responses_dir(train_id, handoff_id) / _safe_id(response_id)

    def export_dir(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "export"

    def manifest_path(self, train_id: str, handoff_id: str) -> Path:
        return self.export_dir(train_id, handoff_id) / "manifest.json"

    def zip_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "release-train-final-handoff.zip"

    def verification_report_path(self, train_id: str, handoff_id: str) -> Path:
        return self.handoff_dir(train_id, handoff_id) / "release-train-final-handoff-verification-report.json"

    def create_handoff(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            handoff_id = _safe_id(str(payload.get("handoff_id") or self._next_handoff_id(train_id)))
            if self.handoff_path(train_id, handoff_id).exists():
                raise UnifiedCommandCenterReleaseTrainHandoffStateError(f"Release Train Handoff already exists: {handoff_id}")
            policy = _policy(payload.get("policy"))
            now = now_iso()
            handoff = {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_release_train_handoff_record",
                "handoff_id": handoff_id,
                "train_id": train_id,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "policy": policy,
            }
            handoff["integrity_hash"] = _integrity_hash(handoff)
            self.handoff_dir(train_id, handoff_id).mkdir(parents=True, exist_ok=True)
            write_json(self.handoff_path(train_id, handoff_id), handoff)
            self.refresh_report(train_id, handoff_id, payload)
            return self.get_handoff(train_id, handoff_id)

    def list_handoffs(self, train_id: str) -> list[dict[str, Any]]:
        if not self.handoffs_dir(train_id).exists():
            return []
        rows = []
        for path in sorted(self.handoffs_dir(train_id).glob("rth-*")):
            handoff_path = path / "handoff.json"
            if handoff_path.exists():
                rows.append(read_json(handoff_path))
        return rows

    def get_handoff(self, train_id: str, handoff_id: str | None = None) -> dict[str, Any]:
        handoff_id = handoff_id or self._latest_handoff_id(train_id)
        if not handoff_id or not self.handoff_path(train_id, handoff_id).exists():
            raise UnifiedCommandCenterReleaseTrainHandoffNotFoundError(f"Release Train Handoff not found: {train_id}/{handoff_id}")
        return {
            "handoff": read_json(self.handoff_path(train_id, handoff_id)),
            "report": _read_optional_json(self.report_path(train_id, handoff_id)),
            "inventory": _read_optional_json(self.inventory_path(train_id, handoff_id)),
            "readiness": _read_optional_json(self.readiness_path(train_id, handoff_id)),
            "gap_plan": _read_optional_json(self.gap_plan_path(train_id, handoff_id)),
            "response_summary": _read_optional_json(self.response_summary_path(train_id, handoff_id)),
            "accepted_evidence_summary": _read_optional_json(self.accepted_summary_path(train_id, handoff_id)),
            "signoff": _read_optional_json(self.signoff_path(train_id, handoff_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(train_id, handoff_id)),
            "verification": _read_optional_json(self.verification_report_path(train_id, handoff_id)),
        }

    def refresh_report(self, train_id: str, handoff_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(train_id, handoff_id)
            inputs = self._with_default_inputs(train_id, _merge_inputs(_read_optional_json(self.source_inputs_path(train_id, handoff_id)), _source_inputs(payload)))
            docs = self._build_documents(train_id, handoff_id, inputs)
            self._write_docs(train_id, handoff_id, docs)
            write_json(self.source_inputs_path(train_id, handoff_id), inputs)
            handoff = read_json(self.handoff_path(train_id, handoff_id))
            handoff["status"] = "ready" if docs["report"].get("status") == "ready" else "blocked"
            handoff["updated_at"] = now_iso()
            handoff["source_hash"] = docs["report"].get("source_hash")
            handoff["external_evidence_manifest_hash"] = docs["external_manifest"].get("integrity_hash")
            handoff["summary"] = docs["report"].get("summary", {})
            handoff["integrity_hash"] = _integrity_hash(handoff)
            write_json(self.handoff_path(train_id, handoff_id), handoff)
            return docs["report"]

    def export_handoff(self, train_id: str, handoff_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._docs_for_export(train_id, handoff_id)
            export_dir = self.export_dir(train_id, handoff_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("handoff-report.json", docs["report"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("recipient-guide.md", _recipient_guide(docs))
            write_entry("gap-plan.json", docs["gap_plan"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("response-summary.json", docs["response_summary"])
            write_entry("accepted-evidence-summary.json", docs["accepted_summary"])
            write_entry("handoff-history.jsonl", _history_text(self._read_history(train_id, handoff_id)))
            if docs.get("signoff"):
                write_entry("handoff-signoff.json", docs["signoff"])
                write_entry("handoff-signoff-binding-summary.json", docs["signoff_binding"])
            write_entry("README.txt", "MusicForge Release Train Final Handoff Board\n")
            file_index = _file_index(train_id, handoff_id, files)
            write_entry("file-index.json", file_index)
            manifest = _manifest_document(train_id, handoff_id, docs, files, file_index)
            write_json(self.manifest_path(train_id, handoff_id), manifest)
            return manifest

    def build_zip(self, train_id: str, handoff_id: str) -> dict[str, Any]:
        with self.lock:
            if not self.manifest_path(train_id, handoff_id).exists():
                self.export_handoff(train_id, handoff_id)
            else:
                try:
                    self._assert_export_current(train_id, handoff_id)
                except UnifiedCommandCenterReleaseTrainHandoffStateError:
                    if not self.signoff_path(train_id, handoff_id).exists():
                        raise
                    self.export_handoff(train_id, handoff_id)
            export_dir = self.export_dir(train_id, handoff_id)
            zip_path = self.zip_path(train_id, handoff_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(train_id, handoff_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(train_id, handoff_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": "passed", "train_id": train_id, "handoff_id": handoff_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_package(self, train_id: str, handoff_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        inputs = self._with_default_inputs(train_id, _merge_inputs(_read_optional_json(self.source_inputs_path(train_id, handoff_id)), _source_inputs(payload)))
        report = verify_unified_command_center_release_train_handoff_package(
            self.zip_path(train_id, handoff_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_lifecycle=bool(payload.get("require_lifecycle", True)),
            require_signed=bool(payload.get("require_signed", False)),
            require_accepted=bool(payload.get("require_accepted", False)),
            external_evidence_manifest_path=inputs.get("external_evidence_manifest"),
            train_archive_path=inputs.get("train_archive"),
            train_verification_report_path=inputs.get("train_verification_report"),
            train_signoff_binding_path=inputs.get("train_signoff_binding"),
            change_control_zip_path=inputs.get("change_control_zip"),
            change_control_verification_report_path=inputs.get("change_control_verification_report"),
            reset_proof_paths=_reset_proof_paths(inputs),
            lifecycle_zip_path=inputs.get("lifecycle_zip"),
            lifecycle_verification_report_path=inputs.get("lifecycle_verification_report"),
            handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(train_id, handoff_id),
            accepted_evidence_dir=payload.get("accepted_evidence_dir") or (self.responses_dir(train_id, handoff_id) if payload.get("require_accepted") else None),
        )
        write_unified_command_center_release_train_handoff_verification_report(report, self.verification_report_path(train_id, handoff_id))
        return report

    def import_response(self, train_id: str, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(train_id, handoff_id)
            if any(key in payload for key in ("source_path", "local_path", "file_path")):
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Response import does not accept source_path/local_path/file_path.")
            response = _response_from_payload(payload)
            required = {"handoff_id", "train_id", "handoff_zip_sha256", "handoff_manifest_hash", "handoff_source_hash", "handoff_verification_report_hash", "reviewer", "decision", "reviewed_at"}
            missing = sorted(key for key in required if not response.get(key))
            if missing:
                raise UnifiedCommandCenterReleaseTrainHandoffStateError(f"Response is missing required binding fields: {', '.join(missing)}")
            if response.get("handoff_id") != handoff_id or response.get("train_id") != train_id:
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Response handoff_id/train_id does not match current handoff.")
            if not self.zip_path(train_id, handoff_id).exists() or not self.verification_report_path(train_id, handoff_id).exists():
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Build and verify handoff ZIP before importing response.")
            verification = read_json(self.verification_report_path(train_id, handoff_id))
            manifest_hash = _zip_manifest_hash(self.zip_path(train_id, handoff_id))
            if response.get("handoff_zip_sha256") != _sha256_path(self.zip_path(train_id, handoff_id)) or response.get("handoff_manifest_hash") != manifest_hash:
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Response does not bind the current handoff ZIP.")
            if response.get("handoff_source_hash") != read_json(self.report_path(train_id, handoff_id)).get("source_hash"):
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Response does not bind the current handoff source.")
            if response.get("handoff_verification_report_hash") != _integrity_hash(verification):
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Response does not bind the current handoff verification report.")
            response_id = _safe_id(str(response.get("response_id") or self._next_response_id(train_id, handoff_id)))
            response["schema_version"] = UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION
            response["package_type"] = "musicforge_release_train_handoff_response"
            response["response_id"] = response_id
            response["payload_hash"] = _integrity_hash(response)
            response["integrity_hash"] = _integrity_hash(response)
            response_dir = self.response_dir(train_id, handoff_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            write_json(response_dir / "response.json", sanitize_metadata(response))
            report = self.verify_response(train_id, handoff_id, response_id)
            return {"response": response, "verification": report}

    def verify_response(self, train_id: str, handoff_id: str, response_id: str) -> dict[str, Any]:
        response_path = self.response_dir(train_id, handoff_id, response_id) / "response.json"
        if not response_path.exists():
            raise UnifiedCommandCenterReleaseTrainHandoffNotFoundError(f"Handoff response not found: {response_id}")
        response = read_json(response_path)
        checks = [
            _check("handoff_response_integrity", _integrity_ok(response), "Response integrity hash is valid."),
            _check("handoff_response_decision_valid", response.get("decision") in {"accepted", "needs_changes", "rejected"}, "Response decision is supported."),
            _check("handoff_response_current_zip", response.get("handoff_zip_sha256") == _sha256_path(self.zip_path(train_id, handoff_id)), "Response binds current handoff ZIP."),
            _check("handoff_response_current_manifest", response.get("handoff_manifest_hash") == _zip_manifest_hash(self.zip_path(train_id, handoff_id)), "Response binds current handoff manifest."),
            _check("handoff_response_current_verification", response.get("handoff_verification_report_hash") == _integrity_hash(read_json(self.verification_report_path(train_id, handoff_id))), "Response binds current handoff verification report."),
        ]
        status = "failed" if any(check["status"] == "failed" for check in checks) else "passed"
        report = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_response_verification", "response_id": response_id, "handoff_id": handoff_id, "train_id": train_id, "status": status, "checks": checks, "summary": _response_public_summary(response)}
        report["integrity_hash"] = _integrity_hash(report)
        write_json(self.response_dir(train_id, handoff_id, response_id) / "response-verification-report.json", report)
        binding = _response_binding_summary(response, report)
        write_json(self.response_dir(train_id, handoff_id, response_id) / "response-binding-summary.json", binding)
        return report

    def create_accepted_evidence(self, train_id: str, handoff_id: str, response_id: str) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(train_id, handoff_id)
            verification = self.verify_response(train_id, handoff_id, response_id)
            response = read_json(self.response_dir(train_id, handoff_id, response_id) / "response.json")
            if verification.get("status") != "passed" or response.get("decision") != "accepted":
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Only current accepted responses can create accepted evidence.")
            evidence = {
                "schema_version": 1,
                "package_type": "musicforge_release_train_handoff_accepted_evidence",
                "evidence_id": f"rthae-{response_id}",
                "response_id": response_id,
                "handoff_id": handoff_id,
                "train_id": train_id,
                "public_summary": _response_public_summary(response),
                "response_binding": _response_binding_summary(response, verification),
            }
            evidence["integrity_hash"] = _integrity_hash(evidence)
            write_json(self.response_dir(train_id, handoff_id, response_id) / "accepted-evidence.json", evidence)
            self.refresh_report(train_id, handoff_id, _read_optional_json(self.source_inputs_path(train_id, handoff_id)))
            return evidence

    def refresh_board(self, train_id: str, handoff_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.refresh_report(train_id, handoff_id, payload or {})

    def signoff(self, train_id: str, handoff_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(train_id, handoff_id)
            inputs = self._with_default_inputs(train_id, _merge_inputs(_read_optional_json(self.source_inputs_path(train_id, handoff_id)), _source_inputs(payload)))
            write_json(self.source_inputs_path(train_id, handoff_id), inputs)
            docs = self._build_documents(train_id, handoff_id, inputs)
            if docs["report"].get("status") != "ready":
                self._write_docs(train_id, handoff_id, docs)
                raise UnifiedCommandCenterReleaseTrainHandoffStateError("Release Train Handoff is not ready for signoff.")
            self._write_docs(train_id, handoff_id, docs)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": 1,
                    "package_type": "musicforge_release_train_handoff_signoff",
                    "handoff_id": handoff_id,
                    "train_id": train_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "release-train-handoff-chair", 120),
                    "role": _bounded(payload.get("role") or "release_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Release Train Handoff accepted.", 1000),
                    "signed_at": now,
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "accepted_evidence_summary_hash": docs["accepted_summary"].get("integrity_hash"),
                    "tool": {"name": "MusicForge Release Train Handoff Board", "version": __version__},
                }
            )
            signoff["payload_hash"] = _integrity_hash(signoff)
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(train_id, handoff_id), signoff)
            event = self._append_history(
                train_id,
                handoff_id,
                {
                    "event_type": "release_train_handoff_signoff_created",
                    "created_at": now,
                    "train_id": train_id,
                    "handoff_id": handoff_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "handoff_report_hash": signoff.get("handoff_report_hash"),
                    "readiness_matrix_hash": signoff.get("readiness_matrix_hash"),
                    "evidence_inventory_hash": signoff.get("evidence_inventory_hash"),
                },
            )
            binding = _signoff_binding_summary(train_id, handoff_id, signoff, event, docs)
            write_json(self.signoff_binding_path(train_id, handoff_id), binding)
            handoff = read_json(self.handoff_path(train_id, handoff_id))
            handoff["status"] = "signed"
            handoff["updated_at"] = now
            handoff["signoff_hash"] = signoff.get("integrity_hash")
            handoff["integrity_hash"] = _integrity_hash(handoff)
            write_json(self.handoff_path(train_id, handoff_id), handoff)
            return signoff

    def gate(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if not payload.get("required", True):
            return {"status": "not_required", "hard_block": False}
        handoff_id = str(payload.get("handoff_id") or self._latest_handoff_id(train_id) or "")
        if not handoff_id:
            return _gate_failed("Release Train Handoff is missing.")
        if not self.zip_path(train_id, handoff_id).exists() or not self.verification_report_path(train_id, handoff_id).exists():
            return _gate_failed("Release Train Handoff ZIP or verification report is missing.")
        runtime = self.verify_package(train_id, handoff_id, {**payload, "require_current": True, "require_lifecycle": True, "require_signed": bool(payload.get("require_signed", True)), "require_accepted": bool(payload.get("require_accepted", False))})
        external = read_json(self.verification_report_path(train_id, handoff_id))
        if runtime.get("status") != "passed" or external.get("status") != "passed":
            return _gate_failed("Release Train Handoff verification failed.", verification=runtime)
        if runtime.get("zip_sha256") != external.get("zip_sha256") or runtime.get("manifest_hash") != external.get("manifest_hash"):
            return _gate_failed("Release Train Handoff verification report is stale.", verification=runtime)
        return {"status": "passed", "hard_block": False, "message": "Release Train Handoff gate passed.", "summary": runtime.get("summary", {})}

    def _build_documents(self, train_id: str, handoff_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        handoff = read_json(self.handoff_path(train_id, handoff_id))
        policy = _policy(handoff.get("policy"))
        train_summary = self._train_summary(inputs)
        reset_count = int(train_summary.get("summary", {}).get("reset_count") or 0)
        change_summary = self._change_summary(inputs, require=reset_count > 0 and policy.get("require_change_control_if_resets", True))
        lifecycle_summary = self._lifecycle_summary(inputs, require=bool(policy.get("require_lifecycle_audit", True)), reset_count=reset_count)
        responses = self._response_summary(train_id, handoff_id)
        accepted = self._accepted_summary(train_id, handoff_id)
        external_manifest = _public_external_manifest(train_id, handoff_id, inputs, train_summary, change_summary, lifecycle_summary)
        source = {
            "schema_version": 1,
            "package_type": "musicforge_release_train_handoff_source",
            "train_id": train_id,
            "handoff_id": handoff_id,
            "policy": policy,
            "current_train_zip_sha256": train_summary.get("zip_sha256"),
            "current_train_manifest_hash": train_summary.get("manifest_hash"),
            "current_train_verification_report_hash": train_summary.get("verification_report_hash"),
            "change_control_zip_sha256": change_summary.get("zip_sha256"),
            "change_control_manifest_hash": change_summary.get("manifest_hash"),
            "change_control_verification_report_hash": change_summary.get("verification_report_hash"),
            "lifecycle_zip_sha256": lifecycle_summary.get("zip_sha256"),
            "lifecycle_manifest_hash": lifecycle_summary.get("manifest_hash"),
            "lifecycle_verification_report_hash": lifecycle_summary.get("verification_report_hash"),
            "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
            "response_summary_hash": responses.get("integrity_hash"),
            "accepted_evidence_summary_hash": accepted.get("integrity_hash"),
        }
        source_hash = stable_hash(source)
        inventory = _inventory_doc(train_id, handoff_id, source_hash, train_summary, change_summary, lifecycle_summary)
        readiness = _readiness_doc(train_id, handoff_id, source_hash, policy, inventory, accepted)
        gap_plan = _gap_plan_doc(train_id, handoff_id, source_hash, readiness)
        status = "ready" if readiness.get("summary", {}).get("status") == "ready" else "blocked" if readiness.get("summary", {}).get("critical_failed") else "manual_required"
        report = {
            "schema_version": 1,
            "package_type": "musicforge_release_train_handoff_report",
            "handoff_id": handoff_id,
            "train_id": train_id,
            "status": status,
            "source": source,
            "source_hash": source_hash,
            "created_at": now,
            "summary": {
                "readiness": readiness.get("summary", {}).get("status"),
                "train_status": train_summary.get("status"),
                "reset_count": reset_count,
                "accepted_response_count": accepted.get("summary", {}).get("accepted_count", 0),
                "blocker_count": readiness.get("summary", {}).get("critical_failed", 0),
            },
            "tool": {"name": "MusicForge Release Train Handoff Board", "version": __version__},
        }
        for doc in (external_manifest, inventory, readiness, gap_plan, responses, accepted, report):
            doc["integrity_hash"] = _integrity_hash(doc)
        return {"handoff": handoff, "report": report, "inventory": inventory, "readiness": readiness, "gap_plan": gap_plan, "external_manifest": external_manifest, "response_summary": responses, "accepted_summary": accepted}

    def _train_summary(self, inputs: dict[str, Any]) -> dict[str, Any]:
        zip_path = Path(inputs.get("train_archive") or "")
        report_path = Path(inputs.get("train_verification_report") or "")
        binding_path = Path(inputs.get("train_signoff_binding") or "")
        manifest_path = Path(inputs.get("external_evidence_manifest") or "")
        if not zip_path.exists() or not report_path.exists() or not binding_path.exists() or not manifest_path.exists():
            return {"evidence_type": "release_train_archive", "status": "missing"}
        external = read_json(report_path)
        runtime = verify_unified_command_center_release_train_package(zip_path, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=binding_path)
        return {"evidence_type": "release_train_archive", "status": "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" else "failed", "runtime_status": runtime.get("status"), "external_status": external.get("status"), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "summary": runtime.get("summary", {})}

    def _with_default_inputs(self, train_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        merged = dict(inputs or {})
        defaults: dict[str, Path] = {
            "train_archive": self.train_store.zip_path(train_id),
            "train_verification_report": self.train_store.verification_report_path(train_id),
            "train_signoff_binding": self.train_store.signoff_binding_path(train_id),
        }
        if self.change_control_store is not None:
            defaults["change_control_zip"] = self.change_control_store.zip_path(train_id)
            defaults["change_control_verification_report"] = self.change_control_store.verification_report_path(train_id)
        if self.lifecycle_store is not None:
            defaults["lifecycle_zip"] = self.lifecycle_store.zip_path(train_id)
            defaults["lifecycle_verification_report"] = self.lifecycle_store.verification_report_path(train_id)
        for key, value in defaults.items():
            if not merged.get(key) and value.exists():
                merged[key] = str(value)
        return merged

    def _change_summary(self, inputs: dict[str, Any], *, require: bool) -> dict[str, Any]:
        if not require:
            return {"evidence_type": "release_train_change_control", "required": False, "status": "not_required"}
        zip_path = Path(inputs.get("change_control_zip") or "")
        report_path = Path(inputs.get("change_control_verification_report") or "")
        if not zip_path.exists() or not report_path.exists():
            return {"evidence_type": "release_train_change_control", "required": True, "status": "missing"}
        external = read_json(report_path)
        reset_proofs = _reset_proof_paths(inputs)
        runtime = verify_unified_command_center_release_train_change_control_package(
            zip_path,
            strict=True,
            require_reset_applied=True,
            require_current_train=True,
            train_archive_path=inputs.get("train_archive"),
            train_archive_verification_report_path=inputs.get("train_verification_report"),
            train_signoff_binding_path=inputs.get("train_signoff_binding"),
            external_evidence_manifest_path=inputs.get("external_evidence_manifest"),
            reset_proof_path=reset_proofs[-1] if reset_proofs else None,
        )
        return {"evidence_type": "release_train_change_control", "required": True, "status": "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" else "failed", "runtime_status": runtime.get("status"), "external_status": external.get("status"), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "reset_proof_count": len(reset_proofs)}

    def _lifecycle_summary(self, inputs: dict[str, Any], *, require: bool, reset_count: int) -> dict[str, Any]:
        if not require:
            return {"evidence_type": "release_train_lifecycle_audit", "required": False, "status": "not_required"}
        zip_path = Path(inputs.get("lifecycle_zip") or "")
        report_path = Path(inputs.get("lifecycle_verification_report") or "")
        if not zip_path.exists() or not report_path.exists():
            return {"evidence_type": "release_train_lifecycle_audit", "required": True, "status": "missing"}
        external = read_json(report_path)
        runtime = verify_unified_command_center_release_train_lifecycle_package(
            zip_path,
            strict=True,
            require_current_train=True,
            require_change_control=reset_count > 0,
            train_archive_path=inputs.get("train_archive"),
            train_archive_verification_report_path=inputs.get("train_verification_report"),
            train_signoff_binding_path=inputs.get("train_signoff_binding"),
            external_evidence_manifest_path=inputs.get("external_evidence_manifest"),
            change_control_zip_path=inputs.get("change_control_zip"),
            change_control_verification_report_path=inputs.get("change_control_verification_report"),
            reset_proof_paths=_reset_proof_paths(inputs),
        )
        return {"evidence_type": "release_train_lifecycle_audit", "required": True, "status": "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" else "failed", "runtime_status": runtime.get("status"), "external_status": external.get("status"), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "summary": runtime.get("summary", {})}

    def _response_summary(self, train_id: str, handoff_id: str) -> dict[str, Any]:
        rows = []
        for response_path in sorted(self.responses_dir(train_id, handoff_id).glob("*/response.json")) if self.responses_dir(train_id, handoff_id).exists() else []:
            response = read_json(response_path)
            rows.append({**_response_public_summary(response), "response_id": response.get("response_id"), "response_hash": response.get("integrity_hash")})
        doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_response_summary", "handoff_id": handoff_id, "train_id": train_id, "items": rows, "summary": {"total": len(rows), "accepted": len([row for row in rows if row.get("decision") == "accepted"])}}
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _accepted_summary(self, train_id: str, handoff_id: str) -> dict[str, Any]:
        rows = []
        for path in sorted(self.responses_dir(train_id, handoff_id).glob("*/accepted-evidence.json")) if self.responses_dir(train_id, handoff_id).exists() else []:
            rows.append(_accepted_evidence_row_from_dir(path.parent))
        passed_rows = [row for row in rows if row.get("status") == "passed"]
        doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_accepted_evidence_summary", "handoff_id": handoff_id, "train_id": train_id, "items": rows, "summary": {"accepted_count": len(passed_rows), "failed_count": len(rows) - len(passed_rows), "organization_count": len({row.get("organization") for row in passed_rows if row.get("organization")}), "roles": sorted({str(row.get("reviewer_role")) for row in passed_rows if row.get("reviewer_role")})}}
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _write_docs(self, train_id: str, handoff_id: str, docs: dict[str, Any]) -> None:
        self.handoff_dir(train_id, handoff_id).mkdir(parents=True, exist_ok=True)
        write_json(self.report_path(train_id, handoff_id), docs["report"])
        write_json(self.inventory_path(train_id, handoff_id), docs["inventory"])
        write_json(self.readiness_path(train_id, handoff_id), docs["readiness"])
        write_json(self.gap_plan_path(train_id, handoff_id), docs["gap_plan"])
        write_json(self.external_manifest_path(train_id, handoff_id), docs["external_manifest"])
        write_json(self.response_summary_path(train_id, handoff_id), docs["response_summary"])
        write_json(self.accepted_summary_path(train_id, handoff_id), docs["accepted_summary"])

    def _docs_for_export(self, train_id: str, handoff_id: str) -> dict[str, Any]:
        if not self.report_path(train_id, handoff_id).exists():
            raise UnifiedCommandCenterReleaseTrainHandoffStateError("Release Train Handoff report is missing. Refresh before export.")
        docs = {
            "report": read_json(self.report_path(train_id, handoff_id)),
            "inventory": read_json(self.inventory_path(train_id, handoff_id)),
            "readiness": read_json(self.readiness_path(train_id, handoff_id)),
            "gap_plan": read_json(self.gap_plan_path(train_id, handoff_id)),
            "external_manifest": read_json(self.external_manifest_path(train_id, handoff_id)),
            "response_summary": read_json(self.response_summary_path(train_id, handoff_id)),
            "accepted_summary": read_json(self.accepted_summary_path(train_id, handoff_id)),
            "signoff": _read_optional_json(self.signoff_path(train_id, handoff_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(train_id, handoff_id)),
        }
        if docs["signoff"]:
            _assert_signed_docs_current(docs)
        return docs

    def _assert_export_current(self, train_id: str, handoff_id: str) -> None:
        docs = self._docs_for_export(train_id, handoff_id)
        manifest = read_json(self.manifest_path(train_id, handoff_id))
        if manifest.get("source_hash") != docs["report"].get("source_hash"):
            raise UnifiedCommandCenterReleaseTrainHandoffStateError("Release Train Handoff export is stale. Re-export before ZIP.")

    def _ensure_unsigned(self, train_id: str, handoff_id: str) -> None:
        handoff = read_json(self.handoff_path(train_id, handoff_id))
        if handoff.get("status") == "signed" or self.signoff_path(train_id, handoff_id).exists() or _latest_signoff_event(self._read_history(train_id, handoff_id)):
            raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed Release Train Handoff is immutable. Create a new handoff for changes.")

    def _append_history(self, train_id: str, handoff_id: str, event: dict[str, Any]) -> dict[str, Any]:
        history = self._read_history(train_id, handoff_id)
        previous = history[-1].get("event_hash") if history else ""
        event = sanitize_metadata({**event, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        history.append(event)
        self.history_path(train_id, handoff_id).parent.mkdir(parents=True, exist_ok=True)
        self.history_path(train_id, handoff_id).write_text(_history_text(history), encoding="utf-8")
        return event

    def _read_history(self, train_id: str, handoff_id: str) -> list[dict[str, Any]]:
        path = self.history_path(train_id, handoff_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _next_handoff_id(self, train_id: str) -> str:
        existing = [path.name for path in self.handoffs_dir(train_id).glob("rth-*")] if self.handoffs_dir(train_id).exists() else []
        return f"rth-{len(existing) + 1:06d}"

    def _latest_handoff_id(self, train_id: str) -> str:
        rows = self.list_handoffs(train_id)
        return str(rows[-1]["handoff_id"]) if rows else ""

    def _next_response_id(self, train_id: str, handoff_id: str) -> str:
        existing = [path.name for path in self.responses_dir(train_id, handoff_id).glob("rthr-*")] if self.responses_dir(train_id, handoff_id).exists() else []
        return f"rthr-{len(existing) + 1:06d}"


def _source_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    keys = ["external_evidence_manifest", "train_archive", "train_verification_report", "train_signoff_binding", "change_control_zip", "change_control_verification_report", "lifecycle_zip", "lifecycle_verification_report"]
    doc = {key: str(payload[key]) for key in keys if payload.get(key)}
    if payload.get("train_archive_verification_report") and not doc.get("train_verification_report"):
        doc["train_verification_report"] = str(payload["train_archive_verification_report"])
    proofs = payload.get("reset_proofs") or payload.get("reset_proof_paths") or payload.get("reset_proof") or []
    if isinstance(proofs, (str, Path)):
        proofs = [proofs]
    if proofs:
        doc["reset_proofs"] = [str(item) for item in proofs]
    return doc


def _merge_inputs(saved: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(saved or {})
    for key, value in (incoming or {}).items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def _reset_proof_paths(inputs: dict[str, Any]) -> list[Path]:
    values = inputs.get("reset_proofs") or []
    if isinstance(values, (str, Path)):
        values = [values]
    return [Path(value) for value in values if str(value)]


def _policy(value: Any) -> dict[str, Any]:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "quorum" and isinstance(item, dict):
                policy["quorum"].update(item)
            else:
                policy[key] = item
    return policy


def _inventory_doc(train_id: str, handoff_id: str, source_hash: str, *summaries: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        rows.append({key: value for key, value in summary.items() if key not in {"runtime", "external_report"}})
    failed = len([row for row in rows if row.get("status") == "failed"])
    missing = len([row for row in rows if row.get("status") == "missing"])
    passed = len([row for row in rows if row.get("status") == "passed"])
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_evidence_inventory", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "items": rows, "summary": {"total": len(rows), "passed": passed, "failed": failed, "missing": missing, "stale": 0}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_doc(train_id: str, handoff_id: str, source_hash: str, policy: dict[str, Any], inventory: dict[str, Any], accepted: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in inventory.get("items", []):
        status = "passed" if row.get("status") in {"passed", "not_required"} else "failed"
        rows.append({"check_id": f"{row.get('evidence_type')}_verified", "status": status, "severity": "critical", "evidence_refs": [row.get("evidence_type")]})
    quorum = policy.get("quorum", {})
    accepted_items = [row for row in accepted.get("items", []) if isinstance(row, dict) and row.get("status") == "passed"]
    roles = {str(row.get("reviewer_role")) for row in accepted_items}
    orgs = {str(row.get("organization")) for row in accepted_items if row.get("organization")}
    required_roles = set(str(role) for role in quorum.get("required_roles", []))
    acceptance_required = bool(policy.get("require_external_acceptance"))
    acceptance_passed = len(accepted_items) >= int(quorum.get("min_accepted", 1)) and len(orgs) >= int(quorum.get("min_organizations", 1)) and required_roles.issubset(roles)
    rows.append({"check_id": "handoff_acceptance_quorum", "status": "passed" if acceptance_passed or not acceptance_required else "failed", "severity": "high" if not acceptance_required else "critical", "evidence_refs": ["accepted_evidence"]})
    critical_failed = len([row for row in rows if row.get("status") == "failed" and row.get("severity") == "critical"])
    manual_required = len([row for row in rows if row.get("status") == "manual_required"])
    overall = "blocked" if critical_failed else "manual_required" if manual_required else "ready"
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_readiness_matrix", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "rows": rows, "summary": {"status": overall, "critical_failed": critical_failed, "manual_required": manual_required, "acceptance_status": "passed" if acceptance_passed else "not_required" if not acceptance_required else "failed"}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _gap_plan_doc(train_id: str, handoff_id: str, source_hash: str, readiness: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for row in readiness.get("rows", []):
        if row.get("status") != "passed":
            actions.append({"check_id": row.get("check_id"), "action": "resolve_or_collect_evidence", "status": "manual_required"})
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_gap_plan", "handoff_id": handoff_id, "train_id": train_id, "source_hash": source_hash, "items": actions, "summary": {"open_count": len(actions)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _public_external_manifest(train_id: str, handoff_id: str, inputs: dict[str, Any], train: dict[str, Any], change: dict[str, Any], lifecycle: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item_id, evidence_type, summary in (
        ("train-current", "release_train_archive", train),
        ("change-control-current", "release_train_change_control", change),
        ("lifecycle-current", "release_train_lifecycle_audit", lifecycle),
    ):
        rows.append({"item_id": item_id, "evidence_type": evidence_type, "component_id": train_id, "status": summary.get("status"), "zip_sha256": summary.get("zip_sha256"), "zip_size_bytes": summary.get("zip_size_bytes"), "manifest_hash": summary.get("manifest_hash"), "verification_report_hash": summary.get("verification_report_hash")})
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_external_evidence_manifest", "handoff_id": handoff_id, "train_id": train_id, "items": rows}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _file_index(train_id: str, handoff_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_file_index", "handoff_id": handoff_id, "train_id": train_id, "files": sorted(files, key=lambda row: row.get("path", ""))}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(train_id: str, handoff_id: str, docs: dict[str, Any], files: list[dict[str, Any]], file_index: dict[str, Any]) -> dict[str, Any]:
    source = {
        "file_index_hash": file_index.get("integrity_hash"),
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "response_summary_hash": docs["response_summary"].get("integrity_hash"),
        "accepted_evidence_summary_hash": docs["accepted_summary"].get("integrity_hash"),
        "handoff_signoff_hash": docs.get("signoff", {}).get("integrity_hash"),
        "handoff_signoff_binding_hash": docs.get("signoff_binding", {}).get("integrity_hash"),
    }
    doc = {"schema_version": 1, "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE, "handoff_id": handoff_id, "train_id": train_id, "source_hash": docs["report"].get("source_hash"), "source": source, "summary": docs["report"].get("summary", {}), "files": sorted(files, key=lambda row: row.get("path", ""))}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _signoff_binding_summary(train_id: str, handoff_id: str, signoff: dict[str, Any], event: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    source = docs["report"].get("source", {})
    doc = {
        "schema_version": 1,
        "package_type": "musicforge_release_train_handoff_signoff_binding_summary",
        "handoff_id": handoff_id,
        "train_id": train_id,
        "signed_by": signoff.get("signed_by"),
        "role": signoff.get("role"),
        "reason": signoff.get("reason"),
        "signed_at": signoff.get("signed_at"),
        "signoff_hash": signoff.get("integrity_hash"),
        "latest_history_event_hash": event.get("event_hash"),
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "current_train_archive_sha256": source.get("current_train_zip_sha256"),
        "lifecycle_audit_zip_sha256": source.get("lifecycle_zip_sha256"),
        "accepted_evidence_summary_hash": docs["accepted_summary"].get("integrity_hash"),
        "accepted_evidence_hashes": [row.get("accepted_evidence_hash") for row in docs["accepted_summary"].get("items", [])],
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _response_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("response_json_base64"):
        raw = base64.b64decode(str(payload["response_json_base64"]))
        return json.loads(raw.decode("utf-8"))
    if isinstance(payload.get("response"), dict):
        return dict(payload["response"])
    return dict(payload)


def _response_public_summary(response: dict[str, Any]) -> dict[str, Any]:
    reviewer = response.get("reviewer") if isinstance(response.get("reviewer"), dict) else {}
    return sanitize_metadata({"reviewer_id": reviewer.get("reviewer_id"), "reviewer_name": reviewer.get("name"), "organization": reviewer.get("organization"), "reviewer_role": reviewer.get("role"), "decision": response.get("decision"), "reviewed_at": response.get("reviewed_at")})


def _response_binding_summary(response: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_response_binding_summary", "response_id": response.get("response_id"), "handoff_id": response.get("handoff_id"), "train_id": response.get("train_id"), "raw_response_sha256": response.get("integrity_hash"), "payload_hash": response.get("payload_hash"), "verification_report_hash": verification.get("integrity_hash"), "handoff_zip_sha256": response.get("handoff_zip_sha256"), "handoff_manifest_hash": response.get("handoff_manifest_hash"), "handoff_source_hash": response.get("handoff_source_hash")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _accepted_evidence_row_from_dir(response_dir: Path) -> dict[str, Any]:
    accepted = _read_optional_json(response_dir / "accepted-evidence.json")
    response = _read_optional_json(response_dir / "response.json")
    verification = _read_optional_json(response_dir / "response-verification-report.json")
    binding = _read_optional_json(response_dir / "response-binding-summary.json")
    response_public = _response_public_summary(response) if response else {}
    expected_binding = _response_binding_summary(response, verification) if response and verification else {}
    evidence_binding = accepted.get("response_binding") if isinstance(accepted.get("response_binding"), dict) else {}
    failures: list[str] = []

    def require(check_id: str, passed: bool) -> None:
        if not passed:
            failures.append(check_id)

    require("accepted_evidence_integrity", _integrity_ok(accepted) and accepted.get("package_type") == "musicforge_release_train_handoff_accepted_evidence")
    require("accepted_evidence_response_integrity", _integrity_ok(response) and response.get("package_type") == "musicforge_release_train_handoff_response")
    require("accepted_evidence_response_verification_integrity", _integrity_ok(verification) and verification.get("package_type") == "musicforge_release_train_handoff_response_verification")
    require("accepted_evidence_response_verification_passed", verification.get("status") == "passed")
    require("accepted_evidence_response_decision", response.get("decision") == "accepted")
    require("accepted_evidence_binding_integrity", _integrity_ok(binding) and binding.get("package_type") == "musicforge_release_train_handoff_response_binding_summary")
    require("accepted_evidence_binding_matches_response", bool(expected_binding) and binding == expected_binding)
    require("accepted_evidence_public_summary_matches_response", accepted.get("public_summary") == response_public)
    require("accepted_evidence_embedded_binding_matches_sidecar", evidence_binding == binding)
    require("accepted_evidence_response_id", accepted.get("response_id") == response.get("response_id") == verification.get("response_id") == binding.get("response_id"))
    require("accepted_evidence_handoff_id", accepted.get("handoff_id") == response.get("handoff_id") == binding.get("handoff_id"))
    require("accepted_evidence_train_id", accepted.get("train_id") == response.get("train_id") == binding.get("train_id"))

    return {
        "response_id": accepted.get("response_id") or response.get("response_id") or response_dir.name,
        "accepted_evidence_hash": accepted.get("integrity_hash"),
        "response_hash": response.get("integrity_hash"),
        "response_verification_report_hash": verification.get("integrity_hash"),
        "response_binding_hash": binding.get("integrity_hash"),
        "reviewer_role": response_public.get("reviewer_role"),
        "organization": response_public.get("organization"),
        "decision": response_public.get("decision"),
        "reviewed_at": response_public.get("reviewed_at"),
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def _assert_signed_docs_current(docs: dict[str, Any]) -> None:
    signoff = docs.get("signoff") or {}
    if signoff.get("handoff_report_hash") != docs["report"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff report hash does not match signoff.")
    if signoff.get("readiness_matrix_hash") != docs["readiness"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff readiness hash does not match signoff.")
    if signoff.get("evidence_inventory_hash") != docs["inventory"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff inventory hash does not match signoff.")
    if signoff.get("accepted_evidence_summary_hash") != docs["accepted_summary"].get("integrity_hash"):
        raise UnifiedCommandCenterReleaseTrainHandoffStateError("Signed handoff accepted evidence hash does not match signoff.")


def _latest_signoff_event(history: list[dict[str, Any]]) -> dict[str, Any]:
    events = [row for row in history if row.get("event_type") == "release_train_handoff_signoff_created"]
    return events[-1] if events else {}


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(message), **extra}


def _read_optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _recipient_guide(docs: dict[str, Any]) -> str:
    return "# MusicForge Release Train Final Handoff\n\nReview the handoff report, readiness matrix, and evidence inventory. Use the verifier with external Train, Change Control, and Lifecycle evidence for current validation.\n"


def _history_text(history: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history)


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _zip_manifest_hash(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    return str(manifest.get("integrity_hash") or "")


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": "blocking", "message": message, "details": details or {}}


def _safe_id(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())[:120].strip("-")
    return cleaned or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]
