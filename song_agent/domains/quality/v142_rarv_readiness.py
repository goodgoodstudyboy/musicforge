# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.delivery.releases import stable_hash as stable_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

check = _make_deferred_global('check')
pattern = _make_deferred_global('pattern')

def bind_globals(namespace: dict[str, object]) -> None:
    global check, pattern
    check = namespace.get('check', check)
    pattern = namespace.get('pattern', pattern)
    _bind_deferred_defaults(namespace)


RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE = "release_audio_regression"
RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE = "release_audio_regression_verification"
RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = {
    "manifest.json",
    "regression-report.json",
    "track-regression-matrix.json",
    "issue-regression-index.json",
    "quality-delta-summary.json",
    "blocker-register.json",
    "baseline-binding.json",
    "current-binding.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"regression-signoff.json", "regression-signoff-history.jsonl"}
SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]




def _expected_documents(baseline_binding: DomainDocument, current_binding: DomainDocument, *, policy: DomainDocument) -> dict[str, DomainDocument]:
    baseline_tracks = _as_list(baseline_binding.get("facts"))
    current_tracks = _as_list(current_binding.get("facts"))
    baseline_by_key = {_identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage")): row for row in baseline_tracks if _identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage"))}
    current_by_key = {_identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage")): row for row in current_tracks if _identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage"))}
    keys = sorted(set(baseline_by_key) | set(current_by_key))
    rows: list[DomainDocument] = []
    issue_rows: list[DomainDocument] = []
    blockers: list[DomainDocument] = []
    warnings: list[DomainDocument] = []
    max_rating_drop = float(policy.get("max_rating_drop", 0.5) or 0.5)
    max_average_rating_drop = float(policy.get("max_average_rating_drop", 0.25) or 0.25)
    for key in keys:
        baseline = baseline_by_key.get(key, {})
        current = current_by_key.get(key, {})
        title = current.get("title") or baseline.get("title")
        identity_status = "matched" if baseline and current else "missing_current" if baseline else "missing_baseline"
        rating_delta = _num(current.get("manual_rating")) - _num(baseline.get("manual_rating")) if baseline and current else None
        new_high = max(0, int(current.get("high_issue_count") or 0) - int(baseline.get("high_issue_count") or 0))
        new_critical = max(0, int(current.get("critical_issue_count") or 0) - int(baseline.get("critical_issue_count") or 0))
        remediation_delta = int(current.get("remediation_count") or 0) - int(baseline.get("remediation_count") or 0)
        row_blockers: list[str] = []
        if identity_status != "matched":
            row_blockers.append(identity_status)
        if new_critical > 0:
            row_blockers.append("new_critical_issue")
        if new_high > 0:
            row_blockers.append("new_high_issue")
        if rating_delta is not None and rating_delta < -max_rating_drop:
            row_blockers.append("rating_drop")
        if current.get("test_fake_count"):
            row_blockers.append("test_fake_audio")
        if current.get("audio_health_status") == "failed":
            row_blockers.append("audio_health_failed")
        status = "failed" if row_blockers else "passed"
        if remediation_delta > int(policy.get("max_remediation_count_increase", 0) or 0) and not row_blockers:
            status = "warning"
            warnings.append(_blocker("remediation_count_increase", "Remediation count increased.", track_id=current.get("track_id") or baseline.get("track_id")))
        for blocker in row_blockers:
            blockers.append(_blocker(blocker, blocker.replace("_", " "), track_id=current.get("track_id") or baseline.get("track_id"), title=title))
        rows.append(
            {
                "track_key": key,
                "track_id": current.get("track_id") or baseline.get("track_id"),
                "title": title,
                "identity_status": identity_status,
                "baseline": baseline,
                "current": current,
                "delta": {
                    "manual_rating_delta": rating_delta,
                    "new_high_issue_count": new_high,
                    "new_critical_issue_count": new_critical,
                    "remediation_count_delta": remediation_delta,
                },
                "status": status,
                "blockers": row_blockers,
            }
        )
        if new_high or new_critical:
            issue_rows.append(
                {
                    "track_id": current.get("track_id") or baseline.get("track_id"),
                    "title": title,
                    "new_high_issue_count": new_high,
                    "new_critical_issue_count": new_critical,
                    "status": "failed",
                }
            )
    rating_deltas = [row.get("delta", {}).get("manual_rating_delta") for row in rows if isinstance(row.get("delta", {}).get("manual_rating_delta"), (int, float))]
    average_rating_delta = round(sum(rating_deltas) / len(rating_deltas), 4) if rating_deltas else 0.0
    if average_rating_delta < -max_average_rating_drop:
        blockers.append(_blocker("average_rating_drop", "Average manual rating dropped beyond policy threshold.", delta=average_rating_delta))
    matrix = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "rows": rows,
        "summary": {
            "track_count": len(rows),
            "matched_track_count": sum(1 for row in rows if row.get("identity_status") == "matched"),
            "failed_track_count": sum(1 for row in rows if row.get("status") == "failed"),
            "warning_track_count": sum(1 for row in rows if row.get("status") == "warning"),
            "passed_track_count": sum(1 for row in rows if row.get("status") == "passed"),
        },
    }
    issue_index = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "issue_taxonomy": issue_rows,
        "new_issues": issue_rows,
        "resolved_issues": [],
    }
    quality = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "metrics": {
            "average_manual_rating_delta": average_rating_delta,
            "min_manual_rating_delta": min(rating_deltas) if rating_deltas else 0,
            "high_issue_delta": sum(int(row.get("delta", {}).get("new_high_issue_count") or 0) for row in rows),
            "critical_issue_delta": sum(int(row.get("delta", {}).get("new_critical_issue_count") or 0) for row in rows),
            "remediation_count_delta": sum(int(row.get("delta", {}).get("remediation_count_delta") or 0) for row in rows),
        },
    }
    blocker_register = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "status": "failed" if blockers else "passed",
        "summary": {"blocker_count": len(blockers), "warning_count": len(warnings)},
        "blockers": blockers,
        "warnings": warnings,
    }
    status = "failed" if blockers else "warning" if warnings else "passed"
    quality["decision"] = {
        "status": status,
        "recommendation": "block_release_until_audio_regression_is_resolved" if blockers else "audio_regression_review_recommended" if warnings else "audio_regression_guard_passed",
        "blockers": [row.get("check_id") for row in blockers],
        "warnings": [row.get("check_id") for row in warnings],
    }
    source = {
        "baseline_binding_hash": baseline_binding.get("integrity_hash"),
        "current_binding_hash": current_binding.get("integrity_hash"),
        "policy_hash": stable_hash(policy or {}),
    }
    source["source_hash"] = stable_hash(source)
    for doc in (matrix, issue_index, quality, blocker_register):
        doc["source_hash"] = source["source_hash"]
        doc["integrity_hash"] = _integrity_hash(doc)
    quality_metrics = _as_document(quality.get("metrics"))
    report: DomainDocument = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "package_type": RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "status": status,
        "readiness": "blocked" if blockers else "warning_requires_audio_lead_review" if warnings else "ready",
        "summary": {
            **_as_document(matrix.get("summary")),
            "new_high_issue_count": quality_metrics.get("high_issue_delta"),
            "new_critical_issue_count": quality_metrics.get("critical_issue_delta"),
            "average_manual_rating_delta": average_rating_delta,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "policy": policy or {},
        "blockers": blockers,
        "warnings": warnings,
        "source": {**source, "track_matrix_hash": matrix.get("integrity_hash"), "issue_index_hash": issue_index.get("integrity_hash"), "quality_delta_hash": quality.get("integrity_hash"), "blocker_register_hash": blocker_register.get("integrity_hash")},
        "source_hash": source["source_hash"],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return {"report": report, "matrix": matrix, "issue_index": issue_index, "quality": quality, "blockers": blocker_register}

def _external_binding_checks(prefix: str, actual: DomainDocument, expected: DomainDocument) -> list[DomainDocument]:
    return [
        _check(f"release_audio_regression_{prefix}_binding_integrity", _integrity_ok(actual), f"{prefix} binding integrity is valid."),
        _check(f"release_audio_regression_{prefix}_binding_matches_external", _semantic_hash(_strip_binding(actual)) == _semantic_hash(_strip_binding(expected)), f"{prefix} binding matches external Timeline/Certification evidence."),
    ]

def _recomputed_document_checks(report: DomainDocument, matrix: DomainDocument, issue_index: DomainDocument, quality: DomainDocument, blockers: DomainDocument, expected: dict[str, DomainDocument]) -> list[DomainDocument]:
    return [
        _check("release_audio_regression_facts_recomputed", True, "Regression facts were recomputed from external Timeline/Certification packages."),
        _check("release_audio_regression_track_matrix_binding", _semantic_hash(matrix) == _semantic_hash(expected["matrix"]), "Track regression matrix matches recomputed external facts."),
        _check("release_audio_regression_issue_index_binding", _semantic_hash(issue_index) == _semantic_hash(expected["issue_index"]), "Issue regression index matches recomputed external facts."),
        _check("release_audio_regression_quality_delta_binding", _semantic_hash(quality) == _semantic_hash(expected["quality"]), "Quality delta summary matches recomputed external facts."),
        _check("release_audio_regression_blocker_register_binding", _semantic_hash(blockers) == _semantic_hash(expected["blockers"]), "Blocker register matches recomputed external facts."),
        _check("release_audio_regression_policy_decision_match", _semantic_hash(report.get("summary")) == _semantic_hash(expected["report"].get("summary")) and report.get("status") == expected["report"].get("status") and report.get("readiness") == expected["report"].get("readiness"), "Regression report decision matches recomputed external facts."),
        _check("release_audio_regression_internal_full_resign_guard", _semantic_hash(report) == _semantic_hash(expected["report"]), "Regression report is not an internally re-signed forgery."),
    ]

def _document_binding_checks(manifest: DomainDocument, report: DomainDocument, matrix: DomainDocument, issue_index: DomainDocument, quality: DomainDocument, blockers: DomainDocument, baseline: DomainDocument, current: DomainDocument) -> list[DomainDocument]:
    same_source = report.get("source_hash") == matrix.get("source_hash") == issue_index.get("source_hash") == quality.get("source_hash") == blockers.get("source_hash")
    return [
        _check("release_audio_regression_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds regression report."),
        _check("release_audio_regression_manifest_matrix_binding", manifest.get("track_matrix_hash") == matrix.get("integrity_hash"), "Manifest binds track matrix."),
        _check("release_audio_regression_manifest_issue_binding", manifest.get("issue_index_hash") == issue_index.get("integrity_hash"), "Manifest binds issue index."),
        _check("release_audio_regression_manifest_quality_binding", manifest.get("quality_delta_hash") == quality.get("integrity_hash"), "Manifest binds quality delta."),
        _check("release_audio_regression_manifest_blocker_binding", manifest.get("blocker_register_hash") == blockers.get("integrity_hash"), "Manifest binds blocker register."),
        _check("release_audio_regression_manifest_baseline_binding", manifest.get("baseline_binding_hash") == baseline.get("integrity_hash"), "Manifest binds baseline binding."),
        _check("release_audio_regression_manifest_current_binding", manifest.get("current_binding_hash") == current.get("integrity_hash"), "Manifest binds current binding."),
        _check("release_audio_regression_source_binding", same_source and manifest.get("source_hash") == report.get("source_hash"), "Regression documents bind same source hash."),
    ]

def _signoff_checks(signoff: DomainDocument | None, history: list[DomainDocument], manifest: DomainDocument, report: DomainDocument, matrix: DomainDocument, issue_index: DomainDocument, quality: DomainDocument, blockers: DomainDocument, baseline: DomainDocument, current: DomainDocument, *, require_signed: bool) -> list[DomainDocument]:
    if signoff is None:
        return [_check("release_audio_regression_signoff_present", not require_signed, "Regression signoff is present when required.")]
    latest = history[-1] if history else {}
    return [
        _check("release_audio_regression_signoff_integrity", _integrity_ok(signoff), "Regression signoff integrity is valid."),
        _check("release_audio_regression_signoff_status", signoff.get("status") == "signed", "Regression signoff status is signed."),
        _check("release_audio_regression_signoff_report_binding", signoff.get("regression_report_hash") == report.get("integrity_hash") == manifest.get("report_hash"), "Regression signoff binds report."),
        _check("release_audio_regression_signoff_matrix_binding", signoff.get("track_matrix_hash") == matrix.get("integrity_hash"), "Regression signoff binds matrix."),
        _check("release_audio_regression_signoff_issue_binding", signoff.get("issue_index_hash") == issue_index.get("integrity_hash"), "Regression signoff binds issue index."),
        _check("release_audio_regression_signoff_quality_binding", signoff.get("quality_delta_hash") == quality.get("integrity_hash"), "Regression signoff binds quality delta."),
        _check("release_audio_regression_signoff_blocker_binding", signoff.get("blocker_register_hash") == blockers.get("integrity_hash"), "Regression signoff binds blockers."),
        _check("release_audio_regression_signoff_baseline_binding", signoff.get("baseline_binding_hash") == baseline.get("integrity_hash"), "Regression signoff binds baseline."),
        _check("release_audio_regression_signoff_current_binding", signoff.get("current_binding_hash") == current.get("integrity_hash"), "Regression signoff binds current evidence."),
        _check("release_audio_regression_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds signoff."),
        _check("release_audio_regression_signoff_history_chain", _history_chain_ok(history), "Regression signoff history hash chain is valid."),
        _check("release_audio_regression_signoff_history_latest", (latest.get("payload") or {}).get("signoff_hash") == signoff.get("integrity_hash"), "Latest signoff history event binds current signoff."),
    ]

def _history_chain_ok(history: list[DomainDocument]) -> bool:
    previous: str | None = None
    for event in history:
        payload = _as_document(event.get("payload"))
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[DomainDocument]:
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
        _check("release_audio_regression_manifest_files_present", bool(files), "Manifest declares package files."),
        _check("release_audio_regression_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)),
        _check("release_audio_regression_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}),
        _check("release_audio_regression_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match fixed Regression layout.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}),
        _check("release_audio_regression_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}),
    ]

def _finish(checks: list[DomainDocument], summary: DomainDocument, *extra: DomainDocument) -> DomainDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
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
    report["integrity_hash"] = _integrity_hash(report)
    return report

def _check(check_id: str, passed: bool, message: str, details: DomainDocument | None = None, *, blocking: bool = True) -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    with archive.open(name) as handle:
        data = json.loads(handle.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data

def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    with archive.open(name) as handle:
        for raw in handle.read().decode("utf-8").splitlines():
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

def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("release_audio_regression_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})

def _certification_signoff_hash(cert_zip: Path) -> str | None:
    try:
        with zipfile.ZipFile(cert_zip) as archive:
            if "certification-signoff.json" not in [item.filename for item in archive.infolist()]:
                return None
            return _read_json_entry(archive, "certification-signoff.json").get("integrity_hash")
    except Exception:
        return None

def _manual_rating(row: DomainDocument) -> float:
    value = row.get("manual_rating") or row.get("rating")
    if isinstance(value, (int, float)):
        return float(value)
    if row.get("review_status") == "accepted":
        return 5.0
    if row.get("review_status") == "needs_fix":
        return 3.0
    if row.get("review_status") == "rejected":
        return 1.0
    return 0.0

def _identity_key(row: DomainDocument, *, mode: str) -> str:
    if mode == "same_artifact_repeat_check":
        value = stable_hash({"project_id": row.get("project_id"), "title": _normalize_title(row.get("title")), "final_export_hash": row.get("final_export_hash")})
    else:
        value = stable_hash({"title": _normalize_title(row.get("title"))})
    return value if row.get("project_id") or row.get("title") else ""

def _normalize_title(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")

def _num(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0

def _blocker(check_id: str, message: str, **details: object) -> DomainDocument:
    return {"check_id": check_id, "message": message, **details}

def _strip_binding(binding: DomainDocument) -> DomainDocument:
    return {key: value for key, value in binding.items() if key not in {"payload_hash", "integrity_hash"}}

def _semantic_hash(value: object) -> str:
    return stable_hash(_strip_volatile(value))

def _strip_volatile(value: object) -> object:
    if isinstance(value, dict):
        return {key: _strip_volatile(item) for key, item in value.items() if key not in {"generated_at", "created_at", "updated_at", "integrity_hash", "payload_hash"}}
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)

def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
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
