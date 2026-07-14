from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_hash as _integrity_hash,
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import (
    ProgramPersistenceError,
    read_program_json as read_json,
    write_program_json as write_json,
)
from song_agent.platform.verification.sanitization import sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program_continuity_acceptance_change_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_acceptance_change_package,
)
from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_acceptance_package,
)
from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_distribution_package,
)
from song_agent.domains.program.unified_release_program_continuity_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_package,
)
from song_agent.domains.program.unified_release_program_vault_operations_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_operations_package,
)
from song_agent.domains.program.unified_release_program_vault_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_package,
)


UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "command-center-report.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "runtime-verification-index.json",
    "gap-plan.json",
    "safe-runbook.json",
    "external-evidence-manifest.json",
}

EXPECTED_VERIFICATION_TYPES = {
    "evidence_vault": UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    "vault_operations": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    "continuity_recovery": UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    "continuity_distribution_kit": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
    "continuity_acceptance_board": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
    "continuity_acceptance_change_control": UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE,
}

EXPECTED_COMPONENT_IDS = {
    "evidence_vault": "v12.3-evidence-vault",
    "vault_operations": "v12.4-vault-operations",
    "continuity_recovery": "v12.5-continuity-recovery",
    "continuity_distribution_kit": "v12.6-continuity-distribution-kit",
    "continuity_acceptance_board": "v12.7-continuity-acceptance-board",
    "continuity_acceptance_change_control": "v12.8-continuity-acceptance-change-control",
}

def verify_unified_release_program_continuity_command_center_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_ready: bool = False,
    evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 256,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpccc_kernel",
                required_entries=frozenset(REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpccc_zip_exists", False, "Continuity Command Center ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpccc_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpccc_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpccc_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpccc_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpccc_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpccc_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpccc_allowed_entries", not extra, "Continuity Command Center contains only fixed entries.", {"extra": extra}),
                    _check("urpccc_required_entries", not missing, "Continuity Command Center contains required entries.", {"missing": missing}),
                    _check("urpccc_no_nested_zip", not nested, "Continuity Command Center ZIP contains no nested ZIP entries.", {"nested": nested}),
                ]
            )
            if _has_blocking_failures(checks):
                if deep:
                    checks.append(_check("urpccc_deep_preflight", False, "Deep verification is skipped when ZIP structure checks fail."))
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "command-center-report.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            runtime_index = _read_json_entry(archive, "runtime-verification-index.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            runbook = _read_json_entry(archive, "safe-runbook.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            summary.update(
                {
                    "program_id": report.get("program_id") or manifest.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "component_count": (inventory.get("summary") or {}).get("component_count"),
                    "ready_count": (report.get("summary") or {}).get("ready_count"),
                }
            )
            checks.extend(
                [
                    _check("urpccc_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpccc_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_SCHEMA_VERSION, "Manifest schema version is supported."),
                    _check("urpccc_report_package_type", report.get("package_type") == "musicforge_unified_release_program_continuity_command_center_report", "Report package type is valid."),
                    _check("urpccc_inventory_package_type", inventory.get("package_type") == "musicforge_unified_release_program_continuity_command_center_evidence_inventory", "Inventory package type is valid."),
                    _check("urpccc_readiness_package_type", readiness.get("package_type") == "musicforge_unified_release_program_continuity_command_center_readiness_matrix", "Readiness package type is valid."),
                    _check("urpccc_runtime_index_package_type", runtime_index.get("package_type") == "musicforge_unified_release_program_continuity_command_center_runtime_verification_index", "Runtime index package type is valid."),
                    _check("urpccc_gap_plan_package_type", gap_plan.get("package_type") == "musicforge_unified_release_program_continuity_command_center_gap_plan", "Gap plan package type is valid."),
                    _check("urpccc_runbook_package_type", runbook.get("package_type") == "musicforge_unified_release_program_continuity_command_center_safe_runbook", "Runbook package type is valid."),
                    _check("urpccc_external_manifest_package_type", external_manifest.get("package_type") == "musicforge_unified_release_program_continuity_command_center_external_evidence_manifest", "External evidence manifest package type is valid."),
                ]
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            for check_id, doc in (
                ("urpccc_manifest_integrity", manifest),
                ("urpccc_report_integrity", report),
                ("urpccc_inventory_integrity", inventory),
                ("urpccc_readiness_integrity", readiness),
                ("urpccc_runtime_index_integrity", runtime_index),
                ("urpccc_gap_plan_integrity", gap_plan),
                ("urpccc_runbook_integrity", runbook),
                ("urpccc_external_manifest_integrity", external_manifest),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, inventory, readiness, runtime_index, gap_plan, runbook, external_manifest))
            checks.extend(_index_binding_checks(inventory, readiness, runtime_index, external_manifest))
            if require_ready:
                checks.extend(
                    [
                        _check("urpccc_require_report_ready", report.get("status") == "ready", "Command Center report is ready."),
                        _check("urpccc_require_readiness_ready", readiness.get("status") == "ready", "Readiness matrix is ready."),
                        _check("urpccc_require_no_blockers", not (report.get("blockers") or readiness.get("blockers")), "Command Center has no blockers."),
                    ]
                )
            if deep or require_ready:
                checks.extend(_external_evidence_checks(external_manifest, runtime_index, evidence_manifest_path, require=bool(require_ready or deep)))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpccc_zip_readable", False, "Continuity Command Center ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_command_center_verification_report(report: dict[str, Any], path: Path | str) -> dict[str, Any]:
    output = dict(report)
    output["package_type"] = UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE
    output["integrity_hash"] = _integrity_hash(output)
    write_json(Path(path), output)
    return output


def unified_release_program_continuity_command_center_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_evidence_checks(public_manifest: dict[str, Any], runtime_index: dict[str, Any], evidence_manifest_path: Path | str | None, *, require: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not evidence_manifest_path or not Path(evidence_manifest_path).exists():
        checks.append(_check("urpccc_external_manifest_required", not require, "External evidence manifest is provided for runtime verification."))
        return checks
    try:
        local_manifest = read_json(Path(evidence_manifest_path))
    except (OSError, json.JSONDecodeError, ProgramPersistenceError) as exc:
        return [_check("urpccc_external_manifest_readable", False, "External evidence manifest can be read.", {"error": sanitize_sensitive_text(str(exc))})]
    local_items = {(_item_key(row)): row for row in local_manifest.get("items") or []}
    public_items = {(_item_key(row)): row for row in public_manifest.get("items") or []}
    runtime_items = {(_item_key(row)): row for row in runtime_index.get("items") or []}
    checks.append(_check("urpccc_external_manifest_integrity_runtime", _integrity_ok(local_manifest), "External evidence manifest integrity is valid."))
    checks.append(_check("urpccc_external_manifest_items_match", set(local_items) == set(public_items), "External evidence manifest item identities match package manifest.", {"missing": sorted(set(public_items) - set(local_items)), "extra": sorted(set(local_items) - set(public_items))}))
    public_state = public_manifest.get("current_state") if isinstance(public_manifest.get("current_state"), dict) else {}
    local_state = local_manifest.get("current_state") if isinstance(local_manifest.get("current_state"), dict) else {}
    state_fields = (
        "generation",
        "generation_hash",
        "acceptance_status",
        "acceptance_signoff_hash",
        "acceptance_history_event_hash",
        "current",
    )
    checks.append(_check("urpccc_external_current_state_binding", all(public_state.get(field) == local_state.get(field) for field in state_fields), "Public and local current-state fingerprints match."))
    generation_path = Path(str(local_state.get("generation_path") or ""))
    history_path = Path(str(local_state.get("acceptance_history_path") or ""))
    checks.append(_check("urpccc_external_generation_exists", generation_path.is_file(), "Current generation evidence exists."))
    checks.append(_check("urpccc_external_acceptance_history_exists", history_path.is_file(), "Acceptance signoff history exists."))
    if generation_path.is_file():
        try:
            generation_doc = read_json(generation_path)
            checks.extend(
                [
                    _check("urpccc_external_generation_integrity", _integrity_ok(generation_doc), "Current generation integrity is valid."),
                    _check("urpccc_external_generation_number", public_state.get("generation") == generation_doc.get("generation"), "Current generation number matches external state."),
                    _check("urpccc_external_generation_hash", public_state.get("generation_hash") == generation_doc.get("integrity_hash"), "Current generation hash matches external state."),
                ]
            )
        except (OSError, json.JSONDecodeError, ProgramPersistenceError) as exc:
            checks.append(_check("urpccc_external_generation_readable", False, "Current generation evidence can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    if history_path.is_file():
        history_state = _acceptance_history_state(history_path)
        checks.extend(
            [
                _check("urpccc_external_acceptance_history_chain", history_state.get("chain_valid") is True, "Acceptance signoff history hash chain is valid."),
                _check("urpccc_external_acceptance_status", public_state.get("acceptance_status") == history_state.get("status") == "signed", "Acceptance signoff is currently signed."),
                _check("urpccc_external_acceptance_signoff_hash", public_state.get("acceptance_signoff_hash") == history_state.get("signoff_hash"), "Current Acceptance signoff hash matches history."),
                _check("urpccc_external_acceptance_event_hash", public_state.get("acceptance_history_event_hash") == history_state.get("event_hash"), "Current Acceptance history event matches external state."),
                _check("urpccc_external_current", public_state.get("current") is True and history_state.get("status") == "signed", "External evidence is current and not reset pending."),
            ]
        )
    for key, public in sorted(public_items.items()):
        local = local_items.get(key) or {}
        runtime_row = runtime_items.get(key) or {}
        component_type = str(public.get("component_type") or "")
        safe_key = _safe_check_key(key)
        binding_fields = (
            "component_type",
            "component_id",
            "status",
            "evidence_status",
            "report_status",
            "runtime_status",
            "zip_sha256",
            "zip_size_bytes",
            "manifest_hash",
            "verification_report_hash",
            "verification_package_type",
            "generation",
            "current",
        )
        checks.append(
            _check(
                f"urpccc_external_{safe_key}_public_local_binding",
                all(public.get(field) == local.get(field) for field in binding_fields),
                "Public and local external evidence fingerprints match.",
            )
        )
        package_path = Path(str(local.get("package_path") or ""))
        verification_path = Path(str(local.get("verification_report_path") or ""))
        checks.append(_check(f"urpccc_external_{safe_key}_package_exists", package_path.exists(), "External component package exists."))
        checks.append(_check(f"urpccc_external_{safe_key}_verification_exists", verification_path.exists(), "External component verification report exists."))
        if not package_path.exists() or not verification_path.exists():
            continue
        try:
            external = read_json(verification_path)
        except ProgramPersistenceError as exc:
            checks.append(
                _check(
                    f"urpccc_external_{safe_key}_verification_authority",
                    False,
                    "External verification projection matches repository authority.",
                    {"error": sanitize_sensitive_text(str(exc))},
                )
            )
            try:
                external = json.loads(verification_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                external = {}
        try:
            runtime = runtime_verify_continuity_command_center_component(component_type, local, local_items)
        except Exception as exc:
            runtime = {
                "status": "failed",
                "blockers": [sanitize_sensitive_text(str(exc))],
                "summary": {},
            }
        expected_package_type = EXPECTED_VERIFICATION_TYPES.get(component_type)
        checks.extend(
            [
                _check(f"urpccc_external_{safe_key}_generation", public.get("generation") == public_state.get("generation"), "Component is bound to the current generation."),
                _check(f"urpccc_external_{safe_key}_current", public.get("current") is True, "Component is marked current."),
                _check(f"urpccc_external_{safe_key}_verification_package_type", external.get("package_type") == expected_package_type, "External verification package type is valid.", {"expected": expected_package_type, "actual": external.get("package_type")}),
                _check(f"urpccc_external_{safe_key}_verification_integrity", _integrity_ok(external), "External verification report integrity is valid."),
                _check(f"urpccc_external_{safe_key}_runtime_passed", runtime.get("status") == "passed", "Runtime verifier passes for component.", {"blockers": runtime.get("blockers") or []}),
                _check(f"urpccc_external_{safe_key}_external_passed", external.get("status") == "passed", "External verification report is passed."),
                _check(f"urpccc_external_{safe_key}_zip_sha256", public.get("package_sha256") == _sha256_path(package_path) == external.get("zip_sha256"), "Package SHA matches manifest and verification report."),
                _check(f"urpccc_external_{safe_key}_zip_size_bytes", int(public.get("zip_size_bytes") or -1) == package_path.stat().st_size == int(external.get("zip_size_bytes") or -2), "Package size matches manifest and verification report."),
                _check(f"urpccc_external_{safe_key}_manifest_hash", public.get("manifest_hash") == runtime.get("manifest_hash") == external.get("manifest_hash"), "Manifest hash matches runtime and verification report."),
                _check(f"urpccc_external_{safe_key}_verification_hash", public.get("verification_report_hash") == external.get("integrity_hash"), "Verification hash matches manifest row."),
                _check(f"urpccc_external_{safe_key}_report_status", public.get("report_status") == external.get("status") == "passed", "Inventory report status follows current external report."),
                _check(f"urpccc_external_{safe_key}_runtime_index_status", runtime_row.get("status") == runtime.get("status") == "passed", "Runtime index reflects current runtime status.", {"runtime_index_status": runtime_row.get("status"), "runtime_status": runtime.get("status")}),
            ]
        )
    return checks


def runtime_verify_continuity_command_center_component(component_type: str, row: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    package = row.get("package_path")
    if component_type == "evidence_vault":
        return verify_unified_release_program_vault_package(package, strict=True, deep=True, require_anchor=True, vault_anchor_path=row.get("anchor_path"))
    if component_type == "vault_operations":
        return verify_unified_release_program_vault_operations_package(package, strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=row.get("signoff_binding_path"))
    if component_type == "continuity_recovery":
        ops = _first_component(rows, "vault_operations")
        return verify_unified_release_program_continuity_package(
            package,
            strict=True,
            deep_restore=True,
            require_signed=True,
            require_current_vault_operations=True,
            signoff_binding_path=row.get("signoff_binding_path"),
            vault_operations_archive_path=ops.get("package_path"),
            vault_operations_verification_report_path=ops.get("verification_report_path"),
            vault_operations_signoff_binding_path=ops.get("signoff_binding_path"),
        )
    if component_type == "continuity_distribution_kit":
        return verify_unified_release_program_continuity_distribution_package(package, strict=True, deep=True)
    if component_type == "continuity_acceptance_board":
        kit = _first_component(rows, "continuity_distribution_kit")
        return verify_unified_release_program_continuity_acceptance_package(
            package,
            strict=True,
            require_current_kit=True,
            require_signed=True,
            require_quorum=True,
            continuity_kit_path=kit.get("package_path"),
            continuity_kit_verification_report_path=kit.get("verification_report_path"),
            signoff_binding_path=row.get("signoff_binding_path"),
        )
    if component_type == "continuity_acceptance_change_control":
        acceptance = _first_component(rows, "continuity_acceptance_board")
        return verify_unified_release_program_continuity_acceptance_change_package(
            package,
            strict=True,
            require_current_acceptance=True,
            acceptance_archive_path=acceptance.get("package_path"),
            acceptance_verification_report_path=acceptance.get("verification_report_path"),
            acceptance_signoff_binding_path=acceptance.get("signoff_binding_path"),
        )
    return {"status": "failed", "blockers": ["unknown_component_type"], "manifest_hash": None, "zip_sha256": None}


def _first_component(rows: dict[str, dict[str, Any]], component_type: str) -> dict[str, Any]:
    for row in rows.values():
        if row.get("component_type") == component_type:
            return row
    return {}


def _acceptance_history_state(path: Path) -> dict[str, Any]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return {"chain_valid": False, "status": "unreadable", "signoff_hash": None, "event_hash": None}
    previous = ""
    state: dict[str, Any] = {"chain_valid": True, "status": "unsigned", "signoff_hash": None, "event_hash": None}
    for row in rows:
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in row.items() if key != "event_hash"})
        if row.get("previous_event_hash") != previous or row.get("payload_hash") != expected_payload or row.get("event_hash") != expected_event:
            state["chain_valid"] = False
        previous = str(row.get("event_hash") or "")
        if row.get("event_type") == "continuity_acceptance_signoff_created":
            state.update({"status": "signed", "signoff_hash": row.get("signoff_hash"), "event_hash": row.get("event_hash")})
        elif row.get("event_type") == "continuity_acceptance_signoff_reset":
            state.update({"status": "reset", "signoff_hash": None, "event_hash": row.get("event_hash")})
    return state


def _document_binding_checks(manifest: dict[str, Any], report: dict[str, Any], inventory: dict[str, Any], readiness: dict[str, Any], runtime_index: dict[str, Any], gap_plan: dict[str, Any], runbook: dict[str, Any], external_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return [
        _check("urpccc_report_inventory_hash", report.get("evidence_inventory_hash") == inventory.get("integrity_hash"), "Report binds evidence inventory."),
        _check("urpccc_report_readiness_hash", report.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Report binds readiness matrix."),
        _check("urpccc_report_runtime_index_hash", report.get("runtime_verification_index_hash") == runtime_index.get("integrity_hash"), "Report binds runtime verification index."),
        _check("urpccc_report_gap_plan_hash", report.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Report binds gap plan."),
        _check("urpccc_report_runbook_hash", report.get("safe_runbook_hash") == runbook.get("integrity_hash"), "Report binds safe runbook."),
        _check("urpccc_report_external_manifest_hash", report.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Report binds external evidence manifest."),
        _check("urpccc_manifest_report_hash", source.get("command_center_report_hash") == report.get("integrity_hash"), "Manifest binds report."),
        _check("urpccc_manifest_inventory_hash", source.get("evidence_inventory_hash") == inventory.get("integrity_hash"), "Manifest binds inventory."),
        _check("urpccc_manifest_readiness_hash", source.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Manifest binds readiness."),
        _check("urpccc_manifest_runtime_index_hash", source.get("runtime_verification_index_hash") == runtime_index.get("integrity_hash"), "Manifest binds runtime index."),
        _check("urpccc_manifest_gap_plan_hash", source.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Manifest binds gap plan."),
        _check("urpccc_manifest_runbook_hash", source.get("safe_runbook_hash") == runbook.get("integrity_hash"), "Manifest binds runbook."),
        _check("urpccc_manifest_external_manifest_hash", source.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Manifest binds external evidence manifest."),
        _check("urpccc_status_binding", source.get("status") == report.get("status"), "Manifest status matches report."),
    ]


def _index_binding_checks(inventory: dict[str, Any], readiness: dict[str, Any], runtime_index: dict[str, Any], external_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    inventory_items = {_item_key(row): row for row in inventory.get("items") or []}
    readiness_items = {_item_key(row): row for row in readiness.get("rows") or []}
    runtime_items = {_item_key(row): row for row in runtime_index.get("items") or []}
    external_items = {_item_key(row): row for row in external_manifest.get("items") or []}
    actual_components = {(str(row.get("component_type") or ""), str(row.get("component_id") or "")) for row in inventory_items.values()}
    expected_components = set(EXPECTED_COMPONENT_IDS.items())
    checks = [
        _check("urpccc_expected_components", actual_components == expected_components, "Inventory contains the fixed Continuity Command Center component set.", {"missing": sorted(expected_components - actual_components), "extra": sorted(actual_components - expected_components)}),
        _check("urpccc_inventory_external_items", set(inventory_items) == set(external_items), "Inventory and external manifest items match."),
        _check("urpccc_inventory_readiness_items", set(inventory_items) == set(readiness_items), "Inventory and readiness items match."),
        _check("urpccc_inventory_runtime_items", set(inventory_items) == set(runtime_items), "Inventory and runtime items match."),
    ]
    for key, row in sorted(inventory_items.items()):
        safe_key = _safe_check_key(key)
        ready = readiness_items.get(key) or {}
        runtime = runtime_items.get(key) or {}
        checks.append(_check(f"urpccc_item_{safe_key}_readiness_status", (row.get("status") == "passed") == (ready.get("status") == "ready"), "Readiness row follows inventory status."))
        checks.append(_check(f"urpccc_item_{safe_key}_runtime_status", row.get("runtime_status") == runtime.get("status"), "Runtime index status follows inventory row."))
        checks.append(_check(f"urpccc_item_{safe_key}_report_status", row.get("report_status") == ready.get("report_status") == runtime.get("report_status"), "Report status is bound across inventory, readiness, and runtime index."))
        checks.append(_check(f"urpccc_item_{safe_key}_runtime_blockers", (row.get("runtime_blockers") or []) == (ready.get("runtime_blockers") or []) == (runtime.get("runtime_blockers") or []), "Runtime blockers are bound across derived documents."))
        checks.append(_check(f"urpccc_item_{safe_key}_zip_fingerprint", row.get("zip_sha256") == runtime.get("zip_sha256") and int(row.get("zip_size_bytes") or -1) == int(runtime.get("zip_size_bytes") or -2), "Runtime index binds the inventory ZIP fingerprint."))
        checks.append(_check(f"urpccc_item_{safe_key}_manifest_fingerprint", row.get("manifest_hash") == runtime.get("manifest_hash"), "Runtime index binds the inventory manifest hash."))
        checks.append(_check(f"urpccc_item_{safe_key}_verification_fingerprint", row.get("verification_report_hash") == runtime.get("verification_report_hash"), "Runtime index binds the external verification report hash."))
        checks.append(_check(f"urpccc_item_{safe_key}_generation", row.get("generation") == ready.get("generation") == runtime.get("generation"), "Generation is bound across derived documents."))
        checks.append(_check(f"urpccc_item_{safe_key}_current", row.get("current") == ready.get("current") == runtime.get("current"), "Current-state marker is bound across derived documents."))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str]) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    paths = {str(row.get("path") or "") for row in files}
    expected = name_set - {"manifest.json"}
    checks = [
        _check("urpccc_manifest_files_exact", paths == expected, "Manifest files match ZIP entries.", {"missing": sorted(expected - paths), "extra": sorted(paths - expected)}),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpccc_manifest_file_{_safe_check_key(rel)}", row.get("sha256") == _sha256_bytes(data) and int(row.get("size_bytes") or -1) == len(data), "Manifest file hash and size match ZIP entry."))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id="urpccc_redaction")


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _item_key(row: dict[str, Any]) -> str:
    return f"{row.get('component_type')}::{row.get('component_id')}::{row.get('generation')}"


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)
