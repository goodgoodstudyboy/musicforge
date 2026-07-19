# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import base64 as base64
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore as UnifiedCommandCenterReleaseTrainStore
from song_agent.domains.program.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore as UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import BASE_REQUIRED_ENTRIES as BASE_REQUIRED_ENTRIES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION, verify_unified_command_center_release_train_handoff_package as verify_unified_command_center_release_train_handoff_package, write_unified_command_center_release_train_handoff_verification_report as write_unified_command_center_release_train_handoff_verification_report
from song_agent.domains.program.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore as UnifiedCommandCenterReleaseTrainLifecycleStore
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package

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

UnifiedCommandCenterReleaseTrainHandoffNotFoundError = _make_deferred_global('UnifiedCommandCenterReleaseTrainHandoffNotFoundError')
UnifiedCommandCenterReleaseTrainHandoffStateError = _make_deferred_global('UnifiedCommandCenterReleaseTrainHandoffStateError')
_bounded = _make_deferred_global('_bounded')
_check = _make_deferred_global('_check')
_file_index = _make_deferred_global('_file_index')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_document = _make_deferred_global('_manifest_document')
_merge_inputs = _make_deferred_global('_merge_inputs')
_policy = _make_deferred_global('_policy')
_read_optional_json = _make_deferred_global('_read_optional_json')
_recipient_guide = _make_deferred_global('_recipient_guide')
_reset_proof_paths = _make_deferred_global('_reset_proof_paths')
_response_binding_summary = _make_deferred_global('_response_binding_summary')
_response_from_payload = _make_deferred_global('_response_from_payload')
_response_public_summary = _make_deferred_global('_response_public_summary')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
_signoff_binding_summary = _make_deferred_global('_signoff_binding_summary')
_source_inputs = _make_deferred_global('_source_inputs')
_zip_manifest_hash = _make_deferred_global('_zip_manifest_hash')
check = _make_deferred_global('check')
info = _make_deferred_global('info')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedCommandCenterReleaseTrainHandoffNotFoundError, UnifiedCommandCenterReleaseTrainHandoffStateError, _bounded, _check, _file_index, _file_record, _gate_failed, _history_text
    global _integrity_hash, _integrity_ok, _manifest_document, _merge_inputs, _policy, _read_optional_json, _recipient_guide
    global _reset_proof_paths, _response_binding_summary, _response_from_payload, _response_public_summary, _safe_id, _sha256_path, _signoff_binding_summary, _source_inputs
    global _zip_manifest_hash, check, info, key
    UnifiedCommandCenterReleaseTrainHandoffNotFoundError = namespace.get('UnifiedCommandCenterReleaseTrainHandoffNotFoundError', UnifiedCommandCenterReleaseTrainHandoffNotFoundError)
    UnifiedCommandCenterReleaseTrainHandoffStateError = namespace.get('UnifiedCommandCenterReleaseTrainHandoffStateError', UnifiedCommandCenterReleaseTrainHandoffStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _check = namespace.get('_check', _check)
    _file_index = namespace.get('_file_index', _file_index)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_document = namespace.get('_manifest_document', _manifest_document)
    _merge_inputs = namespace.get('_merge_inputs', _merge_inputs)
    _policy = namespace.get('_policy', _policy)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _recipient_guide = namespace.get('_recipient_guide', _recipient_guide)
    _reset_proof_paths = namespace.get('_reset_proof_paths', _reset_proof_paths)
    _response_binding_summary = namespace.get('_response_binding_summary', _response_binding_summary)
    _response_from_payload = namespace.get('_response_from_payload', _response_from_payload)
    _response_public_summary = namespace.get('_response_public_summary', _response_public_summary)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _signoff_binding_summary = namespace.get('_signoff_binding_summary', _signoff_binding_summary)
    _source_inputs = namespace.get('_source_inputs', _source_inputs)
    _zip_manifest_hash = namespace.get('_zip_manifest_hash', _zip_manifest_hash)
    check = namespace.get('check', check)
    info = namespace.get('info', info)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


DEFAULT_POLICY = {
    "require_current_train": True,
    "require_change_control_if_resets": True,
    "require_lifecycle_audit": True,
    "require_ga_readiness": False,
    "require_release_check": False,
    "require_external_acceptance": False,
    "quorum": {"min_accepted": 1, "min_organizations": 1, "required_roles": ["release_owner"]},
}




class UnifiedCommandCenterReleaseTrainHandoffStoreReadinessMixin:
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

    def create_handoff(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def list_handoffs(self, train_id: str) -> list[DomainDocument]:
        if not self.handoffs_dir(train_id).exists():
            return []
        rows = []
        for path in sorted(self.handoffs_dir(train_id).glob("rth-*")):
            handoff_path = path / "handoff.json"
            if handoff_path.exists():
                rows.append(read_json(handoff_path))
        return rows

    def get_handoff(self, train_id: str, handoff_id: str | None = None) -> DomainDocument:
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

    def refresh_report(self, train_id: str, handoff_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def export_handoff(self, train_id: str, handoff_id: str) -> DomainDocument:
        with self.lock:
            docs = self._docs_for_export(train_id, handoff_id)
            export_dir = self.export_dir(train_id, handoff_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_entry(rel: str, payload: DomainDocument | str) -> None:
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

    def build_zip(self, train_id: str, handoff_id: str) -> DomainDocument:
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

    def verify_package(self, train_id: str, handoff_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
            reset_proof_paths=_as_list(_reset_proof_paths(inputs)),
            lifecycle_zip_path=inputs.get("lifecycle_zip"),
            lifecycle_verification_report_path=inputs.get("lifecycle_verification_report"),
            handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(train_id, handoff_id),
            accepted_evidence_dir=payload.get("accepted_evidence_dir") or (self.responses_dir(train_id, handoff_id) if payload.get("require_accepted") else None),
        )
        write_unified_command_center_release_train_handoff_verification_report(report, self.verification_report_path(train_id, handoff_id))
        return report

    def import_response(self, train_id: str, handoff_id: str, payload: DomainDocument) -> DomainDocument:
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

    def verify_response(self, train_id: str, handoff_id: str, response_id: str) -> DomainDocument:
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

    def create_accepted_evidence(self, train_id: str, handoff_id: str, response_id: str) -> DomainDocument:
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

    def refresh_board(self, train_id: str, handoff_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        return self.refresh_report(train_id, handoff_id, payload or {})

    def signoff(self, train_id: str, handoff_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def gate(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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
