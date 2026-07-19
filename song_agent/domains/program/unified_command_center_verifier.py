# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE as GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION as GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok as ga_readiness_integrity_ok
from song_agent.domains.creation.lts_backup_verifier import verify_maintenance_backup_zip as verify_maintenance_backup_zip
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.distribution_verifier import verify_distribution_package as verify_distribution_package
from song_agent.domains.quality.release_audio_command_center import evidence_to_verifier_kwargs as audio_command_center_evidence_to_kwargs
from song_agent.domains.quality.release_audio_command_center_verifier import verify_release_audio_command_center_package as verify_release_audio_command_center_package
from song_agent.domains.trust.release_operations_verifier import verify_release_operations_package as verify_release_operations_package
from song_agent.domains.delivery.release_verifier import verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submission_verifier import verify_submission_package as verify_submission_package
from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package as verify_trust_operations_hub_package


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
    audio_evidence: DomainDocument | None = None,
    trust_evidence: DomainDocument | None = None,
    public_trust_evidence: DomainDocument | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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
    audio_evidence: DomainDocument | None = None,
    trust_evidence: DomainDocument | None = None,
    public_trust_evidence: DomainDocument | None = None,
) -> DomainDocument:
    checks: list[ImplementationDocument] = []
    fingerprint: _InferenceType = {
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


def write_unified_command_center_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _runtime_zip_component(key: str, zip_path: Path | str, report_path: Path | str, verifier) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    fingerprint: _InferenceType = {"component_key": key, "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
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
    checks: list[ImplementationDocument] = []
    fingerprint: _InferenceType = {"component_key": "ga-readiness", "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    report_path = Path(report_path)
    checks.append(_check("ucc_ga-readiness_report_exists", report_path.exists() and report_path.is_file(), "GA readiness report exists."))
    if checks[-1]["status"] == "failed":
        return _component_finish("ga-readiness", fingerprint, checks)
    runtime_report = _verify_ga_readiness_report_core(report_path)
    external_report: ImplementationDocument = {}
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


from song_agent.domains.program import v142_uccv_readiness as _v142_uccv_readiness
from song_agent.domains.program.v142_uccv_readiness import _verify_ga_readiness_report_core as _verify_ga_readiness_report_core, _release_check_component as _release_check_component, _generic_report_component as _generic_report_component, _component_finish as _component_finish, _external_component_checks as _external_component_checks, _external_multi_component_checks as _external_multi_component_checks, _document_binding_checks as _document_binding_checks, _manifest_checks as _manifest_checks, _finish as _finish, _check as _check, _external_paths as _external_paths, _public_report as _public_report, _read_json_entry as _read_json_entry, _component_status as _component_status, _component_required as _component_required, _component_forced as _component_forced, _domain_requirement_check as _domain_requirement_check, _readiness_from_checks as _readiness_from_checks, _path_list as _path_list, _report_integrity_hash as _report_integrity_hash, _package_type_matches as _package_type_matches, _report_integrity_ok as _report_integrity_ok, _report_zip_sha256 as _report_zip_sha256, _report_zip_size as _report_zip_size, _report_manifest_hash as _report_manifest_hash, _manifest_binding_matches as _manifest_binding_matches, _component_id_from_report as _component_id_from_report, _safe_component_id as _safe_component_id, _fingerprint_items as _fingerprint_items, _public_fingerprint as _public_fingerprint, _integrity_ok as _integrity_ok, _integrity_hash as _integrity_hash, _semantic_hash as _semantic_hash, _is_safe_entry as _is_safe_entry, _redaction_check as _redaction_check, _sha256_bytes as _sha256_bytes
from song_agent.domains.program import v142_uccv_evidence as _v142_uccv_evidence
from song_agent.domains.program.v142_uccv_evidence import _sha256_path as _sha256_path

_v142_uccv_readiness.bind_globals(globals())
_v142_uccv_evidence.bind_globals(globals())
