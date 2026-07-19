# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.documents import DomainDocument
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train_verifier import EXPECTED_EVIDENCE_PACKAGE_TYPES as EXPECTED_EVIDENCE_PACKAGE_TYPES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package, write_unified_command_center_release_train_verification_report as write_unified_command_center_release_train_verification_report

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

UnifiedCommandCenterReleaseTrainStateError = _make_deferred_global('UnifiedCommandCenterReleaseTrainStateError')
_build_evidence_rows = _make_deferred_global('_build_evidence_rows')
_dependency_document = _make_deferred_global('_dependency_document')
_go_no_go_report = _make_deferred_global('_go_no_go_report')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_inventory_document = _make_deferred_global('_inventory_document')
_read_external_manifest = _make_deferred_global('_read_external_manifest')
_readiness_document = _make_deferred_global('_readiness_document')
_runbook_document = _make_deferred_global('_runbook_document')
_runbook_result = _make_deferred_global('_runbook_result')
_wave_document = _make_deferred_global('_wave_document')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedCommandCenterReleaseTrainStateError, _build_evidence_rows, _dependency_document, _go_no_go_report, _integrity_hash, _integrity_ok, _inventory_document
    global _read_external_manifest, _readiness_document, _runbook_document, _runbook_result, _wave_document, row
    UnifiedCommandCenterReleaseTrainStateError = namespace.get('UnifiedCommandCenterReleaseTrainStateError', UnifiedCommandCenterReleaseTrainStateError)
    _build_evidence_rows = namespace.get('_build_evidence_rows', _build_evidence_rows)
    _dependency_document = namespace.get('_dependency_document', _dependency_document)
    _go_no_go_report = namespace.get('_go_no_go_report', _go_no_go_report)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _inventory_document = namespace.get('_inventory_document', _inventory_document)
    _read_external_manifest = namespace.get('_read_external_manifest', _read_external_manifest)
    _readiness_document = namespace.get('_readiness_document', _readiness_document)
    _runbook_document = namespace.get('_runbook_document', _runbook_document)
    _runbook_result = namespace.get('_runbook_result', _runbook_result)
    _wave_document = namespace.get('_wave_document', _wave_document)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


DEFAULT_REQUIRED_EVIDENCE = [
    "ucc",
    "ucc_archive",
    "handoff",
    "continuous_review",
    "evidence_review",
    "reviewer_decision_board",
]




class UnifiedCommandCenterReleaseTrainStoreEvidenceMixin:
    def _build_documents(self, train_id: str, payload: DomainDocument) -> DomainDocument:
        train = self.read_train(train_id)
        items_doc = self._read_items(train_id)
        evidence_manifest = _read_external_manifest(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"), payload)
        evidence_rows, item_rows = _build_evidence_rows(items_doc, evidence_manifest)
        now = now_iso()
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_source",
                "train_id": train_id,
                "created_at": now,
                "train_hash": train.get("integrity_hash"),
                "items_hash": items_doc.get("integrity_hash"),
                "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
                "external_evidence_item_count": len(evidence_manifest.get("items", [])),
                "evidence_fingerprints": [{key: row.get(key) for key in ("item_id", "center_id", "evidence_type", "zip_sha256", "manifest_hash", "verification_report_hash", "verification_status")} for row in evidence_rows],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        inventory = _inventory_document(train_id, source["source_hash"], evidence_rows, now)
        readiness = _readiness_document(train_id, source["source_hash"], item_rows, evidence_rows, now)
        dependency = _dependency_document(train_id, source["source_hash"], item_rows, now)
        wave = _wave_document(train_id, source["source_hash"], item_rows, now)
        report = _go_no_go_report(train_id, source["source_hash"], train, readiness, dependency, inventory, now)
        runbook = _runbook_document(train_id, source["source_hash"], readiness, report, now)
        runbook_result = _runbook_result(train_id, source["source_hash"], [])
        return {"train": train, "source": source, "items": items_doc, "inventory": inventory, "readiness": readiness, "dependency": dependency, "wave": wave, "report": report, "runbook": runbook, "runbook_result": runbook_result}

    def _ensure_docs(self, train_id: str, payload: DomainDocument) -> DomainDocument:
        if self.report_path(train_id).exists():
            return self.read_docs(train_id)
        docs = self._build_documents(train_id, payload)
        self._write_docs(train_id, docs)
        return docs

    def _write_docs(self, train_id: str, docs: DomainDocument) -> None:
        for key, path_fn in (
            ("source", self.source_path),
            ("items", self.items_path),
            ("inventory", self.inventory_path),
            ("readiness", self.readiness_path),
            ("dependency", self.dependency_path),
            ("wave", self.wave_path),
            ("report", self.report_path),
            ("runbook", self.runbook_path),
            ("runbook_result", self.runbook_result_path),
        ):
            write_json(path_fn(train_id), docs[key])
        train = docs["train"]
        train["source_hash"] = docs["source"].get("source_hash")
        train["status"] = "ready" if docs["report"].get("status") == "go" else "no_go"
        train["updated_at"] = now_iso()
        train["integrity_hash"] = _integrity_hash(train)
        write_json(self.train_path(train_id), train)
        docs["train"] = train

    def _read_items(self, train_id: str) -> DomainDocument:
        if not self.items_path(train_id).exists():
            self._write_items(train_id, [])
        return read_json(self.items_path(train_id))

    def _write_items(self, train_id: str, rows: list[DomainDocument]) -> None:
        doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_items", "train_id": train_id, "items": rows, "summary": {"item_count": len(rows)}})
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(self.items_path(train_id), doc)

    def _signed_docs_for_export(self, train_id: str) -> DomainDocument:
        _train = self.read_train(train_id)
        signoff_path = self.signoff_path(train_id)
        state = self.latest_signoff_state(train_id)
        if state.get("status") != "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train is not currently signed.")
        if not signoff_path.exists() and self.latest_signoff_state(train_id).get("status") == "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff file is missing but history shows a signed state.")
        if not signoff_path.exists():
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train must be signed before archive export.")
        signoff = read_json(signoff_path)
        if not _integrity_ok(signoff) or signoff.get("status") != "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff integrity failed.")
        if state.get("signoff_hash") and state.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff file does not match latest signed history state.")
        binding = self._read_signoff_binding(train_id, signoff)
        docs = self.read_docs(train_id)
        checks = {
            "items_hash": docs["items"].get("integrity_hash"),
            "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
            "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
            "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
            "wave_plan_hash": docs["wave"].get("integrity_hash"),
            "go_no_go_report_hash": docs["report"].get("integrity_hash"),
            "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
            "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
        }
        for key, value in checks.items():
            if signoff.get(key) != value:
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train signed documents no longer match signoff.")
        docs["signoff"] = signoff
        docs["signoff_binding"] = binding
        return docs

    def _read_signoff_binding(self, train_id: str, signoff: DomainDocument) -> DomainDocument:
        path = self.signoff_binding_path(train_id)
        if not path.exists():
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding summary is missing.")
        binding = read_json(path)
        if not _integrity_ok(binding):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding does not match current signoff.")
        return binding

    def _append_history(self, train_id: str, payload: DomainDocument) -> DomainDocument:
        history = self.read_history(train_id)
        previous = str(history[-1].get("event_hash") or "") if history else ""
        event = sanitize_metadata({**payload, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        path = self.history_path(train_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _signoff_binding_summary(self, train_id: str, signoff: DomainDocument, event: DomainDocument) -> DomainDocument:
        binding = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_signoff_binding",
                "train_id": train_id,
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "source": {
                    "source_hash": signoff.get("source_hash"),
                    "train_hash": signoff.get("train_hash"),
                    "items_hash": signoff.get("items_hash"),
                    "evidence_inventory_hash": signoff.get("evidence_inventory_hash"),
                    "readiness_matrix_hash": signoff.get("readiness_matrix_hash"),
                    "dependency_graph_hash": signoff.get("dependency_graph_hash"),
                    "wave_plan_hash": signoff.get("wave_plan_hash"),
                    "go_no_go_report_hash": signoff.get("go_no_go_report_hash"),
                    "safe_runbook_hash": signoff.get("safe_runbook_hash"),
                    "safe_runbook_result_hash": signoff.get("safe_runbook_result_hash"),
                },
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _archive_exported_for_signoff(self, train_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "ucc_release_train_archive_exported" and event.get("signoff_hash") == signoff_hash for event in self.read_history(train_id))

    def _archive_built_for_signoff(self, train_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "ucc_release_train_archive_built" and event.get("signoff_hash") == signoff_hash for event in self.read_history(train_id))

    def _open_approved_change_request(self, train_id: str) -> DomainDocument | None:
        change_dir = self.train_dir(train_id) / "change-control" / "change-requests"
        if not change_dir.exists():
            return None
        for path in sorted(change_dir.glob("*/train-change-request.json")):
            try:
                request = read_json(path)
            except Exception:
                continue
            if request.get("status") == "approved" and not request.get("applied_at"):
                return {
                    "change_request_id": request.get("change_request_id"),
                    "status": request.get("status"),
                    "reason": request.get("reason"),
                }
        return None

    def _next_train_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob("uct-*/train.json"):
            try:
                max_seen = max(max_seen, int(path.parent.name.split("-")[-1]))
            except ValueError:
                continue
        return f"uct-{max_seen + 1:06d}"
