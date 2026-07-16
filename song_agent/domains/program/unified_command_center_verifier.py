from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok
from song_agent.domains.creation.lts_backup_verifier import verify_maintenance_backup_zip
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text
from song_agent.domains.delivery.distribution_verifier import verify_distribution_package
from song_agent.domains.quality.release_audio_command_center import evidence_to_verifier_kwargs as audio_command_center_evidence_to_kwargs
from song_agent.domains.quality.release_audio_command_center_verifier import verify_release_audio_command_center_package
from song_agent.domains.trust.release_operations_verifier import verify_release_operations_package
from song_agent.domains.delivery.release_verifier import verify_release_zip
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.delivery.submission_verifier import verify_submission_package
from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package


UNIFIED_COMMAND_CENTER_PACKAGE_TYPE = "musicforge_unified_command_center"
UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_verification"
UNIFIED_COMMAND_CENTER_SCHEMA_VERSION = 1

COMPONENT_KEYS = (
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
)

RUNTIME_COMPONENT_KEYS = {
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
}

EXPECTED_VERIFICATION_PACKAGE_TYPES: dict[str, set[str]] = {
    "release": {"musicforge_release_verification"},
    "distribution": {"musicforge_distribution_verification"},
    "submission": {"musicforge_submission_verification"},
    "operations": {"musicforge_release_operations_verification"},
    "maintenance": {"musicforge_lts_maintenance_backup_verification_report"},
    "audio-command-center": {"release_audio_command_center_verification"},
    "trust-operations-hub": {"musicforge_trust_operations_hub_verification"},
}

REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "source.json",
    "command-center-report.json",
    "evidence-graph.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "gap-plan.json",
    "safe-runbook.json",
    "runbook-result.json",
    "verification-index.json",
    *{f"component-fingerprints/{key}.json" for key in COMPONENT_KEYS},
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
GA_SENSITIVE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|githubkey\.txt)", re.IGNORECASE)


def verify_unified_command_center_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_ga_ready: bool = False,
    require_audio_ready: bool = False,
    require_trust_ready: bool = False,
    require_public_trust_ready: bool = False,
    require_release_ready: bool = False,
    require_distribution_ready: bool = False,
    require_submission_ready: bool = False,
    require_operations_ready: bool = False,
    require_maintenance_ready: bool = False,
    release_audio_command_center_zip_path: Path | str | None = None,
    release_audio_command_center_verification_report_path: Path | str | None = None,
    release_zip_path: Path | str | None = None,
    release_verification_report_path: Path | str | None = None,
    distribution_zip_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    distribution_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_zip_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    submission_verification_report_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
    release_operations_zip_path: Path | str | None = None,
    release_operations_verification_report_path: Path | str | None = None,
    trust_operations_hub_zip_path: Path | str | None = None,
    trust_operations_hub_verification_report_path: Path | str | None = None,
    public_trust_center_zip_path: Path | str | None = None,
    public_trust_center_verification_report_path: Path | str | None = None,
    maintenance_backup_zip_path: Path | str | None = None,
    maintenance_backup_verification_report_path: Path | str | None = None,
    ga_readiness_report_path: Path | str | None = None,
    ga_readiness_verification_report_path: Path | str | None = None,
    release_check_report_path: Path | str | None = None,
    audio_evidence: dict[str, Any] | None = None,
    trust_evidence: dict[str, Any] | None = None,
    public_trust_evidence: dict[str, Any] | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    external = _external_paths(
        release_audio_command_center_zip_path=release_audio_command_center_zip_path,
        release_audio_command_center_verification_report_path=release_audio_command_center_verification_report_path,
        release_zip_path=release_zip_path,
        release_verification_report_path=release_verification_report_path,
        distribution_zip_paths=distribution_zip_paths,
        distribution_verification_report_paths=distribution_verification_report_paths,
        submission_zip_paths=submission_zip_paths,
        submission_verification_report_paths=submission_verification_report_paths,
        release_operations_zip_path=release_operations_zip_path,
        release_operations_verification_report_path=release_operations_verification_report_path,
        trust_operations_hub_zip_path=trust_operations_hub_zip_path,
        trust_operations_hub_verification_report_path=trust_operations_hub_verification_report_path,
        public_trust_center_zip_path=public_trust_center_zip_path,
        public_trust_center_verification_report_path=public_trust_center_verification_report_path,
        maintenance_backup_zip_path=maintenance_backup_zip_path,
        maintenance_backup_verification_report_path=maintenance_backup_verification_report_path,
        ga_readiness_report_path=ga_readiness_report_path,
        ga_readiness_verification_report_path=ga_readiness_verification_report_path,
        release_check_report_path=release_check_report_path,
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_zip_exists", False, "Unified Command Center ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_zip_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_zip_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_zip_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("ucc_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            checks.append(_check("ucc_zip_no_nested_zip", not nested, "ZIP contains no nested ZIP entries.", {"nested": nested}))
            extra = sorted(set(names) - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - set(names))
            checks.append(_check("ucc_zip_allowed_entries", not extra, "ZIP contains only fixed Unified Command Center entries.", {"extra": extra}))
            checks.append(_check("ucc_zip_expected_entries", not missing, "ZIP contains all fixed Unified Command Center entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            source = _read_json_entry(archive, "source.json")
            report = _read_json_entry(archive, "command-center-report.json")
            graph = _read_json_entry(archive, "evidence-graph.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            runbook = _read_json_entry(archive, "safe-runbook.json")
            runbook_result = _read_json_entry(archive, "runbook-result.json")
            verification_index = _read_json_entry(archive, "verification-index.json")
            fingerprints = {key: _read_json_entry(archive, f"component-fingerprints/{key}.json") for key in COMPONENT_KEYS}

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["center_id"] = report.get("center_id") or manifest.get("center_id")
            summary["readiness"] = report.get("status")
            summary["source_hash"] = report.get("source_hash")
            checks.extend(_manifest_checks(archive, manifest, set(names)))
            checks.append(_check("ucc_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, doc in (
                ("ucc_manifest_integrity", manifest),
                ("ucc_source_integrity", source),
                ("ucc_report_integrity", report),
                ("ucc_graph_integrity", graph),
                ("ucc_inventory_integrity", inventory),
                ("ucc_readiness_integrity", readiness),
                ("ucc_gap_plan_integrity", gap_plan),
                ("ucc_runbook_integrity", runbook),
                ("ucc_runbook_result_integrity", runbook_result),
                ("ucc_verification_index_integrity", verification_index),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            for key in COMPONENT_KEYS:
                checks.append(_check(f"ucc_{key}_fingerprint_integrity", _integrity_ok(fingerprints[key]), f"{key} fingerprint integrity hash is valid."))
            checks.extend(_document_binding_checks(manifest, source, report, graph, inventory, readiness, gap_plan, runbook, runbook_result, verification_index, fingerprints, require_ready=require_ready))
            for key in COMPONENT_KEYS:
                required = _component_required(inventory, key)
                forced = _component_forced(
                    key,
                    require_audio_ready=require_audio_ready,
                    require_trust_ready=require_trust_ready,
                    require_public_trust_ready=require_public_trust_ready,
                    require_release_ready=require_release_ready,
                    require_distribution_ready=require_distribution_ready,
                    require_submission_ready=require_submission_ready,
                    require_operations_ready=require_operations_ready,
                    require_maintenance_ready=require_maintenance_ready,
                    require_ga_ready=require_ga_ready,
                )
                has_external = any(value for value in (external.get(key) or {}).values())
                if required or forced or has_external:
                    checks.extend(
                        _external_component_checks(
                            key,
                            fingerprints[key],
                            external=external,
                            audio_evidence=audio_evidence or {},
                            trust_evidence=trust_evidence or {},
                            public_trust_evidence=public_trust_evidence or {},
                            require_component=required or forced,
                        )
                    )
            checks.append(_redaction_check(archive, names))
            if require_ready:
                checks.append(_check("ucc_require_ready", report.get("status") == "ready" and readiness.get("overall_status") == "ready", "Unified Command Center is ready."))
            if require_audio_ready:
                checks.append(_domain_requirement_check(readiness, "audio", "ucc_require_audio_ready"))
            if require_trust_ready:
                checks.append(_domain_requirement_check(readiness, "trust_operations", "ucc_require_trust_ready"))
            if require_public_trust_ready:
                checks.append(_domain_requirement_check(readiness, "public_trust", "ucc_require_public_trust_ready"))
            if require_release_ready:
                checks.append(_domain_requirement_check(readiness, "release", "ucc_require_release_ready"))
            if require_distribution_ready:
                checks.append(_domain_requirement_check(readiness, "distribution", "ucc_require_distribution_ready"))
            if require_submission_ready:
                checks.append(_domain_requirement_check(readiness, "submission", "ucc_require_submission_ready"))
            if require_operations_ready:
                checks.append(_domain_requirement_check(readiness, "operations", "ucc_require_operations_ready"))
            if require_maintenance_ready:
                checks.append(_domain_requirement_check(readiness, "maintenance", "ucc_require_maintenance_ready"))
            if require_ga_ready:
                checks.append(_domain_requirement_check(readiness, "ga", "ucc_require_ga_ready"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_zip_readable", False, "Unified Command Center ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def verify_unified_command_center_component(
    key: str,
    *,
    zip_path: Path | str | None = None,
    verification_report_path: Path | str | None = None,
    report_path: Path | str | None = None,
    audio_evidence: dict[str, Any] | None = None,
    trust_evidence: dict[str, Any] | None = None,
    public_trust_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    fingerprint = {
        "component_key": key,
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": None,
        "runtime_status": None,
        "runtime_manifest_hash": None,
        "runtime_failed_count": 0,
        "runtime_blockers": [],
    }
    if key == "release":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_release_external_required", False, "Release ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_release_zip(path, strict=True))
    if key == "distribution":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_distribution_external_required", False, "Distribution ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_distribution_package(path, strict=True))
    if key == "submission":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_submission_external_required", False, "Submission ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_submission_package(path, strict=True))
    if key == "operations":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_operations_external_required", False, "Release Operations ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_release_operations_package(path, strict=True))
    if key == "release-check":
        return _release_check_component(report_path or verification_report_path)
    if key == "ga-readiness":
        if not report_path:
            checks.append(_check("ucc_ga-readiness_report_required", False, "GA readiness report is required."))
            return _component_finish(key, fingerprint, checks)
        return _ga_component(report_path, verification_report_path)
    if key == "maintenance":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_maintenance_external_required", False, "Maintenance backup ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_maintenance_backup_zip(path, strict=True))
    if key == "audio-command-center":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_audio-command-center_external_required", False, "Release Audio Command Center ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        kwargs = audio_command_center_evidence_to_kwargs(audio_evidence or {})
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_release_audio_command_center_package(path, strict=True, require_ready=True, **kwargs))
    if key == "trust-operations-hub":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_trust-operations-hub_external_required", False, "Trust Operations Hub ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_trust_operations_hub_package(path, strict=True, require_ready=False, **(trust_evidence or {})))
    if key == "public-trust-center":
        if not zip_path or not verification_report_path:
            checks.append(_check("ucc_public-trust-center_external_required", False, "Public Trust Center ZIP and verification report are required."))
            return _component_finish(key, fingerprint, checks)
        return _runtime_zip_component(key, zip_path, verification_report_path, lambda path: verify_public_trust_center_package(path, strict=True, **(public_trust_evidence or {})))
    checks.append(_check(f"ucc_{key}_known", False, f"Unknown Unified Command Center component: {key}"))
    return _component_finish(key, fingerprint, checks)


def write_unified_command_center_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _runtime_zip_component(key: str, zip_path: Path | str, report_path: Path | str, verifier) -> ImplementationDocument:
    checks: list[dict[str, Any]] = []
    fingerprint = {"component_key": key, "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    zip_path = Path(zip_path)
    report_path = Path(report_path)
    checks.append(_check(f"ucc_{key}_zip_exists", zip_path.exists() and zip_path.is_file(), f"{key} ZIP exists."))
    checks.append(_check(f"ucc_{key}_verification_report_exists", report_path.exists() and report_path.is_file(), f"{key} verification report exists."))
    if any(check["status"] == "failed" for check in checks):
        return _component_finish(key, fingerprint, checks)
    try:
        external_report = read_json(report_path)
    except Exception as exc:
        checks.append(_check(f"ucc_{key}_verification_report_readable", False, f"{key} verification report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
        return _component_finish(key, fingerprint, checks)
    try:
        runtime_report = verifier(zip_path)
    except Exception as exc:
        runtime_report = {"status": "failed", "manifest_hash": None, "blockers": [sanitize_sensitive_text(str(exc))]}
    runtime_blockers = [str(item) for item in runtime_report.get("blockers", []) if str(item)]
    fingerprint.update(
        {
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": _report_manifest_hash(runtime_report),
            "verification_report_hash": _report_integrity_hash(external_report),
            "verification_status": external_report.get("status"),
            "runtime_status": runtime_report.get("status"),
            "runtime_manifest_hash": _report_manifest_hash(runtime_report),
            "runtime_failed_count": len(runtime_blockers),
            "runtime_blockers": runtime_blockers,
            "_external_report": external_report,
            "_runtime_report": runtime_report,
        }
    )
    checks.extend(
        [
            _check(
                f"ucc_{key}_external_package_type",
                _package_type_matches(key, external_report),
                f"{key} external verification report package_type is valid.",
                {"package_type": external_report.get("package_type"), "expected": sorted(EXPECTED_VERIFICATION_PACKAGE_TYPES.get(key, set()))},
            ),
            _check(
                f"ucc_{key}_runtime_package_type",
                _package_type_matches(key, runtime_report),
                f"{key} runtime verification report package_type is valid.",
                {"package_type": runtime_report.get("package_type"), "expected": sorted(EXPECTED_VERIFICATION_PACKAGE_TYPES.get(key, set()))},
            ),
            _check(f"ucc_{key}_external_report_integrity", _report_integrity_ok(external_report), f"{key} external verification report integrity hash is valid."),
            _check(f"ucc_{key}_external_status", external_report.get("status") == "passed", f"{key} external verification report status is passed.", {"external_status": external_report.get("status")}),
            _check(f"ucc_{key}_external_zip_binding", _report_zip_sha256(external_report) == fingerprint["zip_sha256"], f"{key} external verification report matches current ZIP sha256."),
            _check(f"ucc_{key}_external_manifest_binding", _manifest_binding_matches(external_report, fingerprint["runtime_manifest_hash"]), f"{key} external verification report matches current manifest hash."),
            _check(f"ucc_{key}_runtime_status", runtime_report.get("status") == "passed", f"{key} runtime verification is passed.", {"runtime_status": runtime_report.get("status"), "runtime_blockers": runtime_blockers}),
        ]
    )
    return _component_finish(key, fingerprint, checks, runtime_report=runtime_report, external_report=external_report)


def _ga_component(report_path: Path | str, verification_report_path: Path | str | None) -> ImplementationDocument:
    checks: list[dict[str, Any]] = []
    fingerprint = {"component_key": "ga-readiness", "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    report_path = Path(report_path)
    checks.append(_check("ucc_ga-readiness_report_exists", report_path.exists() and report_path.is_file(), "GA readiness report exists."))
    if checks[-1]["status"] == "failed":
        return _component_finish("ga-readiness", fingerprint, checks)
    runtime_report = _verify_ga_readiness_report_core(report_path)
    external_report: dict[str, Any] = {}
    if verification_report_path:
        try:
            external_report = read_json(Path(verification_report_path))
        except Exception as exc:
            checks.append(_check("ucc_ga-readiness_verification_report_readable", False, "GA readiness verification report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
    if external_report:
        checks.extend(
            [
                _check("ucc_ga-readiness_external_report_integrity", _report_integrity_ok(external_report), "GA readiness verification report integrity hash is valid."),
                _check("ucc_ga-readiness_external_status", external_report.get("status") != "failed", "GA readiness external verification is not failed.", {"external_status": external_report.get("status")}),
            ]
        )
    runtime_blockers = [str(item.get("check_id") or item) for item in runtime_report.get("blockers", [])]
    fingerprint.update(
        {
            "verification_report_hash": _report_integrity_hash(external_report) if external_report else None,
            "verification_status": external_report.get("status") if external_report else None,
            "runtime_status": runtime_report.get("status"),
            "runtime_failed_count": len(runtime_blockers),
            "runtime_blockers": runtime_blockers,
        }
    )
    checks.append(_check("ucc_ga-readiness_runtime_status", runtime_report.get("status") != "failed", "GA readiness runtime verification is not failed.", {"runtime_status": runtime_report.get("status")}))
    return _component_finish("ga-readiness", fingerprint, checks, runtime_report=runtime_report, external_report=external_report)


def _verify_ga_readiness_report_core(report_path: Path) -> ImplementationDocument:
    try:
        report = read_json(report_path)
    except Exception as exc:
        return {
            "package_type": "musicforge_ga_readiness_verification_report",
            "status": "failed",
            "blockers": ["ga_readiness_report_readable"],
            "warnings": [],
            "details": {"error": sanitize_sensitive_text(str(exc))},
        }

    status = str(report.get("status") or "unknown")
    checks = [
        _check("ga_readiness_package_type", report.get("package_type") == GA_READINESS_PACKAGE_TYPE, "GA readiness report package type is valid."),
        _check("ga_readiness_schema_version", report.get("schema_version") == GA_READINESS_SCHEMA_VERSION, "GA readiness report schema version is supported."),
        _check("ga_readiness_integrity", ga_readiness_integrity_ok(report), "GA readiness report integrity hash matches."),
        _check("ga_readiness_status_allowed", status in {"ready", "warning"}, f"GA readiness status is {status}.", blocking=status == "blocked"),
        _check("ga_readiness_redaction", not GA_SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)), "GA readiness report contains no obvious sensitive values."),
    ]
    blockers = [row["check_id"] for row in checks if row.get("status") == "failed" and row.get("blocking", True)]
    warnings = [row["check_id"] for row in checks if row.get("status") == "failed" and not row.get("blocking", True)]
    return {
        "package_type": "musicforge_ga_readiness_verification_report",
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def _release_check_component(report_path: Path | str | None) -> ImplementationDocument:
    checks: list[dict[str, Any]] = []
    fingerprint = {"component_key": "release-check", "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    if not report_path:
        checks.append(_check("ucc_release-check_report_required", False, "release-check JSON report is required."))
        return _component_finish("release-check", fingerprint, checks)
    try:
        report = read_json(Path(report_path))
    except Exception as exc:
        checks.append(_check("ucc_release-check_report_readable", False, "release-check report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
        return _component_finish("release-check", fingerprint, checks)
    failed = [str(item.get("check_id") or "") for item in report.get("results", []) if isinstance(item, dict) and item.get("status") == "failed"]
    ok = bool(report.get("ok")) and not failed
    fingerprint.update({"verification_report_hash": stable_hash(report), "verification_status": "passed" if ok else "failed", "runtime_status": "passed" if ok else "failed", "runtime_failed_count": len(failed), "runtime_blockers": failed})
    checks.append(_check("ucc_release-check_status", ok, "release-check report is passed.", {"failed": failed[:10]}))
    return _component_finish("release-check", fingerprint, checks, runtime_report=report, external_report=report)


def _generic_report_component(key: str, report_path: Path | str | None) -> ImplementationDocument:
    checks: list[dict[str, Any]] = []
    fingerprint = {"component_key": key, "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    if not report_path:
        checks.append(_check(f"ucc_{key}_report_required", False, f"{key} verification report is required."))
        return _component_finish(key, fingerprint, checks)
    try:
        report = read_json(Path(report_path))
    except Exception as exc:
        checks.append(_check(f"ucc_{key}_report_readable", False, f"{key} verification report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
        return _component_finish(key, fingerprint, checks)
    blockers = [str(item) for item in report.get("blockers", [])]
    status = str(report.get("status") or "unknown")
    fingerprint.update({"verification_report_hash": _report_integrity_hash(report), "verification_status": status, "runtime_status": status, "manifest_hash": _report_manifest_hash(report), "runtime_manifest_hash": _report_manifest_hash(report), "runtime_failed_count": len(blockers), "runtime_blockers": blockers})
    if report.get("integrity_hash"):
        checks.append(_check(f"ucc_{key}_report_integrity", _report_integrity_ok(report), f"{key} verification report integrity hash is valid."))
    checks.append(_check(f"ucc_{key}_status", status == "passed", f"{key} verification status is passed.", {"status": status}))
    return _component_finish(key, fingerprint, checks, runtime_report=report, external_report=report)


def _component_finish(key: str, fingerprint: ImplementationDocument, checks: list[ImplementationDocument], *, runtime_report: ImplementationDocument | None = None, external_report: ImplementationDocument | None = None) -> ImplementationDocument:
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    public_fingerprint = _public_fingerprint(fingerprint)
    public_fingerprint["integrity_hash"] = _integrity_hash(public_fingerprint)
    result = {
        "component_key": key,
        "status": "passed" if not blockers else "failed",
        "readiness": "ready" if not blockers else _readiness_from_checks(checks),
        "fingerprint": public_fingerprint,
        "checks": checks,
        "blockers": blockers,
        "runtime_report": _public_report(runtime_report or {}),
        "external_report": _public_report(external_report or {}),
    }
    result["integrity_hash"] = _integrity_hash(result)
    return result


def _external_component_checks(key: str, fingerprint: ImplementationDocument, *, external: dict[str, ImplementationDocument], audio_evidence: ImplementationDocument, trust_evidence: ImplementationDocument, public_trust_evidence: ImplementationDocument, require_component: bool) -> list[ImplementationDocument]:
    if key in {"distribution", "submission"}:
        return _external_multi_component_checks(key, fingerprint, external=external, require_component=require_component)
    ext = external.get(key, {})
    if not require_component and not any(ext.values()):
        return []
    runtime = verify_unified_command_center_component(
        key,
        zip_path=ext.get("zip"),
        verification_report_path=ext.get("verification_report"),
        report_path=ext.get("report"),
        audio_evidence=audio_evidence,
        trust_evidence=trust_evidence,
        public_trust_evidence=public_trust_evidence,
    )
    current = runtime.get("fingerprint") if isinstance(runtime.get("fingerprint"), dict) else {}
    return list(runtime.get("checks") or []) + [
        _check(
            f"ucc_{key}_fingerprint_binding",
            (
                fingerprint.get("zip_sha256") == current.get("zip_sha256")
                and fingerprint.get("zip_size_bytes") == current.get("zip_size_bytes")
                and fingerprint.get("manifest_hash") == current.get("manifest_hash")
                and fingerprint.get("verification_report_hash") == current.get("verification_report_hash")
                and fingerprint.get("verification_status") == current.get("verification_status")
                and fingerprint.get("runtime_status") == current.get("runtime_status")
                and fingerprint.get("runtime_manifest_hash") == current.get("runtime_manifest_hash")
                and int(fingerprint.get("runtime_failed_count") or 0) == int(current.get("runtime_failed_count") or 0)
                and sorted(str(item) for item in fingerprint.get("runtime_blockers", []) if str(item)) == sorted(str(item) for item in current.get("runtime_blockers", []) if str(item))
            ),
            f"{key} fingerprint matches current external evidence.",
            {"expected": current},
        )
    ]


def _external_multi_component_checks(key: str, fingerprint: ImplementationDocument, *, external: dict[str, ImplementationDocument], require_component: bool) -> list[ImplementationDocument]:
    ext = external.get(key, {})
    zip_paths = [Path(item) for item in ext.get("zips", []) if item]
    report_paths = [Path(item) for item in ext.get("verification_reports", []) if item]
    checks: list[dict[str, Any]] = []
    if require_component and (not zip_paths or not report_paths):
        checks.append(_check(f"ucc_{key}_external_required", False, f"{key} external ZIP and verification report lists are required."))
        return checks
    if not require_component and not zip_paths and not report_paths:
        return checks
    checks.append(_check(f"ucc_{key}_external_pair_count", len(zip_paths) == len(report_paths), f"{key} external ZIP/report counts match.", {"zip_count": len(zip_paths), "report_count": len(report_paths)}))
    if len(zip_paths) != len(report_paths):
        return checks
    runtime_items: list[dict[str, Any]] = []
    for index, (zip_path, report_path) in enumerate(zip(zip_paths, report_paths), start=1):
        runtime = verify_unified_command_center_component(key, zip_path=zip_path, verification_report_path=report_path)
        current = runtime.get("fingerprint") if isinstance(runtime.get("fingerprint"), dict) else {}
        component_id = _component_id_from_report(key, current.get("external_report") or {}, index)
        # current may not include public reports; fall back to runtime report embedded by component result.
        external_report = runtime.get("external_report") if isinstance(runtime.get("external_report"), dict) else {}
        runtime_report = runtime.get("runtime_report") if isinstance(runtime.get("runtime_report"), dict) else {}
        component_id = _component_id_from_report(key, external_report or runtime_report, index)
        item = {
            "component_id": component_id,
            "zip_sha256": current.get("zip_sha256"),
            "zip_size_bytes": current.get("zip_size_bytes"),
            "manifest_hash": current.get("manifest_hash"),
            "verification_report_hash": current.get("verification_report_hash"),
            "verification_status": current.get("verification_status"),
            "runtime_status": current.get("runtime_status"),
            "runtime_manifest_hash": current.get("runtime_manifest_hash"),
            "runtime_failed_count": current.get("runtime_failed_count"),
            "runtime_blockers": current.get("runtime_blockers", []),
        }
        runtime_items.append(item)
        checks.extend(list(runtime.get("checks") or []))
    expected_items = _fingerprint_items(fingerprint)
    checks.append(_check(f"ucc_{key}_fingerprint_binding", _semantic_hash(expected_items) == _semantic_hash(runtime_items), f"{key} multi-instance fingerprints match current external evidence.", {"expected": expected_items, "current": runtime_items}))
    return checks


def _document_binding_checks(manifest: ImplementationDocument, source: ImplementationDocument, report: ImplementationDocument, graph: ImplementationDocument, inventory: ImplementationDocument, readiness: ImplementationDocument, gap_plan: ImplementationDocument, runbook: ImplementationDocument, runbook_result: ImplementationDocument, verification_index: ImplementationDocument, fingerprints: dict[str, ImplementationDocument], *, require_ready: bool) -> list[ImplementationDocument]:
    source_hash = report.get("source_hash")
    doc_hashes = report.get("document_hashes") if isinstance(report.get("document_hashes"), dict) else {}
    checks = [
        _check("ucc_source_hash_binding", bool(source_hash) and source.get("source_hash") == source_hash and graph.get("source_hash") == source_hash and inventory.get("source_hash") == source_hash and readiness.get("source_hash") == source_hash and gap_plan.get("source_hash") == source_hash and runbook.get("source_hash") == source_hash and runbook_result.get("source_hash") == source_hash, "All documents bind the same source hash."),
        _check("ucc_report_document_hashes", doc_hashes.get("source") == source.get("integrity_hash") and doc_hashes.get("evidence_graph") == graph.get("integrity_hash") and doc_hashes.get("evidence_inventory") == inventory.get("integrity_hash") and doc_hashes.get("readiness_matrix") == readiness.get("integrity_hash") and doc_hashes.get("gap_plan") == gap_plan.get("integrity_hash") and doc_hashes.get("safe_runbook") == runbook.get("integrity_hash") and doc_hashes.get("runbook_result") == runbook_result.get("integrity_hash") and doc_hashes.get("verification_index") == verification_index.get("integrity_hash"), "Report binds all Unified Command Center documents."),
        _check("ucc_manifest_document_hashes", manifest.get("report_hash") == report.get("integrity_hash") and manifest.get("source_hash") == source_hash and (manifest.get("sidecars") or {}).get("evidence_graph_hash") == graph.get("integrity_hash") and (manifest.get("sidecars") or {}).get("inventory_hash") == inventory.get("integrity_hash") and (manifest.get("sidecars") or {}).get("readiness_hash") == readiness.get("integrity_hash") and (manifest.get("sidecars") or {}).get("gap_plan_hash") == gap_plan.get("integrity_hash") and (manifest.get("sidecars") or {}).get("runbook_hash") == runbook.get("integrity_hash"), "Manifest binds all Unified documents."),
    ]
    components = {str(row.get("component_key")): row for row in inventory.get("components", []) if isinstance(row, dict)}
    graph_nodes = {str(row.get("node_id")): row for row in graph.get("nodes", []) if isinstance(row, dict)}
    for key in COMPONENT_KEYS:
        component = components.get(key, {})
        checks.append(_check(f"ucc_{key}_inventory_fingerprint_binding", _semantic_hash(component.get("fingerprint") or {}) == _semantic_hash(fingerprints[key]), f"{key} inventory fingerprint matches sidecar."))
        node = graph_nodes.get(str(component.get("node_id") or ""))
        checks.append(_check(f"ucc_{key}_graph_inventory_binding", bool(node) and node.get("readiness") == component.get("readiness") and _semantic_hash(node.get("fingerprint") or {}) == _semantic_hash(component.get("fingerprint") or {}), f"{key} graph node matches inventory."))
    required_blocked = [row.get("component_key") for row in inventory.get("components", []) if isinstance(row, dict) and row.get("required") and row.get("readiness") != "ready"]
    gap_component_keys = sorted(str(row.get("component_key")) for row in gap_plan.get("items", []) if isinstance(row, dict))
    checks.append(_check("ucc_readiness_gap_semantics", sorted(str(item) for item in required_blocked) == gap_component_keys, "Gap plan matches blocked required inventory components.", {"blocked": required_blocked, "gaps": gap_component_keys}))
    overall_ready = not required_blocked and readiness.get("overall_status") == "ready" and report.get("status") == "ready"
    if require_ready:
        checks.append(_check("ucc_require_ready", overall_ready, "Unified Command Center is ready.", {"blocked": required_blocked}))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective = names - {"manifest.json"}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        data = archive.read(path)
        info = archive.getinfo(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("ucc_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("ucc_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_manifest_fixed_files", declared == expected, "Manifest files match fixed Unified Command Center structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("ucc_manifest_zip_entries_reference_only", True, "manifest.zip.entries is not used as an allow-list."),
    ]


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _external_paths(**kwargs: Any) -> dict[str, ImplementationDocument]:
    return {
        "audio-command-center": {"zip": kwargs.get("release_audio_command_center_zip_path"), "verification_report": kwargs.get("release_audio_command_center_verification_report_path")},
        "trust-operations-hub": {"zip": kwargs.get("trust_operations_hub_zip_path"), "verification_report": kwargs.get("trust_operations_hub_verification_report_path")},
        "public-trust-center": {"zip": kwargs.get("public_trust_center_zip_path"), "verification_report": kwargs.get("public_trust_center_verification_report_path")},
        "maintenance": {"zip": kwargs.get("maintenance_backup_zip_path"), "verification_report": kwargs.get("maintenance_backup_verification_report_path")},
        "ga-readiness": {"report": kwargs.get("ga_readiness_report_path"), "verification_report": kwargs.get("ga_readiness_verification_report_path")},
        "release-check": {"report": kwargs.get("release_check_report_path")},
        "release": {"zip": kwargs.get("release_zip_path"), "verification_report": kwargs.get("release_verification_report_path")},
        "distribution": {"zips": _path_list(kwargs.get("distribution_zip_paths")), "verification_reports": _path_list(kwargs.get("distribution_verification_report_paths"))},
        "submission": {"zips": _path_list(kwargs.get("submission_zip_paths")), "verification_reports": _path_list(kwargs.get("submission_verification_report_paths"))},
        "operations": {"zip": kwargs.get("release_operations_zip_path"), "verification_report": kwargs.get("release_operations_verification_report_path")},
    }


def _public_report(report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    public = {
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
        "blockers": report.get("blockers", []),
        "summary": {key: value for key, value in summary.items() if key not in {"zip_path", "path"}},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _component_status(inventory: ImplementationDocument, key: str) -> str:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return str(row.get("readiness") or row.get("status") or "")
    return ""


def _component_required(inventory: ImplementationDocument, key: str) -> bool:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return bool(row.get("required"))
    return False


def _component_forced(
    key: str,
    *,
    require_audio_ready: bool,
    require_trust_ready: bool,
    require_public_trust_ready: bool,
    require_release_ready: bool,
    require_distribution_ready: bool,
    require_submission_ready: bool,
    require_operations_ready: bool,
    require_maintenance_ready: bool,
    require_ga_ready: bool,
) -> bool:
    return (
        (key == "audio-command-center" and require_audio_ready)
        or (key == "trust-operations-hub" and require_trust_ready)
        or (key == "public-trust-center" and require_public_trust_ready)
        or (key == "release" and require_release_ready)
        or (key == "distribution" and require_distribution_ready)
        or (key == "submission" and require_submission_ready)
        or (key == "operations" and require_operations_ready)
        or (key == "maintenance" and require_maintenance_ready)
        or (key == "ga-readiness" and require_ga_ready)
    )


def _domain_requirement_check(readiness: ImplementationDocument, domain: str, check_id: str) -> ImplementationDocument:
    for row in readiness.get("domains", []):
        if isinstance(row, dict) and row.get("domain") == domain:
            return _check(check_id, row.get("status") == "ready", f"{domain} readiness is ready.", {"status": row.get("status")})
    return _check(check_id, False, f"{domain} readiness row is missing.")


def _readiness_from_checks(checks: list[ImplementationDocument]) -> str:
    failed = [str(check.get("check_id") or "") for check in checks if check.get("status") == "failed"]
    if any("required" in item or "exists" in item for item in failed):
        return "missing"
    if any("integrity" in item or "external_status" in item for item in failed):
        return "verification_failed"
    if any("binding" in item for item in failed):
        return "stale"
    if any("runtime_status" in item for item in failed):
        return "runtime_failed"
    return "blocked"


def _path_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item]
    return [value] if value else []


def _report_integrity_hash(report: ImplementationDocument) -> str:
    return str(report.get("integrity_hash") or stable_hash(report))


def _package_type_matches(key: str, report: ImplementationDocument) -> bool:
    expected = EXPECTED_VERIFICATION_PACKAGE_TYPES.get(key)
    if not expected:
        return True
    return str(report.get("package_type") or "") in expected


def _report_integrity_ok(report: ImplementationDocument) -> bool:
    if not report:
        return False
    if report.get("integrity_hash"):
        return report.get("integrity_hash") == _integrity_hash(report)
    return True


def _report_zip_sha256(report: ImplementationDocument) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    input_doc = report.get("input") if isinstance(report.get("input"), dict) else {}
    return report.get("zip_sha256") or summary.get("zip_sha256") or input_doc.get("sha256")


def _report_zip_size(report: ImplementationDocument) -> int | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    input_doc = report.get("input") if isinstance(report.get("input"), dict) else {}
    value = report.get("zip_size_bytes") or summary.get("zip_size_bytes") or input_doc.get("size_bytes")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _report_manifest_hash(report: ImplementationDocument) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return report.get("manifest_hash") or summary.get("manifest_hash")


def _manifest_binding_matches(report: ImplementationDocument, runtime_manifest_hash: str | None) -> bool:
    expected = _report_manifest_hash(report)
    if expected:
        return expected == runtime_manifest_hash
    # Older verifiers did not persist manifest_hash. In that case ZIP sha/runtime status
    # are still checked, and manifest binding is not claimed as independent evidence.
    return True


def _component_id_from_report(key: str, report: ImplementationDocument, index: int) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    prefix = {"distribution": "distribution", "submission": "submission"}.get(key, key)
    for field in ("release_id", "target_id", "submission_id", "package_id"):
        value = report.get(field) or summary.get(field)
        if value:
            return f"{prefix}:{_safe_component_id(str(value))}"
    return f"{prefix}:{index:03d}"


def _safe_component_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-") or "unknown"


def _fingerprint_items(fingerprint: ImplementationDocument) -> list[ImplementationDocument]:
    items = fingerprint.get("items") if isinstance(fingerprint.get("items"), list) else []
    return sorted([_public_fingerprint(item) for item in items if isinstance(item, dict)], key=lambda item: str(item.get("component_id") or ""))


def _public_fingerprint(value: ImplementationDocument) -> ImplementationDocument:
    return {key: val for key, val in value.items() if not str(key).startswith("_")}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _semantic_hash(value: Any) -> str:
    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    parts = name.split("/")
    return all(part and part not in {".", ".."} and ":" not in part for part in parts)


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("ucc_redaction_scan", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
