from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.quality.release_audio_baseline_governance_verifier import verify_release_audio_baseline_registry_package
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import verify_release_audio_quality_action_queue_signoff_archive_package
from song_agent.domains.quality.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package
from song_agent.domains.quality.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package
from song_agent.domains.quality.release_audio_regression_response_verifier import verify_release_audio_regression_response_package
from song_agent.domains.quality.release_audio_regression_verifier import verify_release_audio_regression_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash


RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE = "release_audio_command_center"
RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "release_audio_command_center_verification"
RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION = 1

COMPONENT_KEYS = (
    "certification",
    "timeline",
    "regression",
    "baseline_governance",
    "regression_response",
    "observatory",
    "action_queue",
    "action_queue_signoff",
)

REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "command-center.json",
    "command-center-report.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "gap-plan.json",
    "runbook.json",
    "runbook-results.json",
    *{f"evidence-fingerprints/{key}.json" for key in COMPONENT_KEYS},
    *{f"verification-summaries/{key}-verification.json" for key in COMPONENT_KEYS},
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


def verify_release_audio_command_center_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    certification_zip_path: Path | str | None = None,
    certification_verification_report_path: Path | str | None = None,
    timeline_zip_path: Path | str | None = None,
    timeline_verification_report_path: Path | str | None = None,
    regression_zip_path: Path | str | None = None,
    regression_verification_report_path: Path | str | None = None,
    baseline_registry_zip_path: Path | str | None = None,
    baseline_registry_verification_report_path: Path | str | None = None,
    regression_response_zip_path: Path | str | None = None,
    regression_response_verification_report_path: Path | str | None = None,
    observatory_zip_path: Path | str | None = None,
    observatory_verification_report_path: Path | str | None = None,
    action_queue_zip_path: Path | str | None = None,
    action_queue_verification_report_path: Path | str | None = None,
    action_queue_signoff_archive_path: Path | str | None = None,
    action_queue_signoff_verification_report_path: Path | str | None = None,
    evidence_root: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_path": str(zip_path), "zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None, "release_ids": []}
    external_paths = {
        "certification": (certification_zip_path, certification_verification_report_path),
        "timeline": (timeline_zip_path, timeline_verification_report_path),
        "regression": (regression_zip_path, regression_verification_report_path),
        "baseline_governance": (baseline_registry_zip_path, baseline_registry_verification_report_path),
        "regression_response": (regression_response_zip_path, regression_response_verification_report_path),
        "observatory": (observatory_zip_path, observatory_verification_report_path),
        "action_queue": (action_queue_zip_path, action_queue_verification_report_path),
        "action_queue_signoff": (action_queue_signoff_archive_path, action_queue_signoff_verification_report_path),
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_command_center_zip_exists", False, "Command Center ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_command_center_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_command_center_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_command_center_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_command_center_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("release_audio_command_center_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            checks.append(_check("release_audio_command_center_no_nested_zip", not nested, "ZIP contains no nested ZIP entries.", {"nested": nested}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)
            extra_entries = sorted(set(names) - REQUIRED_ENTRIES)
            missing_entries = sorted(REQUIRED_ENTRIES - set(names))
            checks.append(_check("release_audio_command_center_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Command Center entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_command_center_zip_expected_entries", not missing_entries, "ZIP contains all required Command Center entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            command_center = _read_json_entry(archive, "command-center.json")
            report = _read_json_entry(archive, "command-center-report.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            gap_plan = _read_json_entry(archive, "gap-plan.json")
            runbook = _read_json_entry(archive, "runbook.json")
            runbook_results = _read_json_entry(archive, "runbook-results.json")
            fingerprints = {key: _read_json_entry(archive, f"evidence-fingerprints/{key}.json") for key in COMPONENT_KEYS}
            verification_summaries = {key: _read_json_entry(archive, f"verification-summaries/{key}-verification.json") for key in COMPONENT_KEYS}

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_ids"] = [str(report.get("release_id") or command_center.get("release_id") or "")]
            summary["readiness"] = report.get("readiness")
            summary["report_status"] = report.get("status")

            checks.extend(_manifest_checks(archive, manifest, set(names)))
            checks.append(_check("release_audio_command_center_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE, "Manifest package_type is release_audio_command_center."))
            checks.append(_check("release_audio_command_center_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_command_center_manifest_integrity", manifest),
                ("release_audio_command_center_command_integrity", command_center),
                ("release_audio_command_center_report_integrity", report),
                ("release_audio_command_center_inventory_integrity", inventory),
                ("release_audio_command_center_readiness_integrity", readiness),
                ("release_audio_command_center_gap_plan_integrity", gap_plan),
                ("release_audio_command_center_runbook_integrity", runbook),
                ("release_audio_command_center_runbook_results_integrity", runbook_results),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            for key in COMPONENT_KEYS:
                checks.append(_check(f"release_audio_command_center_{key}_fingerprint_integrity", _integrity_ok(fingerprints[key]), f"{key} fingerprint integrity hash is valid."))
                checks.append(_check(f"release_audio_command_center_{key}_verification_summary_integrity", _integrity_ok(verification_summaries[key]), f"{key} verification summary integrity hash is valid."))
            checks.extend(_document_binding_checks(manifest, command_center, report, inventory, readiness, gap_plan, runbook, runbook_results, fingerprints, verification_summaries, require_ready=require_ready))
            for key in COMPONENT_KEYS:
                component_status = _component_status(inventory, key)
                if require_ready or component_status == "ready":
                    checks.extend(
                        _external_component_checks(
                            key,
                            fingerprints[key],
                            verification_summaries[key],
                            external_paths=external_paths,
                            evidence_root=evidence_root,
                        )
                    )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_command_center_zip_readable", False, "Command Center ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_command_center_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_command_center_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def verify_release_audio_command_center_component(
    key: str,
    zip_path: Path | str | None,
    verification_report_path: Path | str | None,
    *,
    certification_zip_path: Path | str | None = None,
    certification_verification_report_path: Path | str | None = None,
    timeline_zip_path: Path | str | None = None,
    timeline_verification_report_path: Path | str | None = None,
    regression_zip_path: Path | str | None = None,
    regression_verification_report_path: Path | str | None = None,
    baseline_registry_zip_path: Path | str | None = None,
    baseline_registry_verification_report_path: Path | str | None = None,
    regression_response_zip_path: Path | str | None = None,
    regression_response_verification_report_path: Path | str | None = None,
    observatory_zip_path: Path | str | None = None,
    observatory_verification_report_path: Path | str | None = None,
    action_queue_zip_path: Path | str | None = None,
    action_queue_verification_report_path: Path | str | None = None,
    action_queue_signoff_archive_path: Path | str | None = None,
    action_queue_signoff_verification_report_path: Path | str | None = None,
    evidence_root: Path | str | None = None,
) -> dict[str, Any]:
    if key not in COMPONENT_KEYS:
        raise ValueError(f"Unknown Command Center component: {key}")
    checks: list[dict[str, Any]] = []
    fingerprint: dict[str, Any] = {
        "component_key": key,
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": None,
        "runtime_verification_status": None,
        "runtime_manifest_hash": None,
        "runtime_failed_count": 0,
        "runtime_blockers": [],
    }
    if not zip_path or not verification_report_path:
        checks.append(_check(f"release_audio_command_center_{key}_external_required", False, f"{key} external ZIP and verification report are required."))
        return _component_finish(key, fingerprint, checks)
    zip_path = Path(zip_path)
    report_path = Path(verification_report_path)
    checks.append(_check(f"release_audio_command_center_{key}_zip_exists", zip_path.exists() and zip_path.is_file(), f"{key} ZIP exists."))
    checks.append(_check(f"release_audio_command_center_{key}_verification_report_exists", report_path.exists() and report_path.is_file(), f"{key} verification report exists."))
    if any(check["status"] == "failed" for check in checks):
        return _component_finish(key, fingerprint, checks)

    external_paths = _component_external_paths(
        certification_zip_path=certification_zip_path,
        certification_verification_report_path=certification_verification_report_path,
        timeline_zip_path=timeline_zip_path,
        timeline_verification_report_path=timeline_verification_report_path,
        regression_zip_path=regression_zip_path,
        regression_verification_report_path=regression_verification_report_path,
        baseline_registry_zip_path=baseline_registry_zip_path,
        baseline_registry_verification_report_path=baseline_registry_verification_report_path,
        regression_response_zip_path=regression_response_zip_path,
        regression_response_verification_report_path=regression_response_verification_report_path,
        observatory_zip_path=observatory_zip_path,
        observatory_verification_report_path=observatory_verification_report_path,
        action_queue_zip_path=action_queue_zip_path,
        action_queue_verification_report_path=action_queue_verification_report_path,
        action_queue_signoff_archive_path=action_queue_signoff_archive_path,
        action_queue_signoff_verification_report_path=action_queue_signoff_verification_report_path,
    )
    external_paths[key] = (zip_path, report_path)
    try:
        external_report = read_json(report_path)
    except Exception as exc:
        checks.append(_check(f"release_audio_command_center_{key}_verification_report_readable", False, f"{key} verification report is readable.", {"error": str(exc)}))
        return _component_finish(key, fingerprint, checks)
    try:
        runtime = _runtime_verify(key, zip_path, external_paths=external_paths, evidence_root=evidence_root)
    except Exception as exc:
        runtime = {"status": "failed", "manifest_hash": None, "blockers": [sanitize_sensitive_text(str(exc))]}

    runtime_blockers = [str(item) for item in runtime.get("blockers", []) if str(item)]
    fingerprint.update(
        {
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": external_report.get("integrity_hash"),
            "verification_status": external_report.get("status"),
            "runtime_verification_status": runtime.get("status"),
            "runtime_manifest_hash": runtime.get("manifest_hash"),
            "runtime_failed_count": len(runtime_blockers),
            "runtime_blockers": runtime_blockers,
        }
    )
    checks.extend(
        [
            _check(f"release_audio_command_center_{key}_external_report_integrity", _integrity_ok(external_report), f"{key} external verification report integrity hash is valid."),
            _check(f"release_audio_command_center_{key}_external_status", external_report.get("status") == "passed", f"{key} external verification report status is passed.", {"external_status": external_report.get("status")}),
            _check(f"release_audio_command_center_{key}_external_zip_binding", external_report.get("zip_sha256") == fingerprint["zip_sha256"], f"{key} external verification report matches current ZIP sha256."),
            _check(f"release_audio_command_center_{key}_external_manifest_binding", external_report.get("manifest_hash") == runtime.get("manifest_hash"), f"{key} external verification report matches current manifest hash."),
            _check(f"release_audio_command_center_{key}_runtime_status", runtime.get("status") == "passed", f"{key} runtime verification is passed.", {"runtime_status": runtime.get("status"), "runtime_blockers": runtime_blockers}),
        ]
    )
    return _component_finish(key, fingerprint, checks, runtime=runtime, external_report=external_report)


def _external_component_checks(
    key: str,
    fingerprint: ImplementationDocument,
    verification_summary: ImplementationDocument,
    *,
    external_paths: dict[str, tuple[Path | str | None, Path | str | None]],
    evidence_root: Path | str | None,
) -> list[ImplementationDocument]:
    zip_value, report_value = external_paths[key]
    if not zip_value or not report_value:
        return [_check(f"release_audio_command_center_{key}_external_required", False, f"{key} external ZIP and verification report are required.")]
    runtime_component = verify_release_audio_command_center_component(
        key,
        zip_value,
        report_value,
        certification_zip_path=external_paths["certification"][0],
        certification_verification_report_path=external_paths["certification"][1],
        timeline_zip_path=external_paths["timeline"][0],
        timeline_verification_report_path=external_paths["timeline"][1],
        regression_zip_path=external_paths["regression"][0],
        regression_verification_report_path=external_paths["regression"][1],
        baseline_registry_zip_path=external_paths["baseline_governance"][0],
        baseline_registry_verification_report_path=external_paths["baseline_governance"][1],
        regression_response_zip_path=external_paths["regression_response"][0],
        regression_response_verification_report_path=external_paths["regression_response"][1],
        observatory_zip_path=external_paths["observatory"][0],
        observatory_verification_report_path=external_paths["observatory"][1],
        action_queue_zip_path=external_paths["action_queue"][0],
        action_queue_verification_report_path=external_paths["action_queue"][1],
        action_queue_signoff_archive_path=external_paths["action_queue_signoff"][0],
        action_queue_signoff_verification_report_path=external_paths["action_queue_signoff"][1],
        evidence_root=evidence_root,
    )
    external_report = runtime_component.get("external_report") if isinstance(runtime_component.get("external_report"), dict) else {}
    current_fingerprint = runtime_component.get("fingerprint") if isinstance(runtime_component.get("fingerprint"), dict) else {}
    public_summary = _public_verification_summary(key, external_report)
    return list(runtime_component.get("checks") or []) + [
        _check(
            f"release_audio_command_center_{key}_fingerprint_binding",
            (
                fingerprint.get("zip_sha256") == current_fingerprint.get("zip_sha256")
                and int(fingerprint.get("zip_size_bytes") or -1) == int(current_fingerprint.get("zip_size_bytes") or -2)
                and fingerprint.get("manifest_hash") == current_fingerprint.get("manifest_hash")
                and fingerprint.get("verification_report_hash") == current_fingerprint.get("verification_report_hash")
                and fingerprint.get("verification_status") == current_fingerprint.get("verification_status")
                and fingerprint.get("runtime_verification_status") == current_fingerprint.get("runtime_verification_status")
                and fingerprint.get("runtime_manifest_hash") == current_fingerprint.get("runtime_manifest_hash")
                and int(fingerprint.get("runtime_failed_count") or 0) == int(current_fingerprint.get("runtime_failed_count") or 0)
                and sorted(str(item) for item in fingerprint.get("runtime_blockers", []) if str(item)) == sorted(str(item) for item in current_fingerprint.get("runtime_blockers", []) if str(item))
            ),
            f"{key} Command Center fingerprint matches external evidence.",
            {"expected": current_fingerprint},
        ),
        _check(
            f"release_audio_command_center_{key}_verification_summary_binding",
            _semantic_hash(verification_summary) == _semantic_hash(public_summary),
            f"{key} Command Center verification summary matches external report projection.",
        ),
    ]


def _runtime_verify(key: str, zip_path: Path, *, external_paths: dict[str, tuple[Path | str | None, Path | str | None]], evidence_root: Path | str | None) -> ImplementationDocument:
    cert_zip, cert_report = external_paths["certification"]
    timeline_zip, timeline_report = external_paths["timeline"]
    regression_zip, regression_report = external_paths["regression"]
    observatory_zip, observatory_report = external_paths["observatory"]
    queue_zip, queue_report = external_paths["action_queue"]
    if key == "certification":
        return verify_release_audio_certification_package(zip_path, strict=True, require_passed=True, require_signed=True, require_real_audio=True, require_manual_review=True, require_remediation_when_needed=True)
    if key == "timeline":
        return verify_release_audio_timeline_package(zip_path, strict=True, require_passed=True, require_signed=True, require_real_audio=True, require_manual_review=True, require_current_certification=True, release_audio_certification_path=cert_zip, release_audio_certification_verification_report_path=cert_report)
    if key == "regression":
        # Baseline evidence is optional here because the regression package may cover a
        # different baseline release. The regression verifier still checks its own fixed structure.
        return verify_release_audio_regression_package(zip_path, strict=True, require_passed=True, require_signed=True)
    if key == "baseline_governance":
        return verify_release_audio_baseline_registry_package(zip_path, strict=True, require_active=True)
    if key == "regression_response":
        return verify_release_audio_regression_response_package(zip_path, strict=True, require_closed=True, require_signed=True, require_regression_current=False, release_audio_regression_path=regression_zip, release_audio_regression_verification_report_path=regression_report)
    if key == "observatory":
        return verify_release_audio_quality_observatory_package(zip_path, strict=True, require_current_evidence=True, evidence_root=evidence_root, require_no_critical_risk=True)
    if key == "action_queue":
        return verify_release_audio_quality_action_queue_package(zip_path, strict=True, require_current_observatory=True, observatory_zip_path=observatory_zip, observatory_verification_report_path=observatory_report, evidence_root=evidence_root, require_no_blocking=False)
    if key == "action_queue_signoff":
        return verify_release_audio_quality_action_queue_signoff_archive_package(zip_path, strict=True, require_signed=True, require_current_queue=True, queue_zip_path=queue_zip, queue_verification_report_path=queue_report, observatory_zip_path=observatory_zip, observatory_verification_report_path=observatory_report, evidence_root=evidence_root, require_no_unresolved_manual=True)
    raise ValueError(f"Unknown Command Center component: {key}")


def _component_external_paths(
    *,
    certification_zip_path: Path | str | None = None,
    certification_verification_report_path: Path | str | None = None,
    timeline_zip_path: Path | str | None = None,
    timeline_verification_report_path: Path | str | None = None,
    regression_zip_path: Path | str | None = None,
    regression_verification_report_path: Path | str | None = None,
    baseline_registry_zip_path: Path | str | None = None,
    baseline_registry_verification_report_path: Path | str | None = None,
    regression_response_zip_path: Path | str | None = None,
    regression_response_verification_report_path: Path | str | None = None,
    observatory_zip_path: Path | str | None = None,
    observatory_verification_report_path: Path | str | None = None,
    action_queue_zip_path: Path | str | None = None,
    action_queue_verification_report_path: Path | str | None = None,
    action_queue_signoff_archive_path: Path | str | None = None,
    action_queue_signoff_verification_report_path: Path | str | None = None,
) -> dict[str, tuple[Path | str | None, Path | str | None]]:
    return {
        "certification": (certification_zip_path, certification_verification_report_path),
        "timeline": (timeline_zip_path, timeline_verification_report_path),
        "regression": (regression_zip_path, regression_verification_report_path),
        "baseline_governance": (baseline_registry_zip_path, baseline_registry_verification_report_path),
        "regression_response": (regression_response_zip_path, regression_response_verification_report_path),
        "observatory": (observatory_zip_path, observatory_verification_report_path),
        "action_queue": (action_queue_zip_path, action_queue_verification_report_path),
        "action_queue_signoff": (action_queue_signoff_archive_path, action_queue_signoff_verification_report_path),
    }


def _component_finish(
    key: str,
    fingerprint: ImplementationDocument,
    checks: list[ImplementationDocument],
    *,
    runtime: ImplementationDocument | None = None,
    external_report: ImplementationDocument | None = None,
) -> ImplementationDocument:
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    runtime = runtime if isinstance(runtime, dict) else {}
    external_report = external_report if isinstance(external_report, dict) else {}
    if "integrity_hash" not in fingerprint:
        fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    result = {
        "component_key": key,
        "status": "passed" if not blockers else "failed",
        "readiness": "ready" if not blockers else _component_readiness_from_checks(checks),
        "fingerprint": fingerprint,
        "checks": checks,
        "blockers": blockers,
        "runtime_report": _public_runtime_report(runtime),
        "external_report": external_report,
    }
    result["integrity_hash"] = _integrity_hash(result)
    return result


def _public_runtime_report(report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    public_summary = {key: value for key, value in summary.items() if key not in {"zip_path"}}
    public = {
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "blockers": report.get("blockers", []),
        "summary": public_summary,
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _component_readiness_from_checks(checks: list[ImplementationDocument]) -> str:
    failed_ids = [str(check.get("check_id") or "") for check in checks if check.get("status") == "failed"]
    if any(check_id.endswith("_external_required") or check_id.endswith("_zip_exists") or check_id.endswith("_verification_report_exists") for check_id in failed_ids):
        return "missing"
    if any(check_id.endswith("_external_report_integrity") or check_id.endswith("_external_status") for check_id in failed_ids):
        return "verification_failed"
    if any(check_id.endswith("_external_zip_binding") or check_id.endswith("_external_manifest_binding") for check_id in failed_ids):
        return "stale"
    if any(check_id.endswith("_runtime_status") for check_id in failed_ids):
        return "runtime_failed"
    return "blocked"


def _document_binding_checks(
    manifest: ImplementationDocument,
    command_center: ImplementationDocument,
    report: ImplementationDocument,
    inventory: ImplementationDocument,
    readiness: ImplementationDocument,
    gap_plan: ImplementationDocument,
    runbook: ImplementationDocument,
    runbook_results: ImplementationDocument,
    fingerprints: dict[str, ImplementationDocument],
    verification_summaries: dict[str, ImplementationDocument],
    *,
    require_ready: bool,
) -> list[ImplementationDocument]:
    component_by_key = {str(row.get("component_key")): row for row in inventory.get("components", []) if isinstance(row, dict)}
    source_hash = report.get("source_hash")
    doc_hashes = report.get("document_hashes") if isinstance(report.get("document_hashes"), dict) else {}
    checks = [
        _check("release_audio_command_center_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds report."),
        _check("release_audio_command_center_manifest_inventory_binding", manifest.get("evidence_inventory_hash") == inventory.get("integrity_hash"), "Manifest binds inventory."),
        _check("release_audio_command_center_manifest_readiness_binding", manifest.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Manifest binds readiness matrix."),
        _check("release_audio_command_center_manifest_gap_plan_binding", manifest.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Manifest binds gap plan."),
        _check("release_audio_command_center_manifest_runbook_binding", manifest.get("runbook_hash") == runbook.get("integrity_hash"), "Manifest binds runbook."),
        _check("release_audio_command_center_manifest_runbook_results_binding", manifest.get("runbook_results_hash") == runbook_results.get("integrity_hash"), "Manifest binds runbook results."),
        _check("release_audio_command_center_source_hash_binding", source_hash and manifest.get("source_hash") == source_hash and command_center.get("source_hash") == source_hash and inventory.get("source_hash") == source_hash and readiness.get("source_hash") == source_hash and gap_plan.get("source_hash") == source_hash and runbook.get("source_hash") == source_hash, "Command Center documents bind the same source hash."),
        _check("release_audio_command_center_report_document_hashes", doc_hashes.get("command_center") == command_center.get("integrity_hash") and doc_hashes.get("evidence_inventory") == inventory.get("integrity_hash") and doc_hashes.get("readiness_matrix") == readiness.get("integrity_hash") and doc_hashes.get("gap_plan") == gap_plan.get("integrity_hash") and doc_hashes.get("runbook") == runbook.get("integrity_hash") and doc_hashes.get("runbook_results") == runbook_results.get("integrity_hash"), "Report binds all Command Center documents."),
    ]
    for key in COMPONENT_KEYS:
        component = component_by_key.get(key, {})
        checks.append(_check(f"release_audio_command_center_{key}_inventory_fingerprint_binding", _semantic_hash(component.get("fingerprint") or {}) == _semantic_hash(fingerprints[key]), f"{key} inventory fingerprint matches sidecar."))
        checks.append(_check(f"release_audio_command_center_{key}_inventory_verification_summary_binding", _semantic_hash(component.get("verification_summary") or {}) == _semantic_hash(verification_summaries[key]), f"{key} inventory verification summary matches sidecar."))
    required_blocked = [row.get("component_key") for row in readiness.get("rows", []) if isinstance(row, dict) and row.get("required") and row.get("readiness") != "ready"]
    checks.append(_check("release_audio_command_center_readiness_counts", (readiness.get("summary") or {}).get("blocked_count") == len(required_blocked), "Readiness summary matches required blocked rows.", {"blocked": required_blocked}))
    if require_ready:
        checks.append(_check("release_audio_command_center_require_ready", report.get("status") == "passed" and report.get("readiness") == "ready" and not required_blocked, "Command Center is ready when required.", {"blocked": required_blocked}))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    mismatches = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = archive.getinfo(path)
        data = archive.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_command_center_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("release_audio_command_center_manifest_declares_files", declared == effective_names, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective_names), "undeclared": sorted(effective_names - declared)}),
        _check("release_audio_command_center_manifest_fixed_files", declared == expected_files, "Manifest files match fixed Command Center structure.", {"extra": sorted(declared - expected_files), "missing": sorted(expected_files - declared)}),
        _check("release_audio_command_center_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("release_audio_command_center_manifest_zip_entries_untrusted", True, "manifest.zip.entries is not used as an allow-list."),
    ]


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    public_summary = {key: value for key, value in summary.items() if key != "zip_path"}
    report = {
        "package_type": RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**public_summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
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


def _component_required(inventory: ImplementationDocument, key: str) -> bool:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return bool(row.get("required"))
    return False


def _component_status(inventory: ImplementationDocument, key: str) -> str:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return str(row.get("status") or "")
    return ""


def _public_verification_summary(component_key: str, report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    public = {
        "component_key": component_key,
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "original_integrity_hash": report.get("integrity_hash"),
        "summary": {key: value for key, value in summary.items() if key != "zip_path"},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


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
    return _check("release_audio_command_center_redaction", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})


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
