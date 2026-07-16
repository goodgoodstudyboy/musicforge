from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import shutil
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder, HistoryChain
from song_agent.platform.persistence import WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade
from song_agent.platform.time import now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata, sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_handoff import UnifiedReleaseProgramHandoffStore
from song_agent.domains.program.unified_release_program_operations import UnifiedReleaseProgramOperationsStore
from song_agent.domains.program.unified_release_program_vault_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
    verify_unified_release_program_vault_package,
    write_unified_release_program_vault_verification_report,
)


VAULT_BLOCKED_METADATA_KEYS = {
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


class UnifiedReleaseProgramVaultError(ValueError):
    pass


class UnifiedReleaseProgramVaultNotFoundError(UnifiedReleaseProgramVaultError):
    pass


class UnifiedReleaseProgramVaultStateError(UnifiedReleaseProgramVaultError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramVaultStateError)


class UnifiedReleaseProgramVaultStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore()
        self.operations_store = UnifiedReleaseProgramOperationsStore(self.program_store)
        self.handoff_store = UnifiedReleaseProgramHandoffStore(self.program_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

    def vault_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "evidence-vault"

    def report_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "vault-report.json"

    def source_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "source-summary.json"

    def package_index_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "package-index.json"

    def verification_index_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "verification-index.json"

    def proof_index_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "proof-index.json"

    def chain_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "chain-of-custody.json"

    def public_summary_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "public-summary.json"

    def replay_plan_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "replay-plan.json"

    def export_dir(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "export"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def zip_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "unified-release-program-evidence-vault.zip"

    def anchor_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "vault-anchor.json"

    def verification_report_path(self, program_id: str) -> Path:
        return self.vault_dir(program_id) / "unified-release-program-evidence-vault-verification-report.json"

    def get_vault(self, program_id: str) -> dict[str, Any]:
        return {
            "report": _read_optional_json(self.report_path(program_id)),
            "source": _read_optional_json(self.source_path(program_id)),
            "package_index": _read_optional_json(self.package_index_path(program_id)),
            "verification_index": _read_optional_json(self.verification_index_path(program_id)),
            "proof_index": _read_optional_json(self.proof_index_path(program_id)),
            "chain_of_custody": _read_optional_json(self.chain_path(program_id)),
            "anchor": _read_optional_json(self.anchor_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def refresh_vault(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            docs = self._build_documents(program_id, payload)
            self.vault_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.report_path(program_id), docs["report"])
            write_json(self.source_path(program_id), docs["source"])
            write_json(self.package_index_path(program_id), docs["package_index"])
            write_json(self.verification_index_path(program_id), docs["verification_index"])
            write_json(self.proof_index_path(program_id), docs["proof_index"])
            write_json(self.chain_path(program_id), docs["chain"])
            write_json(self.public_summary_path(program_id), docs["public_summary"])
            write_json(self.replay_plan_path(program_id), docs["replay_plan"])
            return docs["report"]

    def export_vault(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            docs = self._ensure_docs(program_id, payload)
            if docs["report"].get("status") != "passed":
                raise UnifiedReleaseProgramVaultStateError("Unified Release Program Vault report must be passed before export.")
            export_dir = self.export_dir(program_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, value: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(value, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            def copy_entry(source: Path, rel: str) -> None:
                if not source.exists() or not source.is_file():
                    raise UnifiedReleaseProgramVaultStateError(f"Required Vault evidence is missing: {source}")
                dest = export_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                files.append(_file_record(dest, rel))

            write_entry("vault-report.json", docs["report"])
            write_entry("source-summary.json", docs["source"])
            write_entry("package-index.json", docs["package_index"])
            write_entry("verification-index.json", docs["verification_index"])
            write_entry("proof-index.json", docs["proof_index"])
            write_entry("chain-of-custody.json", docs["chain"])
            write_entry("replay-plan.json", docs["replay_plan"])
            write_entry("auditor-guide.md", _auditor_guide(docs))
            write_entry("public-summary.json", docs["public_summary"])
            write_entry("README.txt", "MusicForge Unified Release Program Evidence Vault\n")
            for row in self._package_rows(program_id, payload):
                copy_entry(Path(row["source_path"]), str(row["path"]))
            for row in self._verification_rows(program_id, payload):
                write_entry(str(row["path"]), _verification_export_doc(Path(row["source_path"])))
            for row in self._proof_rows(program_id, payload):
                proof_doc = _proof_export_doc(Path(row["source_path"]), str(row.get("proof_type") or ""))
                if isinstance(proof_doc, dict):
                    write_entry(str(row["path"]), proof_doc)
                else:
                    copy_entry(Path(row["source_path"]), str(row["path"]))
            manifest = _manifest_document(program_id, docs, files)
            write_json(self.manifest_path(program_id), manifest)
            return manifest

    def build_vault_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        with self.lock:
            self.export_vault(program_id, payload)
            export_dir = self.export_dir(program_id)
            zip_path = self.zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            docs = self._read_docs(program_id)
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            zip_path.unlink(missing_ok=True)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            anchor = _anchor_document(program_id, zip_path, manifest, docs)
            write_json(self.anchor_path(program_id), anchor)
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "anchor_path": str(self.anchor_path(program_id)), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_vault_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _sanitize_payload(payload or {})
        report = verify_unified_release_program_vault_package(
            payload.get("vault_zip") or payload.get("zip_path") or self.zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_anchor=bool(payload.get("require_anchor", True)),
            vault_anchor_path=payload.get("vault_anchor") or payload.get("anchor") or self.anchor_path(program_id),
            require_current_program=bool(payload.get("require_current_program", False)),
            require_current_operations=bool(payload.get("require_current_operations", False)),
            require_current_handoff=bool(payload.get("require_current_handoff", False)),
            require_accepted_evidence=bool(payload.get("require_accepted_evidence", True)),
        )
        write_unified_release_program_vault_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        vault_zip_path: Path | str | None = None,
        vault_verification_report_path: Path | str | None = None,
        vault_anchor_path: Path | str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(vault_zip_path) if vault_zip_path else self.zip_path(program_id)
        report_path = Path(vault_verification_report_path) if vault_verification_report_path else self.verification_report_path(program_id)
        anchor_path = Path(vault_anchor_path) if vault_anchor_path else self.anchor_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Evidence Vault ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Evidence Vault verification report is missing.")
        if not anchor_path.exists():
            return _gate_failed("Unified Release Program Evidence Vault anchor is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_vault_package(
                zip_path,
                strict=True,
                deep=True,
                require_anchor=True,
                vault_anchor_path=anchor_path,
                require_current_program=bool(payload.get("require_current_program", False)),
                require_current_operations=bool(payload.get("require_current_operations", False)),
                require_current_handoff=bool(payload.get("require_current_handoff", False)),
                require_accepted_evidence=bool(payload.get("require_accepted_evidence", True)),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program Evidence Vault verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program Evidence Vault verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program Evidence Vault verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program Evidence Vault gate passed.", "summary": runtime.get("summary", {}), "vault_zip_sha256": runtime.get("zip_sha256"), "verification_hash": external.get("integrity_hash")}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _ensure_docs(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        if not self.report_path(program_id).exists():
            self.refresh_vault(program_id, payload)
        return self._read_docs(program_id)

    def _read_docs(self, program_id: str) -> ImplementationDocument:
        return {
            "report": read_json(self.report_path(program_id)),
            "source": read_json(self.source_path(program_id)),
            "package_index": read_json(self.package_index_path(program_id)),
            "verification_index": read_json(self.verification_index_path(program_id)),
            "proof_index": read_json(self.proof_index_path(program_id)),
            "chain": read_json(self.chain_path(program_id)),
            "public_summary": read_json(self.public_summary_path(program_id)),
            "replay_plan": read_json(self.replay_plan_path(program_id)),
        }

    def _build_documents(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        package_rows = self._package_rows(program_id, payload)
        verification_rows = self._verification_rows(program_id, payload)
        proof_rows = self._proof_rows(program_id, payload)
        now = now_iso()
        statuses = [row.get("status") for row in verification_rows]
        missing = [row for row in package_rows + verification_rows + proof_rows if not Path(str(row.get("source_path") or "")).exists()]
        failed_status = [row for row in verification_rows if row.get("status") != "passed"]
        source = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_evidence_vault_source",
                "program_id": program_id,
                "created_at": now,
                "package_fingerprints": [_public_row(row) for row in package_rows],
                "verification_fingerprints": [_public_row(row) for row in verification_rows],
                "proof_fingerprints": [_public_row(row) for row in proof_rows],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        package_index = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_package_index", "program_id": program_id, "source_hash": source["source_hash"], "packages": [_public_row(row) for row in package_rows], "summary": {"package_count": len(package_rows)}})
        verification_index = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_verification_index", "program_id": program_id, "source_hash": source["source_hash"], "verifications": [_public_row(row) for row in verification_rows], "summary": {"verification_count": len(verification_rows), "passed_count": sum(1 for row in verification_rows if row.get("status") == "passed")}})
        proof_index = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_proof_index", "program_id": program_id, "source_hash": source["source_hash"], "proofs": [_public_row(row) for row in proof_rows], "summary": {"proof_count": len(proof_rows)}})
        chain = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_chain_of_custody", "program_id": program_id, "source_hash": source["source_hash"], "events": _chain_events(program_id, package_rows, verification_rows, proof_rows), "summary": {"event_count": len(package_rows) + len(verification_rows) + len(proof_rows)}})
        status = "failed" if missing or failed_status or not all(status == "passed" for status in statuses) else "passed"
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_evidence_vault_report",
                "program_id": program_id,
                "vault_id": str(payload.get("vault_id") or "urpv-000001"),
                "created_at": now,
                "status": status,
                "source_hash": source["source_hash"],
                "summary": {
                    "package_count": len(package_rows),
                    "verification_count": len(verification_rows),
                    "proof_count": len(proof_rows),
                    "missing_evidence_count": len(missing),
                    "failed_verification_count": len(failed_status),
                },
                "blockers": [f"missing:{row.get('component_type')}:{row.get('component_id')}" for row in missing] + [f"failed:{row.get('component_type')}:{row.get('component_id')}" for row in failed_status],
                "tool": {"name": "MusicForge Unified Release Program Evidence Vault", "version": __version__},
            }
        )
        public_summary = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_public_summary", "program_id": program_id, "vault_id": report["vault_id"], "source_hash": source["source_hash"], "status": status, "summary": report["summary"]})
        replay_plan = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_replay_plan", "program_id": program_id, "vault_id": report["vault_id"], "source_hash": source["source_hash"], "steps": _replay_steps(package_rows, verification_rows, proof_rows)})
        return {"report": report, "source": source, "package_index": package_index, "verification_index": verification_index, "proof_index": proof_index, "chain": chain, "public_summary": public_summary, "replay_plan": replay_plan}

    def _package_rows(self, program_id: str, payload: ImplementationDocument) -> list[ImplementationDocument]:
        rows = [
            _package_row("program", program_id, self.program_store.zip_path(program_id), "packages/unified-release-program.zip"),
            _package_row("operations", program_id, self.operations_store.archive_zip_path(program_id), "packages/unified-release-program-operations.zip"),
            _package_row("handoff", program_id, self.handoff_store.archive_zip_path(program_id), "packages/unified-release-program-handoff.zip"),
        ]
        for item in self._accepted_evidence_items(program_id, payload):
            evidence_id = str(item["evidence_id"])
            rows.append(_package_row("accepted_evidence", evidence_id, Path(item["zip_path"]), f"packages/accepted-evidence/{evidence_id}.zip"))
        return rows

    def _verification_rows(self, program_id: str, payload: ImplementationDocument) -> list[ImplementationDocument]:
        rows = [
            _verification_row("program", program_id, self.program_store.verification_report_path(program_id), "proofs/program-verification-report.json"),
            _verification_row("operations", program_id, self.operations_store.archive_verification_report_path(program_id), "proofs/operations-verification-report.json"),
            _verification_row("handoff", program_id, self.handoff_store.archive_verification_report_path(program_id), "proofs/handoff-verification-report.json"),
        ]
        for item in self._accepted_evidence_items(program_id, payload):
            evidence_id = str(item["evidence_id"])
            rows.append(_verification_row("accepted_evidence", evidence_id, Path(item["verification_report_path"]), f"proofs/accepted-evidence/{evidence_id}-verification-report.json"))
        return rows

    def _proof_rows(self, program_id: str, payload: ImplementationDocument) -> list[ImplementationDocument]:
        rows = [
            _proof_row("program", program_id, "signoff_binding", self.program_store.signoff_binding_path(program_id), "proofs/program-signoff-binding-summary.json"),
            _proof_row("program", program_id, "external_evidence_manifest", self.program_store.external_manifest_path(program_id), "proofs/program-external-evidence-manifest.json"),
            _proof_row("handoff", program_id, "signoff_binding", self.handoff_store.signoff_binding_path(program_id), "proofs/handoff-signoff-binding-summary.json"),
            _proof_row("handoff", program_id, "external_evidence_manifest", self.handoff_store.runtime_external_manifest_path(program_id), "proofs/handoff-external-evidence-manifest.json"),
        ]
        for item in self._accepted_evidence_items(program_id, payload):
            evidence_id = str(item["evidence_id"])
            rows.append(_proof_row("accepted_evidence", evidence_id, "response_verification", Path(item["response_verification_path"]), f"proofs/accepted-evidence/{evidence_id}-response-verification-report.json"))
            rows.append(_proof_row("accepted_evidence", evidence_id, "response_binding", Path(item["response_binding_path"]), f"proofs/accepted-evidence/{evidence_id}-response-binding-summary.json"))
        return rows

    def _accepted_evidence_items(self, program_id: str, payload: ImplementationDocument) -> list[ImplementationDocument]:
        explicit = payload.get("accepted_evidence")
        if isinstance(explicit, list):
            rows = []
            for item in explicit:
                if isinstance(item, dict) and item.get("evidence_id"):
                    rows.append(item)
            return rows
        base = self.handoff_store.handoff_dir(program_id) / "accepted-evidence"
        if not base.exists():
            return []
        rows: list[dict[str, Any]] = []
        for report_path in sorted(base.glob("*/accepted-evidence-report.json")):
            report = read_json(report_path)
            evidence_id = str(report.get("evidence_id") or report_path.parent.name)
            response_id = str(report.get("response_id") or "")
            rows.append(
                {
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "zip_path": str(self.handoff_store.accepted_evidence_zip_path(program_id, evidence_id)),
                    "verification_report_path": str(self.handoff_store.accepted_evidence_verification_report_path(program_id, evidence_id)),
                    "response_verification_path": str(self.handoff_store.response_verification_path(program_id, response_id)),
                    "response_binding_path": str(self.handoff_store.response_binding_path(program_id, response_id)),
                }
            )
        return rows


def _package_row(component_type: str, component_id: str, source_path: Path, rel: str) -> ImplementationDocument:
    return {"component_type": component_type, "component_id": component_id, "path": rel, "source_path": str(source_path), "zip_sha256": _sha256_path(source_path), "zip_size_bytes": source_path.stat().st_size if source_path.exists() else 0, "exists": source_path.exists()}


def _verification_row(component_type: str, component_id: str, source_path: Path, rel: str) -> ImplementationDocument:
    doc = _verification_export_doc(source_path) if source_path.exists() else {}
    return {"component_type": component_type, "component_id": component_id, "path": rel, "source_path": str(source_path), "package_type": doc.get("package_type"), "status": doc.get("status") or "missing", "zip_sha256": doc.get("zip_sha256"), "manifest_hash": doc.get("manifest_hash"), "verification_report_hash": doc.get("integrity_hash"), "exists": source_path.exists()}


def _proof_row(component_type: str, component_id: str, proof_type: str, source_path: Path, rel: str) -> ImplementationDocument:
    proof_doc = _proof_export_doc(source_path, proof_type) if source_path.exists() else None
    data = _json_bytes(proof_doc) if isinstance(proof_doc, dict) else source_path.read_bytes() if source_path.exists() else b""
    integrity_hash = None
    package_type = None
    if isinstance(proof_doc, dict):
        doc = proof_doc
        integrity_hash = doc.get("integrity_hash")
        package_type = doc.get("package_type")
    return {"component_type": component_type, "component_id": component_id, "proof_type": proof_type, "path": rel, "source_path": str(source_path), "package_type": package_type, "sha256": _sha256_bytes(data) if data else None, "size_bytes": len(data), "integrity_hash": integrity_hash, "exists": source_path.exists()}


def _verification_export_doc(source_path: Path) -> ImplementationDocument:
    if not source_path.exists():
        return {}
    source = read_json(source_path)
    doc = sanitize_metadata(
        {
            "schema_version": source.get("schema_version") or UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": source.get("package_type"),
            "status": source.get("status"),
            "zip_sha256": source.get("zip_sha256") or (source.get("summary") or {}).get("zip_sha256"),
            "zip_size_bytes": source.get("zip_size_bytes") or (source.get("summary") or {}).get("zip_size_bytes"),
            "manifest_hash": source.get("manifest_hash") or (source.get("summary") or {}).get("manifest_hash"),
            "summary": _public_verification_summary(source.get("summary") if isinstance(source.get("summary"), dict) else {}),
            "blockers": list(source.get("blockers") or []),
            "warnings": list(source.get("warnings") or []),
        },
        blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _public_verification_summary(summary: ImplementationDocument) -> ImplementationDocument:
    allowed = {
        "program_id",
        "handoff_id",
        "evidence_id",
        "response_id",
        "status",
        "signed",
        "accepted_count",
        "quorum_status",
        "program_status",
        "continuous_review_status",
        "lifecycle_status",
        "zip_sha256",
        "zip_size_bytes",
        "manifest_hash",
    }
    public = {key: value for key, value in summary.items() if key in allowed or key.endswith("_hash") or key.endswith("_sha256") or key.endswith("_status")}
    return sanitize_metadata(public, blocked_keys=VAULT_BLOCKED_METADATA_KEYS)


def _proof_export_doc(source_path: Path, proof_type: str) -> ImplementationDocument | None:
    if not source_path.exists() or source_path.suffix.lower() != ".json":
        return None
    doc = read_json(source_path)
    if proof_type == "external_evidence_manifest":
        public_items = []
        for row in doc.get("items", []) if isinstance(doc.get("items"), list) else []:
            if not isinstance(row, dict):
                continue
            public_items.append(
                sanitize_metadata(
                    {
                        key: value
                        for key, value in row.items()
                        if key
                        in {
                            "item_id",
                            "train_id",
                            "handoff_id",
                            "evidence_id",
                            "evidence_type",
                            "component_id",
                            "program_id",
                            "role",
                            "organization",
                            "decision",
                        }
                        or key.endswith("_hash")
                        or key.endswith("_sha256")
                        or key.endswith("_size_bytes")
                        or key.endswith("_status")
                    },
                    blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
                )
            )
        public = {
            "schema_version": doc.get("schema_version") or UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": doc.get("package_type"),
            "program_id": doc.get("program_id"),
            "handoff_id": doc.get("handoff_id"),
            "created_at": doc.get("created_at"),
            "items": public_items,
            "summary": {"item_count": len(public_items)},
        }
        public["integrity_hash"] = _integrity_hash(public)
        return public
    return sanitize_metadata(doc, blocked_keys=VAULT_BLOCKED_METADATA_KEYS)


def _manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    source = {
        "vault_report_hash": docs["report"].get("integrity_hash"),
        "source_summary_hash": docs["source"].get("integrity_hash"),
        "package_index_hash": docs["package_index"].get("integrity_hash"),
        "verification_index_hash": docs["verification_index"].get("integrity_hash"),
        "proof_index_hash": docs["proof_index"].get("integrity_hash"),
        "chain_of_custody_hash": docs["chain"].get("integrity_hash"),
        "public_summary_hash": docs["public_summary"].get("integrity_hash"),
        "replay_plan_hash": docs["replay_plan"].get("integrity_hash"),
    }
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE,
            "program_id": program_id,
            "vault_id": docs["report"].get("vault_id"),
            "created_at": now_iso(),
            "source_hash": docs["source"].get("source_hash"),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        },
        blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _anchor_document(program_id: str, zip_path: Path, manifest: ImplementationDocument, docs: ImplementationDocument) -> ImplementationDocument:
    anchor = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE,
            "program_id": program_id,
            "vault_id": docs["report"].get("vault_id"),
            "created_at": now_iso(),
            "vault_zip_sha256": _sha256_path(zip_path),
            "vault_zip_size_bytes": zip_path.stat().st_size,
            "vault_manifest_hash": manifest.get("integrity_hash"),
            "vault_source_hash": docs["source"].get("source_hash"),
            "vault_report_hash": docs["report"].get("integrity_hash"),
            "package_index_hash": docs["package_index"].get("integrity_hash"),
            "verification_index_hash": docs["verification_index"].get("integrity_hash"),
            "proof_index_hash": docs["proof_index"].get("integrity_hash"),
            "chain_of_custody_hash": docs["chain"].get("integrity_hash"),
        },
        blocked_keys=VAULT_BLOCKED_METADATA_KEYS,
    )
    anchor["integrity_hash"] = _integrity_hash(anchor)
    return anchor


def _chain_events(program_id: str, packages: list[ImplementationDocument], verifications: list[ImplementationDocument], proofs: list[ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    previous = ""
    for index, row in enumerate(packages + verifications + proofs, start=1):
        event = HistoryChain.build_event(
            {"event_index": index, "program_id": program_id, "event_type": f"vault_{row.get('component_type')}_{'indexed'}", "component_type": row.get("component_type"), "component_id": row.get("component_id"), "path": row.get("path")},
            previous_event_hash=previous,
        )
        previous = event["event_hash"]
        rows.append(event)
    return rows


def _replay_steps(packages: list[ImplementationDocument], verifications: list[ImplementationDocument], proofs: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {"step": "verify_package_index", "package_count": len(packages)},
        {"step": "verify_verification_index", "verification_count": len(verifications)},
        {"step": "verify_proof_index", "proof_count": len(proofs)},
        {"step": "deep_verify_program_operations_handoff", "status": "required"},
        {"step": "deep_verify_accepted_evidence", "status": "required"},
    ]


def _auditor_guide(docs: ImplementationDocument) -> str:
    summary = docs["report"].get("summary", {})
    return "\n".join(
        [
            "# Unified Release Program Evidence Vault",
            "",
            f"Status: {docs['report'].get('status')}",
            f"Packages: {summary.get('package_count')}",
            f"Verifications: {summary.get('verification_count')}",
            "",
            "Run the verifier with --deep and the external vault-anchor.json before relying on this package.",
            "",
        ]
    )


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _public_row(row: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in row.items() if key not in {"source_path"}}


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    doc = sanitize_metadata(doc, blocked_keys=VAULT_BLOCKED_METADATA_KEYS)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: ImplementationDocument) -> bytes:
    import json
    import os

    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if os.linesep != "\n":
        text = text.replace("\n", os.linesep)
    return text.encode("utf-8")


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _sanitize_payload(payload: ImplementationDocument) -> ImplementationDocument:
    for forbidden in ("source_path", "local_path", "file_path"):
        if payload.get(forbidden):
            raise UnifiedReleaseProgramVaultStateError(f"{forbidden} is not allowed for Vault operations.")
    return payload


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
