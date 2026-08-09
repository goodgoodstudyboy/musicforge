from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.quality.release_audio_certification_verifier import RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE, verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.delivery.releases import stable_hash as stable_hash


RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE = "release_audio_timeline"
RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE = "release_audio_timeline_verification"
RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "audio-timeline-report.json",
    "track-timeline-index.json",
    "event-ledger.jsonl",
    "quality-trend.json",
    "issue-taxonomy.json",
    "risk-register.json",
    "evidence-bindings.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"timeline-signoff.json"}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_timeline_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_passed: bool = False,
    require_signed: bool = False,
    require_real_audio: bool = False,
    require_manual_review: bool = False,
    require_current_certification: bool = False,
    release_audio_certification_path: Path | str | None = None,
    release_audio_certification_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_path": zip_path.name,
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "release_id": None,
        "timeline_id": None,
        "track_count": 0,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_timeline_zip_exists", False, "Release Audio Timeline ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_timeline_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_timeline_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_timeline_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_timeline_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_timeline_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            expected_entries = set(REQUIRED_ENTRIES)
            if "timeline-signoff.json" in names:
                expected_entries.add("timeline-signoff.json")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("release_audio_timeline_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Release Audio Timeline entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_timeline_zip_expected_entries", not missing_entries, "ZIP contains all expected Release Audio Timeline entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(zf, "manifest.json")
            report = _read_json_entry(zf, "audio-timeline-report.json")
            track_index = _read_json_entry(zf, "track-timeline-index.json")
            events = _read_jsonl_entry(zf, "event-ledger.jsonl")
            trend = _read_json_entry(zf, "quality-trend.json")
            taxonomy = _read_json_entry(zf, "issue-taxonomy.json")
            risks = _read_json_entry(zf, "risk-register.json")
            bindings = _read_json_entry(zf, "evidence-bindings.json")
            signoff = _read_json_entry(zf, "timeline-signoff.json") if "timeline-signoff.json" in names else None

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_id"] = manifest.get("release_id") or report.get("release_id")
            summary["timeline_id"] = manifest.get("timeline_id") or report.get("timeline_id")
            summary["track_count"] = int((track_index.get("summary") or {}).get("track_count") or 0)

            checks.extend(_manifest_checks(zf, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_timeline_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE, "Manifest package_type is release_audio_timeline."))
            checks.append(_check("release_audio_timeline_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_timeline_manifest_integrity", manifest),
                ("release_audio_timeline_report_integrity", report),
                ("release_audio_timeline_track_index_integrity", track_index),
                ("release_audio_timeline_quality_trend_integrity", trend),
                ("release_audio_timeline_issue_taxonomy_integrity", taxonomy),
                ("release_audio_timeline_risk_register_integrity", risks),
                ("release_audio_timeline_evidence_bindings_integrity", bindings),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))

            checks.extend(_document_binding_checks(manifest, report, track_index, events, trend, taxonomy, risks, bindings))
            checks.extend(_event_chain_checks(events))
            checks.extend(_derived_document_checks(report, track_index, events, trend, taxonomy, risks))

            if require_passed:
                checks.append(_check("release_audio_timeline_report_passed", report.get("status") == "passed", "Timeline report is passed."))
            matrix_summary = _as_document(track_index.get("summary"))
            track_count = int(matrix_summary.get("track_count") or 0)
            if require_real_audio:
                checks.append(_check("release_audio_timeline_real_audio_complete", track_count > 0 and int(matrix_summary.get("real_audio_review_count") or 0) == track_count and int(matrix_summary.get("test_fake_count") or 0) == 0, "All timeline tracks use release-ready real audio."))
            if require_manual_review:
                checks.append(_check("release_audio_timeline_manual_review_complete", track_count > 0 and int(matrix_summary.get("manual_review_count") or 0) >= track_count, "All timeline tracks have manual review evidence."))

            checks.extend(_certification_binding_checks(bindings, report, require_current_certification=require_current_certification, certification_zip_path=release_audio_certification_path, certification_report_path=release_audio_certification_verification_report_path))
            checks.extend(_signoff_checks(signoff, manifest, report, track_index, events, trend, taxonomy, risks, bindings, require_signed=require_signed))
            checks.append(_redaction_check(zf, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_timeline_zip_readable", False, "Release Audio Timeline ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_timeline_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_timeline_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _document_binding_checks(
    manifest: ImplementationDocument,
    report: ImplementationDocument,
    track_index: ImplementationDocument,
    events: list[ImplementationDocument],
    trend: ImplementationDocument,
    taxonomy: ImplementationDocument,
    risks: ImplementationDocument,
    bindings: ImplementationDocument,
) -> list[ImplementationDocument]:
    ledger_hash = _event_ledger_hash(events)
    same_source = manifest.get("source_hash") == report.get("source_hash") == track_index.get("source_hash") == trend.get("source_hash") == taxonomy.get("source_hash") == risks.get("source_hash") == bindings.get("source_hash")
    return [
        _check("release_audio_timeline_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds timeline report."),
        _check("release_audio_timeline_manifest_track_index_binding", manifest.get("track_index_hash") == track_index.get("integrity_hash"), "Manifest binds track index."),
        _check("release_audio_timeline_manifest_ledger_binding", manifest.get("event_ledger_hash") == ledger_hash, "Manifest binds event ledger."),
        _check("release_audio_timeline_manifest_trend_binding", manifest.get("quality_trend_hash") == trend.get("integrity_hash"), "Manifest binds quality trend."),
        _check("release_audio_timeline_manifest_taxonomy_binding", manifest.get("issue_taxonomy_hash") == taxonomy.get("integrity_hash"), "Manifest binds issue taxonomy."),
        _check("release_audio_timeline_manifest_risk_binding", manifest.get("risk_register_hash") == risks.get("integrity_hash"), "Manifest binds risk register."),
        _check("release_audio_timeline_manifest_evidence_binding", manifest.get("evidence_bindings_hash") == bindings.get("integrity_hash"), "Manifest binds evidence bindings."),
        _check("release_audio_timeline_source_binding", same_source, "Timeline documents bind the same source hash."),
        _check("release_audio_timeline_report_ledger_binding", report.get("event_ledger_hash") == ledger_hash, "Timeline report binds event ledger."),
    ]


def _event_chain_checks(events: list[ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    ids = [str(event.get("event_id") or "") for event in events]
    checks.append(_check("release_audio_timeline_events_present", bool(events), "Timeline event ledger is present."))
    checks.append(_check("release_audio_timeline_event_ids_unique", len(ids) == len(set(ids)) and all(ids), "Timeline event ids are unique and present."))
    previous_hash: str | None = None
    chain_ok = True
    payload_ok = True
    hash_ok = True
    redaction_ok = True
    for event in events:
        if event.get("previous_event_hash") != previous_hash:
            chain_ok = False
        payload = _as_document(event.get("payload"))
        if event.get("payload_hash") != stable_hash(payload):
            payload_ok = False
        expected_hash = _event_hash(event)
        if event.get("event_hash") != expected_hash:
            hash_ok = False
        previous_hash = str(event.get("event_hash") or "")
        if _SENSITIVE_TEXT_RE.search(json.dumps(event, ensure_ascii=False)):
            redaction_ok = False
    checks.append(_check("release_audio_timeline_event_chain", chain_ok, "Timeline event hash chain is continuous."))
    checks.append(_check("release_audio_timeline_event_payload_hashes", payload_ok, "Timeline event payload hashes are valid."))
    checks.append(_check("release_audio_timeline_event_hashes", hash_ok, "Timeline event hashes are valid."))
    checks.append(_check("release_audio_timeline_event_redaction", redaction_ok, "Timeline events contain no obvious secrets or local paths."))
    return checks


def _derived_document_checks(report: ImplementationDocument, track_index: ImplementationDocument, events: list[ImplementationDocument], trend: ImplementationDocument, taxonomy: ImplementationDocument, risks: ImplementationDocument) -> list[ImplementationDocument]:
    derived = _derive_from_events(report.get("release_id"), report.get("timeline_id"), events, source_hash=report.get("source_hash"))
    return [
        _check("release_audio_timeline_track_index_semantics", _semantic_hash(track_index.get("tracks")) == _semantic_hash(derived["track_index"].get("tracks")) and _semantic_hash(track_index.get("summary")) == _semantic_hash(derived["track_index"].get("summary")), "Track timeline index matches event ledger."),
        _check("release_audio_timeline_quality_trend_semantics", _semantic_hash(trend.get("summary")) == _semantic_hash(derived["trend"].get("summary")) and _semantic_hash(trend.get("trend_points")) == _semantic_hash(derived["trend"].get("trend_points")), "Quality trend matches event ledger."),
        _check("release_audio_timeline_issue_taxonomy_semantics", _semantic_hash(taxonomy.get("issues")) == _semantic_hash(derived["taxonomy"].get("issues")) and _semantic_hash(taxonomy.get("summary")) == _semantic_hash(derived["taxonomy"].get("summary")), "Issue taxonomy matches event ledger."),
        _check("release_audio_timeline_risk_register_semantics", _semantic_hash(risks.get("risks")) == _semantic_hash(derived["risks"].get("risks")) and _semantic_hash(risks.get("summary")) == _semantic_hash(derived["risks"].get("summary")), "Risk register matches event ledger."),
    ]


def _certification_binding_checks(
    bindings: ImplementationDocument,
    report: ImplementationDocument,
    *,
    require_current_certification: bool,
    certification_zip_path: Path | str | None,
    certification_report_path: Path | str | None,
) -> list[ImplementationDocument]:
    if not require_current_certification:
        return []
    checks: list[dict[str, Any]] = []
    if not certification_zip_path:
        return [_check("release_audio_timeline_certification_zip_required", False, "Current Certification requirement needs external Certification ZIP.")]
    if not certification_report_path:
        return [_check("release_audio_timeline_certification_report_required", False, "Current Certification requirement needs external Certification verification report.")]
    zip_path = Path(certification_zip_path)
    report_path = Path(certification_report_path)
    try:
        external_report = read_json(report_path)
    except Exception as exc:
        return [_check("release_audio_timeline_certification_report_readable", False, f"Certification verification report could not be read: {exc}")]
    try:
        current_report = verify_release_audio_certification_package(
            zip_path,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_real_audio=True,
            require_manual_review=True,
            require_remediation_when_needed=True,
        )
    except Exception as exc:
        current_report = {"status": "failed", "error": str(exc), "summary": {}}
    external_integrity_ok = external_report.get("integrity_hash") == stable_hash({key: value for key, value in external_report.items() if key != "integrity_hash"})
    binding = ((bindings.get("bindings") or {}).get("release_audio_certification") or {}) if isinstance(bindings.get("bindings"), dict) else {}
    checks.extend(
        [
            _check("release_audio_timeline_certification_verification_package_type", external_report.get("package_type") == RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE, "Certification verification package type is valid."),
            _check("release_audio_timeline_certification_verification_integrity", external_integrity_ok, "Certification verification report integrity is valid."),
            _check("release_audio_timeline_certification_verification_status", external_report.get("status") == "passed" and current_report.get("status") == "passed", "External Certification verification is passed."),
            _check("release_audio_timeline_certification_zip_binding", external_report.get("zip_sha256") == _sha256_path(zip_path) and external_report.get("manifest_hash") == current_report.get("manifest_hash"), "Certification verification report matches current ZIP."),
            _check(
                "release_audio_timeline_certification_evidence_binding",
                binding.get("zip_sha256") == external_report.get("zip_sha256")
                and binding.get("zip_size_bytes") == external_report.get("zip_size_bytes")
                and binding.get("manifest_hash") == external_report.get("manifest_hash")
                and binding.get("verification_report_hash") == external_report.get("integrity_hash")
                and binding.get("status") == "passed",
                "Timeline evidence bindings match external Certification verification.",
                {"binding": binding},
            ),
            _check(
                "release_audio_timeline_report_certification_binding",
                ((report.get("certification") or {}).get("zip_sha256") == external_report.get("zip_sha256"))
                and ((report.get("certification") or {}).get("manifest_hash") == external_report.get("manifest_hash"))
                and ((report.get("certification") or {}).get("verification_report_hash") == external_report.get("integrity_hash")),
                "Timeline report Certification summary matches external evidence.",
            ),
        ]
    )
    return checks


def _signoff_checks(
    signoff: ImplementationDocument | None,
    manifest: ImplementationDocument,
    report: ImplementationDocument,
    track_index: ImplementationDocument,
    events: list[ImplementationDocument],
    trend: ImplementationDocument,
    taxonomy: ImplementationDocument,
    risks: ImplementationDocument,
    bindings: ImplementationDocument,
    *,
    require_signed: bool,
) -> list[ImplementationDocument]:
    if signoff is None:
        return [_check("release_audio_timeline_signoff_present", not require_signed, "Timeline signoff is present when required.")]
    ledger_hash = _event_ledger_hash(events)
    return [
        _check("release_audio_timeline_signoff_integrity", _integrity_ok(signoff), "Timeline signoff integrity hash is valid."),
        _check("release_audio_timeline_signoff_status", signoff.get("status") == "signed", "Timeline signoff status is signed."),
        _check("release_audio_timeline_signoff_report_binding", signoff.get("timeline_report_hash") == report.get("integrity_hash") == manifest.get("report_hash"), "Timeline signoff binds report."),
        _check("release_audio_timeline_signoff_ledger_binding", signoff.get("event_ledger_hash") == ledger_hash == manifest.get("event_ledger_hash"), "Timeline signoff binds event ledger."),
        _check("release_audio_timeline_signoff_track_binding", signoff.get("track_index_hash") == track_index.get("integrity_hash"), "Timeline signoff binds track index."),
        _check("release_audio_timeline_signoff_trend_binding", signoff.get("quality_trend_hash") == trend.get("integrity_hash"), "Timeline signoff binds quality trend."),
        _check("release_audio_timeline_signoff_taxonomy_binding", signoff.get("issue_taxonomy_hash") == taxonomy.get("integrity_hash"), "Timeline signoff binds issue taxonomy."),
        _check("release_audio_timeline_signoff_risk_binding", signoff.get("risk_register_hash") == risks.get("integrity_hash"), "Timeline signoff binds risk register."),
        _check("release_audio_timeline_signoff_evidence_binding", signoff.get("evidence_bindings_hash") == bindings.get("integrity_hash"), "Timeline signoff binds evidence bindings."),
        _check("release_audio_timeline_signoff_source_binding", signoff.get("source_hash") == report.get("source_hash") == manifest.get("source_hash"), "Timeline signoff binds source hash."),
        _check("release_audio_timeline_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds timeline signoff."),
    ]


def _manifest_checks(zf: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    fixed_extra_declared = sorted(declared - expected_files)
    fixed_missing_declared = sorted(expected_files - declared)
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = zf.getinfo(path)
        data = zf.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_timeline_manifest_files_present", bool(files), "Manifest declares package files."),
        _check("release_audio_timeline_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)),
        _check("release_audio_timeline_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}),
        _check("release_audio_timeline_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match fixed Timeline layout.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}),
        _check("release_audio_timeline_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}),
    ]


def _derive_from_events(release_id: Any, timeline_id: Any, events: list[ImplementationDocument], *, source_hash: Any) -> ImplementationDocument:
    track_events = [event for event in events if event.get("event_type") == "track_certification_summary"]
    tracks: list[dict[str, Any]] = []
    issues: dict[str, dict[str, Any]] = {}
    risks: list[dict[str, Any]] = []
    accepted = needs_fix = rejected = open_markers = 0
    for event in track_events:
        payload = _as_document(event.get("payload"))
        track = dict(payload.get("track") or {})
        event_ids = [event.get("event_id")]
        track["event_ids"] = event_ids
        tracks.append(track)
        if track.get("review_status") == "accepted":
            accepted += 1
        elif track.get("review_status") == "needs_fix":
            needs_fix += 1
        elif track.get("review_status") == "rejected":
            rejected += 1
        open_markers += int(track.get("open_issue_count") or 0)
        for issue in payload.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            key = str(issue.get("issue_key") or "unknown_issue")
            item = issues.setdefault(
                key,
                {
                    "issue_key": key,
                    "label": str(issue.get("label") or key),
                    "severity_max": str(issue.get("severity") or "info"),
                    "occurrence_count": 0,
                    "track_ids": set(),
                    "resolved_count": 0,
                    "open_count": 0,
                    "first_seen_event_id": event.get("event_id"),
                    "latest_seen_event_id": event.get("event_id"),
                },
            )
            item["occurrence_count"] += 1
            item["track_ids"].add(track.get("track_id"))
            if str(issue.get("status") or "open") == "resolved":
                item["resolved_count"] += 1
            else:
                item["open_count"] += 1
            item["latest_seen_event_id"] = event.get("event_id")
        for risk in payload.get("risks") or []:
            if isinstance(risk, dict):
                risks.append(dict(risk))

    tracks = sorted(tracks, key=lambda row: (int(row.get("track_number") or 0), str(row.get("track_id") or "")))
    track_index = {
        "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
        "release_id": release_id,
        "timeline_id": timeline_id,
        "tracks": tracks,
        "summary": {
            "track_count": len(tracks),
            "certified_track_count": sum(1 for row in tracks if row.get("status") == "certified"),
            "tracks_with_open_issues": sum(1 for row in tracks if int(row.get("open_issue_count") or 0) > 0),
            "tracks_with_remediation": sum(1 for row in tracks if int(row.get("fix_sprint_count") or 0) > 0),
            "manual_review_count": sum(int(row.get("manual_review_count") or 0) for row in tracks),
            "real_audio_review_count": sum(1 for row in tracks if int(row.get("real_audio_review_count") or 0) > 0),
            "test_fake_count": sum(int(row.get("test_fake_count") or 0) for row in tracks),
        },
        "source_hash": source_hash,
    }
    issue_rows = []
    for item in issues.values():
        issue_rows.append(
            {
                "issue_key": item["issue_key"],
                "label": item["label"],
                "severity_max": item["severity_max"],
                "occurrence_count": item["occurrence_count"],
                "track_count": len({track_id for track_id in item["track_ids"] if track_id}),
                "resolved_count": item["resolved_count"],
                "open_count": item["open_count"],
                "first_seen_event_id": item["first_seen_event_id"],
                "latest_seen_event_id": item["latest_seen_event_id"],
            }
        )
    issue_rows = sorted(issue_rows, key=lambda row: (-int(row.get("occurrence_count") or 0), str(row.get("issue_key") or "")))
    taxonomy = {
        "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
        "release_id": release_id,
        "timeline_id": timeline_id,
        "issues": issue_rows,
        "summary": {"issue_type_count": len(issue_rows), "open_issue_type_count": sum(1 for row in issue_rows if int(row.get("open_count") or 0) > 0), "top_issue_keys": [row.get("issue_key") for row in issue_rows[:5]]},
        "source_hash": source_hash,
    }
    blocking_count = sum(1 for risk in risks if str(risk.get("severity") or "") in {"blocking", "critical"})
    risk_doc = {
        "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
        "release_id": release_id,
        "timeline_id": timeline_id,
        "risks": sorted(risks, key=lambda row: str(row.get("risk_id") or "")),
        "summary": {"open_risk_count": len(risks), "blocking_risk_count": blocking_count},
        "source_hash": source_hash,
    }
    track_count = len(tracks)
    manual_count = sum(int(row.get("manual_review_count") or 0) for row in tracks)
    real_count = sum(1 for row in tracks if int(row.get("real_audio_review_count") or 0) > 0)
    remediation_tracks = sum(1 for row in tracks if int(row.get("fix_sprint_count") or 0) > 0)
    trend = {
        "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
        "release_id": release_id,
        "timeline_id": timeline_id,
        "summary": {
            "track_count": track_count,
            "average_fix_cycles_per_track": round(remediation_tracks / track_count, 4) if track_count else 0,
            "manual_acceptance_rate": round(manual_count / track_count, 4) if track_count else 0,
            "real_audio_coverage": round(real_count / track_count, 4) if track_count else 0,
            "remediation_success_rate": 1.0 if blocking_count == 0 else 0.0,
            "recurring_issue_count": sum(1 for row in issue_rows if int(row.get("occurrence_count") or 0) > 1),
            "open_blocker_count": blocking_count,
        },
        "trend_points": [
            {"stage": "audio_review", "accepted": accepted, "needs_fix": needs_fix, "rejected": rejected, "open_markers": open_markers},
            {"stage": "certification", "accepted": sum(1 for row in tracks if row.get("status") == "certified"), "needs_fix": 0 if blocking_count == 0 else needs_fix, "rejected": 0 if blocking_count == 0 else rejected, "open_markers": 0 if blocking_count == 0 else open_markers},
        ],
        "source_hash": source_hash,
    }
    return {"track_index": track_index, "taxonomy": taxonomy, "risks": risk_doc, "trend": trend}


def _event_ledger_hash(events: list[ImplementationDocument]) -> str:
    return stable_hash(events)


def _event_hash(event: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in event.items() if key != "event_hash"})


def _manifest_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _manifest_hash(payload)


def _semantic_hash(value: Any) -> str:
    return stable_hash(_strip_volatile(value))


def _strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_volatile(item) for key, item in value.items() if key not in {"generated_at", "integrity_hash"}}
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    if isinstance(value, set):
        return sorted(value)
    return value


def _redaction_check(zf: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = zf.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("release_audio_timeline_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_TIMELINE_VERIFICATION_PACKAGE_TYPE,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "ok": not blockers,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "summary": {**summary, "check_count": len(checks), "blocker_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": [check.get("check_id") for check in blockers],
        "warnings": [check.get("check_id") for check in warnings],
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(zf: zipfile.ZipFile, name: str) -> ImplementationDocument:
    with zf.open(name) as fp:
        data = json.loads(fp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _read_jsonl_entry(zf: zipfile.ZipFile, name: str) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    with zf.open(name) as fp:
        for raw in fp.read().decode("utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError(f"{name} must contain JSON objects.")
            rows.append(item)
    return rows


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    if not name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered or lowered.endswith(".zip"):
        return False
    return True


def _sha256_path(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


_SENSITIVE_TEXT_RE = re.compile(r"((?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}|api[_-]?key|[A-Za-z]:\\Users\\|\.musicforge[\\/])", re.IGNORECASE)
