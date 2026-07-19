# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_archive_verifier import UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_archive_package as verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_continuous_review_verifier import UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package
from song_agent.domains.program.unified_command_center_drift_response_verifier import UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package
from song_agent.domains.program.unified_command_center_handoff_verifier import UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_verifier import UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_package as verify_unified_command_center_package


UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "review-source.json",
    "evidence-index.json",
    "external-proof-index.json",
    "replay-plan.json",
    "replay-result.json",
    "evidence-narrative.json",
    "manual-checklist.json",
    "reviewer-guide.md",
    "README.txt",
    "verification-summaries/ucc.json",
    "verification-summaries/ucc-archive.json",
    "verification-summaries/ucc-handoff.json",
    "verification-summaries/continuous-review.json",
    "verification-summaries/drift-response.json",
    "verification-summaries/ga-readiness.json",
    "verification-summaries/release-check.json",
    "proof-summaries/signoff-binding-summary.json",
    "proof-summaries/change-request-binding-report.json",
}

ACCEPTANCE_REQUIRED_ENTRIES = {
    "manifest.json",
    "acceptance-report.json",
    "original-response-public.json",
    "response-verification-summary.json",
    "original-response-binding-summary.json",
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


def verify_unified_command_center_evidence_review_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_replay_passed: bool = False,
    ucc_zip_path: Path | str | None = None,
    ucc_verification_report_path: Path | str | None = None,
    archive_zip_path: Path | str | None = None,
    archive_verification_report_path: Path | str | None = None,
    handoff_zip_path: Path | str | None = None,
    handoff_verification_report_path: Path | str | None = None,
    continuous_review_zip_path: Path | str | None = None,
    continuous_review_verification_report_path: Path | str | None = None,
    drift_response_zip_path: Path | str | None = None,
    drift_response_verification_report_path: Path | str | None = None,
    drift_change_request_binding_report_path: Path | str | None = None,
    source_review_zip_path: Path | str | None = None,
    source_review_verification_report_path: Path | str | None = None,
    recheck_review_zip_path: Path | str | None = None,
    recheck_review_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    ga_readiness_report_path: Path | str | None = None,
    release_check_report_path: Path | str | None = None,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 256,
    max_entry_count: int = 200,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_review_zip_exists", False, "Evidence Review ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_review_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_review_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_review_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_review_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_review_raw_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("ucc_review_no_nested_zip", not nested, "Evidence Review ZIP does not contain nested ZIP files.", {"nested": nested}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_review_allowed_entries", not extra, "Evidence Review ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_review_required_entries", not missing, "Evidence Review ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            source = _read_json_entry(archive, "review-source.json")
            evidence_index = _read_json_entry(archive, "evidence-index.json")
            proof_index = _read_json_entry(archive, "external-proof-index.json")
            replay_plan = _read_json_entry(archive, "replay-plan.json")
            replay_result = _read_json_entry(archive, "replay-result.json")
            narrative = _read_json_entry(archive, "evidence-narrative.json")
            checklist = _read_json_entry(archive, "manual-checklist.json")
            summaries = {
                "ucc": _read_json_entry(archive, "verification-summaries/ucc.json"),
                "archive": _read_json_entry(archive, "verification-summaries/ucc-archive.json"),
                "handoff": _read_json_entry(archive, "verification-summaries/ucc-handoff.json"),
                "continuous_review": _read_json_entry(archive, "verification-summaries/continuous-review.json"),
                "drift_response": _read_json_entry(archive, "verification-summaries/drift-response.json"),
                "ga": _read_json_entry(archive, "verification-summaries/ga-readiness.json"),
                "release_check": _read_json_entry(archive, "verification-summaries/release-check.json"),
            }
            proof_summaries = {
                "signoff_binding": _read_json_entry(archive, "proof-summaries/signoff-binding-summary.json"),
                "cr_binding": _read_json_entry(archive, "proof-summaries/change-request-binding-report.json"),
            }
            summary.update({"center_id": manifest.get("center_id"), "review_id": manifest.get("review_id"), "manifest_hash": manifest.get("integrity_hash"), "replay_status": replay_result.get("status")})

            checks.extend(_manifest_checks(archive, manifest, name_set, REQUIRED_ENTRIES, "ucc_review"))
            checks.append(_check("ucc_review_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_review_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_review_source_integrity", source),
                ("ucc_review_evidence_index_integrity", evidence_index),
                ("ucc_review_external_proof_index_integrity", proof_index),
                ("ucc_review_replay_plan_integrity", replay_plan),
                ("ucc_review_replay_result_integrity", replay_result),
                ("ucc_review_narrative_integrity", narrative),
                ("ucc_review_manual_checklist_integrity", checklist),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            manifest_source = _as_document(manifest.get("source"))
            checks.extend(
                [
                    _check("ucc_review_source_hash_binding", manifest.get("source_hash") == source.get("source_hash") == evidence_index.get("source_hash") == proof_index.get("source_hash") == replay_plan.get("source_hash") == replay_result.get("source_hash") == narrative.get("source_hash") == checklist.get("source_hash"), "Review documents bind the same source hash."),
                    _check("ucc_review_manifest_source_binding", manifest_source.get("review_source_hash") == source.get("integrity_hash"), "Manifest binds review source."),
                    _check("ucc_review_manifest_evidence_index_binding", manifest_source.get("evidence_index_hash") == evidence_index.get("integrity_hash"), "Manifest binds evidence index."),
                    _check("ucc_review_manifest_external_proof_index_binding", manifest_source.get("external_proof_index_hash") == proof_index.get("integrity_hash"), "Manifest binds external proof index."),
                    _check("ucc_review_manifest_replay_plan_binding", manifest_source.get("replay_plan_hash") == replay_plan.get("integrity_hash"), "Manifest binds replay plan."),
                    _check("ucc_review_manifest_replay_result_binding", manifest_source.get("replay_result_hash") == replay_result.get("integrity_hash"), "Manifest binds replay result."),
                    _check("ucc_review_replay_steps_match_plan", _replay_steps_match(replay_plan, replay_result), "Replay result steps match replay plan."),
                ]
            )
            checks.extend(_summary_binding_checks(source, evidence_index, proof_index, summaries, proof_summaries))
            if require_replay_passed:
                checks.append(_check("ucc_review_replay_all_required_passed", replay_result.get("status") == "passed" and not _required_replay_failures(replay_plan, replay_result), "All required replay steps passed.", {"status": replay_result.get("status")}))
                checks.extend(
                    _runtime_replay_checks(
                        source,
                        replay_result,
                        ucc_zip_path=ucc_zip_path,
                        ucc_verification_report_path=ucc_verification_report_path,
                        archive_zip_path=archive_zip_path,
                        archive_verification_report_path=archive_verification_report_path,
                        handoff_zip_path=handoff_zip_path,
                        handoff_verification_report_path=handoff_verification_report_path,
                        continuous_review_zip_path=continuous_review_zip_path,
                        continuous_review_verification_report_path=continuous_review_verification_report_path,
                        drift_response_zip_path=drift_response_zip_path,
                        drift_response_verification_report_path=drift_response_verification_report_path,
                        drift_change_request_binding_report_path=drift_change_request_binding_report_path,
                        source_review_zip_path=source_review_zip_path,
                        source_review_verification_report_path=source_review_verification_report_path,
                        recheck_review_zip_path=recheck_review_zip_path,
                        recheck_review_verification_report_path=recheck_review_verification_report_path,
                        signoff_binding_path=signoff_binding_path,
                        ga_readiness_report_path=ga_readiness_report_path,
                        release_check_report_path=release_check_report_path,
                    )
                )
            elif strict:
                checks.extend(_external_presence_checks(source, ucc_verification_report_path, archive_verification_report_path, handoff_verification_report_path, continuous_review_verification_report_path, drift_response_verification_report_path, drift_change_request_binding_report_path, ga_readiness_report_path, release_check_report_path))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_review_zip_readable", False, "Evidence Review ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def verify_unified_command_center_evidence_review_acceptance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_accepted: bool = False,
    review_pack_path: Path | str | None = None,
    review_pack_verification_report_path: Path | str | None = None,
    response_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 16,
    max_uncompressed_size_mb: int = 64,
    max_entry_count: int = 50,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(
            checks,
            summary,
            _check("ucc_review_acceptance_zip_exists", False, "Evidence Review Acceptance ZIP exists."),
            package_type=UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE,
        )
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_review_acceptance_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_review_acceptance_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_review_acceptance_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_review_acceptance_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_review_acceptance_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            extra = sorted(name_set - ACCEPTANCE_REQUIRED_ENTRIES)
            missing = sorted(ACCEPTANCE_REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_review_acceptance_allowed_entries", not extra, "Acceptance ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_review_acceptance_required_entries", not missing, "Acceptance ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary, package_type=UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE)
            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "acceptance-report.json")
            public_response = _read_json_entry(archive, "original-response-public.json")
            response_summary = _read_json_entry(archive, "response-verification-summary.json")
            binding_summary = _read_json_entry(archive, "original-response-binding-summary.json")
            summary.update({"evidence_id": manifest.get("evidence_id"), "review_id": manifest.get("review_id"), "manifest_hash": manifest.get("integrity_hash"), "result": report.get("result")})
            checks.extend(_manifest_checks(archive, manifest, name_set, ACCEPTANCE_REQUIRED_ENTRIES, "ucc_review_acceptance"))
            checks.append(_check("ucc_review_acceptance_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_review_acceptance_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_review_acceptance_report_integrity", report),
                ("ucc_review_acceptance_public_response_integrity", public_response),
                ("ucc_review_acceptance_response_summary_integrity", response_summary),
                ("ucc_review_acceptance_binding_summary_integrity", binding_summary),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            source = _as_document(manifest.get("source"))
            checks.extend(
                [
                    _check("ucc_review_acceptance_report_binding", source.get("acceptance_report_hash") == report.get("integrity_hash"), "Manifest binds acceptance report."),
                    _check("ucc_review_acceptance_response_binding", report.get("response_public_hash") == public_response.get("integrity_hash") == response_summary.get("response_public_hash"), "Acceptance report binds public response."),
                    _check("ucc_review_acceptance_pack_binding", report.get("review_pack_zip_sha256") == binding_summary.get("review_pack_zip_sha256"), "Acceptance binds review pack ZIP."),
                    _check("ucc_review_acceptance_result", report.get("result") == "accepted" or not require_accepted, "Acceptance result is accepted when required.", {"result": report.get("result")}),
                ]
            )
            if require_accepted or strict:
                checks.extend(_acceptance_external_checks(report, response_summary, binding_summary, review_pack_path, review_pack_verification_report_path, response_verification_report_path))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_review_acceptance_zip_readable", False, "Evidence Review Acceptance ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, package_type=UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE)


def write_unified_command_center_evidence_review_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def write_unified_command_center_evidence_review_acceptance_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_evidence_review_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def unified_command_center_evidence_review_acceptance_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _runtime_replay_checks(source: ImplementationDocument, replay_result: ImplementationDocument, **paths: Any) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    source_map = _as_document(source.get("source"))
    step_reports: dict[str, ImplementationDocument] = {}

    def require_pair(step: str, zip_key: str, report_key: str, label: str) -> tuple[Path, Path] | None:
        zip_path = paths.get(zip_key)
        report_path = paths.get(report_key)
        if not zip_path:
            checks.append(_check(f"ucc_review_{step}_zip_required", False, f"{label} ZIP is required."))
            return None
        if not report_path:
            checks.append(_check(f"ucc_review_{step}_verification_required", False, f"{label} verification report is required."))
            return None
        zip_path = Path(zip_path)
        report_path = Path(report_path)
        checks.append(_check(f"ucc_review_{step}_zip_exists", zip_path.exists(), f"{label} ZIP exists."))
        checks.append(_check(f"ucc_review_{step}_verification_exists", report_path.exists(), f"{label} verification report exists."))
        if not zip_path.exists() or not report_path.exists():
            return None
        return zip_path, report_path

    pair = require_pair("ucc_external_binding", "ucc_zip_path", "ucc_verification_report_path", "UCC")
    if pair:
        runtime = verify_unified_command_center_package(pair[0], strict=True, release_check_report_path=paths.get("release_check_report_path"))
        checks.extend(_external_report_checks("ucc_review_ucc_external_binding", pair[0], pair[1], runtime, UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, source_map, "ucc"))
        step_reports["verify_ucc"] = runtime
    pair = require_pair("archive_external_binding", "archive_zip_path", "archive_verification_report_path", "UCC Archive")
    if pair:
        runtime = verify_unified_command_center_archive_package(pair[0], strict=True, require_signed=True, require_current_ucc=True, command_center_zip_path=paths.get("ucc_zip_path"), command_center_verification_report_path=paths.get("ucc_verification_report_path"), signoff_binding_path=paths.get("signoff_binding_path"))
        checks.extend(_external_report_checks("ucc_review_archive_external_binding", pair[0], pair[1], runtime, UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, source_map, "archive"))
        step_reports["verify_archive"] = runtime
    pair = require_pair("handoff_external_binding", "handoff_zip_path", "handoff_verification_report_path", "UCC Handoff")
    if pair:
        runtime = verify_unified_command_center_handoff_package(pair[0], strict=True, require_archive=True, archive_zip_path=paths.get("archive_zip_path"), archive_verification_report_path=paths.get("archive_verification_report_path"))
        checks.extend(_external_report_checks("ucc_review_handoff_external_binding", pair[0], pair[1], runtime, UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, source_map, "handoff"))
        step_reports["verify_handoff"] = runtime
    pair = require_pair("continuous_review_external_binding", "continuous_review_zip_path", "continuous_review_verification_report_path", "Continuous Review")
    if pair:
        runtime = verify_unified_command_center_continuous_review_package(pair[0], strict=True, require_clear=False, require_recovery_drill=False, require_current_review=True, archive_zip_path=paths.get("archive_zip_path"), archive_verification_report_path=paths.get("archive_verification_report_path"), handoff_zip_path=paths.get("handoff_zip_path"), handoff_verification_report_path=paths.get("handoff_verification_report_path"), command_center_zip_path=paths.get("ucc_zip_path"), command_center_verification_report_path=paths.get("ucc_verification_report_path"), signoff_binding_path=paths.get("signoff_binding_path"))
        checks.extend(_external_report_checks("ucc_review_continuous_review_external_binding", pair[0], pair[1], runtime, UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE, source_map, "continuous_review"))
        step_reports["verify_continuous_review"] = runtime
    if source_map.get("drift_response_zip_sha256") or paths.get("drift_response_zip_path"):
        pair = require_pair("drift_response_external_binding", "drift_response_zip_path", "drift_response_verification_report_path", "Drift Response")
        if pair:
            if not paths.get("drift_change_request_binding_report_path"):
                checks.append(_check("ucc_review_cr_proof_external_binding", False, "Drift Response CR proof is required."))
            runtime = verify_unified_command_center_drift_response_package(
                pair[0],
                strict=True,
                require_closed=True,
                require_recheck_clear=True,
                require_current_review=True,
                source_review_zip_path=paths.get("source_review_zip_path") or paths.get("continuous_review_zip_path"),
                source_review_verification_report_path=paths.get("source_review_verification_report_path") or paths.get("continuous_review_verification_report_path"),
                recheck_review_zip_path=paths.get("recheck_review_zip_path") or paths.get("continuous_review_zip_path"),
                recheck_review_verification_report_path=paths.get("recheck_review_verification_report_path") or paths.get("continuous_review_verification_report_path"),
                change_request_binding_report_path=paths.get("drift_change_request_binding_report_path"),
                archive_zip_path=paths.get("archive_zip_path"),
                archive_verification_report_path=paths.get("archive_verification_report_path"),
                handoff_zip_path=paths.get("handoff_zip_path"),
                handoff_verification_report_path=paths.get("handoff_verification_report_path"),
                command_center_zip_path=paths.get("ucc_zip_path"),
                command_center_verification_report_path=paths.get("ucc_verification_report_path"),
                signoff_binding_path=paths.get("signoff_binding_path"),
            )
            checks.extend(_external_report_checks("ucc_review_drift_response_external_binding", pair[0], pair[1], runtime, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE, source_map, "drift_response"))
            if paths.get("drift_change_request_binding_report_path"):
                checks.extend(_cr_proof_checks(paths.get("drift_change_request_binding_report_path"), source_map))
            step_reports["verify_drift_response"] = runtime
    checks.extend(_ga_release_check_external_checks(source_map, paths.get("ga_readiness_report_path"), paths.get("release_check_report_path")))
    checks.extend(_replay_runtime_match_checks(replay_result, step_reports))
    return checks


def _external_presence_checks(source: ImplementationDocument, *paths: Path | str | None) -> list[ImplementationDocument]:
    if source.get("status") == "not_applicable":
        return []
    missing = [index for index, path in enumerate(paths) if path is None]
    return [_check("ucc_review_external_evidence_present", not missing, "Strict review verification received external evidence paths.", {"missing_indexes": missing})]


def _external_report_checks(check_id: str, zip_path: Path, report_path: Path, runtime: ImplementationDocument, package_type: str, source_map: ImplementationDocument, prefix: str) -> list[ImplementationDocument]:
    external = _read_json_file(report_path)
    actual_sha = _sha256_path(zip_path)
    manifest_hash = _zip_manifest_hash(zip_path)
    return [
        _check(f"{check_id}_package_type", external.get("package_type") == package_type, "External verification report package type is valid."),
        _check(f"{check_id}_integrity", _integrity_ok(external), "External verification report integrity is valid."),
        _check(f"{check_id}_status", external.get("status") == "passed" and runtime.get("status") == "passed", "External and runtime verification passed.", {"external_status": external.get("status"), "runtime_status": runtime.get("status")}),
        _check(f"{check_id}_zip_sha256", source_map.get(f"{prefix}_zip_sha256") == actual_sha == external.get("zip_sha256") == runtime.get("zip_sha256"), "ZIP sha256 matches review source and verification reports."),
        _check(f"{check_id}_manifest_hash", source_map.get(f"{prefix}_manifest_hash") == manifest_hash == external.get("manifest_hash") == runtime.get("manifest_hash"), "Manifest hash matches review source and verification reports."),
        _check(f"{check_id}_verification_hash", source_map.get(f"{prefix}_verification_hash") == external.get("integrity_hash"), "Review source binds external verification report hash."),
    ]


def _cr_proof_checks(path: Path | str | None, source_map: ImplementationDocument) -> list[ImplementationDocument]:
    if not path:
        return [_check("ucc_review_cr_proof_external_binding", False, "External CR proof report is required.")]
    path = Path(path)
    if not path.exists():
        return [_check("ucc_review_cr_proof_external_binding", False, "External CR proof report exists.")]
    report = _read_json_file(path)
    return [
        _check("ucc_review_cr_proof_package_type", report.get("package_type") == UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, "CR proof package type is valid."),
        _check("ucc_review_cr_proof_integrity", _integrity_ok(report), "CR proof integrity is valid."),
        _check("ucc_review_cr_proof_external_binding", source_map.get("cr_binding_report_hash") == report.get("integrity_hash"), "Review source binds CR proof report hash."),
    ]


def _ga_release_check_external_checks(source_map: ImplementationDocument, ga_path: Path | str | None, release_check_path: Path | str | None) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    if source_map.get("ga_report_hash"):
        if not ga_path:
            checks.append(_check("ucc_review_ga_report_binding", False, "GA readiness report is required."))
        else:
            report = _read_json_file(Path(ga_path))
            checks.append(_check("ucc_review_ga_report_binding", source_map.get("ga_report_hash") == _integrity_or_stable(report) and str(report.get("status") or "") not in {"failed", "blocked"}, "GA readiness report matches review source."))
    if source_map.get("release_check_report_hash"):
        if not release_check_path:
            checks.append(_check("ucc_review_release_check_report_binding", False, "Release-check report is required."))
        else:
            report = _read_json_file(Path(release_check_path))
            checks.append(_check("ucc_review_release_check_report_binding", source_map.get("release_check_report_hash") == _integrity_or_stable(report) and bool(report.get("ok", False)), "Release-check report matches review source."))
    return checks


def _acceptance_external_checks(report: ImplementationDocument, response_summary: ImplementationDocument, binding_summary: ImplementationDocument, review_pack_path: Path | str | None, review_pack_verification_report_path: Path | str | None, response_verification_report_path: Path | str | None) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    if not review_pack_path:
        checks.append(_check("ucc_review_acceptance_review_pack_required", False, "Review Pack ZIP is required."))
    if not review_pack_verification_report_path:
        checks.append(_check("ucc_review_acceptance_review_pack_verification_required", False, "Review Pack verification report is required."))
    if not response_verification_report_path:
        checks.append(_check("ucc_review_acceptance_response_verification_required", False, "External response verification summary is required."))
    if any(check["status"] == "failed" for check in checks):
        return checks
    review_pack_path = _as_path(review_pack_path)
    review_verification = _read_json_file(_as_path(review_pack_verification_report_path))
    response_verification = _read_json_file(_as_path(response_verification_report_path))
    checks.extend(
        [
            _check("ucc_review_acceptance_review_pack_status", review_verification.get("status") == "passed", "Review Pack verification is passed."),
            _check("ucc_review_acceptance_review_pack_zip_binding", report.get("review_pack_zip_sha256") == _sha256_path(review_pack_path) == review_verification.get("zip_sha256") == binding_summary.get("review_pack_zip_sha256"), "Accepted evidence binds current Review Pack ZIP."),
            _check("ucc_review_acceptance_review_pack_manifest_binding", report.get("review_pack_manifest_hash") == review_verification.get("manifest_hash") == binding_summary.get("review_pack_manifest_hash"), "Accepted evidence binds Review Pack manifest."),
            _check("ucc_review_acceptance_response_verification_integrity", _integrity_ok(response_verification), "External response verification summary integrity is valid."),
            _check("ucc_review_acceptance_response_public_hash", response_summary.get("response_public_hash") == response_verification.get("response_public_hash") == report.get("response_public_hash"), "Accepted evidence binds original response public projection."),
            _check("ucc_review_acceptance_response_payload_hash", response_summary.get("response_payload_hash") == response_verification.get("response_payload_hash"), "Accepted evidence binds original response payload."),
        ]
    )
    return checks


def _summary_binding_checks(source: ImplementationDocument, evidence_index: ImplementationDocument, proof_index: ImplementationDocument, summaries: dict[str, ImplementationDocument], proofs: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    source_map = _as_document(source.get("source"))
    evidence_items = [row for row in evidence_index.get("items", []) if isinstance(row, dict)]
    proof_items = [row for row in proof_index.get("proofs", []) if isinstance(row, dict)]
    checks.append(_check("ucc_review_evidence_index_summary", evidence_index.get("summary", {}).get("required_count") == len([row for row in evidence_items if row.get("required")]), "Evidence index summary matches rows."))
    checks.append(_check("ucc_review_external_proof_index_summary", proof_index.get("summary", {}).get("proof_count") == len(proof_items), "External proof index summary matches rows."))
    for key, prefix in (("ucc", "ucc"), ("archive", "archive"), ("handoff", "handoff"), ("continuous_review", "continuous_review"), ("drift_response", "drift_response")):
        report = summaries.get(key) or {}
        expected = source_map.get(f"{prefix}_verification_hash")
        if expected:
            checks.append(_check(f"ucc_review_{key}_summary_binding", report.get("integrity_hash") == expected, f"{key} summary binds source verification hash."))
    if source_map.get("cr_binding_report_hash"):
        checks.append(_check("ucc_review_cr_proof_summary_binding", (proofs.get("cr_binding") or {}).get("integrity_hash") == source_map.get("cr_binding_report_hash"), "CR proof summary binds source hash."))
    return checks


def _replay_runtime_match_checks(replay_result: ImplementationDocument, step_reports: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
    by_step = {str(row.get("step_id")): row for row in replay_result.get("steps", []) if isinstance(row, dict)}
    for step_id, runtime in step_reports.items():
        row = by_step.get(step_id)
        if row is None:
            checks.append(_check(f"ucc_review_runtime_{step_id}_present", False, "Replay result contains runtime step."))
            continue
        checks.append(_check(f"ucc_review_runtime_{step_id}_status", row.get("status") == runtime.get("status") == "passed", "Runtime replay status matches packaged replay result."))
        checks.append(_check(f"ucc_review_runtime_{step_id}_verification_hash", row.get("verification_hash") == runtime.get("integrity_hash"), "Runtime replay verification hash matches packaged replay result."))
    return checks


def _replay_steps_match(plan: ImplementationDocument, result: ImplementationDocument) -> bool:
    planned = [str(row.get("step_id")) for row in plan.get("steps", []) if isinstance(row, dict)]
    actual = [str(row.get("step_id")) for row in result.get("steps", []) if isinstance(row, dict)]
    return planned == actual


def _required_replay_failures(plan: ImplementationDocument, result: ImplementationDocument) -> list[str]:
    required = {str(row.get("step_id")) for row in plan.get("steps", []) if isinstance(row, dict) and row.get("required")}
    return [str(row.get("step_id")) for row in result.get("steps", []) if isinstance(row, dict) and row.get("step_id") in required and row.get("status") != "passed"]


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], required: set[str], prefix: str) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = required - {"manifest.json"}
    effective = names - {"manifest.json"}
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if not rel or rel not in names:
            continue
        data = archive.read(rel)
        info = archive.getinfo(rel)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(rel)
    return [
        _check(f"{prefix}_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check(f"{prefix}_manifest_files_fixed", declared == expected, "Manifest files match fixed structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check(f"{prefix}_manifest_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
    ]


from song_agent.domains.program import v142_uccerv_readiness as _v142_uccerv_readiness
from song_agent.domains.program.v142_uccerv_readiness import (
    _redaction_check,
    _finish,
    _check,
    _read_json_entry,
    _read_json_file,
    _integrity_hash,
    _integrity_ok,
    _integrity_or_stable,
    _sha256_path,
    _sha256_bytes,
    _zip_manifest_hash,
    _is_safe_entry,
)

_v142_uccerv_readiness.bind_globals(globals())
