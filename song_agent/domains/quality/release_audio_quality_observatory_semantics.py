from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from song_agent.domains.studio.projectio import read_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package
from song_agent.domains.delivery.releases import stable_hash


RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE = "release_audio_quality_observatory"


RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION = 1


def build_observatory_documents(config: DomainDocument, release_entries: list[DomainDocument]) -> dict[str, DomainDocument]:
    now = now_iso()
    config_doc = dict(config)
    config_doc["integrity_hash"] = _integrity_hash(config_doc)
    thresholds = _default_thresholds(_as_document(config_doc.get("thresholds")))
    facts = [_external_facts_from_entry(entry) for entry in release_entries]
    release_rows = [_source_row(item) for item in facts]
    fingerprint_rows = [component for item in facts for component in item.get("components", [])]
    source_hash = stable_hash(
        {
            "config_hash": _stable_config_hash(config_doc),
            "release_rows": release_rows,
            "fingerprint_rows": fingerprint_rows,
            "thresholds": thresholds,
        }
    )
    source_index = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config_doc.get("observatory_id"),
        "source_hash": source_hash,
        "release_count": len(release_rows),
        "releases": release_rows,
    }
    evidence_fingerprints = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config_doc.get("observatory_id"),
        "source_hash": source_hash,
        "components": fingerprint_rows,
        "summary": {
            "component_count": len(fingerprint_rows),
            "failed_component_count": sum(1 for row in fingerprint_rows if row.get("status") != "passed"),
        },
    }
    trend_report = _trend_report(config_doc, facts, source_hash=source_hash)
    issue_heatmap = _issue_heatmap(config_doc, facts, source_hash=source_hash)
    baseline_drift = _baseline_drift(config_doc, facts, source_hash=source_hash)
    remediation_cost = _remediation_cost(config_doc, facts, source_hash=source_hash)
    risk_register = _risk_register(config_doc, facts, trend_report, issue_heatmap, baseline_drift, remediation_cost, thresholds=thresholds, source_hash=source_hash)
    recommendation_report = _recommendation_report(config_doc, risk_register, source_hash=source_hash)
    status = "failed" if risk_register.get("summary", {}).get("critical_risk_count", 0) else "warning" if risk_register.get("summary", {}).get("warning_risk_count", 0) else "passed"
    fingerprint_summary = _as_document(evidence_fingerprints.get("summary"))
    risk_summary = _as_document(risk_register.get("summary"))
    trend_summary = _as_document(trend_report.get("summary"))
    summary: ImplementationDocument = {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "package_type": RELEASE_AUDIO_QUALITY_OBSERVATORY_PACKAGE_TYPE,
        "observatory_id": config_doc.get("observatory_id"),
        "status": status,
        "readiness": "blocked" if status == "failed" else "warning_requires_audio_lead_review" if status == "warning" else "ready",
        "source_hash": source_hash,
        "summary": {
            "release_count": len(release_rows),
            "release_ids": [row.get("release_id") for row in release_rows if row.get("release_id")],
            "track_count": sum(int(row.get("track_count") or 0) for row in release_rows),
            "component_count": len(fingerprint_rows),
            "failed_component_count": fingerprint_summary.get("failed_component_count"),
            "critical_risk_count": risk_summary.get("critical_risk_count"),
            "warning_risk_count": risk_summary.get("warning_risk_count"),
            "average_manual_rating": trend_summary.get("average_manual_rating"),
            "minimum_manual_rating": trend_summary.get("minimum_manual_rating"),
        },
        "document_hashes": {},
        "created_at": now,
    }
    docs = {
        "config": config_doc,
        "source_index": source_index,
        "evidence_fingerprints": evidence_fingerprints,
        "trend_report": trend_report,
        "issue_heatmap": issue_heatmap,
        "baseline_drift": baseline_drift,
        "remediation_cost": remediation_cost,
        "risk_register": risk_register,
        "recommendation_report": recommendation_report,
        "summary": summary,
    }
    for key, doc in docs.items():
        if key != "summary":
            doc["integrity_hash"] = _integrity_hash(doc)
    summary["document_hashes"] = {key: doc.get("integrity_hash") for key, doc in docs.items() if key != "summary"}
    summary["integrity_hash"] = _integrity_hash(summary)
    return docs


def build_observatory_documents_from_evidence_root(config: DomainDocument, evidence_root: Path | str) -> dict[str, DomainDocument]:
    root = Path(evidence_root)
    release_ids = [str(item) for item in config.get("release_ids", []) if str(item).strip()]
    candidates = [root / release_id for release_id in release_ids] if release_ids else sorted(path for path in root.glob("release-*") if path.is_dir())
    entries: list[ImplementationDocument] = []
    for release_dir in candidates:
        try:
            release_doc = read_json(release_dir / "release.json") if (release_dir / "release.json").exists() else {"release_id": release_dir.name}
            entries.append(_build_release_entry_from_paths(release_dir, release_doc))
        except Exception as exc:
            entries.append({"release_id": release_dir.name, "release": {"release_id": release_dir.name}, "status": "failed", "error": sanitize_sensitive_text(str(exc)), "components": []})
    return build_observatory_documents(config, entries)


def _build_release_entry_from_paths(release_dir: Path, release_doc: ImplementationDocument) -> ImplementationDocument:
    release_id = str(release_doc.get("release_id") or release_dir.name)
    timeline_id = _current_timeline_id(release_dir)
    paths = {
        "certification_zip": release_dir / "audio-certification" / "release-audio-certification.zip",
        "certification_verification_report": release_dir / "audio-certification" / "verification-report.json",
        "timeline_zip": release_dir / "audio-timelines" / timeline_id / "release-audio-timeline.zip" if timeline_id else None,
        "timeline_verification_report": release_dir / "audio-timelines" / timeline_id / "verification-report.json" if timeline_id else None,
        "regression_zip": release_dir / "audio-regression" / "release-audio-regression.zip",
        "regression_verification_report": release_dir / "audio-regression" / "verification-report.json",
        "regression_response_zip": release_dir / "audio-regression-response" / "release-audio-regression-response.zip",
        "regression_response_verification_report": release_dir / "audio-regression-response" / "verification-report.json",
    }
    return _build_release_entry({"release_id": release_id, **release_doc}, paths, explicit=False)


def _build_release_entry(release_doc: ImplementationDocument, paths: dict[str, Path | None], *, explicit: bool) -> ImplementationDocument:
    release_id = str(release_doc.get("release_id") or "")
    components: list[ImplementationDocument] = []
    cert = _verification_component("release_audio_certification", release_id, paths.get("certification_zip"), paths.get("certification_verification_report"), verifier="certification")
    timeline = _verification_component(
        "release_audio_timeline",
        release_id,
        paths.get("timeline_zip"),
        paths.get("timeline_verification_report"),
        verifier="timeline",
        certification_zip=paths.get("certification_zip"),
        certification_report=paths.get("certification_verification_report"),
    )
    components.extend([cert, timeline])
    for component_type, zip_key, report_key in (
        ("release_audio_regression", "regression_zip", "regression_verification_report"),
        ("release_audio_regression_response", "regression_response_zip", "regression_response_verification_report"),
    ):
        component = _basic_component(component_type, release_id, paths.get(zip_key), paths.get(report_key))
        if component.get("present"):
            components.append(component)
    facts = _timeline_facts(paths.get("timeline_zip")) if timeline.get("status") == "passed" and paths.get("timeline_zip") else {"tracks": [], "issues": [], "release_id": release_id}
    status = "passed" if cert.get("status") == "passed" and timeline.get("status") == "passed" else "failed"
    return {
        "release_id": release_id,
        "release": release_doc,
        "explicit": explicit,
        "status": status,
        "components": components,
        "facts": facts,
    }


def _verification_component(
    component_type: str,
    release_id: str,
    zip_path: Path | None,
    report_path: Path | None,
    *,
    verifier: str,
    certification_zip: Path | None = None,
    certification_report: Path | None = None,
) -> ImplementationDocument:
    if not zip_path or not report_path or not Path(zip_path).exists() or not Path(report_path).exists():
        return {"component_type": component_type, "release_id": release_id, "present": False, "status": "missing", "message": f"{component_type} evidence is missing."}
    zip_path = Path(zip_path)
    report_path = Path(report_path)
    try:
        report = read_json(report_path)
        runtime = (
            verify_release_audio_certification_package(zip_path, strict=True, require_passed=True, require_signed=True, require_real_audio=True, require_manual_review=True, require_remediation_when_needed=True)
            if verifier == "certification"
            else verify_release_audio_timeline_package(
                zip_path,
                strict=True,
                require_passed=True,
                require_signed=True,
                require_real_audio=True,
                require_manual_review=True,
                require_current_certification=True,
                release_audio_certification_path=certification_zip,
                release_audio_certification_verification_report_path=certification_report,
            )
        )
        report_ok = _integrity_ok(report) and report.get("status") == "passed" and report.get("zip_sha256") == _sha256_path(zip_path) and report.get("zip_size_bytes") == zip_path.stat().st_size and report.get("manifest_hash") == runtime.get("manifest_hash")
        runtime_ok = runtime.get("status") == "passed"
        return {
            "component_type": component_type,
            "release_id": release_id,
            "present": True,
            "status": "passed" if report_ok and runtime_ok else "failed",
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_report_hash": report.get("integrity_hash"),
            "verification_status": report.get("status"),
            "runtime_status": runtime.get("status"),
            "package_type": report.get("package_type"),
        }
    except Exception as exc:
        return {"component_type": component_type, "release_id": release_id, "present": True, "status": "failed", "message": sanitize_sensitive_text(str(exc))}


def _basic_component(component_type: str, release_id: str, zip_path: Path | None, report_path: Path | None) -> ImplementationDocument:
    if not zip_path or not report_path or not Path(zip_path).exists() or not Path(report_path).exists():
        return {"component_type": component_type, "release_id": release_id, "present": False, "status": "missing"}
    zip_path = Path(zip_path)
    try:
        report = read_json(Path(report_path))
        ok = _integrity_ok(report) and report.get("status") == "passed" and report.get("zip_sha256") == _sha256_path(zip_path) and int(report.get("zip_size_bytes") or -1) == zip_path.stat().st_size
        return {
            "component_type": component_type,
            "release_id": release_id,
            "present": True,
            "status": "passed" if ok else "failed",
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": report.get("manifest_hash"),
            "verification_report_hash": report.get("integrity_hash"),
            "verification_status": report.get("status"),
            "package_type": report.get("package_type"),
        }
    except Exception as exc:
        return {"component_type": component_type, "release_id": release_id, "present": True, "status": "failed", "message": sanitize_sensitive_text(str(exc))}


def _timeline_facts(timeline_zip: Path | None) -> ImplementationDocument:
    if not timeline_zip or not Path(timeline_zip).exists():
        return {"tracks": [], "issues": []}
    with zipfile.ZipFile(Path(timeline_zip)) as archive:
        report = _read_json_entry(archive, "audio-timeline-report.json")
        track_index = _read_json_entry(archive, "track-timeline-index.json")
        taxonomy = _read_json_entry(archive, "issue-taxonomy.json")
        trend = _read_json_entry(archive, "quality-trend.json")
    tracks: list[ImplementationDocument] = []
    for row in track_index.get("tracks") or []:
        if not isinstance(row, dict):
            continue
        tracks.append(
            {
                "track_id": row.get("track_id"),
                "project_id": row.get("project_id"),
                "version_id": row.get("version_id"),
                "title": row.get("title"),
                "normalized_title": _normalize_title(row.get("title")),
                "final_export_hash": row.get("final_export_hash"),
                "manual_rating": _manual_rating(row),
                "review_status": row.get("review_status") or row.get("status"),
                "manual_review_count": int(row.get("manual_review_count") or 0),
                "real_audio_review_count": int(row.get("real_audio_review_count") or 0),
                "test_fake_count": int(row.get("test_fake_count") or 0),
                "open_issue_count": int(row.get("open_issue_count") or 0),
                "high_issue_count": int(row.get("high_issue_count") or 0),
                "critical_issue_count": int(row.get("critical_issue_count") or 0),
                "needs_fix_count": 1 if row.get("review_status") == "needs_fix" else 0,
                "rejected_count": 1 if row.get("review_status") == "rejected" else 0,
                "remediation_count": int(row.get("fix_sprint_count") or 0),
            }
        )
    issues = [item for item in taxonomy.get("issues") or [] if isinstance(item, dict)]
    return {"release_id": report.get("release_id"), "tracks": tracks, "issues": issues, "trend_summary": trend.get("summary") or {}}


def _source_row(facts: ImplementationDocument) -> ImplementationDocument:
    tracks = facts.get("facts", {}).get("tracks", []) if isinstance(facts.get("facts"), dict) else []
    return {
        "release_id": facts.get("release_id"),
        "status": facts.get("status"),
        "track_count": len(tracks),
        "average_manual_rating": _avg([_num(track.get("manual_rating")) for track in tracks if _num(track.get("manual_rating")) is not None]),
        "minimum_manual_rating": _min([_num(track.get("manual_rating")) for track in tracks if _num(track.get("manual_rating")) is not None]),
        "high_issue_count": sum(int(track.get("high_issue_count") or 0) for track in tracks),
        "critical_issue_count": sum(int(track.get("critical_issue_count") or 0) for track in tracks),
        "needs_fix_count": sum(int(track.get("needs_fix_count") or 0) for track in tracks),
        "remediation_count": sum(int(track.get("remediation_count") or 0) for track in tracks),
        "component_statuses": {row.get("component_type"): row.get("status") for row in facts.get("components", []) if row.get("present", True)},
    }


def _external_facts_from_entry(entry: ImplementationDocument) -> ImplementationDocument:
    return {"release_id": entry.get("release_id"), "status": entry.get("status"), "release": entry.get("release") or {}, "components": entry.get("components") or [], "facts": entry.get("facts") or {"tracks": [], "issues": []}}


def _trend_report(config: ImplementationDocument, facts: list[ImplementationDocument], *, source_hash: str) -> ImplementationDocument:
    releases = [_source_row(item) for item in facts]
    ratings = [row["average_manual_rating"] for row in releases if row.get("average_manual_rating") is not None]
    min_ratings = [row["minimum_manual_rating"] for row in releases if row.get("minimum_manual_rating") is not None]
    return {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config.get("observatory_id"),
        "source_hash": source_hash,
        "release_trends": releases,
        "summary": {
            "release_count": len(releases),
            "average_manual_rating": _avg(ratings),
            "minimum_manual_rating": _min(min_ratings),
            "average_rating_delta": round(ratings[-1] - ratings[0], 4) if len(ratings) >= 2 else 0.0,
            "high_issue_count": sum(int(row.get("high_issue_count") or 0) for row in releases),
            "critical_issue_count": sum(int(row.get("critical_issue_count") or 0) for row in releases),
        },
    }


def _issue_heatmap(config: ImplementationDocument, facts: list[ImplementationDocument], *, source_hash: str) -> ImplementationDocument:
    buckets: dict[str, ImplementationDocument] = {}
    for item in facts:
        release_id = item.get("release_id")
        for issue in item.get("facts", {}).get("issues", []) if isinstance(item.get("facts"), dict) else []:
            issue_type = str(issue.get("issue_type") or issue.get("category") or issue.get("check_id") or "unknown")
            bucket = buckets.setdefault(issue_type, {"issue_type": issue_type, "release_ids": set(), "high_count": 0, "critical_count": 0, "open_count": 0})
            bucket["release_ids"].add(release_id)
            severity = str(issue.get("severity_max") or issue.get("severity") or "info")
            count = int(issue.get("open_count") or issue.get("count") or 1)
            bucket["open_count"] += count
            if severity == "high":
                bucket["high_count"] += count
            if severity in {"critical", "blocking"}:
                bucket["critical_count"] += count
    rows = [{**value, "release_ids": sorted(value["release_ids"])} for value in buckets.values()]
    return {
        "schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION,
        "observatory_id": config.get("observatory_id"),
        "source_hash": source_hash,
        "issues": sorted(rows, key=lambda row: (-int(row.get("critical_count") or 0), -int(row.get("high_count") or 0), row.get("issue_type") or "")),
        "summary": {"issue_type_count": len(rows), "critical_issue_count": sum(int(row.get("critical_count") or 0) for row in rows), "high_issue_count": sum(int(row.get("high_count") or 0) for row in rows)},
    }


def _baseline_drift(config: ImplementationDocument, facts: list[ImplementationDocument], *, source_hash: str) -> ImplementationDocument:
    release_rows = [_source_row(item) for item in facts]
    drift_rows: list[ImplementationDocument] = []
    if len(release_rows) >= 2:
        first = release_rows[0]
        latest = release_rows[-1]
        drift_rows.append(
            {
                "metric": "average_manual_rating",
                "baseline_value": first.get("average_manual_rating"),
                "current_value": latest.get("average_manual_rating"),
                "delta": _delta(latest.get("average_manual_rating"), first.get("average_manual_rating")),
                "status": "warning" if _delta(latest.get("average_manual_rating"), first.get("average_manual_rating")) < 0 else "passed",
            }
        )
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "drift": drift_rows, "summary": {"drift_count": len([row for row in drift_rows if row.get("status") != "passed"])}}


def _remediation_cost(config: ImplementationDocument, facts: list[ImplementationDocument], *, source_hash: str) -> ImplementationDocument:
    rows = []
    for item in facts:
        source = _source_row(item)
        rows.append({"release_id": item.get("release_id"), "remediation_count": source.get("remediation_count"), "needs_fix_count": source.get("needs_fix_count"), "high_issue_count": source.get("high_issue_count"), "critical_issue_count": source.get("critical_issue_count")})
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "rows": rows, "summary": {"remediation_count": sum(int(row.get("remediation_count") or 0) for row in rows), "needs_fix_count": sum(int(row.get("needs_fix_count") or 0) for row in rows)}}


def _risk_register(config: ImplementationDocument, facts: list[ImplementationDocument], trend: ImplementationDocument, heatmap: ImplementationDocument, drift: ImplementationDocument, remediation: ImplementationDocument, *, thresholds: ImplementationDocument, source_hash: str) -> ImplementationDocument:
    risks: list[ImplementationDocument] = []
    for item in facts:
        failed = [component for component in item.get("components", []) if component.get("present", True) and component.get("status") != "passed"]
        if failed or item.get("status") != "passed":
            risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "audio_evidence_not_current", "release_id": item.get("release_id"), "severity": "critical", "status": "failed", "message": "Release audio evidence is missing, stale, or failed.", "components": failed})
    min_rating = trend.get("summary", {}).get("minimum_manual_rating")
    if min_rating is not None and float(min_rating) < float(thresholds.get("min_manual_rating", 3.0)):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "manual_rating_floor", "severity": "critical", "status": "failed", "message": "A release has manual audio rating below policy floor.", "value": min_rating})
    rating_delta = trend.get("summary", {}).get("average_rating_delta")
    if rating_delta is not None and float(rating_delta) < -float(thresholds.get("max_average_rating_drop", 0.25)):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "quality_trend_decline", "severity": "high", "status": "warning", "message": "Average manual rating declined across the observation window.", "delta": rating_delta})
    if int(heatmap.get("summary", {}).get("critical_issue_count") or 0) > int(thresholds.get("max_critical_issue_count", 0) or 0):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "critical_issue_hotspot", "severity": "critical", "status": "failed", "message": "Critical audio issue hotspot detected."})
    if int(remediation.get("summary", {}).get("needs_fix_count") or 0) > int(thresholds.get("max_needs_fix_count", 0) or 0):
        risks.append({"risk_id": f"aqr-{len(risks)+1:06d}", "check_id": "needs_fix_backlog", "severity": "high", "status": "warning", "message": "Needs-fix backlog is present."})
    critical = [risk for risk in risks if risk.get("status") == "failed" or risk.get("severity") == "critical"]
    warnings = [risk for risk in risks if risk not in critical]
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "status": "failed" if critical else "warning" if warnings else "passed", "risks": risks, "summary": {"risk_count": len(risks), "critical_risk_count": len(critical), "warning_risk_count": len(warnings)}}


def _recommendation_report(config: ImplementationDocument, risk_register: ImplementationDocument, *, source_hash: str) -> ImplementationDocument:
    recommendations: list[_InferenceType] = []
    for risk in risk_register.get("risks") or []:
        action = "refresh_audio_evidence" if risk.get("check_id") == "audio_evidence_not_current" else "open_audio_quality_review"
        recommendations.append({"recommendation_id": f"aqrec-{len(recommendations)+1:06d}", "source_risk_id": risk.get("risk_id"), "action": action, "manual_required": True, "reason": risk.get("message")})
    return {"schema_version": RELEASE_AUDIO_QUALITY_OBSERVATORY_SCHEMA_VERSION, "observatory_id": config.get("observatory_id"), "source_hash": source_hash, "recommendations": recommendations, "summary": {"recommendation_count": len(recommendations)}}


def _current_timeline_id(release_dir: Path) -> str | None:
    current_path = release_dir / "audio-timelines" / "current-timeline.json"
    if current_path.exists():
        try:
            current = read_json(current_path)
            if current.get("timeline_id"):
                return str(current.get("timeline_id"))
        except Exception:
            pass
    candidates = sorted((release_dir / "audio-timelines").glob("*/audio-timeline-report.json"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return candidates[0].parent.name if candidates else None


def _default_thresholds(overrides: ImplementationDocument) -> ImplementationDocument:
    thresholds = {"min_manual_rating": 3.0, "max_average_rating_drop": 0.25, "max_critical_issue_count": 0, "max_needs_fix_count": 0}
    thresholds.update({key: overrides[key] for key in thresholds if key in overrides})
    return thresholds


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _stable_config_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"integrity_hash", "created_at", "updated_at"}})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _avg(values: list[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def _min(values: list[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return min(numbers) if numbers else None


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(current: Any, baseline: Any) -> float:
    current_num = _num(current)
    baseline_num = _num(baseline)
    if current_num is None or baseline_num is None:
        return 0.0
    return round(current_num - baseline_num, 4)


def _manual_rating(row: ImplementationDocument) -> float | None:
    for key in ("manual_rating", "rating", "review_rating", "latest_manual_rating"):
        value = _num(row.get(key))
        if value is not None:
            return value
    for key in ("manual_review", "review"):
        nested = row.get(key)
        if isinstance(nested, dict):
            value = _num(nested.get("rating"))
            if value is not None:
                return value
    if row.get("review_status") == "accepted":
        return 4.0
    if row.get("review_status") == "needs_fix":
        return 2.5
    if row.get("review_status") == "rejected":
        return 1.0
    return None


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
