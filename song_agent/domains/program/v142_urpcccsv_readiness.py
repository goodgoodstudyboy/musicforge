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
    integrity_hash as _integrity_hash,
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
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package

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

field = _make_deferred_global('field')
line = _make_deferred_global('line')
verify_unified_release_program_continuity_command_center_signoff_package = _make_deferred_global('verify_unified_release_program_continuity_command_center_signoff_package')

def bind_globals(namespace: dict[str, object]) -> None:
    global field, line, verify_unified_release_program_continuity_command_center_signoff_package
    field = namespace.get('field', field)
    line = namespace.get('line', line)
    verify_unified_release_program_continuity_command_center_signoff_package = namespace.get('verify_unified_release_program_continuity_command_center_signoff_package', verify_unified_release_program_continuity_command_center_signoff_package)
    _bind_deferred_defaults(namespace)


COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_signoff_archive"
)
COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_signoff_archive_verification"
)
COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_final_handoff"
)
COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE = (
    "musicforge_unified_release_program_continuity_command_center_final_handoff_verification"
)
COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION = 1
ARCHIVE_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "command-center-signoff.json",
    "command-center-signoff-binding-summary.json",
    "command-center-signoff-history.jsonl",
    "command-center-signoff-policy.json",
    "command-center-signoff-state.json",
    "command-center-fingerprint-summary.json",
    "command-center-verification-summary.json",
    "external-evidence-manifest-summary.json",
    "final-handoff-checklist.json",
}
HANDOFF_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "final-handoff-summary.json",
    "receiver-checklist.json",
    "archive-verification-summary.json",
    "signoff-binding-summary.json",
}
_SOURCE_FIELDS = (
    "command_center_zip_sha256",
    "command_center_zip_size_bytes",
    "command_center_manifest_hash",
    "command_center_verification_report_hash",
    "external_evidence_manifest_hash",
    "current_generation",
    "current_generation_hash",
    "acceptance_signoff_hash",
    "acceptance_history_event_hash",
)




def _external_archive_checks(
    archive_zip_value: Path | str | None,
    report_value: Path | str | None,
    binding_value: Path | str | None,
    command_center_zip_value: Path | str | None,
    command_center_report_value: Path | str | None,
    evidence_value: Path | str | None,
    packaged_summary: DomainDocument,
) -> list[DomainDocument]:
    if not archive_zip_value or not report_value or not binding_value:
        return [_check("urpccch_external_archive_required", False, "External Archive ZIP, verification report, and signoff binding are required.")]
    archive_path, report_path = Path(archive_zip_value), Path(report_value)
    checks = [
        _check("urpccch_external_archive_exists", archive_path.is_file(), "External Archive ZIP exists."),
        _check("urpccch_external_archive_report_exists", report_path.is_file(), "External Archive verification report exists."),
    ]
    if _has_blockers(checks):
        return checks
    external = read_json(report_path)
    runtime = verify_unified_release_program_continuity_command_center_signoff_package(
        archive_path,
        strict=True,
        require_signed=True,
        signoff_binding_path=binding_value,
        command_center_zip_path=command_center_zip_value,
        command_center_verification_report_path=command_center_report_value,
        command_center_external_evidence_manifest_path=evidence_value,
    )
    checks.extend(
        [
            _check("urpccch_external_archive_report_integrity", _integrity_ok(external), "External Archive verification report integrity is valid."),
            _check("urpccch_external_archive_report_package_type", external.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "External Archive verification report package type is valid."),
            _check("urpccch_external_archive_report_status", external.get("status") == "passed", "External Archive verification report passed."),
            _check("urpccch_external_archive_runtime", runtime.get("status") == "passed", "External Archive runtime verification passed.", {"blockers": runtime.get("blockers") or []}),
            _check("urpccch_external_archive_zip_binding", packaged_summary.get("zip_sha256") == external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(archive_path), "Handoff binds current Archive ZIP."),
            _check("urpccch_external_archive_manifest_binding", packaged_summary.get("manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Handoff binds current Archive manifest."),
            _check("urpccch_external_archive_verification_binding", packaged_summary.get("verification_report_hash") == external.get("integrity_hash"), "Handoff binds external Archive verification report."),
        ]
    )
    return checks

def _source_projection(value: DomainDocument) -> DomainDocument:
    return {field: value.get(field) for field in _SOURCE_FIELDS}

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, required: set[str], prefix: str) -> list[DomainDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = required - {"manifest.json"}
    checks = [_check(f"{prefix}_manifest_files_exact", declared == expected, "Manifest files match fixed package entries.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)})]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in expected:
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}", row.get("sha256") == _sha256_bytes(data) and int(row.get("size_bytes") or -1) == len(data), "Manifest file hash and size match ZIP entry."))
    return checks

def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> DomainDocument:
    return archive_redaction_check(archive, names, check_id=check_id)

def _finish_archive(checks: list[DomainDocument], summary: DomainDocument, *extra: DomainDocument) -> DomainDocument:
    return _finish(checks, summary, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, *extra)

def _finish_handoff(checks: list[DomainDocument], summary: DomainDocument, *extra: DomainDocument) -> DomainDocument:
    return _finish(checks, summary, COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, *extra)

def _finish(checks: list[DomainDocument], summary: DomainDocument, package_type: str, *extra: DomainDocument) -> DomainDocument:
    checks.extend(extra)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
    )

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _parse_jsonl(value: str) -> list[DomainDocument]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]

def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"

def _has_blockers(checks: list[DomainDocument]) -> bool:
    return any(row.get("status") == "failed" for row in checks)
