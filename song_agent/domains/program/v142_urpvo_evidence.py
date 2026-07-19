# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import shutil as shutil
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore as UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package, write_unified_release_program_vault_operations_verification_report as write_unified_release_program_vault_operations_verification_report

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

UnifiedReleaseProgramVaultOperationsNotFoundError = _make_deferred_global('UnifiedReleaseProgramVaultOperationsNotFoundError')
UnifiedReleaseProgramVaultOperationsStateError = _make_deferred_global('UnifiedReleaseProgramVaultOperationsStateError')
_archive_manifest_document = _make_deferred_global('_archive_manifest_document')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_read_history = _make_deferred_global('_read_history')
_read_optional_json = _make_deferred_global('_read_optional_json')
_recipient_guide = _make_deferred_global('_recipient_guide')
_sanitize_payload = _make_deferred_global('_sanitize_payload')
_sha256_path = _make_deferred_global('_sha256_path')
_with_integrity = _make_deferred_global('_with_integrity')
read_json = _make_deferred_global('read_json')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramVaultOperationsNotFoundError, UnifiedReleaseProgramVaultOperationsStateError, _archive_manifest_document, _file_record, _gate_failed, _integrity_hash, _integrity_ok
    global _read_history, _read_optional_json, _recipient_guide, _sanitize_payload, _sha256_path, _with_integrity, read_json, write_json
    UnifiedReleaseProgramVaultOperationsNotFoundError = namespace.get('UnifiedReleaseProgramVaultOperationsNotFoundError', UnifiedReleaseProgramVaultOperationsNotFoundError)
    UnifiedReleaseProgramVaultOperationsStateError = namespace.get('UnifiedReleaseProgramVaultOperationsStateError', UnifiedReleaseProgramVaultOperationsStateError)
    _archive_manifest_document = namespace.get('_archive_manifest_document', _archive_manifest_document)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _read_history = namespace.get('_read_history', _read_history)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _recipient_guide = namespace.get('_recipient_guide', _recipient_guide)
    _sanitize_payload = namespace.get('_sanitize_payload', _sanitize_payload)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _with_integrity = namespace.get('_with_integrity', _with_integrity)
    read_json = namespace.get('read_json', read_json)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


VAULT_OPERATIONS_BLOCKED_METADATA_KEYS = {
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




class UnifiedReleaseProgramVaultOperationsStoreEvidenceMixin:
    def export_archive(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            docs = self._signed_archive_docs(program_id)
            export_dir = self.export_dir(program_id)
            manifest_path = self.manifest_path(program_id)
            if manifest_path.exists():
                manifest = read_json(manifest_path)
                if manifest.get("source", {}).get("signoff_binding_hash") != docs["binding"].get("integrity_hash"):
                    raise UnifiedReleaseProgramVaultOperationsStateError("Existing Vault Operations archive export does not match current signoff binding.")
                return manifest
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_doc(rel: str, value: DomainDocument | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            def copy_file(source: Path, rel: str) -> None:
                if not source.exists() or not source.is_file():
                    raise UnifiedReleaseProgramVaultOperationsStateError(f"Required Vault Operations archive evidence is missing: {source}")
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, path)
                files.append(_file_record(path, rel))

            write_doc("vault-operations-report.json", docs["report"])
            write_doc("registry.json", docs["registry"])
            write_doc("policy.json", docs["policy"])
            write_doc("latest-review-report.json", docs["review"])
            write_doc("rotation-plan-summary.json", docs["rotation"])
            write_doc("transfer-report.json", docs["transfer"])
            write_doc("vault-operations-signoff.json", docs["signoff"])
            write_doc("vault-operations-signoff-binding-summary.json", docs["binding"])
            history_text = self.history_path(program_id).read_text(encoding="utf-8") if self.history_path(program_id).exists() else ""
            write_doc("vault-operations-history.jsonl", history_text)
            vault_zip, vault_anchor, vault_verification = self._vault_evidence_paths(program_id, docs["current_vault"])
            copy_file(vault_zip, "packages/current-vault.zip")
            copy_file(vault_anchor, "proofs/current-vault-anchor.json")
            copy_file(vault_verification, "proofs/current-vault-verification-report.json")
            write_doc("docs/recipient-guide.md", self.recipient_guide_path(program_id).read_text(encoding="utf-8") if self.recipient_guide_path(program_id).exists() else _recipient_guide(program_id, docs["transfer"]))
            write_doc("docs/replica-checklist.json", _read_optional_json(self.replica_checklist_path(program_id)) or _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_replica_checklist", "program_id": program_id, "items": []}))
            write_doc("README.txt", "MusicForge Unified Release Program Vault Operations Archive\n")
            manifest = _archive_manifest_document(program_id, docs, files)
            write_json(manifest_path, manifest)
            return manifest

    def build_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        _sanitize_payload(payload or {})
        with self.lock:
            self._signed_archive_docs(program_id)
            zip_path = self.archive_zip_path(program_id)
            if zip_path.exists():
                return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": _read_optional_json(self.manifest_path(program_id)).get("integrity_hash")}
            manifest = self.export_archive(program_id)
            export_dir = self.export_dir(program_id)
            entries = sorted(path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            ArchiveBuilder.build_directory_zip(export_dir, zip_path)
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": manifest.get("integrity_hash")}

    def verify_archive_zip(self, program_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = _sanitize_payload(payload or {})
        report = verify_unified_release_program_vault_operations_package(
            payload.get("archive_zip") or payload.get("zip_path") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current_vault=bool(payload.get("require_current_vault", True)),
            signoff_binding_path=payload.get("signoff_binding") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_vault_operations_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        program_id: str,
        *,
        required: bool = False,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
        **_: object,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(program_id)
        binding_path = Path(signoff_binding_path) if signoff_binding_path else self.signoff_binding_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Vault Operations archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Vault Operations verification report is missing.")
        if not binding_path.exists():
            return _gate_failed("Unified Release Program Vault Operations signoff binding is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_vault_operations_package(zip_path, strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=binding_path)
        except Exception as exc:
            return _gate_failed(f"Unified Release Program Vault Operations gate could not verify evidence: {sanitize_sensitive_text(str(exc))}")
        if external.get("package_type") != "musicforge_unified_release_program_vault_operations_verification":
            return _gate_failed("Unified Release Program Vault Operations verification report package type is invalid.")
        if not _integrity_ok(external):
            return _gate_failed("Unified Release Program Vault Operations verification report integrity failed.")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            return _gate_failed("Unified Release Program Vault Operations verifier failed.", summary=runtime.get("summary", {}), blockers=runtime.get("blockers", []))
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            return _gate_failed("Unified Release Program Vault Operations verification report does not match current archive ZIP.")
        return {"status": "passed", "hard_block": False, "summary": runtime.get("summary", {}), "verification_report_hash": external.get("integrity_hash")}

    def latest_signoff_state(self, program_id: str) -> DomainDocument:
        events = _read_history(self.history_path(program_id))
        signoffs = [row for row in events if row.get("event_type") == "vault_operations_signoff_created"]
        if not signoffs:
            return {"status": "unsigned", "signed": False}
        latest = signoffs[-1]
        return {"status": "signed", "signed": True, "signoff_hash": latest.get("signoff_hash"), "event_hash": latest.get("event_hash"), "event_index": latest.get("event_index")}

    def _ensure_unsigned(self, program_id: str) -> None:
        state = self.latest_signoff_state(program_id)
        if state.get("signed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Unified Release Program Vault Operations are signed. Create a successor operations record before mutation.")

    def _read_registry(self, program_id: str) -> DomainDocument:
        registry = _read_optional_json(self.registry_path(program_id))
        if not registry:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault Operations registry is missing.")
        if not _integrity_ok(registry):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations registry integrity failed.")
        return registry

    def _read_policy(self, program_id: str) -> DomainDocument:
        policy = _read_optional_json(self.policy_path(program_id))
        if not policy:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault Operations policy is missing.")
        if not _integrity_ok(policy):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations policy integrity failed.")
        return policy

    def _read_latest_review(self, program_id: str) -> DomainDocument:
        review = _read_optional_json(self.latest_review_path(program_id))
        if not review:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Latest Vault custody review is missing.")
        if not _integrity_ok(review):
            raise UnifiedReleaseProgramVaultOperationsStateError("Latest Vault custody review integrity failed.")
        return review

    def _read_transfer(self, program_id: str) -> DomainDocument:
        transfer = _read_optional_json(self.transfer_report_path(program_id))
        if not transfer:
            raise UnifiedReleaseProgramVaultOperationsNotFoundError("Vault transfer report is missing.")
        if not _integrity_ok(transfer):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault transfer report integrity failed.")
        return transfer

    def _current_generation(self, registry: DomainDocument) -> DomainDocument:
        current_id = str(registry.get("current_generation_id") or "")
        for row in registry.get("generations", []) or []:
            if isinstance(row, dict) and row.get("generation_id") == current_id:
                return row
        return {}

    def _current_vault_binding(self, program_id: str, payload: DomainDocument, *, require_passed: bool) -> DomainDocument:
        vault_zip = Path(payload.get("vault_zip") or payload.get("vault") or self.vault_store.zip_path(program_id))
        vault_anchor = Path(payload.get("vault_anchor") or payload.get("anchor") or self.vault_store.anchor_path(program_id))
        vault_verification = Path(payload.get("vault_verification_report") or self.vault_store.verification_report_path(program_id))
        for label, path in (("Vault ZIP", vault_zip), ("Vault anchor", vault_anchor), ("Vault verification report", vault_verification)):
            if not path.exists():
                raise UnifiedReleaseProgramVaultOperationsStateError(f"{label} is missing: {path}")
        runtime = verify_unified_release_program_vault_package(vault_zip, strict=True, deep=True, require_anchor=True, vault_anchor_path=vault_anchor, require_accepted_evidence=True)
        external = read_json(vault_verification)
        anchor = read_json(vault_anchor)
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report package type is invalid.")
        if anchor.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor package type is invalid.")
        if not _integrity_ok(external):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report integrity failed.")
        if not _integrity_ok(anchor):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor integrity failed.")
        if require_passed and (runtime.get("status") != "passed" or external.get("status") != "passed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Current Vault runtime and external verification must pass.")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault verification report does not match current Vault ZIP.")
        if anchor.get("vault_zip_sha256") != runtime.get("zip_sha256") or anchor.get("vault_manifest_hash") != runtime.get("manifest_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault anchor does not match current Vault ZIP.")
        return {
            "vault_zip_sha256": _sha256_path(vault_zip),
            "vault_zip_size_bytes": vault_zip.stat().st_size,
            "vault_manifest_hash": runtime.get("manifest_hash"),
            "vault_source_hash": (runtime.get("summary") or {}).get("source_hash") or anchor.get("vault_source_hash"),
            "vault_anchor_hash": anchor.get("integrity_hash"),
            "vault_verification_report_hash": external.get("integrity_hash"),
            "runtime_vault_verification_hash": runtime.get("integrity_hash"),
        }

    def _vault_evidence_paths(self, program_id: str, vault: DomainDocument) -> tuple[Path, Path, Path]:
        candidates = (
            Path(str(vault.get("vault_zip_path") or "")),
            Path(str(vault.get("vault_anchor_path") or "")),
            Path(str(vault.get("vault_verification_report_path") or "")),
        )
        defaults = (
            self.vault_store.zip_path(program_id),
            self.vault_store.anchor_path(program_id),
            self.vault_store.verification_report_path(program_id),
        )
        resolved: list[Path] = []
        for candidate, default in zip(candidates, defaults, strict=True):
            resolved.append(candidate if candidate.exists() and candidate.is_file() else default)
        return resolved[0], resolved[1], resolved[2]

    def _signed_archive_docs(self, program_id: str) -> DomainDocument:
        state = self.latest_signoff_state(program_id)
        if not state.get("signed"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations must be signed before archive export.")
        signoff = _read_optional_json(self.signoff_path(program_id))
        binding = _read_optional_json(self.signoff_binding_path(program_id))
        if not signoff or not binding:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff and binding are required.")
        registry = self._read_registry(program_id)
        policy = self._read_policy(program_id)
        review = self._read_latest_review(program_id)
        transfer = self._read_transfer(program_id)
        report = _read_optional_json(self.report_path(program_id))
        rotation = _read_optional_json(self.rotation_plan_path(program_id)) or _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_vault_rotation_plan", "program_id": program_id, "status": "not_required", "actions": []})
        if not _integrity_ok(signoff) or not _integrity_ok(binding) or not _integrity_ok(report):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signed documents integrity failed.")
        if signoff.get("integrity_hash") != state.get("signoff_hash") or binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff does not match signed history.")
        if binding.get("latest_history_event_hash") != state.get("event_hash"):
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations signoff binding does not match latest history event.")
        expected = {
            "report_hash": report.get("integrity_hash"),
            "registry_hash": registry.get("integrity_hash"),
            "policy_hash": policy.get("integrity_hash"),
            "latest_review_hash": review.get("integrity_hash"),
            "transfer_report_hash": transfer.get("integrity_hash"),
        }
        for key, value in expected.items():
            if signoff.get(key) != value or binding.get(key) != value:
                raise UnifiedReleaseProgramVaultOperationsStateError(f"Vault Operations signed binding mismatch: {key}.")
        context = self._current_registry_vault_binding(program_id, registry)
        if context["blockers"]:
            raise UnifiedReleaseProgramVaultOperationsStateError("Vault Operations current Vault binding failed: " + ", ".join(context["blockers"]))
        vault = context["vault"]
        vault_expected = {
            "vault_zip_sha256": vault.get("vault_zip_sha256"),
            "vault_zip_size_bytes": vault.get("vault_zip_size_bytes"),
            "vault_manifest_hash": vault.get("vault_manifest_hash"),
            "vault_anchor_hash": vault.get("vault_anchor_hash"),
            "vault_verification_report_hash": vault.get("vault_verification_report_hash"),
        }
        for key, value in vault_expected.items():
            if binding.get(key) != value:
                raise UnifiedReleaseProgramVaultOperationsStateError(f"Vault Operations signed Vault binding mismatch: {key}.")
        return {"report": report, "registry": registry, "policy": policy, "review": review, "rotation": rotation, "transfer": transfer, "signoff": signoff, "binding": binding, "current_vault": vault}

    def _current_registry_vault_binding(self, program_id: str, registry: DomainDocument) -> DomainDocument:
        current = self._current_generation(registry)
        if not current:
            raise UnifiedReleaseProgramVaultOperationsStateError("A current Vault generation is required.")
        vault = _as_document(current.get("vault"))
        if not vault:
            raise UnifiedReleaseProgramVaultOperationsStateError("Current Vault generation binding is missing.")
        vault_zip, vault_anchor, vault_verification = self._vault_evidence_paths(program_id, vault)
        for label, path in (("Vault ZIP", vault_zip), ("Vault anchor", vault_anchor), ("Vault verification report", vault_verification)):
            if not path.exists() or not path.is_file():
                raise UnifiedReleaseProgramVaultOperationsStateError(f"{label} is missing: {path}")
        runtime = verify_unified_release_program_vault_package(
            vault_zip,
            strict=True,
            deep=True,
            require_anchor=True,
            vault_anchor_path=vault_anchor,
            require_accepted_evidence=True,
        )
        external = read_json(vault_verification)
        anchor = read_json(vault_anchor)
        blockers = self._current_registry_vault_blockers(vault, vault_zip, runtime, external, anchor)
        return {
            "current": current,
            "vault": vault,
            "vault_zip": vault_zip,
            "vault_anchor": vault_anchor,
            "vault_verification": vault_verification,
            "runtime": runtime,
            "external": external,
            "anchor": anchor,
            "blockers": blockers,
        }

    def _current_registry_vault_blockers(self, vault: DomainDocument, vault_zip: Path, runtime: DomainDocument, external: DomainDocument, anchor: DomainDocument) -> list[str]:
        blockers: list[str] = []
        if runtime.get("status") != "passed":
            blockers.append("runtime_vault_verification_failed")
        if external.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE:
            blockers.append("external_vault_verification_package_type")
        if anchor.get("package_type") != UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE:
            blockers.append("vault_anchor_package_type")
        if external.get("status") != "passed" or not _integrity_ok(external):
            blockers.append("external_vault_verification_failed")
        if not _integrity_ok(anchor):
            blockers.append("vault_anchor_integrity_failed")
        current_zip_hash = _sha256_path(vault_zip)
        current_zip_size = vault_zip.stat().st_size if vault_zip.exists() else None
        expected = {
            "vault_zip_sha256": current_zip_hash,
            "vault_zip_size_bytes": current_zip_size,
            "vault_manifest_hash": runtime.get("manifest_hash"),
            "vault_anchor_hash": anchor.get("integrity_hash"),
            "vault_verification_report_hash": external.get("integrity_hash"),
        }
        for key, value in expected.items():
            if vault.get(key) != value:
                blockers.append(f"registry_current_{key}")
        if external.get("zip_sha256") != current_zip_hash or external.get("zip_sha256") != runtime.get("zip_sha256"):
            blockers.append("external_vault_verification_zip_sha256")
        if external.get("manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("external_vault_verification_manifest_hash")
        if anchor.get("vault_zip_sha256") != current_zip_hash or anchor.get("vault_zip_sha256") != runtime.get("zip_sha256"):
            blockers.append("vault_anchor_zip_sha256")
        if int(anchor.get("vault_zip_size_bytes") or -1) != int(current_zip_size or -2):
            blockers.append("vault_anchor_zip_size")
        if anchor.get("vault_manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("vault_anchor_manifest_hash")
        vault_source = (runtime.get("summary") or {}).get("source_hash") or anchor.get("vault_source_hash")
        if vault.get("vault_source_hash") and vault_source and vault.get("vault_source_hash") != vault_source:
            blockers.append("registry_current_vault_source_hash")
        if vault.get("runtime_vault_verification_hash") and runtime.get("integrity_hash") and vault.get("runtime_vault_verification_hash") != runtime.get("integrity_hash"):
            blockers.append("registry_current_runtime_vault_verification_hash")
        return sorted(set(blockers))

    def _append_history(self, program_id: str, event: DomainDocument) -> DomainDocument:
        path = self.history_path(program_id)
        chain = HistoryChain(path, sanitizer=lambda value: sanitize_metadata(value, blocked_keys=VAULT_OPERATIONS_BLOCKED_METADATA_KEYS))
        return chain.append({**event, "event_index": len(chain.read()) + 1})

    def _next_review_id(self, program_id: str) -> str:
        base = self.ops_dir(program_id) / "custody-review-runs"
        count = len([path for path in base.glob("vault-review-*") if path.is_dir()]) if base.exists() else 0
        return f"vault-review-{count + 1:06d}"
