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

UnifiedCommandCenterReleaseTrainHandoffStateError = _make_deferred_global('UnifiedCommandCenterReleaseTrainHandoffStateError')
_accepted_evidence_row_from_dir = _make_deferred_global('_accepted_evidence_row_from_dir')
_assert_signed_docs_current = _make_deferred_global('_assert_signed_docs_current')
_gap_plan_doc = _make_deferred_global('_gap_plan_doc')
_history_text = _make_deferred_global('_history_text')
_integrity_hash = _make_deferred_global('_integrity_hash')
_inventory_doc = _make_deferred_global('_inventory_doc')
_latest_signoff_event = _make_deferred_global('_latest_signoff_event')
_policy = _make_deferred_global('_policy')
_public_external_manifest = _make_deferred_global('_public_external_manifest')
_read_optional_json = _make_deferred_global('_read_optional_json')
_readiness_doc = _make_deferred_global('_readiness_doc')
_reset_proof_paths = _make_deferred_global('_reset_proof_paths')
_response_public_summary = _make_deferred_global('_response_public_summary')
_sha256_path = _make_deferred_global('_sha256_path')
line = _make_deferred_global('line')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedCommandCenterReleaseTrainHandoffStateError, _accepted_evidence_row_from_dir, _assert_signed_docs_current, _gap_plan_doc, _history_text, _integrity_hash, _inventory_doc, _latest_signoff_event
    global _policy, _public_external_manifest, _read_optional_json, _readiness_doc, _reset_proof_paths, _response_public_summary, _sha256_path
    global line, row
    UnifiedCommandCenterReleaseTrainHandoffStateError = namespace.get('UnifiedCommandCenterReleaseTrainHandoffStateError', UnifiedCommandCenterReleaseTrainHandoffStateError)
    _accepted_evidence_row_from_dir = namespace.get('_accepted_evidence_row_from_dir', _accepted_evidence_row_from_dir)
    _assert_signed_docs_current = namespace.get('_assert_signed_docs_current', _assert_signed_docs_current)
    _gap_plan_doc = namespace.get('_gap_plan_doc', _gap_plan_doc)
    _history_text = namespace.get('_history_text', _history_text)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _inventory_doc = namespace.get('_inventory_doc', _inventory_doc)
    _latest_signoff_event = namespace.get('_latest_signoff_event', _latest_signoff_event)
    _policy = namespace.get('_policy', _policy)
    _public_external_manifest = namespace.get('_public_external_manifest', _public_external_manifest)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _readiness_doc = namespace.get('_readiness_doc', _readiness_doc)
    _reset_proof_paths = namespace.get('_reset_proof_paths', _reset_proof_paths)
    _response_public_summary = namespace.get('_response_public_summary', _response_public_summary)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    line = namespace.get('line', line)
    row = namespace.get('row', row)
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




class UnifiedCommandCenterReleaseTrainHandoffStoreEvidenceMixin:
    def _build_documents(self, train_id: str, handoff_id: str, inputs: DomainDocument) -> DomainDocument:
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

    def _train_summary(self, inputs: DomainDocument) -> DomainDocument:
        zip_path = Path(inputs.get("train_archive") or "")
        report_path = Path(inputs.get("train_verification_report") or "")
        binding_path = Path(inputs.get("train_signoff_binding") or "")
        manifest_path = Path(inputs.get("external_evidence_manifest") or "")
        if not zip_path.exists() or not report_path.exists() or not binding_path.exists() or not manifest_path.exists():
            return {"evidence_type": "release_train_archive", "status": "missing"}
        external = read_json(report_path)
        runtime = verify_unified_command_center_release_train_package(zip_path, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=binding_path)
        return {"evidence_type": "release_train_archive", "status": "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" else "failed", "runtime_status": runtime.get("status"), "external_status": external.get("status"), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "summary": runtime.get("summary", {})}

    def _with_default_inputs(self, train_id: str, inputs: DomainDocument) -> DomainDocument:
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

    def _change_summary(self, inputs: DomainDocument, *, require: bool) -> DomainDocument:
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

    def _lifecycle_summary(self, inputs: DomainDocument, *, require: bool, reset_count: int) -> DomainDocument:
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
            reset_proof_paths=_as_list(_reset_proof_paths(inputs)),
        )
        return {"evidence_type": "release_train_lifecycle_audit", "required": True, "status": "passed" if runtime.get("status") == "passed" and external.get("status") == "passed" else "failed", "runtime_status": runtime.get("status"), "external_status": external.get("status"), "zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size, "manifest_hash": runtime.get("manifest_hash"), "verification_report_hash": _integrity_hash(external), "summary": runtime.get("summary", {})}

    def _response_summary(self, train_id: str, handoff_id: str) -> DomainDocument:
        rows = []
        for response_path in sorted(self.responses_dir(train_id, handoff_id).glob("*/response.json")) if self.responses_dir(train_id, handoff_id).exists() else []:
            response = read_json(response_path)
            rows.append({**_response_public_summary(response), "response_id": response.get("response_id"), "response_hash": response.get("integrity_hash")})
        doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_response_summary", "handoff_id": handoff_id, "train_id": train_id, "items": rows, "summary": {"total": len(rows), "accepted": len([row for row in rows if row.get("decision") == "accepted"])}}
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _accepted_summary(self, train_id: str, handoff_id: str) -> DomainDocument:
        rows = []
        for path in sorted(self.responses_dir(train_id, handoff_id).glob("*/accepted-evidence.json")) if self.responses_dir(train_id, handoff_id).exists() else []:
            rows.append(_accepted_evidence_row_from_dir(path.parent))
        passed_rows = [row for row in rows if row.get("status") == "passed"]
        doc = {"schema_version": 1, "package_type": "musicforge_release_train_handoff_accepted_evidence_summary", "handoff_id": handoff_id, "train_id": train_id, "items": rows, "summary": {"accepted_count": len(passed_rows), "failed_count": len(rows) - len(passed_rows), "organization_count": len({row.get("organization") for row in passed_rows if row.get("organization")}), "roles": sorted({str(row.get("reviewer_role")) for row in passed_rows if row.get("reviewer_role")})}}
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _write_docs(self, train_id: str, handoff_id: str, docs: DomainDocument) -> None:
        self.handoff_dir(train_id, handoff_id).mkdir(parents=True, exist_ok=True)
        write_json(self.report_path(train_id, handoff_id), docs["report"])
        write_json(self.inventory_path(train_id, handoff_id), docs["inventory"])
        write_json(self.readiness_path(train_id, handoff_id), docs["readiness"])
        write_json(self.gap_plan_path(train_id, handoff_id), docs["gap_plan"])
        write_json(self.external_manifest_path(train_id, handoff_id), docs["external_manifest"])
        write_json(self.response_summary_path(train_id, handoff_id), docs["response_summary"])
        write_json(self.accepted_summary_path(train_id, handoff_id), docs["accepted_summary"])

    def _docs_for_export(self, train_id: str, handoff_id: str) -> DomainDocument:
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

    def _append_history(self, train_id: str, handoff_id: str, event: DomainDocument) -> DomainDocument:
        history = self._read_history(train_id, handoff_id)
        previous = history[-1].get("event_hash") if history else ""
        event = sanitize_metadata({**event, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        history.append(event)
        self.history_path(train_id, handoff_id).parent.mkdir(parents=True, exist_ok=True)
        self.history_path(train_id, handoff_id).write_text(_history_text(history), encoding="utf-8")
        return event

    def _read_history(self, train_id: str, handoff_id: str) -> list[DomainDocument]:
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
