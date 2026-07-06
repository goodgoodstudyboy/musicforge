from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train_handoff_verifier import (
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    verify_unified_command_center_release_train_handoff_package,
)


UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE = "musicforge_unified_release_program"
UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_verification"
UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE = "musicforge_unified_release_program_external_evidence_manifest"
UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION = 1

BASE_REQUIRED_ENTRIES = {
    "manifest.json",
    "file-index.json",
    "README.txt",
    "program-report.json",
    "train-items.json",
    "external-evidence-manifest.json",
    "dependency-graph.json",
    "readiness-matrix.json",
    "risk-register.json",
    "exception-register.json",
    "gap-plan.json",
    "recipient-guide.md",
    "program-history.jsonl",
}
SIGNED_ENTRIES = {"program-signoff.json", "program-signoff-binding-summary.json"}
REQUIRED_ENTRIES = BASE_REQUIRED_ENTRIES | SIGNED_ENTRIES

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_unified_release_program_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_signed: bool = False,
    external_evidence_manifest_path: Path | str | None = None,
    program_signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("urp_zip_exists", False, "Unified Release Program ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urp_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            signed_present = bool(SIGNED_ENTRIES & name_set)
            expected_entries = REQUIRED_ENTRIES if (require_signed or signed_present) else BASE_REQUIRED_ENTRIES
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - expected_entries)
            missing = sorted(expected_entries - name_set)
            checks.extend(
                [
                    _check("urp_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urp_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urp_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urp_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urp_no_nested_zip", not nested, "Program ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("urp_allowed_entries", not extra, "Program ZIP contains only fixed entries.", {"extra": extra}),
                    _check("urp_required_entries", not missing, "Program ZIP contains required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            file_index = _read_json_entry(archive, "file-index.json")
            report = _read_json_entry(archive, "program-report.json")
            items = _read_json_entry(archive, "train-items.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            dependency = _read_json_entry(archive, "dependency-graph.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            risk = _read_json_entry(archive, "risk-register.json")
            exceptions = _read_json_entry(archive, "exception-register.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            history = _parse_jsonl(archive.read("program-history.jsonl").decode("utf-8"))
            signoff = _read_json_entry(archive, "program-signoff.json") if "program-signoff.json" in name_set else {}
            binding = _read_json_entry(archive, "program-signoff-binding-summary.json") if "program-signoff-binding-summary.json" in name_set else {}
            summary.update(
                {
                    "program_id": report.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "readiness": report.get("summary", {}).get("readiness"),
                    "signed": signoff.get("status") == "signed",
                    "signoff_hash": signoff.get("integrity_hash"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set, expected_entries))
            checks.extend(_file_index_checks(file_index, expected_entries - {"manifest.json", "file-index.json"}))
            checks.extend(
                [
                    _check("urp_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urp_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("urp_manifest_integrity", manifest),
                ("urp_file_index_integrity", file_index),
                ("urp_report_integrity", report),
                ("urp_items_integrity", items),
                ("urp_external_manifest_integrity", external_manifest),
                ("urp_dependency_integrity", dependency),
                ("urp_readiness_integrity", readiness),
                ("urp_risk_integrity", risk),
                ("urp_exception_integrity", exceptions),
                ("urp_gap_plan_integrity", gap_plan),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            if signoff:
                checks.append(_check("urp_signoff_integrity", _integrity_ok(signoff), "Program signoff integrity hash is valid."))
            if binding:
                checks.append(_check("urp_signoff_binding_integrity", _integrity_ok(binding), "Program signoff binding integrity hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, items, external_manifest, dependency, readiness, risk, exceptions, gap_plan, signoff, binding))
            checks.extend(_dependency_semantics_checks(dependency, readiness, report))
            checks.extend(_history_checks(history, signoff))
            checks.extend(_signoff_binding_checks(binding, signoff, history, report, items, external_manifest, dependency, readiness, risk, exceptions, require=require_signed))
            checks.extend(_external_signoff_binding_checks(program_signoff_binding_path, binding, signoff, history, report, items, external_manifest, dependency, readiness, risk, exceptions, require=require_signed))
            checks.extend(_external_manifest_checks(external_evidence_manifest_path, items, require=require_current))
            checks.extend(_external_handoff_checks(external_evidence_manifest_path, items, require=require_current))
            checks.append(_redaction_check(archive, names))
            if require_signed:
                checks.append(_check("urp_require_signed", signoff.get("status") == "signed", "Program is signed."))
            if require_current:
                checks.append(_check("urp_require_ready", report.get("status") in {"ready", "signed"} and readiness.get("summary", {}).get("status") == "ready", "Program readiness is current and ready."))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urp_zip_readable", False, "Program ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_manifest_checks(path: Path | str | None, items: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not path:
        if require:
            return [_check("urp_external_evidence_manifest_required", False, "External evidence manifest is required.")]
        return checks
    manifest_path = Path(path)
    checks.append(_check("urp_external_evidence_manifest_exists", manifest_path.exists() and manifest_path.is_file(), "External evidence manifest exists."))
    if not manifest_path.exists() or not manifest_path.is_file():
        return checks
    external = _read_json_file(manifest_path)
    checks.extend(
        [
            _check("urp_external_evidence_manifest_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, "External evidence manifest package type is valid."),
            _check("urp_external_evidence_manifest_integrity", _integrity_ok(external), "External evidence manifest integrity hash is valid."),
        ]
    )
    expected_rows = [row for row in items.get("items", []) if isinstance(row, dict)]
    external_rows = [row for row in external.get("items", []) if isinstance(row, dict)]
    expected_keys = {_item_key(row): row for row in expected_rows}
    external_keys = {_item_key(row): row for row in external_rows}
    missing = sorted(set(expected_keys) - set(external_keys))
    extra = sorted(set(external_keys) - set(expected_keys))
    checks.append(_check("urp_external_evidence_manifest_identity", not missing and not extra, "External evidence manifest matches item_id + train_id + handoff_id.", {"missing": missing, "extra": extra}))
    for key, expected in expected_keys.items():
        external_row = external_keys.get(key)
        if not external_row:
            continue
        checks.extend(_external_row_fingerprint_checks(key, expected, external_row))
    return checks


def _external_handoff_checks(path: Path | str | None, items: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not path:
        return []
    external = _read_json_file(Path(path))
    external_by_key = {_item_key(row): row for row in external.get("items", []) if isinstance(row, dict)}
    checks: list[dict[str, Any]] = []
    for item in items.get("items", []):
        key = _item_key(item)
        external_row = external_by_key.get(key)
        if not external_row:
            continue
        checks.extend(_runtime_handoff_checks(key, item, external_row, require=require))
    return checks


def _external_row_fingerprint_checks(key: str, expected: dict[str, Any], external_row: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    prefix = f"urp_external_evidence_{_safe_check_key(key)}"
    fp = expected.get("fingerprint") if isinstance(expected.get("fingerprint"), dict) else {}
    for field in ("handoff_zip_sha256", "handoff_manifest_hash", "handoff_verification_report_hash", "handoff_signoff_binding_hash"):
        checks.append(_check(f"{prefix}_{field}", not fp.get(field) or fp.get(field) == external_row.get(field), f"External evidence manifest {field} matches Program item.", {"key": key}))
    return checks


def _runtime_handoff_checks(key: str, expected: dict[str, Any], external_row: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    prefix = f"urp_handoff_runtime_{_safe_check_key(key)}"
    zip_path = Path(str(external_row.get("handoff_zip") or external_row.get("handoff_zip_path") or ""))
    report_path = Path(str(external_row.get("handoff_verification_report") or external_row.get("handoff_verification_report_path") or ""))
    binding_path = Path(str(external_row.get("handoff_signoff_binding") or external_row.get("handoff_signoff_binding_path") or ""))
    accepted_dir_raw = external_row.get("accepted_evidence_dir") or external_row.get("accepted_evidence_directory")
    accepted_dir = Path(str(accepted_dir_raw)) if accepted_dir_raw else None
    checks = [
        _check(f"{prefix}_zip_exists", zip_path.exists() and zip_path.is_file(), "Handoff ZIP exists.", {"key": key}),
        _check(f"{prefix}_verification_exists", report_path.exists() and report_path.is_file(), "Handoff verification report exists.", {"key": key}),
        _check(f"{prefix}_binding_exists", binding_path.exists() and binding_path.is_file(), "Handoff signoff binding exists.", {"key": key}),
    ]
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = _read_json_file(report_path)
    runtime = verify_unified_command_center_release_train_handoff_package(
        zip_path,
        strict=True,
        require_signed=True,
        require_accepted=bool(expected.get("require_accepted") or False),
        handoff_signoff_binding_path=binding_path,
        accepted_evidence_dir=accepted_dir,
    )
    external_zip_sha256 = _verification_zip_sha256(external_report)
    external_manifest_hash = _verification_manifest_hash(external_report)
    runtime_zip_sha256 = _verification_zip_sha256(runtime)
    runtime_manifest_hash = _verification_manifest_hash(runtime)
    runtime_ok = (
        runtime.get("status") == "passed"
        and external_report.get("status") == "passed"
        and external_report.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE
        and _integrity_ok(external_report)
        and external_zip_sha256 == runtime_zip_sha256 == _sha256_path(zip_path)
        and external_manifest_hash == runtime_manifest_hash
    )
    fp = expected.get("fingerprint") if isinstance(expected.get("fingerprint"), dict) else {}
    checks.extend(
        [
            _check(f"{prefix}_package_type", external_report.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE, "Handoff verification package type is valid.", {"key": key}),
            _check(f"{prefix}_integrity", _integrity_ok(external_report), "Handoff verification report integrity hash is valid.", {"key": key}),
            _check(f"{prefix}_status", external_report.get("status") == "passed" and runtime.get("status") == "passed", "Handoff runtime and external verification passed.", {"key": key, "external_status": external_report.get("status"), "runtime_status": runtime.get("status")}),
            _check(f"{prefix}_zip_sha256", external_zip_sha256 == runtime_zip_sha256 == _sha256_path(zip_path) == fp.get("handoff_zip_sha256"), "Handoff ZIP hash matches Program fingerprint, runtime, and report.", {"key": key}),
            _check(f"{prefix}_manifest_hash", external_manifest_hash == runtime_manifest_hash == fp.get("handoff_manifest_hash"), "Handoff manifest hash matches Program fingerprint, runtime, and report.", {"key": key}),
            _check(f"{prefix}_verification_report_hash", _integrity_hash(external_report) == fp.get("handoff_verification_report_hash"), "Handoff verification report hash matches Program fingerprint.", {"key": key}),
            _check(f"{prefix}_signoff_binding_hash", _sha256_or_integrity(binding_path) == fp.get("handoff_signoff_binding_hash"), "Handoff signoff binding hash matches Program fingerprint.", {"key": key}),
            _check(f"{prefix}", runtime_ok, "Handoff external evidence is current and verified.", {"key": key, "runtime_blockers": runtime.get("blockers", [])}),
        ]
    )
    return checks


def _document_binding_checks(
    manifest: dict[str, Any],
    report: dict[str, Any],
    items: dict[str, Any],
    external_manifest: dict[str, Any],
    dependency: dict[str, Any],
    readiness: dict[str, Any],
    risk: dict[str, Any],
    exceptions: dict[str, Any],
    gap_plan: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    source_hash = report.get("source_hash")
    checks = [
        _check("urp_source_hash_consistent", manifest.get("source_hash") == source_hash == readiness.get("source_hash") == risk.get("source_hash") == gap_plan.get("source_hash"), "Source hash is consistent across Program documents."),
        _check("urp_manifest_report_binding", source.get("program_report_hash") == report.get("integrity_hash"), "Manifest binds Program report."),
        _check("urp_manifest_items_binding", source.get("train_items_hash") == items.get("integrity_hash"), "Manifest binds train items."),
        _check("urp_manifest_external_manifest_binding", source.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Manifest binds external evidence manifest."),
        _check("urp_manifest_dependency_binding", source.get("dependency_graph_hash") == dependency.get("integrity_hash"), "Manifest binds dependency graph."),
        _check("urp_manifest_readiness_binding", source.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Manifest binds readiness matrix."),
        _check("urp_manifest_risk_binding", source.get("risk_register_hash") == risk.get("integrity_hash"), "Manifest binds risk register."),
        _check("urp_manifest_exception_binding", source.get("exception_register_hash") == exceptions.get("integrity_hash"), "Manifest binds exception register."),
        _check("urp_manifest_gap_binding", source.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Manifest binds gap plan."),
    ]
    if signoff:
        checks.append(_check("urp_manifest_signoff_binding", source.get("program_signoff_hash") == signoff.get("integrity_hash"), "Manifest binds Program signoff."))
    if binding:
        checks.append(_check("urp_manifest_signoff_sidecar_binding", source.get("program_signoff_binding_hash") == binding.get("integrity_hash"), "Manifest binds Program signoff binding sidecar."))
    return checks


def _dependency_semantics_checks(dependency: dict[str, Any], readiness: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in readiness.get("rows", []) if isinstance(row, dict)]
    row_status = {str(row.get("item_id")): str(row.get("status")) for row in rows if row.get("item_id")}
    edges = [row for row in dependency.get("edges", []) if isinstance(row, dict)]
    cycle = _has_cycle([str(row.get("from") or "") for row in edges], [str(row.get("to") or "") for row in edges])
    blocked = []
    for row in edges:
        upstream = str(row.get("from") or "")
        downstream = str(row.get("to") or "")
        if row_status.get(upstream) not in {"passed", "ready"}:
            blocked.append({"from": upstream, "to": downstream, "upstream_status": row_status.get(upstream)})
    expected = "ready" if not cycle and not blocked and int(readiness.get("summary", {}).get("critical_failed") or 0) == 0 else "blocked"
    return [
        _check("urp_dependency_graph_acyclic", not cycle, "Dependency graph is acyclic."),
        _check("urp_dependency_blockers_match", int(dependency.get("summary", {}).get("blocked_dependency_count") or 0) == len(blocked), "Dependency blocker count is derived from readiness.", {"blocked_dependencies": blocked}),
        _check("urp_report_status_semantics", report.get("status") == expected == readiness.get("summary", {}).get("status"), "Program status matches readiness and dependency graph.", {"expected": expected, "actual": report.get("status")}),
    ]


def _history_checks(history: list[dict[str, Any]], signoff: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    signoff_event: dict[str, Any] | None = None
    for index, event in enumerate(history):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"urp_history_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History event payload hash is valid."))
        checks.append(_check(f"urp_history_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"urp_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
        if event.get("event_type") == "unified_release_program_signoff_created":
            signoff_event = event
    if signoff:
        checks.append(_check("urp_history_has_signoff_event", bool(signoff_event), "History contains Program signoff event."))
    if signoff_event:
        checks.extend(
            [
                _check("urp_history_signoff_hash", signoff_event.get("signoff_hash") == signoff.get("integrity_hash"), "History signoff hash matches signoff."),
                _check("urp_history_signed_by", signoff_event.get("signed_by") == signoff.get("signed_by"), "History signed_by matches signoff."),
                _check("urp_history_report_hash", signoff_event.get("program_report_hash") == signoff.get("program_report_hash"), "History report hash matches signoff."),
            ]
        )
    return checks


def _signoff_binding_checks(
    binding: dict[str, Any],
    signoff: dict[str, Any],
    history: list[dict[str, Any]],
    report: dict[str, Any],
    items: dict[str, Any],
    external_manifest: dict[str, Any],
    dependency: dict[str, Any],
    readiness: dict[str, Any],
    risk: dict[str, Any],
    exceptions: dict[str, Any],
    *,
    require: bool,
) -> list[dict[str, Any]]:
    if not binding:
        return [_check("urp_signoff_binding_required", not require, "Program signoff binding is present when required.")]
    signoff_event = next((row for row in reversed(history) if row.get("event_type") == "unified_release_program_signoff_created"), {})
    checks = [
        _check("urp_signoff_binding_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("urp_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("urp_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("urp_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("urp_signoff_binding_history_event", binding.get("latest_history_event_hash") == signoff_event.get("event_hash"), "Signoff binding matches latest signoff history event."),
        _check("urp_signoff_binding_report_hash", binding.get("program_report_hash") == report.get("integrity_hash") == signoff.get("program_report_hash"), "Binding Program report hash matches."),
        _check("urp_signoff_binding_items_hash", binding.get("train_items_hash") == items.get("integrity_hash") == signoff.get("train_items_hash"), "Binding train items hash matches."),
        _check("urp_signoff_binding_external_manifest_hash", binding.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash") == signoff.get("external_evidence_manifest_hash"), "Binding external evidence manifest hash matches."),
        _check("urp_signoff_binding_dependency_hash", binding.get("dependency_graph_hash") == dependency.get("integrity_hash") == signoff.get("dependency_graph_hash"), "Binding dependency graph hash matches."),
        _check("urp_signoff_binding_readiness_hash", binding.get("readiness_matrix_hash") == readiness.get("integrity_hash") == signoff.get("readiness_matrix_hash"), "Binding readiness matrix hash matches."),
        _check("urp_signoff_binding_risk_hash", binding.get("risk_register_hash") == risk.get("integrity_hash") == signoff.get("risk_register_hash"), "Binding risk register hash matches."),
        _check("urp_signoff_binding_exception_hash", binding.get("exception_register_hash") == exceptions.get("integrity_hash") == signoff.get("exception_register_hash"), "Binding exception register hash matches."),
    ]
    return checks


def _external_signoff_binding_checks(
    path: Path | str | None,
    binding: dict[str, Any],
    signoff: dict[str, Any],
    history: list[dict[str, Any]],
    report: dict[str, Any],
    items: dict[str, Any],
    external_manifest: dict[str, Any],
    dependency: dict[str, Any],
    readiness: dict[str, Any],
    risk: dict[str, Any],
    exceptions: dict[str, Any],
    *,
    require: bool,
) -> list[dict[str, Any]]:
    if not path:
        if require:
            return [_check("urp_external_signoff_binding_required", False, "External Program signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    checks = [_check("urp_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External Program signoff binding proof exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = _read_json_file(binding_path)
    checks.extend(
        [
            _check("urp_external_signoff_binding_integrity", _integrity_ok(external), "External Program signoff binding integrity hash is valid."),
            _check("urp_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External Program signoff binding matches ZIP sidecar hash."),
            _check("urp_external_signoff_binding_signed_by", external.get("signed_by") == binding.get("signed_by") == signoff.get("signed_by"), "External Program signoff binding matches signed_by."),
            _check("urp_external_signoff_binding_role", external.get("role") == binding.get("role") == signoff.get("role"), "External Program signoff binding matches role."),
            _check("urp_external_signoff_binding_reason", external.get("reason") == binding.get("reason") == signoff.get("reason"), "External Program signoff binding matches reason."),
        ]
    )
    checks.extend(_signoff_binding_checks(external, signoff, history, report, items, external_manifest, dependency, readiness, risk, exceptions, require=require))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str], expected_entries: set[str]) -> list[dict[str, Any]]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path")) for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check("urp_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed Program layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urp_manifest_no_zip_entry_spoof", set(manifest.get("zip", {}).get("entries") or []) <= name_set, "Manifest ZIP entries do not spoof extra paths."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"urp_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urp_manifest_file_{_safe_check_key(rel)}_hash", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks


def _file_index_checks(file_index: dict[str, Any], expected_files: set[str]) -> list[dict[str, Any]]:
    rows = [row for row in file_index.get("files", []) if isinstance(row, dict)]
    paths = {str(row.get("path")) for row in rows}
    return [
        _check("urp_file_index_package_type", file_index.get("package_type") == "musicforge_unified_release_program_file_index", "File index package type is valid."),
        _check("urp_file_index_files_exact", paths == expected_files, "File index matches fixed Program layout.", {"missing": sorted(expected_files - paths), "extra": sorted(paths - expected_files)}),
    ]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], first_check: dict[str, Any] | None = None) -> dict[str, Any]:
    if first_check is not None:
        checks.insert(0, first_check)
    failed = [check for check in checks if check.get("status") == "failed"]
    status = "failed" if failed else "passed"
    report = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE,
        "status": status,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "summary": summary,
        "checks": checks,
        "blockers": [check["check_id"] for check in failed],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {"check_id": check_id, "status": "passed" if passed else "failed", "message": message}
    if details:
        row["details"] = details
    return row


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path) -> dict[str, Any]:
    return read_json(path)


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_or_integrity(path: Path) -> str:
    try:
        doc = read_json(path)
        if isinstance(doc, dict) and doc.get("integrity_hash"):
            return str(doc.get("integrity_hash"))
    except Exception:
        pass
    return _sha256_path(path)


def _verification_zip_sha256(report: dict[str, Any]) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return report.get("zip_sha256") or summary.get("zip_sha256")


def _verification_manifest_hash(report: dict[str, Any]) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return report.get("manifest_hash") or summary.get("manifest_hash")


def _is_safe_entry(name: str) -> bool:
    if "\\" in name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    return bool(name) and not Path(name).is_absolute()


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    offenders = []
    for name in names:
        lowered = name.lower()
        if not lowered.endswith((".json", ".txt", ".md", ".html", ".jsonl")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                offenders.append(name)
                break
    return _check("urp_redaction_scan", not offenders, "Program package contains no obvious secrets or local paths.", {"offenders": sorted(set(offenders))})


def _item_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "train_id", "handoff_id"))


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _has_cycle(from_nodes: list[str], to_nodes: list[str]) -> bool:
    graph: dict[str, list[str]] = {}
    for source, target in zip(from_nodes, to_nodes):
        if source and target:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))
