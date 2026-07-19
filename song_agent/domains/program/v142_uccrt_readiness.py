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

UnifiedCommandCenterReleaseTrainNotFoundError = _make_deferred_global('UnifiedCommandCenterReleaseTrainNotFoundError')
UnifiedCommandCenterReleaseTrainStateError = _make_deferred_global('UnifiedCommandCenterReleaseTrainStateError')
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_integrity_ok = _make_deferred_global('_integrity_ok')
_manifest_document = _make_deferred_global('_manifest_document')
_readme = _make_deferred_global('_readme')
_required_evidence = _make_deferred_global('_required_evidence')
_reviewer_guide = _make_deferred_global('_reviewer_guide')
_runbook_result = _make_deferred_global('_runbook_result')
_safe_id = _make_deferred_global('_safe_id')
_sha256_path = _make_deferred_global('_sha256_path')
info = _make_deferred_global('info')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedCommandCenterReleaseTrainNotFoundError, UnifiedCommandCenterReleaseTrainStateError, _bounded, _file_record, _gate_failed, _integrity_hash, _integrity_ok
    global _manifest_document, _readme, _required_evidence, _reviewer_guide, _runbook_result, _safe_id, _sha256_path, info
    global key, value
    UnifiedCommandCenterReleaseTrainNotFoundError = namespace.get('UnifiedCommandCenterReleaseTrainNotFoundError', UnifiedCommandCenterReleaseTrainNotFoundError)
    UnifiedCommandCenterReleaseTrainStateError = namespace.get('UnifiedCommandCenterReleaseTrainStateError', UnifiedCommandCenterReleaseTrainStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _integrity_ok = namespace.get('_integrity_ok', _integrity_ok)
    _manifest_document = namespace.get('_manifest_document', _manifest_document)
    _readme = namespace.get('_readme', _readme)
    _required_evidence = namespace.get('_required_evidence', _required_evidence)
    _reviewer_guide = namespace.get('_reviewer_guide', _reviewer_guide)
    _runbook_result = namespace.get('_runbook_result', _runbook_result)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    info = namespace.get('info', info)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


DEFAULT_REQUIRED_EVIDENCE = [
    "ucc",
    "ucc_archive",
    "handoff",
    "continuous_review",
    "evidence_review",
    "reviewer_decision_board",
]




class UnifiedCommandCenterReleaseTrainStoreReadinessMixin:
    def train_dir(self, train_id: str) -> Path:
        return self.root / _safe_id(train_id)

    def train_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train.json"

    def source_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-source.json"

    def items_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-items.json"

    def inventory_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "evidence-inventory.json"

    def readiness_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "readiness-matrix.json"

    def dependency_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "dependency-graph.json"

    def wave_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "wave-plan.json"

    def report_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "go-no-go-report.json"

    def runbook_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "safe-runbook.json"

    def runbook_result_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "safe-runbook-result.json"

    def signoff_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-signoff.json"

    def signoff_binding_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-signoff-binding-summary.json"

    def history_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-history.jsonl"

    def archive_dir(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "archive"

    def archive_manifest_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "manifest.json"

    def zip_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "unified-command-center-release-train.zip"

    def verification_report_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "unified-command-center-release-train-verification-report.json"

    def archive_history_dir(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "archive-history"

    def archive_history_signoff_dir(self, train_id: str, signoff_hash: str) -> Path:
        safe_hash = _safe_id(signoff_hash)
        return self.archive_history_dir(train_id) / (safe_hash[:16] or "unknown")

    def create_train(self, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            train_id = _safe_id(str(payload.get("train_id") or self._next_train_id()))
            if self.train_path(train_id).exists():
                raise UnifiedCommandCenterReleaseTrainStateError(f"Unified Command Center Release Train already exists: {train_id}")
            now = now_iso()
            train = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_record",
                    "train_id": train_id,
                    "name": _bounded(payload.get("name") or "Unified Command Center Release Train", 200),
                    "profile": _bounded(payload.get("profile") or "ga", 80),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                    "policy": {
                        "required_evidence": _required_evidence(payload.get("required_evidence")),
                        "allow_duplicate_center": bool(payload.get("allow_duplicate_center", False)),
                    },
                }
            )
            train["integrity_hash"] = _integrity_hash(train)
            self.train_dir(train_id).mkdir(parents=True, exist_ok=True)
            write_json(self.train_path(train_id), train)
            self._write_items(train_id, [])
            if payload.get("items"):
                for item in payload.get("items") or []:
                    self.add_item(train_id, dict(item))
            return self.read_train(train_id)

    def list_trains(self) -> list[DomainDocument]:
        if not self.root.exists():
            return []
        rows = []
        for path in sorted(self.root.glob("uct-*")):
            train_path = path / "train.json"
            if train_path.exists():
                rows.append(read_json(train_path))
        return rows

    def read_train(self, train_id: str) -> DomainDocument:
        if not self.train_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainNotFoundError(f"Unified Command Center Release Train not found: {train_id}")
        return read_json(self.train_path(train_id))

    def read_docs(self, train_id: str) -> DomainDocument:
        if not self.report_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainNotFoundError(f"Unified Command Center Release Train report not found: {train_id}")
        return {
            "train": self.read_train(train_id),
            "source": read_json(self.source_path(train_id)),
            "items": read_json(self.items_path(train_id)),
            "inventory": read_json(self.inventory_path(train_id)),
            "readiness": read_json(self.readiness_path(train_id)),
            "dependency": read_json(self.dependency_path(train_id)),
            "wave": read_json(self.wave_path(train_id)),
            "report": read_json(self.report_path(train_id)),
            "runbook": read_json(self.runbook_path(train_id)),
            "runbook_result": read_json(self.runbook_result_path(train_id)),
        }

    def add_item(self, train_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(train_id)
            train = self.read_train(train_id)
            items_doc = self._read_items(train_id)
            rows = list(items_doc.get("items") or [])
            center_id = _safe_id(str(payload.get("center_id") or ""))
            if not center_id:
                raise UnifiedCommandCenterReleaseTrainStateError("center_id is required.")
            allow_duplicate = bool(payload.get("allow_duplicate_center", train.get("policy", {}).get("allow_duplicate_center", False)))
            if not allow_duplicate and any(row.get("center_id") == center_id for row in rows):
                raise UnifiedCommandCenterReleaseTrainStateError("Duplicate center_id requires allow_duplicate_center=true.")
            item_id = _safe_id(str(payload.get("item_id") or f"item-{len(rows) + 1:03d}"))
            if any(row.get("item_id") == item_id for row in rows):
                raise UnifiedCommandCenterReleaseTrainStateError(f"Duplicate train item_id: {item_id}")
            row = sanitize_metadata(
                {
                    "item_id": item_id,
                    "center_id": center_id,
                    "label": _bounded(payload.get("label") or center_id, 200),
                    "wave": int(payload.get("wave") or len(rows) + 1),
                    "depends_on": [_safe_id(str(item)) for item in payload.get("depends_on", []) if str(item)],
                    "required_evidence": _required_evidence(payload.get("required_evidence") or train.get("policy", {}).get("required_evidence")),
                    "status": "pending",
                }
            )
            rows.append(row)
            self._write_items(train_id, rows)
            train["updated_at"] = now_iso()
            train["integrity_hash"] = _integrity_hash(train)
            write_json(self.train_path(train_id), train)
            return row

    def refresh(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._build_documents(train_id, payload or {})
            self._write_docs(train_id, docs)
            return docs["report"]

    def run_safe(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._ensure_docs(train_id, payload or {})
            current_source = self._build_documents(train_id, payload or {})["source"]["source_hash"]
            if current_source != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train source is stale. Refresh before running safe actions.")
            results = []
            for item in docs["runbook"].get("items", []):
                action = str(item.get("action") or "")
                item_id = str(item.get("item_id") or "")
                if action == "release_train.refresh":
                    refreshed = self._build_documents(train_id, payload or {})
                    self._write_docs(train_id, refreshed)
                    results.append({"item_id": item_id, "action": action, "status": "completed"})
                elif action in {"release_train.export", "release_train.zip", "release_train.verify"}:
                    results.append({"item_id": item_id, "action": action, "status": "manual_required", "reason": "Archive actions require signed Release Train."})
                else:
                    results.append({"item_id": item_id, "action": action, "status": "skipped_unsupported", "reason": "Safe action must be executed by the owning UCC module."})
            result_doc = _runbook_result(train_id, docs["source"].get("source_hash"), results)
            write_json(self.runbook_result_path(train_id), result_doc)
            return result_doc

    def signoff(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._build_documents(train_id, payload)
            if docs["report"].get("status") != "go":
                self._write_docs(train_id, docs)
                raise UnifiedCommandCenterReleaseTrainStateError("Unified Command Center Release Train must be GO before signoff.")
            self._write_docs(train_id, docs)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_signoff",
                    "train_id": train_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "release-train-owner", 120),
                    "role": _bounded(payload.get("role") or "release_train_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Unified Command Center Release Train approved for release.", 1000),
                    "signed_at": now,
                    "source_hash": docs["source"].get("source_hash"),
                    "train_hash": docs["train"].get("integrity_hash"),
                    "items_hash": docs["items"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                    "wave_plan_hash": docs["wave"].get("integrity_hash"),
                    "go_no_go_report_hash": docs["report"].get("integrity_hash"),
                    "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
                    "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                    "summary": docs["report"].get("summary", {}),
                    "tool": {"name": "MusicForge Unified Command Center Release Train Signoff", "version": __version__},
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(train_id), signoff)
            event = self._append_history(
                train_id,
                {
                    "event_type": "ucc_release_train_signoff_created",
                    "created_at": now,
                    "train_id": train_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "go_no_go_report_hash": signoff.get("go_no_go_report_hash"),
                    "evidence_inventory_hash": signoff.get("evidence_inventory_hash"),
                },
            )
            write_json(self.signoff_binding_path(train_id), self._signoff_binding_summary(train_id, signoff, event))
            train = docs["train"]
            train["status"] = "signed"
            train["signed_at"] = now
            train["signoff_hash"] = signoff.get("integrity_hash")
            train["updated_at"] = now
            train["integrity_hash"] = _integrity_hash(train)
            write_json(self.train_path(train_id), train)
            return signoff

    def export_archive(self, train_id: str) -> DomainDocument:
        with self.lock:
            docs = self._signed_docs_for_export(train_id)
            signoff_hash = docs["signoff"].get("integrity_hash")
            if self._archive_exported_for_signoff(train_id, str(signoff_hash)):
                if self.archive_manifest_path(train_id).exists():
                    return read_json(self.archive_manifest_path(train_id))
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train archive was already exported for this signoff. Create a new train before rebuilding.")
            archive_dir = self.archive_dir(train_id)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_entry(rel: str, payload: DomainDocument | str) -> None:
                path = archive_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("train.json", docs["train"])
            write_entry("train-source.json", docs["source"])
            write_entry("train-items.json", docs["items"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("dependency-graph.json", docs["dependency"])
            write_entry("wave-plan.json", docs["wave"])
            write_entry("go-no-go-report.json", docs["report"])
            write_entry("safe-runbook.json", docs["runbook"])
            write_entry("safe-runbook-result.json", docs["runbook_result"])
            write_entry("train-signoff.json", docs["signoff"])
            write_entry("train-signoff-binding-summary.json", docs["signoff_binding"])
            write_entry("train-history.jsonl", self.history_path(train_id).read_text(encoding="utf-8") if self.history_path(train_id).exists() else "")
            write_entry("REVIEWER_GUIDE.md", _reviewer_guide(docs))
            write_entry("README.txt", _readme(docs))
            manifest = _manifest_document(train_id, docs, files)
            write_json(self.archive_manifest_path(train_id), manifest)
            self._append_history(train_id, {"event_type": "ucc_release_train_archive_exported", "created_at": now_iso(), "train_id": train_id, "signoff_hash": signoff_hash, "archive_manifest_hash": manifest.get("integrity_hash")})
            return manifest

    def build_zip(self, train_id: str) -> DomainDocument:
        with self.lock:
            docs = self._signed_docs_for_export(train_id)
            signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
            if self._archive_built_for_signoff(train_id, signoff_hash):
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train archive ZIP already exists for this signoff. Create a new train before rebuilding.")
            if not self.archive_manifest_path(train_id).exists():
                self.export_archive(train_id)
            archive_dir = self.archive_dir(train_id)
            zip_path = self.zip_path(train_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.archive_manifest_path(train_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(train_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            self._append_history(train_id, {"event_type": "ucc_release_train_archive_built", "created_at": now_iso(), "train_id": train_id, "signoff_hash": signoff_hash, "archive_zip_sha256": final_sha, "archive_manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "train_id": train_id, "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_archive(self, train_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_command_center_release_train_package(
            self.zip_path(train_id),
            strict=bool(payload.get("strict", True)),
            require_go=bool(payload.get("require_go", True)),
            require_signed=bool(payload.get("require_signed", True)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or payload.get("unified_command_center_release_train_signoff_binding") or self.signoff_binding_path(train_id),
        )
        write_unified_command_center_release_train_verification_report(report, self.verification_report_path(train_id))
        return report

    def gate(
        self,
        train_id: str,
        *,
        required: bool = True,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        external_evidence_manifest_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        state = self.latest_signoff_state(train_id)
        if state.get("status") != "signed":
            return _gate_failed("Unified Command Center Release Train is not currently signed.", signoff_state=state)
        open_change = self._open_approved_change_request(train_id)
        if open_change:
            return _gate_failed("Unified Command Center Release Train has an approved unapplied Change Request.", change_request=open_change)
        archive_zip = Path(archive_zip_path) if archive_zip_path else self.zip_path(train_id)
        verification_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(train_id)
        if not archive_zip.exists():
            return _gate_failed("Unified Command Center Release Train archive ZIP is missing.")
        if not verification_path.exists():
            return _gate_failed("Unified Command Center Release Train verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_command_center_release_train_package(
                archive_zip,
                strict=True,
                require_go=True,
                require_signed=True,
                external_evidence_manifest_path=external_evidence_manifest_path,
                signoff_binding_path=signoff_binding_path or self.signoff_binding_path(train_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Command Center Release Train verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Release Train verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Release Train verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Release Train gate passed.", "archive_zip_sha256": runtime.get("zip_sha256"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, train_id: str) -> None:
        state = self.latest_signoff_state(train_id)
        if state.get("status") == "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Unified Command Center Release Train is signed. Create a new train for changes.")

    def latest_signoff_state(self, train_id: str) -> DomainDocument:
        latest: DomainDocument | None = None
        for event in self.read_history(train_id):
            if event.get("event_type") == "ucc_release_train_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "ucc_release_train_signoff_reset":
                latest = {
                    "status": "reset",
                    "signoff_hash": event.get("previous_signoff_hash") or event.get("signoff_hash"),
                    "change_request_id": event.get("change_request_id"),
                    "event": event,
                }
        if latest:
            return latest
        if self.signoff_path(train_id).exists():
            signoff = read_json(self.signoff_path(train_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, train_id: str) -> list[DomainDocument]:
        path = self.history_path(train_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
