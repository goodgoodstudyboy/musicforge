from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash


UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE = "musicforge_unified_command_center_release_train"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_verification"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_external_evidence_manifest"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION = 1

EXPECTED_EVIDENCE_PACKAGE_TYPES: dict[str, str] = {
    "ucc": "musicforge_unified_command_center_verification",
    "ucc_archive": "musicforge_unified_command_center_archive_verification",
    "handoff": "musicforge_final_handoff_pack_verification",
    "continuous_review": "musicforge_unified_command_center_continuous_review_verification",
    "evidence_review": "musicforge_unified_command_center_evidence_review_verification",
    "reviewer_decision_board": "musicforge_unified_command_center_reviewer_decision_board_verification",
}

REQUIRED_ENTRIES = {
    "manifest.json",
    "train.json",
    "train-source.json",
    "train-items.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "dependency-graph.json",
    "wave-plan.json",
    "go-no-go-report.json",
    "safe-runbook.json",
    "safe-runbook-result.json",
    "train-signoff.json",
    "train-signoff-binding-summary.json",
    "train-history.jsonl",
    "REVIEWER_GUIDE.md",
    "README.txt",
}

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


def verify_unified_command_center_release_train_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_go: bool = False,
    require_signed: bool = False,
    external_evidence_manifest_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_train_zip_exists", False, "Release Train ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_train_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.extend(
                [
                    _check("ucc_train_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("ucc_train_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("ucc_train_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("ucc_train_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("ucc_train_no_nested_zip", not nested, "Release Train ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("ucc_train_allowed_entries", not extra, "Release Train ZIP contains only fixed entries.", {"extra": extra}),
                    _check("ucc_train_required_entries", not missing, "Release Train ZIP contains all required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            train = _read_json_entry(archive, "train.json")
            source = _read_json_entry(archive, "train-source.json")
            items = _read_json_entry(archive, "train-items.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            dependency = _read_json_entry(archive, "dependency-graph.json")
            wave = _read_json_entry(archive, "wave-plan.json")
            report = _read_json_entry(archive, "go-no-go-report.json")
            runbook = _read_json_entry(archive, "safe-runbook.json")
            runbook_result = _read_json_entry(archive, "safe-runbook-result.json")
            signoff = _read_json_entry(archive, "train-signoff.json")
            binding = _read_json_entry(archive, "train-signoff-binding-summary.json")
            history = _parse_jsonl(archive.read("train-history.jsonl").decode("utf-8"))

            summary.update(
                {
                    "train_id": manifest.get("train_id") or train.get("train_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "signed": signoff.get("status") == "signed",
                    "signoff_hash": signoff.get("integrity_hash"),
                }
            )

            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.extend(
                [
                    _check("ucc_train_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("ucc_train_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("ucc_train_manifest_integrity", manifest),
                ("ucc_train_record_integrity", train),
                ("ucc_train_source_integrity", source),
                ("ucc_train_items_integrity", items),
                ("ucc_train_inventory_integrity", inventory),
                ("ucc_train_readiness_integrity", readiness),
                ("ucc_train_dependency_integrity", dependency),
                ("ucc_train_wave_integrity", wave),
                ("ucc_train_report_integrity", report),
                ("ucc_train_runbook_integrity", runbook),
                ("ucc_train_runbook_result_integrity", runbook_result),
                ("ucc_train_signoff_integrity", signoff),
                ("ucc_train_signoff_binding_integrity", binding),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, train, source, items, inventory, readiness, dependency, wave, report, runbook, runbook_result, signoff, binding))
            checks.extend(_dependency_semantics_checks(dependency, readiness, report))
            checks.extend(_history_checks(history, signoff))
            checks.extend(_signoff_binding_checks(binding, signoff, history, source, report, inventory, readiness))
            checks.extend(_external_signoff_binding_checks(signoff_binding_path, binding, signoff, history, source, report, inventory, readiness, require=require_signed))
            checks.extend(_external_evidence_manifest_checks(external_evidence_manifest_path, inventory, require=require_go or require_signed or strict))
            checks.append(_redaction_check(archive, names))
            if require_go:
                checks.append(_check("ucc_train_require_go", report.get("status") == "go" and readiness.get("overall_status") == "go", "Release Train is GO."))
            if require_signed:
                checks.append(_check("ucc_train_require_signed", signoff.get("status") == "signed", "Release Train is signed."))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_train_zip_readable", False, "Release Train ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_release_train_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_release_train_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_evidence_manifest_checks(path: Path | str | None, inventory: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not path:
        if require:
            return [_check("ucc_train_external_evidence_manifest_required", False, "External evidence manifest is required.")]
        return checks
    manifest_path = Path(path)
    checks.append(_check("ucc_train_external_evidence_manifest_exists", manifest_path.exists(), "External evidence manifest exists."))
    if not manifest_path.exists():
        return checks
    external = _read_json_file(manifest_path)
    checks.extend(
        [
            _check("ucc_train_external_evidence_manifest_package_type", external.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, "External evidence manifest package type is valid."),
            _check("ucc_train_external_evidence_manifest_integrity", _integrity_ok(external), "External evidence manifest integrity hash is valid."),
        ]
    )
    expected_rows = [row for row in inventory.get("items", []) if isinstance(row, dict)]
    external_rows = [row for row in external.get("items", []) if isinstance(row, dict)]
    expected_keys = {_evidence_key(row): row for row in expected_rows}
    external_keys = {_evidence_key(row): row for row in external_rows}
    missing = sorted(set(expected_keys) - set(external_keys))
    extra = sorted(set(external_keys) - set(expected_keys))
    checks.append(_check("ucc_train_external_evidence_manifest_identity", not missing and not extra, "External evidence manifest matches item_id + center_id + evidence_type.", {"missing": missing, "extra": extra}))
    for key, expected in expected_keys.items():
        external_row = external_keys.get(key)
        if not external_row:
            continue
        checks.extend(_external_row_checks(key, expected, external_row))
    return checks


def _external_row_checks(key: str, expected: dict[str, Any], external_row: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = "ucc_train_external_evidence_binding"
    checks: list[dict[str, Any]] = []
    zip_path = Path(str(external_row.get("zip_path") or ""))
    report_path = Path(str(external_row.get("verification_report_path") or ""))
    checks.append(_check(f"{prefix}_{_safe_check_key(key)}_zip_exists", zip_path.exists() and zip_path.is_file(), "External ZIP exists.", {"key": key}))
    checks.append(_check(f"{prefix}_{_safe_check_key(key)}_report_exists", report_path.exists() and report_path.is_file(), "External verification report exists.", {"key": key}))
    if any(check["status"] == "failed" for check in checks[-2:]):
        return checks
    report = _read_json_file(report_path)
    actual_zip_sha = _sha256_path(zip_path)
    actual_manifest_hash = _zip_manifest_hash(zip_path)
    evidence_type = str(expected.get("evidence_type") or "")
    expected_package_type = EXPECTED_EVIDENCE_PACKAGE_TYPES.get(evidence_type)
    row_ok = (
        expected.get("zip_sha256") == actual_zip_sha == _report_zip_sha(report)
        and expected.get("zip_size_bytes") == zip_path.stat().st_size
        and expected.get("manifest_hash") == actual_manifest_hash == _report_manifest_hash(report)
        and expected.get("verification_report_hash") == _integrity_hash(report)
        and expected.get("verification_status") == report.get("status") == "passed"
        and report.get("package_type") == expected_package_type
        and _integrity_ok(report)
    )
    checks.extend(
        [
            _check(f"{prefix}_{_safe_check_key(key)}_package_type", report.get("package_type") == expected_package_type, "External verification package type matches evidence type.", {"key": key, "package_type": report.get("package_type"), "expected": expected_package_type}),
            _check(f"{prefix}_{_safe_check_key(key)}_integrity", _integrity_ok(report), "External verification report integrity hash is valid.", {"key": key}),
            _check(f"{prefix}_{_safe_check_key(key)}_status", report.get("status") == "passed", "External verification report status is passed.", {"key": key, "status": report.get("status")}),
            _check(f"{prefix}_{_safe_check_key(key)}_zip_sha256", expected.get("zip_sha256") == actual_zip_sha == _report_zip_sha(report), "Evidence ZIP sha256 matches inventory and verification report.", {"key": key}),
            _check(f"{prefix}_{_safe_check_key(key)}_manifest_hash", expected.get("manifest_hash") == actual_manifest_hash == _report_manifest_hash(report), "Evidence manifest hash matches inventory and verification report.", {"key": key}),
            _check(f"{prefix}_{_safe_check_key(key)}_verification_hash", expected.get("verification_report_hash") == _integrity_hash(report), "Evidence verification report hash matches inventory.", {"key": key}),
            _check(f"{prefix}_{_safe_check_key(key)}", row_ok, "External evidence row fully matches Release Train inventory.", {"key": key}),
        ]
    )
    return checks


def _document_binding_checks(
    manifest: dict[str, Any],
    train: dict[str, Any],
    source: dict[str, Any],
    items: dict[str, Any],
    inventory: dict[str, Any],
    readiness: dict[str, Any],
    dependency: dict[str, Any],
    wave: dict[str, Any],
    report: dict[str, Any],
    runbook: dict[str, Any],
    runbook_result: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    source_hash = source.get("source_hash")
    checks = [
        _check("ucc_train_source_hash_manifest", manifest.get("source_hash") == source_hash == report.get("source_hash") == inventory.get("source_hash") == readiness.get("source_hash"), "Source hash is consistent across train documents."),
        _check("ucc_train_manifest_train_binding", manifest_source.get("train_hash") == train.get("integrity_hash"), "Manifest binds train record."),
        _check("ucc_train_manifest_source_binding", manifest_source.get("source_hash") == source.get("integrity_hash"), "Manifest binds source document."),
        _check("ucc_train_manifest_items_binding", manifest_source.get("items_hash") == items.get("integrity_hash"), "Manifest binds train items."),
        _check("ucc_train_manifest_inventory_binding", manifest_source.get("evidence_inventory_hash") == inventory.get("integrity_hash"), "Manifest binds evidence inventory."),
        _check("ucc_train_manifest_readiness_binding", manifest_source.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Manifest binds readiness matrix."),
        _check("ucc_train_manifest_dependency_binding", manifest_source.get("dependency_graph_hash") == dependency.get("integrity_hash"), "Manifest binds dependency graph."),
        _check("ucc_train_manifest_wave_binding", manifest_source.get("wave_plan_hash") == wave.get("integrity_hash"), "Manifest binds wave plan."),
        _check("ucc_train_manifest_report_binding", manifest_source.get("go_no_go_report_hash") == report.get("integrity_hash"), "Manifest binds Go/No-Go report."),
        _check("ucc_train_manifest_runbook_binding", manifest_source.get("safe_runbook_hash") == runbook.get("integrity_hash"), "Manifest binds safe runbook."),
        _check("ucc_train_manifest_runbook_result_binding", manifest_source.get("safe_runbook_result_hash") == runbook_result.get("integrity_hash"), "Manifest binds safe runbook result."),
        _check("ucc_train_manifest_signoff_binding", manifest_source.get("train_signoff_hash") == signoff.get("integrity_hash"), "Manifest binds train signoff."),
        _check("ucc_train_manifest_signoff_sidecar_binding", manifest_source.get("train_signoff_binding_hash") == binding.get("integrity_hash"), "Manifest binds signoff binding sidecar."),
    ]
    return checks


def _external_signoff_binding_checks(
    path: Path | str | None,
    binding: dict[str, Any],
    signoff: dict[str, Any],
    history: list[dict[str, Any]],
    source: dict[str, Any],
    report: dict[str, Any],
    inventory: dict[str, Any],
    readiness: dict[str, Any],
    *,
    require: bool,
) -> list[dict[str, Any]]:
    if not path:
        if require:
            return [_check("ucc_train_external_signoff_binding_required", False, "External train signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    checks = [_check("ucc_train_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External train signoff binding proof exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = _read_json_file(binding_path)
    checks.extend(
        [
            _check("ucc_train_external_signoff_binding_integrity", _integrity_ok(external), "External train signoff binding integrity hash is valid."),
            _check("ucc_train_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External signoff binding matches archive binding hash."),
            _check("ucc_train_external_signoff_binding_signed_by", external.get("signed_by") == binding.get("signed_by") == signoff.get("signed_by"), "External signoff binding matches signed_by."),
            _check("ucc_train_external_signoff_binding_role", external.get("role") == binding.get("role") == signoff.get("role"), "External signoff binding matches role."),
            _check("ucc_train_external_signoff_binding_reason", external.get("reason") == binding.get("reason") == signoff.get("reason"), "External signoff binding matches reason."),
            _check("ucc_train_external_signoff_binding_signed_at", external.get("signed_at") == binding.get("signed_at") == signoff.get("signed_at"), "External signoff binding matches signed_at."),
        ]
    )
    checks.extend(_signoff_binding_checks(external, signoff, history, source, report, inventory, readiness))
    return checks


def _dependency_semantics_checks(dependency: dict[str, Any], readiness: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    items = [row for row in readiness.get("items", []) if isinstance(row, dict)]
    item_status = {str(row.get("item_id")): str(row.get("status")) for row in items}
    edges = [row for row in dependency.get("edges", []) if isinstance(row, dict)]
    cycle = _has_cycle([str(row.get("from_item_id") or "") for row in edges], [str(row.get("to_item_id") or "") for row in edges])
    blocked_dependencies = []
    for row in edges:
        upstream = str(row.get("from_item_id") or "")
        downstream = str(row.get("to_item_id") or "")
        if item_status.get(upstream) not in {"ready", "go"}:
            blocked_dependencies.append({"from_item_id": upstream, "to_item_id": downstream, "upstream_status": item_status.get(upstream)})
    expected_status = "go" if not cycle and not blocked_dependencies and all(status in {"ready", "go"} for status in item_status.values()) else "no_go"
    checks.extend(
        [
            _check("ucc_train_dependency_graph_acyclic", not cycle, "Dependency graph is acyclic."),
            _check("ucc_train_dependency_blockers_match", dependency.get("summary", {}).get("blocked_dependency_count") == len(blocked_dependencies), "Dependency blocker count is derived from readiness.", {"blocked_dependencies": blocked_dependencies}),
            _check("ucc_train_go_no_go_status_semantics", report.get("status") == expected_status == readiness.get("overall_status"), "Go/No-Go status matches readiness and dependency graph.", {"expected": expected_status, "actual": report.get("status")}),
        ]
    )
    return checks


def _history_checks(history: list[dict[str, Any]], signoff: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    signoff_event: dict[str, Any] | None = None
    for index, event in enumerate(history):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"ucc_train_history_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History event payload hash is valid."))
        checks.append(_check(f"ucc_train_history_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"ucc_train_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
        if event.get("event_type") == "ucc_release_train_signoff_created":
            signoff_event = event
    checks.append(_check("ucc_train_history_has_signoff_event", bool(signoff_event), "History contains train signoff event."))
    if signoff_event:
        checks.extend(
            [
                _check("ucc_train_history_signoff_hash", signoff_event.get("signoff_hash") == signoff.get("integrity_hash"), "History signoff hash matches signoff."),
                _check("ucc_train_history_signed_by", signoff_event.get("signed_by") == signoff.get("signed_by"), "History signed_by matches signoff."),
                _check("ucc_train_history_report_hash", signoff_event.get("go_no_go_report_hash") == signoff.get("go_no_go_report_hash"), "History report hash matches signoff."),
            ]
        )
    return checks


def _signoff_binding_checks(binding: dict[str, Any], signoff: dict[str, Any], history: list[dict[str, Any]], source: dict[str, Any], report: dict[str, Any], inventory: dict[str, Any], readiness: dict[str, Any]) -> list[dict[str, Any]]:
    signoff_event = None
    for row in history:
        if row.get("event_type") == "ucc_release_train_signoff_created" and row.get("signoff_hash") == signoff.get("integrity_hash"):
            signoff_event = row
    binding_source = binding.get("source") if isinstance(binding.get("source"), dict) else {}
    checks = [
        _check("ucc_train_signoff_binding_package_type", binding.get("package_type") == "musicforge_unified_command_center_release_train_signoff_binding", "Signoff binding package type is valid."),
        _check("ucc_train_signoff_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("ucc_train_signoff_binding_payload_hash", binding.get("signoff_payload_hash") == signoff.get("payload_hash"), "Signoff binding matches signoff payload hash."),
        _check("ucc_train_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("ucc_train_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("ucc_train_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("ucc_train_signoff_binding_signed_at", binding.get("signed_at") == signoff.get("signed_at"), "Signoff binding matches signed_at."),
        _check("ucc_train_signoff_binding_source_hash", binding_source.get("source_hash") == source.get("source_hash") == signoff.get("source_hash"), "Signoff binding matches source hash."),
        _check("ucc_train_signoff_binding_report_hash", binding_source.get("go_no_go_report_hash") == report.get("integrity_hash") == signoff.get("go_no_go_report_hash"), "Signoff binding matches Go/No-Go report hash."),
        _check("ucc_train_signoff_binding_inventory_hash", binding_source.get("evidence_inventory_hash") == inventory.get("integrity_hash") == signoff.get("evidence_inventory_hash"), "Signoff binding matches evidence inventory hash."),
        _check("ucc_train_signoff_binding_readiness_hash", binding_source.get("readiness_matrix_hash") == readiness.get("integrity_hash") == signoff.get("readiness_matrix_hash"), "Signoff binding matches readiness matrix hash."),
    ]
    if signoff_event:
        checks.extend(
            [
                _check("ucc_train_signoff_binding_history_event_hash", binding.get("history_event_hash") == signoff_event.get("event_hash"), "Signoff binding matches history event hash."),
                _check("ucc_train_signoff_binding_history_payload_hash", binding.get("history_event_payload_hash") == signoff_event.get("payload_hash"), "Signoff binding matches history payload hash."),
            ]
        )
    else:
        checks.append(_check("ucc_train_signoff_binding_history_event_hash", False, "Signoff binding requires a history signoff event."))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    declared = {str(row.get("path") or "") for row in files}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    checks.append(_check("ucc_train_manifest_files_fixed", declared == expected_files, "Manifest files match the fixed Release Train layout.", {"missing": sorted(expected_files - declared), "extra": sorted(declared - expected_files)}))
    mismatches = []
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in names:
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        data = archive.read(rel)
        if row.get("size_bytes") != len(data) or row.get("sha256") != _sha256_bytes(data):
            mismatches.append({"path": rel, "reason": "hash_or_size"})
    checks.append(_check("ucc_train_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".jsonl", ".txt", ".md")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                leaks.append(name)
                break
    return _check("ucc_train_redaction_scan", not leaks, "Release Train text files do not contain obvious secrets or local paths.", {"leaks": sorted(set(leaks))})


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    all_checks = [*checks, *extra]
    blockers = [check["check_id"] for check in all_checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in all_checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
        "status": status,
        "summary": summary,
        "checks": all_checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, severity: str = "blocking") -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}}


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path | str) -> dict[str, Any]:
    return read_json(Path(path))


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    path = Path(name)
    lowered = name.lower()
    return bool(name and not path.is_absolute() and ".." not in path.parts and not lowered.startswith(".musicforge/") and "/.musicforge/" not in lowered)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _zip_manifest_hash(path: Path | str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = _read_json_entry(archive, "manifest.json")
            return manifest.get("integrity_hash")
    except Exception:
        return None


def _report_zip_sha(report: dict[str, Any]) -> str | None:
    return report.get("zip_sha256") or (report.get("summary") or {}).get("zip_sha256") or (report.get("zip") or {}).get("sha256")


def _report_manifest_hash(report: dict[str, Any]) -> str | None:
    return report.get("manifest_hash") or (report.get("summary") or {}).get("manifest_hash")


def _evidence_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "center_id", "evidence_type"))


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")[:120] or "row"


def _has_cycle(from_nodes: list[str], to_nodes: list[str]) -> bool:
    graph: dict[str, list[str]] = {}
    for source, target in zip(from_nodes, to_nodes):
        if not source or not target:
            continue
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, graph.get(target, []))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))
