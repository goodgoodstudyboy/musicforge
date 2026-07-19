# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report as build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check as archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)
from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_verifier import ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_acceptance_package as verify_unified_release_program_continuity_command_center_acceptance_package

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

line = _make_deferred_global('line')
path = _make_deferred_global('path')

def bind_globals(namespace: dict[str, object]) -> None:
    global line, path
    line = namespace.get('line', line)
    path = namespace.get('path', path)
    _bind_deferred_defaults(namespace)


UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_SCHEMA_VERSION = 1
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_CONTROL_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_archive"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_control_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_request"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_APPROVAL_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_change_approval"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_RESET_PROOF_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_reset_proof"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_LIFECYCLE_REPORT_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_lifecycle_report"
RESET_ACTION = "reset_receiver_acceptance_signoff"
RESET_CHANGE_TYPE = "reset_receiver_acceptance_signoff"
FIXED_ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "state.json",
    "request-index.json",
    "reset-index.json",
    "generation.json",
    "lifecycle.json",
    "events.jsonl",
}




def _generation_checks(
    generations: dict[int, DomainDocument],
    current_generation: DomainDocument,
    state: DomainDocument,
    resets: dict[str, DomainDocument],
) -> list[DomainDocument]:
    current_number = _as_int(current_generation.get("generation"))
    proofs_by_previous = {
        _as_int(proof.get("previous_generation")): proof
        for proof in (bundle.get("proof") or {} for bundle in resets.values())
        if _as_int(proof.get("previous_generation")) is not None
    }
    expected = set(proofs_by_previous)
    if current_number is not None:
        expected.add(current_number)
    checks: list[DomainDocument] = [
        _check(
            "urpcccacc_generation_set",
            set(generations) == expected,
            "Generation sidecars cover every historical reset generation and the current generation.",
            {"expected": sorted(expected), "actual": sorted(generations)},
        )
    ]
    current_acceptance = _as_document(state.get("current_acceptance"))
    for generation, bundle in sorted(generations.items()):
        for key, doc in bundle.items():
            checks.append(_check(f"urpcccacc_generation_{generation:06d}_{key}_integrity", _integrity_ok(doc), "Generation sidecar integrity is valid."))
            checks.append(_check(f"urpcccacc_generation_{generation:06d}_{key}_identity", _same_number(doc.get("generation"), generation), "Generation sidecar identity matches its path."))
        verification = bundle.get("verification_summary") or {}
        signoff = bundle.get("signoff_binding_summary") or {}
        source_doc = bundle.get("source_summary") or {}
        source = _as_document(source_doc.get("source"))
        expected_source = current_acceptance if generation == current_number else (proofs_by_previous.get(generation) or {}).get("source") or {}
        checks.extend(
            [
                _check(f"urpcccacc_generation_{generation:06d}_source", source == expected_source, "Generation source matches current or reset-time Receiver Acceptance evidence."),
                _check(f"urpcccacc_generation_{generation:06d}_signoff", _same_nonempty(signoff.get("signoff_hash"), expected_source.get("signoff_hash")), "Generation summary binds Receiver Acceptance signoff."),
                _check(f"urpcccacc_generation_{generation:06d}_signoff_binding", _same_nonempty(signoff.get("signoff_binding_hash"), expected_source.get("signoff_binding_hash")), "Generation summary binds Receiver Acceptance signoff proof."),
                _check(f"urpcccacc_generation_{generation:06d}_archive", _same_nonempty(verification.get("archive_zip_sha256"), expected_source.get("archive_zip_sha256")), "Generation summary binds Receiver Acceptance Archive."),
                _check(f"urpcccacc_generation_{generation:06d}_manifest", _same_nonempty(verification.get("archive_manifest_hash"), expected_source.get("archive_manifest_hash")), "Generation summary binds Receiver Acceptance manifest."),
                _check(f"urpcccacc_generation_{generation:06d}_verification", _same_nonempty(verification.get("verification_report_hash"), expected_source.get("verification_report_hash")), "Generation summary binds Receiver Acceptance verification report."),
            ]
        )
    return checks

def _current_generation_checks(
    generation: DomainDocument,
    state: DomainDocument,
    resets: dict[str, DomainDocument],
    events: list[DomainDocument],
) -> list[DomainDocument]:
    current_number = _as_int(generation.get("generation"))
    current_acceptance = _as_document(state.get("current_acceptance"))
    signed_event = next(
        (
            row
            for row in reversed(events)
            if row.get("event_type") in {"receiver_acceptance_signed", "successor_receiver_acceptance_signed"}
        ),
        {},
    )
    checks = [
        _check("urpcccacc_current_generation_package_type", generation.get("package_type") == "musicforge_unified_release_program_continuity_command_center_acceptance_generation", "Current generation package type is valid."),
        _check("urpcccacc_current_generation_status", generation.get("status") == "current_signed", "Current generation is signed."),
        _check("urpcccacc_current_generation_state", _same_number(current_number, current_acceptance.get("generation")), "Current generation matches current Receiver Acceptance state."),
        _check("urpcccacc_current_generation_event", _same_number(current_number, signed_event.get("generation")), "Current generation matches the latest signed lifecycle event."),
    ]
    if resets:
        latest = max(
            (bundle.get("proof") or {} for bundle in resets.values()),
            key=lambda proof: _as_int(proof.get("next_generation")) or -1,
        )
        checks.extend(
            [
                _check("urpcccacc_current_generation_reset_proof", generation.get("reset_proof_hash") == latest.get("integrity_hash"), "Current generation binds the latest reset proof."),
                _check("urpcccacc_current_generation_previous", _same_number(generation.get("previous_generation"), latest.get("previous_generation")), "Current generation preserves the previous generation."),
                _check("urpcccacc_current_generation_next", _same_number(current_number, latest.get("next_generation")), "Current generation follows the latest reset proof."),
                _check("urpcccacc_current_generation_successor_event", signed_event.get("event_type") == "successor_receiver_acceptance_signed" and signed_event.get("reset_proof_hash") == latest.get("integrity_hash"), "Successor lifecycle event binds the latest reset proof."),
            ]
        )
    return checks

def _document_binding_checks(manifest: DomainDocument, state: DomainDocument, request_index: DomainDocument, reset_index: DomainDocument, generation: DomainDocument, lifecycle: DomainDocument) -> list[DomainDocument]:
    source = _as_document(manifest.get("source"))
    docs = {
        "change_control_state_hash": state,
        "change_request_index_hash": request_index,
        "reset_proof_index_hash": reset_index,
        "current_generation_hash": generation,
        "lifecycle_report_hash": lifecycle,
    }
    return [_check(f"urpcccacc_manifest_{key}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}.") for key, doc in docs.items()]

def _current_acceptance_checks(state: DomainDocument, archive_path: Path | str | None, verification_report_path: Path | str | None, signoff_binding_path: Path | str | None, *, require: bool) -> list[DomainDocument]:
    if not require:
        return []
    if not archive_path:
        return [_check("urpcccacc_current_acceptance_required", False, "Current Command Center Receiver Acceptance Archive is required.")]
    if not verification_report_path:
        return [_check("urpcccacc_current_acceptance_report_required", False, "Current Command Center Receiver Acceptance verification report is required.")]
    if not signoff_binding_path:
        return [_check("urpcccacc_current_acceptance_binding_required", False, "Current Command Center Receiver Acceptance signoff binding is required.")]
    archive = Path(archive_path)
    report_path = Path(verification_report_path)
    binding_path = Path(signoff_binding_path)
    checks = [
        _check("urpcccacc_current_acceptance_exists", archive.exists() and archive.is_file(), "Current Command Center Receiver Acceptance Archive exists."),
        _check("urpcccacc_current_acceptance_report_exists", report_path.exists() and report_path.is_file(), "Current Command Center Receiver Acceptance verification report exists."),
        _check("urpcccacc_current_acceptance_binding_exists", binding_path.exists() and binding_path.is_file(), "Current Command Center Receiver Acceptance signoff binding exists."),
    ]
    if _has_blocking_failures(checks):
        return checks
    external = read_json(report_path)
    external_binding = read_json(binding_path)
    runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
        archive,
        strict=True,
        require_signed=False,
    )
    current = _as_document(state.get("current_acceptance"))
    checks.extend(
        [
            _check("urpcccacc_current_acceptance_report_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, "Current Acceptance verification package type is valid."),
            _check("urpcccacc_current_acceptance_report_integrity", _integrity_ok(external), "Current Acceptance verification report integrity is valid."),
            _check("urpcccacc_current_acceptance_binding_integrity", _integrity_ok(external_binding), "Current Acceptance signoff binding integrity is valid."),
            _check("urpcccacc_current_acceptance_runtime_passed", runtime.get("status") == "passed", "Current Acceptance runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urpcccacc_current_acceptance_report_passed", external.get("status") == "passed", "Current Acceptance external verification passed."),
            _check("urpcccacc_current_acceptance_zip_sha256", current.get("archive_zip_sha256") == external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(archive), "Current Acceptance ZIP hash matches state, report, and runtime."),
            _check("urpcccacc_current_acceptance_manifest_hash", current.get("archive_manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Current Acceptance manifest hash matches state, report, and runtime."),
            _check("urpcccacc_current_acceptance_verification_hash", current.get("verification_report_hash") == external.get("integrity_hash"), "Current Acceptance verification hash matches state."),
            _check("urpcccacc_current_acceptance_signoff_binding", current.get("signoff_binding_hash") == external_binding.get("integrity_hash"), "Current Acceptance state binds external signoff proof."),
            _check("urpcccacc_current_acceptance_signoff", current.get("signoff_hash") == external_binding.get("signoff_hash"), "Current Acceptance state binds current signoff."),
        ]
    )
    return checks

def command_center_acceptance_change_previous_evidence_checks(
    resets: dict[str, DomainDocument],
    root_value: Path | str | None,
    *,
    require: bool,
) -> list[DomainDocument]:
    if not resets:
        return []
    if not root_value:
        return [_check("urpcccacc_previous_acceptance_root_required", not require, "Historical Receiver Acceptance evidence root is required for reset proof verification.")]
    root = Path(root_value)
    checks: list[DomainDocument] = [
        _check("urpcccacc_previous_acceptance_root_exists", root.is_dir(), "Historical Receiver Acceptance evidence root exists.")
    ]
    if not root.is_dir():
        return checks
    for reset_id, bundle in sorted(resets.items()):
        proof = bundle.get("proof") or {}
        generation = int(proof.get("previous_generation") or 0)
        snapshot = root / f"gen-{generation:06d}" / "acceptance-snapshot"
        archive_path = snapshot / "receiver-acceptance-archive.zip"
        report_path = snapshot / "receiver-acceptance-verification-report.json"
        binding_path = snapshot / "receiver-acceptance-signoff-binding-summary.json"
        signoff_path = snapshot / "receiver-acceptance-signoff.json"
        history_path = snapshot / "receiver-acceptance-history.jsonl"
        prefix = f"urpcccacc_previous_{_safe_check_key(reset_id)}"
        required_paths = (archive_path, report_path, binding_path, signoff_path, history_path)
        checks.append(_check(f"{prefix}_files", all(path.is_file() for path in required_paths), "Historical Receiver Acceptance snapshot is complete."))
        if not all(path.is_file() for path in required_paths):
            continue
        report = read_json(report_path)
        binding = read_json(binding_path)
        signoff = read_json(signoff_path)
        runtime = verify_unified_release_program_continuity_command_center_acceptance_package(
            archive_path,
            strict=True,
            require_signed=False,
        )
        try:
            history = _parse_jsonl(history_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            history = []
        history_event = next(
            (
                row
                for row in reversed(history)
                if row.get("event_type") == "receiver_acceptance_signoff_created"
                and row.get("signoff_hash") == signoff.get("integrity_hash")
            ),
            {},
        )
        checks.extend(
            [
                _check(f"{prefix}_runtime", runtime.get("status") == "passed", "Historical Receiver Acceptance archive runtime verification passed.", {"blockers": runtime.get("blockers") or []}),
                _check(f"{prefix}_report_type", report.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, "Historical verification package type is valid."),
                _check(f"{prefix}_report_integrity", _integrity_ok(report) and report.get("status") == "passed", "Historical verification report is valid and passed."),
                _check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Historical signoff binding integrity is valid."),
                _check(f"{prefix}_signoff_integrity", _integrity_ok(signoff), "Historical signoff integrity is valid."),
                _check(f"{prefix}_archive_hash", proof.get("previous_archive_zip_sha256") == _sha256_path(archive_path) == report.get("zip_sha256") == runtime.get("zip_sha256"), "Reset proof binds historical archive ZIP."),
                _check(f"{prefix}_manifest_hash", proof.get("previous_archive_manifest_hash") == report.get("manifest_hash") == runtime.get("manifest_hash"), "Reset proof binds historical archive manifest."),
                _check(f"{prefix}_verification_hash", proof.get("previous_verification_report_hash") == report.get("integrity_hash"), "Reset proof binds historical verification report."),
                _check(f"{prefix}_signoff_hash", proof.get("previous_signoff_hash") == signoff.get("integrity_hash") == binding.get("signoff_hash"), "Reset proof binds historical signoff."),
                _check(f"{prefix}_binding_hash", proof.get("previous_signoff_binding_hash") == binding.get("integrity_hash"), "Reset proof binds historical signoff binding."),
                _check(f"{prefix}_history_event", proof.get("previous_signoff_history_event_hash") == history_event.get("event_hash") == binding.get("history_event_hash"), "Reset proof binds historical signoff history event."),
            ]
        )
    return checks

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, name_set: set[str], expected_entries: set[str]) -> list[DomainDocument]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path") or "") for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check("urpcccacc_manifest_files_exact", file_paths == expected_files, "Manifest files match archive layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpcccacc_manifest_entries_exact", name_set == expected_entries, "Manifest entries match fixed/patterned layout.", {"missing": sorted(expected_entries - name_set), "extra": sorted(name_set - expected_entries)}),
        _check("urpcccacc_manifest_zip_filename", (manifest.get("zip") or {}).get("filename") == "cc-archive.zip", "Manifest ZIP filename is canonical."),
        _check("urpcccacc_manifest_zip_entries", sorted((manifest.get("zip") or {}).get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists."))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."))
        checks.append(_check(f"urpcccacc_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."))
    return checks

def _history_checks(rows: list[DomainDocument]) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    previous = ""
    for index, row in enumerate(rows, start=1):
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in {**row, "payload_hash": expected_payload}.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpcccacc_history_{index:03d}_previous", row.get("previous_event_hash") == previous, "History previous hash matches."),
                _check(f"urpcccacc_history_{index:03d}_payload", row.get("payload_hash") == expected_payload, "History payload hash matches."),
                _check(f"urpcccacc_history_{index:03d}_event", row.get("event_hash") == expected_event, "History event hash matches."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks

def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    return archive_redaction_check(archive, names, check_id="urpcccacc_redaction_scan")

def _finish(checks: list[DomainDocument], summary: DomainDocument, extra: DomainDocument | None = None) -> DomainDocument:
    if extra:
        checks.append(extra)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
    )

def _same_nonempty(*values: object) -> bool:
    normalized = [str(value) for value in values if value not in {None, ""}]
    return len(normalized) == len(values) and len(set(normalized)) == 1

def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _same_number(*values: object) -> bool:
    normalized = [_as_int(value) for value in values]
    return all(value is not None for value in normalized) and len(set(normalized)) == 1

def _next_generation_ok(previous: object, next_generation: object) -> bool:
    previous_int = _as_int(previous)
    next_int = _as_int(next_generation)
    return previous_int is not None and next_int == previous_int + 1

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _parse_jsonl(text: str) -> list[DomainDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]

def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"

def _has_blocking_failures(checks: list[DomainDocument]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)
