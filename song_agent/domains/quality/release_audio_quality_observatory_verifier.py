from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.quality.release_audio_quality_observatory_semantics import RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE, RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, build_observatory_documents_from_evidence_root as build_observatory_documents_from_evidence_root
from song_agent.domains.delivery.releases import stable_hash as stable_hash


RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE = "release_audio_quality_observatory_verification"

REQUIRED_ENTRIES = {
    "manifest.json",
    "observatory-config.json",
    "source-index.json",
    "evidence-fingerprints.json",
    "trend-report.json",
    "issue-heatmap.json",
    "baseline-drift-report.json",
    "remediation-cost-report.json",
    "risk-register.json",
    "recommendation-report.json",
    "observatory-summary.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"observatory-history.jsonl"}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_quality_observatory_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current_evidence: bool = False,
    evidence_root: Path | str | None = None,
    require_no_critical_risk: bool = False,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "observatory_id": None,
        "release_ids": [],
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_quality_observatory_zip_exists", False, "Release Audio Quality Observatory ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_quality_observatory_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_quality_observatory_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_quality_observatory_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_quality_observatory_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_quality_observatory_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            expected_entries = set(REQUIRED_ENTRIES)
            if "observatory-history.jsonl" in names:
                expected_entries.add("observatory-history.jsonl")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("release_audio_quality_observatory_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Release Audio Quality Observatory entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_quality_observatory_zip_expected_entries", not missing_entries, "ZIP contains all expected Release Audio Quality Observatory entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            config = _read_json_entry(archive, "observatory-config.json")
            source_index = _read_json_entry(archive, "source-index.json")
            evidence_fingerprints = _read_json_entry(archive, "evidence-fingerprints.json")
            trend = _read_json_entry(archive, "trend-report.json")
            heatmap = _read_json_entry(archive, "issue-heatmap.json")
            baseline = _read_json_entry(archive, "baseline-drift-report.json")
            remediation = _read_json_entry(archive, "remediation-cost-report.json")
            risks = _read_json_entry(archive, "risk-register.json")
            recommendations = _read_json_entry(archive, "recommendation-report.json")
            observatory_summary = _read_json_entry(archive, "observatory-summary.json")

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["observatory_id"] = manifest.get("observatory_id") or config.get("observatory_id")
            summary["release_ids"] = (observatory_summary.get("summary") or {}).get("release_ids") or [row.get("release_id") for row in source_index.get("releases", []) if isinstance(row, dict)]

            checks.extend(_manifest_checks(archive, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_quality_observatory_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE, "Manifest package_type is release_audio_quality_observatory."))
            checks.append(_check("release_audio_quality_observatory_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "Manifest schema version is supported."))

            documents = {
                "manifest": manifest,
                "config": config,
                "source_index": source_index,
                "evidence_fingerprints": evidence_fingerprints,
                "trend_report": trend,
                "issue_heatmap": heatmap,
                "baseline_drift": baseline,
                "remediation_cost": remediation,
                "risk_register": risks,
                "recommendation_report": recommendations,
                "summary": observatory_summary,
            }
            for check_id, document in (
                ("release_audio_quality_observatory_manifest_integrity", manifest),
                ("release_audio_quality_observatory_config_integrity", config),
                ("release_audio_quality_observatory_source_index_integrity", source_index),
                ("release_audio_quality_observatory_evidence_fingerprints_integrity", evidence_fingerprints),
                ("release_audio_quality_observatory_trend_report_integrity", trend),
                ("release_audio_quality_observatory_issue_heatmap_integrity", heatmap),
                ("release_audio_quality_observatory_baseline_drift_integrity", baseline),
                ("release_audio_quality_observatory_remediation_cost_integrity", remediation),
                ("release_audio_quality_observatory_risk_register_integrity", risks),
                ("release_audio_quality_observatory_recommendation_report_integrity", recommendations),
                ("release_audio_quality_observatory_summary_integrity", observatory_summary),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(documents))

            if require_current_evidence:
                checks.extend(_external_semantics_checks(config, documents, evidence_root=evidence_root))
            if require_no_critical_risk:
                checks.append(_check("release_audio_quality_observatory_no_critical_risk", int((risks.get("summary") or {}).get("critical_risk_count") or 0) == 0 and risks.get("status") != "failed", "Observatory has no critical audio quality risk."))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_quality_observatory_zip_readable", False, "Release Audio Quality Observatory ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_quality_observatory_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_quality_observatory_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_semantics_checks(config: ImplementationDocument, documents: dict[str, ImplementationDocument], *, evidence_root: Path | str | None) -> list[ImplementationDocument]:
    if evidence_root is None:
        return [_check("release_audio_quality_observatory_external_evidence_root_required", False, "Current evidence verification requires an evidence root.")]
    try:
        expected = build_observatory_documents_from_evidence_root(config, Path(evidence_root))
    except Exception as exc:
        return [_check("release_audio_quality_observatory_external_evidence_readable", False, f"External audio evidence could not be rebuilt: {exc}")]
    checks = [
        _check("release_audio_quality_observatory_external_fingerprints_match", _semantic_hash(documents["evidence_fingerprints"]) == _semantic_hash(expected["evidence_fingerprints"]), "Evidence fingerprints match external Certification/Timeline verification reports."),
        _check("release_audio_quality_observatory_external_source_index_match", _semantic_hash(documents["source_index"]) == _semantic_hash(expected["source_index"]), "Source index matches external audio evidence."),
        _check("release_audio_quality_observatory_external_trend_match", _semantic_hash(documents["trend_report"]) == _semantic_hash(expected["trend_report"]), "Trend report matches recomputed external audio facts."),
        _check("release_audio_quality_observatory_external_heatmap_match", _semantic_hash(documents["issue_heatmap"]) == _semantic_hash(expected["issue_heatmap"]), "Issue heatmap matches recomputed external audio facts."),
        _check("release_audio_quality_observatory_external_risk_match", _semantic_hash(documents["risk_register"]) == _semantic_hash(expected["risk_register"]), "Risk register matches recomputed external audio facts."),
        _check("release_audio_quality_observatory_external_summary_match", _semantic_hash(documents["summary"]) == _semantic_hash(expected["summary"]), "Observatory summary matches recomputed external audio facts."),
    ]
    return checks


def _document_binding_checks(documents: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    manifest = documents["manifest"]
    source_hash = documents["summary"].get("source_hash")
    same_source = all(doc.get("source_hash") == source_hash for key, doc in documents.items() if key not in {"manifest", "config"})
    doc_hashes = _as_document(documents["summary"].get("document_hashes"))
    return [
        _check("release_audio_quality_observatory_manifest_config_binding", manifest.get("config_hash") == documents["config"].get("integrity_hash"), "Manifest binds config."),
        _check("release_audio_quality_observatory_manifest_source_index_binding", manifest.get("source_index_hash") == documents["source_index"].get("integrity_hash"), "Manifest binds source index."),
        _check("release_audio_quality_observatory_manifest_evidence_binding", manifest.get("evidence_fingerprints_hash") == documents["evidence_fingerprints"].get("integrity_hash"), "Manifest binds evidence fingerprints."),
        _check("release_audio_quality_observatory_manifest_trend_binding", manifest.get("trend_report_hash") == documents["trend_report"].get("integrity_hash"), "Manifest binds trend report."),
        _check("release_audio_quality_observatory_manifest_heatmap_binding", manifest.get("issue_heatmap_hash") == documents["issue_heatmap"].get("integrity_hash"), "Manifest binds issue heatmap."),
        _check("release_audio_quality_observatory_manifest_baseline_binding", manifest.get("baseline_drift_hash") == documents["baseline_drift"].get("integrity_hash"), "Manifest binds baseline drift."),
        _check("release_audio_quality_observatory_manifest_remediation_binding", manifest.get("remediation_cost_hash") == documents["remediation_cost"].get("integrity_hash"), "Manifest binds remediation cost."),
        _check("release_audio_quality_observatory_manifest_risk_binding", manifest.get("risk_register_hash") == documents["risk_register"].get("integrity_hash"), "Manifest binds risk register."),
        _check("release_audio_quality_observatory_manifest_recommendation_binding", manifest.get("recommendation_report_hash") == documents["recommendation_report"].get("integrity_hash"), "Manifest binds recommendation report."),
        _check("release_audio_quality_observatory_manifest_summary_binding", manifest.get("summary_hash") == documents["summary"].get("integrity_hash"), "Manifest binds summary."),
        _check("release_audio_quality_observatory_source_binding", same_source and manifest.get("source_hash") == source_hash, "Observatory documents bind the same source hash."),
        _check("release_audio_quality_observatory_summary_document_hashes", all(doc_hashes.get(key) == doc.get("integrity_hash") for key, doc in documents.items() if key not in {"manifest", "summary"}), "Summary binds all Observatory documents."),
    ]


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[ImplementationDocument]:
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
        info = archive.getinfo(path)
        data = archive.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_quality_observatory_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("release_audio_quality_observatory_manifest_declares_files", not undeclared and not extra_declared, "Manifest files match ZIP entries.", {"undeclared": undeclared, "extra_declared": extra_declared}),
        _check("release_audio_quality_observatory_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match fixed Observatory structure.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}),
        _check("release_audio_quality_observatory_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("release_audio_quality_observatory_manifest_zip_entries_untrusted", strict or True, "manifest.zip.entries is not used as an allow-list."),
    ]


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "status": status,
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


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
    path = Path(name)
    if path.is_absolute():
        return False
    parts = name.split("/")
    return all(part and part not in {".", ".."} for part in parts)


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("release_audio_quality_observatory_redaction", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
