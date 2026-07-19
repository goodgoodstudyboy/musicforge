# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submission_export import read_submission_export_manifest as read_submission_export_manifest
from song_agent.domains.delivery.submissions import SIGNED_SUBMISSION_STATUSES as SIGNED_SUBMISSION_STATUSES, SubmissionBatch as SubmissionBatch, SubmissionItem as SubmissionItem, SubmissionNotFoundError as SubmissionNotFoundError, SubmissionStateError as SubmissionStateError, SubmissionStore as SubmissionStore, SubmissionValidationError as SubmissionValidationError, submission_batch_summary as submission_batch_summary, submission_item_current_snapshot as submission_item_current_snapshot
from song_agent.domains.delivery.v142_se_readiness import SubmissionEvidenceStoreReadinessMixin
from song_agent.domains.delivery import v142_se_readiness as _v142_se_readiness
from song_agent.domains.delivery.v142_se_evidence import SubmissionEvidenceStoreEvidenceMixin
from song_agent.domains.delivery import v142_se_evidence as _v142_se_evidence
from song_agent.domains.delivery.v142_se_lifecycle import SubmissionEvidenceStoreLifecycleMixin
from song_agent.domains.delivery import v142_se_lifecycle as _v142_se_lifecycle



SUBMISSION_EVIDENCE_SCHEMA_VERSION = 1
SUBMISSION_EVIDENCE_EXPORT_SCHEMA_VERSION = 1
SUBMISSION_EVIDENCE_SIGNOFF_EXCLUDE_KEYS = {"export_manifest_hash", "payload_hash"}
SUBMISSION_EVIDENCE_BLOCKED_PAYLOAD_KEYS = {
    *DISTRIBUTION_BLOCKED_KEYS,
    "source_path",
    "local_path",
    "file_path",
}
SUBMISSION_EVIDENCE_TYPES = {
    "submission_receipt",
    "platform_feedback",
    "acceptance_confirmation",
    "rejection_notice",
    "needs_changes_notice",
    "resubmission_receipt",
    "withdrawal_confirmation",
    "manual_note",
}
SUBMISSION_PLATFORM_STATUSES = {
    "draft",
    "submitted",
    "feedback_received",
    "needs_changes",
    "resubmitted",
    "accepted",
    "rejected",
    "withdrawn",
    "archived",
}
SUBMITTED_OR_LATER = {"submitted", "feedback_received", "needs_changes", "resubmitted", "accepted", "rejected", "withdrawn"}
ALLOWED_ATTACHMENT_TYPES = {"text/plain", "application/json", "text/csv", "image/png", "image/jpeg"}
ATTACHMENT_TYPE_EXTENSIONS = {
    "text/plain": {".txt"},
    "application/json": {".json"},
    "text/csv": {".csv"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
MAX_ITEM_ATTACHMENT_COUNT = 50
MAX_TOTAL_ATTACHMENT_BYTES = 200 * 1024 * 1024
HEX_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class SubmissionEvidenceError(Exception):
    pass


class SubmissionEvidenceNotFoundError(SubmissionEvidenceError):
    pass


class SubmissionEvidenceValidationError(SubmissionEvidenceError):
    pass


class SubmissionEvidenceStateError(SubmissionEvidenceError):
    pass


class SubmissionEvidenceStore(SubmissionEvidenceStoreReadinessMixin, SubmissionEvidenceStoreEvidenceMixin, SubmissionEvidenceStoreLifecycleMixin):
    def __init__(self, submission_store: SubmissionStore) -> None:
        self.submission_store = submission_store
        self.lock = threading.RLock()


















































def submission_evidence_record_integrity_hash(record: DomainDocument) -> str:
    return stable_hash({key: value for key, value in record.items() if key not in {"integrity_hash", "stale", "warnings"}})


def submission_evidence_record_integrity_ok(record: DomainDocument) -> bool:
    return bool(record.get("integrity_hash")) and str(record.get("integrity_hash")) == submission_evidence_record_integrity_hash(record)


def submission_evidence_attachment_integrity_hash(record: DomainDocument) -> str:
    return stable_hash({key: value for key, value in record.items() if key != "integrity_hash"})


def submission_evidence_attachment_integrity_ok(record: DomainDocument) -> bool:
    return bool(record.get("integrity_hash")) and str(record.get("integrity_hash")) == submission_evidence_attachment_integrity_hash(record)


def submission_evidence_report_integrity_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def submission_evidence_report_integrity_ok(report: DomainDocument) -> bool:
    return bool(report.get("integrity_hash")) and str(report.get("integrity_hash")) == submission_evidence_report_integrity_hash(report)


def submission_evidence_signoff_payload_hash(signoff: DomainDocument) -> str:
    return stable_hash({key: value for key, value in signoff.items() if key not in SUBMISSION_EVIDENCE_SIGNOFF_EXCLUDE_KEYS})


def submission_evidence_signoff_summary(signoff: DomainDocument | None) -> DomainDocument:
    data = _as_document(signoff)
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "submission_id": data.get("submission_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "require_submitted": bool(data.get("require_submitted", False)),
            "require_accepted": bool(data.get("require_accepted", False)),
            "submission_package_sha256": data.get("submission_package_sha256"),
            "report_hash": data.get("report_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def submission_evidence_report_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "submission_id": data.get("submission_id"),
            "source_hash": data.get("source_hash"),
            "integrity_hash": data.get("integrity_hash"),
            "item_count": summary.get("item_count", 0),
            "evidence_count": summary.get("evidence_count", 0),
            "attachment_count": summary.get("attachment_count", 0),
            "round_count": summary.get("round_count", 0),
            "submitted_count": summary.get("submitted_count", 0),
            "accepted_count": summary.get("accepted_count", 0),
            "stale_evidence_count": summary.get("stale_evidence_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _submission_evidence_signoff_export_summary(signoff: ImplementationDocument) -> ImplementationDocument:
    public = {
        "status": signoff.get("status") or "not_signed",
        "signed_by": signoff.get("signed_by"),
        "signed_at": signoff.get("signed_at"),
        "require_submitted": bool(signoff.get("require_submitted", False)),
        "require_accepted": bool(signoff.get("require_accepted", False)),
        "submission_package_sha256": signoff.get("submission_package_sha256"),
        "report_hash": signoff.get("report_hash"),
        "export_manifest_hash": signoff.get("export_manifest_hash"),
    }
    public["payload_hash"] = submission_evidence_signoff_payload_hash(public)
    return sanitize_metadata(public, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _submission_evidence_signoff_sidecar_record(signoff_public: ImplementationDocument) -> ImplementationDocument:
    return {
        "path": "submission-evidence-signoff.json",
        "payload_hash": submission_evidence_signoff_payload_hash(signoff_public),
        "payload_hash_excludes": sorted(SUBMISSION_EVIDENCE_SIGNOFF_EXCLUDE_KEYS),
    }


def _index_records(index: ImplementationDocument) -> list[ImplementationDocument]:
    return [row for row in index.get("evidence_records", []) if isinstance(row, dict)]


def _index_attachments(index: ImplementationDocument) -> list[ImplementationDocument]:
    return [row for row in index.get("attachments", []) if isinstance(row, dict)]


def _index_rounds(index: ImplementationDocument) -> list[ImplementationDocument]:
    return [row for row in index.get("rounds", []) if isinstance(row, dict)]


def _find_item(batch: SubmissionBatch, item_id: str) -> SubmissionItem:
    for item in batch.items:
        if item.item_id == item_id:
            return item
    raise SubmissionNotFoundError(item_id)


def _find_evidence(index: ImplementationDocument, evidence_id: str) -> ImplementationDocument:
    for row in _index_records(index):
        if row.get("evidence_id") == evidence_id:
            return row
    raise SubmissionEvidenceNotFoundError(evidence_id)


def _item_source_payload(item: SubmissionItem) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "item_id": item.item_id,
            "release_id": item.release_id,
            "submission_id": item.submission_id,
            "target_id": item.target_id,
            "profile_id": item.profile_id,
            "target_name": item.target_name,
            "package_id": item.package_id,
            "package_zip_sha256": item.package_zip_sha256,
            "distribution_manifest_hash": item.distribution_manifest_hash,
            "distribution_signoff_hash": item.distribution_signoff_hash,
            "target_summary": item.target_summary,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _attachment_hashes(index: ImplementationDocument, attachment_ids: list[str]) -> list[ImplementationDocument]:
    rows = []
    for row in _index_attachments(index):
        if row.get("attachment_id") in attachment_ids:
            rows.append({"attachment_id": row.get("attachment_id"), "sha256": row.get("sha256"), "size_bytes": row.get("size_bytes")})
    return sorted(rows, key=lambda row: str(row.get("attachment_id") or ""))


def _validated_attachment_ids(index: ImplementationDocument, item_id: str, raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SubmissionEvidenceValidationError("attachment_ids must be a list.")
    allowed = {str(row.get("attachment_id")) for row in _index_attachments(index) if row.get("item_id") == item_id}
    result: list[str] = []
    for value in raw:
        text = str(value or "").strip()
        if text not in allowed:
            raise SubmissionEvidenceValidationError(f"Unknown attachment id: {text}.")
        result.append(text)
    return result


def _reject_blocked_payload(value: Any, *, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            text = str(key).lower()
            if text in SUBMISSION_EVIDENCE_BLOCKED_PAYLOAD_KEYS:
                raise SubmissionEvidenceValidationError(f"Submission evidence payload must not contain {path + '.' if path else ''}{key}.")
            _reject_blocked_payload(item, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_blocked_payload(item, path=f"{path}[{index}]")


def _attachment_bytes(payload: ImplementationDocument) -> bytes:
    raw = payload.get("content_base64") or payload.get("data_base64")
    if not raw:
        raise SubmissionEvidenceValidationError("Attachment upload requires content_base64 or data_base64.")
    try:
        data = base64.b64decode(str(raw), validate=True)
    except Exception as exc:
        raise SubmissionEvidenceValidationError("Attachment content_base64 is invalid.") from exc
    if not data:
        raise SubmissionEvidenceValidationError("Attachment content is empty.")
    if len(data) > MAX_ATTACHMENT_SIZE_BYTES:
        raise SubmissionEvidenceValidationError("Attachment exceeds the 10 MB size limit.")
    return data


def _validate_content_type(raw: Any, data: bytes) -> str:
    content_type = str(raw or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise SubmissionEvidenceValidationError("Unsupported attachment content_type.")
    if content_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SubmissionEvidenceValidationError("image/png attachment does not have a PNG header.")
    if content_type == "image/jpeg" and not data.startswith(b"\xff\xd8"):
        raise SubmissionEvidenceValidationError("image/jpeg attachment does not have a JPEG header.")
    if content_type == "application/json":
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SubmissionEvidenceValidationError("application/json attachment is not valid UTF-8 JSON.") from exc
    if content_type in {"text/plain", "text/csv"}:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SubmissionEvidenceValidationError(f"{content_type} attachment is not valid UTF-8.") from exc
    return content_type


def _safe_filename(raw: Any, content_type: str) -> str:
    name = str(raw or "").strip()
    if not name or "/" in name or "\\" in name or ":" in name or name in {".", ".."}:
        raise SubmissionEvidenceValidationError("Attachment filename must be a safe basename.")
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    if not sanitized:
        raise SubmissionEvidenceValidationError("Attachment filename is invalid.")
    ext = Path(sanitized).suffix.lower()
    if ext not in ATTACHMENT_TYPE_EXTENSIONS[content_type]:
        raise SubmissionEvidenceValidationError("Attachment filename extension does not match content_type.")
    return sanitized[:160]


def _attachment_kind(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "screenshot"
    if content_type in {"application/json", "text/csv"}:
        return "receipt"
    return "note"


def _attachment_redaction_summary(content_type: str, data: bytes) -> ImplementationDocument:
    if content_type.startswith("image/"):
        return {"status": "passed", "finding_count": 0, "scan": "binary_header_only"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "failed", "finding_count": 1}
    sanitized = sanitize_sensitive_text(text)
    findings = 0 if sanitized == text else 1
    return {"status": "failed" if findings else "passed", "finding_count": findings}


def _safe_text(value: Any, limit: int) -> str | None:
    text = sanitize_sensitive_text(str(value or "")).strip()
    if not text:
        return None
    return text[:limit]


def _safe_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if "?" in raw or "#" in raw or "@" in raw:
        return None
    sanitized = sanitize_sensitive_text(raw)
    return sanitized[:300] if sanitized.startswith(("https://", "http://")) else None


def _validate_evidence_type(value: str) -> str:
    if value not in SUBMISSION_EVIDENCE_TYPES:
        raise SubmissionEvidenceValidationError(f"Unsupported evidence_type: {value}.")
    return value


def _validate_platform_status(value: str) -> str:
    if value not in SUBMISSION_PLATFORM_STATUSES:
        raise SubmissionEvidenceValidationError(f"Unsupported platform_status: {value}.")
    return value


def _default_evidence_title(evidence_type: str) -> str:
    return {
        "submission_receipt": "Submission receipt",
        "platform_feedback": "Platform feedback",
        "acceptance_confirmation": "Acceptance confirmation",
        "rejection_notice": "Rejection notice",
        "needs_changes_notice": "Needs changes notice",
        "resubmission_receipt": "Resubmission receipt",
        "withdrawal_confirmation": "Withdrawal confirmation",
        "manual_note": "Manual note",
    }.get(evidence_type, "Submission evidence")


def _latest_blocking_after_acceptance(summary: ImplementationDocument) -> str | None:
    timeline = _as_list(summary.get("timeline"))
    accepted_at = max([str(row.get("recorded_at") or "") for row in timeline if isinstance(row, dict) and row.get("evidence_type") == "acceptance_confirmation"], default="")
    if not accepted_at:
        return "missing_acceptance_confirmation"
    for row in timeline:
        if not isinstance(row, dict):
            continue
        if row.get("evidence_type") in {"needs_changes_notice", "rejection_notice"} and str(row.get("recorded_at") or "") > accepted_at:
            return str(row.get("evidence_id") or row.get("evidence_type"))
    return None


def _check(scope: str, item_id: Any, check_id: str, status: str, severity: str, message: str, **extra: Any) -> ImplementationDocument:
    row = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
    if item_id:
        row["item_id"] = item_id
    row.update({key: value for key, value in extra.items() if value is not None})
    return sanitize_metadata(row, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp-{os.getpid()}-{threading.get_ident()}.json"
    tmp_path.write_text(json.dumps(sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir, resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir).as_posix())
        if entry in seen:
            raise SubmissionEvidenceValidationError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise SubmissionEvidenceValidationError("Unsafe relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise SubmissionEvidenceValidationError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SubmissionEvidenceValidationError("Refusing to operate outside submission evidence boundaries.") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

_v142_se_readiness.bind_globals(globals())
_v142_se_evidence.bind_globals(globals())
_v142_se_lifecycle.bind_globals(globals())
