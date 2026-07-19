# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import GenerationRef as GenerationRef, ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, GenerationService as GenerationService, HistoryChain as HistoryChain, ResetService as ResetService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore as UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore, _bounded as _bounded, _gate_failed as _gate_failed, _history_text as _history_text, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _read_optional_json as _read_optional_json, _safe_id as _safe_id, _sha256_path as _sha256_path, _with_integrity as _with_integrity
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import (
    ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, command_center_acceptance_change_lifecycle_semantic_checks as command_center_acceptance_change_lifecycle_semantic_checks, command_center_acceptance_change_previous_evidence_checks as command_center_acceptance_change_previous_evidence_checks, command_center_acceptance_change_reset_semantic_checks as command_center_acceptance_change_reset_semantic_checks, verify_unified_release_program_continuity_command_center_acceptance_change_package as verify_unified_release_program_continuity_command_center_acceptance_change_package, write_unified_release_program_continuity_command_center_acceptance_change_verification_report as write_unified_release_program_continuity_command_center_acceptance_change_verification_report

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

UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = _make_deferred_global('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError')
_file_record = _make_deferred_global('_file_record')
_lifecycle_history_ok = _make_deferred_global('_lifecycle_history_ok')
item = _make_deferred_global('item')
line = _make_deferred_global('line')
read_json = _make_deferred_global('read_json')
row = _make_deferred_global('row')
write_json = _make_deferred_global('write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError, _file_record, _lifecycle_history_ok, item, line, read_json, row
    global write_json
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError = namespace.get('UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError', UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError)
    _file_record = namespace.get('_file_record', _file_record)
    _lifecycle_history_ok = namespace.get('_lifecycle_history_ok', _lifecycle_history_ok)
    item = namespace.get('item', item)
    line = namespace.get('line', line)
    read_json = namespace.get('read_json', read_json)
    row = namespace.get('row', row)
    write_json = namespace.get('write_json', write_json)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"




class UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStoreLifecycleMixin:
    def _lifecycle_report(self, program_id: str, state: DomainDocument, request_index: DomainDocument, reset_index: DomainDocument) -> DomainDocument:
        existing = _read_optional_json(self.lifecycle_report_path(program_id))
        events = self.read_lifecycle_events(program_id)
        history_ok = _lifecycle_history_ok(events)
        blockers = []
        if not history_ok:
            blockers.append("lifecycle_history_integrity")
        if state.get("latest_acceptance_status") == "reset_pending":
            blockers.append("successor_acceptance_signoff_required")
        status = "passed" if not blockers else "failed"
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_lifecycle_report",
                "program_id": program_id,
                "status": status,
                "summary": {
                    "change_request_count": (request_index.get("summary") or {}).get("request_count"),
                    "reset_count": (reset_index.get("summary") or {}).get("reset_count"),
                    "latest_acceptance_status": state.get("latest_acceptance_status"),
                    "event_count": len(events),
                },
                "blockers": blockers,
                "source": {
                    "state_hash": state.get("integrity_hash"),
                    "change_request_index_hash": request_index.get("integrity_hash"),
                    "reset_proof_index_hash": reset_index.get("integrity_hash"),
                    "event_hashes": [row.get("event_hash") for row in events],
                },
                "created_at": existing.get("created_at") or now_iso(),
            }
        )

    def _archive_documents(self, program_id: str) -> DomainDocument:
        self._sync_acceptance_lifecycle_event(program_id)
        state = self._change_control_state(program_id)
        if state.get("status") != "passed" or state.get("latest_acceptance_status") != "signed":
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance Change Control Archive requires a current signed Acceptance Board.")
        request_index = self._change_request_index(program_id)
        reset_index = self._reset_proof_index(program_id)
        lifecycle = self._lifecycle_report(program_id, state, request_index, reset_index)
        self.change_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.state_path(program_id), state)
        write_json(self.request_index_path(program_id), request_index)
        write_json(self.reset_index_path(program_id), reset_index)
        write_json(self.lifecycle_report_path(program_id), lifecycle)
        events = self.read_lifecycle_events(program_id)
        generation = _read_optional_json(self.current_generation_path(program_id)) or self._write_generation(program_id, 1, "current_signed" if state.get("latest_acceptance_status") == "signed" else "unsigned")
        requests = {}
        for request in self.list_change_requests(program_id):
            request_id = str(request.get("change_request_id") or "")
            requests[request_id] = {"request": request, "approval": _read_optional_json(self.approval_path(program_id, request_id)), "binding": _read_optional_json(self.request_binding_path(program_id, request_id))}
        resets = {}
        for proof in self.list_reset_proofs(program_id):
            reset_id = str(proof.get("reset_id") or "")
            resets[reset_id] = {"proof": proof, "binding": _read_optional_json(self.reset_binding_path(program_id, reset_id))}
        reset_checks = command_center_acceptance_change_reset_semantic_checks(resets, requests, events, reset_index)
        reset_checks.extend(command_center_acceptance_change_lifecycle_semantic_checks(events, resets))
        reset_blockers = [row.get("check_id") for row in reset_checks if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"]
        if reset_blockers:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError("Command Center Receiver Acceptance reset proof binding failed: " + ", ".join(str(item) for item in reset_blockers[:5]))
        previous_checks = command_center_acceptance_change_previous_evidence_checks(
            resets,
            self.generations_dir(program_id),
            require=bool(resets),
        )
        previous_blockers = [
            row.get("check_id")
            for row in previous_checks
            if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
        ]
        if previous_blockers:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Historical Receiver Acceptance evidence binding failed: "
                + ", ".join(str(item) for item in previous_blockers[:5])
            )
        generations = self._generation_summaries(program_id, state, resets)
        return {"state": state, "request_index": request_index, "reset_index": reset_index, "lifecycle": lifecycle, "events": events, "generation": generation, "requests": requests, "resets": resets, "generations": generations}

    def _validate_archive_export(self, program_id: str, root: Path, docs: DomainDocument) -> None:
        expected: DomainDocument = {
            "state.json": docs["state"],
            "request-index.json": docs["request_index"],
            "reset-index.json": docs["reset_index"],
            "generation.json": docs["generation"],
            "lifecycle.json": docs["lifecycle"],
        }
        for request_id, bundle in sorted(docs["requests"].items()):
            expected[f"cr/{request_id}/request.json"] = bundle["request"]
            expected[f"cr/{request_id}/binding.json"] = bundle["binding"]
            if bundle.get("approval"):
                expected[f"cr/{request_id}/approval.json"] = bundle["approval"]
        for reset_id, bundle in sorted(docs["resets"].items()):
            expected[f"rp/{reset_id}/proof.json"] = bundle["proof"]
            expected[f"rp/{reset_id}/binding.json"] = bundle["binding"]
        for generation, bundle in sorted(docs["generations"].items()):
            prefix = f"gen/g{generation:06d}"
            expected[f"{prefix}/verification.json"] = bundle["verification_summary"]
            expected[f"{prefix}/signoff-binding.json"] = bundle["signoff_binding_summary"]
            expected[f"{prefix}/source.json"] = bundle["source_summary"]
        expected_paths = set(expected) | {"README.txt", "events.jsonl", "manifest.json"}
        actual_paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual_paths != expected_paths:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Receiver Acceptance Change Control export layout no longer matches the frozen snapshot."
            )
        for rel, value in expected.items():
            if read_json(root / rel) != value:
                raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                    f"Receiver Acceptance Change Control export file changed: {rel}"
                )
        try:
            exported_events = [
                json.loads(line)
                for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Receiver Acceptance Change Control export lifecycle log is invalid."
            ) from exc
        if exported_events != docs["events"]:
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Receiver Acceptance Change Control export lifecycle log changed."
            )
        manifest = read_json(root / "manifest.json")
        expected_source = {
            "change_control_state_hash": docs["state"].get("integrity_hash"),
            "change_request_index_hash": docs["request_index"].get("integrity_hash"),
            "reset_proof_index_hash": docs["reset_index"].get("integrity_hash"),
            "current_generation_hash": docs["generation"].get("integrity_hash"),
            "lifecycle_report_hash": docs["lifecycle"].get("integrity_hash"),
            "latest_acceptance_signoff_hash": docs["state"].get("latest_acceptance_signoff_hash"),
            "latest_reset_proof_hash": docs["state"].get("latest_reset_proof_hash"),
        }
        actual_files = sorted(
            (
                _file_record(path, path.relative_to(root).as_posix())
                for path in root.rglob("*")
                if path.is_file() and path.name != "manifest.json"
            ),
            key=lambda row: str(row.get("path") or ""),
        )
        if (
            manifest.get("package_type") != UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE
            or manifest.get("program_id") != program_id
            or not _integrity_ok(manifest)
            or manifest.get("source") != expected_source
            or manifest.get("files") != actual_files
        ):
            raise UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError(
                "Receiver Acceptance Change Control export manifest no longer matches the frozen snapshot."
            )

    def _generation_summaries(self, program_id: str, state: DomainDocument, resets: dict[str, DomainDocument]) -> dict[int, DomainDocument]:
        generation_number = int((_read_optional_json(self.current_generation_path(program_id)).get("generation") or 1))
        summaries: dict[int, DomainDocument] = {}
        for snapshot_dir in sorted(self.generations_dir(program_id).glob("gen-*/acceptance-snapshot")):
            try:
                historical_generation = int(snapshot_dir.parent.name.split("-")[-1])
            except ValueError:
                continue
            verification = _read_optional_json(snapshot_dir / "receiver-acceptance-verification-report.json")
            signoff = _read_optional_json(snapshot_dir / "receiver-acceptance-signoff.json")
            binding = _read_optional_json(snapshot_dir / "receiver-acceptance-signoff-binding-summary.json")
            archive_path = snapshot_dir / "receiver-acceptance-archive.zip"
            summaries[historical_generation] = {
                "verification_summary": _with_integrity(
                    {
                        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                        "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_verification_summary",
                        "program_id": program_id,
                        "generation": historical_generation,
                        "verification_status": verification.get("status"),
                        "verification_report_hash": verification.get("integrity_hash"),
                        "archive_zip_sha256": _sha256_path(archive_path) if archive_path.is_file() else None,
                        "archive_manifest_hash": verification.get("manifest_hash"),
                    }
                ),
                "signoff_binding_summary": _with_integrity(
                    {
                        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                        "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_signoff_binding_summary",
                        "program_id": program_id,
                        "generation": historical_generation,
                        "signoff_hash": signoff.get("integrity_hash"),
                        "signoff_binding_hash": binding.get("integrity_hash"),
                        "history_event_hash": binding.get("history_event_hash"),
                    }
                ),
                "source_summary": _with_integrity(
                    {
                        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION,
                        "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_source_summary",
                        "program_id": program_id,
                        "generation": historical_generation,
                        "source": next(
                            (
                                proof.get("source")
                                for proof in self.list_reset_proofs(program_id)
                                if int(proof.get("previous_generation") or 0) == historical_generation
                            ),
                            {},
                        ),
                    }
                ),
            }
        acceptance_verification = _read_optional_json(self.acceptance_store.archive_verification_report_path(program_id))
        signoff_binding = _read_optional_json(self.acceptance_store.signoff_binding_path(program_id))
        source = _as_document(state.get("current_acceptance"))
        summaries[generation_number] = {
            "verification_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_verification_summary", "program_id": program_id, "generation": generation_number, "verification_status": acceptance_verification.get("status"), "verification_report_hash": acceptance_verification.get("integrity_hash"), "archive_zip_sha256": acceptance_verification.get("zip_sha256"), "archive_manifest_hash": acceptance_verification.get("manifest_hash")}),
            "signoff_binding_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_signoff_binding_summary", "program_id": program_id, "generation": generation_number, "signoff_hash": signoff_binding.get("signoff_hash"), "signoff_binding_hash": signoff_binding.get("integrity_hash"), "history_event_hash": signoff_binding.get("history_event_hash")}),
            "source_summary": _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_continuity_command_center_acceptance_generation_source_summary", "program_id": program_id, "generation": generation_number, "source": source}),
        }
        return summaries

    def _append_lifecycle_event(self, program_id: str, payload: DomainDocument) -> DomainDocument:
        return HistoryChain(self.lifecycle_event_log_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _sync_acceptance_lifecycle_event(self, program_id: str) -> None:
        latest = self.acceptance_store.latest_signoff_state(program_id)
        if latest.get("status") != "signed":
            return
        current = self._current_acceptance_state(program_id)
        events = self.read_lifecycle_events(program_id)
        if any(
            row.get("event_type") in {"receiver_acceptance_signed", "successor_receiver_acceptance_signed"}
            and row.get("signoff_hash") == current.get("signoff_hash")
            for row in events
        ):
            return
        event_type = "successor_receiver_acceptance_signed" if self.list_reset_proofs(program_id) else "receiver_acceptance_signed"
        self._append_lifecycle_event(
            program_id,
            {
                "event_type": event_type,
                "created_at": now_iso(),
                "program_id": program_id,
                "generation": current.get("generation"),
                "signoff_hash": current.get("signoff_hash"),
                "signoff_binding_hash": current.get("signoff_binding_hash"),
                "archive_zip_sha256": current.get("archive_zip_sha256"),
                "archive_manifest_hash": current.get("archive_manifest_hash"),
                "verification_report_hash": current.get("verification_report_hash"),
                "reset_proof_hash": (_read_optional_json(self.acceptance_store.state_path(program_id))).get("reset_proof_hash"),
            },
        )
        self._write_generation(program_id, int(current.get("generation") or 1), "current_signed")

    def _next_request_id(self, program_id: str) -> str:
        self.requests_dir(program_id).mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.requests_dir(program_id).glob("cr-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"cr-{max_seen + 1:06d}"
