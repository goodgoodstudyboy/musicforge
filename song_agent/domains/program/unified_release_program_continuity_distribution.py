from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import shutil
from pathlib import Path
from typing import Any

from song_agent.platform.lifecycle import ArchiveBuilder
from song_agent.platform.persistence import WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade
from song_agent.platform.time import now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata, sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity import UnifiedReleaseProgramContinuityStore
from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import (
    PACKAGE_COMPONENTS,
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_RECEIPT_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
    verify_unified_release_program_continuity_distribution_package,
    write_unified_release_program_continuity_distribution_verification_report,
)
from song_agent.domains.program.unified_release_program_continuity_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_package,
)
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.unified_release_program_vault_operations_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_operations_package,
)
from song_agent.domains.program.unified_release_program_vault_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_package,
)


CONTINUITY_DISTRIBUTION_BLOCKED_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "raw_provider_response",
    "secret",
    "source_path",
    "token",
}


class UnifiedReleaseProgramContinuityDistributionError(ValueError):
    pass


class UnifiedReleaseProgramContinuityDistributionNotFoundError(UnifiedReleaseProgramContinuityDistributionError):
    pass


class UnifiedReleaseProgramContinuityDistributionStateError(UnifiedReleaseProgramContinuityDistributionError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramContinuityDistributionStateError)


class UnifiedReleaseProgramContinuityDistributionStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.continuity_store = UnifiedReleaseProgramContinuityStore(self.program_store)
        self.vault_operations_store = UnifiedReleaseProgramVaultOperationsStore(self.program_store)
        self.vault_store = UnifiedReleaseProgramVaultStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

    def distribution_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "continuity-distribution"

    def package_index_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "package-index.json"

    def verification_index_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "verification-index.json"

    def source_binding_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "source-binding-summary.json"

    def custody_checklist_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "custody-checklist.json"

    def redaction_report_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "redaction-report.json"

    def export_dir(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "continuity-distribution-kit"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def kit_zip_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "unified-release-program-continuity-distribution-kit.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "unified-release-program-continuity-distribution-verification-report.json"

    def receipt_template_path(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "receiver-receipt-template.json"

    def receiver_receipts_dir(self, program_id: str) -> Path:
        return self.distribution_dir(program_id) / "receiver-receipts"

    def receiver_receipt_path(self, program_id: str, receipt_id: str) -> Path:
        return self.receiver_receipts_dir(program_id) / f"{_safe_id(receipt_id)}.json"

    def get_kit(self, program_id: str) -> dict[str, Any]:
        return {
            "package_index": _read_optional_json(self.package_index_path(program_id)),
            "verification_index": _read_optional_json(self.verification_index_path(program_id)),
            "source_binding": _read_optional_json(self.source_binding_path(program_id)),
            "custody_checklist": _read_optional_json(self.custody_checklist_path(program_id)),
            "redaction_report": _read_optional_json(self.redaction_report_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
            "zip_path": str(self.kit_zip_path(program_id)),
        }

    def prepare_kit(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            context = self._current_context(program_id, payload, require_passed=True)
            self.distribution_dir(program_id).mkdir(parents=True, exist_ok=True)
            docs = self._build_documents(program_id, context)
            write_json(self.package_index_path(program_id), docs["package_index"])
            write_json(self.verification_index_path(program_id), docs["verification_index"])
            write_json(self.source_binding_path(program_id), docs["source_binding"])
            write_json(self.custody_checklist_path(program_id), docs["custody_checklist"])
            write_json(self.redaction_report_path(program_id), docs["redaction_report"])
            write_json(self.receipt_template_path(program_id), docs["receipt_template"])
            return docs["source_binding"]

    def export_kit(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            context = self._current_context(program_id, payload, require_passed=True)
            docs = self._build_documents(program_id, context)
            export_dir = self.export_dir(program_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_doc(rel: str, value: dict[str, Any] | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            def copy_file(source: Path, rel: str) -> None:
                if not source.exists() or not source.is_file():
                    raise UnifiedReleaseProgramContinuityDistributionStateError(f"Required continuity distribution evidence is missing: {source}")
                dest = export_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                files.append(_file_record(dest, rel))

            write_doc("README.txt", "MusicForge Unified Release Program Continuity Distribution Kit\n")
            write_doc("package-index.json", docs["package_index"])
            write_doc("verification-index.json", docs["verification_index"])
            write_doc("source-binding-summary.json", docs["source_binding"])
            write_doc("restore-command-guide.md", _restore_command_guide(program_id))
            write_doc("receiver-guide.md", _receiver_guide(program_id))
            write_doc("custody-checklist.json", docs["custody_checklist"])
            write_doc("redaction-report.json", docs["redaction_report"])
            write_doc("receipts/receiver-receipt-template.json", docs["receipt_template"])
            copy_file(context["continuity_zip_path"], "packages/continuity-archive.zip")
            copy_file(context["vault_operations_zip_path"], "packages/vault-operations-archive.zip")
            copy_file(context["vault_zip_path"], "packages/evidence-vault.zip")
            copy_file(context["continuity_verification_path"], "verification/continuity-verification-report.json")
            copy_file(context["vault_operations_verification_path"], "verification/vault-operations-verification-report.json")
            copy_file(context["vault_verification_path"], "verification/vault-verification-report.json")
            copy_file(context["continuity_signoff_binding_path"], "bindings/continuity-signoff-binding-summary.json")
            copy_file(context["vault_operations_signoff_binding_path"], "bindings/vault-operations-signoff-binding-summary.json")
            copy_file(context["vault_anchor_path"], "bindings/vault-anchor.json")
            manifest = _manifest_document(program_id, docs, files)
            write_json(self.manifest_path(program_id), manifest)
            self.prepare_kit(program_id, payload)
            return manifest

    def build_kit_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self.export_kit(program_id, payload)
            export_dir = self.export_dir(program_id)
            zip_path = self.kit_zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            entries = sorted(path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest.get("integrity_hash")}

    def verify_kit(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        report = verify_unified_release_program_continuity_distribution_package(
            payload.get("kit_zip") or payload.get("zip_path") or self.kit_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_receiver_receipt=bool(payload.get("require_receiver_receipt", False)),
            receiver_receipt_path=payload.get("receiver_receipt") or payload.get("receiver_receipt_path"),
            kit_verification_report_path=payload.get("verification_report") or payload.get("verification_report_path") or self.verification_report_path(program_id),
        )
        if not bool(payload.get("require_receiver_receipt", False)):
            write_unified_release_program_continuity_distribution_verification_report(report, self.verification_report_path(program_id))
        return report

    def create_receiver_receipt_template(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _sanitize_payload(payload or {})
        with self.lock:
            if not self.kit_zip_path(program_id).exists():
                self.build_kit_zip(program_id)
            verification = _read_optional_json(self.verification_report_path(program_id))
            if not verification:
                verification = self.verify_kit(program_id)
            manifest = _read_optional_json(self.manifest_path(program_id))
            template = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_continuity_distribution_receiver_receipt_template",
                    "program_id": program_id,
                    "created_at": now_iso(),
                    "kit_sha256": _sha256_path(self.kit_zip_path(program_id)),
                    "kit_manifest_hash": manifest.get("integrity_hash"),
                    "verification_report_hash": verification.get("integrity_hash"),
                    "fields": ["receiver_name", "organization", "decision", "verification_status", "notes"],
                    "decision_values": ["accepted", "needs_changes", "rejected"],
                }
            )
            write_json(self.receipt_template_path(program_id), template)
            return template

    def import_receiver_receipt(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        required = ("kit_sha256", "kit_manifest_hash", "verification_report_hash", "decision")
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise UnifiedReleaseProgramContinuityDistributionStateError("Receiver receipt is missing required binding fields: " + ", ".join(missing))
        receipt_id = _safe_id(str(payload.get("receipt_id") or self._next_receipt_id(program_id)))
        receipt = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_RECEIPT_PACKAGE_TYPE,
                "program_id": program_id,
                "receipt_id": receipt_id,
                "received_at": _bounded(payload.get("received_at") or now_iso(), 80),
                "receiver_name": _bounded(payload.get("receiver_name") or "receiver", 120),
                "organization": _bounded(payload.get("organization") or "receiver", 120),
                "decision": _bounded(payload.get("decision"), 40),
                "verification_status": _bounded(payload.get("verification_status") or "passed", 40),
                "kit_sha256": _bounded(payload.get("kit_sha256"), 128),
                "kit_manifest_hash": _bounded(payload.get("kit_manifest_hash"), 128),
                "verification_report_hash": _bounded(payload.get("verification_report_hash"), 128),
                "notes": _bounded(payload.get("notes") or "", 2000),
            }
        )
        self.receiver_receipts_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.receiver_receipt_path(program_id, receipt_id), receipt)
        return receipt

    def verify_receiver_receipt(self, program_id: str, receipt_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        _sanitize_payload(payload or {})
        receipt_path = self.receiver_receipt_path(program_id, receipt_id)
        report = verify_unified_release_program_continuity_distribution_package(
            self.kit_zip_path(program_id),
            strict=True,
            deep=True,
            require_receiver_receipt=True,
            receiver_receipt_path=receipt_path,
            kit_verification_report_path=self.verification_report_path(program_id),
        )
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        kit_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        receiver_receipt_path: Path | str | None = None,
        require_receiver_receipt: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(kit_zip_path) if kit_zip_path else self.kit_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Continuity Distribution Kit ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Continuity Distribution Kit verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_continuity_distribution_package(zip_path, strict=True, deep=True, require_receiver_receipt=require_receiver_receipt, receiver_receipt_path=receiver_receipt_path, kit_verification_report_path=report_path)
        except Exception as exc:
            return _gate_failed(f"Continuity Distribution Kit gate could not verify evidence: {sanitize_sensitive_text(str(exc))}")
        if external.get("package_type") != "musicforge_unified_release_program_continuity_distribution_verification":
            return _gate_failed("Continuity Distribution Kit verification report package type is invalid.")
        if not _integrity_ok(external):
            return _gate_failed("Continuity Distribution Kit verification report integrity failed.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            return _gate_failed("Continuity Distribution Kit verifier failed.", summary=runtime.get("summary", {}), blockers=runtime.get("blockers", []))
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            return _gate_failed("Continuity Distribution Kit verification report does not match current ZIP.")
        return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {}), "verification_report_hash": external.get("integrity_hash")}

    def _next_receipt_id(self, program_id: str) -> str:
        existing = list(self.receiver_receipts_dir(program_id).glob("receipt-*.json")) if self.receiver_receipts_dir(program_id).exists() else []
        return f"receipt-{len(existing) + 1:06d}"

    def _current_context(self, program_id: str, payload: ImplementationDocument, *, require_passed: bool) -> ImplementationDocument:
        paths = {
            "continuity_zip_path": Path(payload.get("continuity_archive") or payload.get("continuity_zip") or self.continuity_store.archive_zip_path(program_id)),
            "continuity_verification_path": Path(payload.get("continuity_verification_report") or self.continuity_store.verification_report_path(program_id)),
            "continuity_signoff_binding_path": Path(payload.get("continuity_signoff_binding") or self.continuity_store.signoff_binding_path(program_id)),
            "vault_operations_zip_path": Path(payload.get("vault_operations_archive") or payload.get("vault_operations_zip") or self.vault_operations_store.archive_zip_path(program_id)),
            "vault_operations_verification_path": Path(payload.get("vault_operations_verification_report") or self.vault_operations_store.verification_report_path(program_id)),
            "vault_operations_signoff_binding_path": Path(payload.get("vault_operations_signoff_binding") or self.vault_operations_store.signoff_binding_path(program_id)),
            "vault_zip_path": Path(payload.get("evidence_vault") or payload.get("vault_zip") or self.vault_store.zip_path(program_id)),
            "vault_verification_path": Path(payload.get("vault_verification_report") or self.vault_store.verification_report_path(program_id)),
            "vault_anchor_path": Path(payload.get("vault_anchor") or self.vault_store.anchor_path(program_id)),
        }
        for label, path in paths.items():
            if not path.exists() or not path.is_file():
                raise UnifiedReleaseProgramContinuityDistributionStateError(f"Required continuity distribution evidence is missing: {label}={path}")
        runtime = {
            "continuity": verify_unified_release_program_continuity_package(paths["continuity_zip_path"], strict=True, deep_restore=True, require_signed=True, require_current_vault_operations=True, signoff_binding_path=paths["continuity_signoff_binding_path"], vault_operations_archive_path=paths["vault_operations_zip_path"], vault_operations_verification_report_path=paths["vault_operations_verification_path"], vault_operations_signoff_binding_path=paths["vault_operations_signoff_binding_path"]),
            "vault_operations": verify_unified_release_program_vault_operations_package(paths["vault_operations_zip_path"], strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=paths["vault_operations_signoff_binding_path"]),
            "evidence_vault": verify_unified_release_program_vault_package(paths["vault_zip_path"], strict=True, deep=True, require_anchor=True, vault_anchor_path=paths["vault_anchor_path"]),
        }
        external = {
            "continuity": read_json(paths["continuity_verification_path"]),
            "vault_operations": read_json(paths["vault_operations_verification_path"]),
            "evidence_vault": read_json(paths["vault_verification_path"]),
        }
        bindings = {
            "continuity": read_json(paths["continuity_signoff_binding_path"]),
            "vault_operations": read_json(paths["vault_operations_signoff_binding_path"]),
            "evidence_vault": read_json(paths["vault_anchor_path"]),
        }
        blockers: list[str] = []
        expected_types = {
            "continuity": UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
            "vault_operations": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
            "evidence_vault": UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
        }
        for key in ("continuity", "vault_operations", "evidence_vault"):
            if runtime[key].get("status") != "passed":
                blockers.append(f"{key}_runtime_failed")
            if external[key].get("package_type") != expected_types[key]:
                blockers.append(f"{key}_external_package_type")
            if not _integrity_ok(external[key]):
                blockers.append(f"{key}_external_integrity")
            if external[key].get("status") != "passed":
                blockers.append(f"{key}_external_failed")
            if external[key].get("zip_sha256") != runtime[key].get("zip_sha256"):
                blockers.append(f"{key}_zip_sha256")
            if external[key].get("manifest_hash") != runtime[key].get("manifest_hash"):
                blockers.append(f"{key}_manifest_hash")
            if not _integrity_ok(bindings[key]):
                blockers.append(f"{key}_binding_integrity")
        if require_passed and blockers:
            raise UnifiedReleaseProgramContinuityDistributionStateError("Continuity Distribution source evidence is not current: " + ", ".join(sorted(set(blockers))))
        return {**paths, "runtime": runtime, "external": external, "bindings": bindings, "blockers": sorted(set(blockers))}

    def _build_documents(self, program_id: str, context: ImplementationDocument) -> ImplementationDocument:
        now = now_iso()
        package_rows = []
        verification_rows = []
        source: dict[str, Any] = {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_continuity_distribution_source_binding",
            "program_id": program_id,
            "status": "passed" if not context.get("blockers") else "failed",
            "created_at": now,
            "blockers": context.get("blockers", []),
        }
        for key, component in PACKAGE_COMPONENTS.items():
            package_path = context[f"{key}_zip_path"] if key != "evidence_vault" else context["vault_zip_path"]
            external = context["external"][key]
            binding = context["bindings"][key]
            package_rows.append(
                {
                    "component_type": key,
                    "program_id": program_id,
                    "path": component["path"],
                    "sha256": _sha256_path(package_path),
                    "size_bytes": package_path.stat().st_size,
                    "manifest_hash": context["runtime"][key].get("manifest_hash"),
                    "verification_report_hash": external.get("integrity_hash"),
                    "binding_hash": binding.get("integrity_hash"),
                }
            )
            verification_rows.append(
                {
                    "component_type": key,
                    "program_id": program_id,
                    "path": component["verification_path"],
                    "status": external.get("status"),
                    "package_type": external.get("package_type"),
                    "verification_report_hash": external.get("integrity_hash"),
                    "zip_sha256": external.get("zip_sha256"),
                    "manifest_hash": external.get("manifest_hash"),
                }
            )
            source[f"{key}_zip_sha256"] = _sha256_path(package_path)
            source[f"{key}_manifest_hash"] = context["runtime"][key].get("manifest_hash")
            source[f"{key}_verification_report_hash"] = external.get("integrity_hash")
            source[f"{key}_binding_hash" if key != "evidence_vault" else "evidence_vault_anchor_hash"] = binding.get("integrity_hash")
        package_index = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_distribution_package_index",
                "program_id": program_id,
                "created_at": now,
                "packages": sorted(package_rows, key=lambda row: str(row.get("component_type") or "")),
            }
        )
        verification_index = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_distribution_verification_index",
                "program_id": program_id,
                "created_at": now,
                "verifications": sorted(verification_rows, key=lambda row: str(row.get("component_type") or "")),
            }
        )
        source["package_index_hash"] = package_index.get("integrity_hash")
        source["verification_index_hash"] = verification_index.get("integrity_hash")
        source_binding = _with_integrity(source)
        custody_checklist = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_distribution_custody_checklist",
                "program_id": program_id,
                "created_at": now,
                "status": "ready",
                "items": [
                    {"item_id": "verify_kit", "status": "manual_required"},
                    {"item_id": "store_kit_and_anchor", "status": "manual_required"},
                    {"item_id": "collect_receiver_receipt", "status": "manual_required"},
                ],
            }
        )
        redaction_report = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_distribution_redaction_report", "program_id": program_id, "status": "passed", "created_at": now, "offenders": []})
        receipt_template = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_distribution_receiver_receipt_template",
                "program_id": program_id,
                "created_at": now,
                "kit_sha256": _sha256_path(self.kit_zip_path(program_id)),
                "kit_manifest_hash": _read_optional_json(self.manifest_path(program_id)).get("integrity_hash"),
                "verification_report_hash": _read_optional_json(self.verification_report_path(program_id)).get("integrity_hash"),
                "decision_values": ["accepted", "needs_changes", "rejected"],
            }
        )
        return {"package_index": package_index, "verification_index": verification_index, "source_binding": source_binding, "custody_checklist": custody_checklist, "redaction_report": redaction_report, "receipt_template": receipt_template}


def _manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source": {
                "package_index_hash": docs["package_index"].get("integrity_hash"),
                "verification_index_hash": docs["verification_index"].get("integrity_hash"),
                "source_binding_hash": docs["source_binding"].get("integrity_hash"),
            },
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=CONTINUITY_DISTRIBUTION_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _restore_command_guide(program_id: str) -> str:
    return f"# MusicForge Continuity Distribution Restore\n\nProgram: {sanitize_sensitive_text(program_id)}\n\nRun the kit verifier with --deep before using any nested evidence.\n"


def _receiver_guide(program_id: str) -> str:
    return f"# MusicForge Continuity Distribution Receiver Guide\n\nProgram: {sanitize_sensitive_text(program_id)}\n\nVerify the kit, then fill the receiver receipt only with public-safe information.\n"


def _sanitize_payload(payload: ImplementationDocument) -> ImplementationDocument:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramContinuityDistributionStateError(f"{forbidden} is not allowed for Continuity Distribution Kit.")
    return payload


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    doc = sanitize_metadata(doc, blocked_keys=CONTINUITY_DISTRIBUTION_BLOCKED_METADATA_KEYS)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _safe_id(value: str) -> str:
    import re

    value = sanitize_sensitive_text(str(value or "")).strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value[:120] or "item"


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
