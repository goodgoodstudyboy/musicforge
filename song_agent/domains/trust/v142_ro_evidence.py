# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_text as _as_text
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.quality.audio_encoding import AudioEncodingStore as AudioEncodingStore
from song_agent.domains.quality.audio_review_evidence import AudioReviewEvidenceStore as AudioReviewEvidenceStore, audio_review_summary_public as audio_review_summary_public
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore, distribution_signoff_summary as distribution_signoff_summary, distribution_target_summary as distribution_target_summary
from song_agent.domains.delivery.distribution_export import distribution_export_summary as distribution_export_summary, read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore as EncodedAudioAcceptanceStore, encoded_audio_acceptance_summary_public as encoded_audio_acceptance_summary_public
from song_agent.domains.delivery.format_decisions import FormatDecisionStore as FormatDecisionStore, format_decision_export_summary as format_decision_export_summary
from song_agent.domains.quality.mastering_qa import MasteringStore as MasteringStore
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio import read_release_audio_qa as read_release_audio_qa, release_audio_summary as release_audio_summary
from song_agent.domains.delivery.release_export import read_release_export_manifest as read_release_export_manifest, release_export_summary as release_export_summary
from song_agent.domains.delivery.release_metadata import metadata_export_summary as metadata_export_summary, read_release_metadata as read_release_metadata, read_release_metadata_qa as read_release_metadata_qa, release_metadata_summary as release_metadata_summary
from song_agent.domains.delivery.release_metadata_qa import release_metadata_qa_summary as release_metadata_qa_summary
from song_agent.domains.delivery.release_qa import release_qa_summary as release_qa_summary, release_signoff_summary as release_signoff_summary
from song_agent.domains.delivery.release_verifier import verification_summary as verification_summary, verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, release_document_source as release_document_source, release_summary as release_summary, stable_hash as stable_hash
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore as RightsClearanceStore, rights_report_integrity_ok as rights_report_integrity_ok, rights_summary_hash as rights_summary_hash
from song_agent.domains.delivery.submission_evidence import SUBMITTED_OR_LATER as SUBMITTED_OR_LATER, SubmissionEvidenceStore as SubmissionEvidenceStore, submission_evidence_report_summary as submission_evidence_report_summary, submission_evidence_signoff_summary as submission_evidence_signoff_summary
from song_agent.domains.delivery.submission_evidence_verifier import submission_evidence_verification_summary as submission_evidence_verification_summary, verify_submission_evidence_package as verify_submission_evidence_package
from song_agent.domains.delivery.submission_export import read_submission_export_manifest as read_submission_export_manifest, submission_export_summary as submission_export_summary
from song_agent.domains.delivery.submission_verifier import submission_verification_summary as submission_verification_summary, verify_submission_package as verify_submission_package
from song_agent.domains.delivery.submissions import SubmissionStore as SubmissionStore, submission_batch_summary as submission_batch_summary, submission_signoff_summary as submission_signoff_summary
from song_agent.domains.trust.release_operations_contracts import OPERATIONS_BLOCKED_KEYS as OPERATIONS_BLOCKED_KEYS, REPORT_HASH_EXCLUDE_KEYS as REPORT_HASH_EXCLUDE_KEYS, operations_report_integrity_hash as operations_report_integrity_hash

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

ReleaseOperationsError = _make_deferred_global('ReleaseOperationsError')
ReleaseOperationsStore = _make_deferred_global('ReleaseOperationsStore')
part = _make_deferred_global('part')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseOperationsError, ReleaseOperationsStore, part, row
    ReleaseOperationsError = namespace.get('ReleaseOperationsError', ReleaseOperationsError)
    ReleaseOperationsStore = namespace.get('ReleaseOperationsStore', ReleaseOperationsStore)
    part = namespace.get('part', part)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)


OPERATIONS_SCHEMA_VERSION = 1
OPERATIONS_EXPORT_SCHEMA_VERSION = 1
OPERATIONS_STAGES = [
    "draft",
    "project_ready",
    "release_ready",
    "audio_ready",
    "metadata_ready",
    "rights_ready",
    "format_ready",
    "distribution_ready",
    "submission_ready",
    "submitted",
    "accepted",
    "archived",
]




def _action_for_check(check_id: str) -> DomainDocument:
    mapping = {
        "release_tracks_exist": ("release", "release.add_track", "Add Release Track", "Add at least one signed project to the release."),
        "release_qa_passed": ("release", "release.qa.refresh", "Refresh Release QA", "Refresh Release QA and fix blockers."),
        "release_export_exists": ("release", "release.export", "Build Release Export", "Build the Release Export bundle."),
        "release_zip_exists": ("release", "release.zip", "Build Release ZIP", "Build the Release ZIP."),
        "release_signoff_exists": ("release", "release.signoff", "Sign Release", "Sign the Release after QA and export are current."),
        "release_zip_verify": ("release", "release.verify", "Verify Release ZIP", "Run the Release ZIP verifier."),
        "metadata_qa_missing_or_failed": ("metadata", "metadata.qa.refresh", "Refresh Metadata QA", "Refresh Metadata QA and fix required fields."),
        "metadata_export_missing": ("metadata", "metadata.export", "Export Metadata", "Export platform metadata files."),
        "audio_health_failed": ("audio", "audio.render_or_health", "Refresh Audio QA", "Render audio or refresh Release Audio QA."),
        "audio_review_missing": ("audio", "audio.review", "Complete Audio Review", "Complete current per-track manual audio reviews."),
        "mastering_not_ready": ("audio", "mastering.select", "Complete Mastering", "Select and review a mastered candidate."),
        "encoded_audio_not_ready": ("audio", "encoded.render", "Render Encoded Audio", "Render required encoded audio formats."),
        "encoded_review_missing": ("audio", "encoded.review", "Review Encoded Audio", "Complete encoded format listening reviews."),
        "rights_clearance_failed": ("rights", "rights.refresh", "Refresh Rights Clearance", "Fix rights clearance and refresh the report."),
        "format_decision_failed": ("format_decision", "format_decision.refresh", "Complete Format Decision", "Create or refresh a format decision report."),
        "distribution_qa_missing": ("distribution", "distribution.qa.refresh", "Refresh Distribution QA", "Refresh target QA."),
        "distribution_export_missing": ("distribution", "distribution.export", "Build Distribution Export", "Build target export."),
        "distribution_zip_missing": ("distribution", "distribution.zip", "Build Distribution ZIP", "Build target ZIP."),
        "distribution_signoff_missing": ("distribution", "distribution.signoff", "Sign Distribution", "Sign target package."),
        "distribution_verify_failed": ("distribution", "distribution.verify", "Verify Distribution", "Run distribution verifier."),
        "submission_qa_missing": ("submission", "submission.qa.refresh", "Refresh Submission QA", "Refresh submission QA."),
        "submission_export_missing": ("submission", "submission.export", "Build Submission Export", "Build submission export."),
        "submission_zip_missing": ("submission", "submission.zip", "Build Submission ZIP", "Build submission ZIP."),
        "submission_signoff_missing": ("submission", "submission.signoff", "Sign Submission", "Sign submission package."),
        "submission_verify_failed": ("submission", "submission.verify", "Verify Submission", "Run submission verifier."),
        "submission_item_not_submitted": ("submission", "submission.record_receipt", "Record Submission Receipt", "Record submitted-or-later evidence for each submission item."),
        "submission_evidence_report_missing": ("submission_evidence", "submission_evidence.report.refresh", "Refresh Evidence Report", "Refresh submission evidence report."),
        "submission_evidence_acceptance_missing": ("submission_evidence", "submission_evidence.acceptance", "Record Acceptance Evidence", "Record platform acceptance evidence."),
        "submission_evidence_export_missing": ("submission_evidence", "submission_evidence.export", "Build Evidence Export", "Build submission evidence export."),
        "submission_evidence_zip_missing": ("submission_evidence", "submission_evidence.zip", "Build Evidence ZIP", "Build submission evidence ZIP."),
        "submission_evidence_signoff_missing": ("submission_evidence", "submission_evidence.signoff", "Sign Evidence", "Sign submission evidence archive."),
        "submission_evidence_verify_failed": ("submission_evidence", "submission_evidence.verify", "Verify Evidence", "Run submission evidence verifier."),
        "package_verifier_failed": ("verifiers", "package.verify", "Verify Package", "Run the relevant package verifier and fix blockers."),
    }
    domain, action_type, label, description = mapping.get(check_id, ("operations", "operations.refresh", "Refresh Operations", "Refresh the Operations report."))
    return {"priority": _action_priority(action_type), "domain": domain, "scope": domain, "action_type": action_type, "label": label, "description": description, "api_hint": ""}

def _action_priority(action_type: str) -> int:
    order = ["release.add_track", "release.qa.refresh", "release.export", "release.zip", "release.signoff", "distribution.qa.refresh", "distribution.export", "distribution.zip", "distribution.signoff", "submission.qa.refresh", "submission.export", "submission.zip", "submission.signoff", "submission.record_receipt", "submission_evidence.report.refresh", "submission_evidence.acceptance", "submission_evidence.export", "submission_evidence.zip", "submission_evidence.signoff"]
    try:
        return order.index(action_type) + 1
    except ValueError:
        return 100

def _stage_statuses(domains: DomainDocument) -> list[DomainDocument]:
    blockers_by_stage: dict[str, list[DomainDocument]] = {}
    warnings_by_stage: dict[str, list[DomainDocument]] = {}
    for domain in domains.values():
        if not isinstance(domain, dict):
            continue
        for item in domain.get("blockers", []) if isinstance(domain.get("blockers"), list) else []:
            if isinstance(item, dict):
                blockers_by_stage.setdefault(str(item.get("stage") or "release_ready"), []).append(item)
        for item in domain.get("warnings", []) if isinstance(domain.get("warnings"), list) else []:
            if isinstance(item, dict):
                warnings_by_stage.setdefault(str(item.get("stage") or "release_ready"), []).append(item)
    statuses: list[DomainDocument] = []
    for stage in OPERATIONS_STAGES:
        if stage == "draft":
            statuses.append({"stage": stage, "status": "passed"})
            continue
        if stage == "archived":
            statuses.append({"stage": stage, "status": "pending"})
            continue
        failed = blockers_by_stage.get(stage, [])
        warning_count = len(warnings_by_stage.get(stage, []))
        status = "failed" if failed else "warning" if warning_count else "passed"
        statuses.append({"stage": stage, "status": status, "blocker_count": len(failed), "warning_count": warning_count})
    return statuses

def _current_stage(stage_statuses: list[DomainDocument]) -> tuple[str, str | None]:
    current = "draft"
    for item in stage_statuses:
        stage = str(item.get("stage") or "")
        if item.get("status") in {"passed", "warning"}:
            current = stage
            continue
        if stage == "archived" and item.get("status") == "pending":
            return current, stage
        return current, stage
    return current, None

def _stage_progress(stage_statuses: list[DomainDocument]) -> DomainDocument:
    total = len(stage_statuses)
    completed = sum(1 for item in stage_statuses if item.get("status") in {"passed", "warning"})
    return {"completed": completed, "total": total, "percent": int(round((completed / total) * 100)) if total else 0}

def _domain_items(domains: DomainDocument, key: str) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for domain_id, domain in domains.items():
        if not isinstance(domain, dict):
            continue
        for item in domain.get(key, []) if isinstance(domain.get(key), list) else []:
            if isinstance(item, dict):
                rows.append({**item, "domain": item.get("domain") or domain_id})
    return rows

def _renumber(rows: list[DomainDocument], key: str, prefix: str) -> list[DomainDocument]:
    return [{**row, key: f"{prefix}-{index:06d}"} for index, row in enumerate(rows, start=1)]

def _package_summary(path: Path, *, status: str) -> DomainDocument:
    if not path or not path.exists() or not path.is_file() or path.is_symlink():
        return {"status": status, "exists": False}
    return {"status": status, "exists": True, "filename": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _package_summary_count(package_summaries: DomainDocument) -> int:
    count = 1 if isinstance(package_summaries.get("release_zip"), dict) and package_summaries["release_zip"].get("exists") else 0
    for key in ("distribution_packages", "submission_packages", "submission_evidence_packages"):
        count += sum(1 for item in package_summaries.get(key, []) if isinstance(item, dict) and item.get("exists"))
    return count

def _summary_status(value: DomainDocument | None) -> DomainDocument:
    data = _as_document(value)
    if not data:
        return {"status": "missing"}
    summary = _as_document(data.get("summary"))
    return sanitize_metadata({**summary, "status": data.get("status") or summary.get("status") or "present", "source_hash": data.get("source_hash") or summary.get("source_hash"), "integrity_hash": data.get("integrity_hash") or summary.get("integrity_hash")}, blocked_keys=OPERATIONS_BLOCKED_KEYS)

def _rights_summary(report: DomainDocument) -> DomainDocument:
    if not report:
        return {"status": "missing"}
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status") or summary.get("status") or "present",
            "release_id": report.get("release_id"),
            "track_count": summary.get("track_count", 0),
            "manual_cleared_track_count": summary.get("manual_cleared_track_count", 0),
            "source_usage_count": summary.get("source_usage_count", 0),
            "integrity_ok": rights_report_integrity_ok(report),
            "summary_hash": rights_summary_hash(summary) if summary else None,
        },
        blocked_keys=OPERATIONS_BLOCKED_KEYS,
    )

def _operations_signoff_summary_for_report(store: ReleaseOperationsStore, release_id: str, current_source_hash: str) -> DomainDocument:
    path = store.operations_dir(release_id) / "operations-signoff.json"
    if not path.exists():
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    try:
        signoff = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "failed", "integrity_ok": False, "stale": True}
    if not isinstance(signoff, dict):
        return {"status": "failed", "integrity_ok": False, "stale": True}
    payload_hash = str(signoff.get("payload_hash") or "")
    actual_hash = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "export_manifest_hash", "updated_at"}})
    integrity_ok = bool(payload_hash) and payload_hash == actual_hash
    stale = bool(signoff.get("source_hash")) and str(signoff.get("source_hash")) != str(current_source_hash)
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "missing",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "force": bool(signoff.get("force")),
            "payload_hash": signoff.get("payload_hash"),
            "integrity_ok": integrity_ok,
            "payload_hash_ok": integrity_ok,
            "stale": stale,
            "source_hash": signoff.get("source_hash"),
            "current_source_hash": current_source_hash,
        },
        blocked_keys=OPERATIONS_BLOCKED_KEYS,
    )

def _apply_operations_signoff_stage(stage_statuses: list[DomainDocument], signoff_summary: DomainDocument) -> list[DomainDocument]:
    rows = [dict(item) for item in stage_statuses]
    for item in rows:
        if item.get("stage") != "archived":
            continue
        status = str(signoff_summary.get("status") or "")
        if status in {"signed", "force_signed"} and signoff_summary.get("integrity_ok") and not signoff_summary.get("stale"):
            item.update({"status": "passed", "blocker_count": 0, "warning_count": 0})
        elif status in {"signed", "force_signed"}:
            item.update({"status": "failed", "blocker_count": 1, "warning_count": 0})
        else:
            item.update({"status": "pending", "blocker_count": 0, "warning_count": 0})
        break
    return rows

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    lines = [
        "MusicForge Release Operations Package",
        "",
        f"Release ID: {report.get('release_id')}",
        f"Status: {report.get('status')}",
        f"Current Stage: {report.get('current_stage')}",
        f"Next Stage: {report.get('next_stage') or '-'}",
        f"Blockers: {summary.get('blocker_count', 0)}",
        f"Warnings: {summary.get('warning_count', 0)}",
        "",
        "This package contains summary evidence only. It does not include audio, artwork, distribution packages, submission packages, or attachments.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _next_report_id(root: Path, *, existing: str | None = None) -> str:
    if existing:
        return existing
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1_000_000):
        report_id = f"ops-{index:06d}"
        if not (root / f"{report_id}.json").exists():
            return report_id
    raise ReleaseOperationsError("Unable to allocate operations report id.")

def _write_json(path: Path, data: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_BLOCKED_KEYS))

def _file_record(export_dir: Path, path: Path) -> DomainDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleaseOperationsError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsError("Refusing to operate outside release operations boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
