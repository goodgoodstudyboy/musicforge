# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submission_export import read_submission_export_manifest as read_submission_export_manifest
from song_agent.domains.delivery.submissions import SIGNED_SUBMISSION_STATUSES as SIGNED_SUBMISSION_STATUSES, SubmissionBatch as SubmissionBatch, SubmissionItem as SubmissionItem, SubmissionNotFoundError as SubmissionNotFoundError, SubmissionStateError as SubmissionStateError, SubmissionStore as SubmissionStore, SubmissionValidationError as SubmissionValidationError, submission_batch_summary as submission_batch_summary, submission_item_current_snapshot as submission_item_current_snapshot

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

MAX_TOTAL_ATTACHMENT_BYTES = _make_deferred_global('MAX_TOTAL_ATTACHMENT_BYTES')
SubmissionEvidenceNotFoundError = _make_deferred_global('SubmissionEvidenceNotFoundError')
SubmissionEvidenceStateError = _make_deferred_global('SubmissionEvidenceStateError')
SubmissionEvidenceValidationError = _make_deferred_global('SubmissionEvidenceValidationError')
_attachment_bytes = _make_deferred_global('_attachment_bytes')
_attachment_kind = _make_deferred_global('_attachment_kind')
_attachment_redaction_summary = _make_deferred_global('_attachment_redaction_summary')
_check = _make_deferred_global('_check')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_find_evidence = _make_deferred_global('_find_evidence')
_find_item = _make_deferred_global('_find_item')
_index_attachments = _make_deferred_global('_index_attachments')
_index_records = _make_deferred_global('_index_records')
_index_rounds = _make_deferred_global('_index_rounds')
_latest_blocking_after_acceptance = _make_deferred_global('_latest_blocking_after_acceptance')
_reject_blocked_payload = _make_deferred_global('_reject_blocked_payload')
_safe_filename = _make_deferred_global('_safe_filename')
_safe_text = _make_deferred_global('_safe_text')
_sha256_file = _make_deferred_global('_sha256_file')
_submission_evidence_signoff_export_summary = _make_deferred_global('_submission_evidence_signoff_export_summary')
_submission_evidence_signoff_sidecar_record = _make_deferred_global('_submission_evidence_signoff_sidecar_record')
_validate_content_type = _make_deferred_global('_validate_content_type')
_write_json = _make_deferred_global('_write_json')
_zip_entries = _make_deferred_global('_zip_entries')
check = _make_deferred_global('check')
key = _make_deferred_global('key')
row = _make_deferred_global('row')
submission_evidence_attachment_integrity_hash = _make_deferred_global('submission_evidence_attachment_integrity_hash')
submission_evidence_record_integrity_ok = _make_deferred_global('submission_evidence_record_integrity_ok')
submission_evidence_report_integrity_hash = _make_deferred_global('submission_evidence_report_integrity_hash')
submission_evidence_report_summary = _make_deferred_global('submission_evidence_report_summary')
submission_evidence_signoff_payload_hash = _make_deferred_global('submission_evidence_signoff_payload_hash')
submission_evidence_signoff_summary = _make_deferred_global('submission_evidence_signoff_summary')

def bind_globals(namespace: dict[str, object]) -> None:
    global MAX_TOTAL_ATTACHMENT_BYTES, SubmissionEvidenceNotFoundError, SubmissionEvidenceStateError, SubmissionEvidenceValidationError, _attachment_bytes, _attachment_kind, _attachment_redaction_summary, _check
    global _ensure_within, _file_record, _find_evidence, _find_item, _index_attachments, _index_records, _index_rounds, _latest_blocking_after_acceptance
    global _reject_blocked_payload, _safe_filename, _safe_text, _sha256_file, _submission_evidence_signoff_export_summary, _submission_evidence_signoff_sidecar_record, _validate_content_type
    global _write_json, _zip_entries, check, key, row, submission_evidence_attachment_integrity_hash, submission_evidence_record_integrity_ok, submission_evidence_report_integrity_hash
    global submission_evidence_report_summary, submission_evidence_signoff_payload_hash, submission_evidence_signoff_summary
    MAX_TOTAL_ATTACHMENT_BYTES = namespace.get('MAX_TOTAL_ATTACHMENT_BYTES', MAX_TOTAL_ATTACHMENT_BYTES)
    SubmissionEvidenceNotFoundError = namespace.get('SubmissionEvidenceNotFoundError', SubmissionEvidenceNotFoundError)
    SubmissionEvidenceStateError = namespace.get('SubmissionEvidenceStateError', SubmissionEvidenceStateError)
    SubmissionEvidenceValidationError = namespace.get('SubmissionEvidenceValidationError', SubmissionEvidenceValidationError)
    _attachment_bytes = namespace.get('_attachment_bytes', _attachment_bytes)
    _attachment_kind = namespace.get('_attachment_kind', _attachment_kind)
    _attachment_redaction_summary = namespace.get('_attachment_redaction_summary', _attachment_redaction_summary)
    _check = namespace.get('_check', _check)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _find_evidence = namespace.get('_find_evidence', _find_evidence)
    _find_item = namespace.get('_find_item', _find_item)
    _index_attachments = namespace.get('_index_attachments', _index_attachments)
    _index_records = namespace.get('_index_records', _index_records)
    _index_rounds = namespace.get('_index_rounds', _index_rounds)
    _latest_blocking_after_acceptance = namespace.get('_latest_blocking_after_acceptance', _latest_blocking_after_acceptance)
    _reject_blocked_payload = namespace.get('_reject_blocked_payload', _reject_blocked_payload)
    _safe_filename = namespace.get('_safe_filename', _safe_filename)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _submission_evidence_signoff_export_summary = namespace.get('_submission_evidence_signoff_export_summary', _submission_evidence_signoff_export_summary)
    _submission_evidence_signoff_sidecar_record = namespace.get('_submission_evidence_signoff_sidecar_record', _submission_evidence_signoff_sidecar_record)
    _validate_content_type = namespace.get('_validate_content_type', _validate_content_type)
    _write_json = namespace.get('_write_json', _write_json)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    check = namespace.get('check', check)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    submission_evidence_attachment_integrity_hash = namespace.get('submission_evidence_attachment_integrity_hash', submission_evidence_attachment_integrity_hash)
    submission_evidence_record_integrity_ok = namespace.get('submission_evidence_record_integrity_ok', submission_evidence_record_integrity_ok)
    submission_evidence_report_integrity_hash = namespace.get('submission_evidence_report_integrity_hash', submission_evidence_report_integrity_hash)
    submission_evidence_report_summary = namespace.get('submission_evidence_report_summary', submission_evidence_report_summary)
    submission_evidence_signoff_payload_hash = namespace.get('submission_evidence_signoff_payload_hash', submission_evidence_signoff_payload_hash)
    submission_evidence_signoff_summary = namespace.get('submission_evidence_signoff_summary', submission_evidence_signoff_summary)
    _bind_deferred_defaults(namespace)


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
MAX_ITEM_ATTACHMENT_COUNT = 50




class SubmissionEvidenceStoreReadinessMixin:
    def evidence_dir(self, release_id: str, submission_id: str) -> Path:
        return self.submission_store.submission_dir(release_id, submission_id) / "evidence"

    def index_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-index.json"

    def events_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-events.jsonl"

    def report_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-report.json"

    def signoff_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-signoff.json"

    def signoff_history_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-signoff-history.jsonl"

    def export_dir(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "evidence-export"

    def package_zip_path(self, release_id: str, submission_id: str) -> Path:
        return self.evidence_dir(release_id, submission_id) / "submission-evidence-package.zip"

    def read_index(self, release_id: str, submission_id: str) -> DomainDocument:
        self.submission_store.get_submission(release_id, submission_id)
        path = self.index_path(release_id, submission_id)
        if not path.exists():
            return self._empty_index(release_id, submission_id)
        value = read_json(path)
        return sanitize_metadata(_document_or(value, self._empty_index(release_id, submission_id)), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_index(self, release_id: str, submission_id: str, index: DomainDocument) -> DomainDocument:
        clean = sanitize_metadata(index, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.index_path(release_id, submission_id), clean)
        return clean

    def read_report(self, release_id: str, submission_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.report_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionEvidenceNotFoundError("Submission evidence report does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def read_signoff(self, release_id: str, submission_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.signoff_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionEvidenceNotFoundError("Submission evidence signoff does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def overview(self, release_id: str, submission_id: str) -> DomainDocument:
        batch = self.submission_store.get_submission(release_id, submission_id)
        index = self.read_index(release_id, submission_id)
        report = self.read_report(release_id, submission_id, default={})
        signoff = self.read_signoff(release_id, submission_id, default={})
        return sanitize_metadata(
            {
                "release_id": release_id,
                "submission_id": submission_id,
                "summary": self.index_summary(index, batch=batch),
                "report_summary": submission_evidence_report_summary(report),
                "signoff_summary": submission_evidence_signoff_summary(signoff),
                "items": self.item_summaries(release_id, submission_id, index=index, batch=batch),
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    def upload_attachment(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            _reject_blocked_payload(payload)
            self._ensure_mutable_evidence(release_id, submission_id)
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            item = _find_item(batch, item_id)
            index = self.read_index(release_id, submission_id)
            item_attachment_count = sum(1 for row in _index_attachments(index) if row.get("item_id") == item.item_id)
            if item_attachment_count >= MAX_ITEM_ATTACHMENT_COUNT:
                raise SubmissionEvidenceValidationError("Submission evidence item attachment limit reached.")
            total_bytes = sum(int(row.get("size_bytes") or 0) for row in _index_attachments(index))
            content = _attachment_bytes(payload)
            if total_bytes + len(content) > MAX_TOTAL_ATTACHMENT_BYTES:
                raise SubmissionEvidenceValidationError("Submission evidence total attachment size limit reached.")
            content_type = _validate_content_type(payload.get("content_type"), content)
            filename = _safe_filename(payload.get("filename"), content_type)
            attachment_id = self._next_attachment_id(index)
            item_dir = self.evidence_dir(release_id, submission_id) / "items" / item.item_id / "attachments"
            item_dir.mkdir(parents=True, exist_ok=True)
            bin_path = item_dir / f"{attachment_id}.bin"
            bin_path.write_bytes(content)
            created_at = str(payload.get("created_at") or now_iso())
            record = {
                "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
                "attachment_id": attachment_id,
                "release_id": release_id,
                "submission_id": submission_id,
                "item_id": item.item_id,
                "filename": filename,
                "stored_filename": f"{attachment_id}.bin",
                "content_type": content_type,
                "kind": _safe_text(payload.get("kind"), 80) or _attachment_kind(content_type),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "created_by": _safe_text(payload.get("created_by"), 120) or "local-user",
                "created_at": created_at,
                "redaction_summary": _attachment_redaction_summary(content_type, content),
            }
            record["integrity_hash"] = submission_evidence_attachment_integrity_hash(record)
            write_json(item_dir / f"{attachment_id}.json", sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
            attachments = _index_attachments(index)
            attachments.append(record)
            index["attachments"] = sorted(attachments, key=lambda row: str(row.get("attachment_id") or ""))
            index["updated_at"] = now_iso()
            self.write_index(release_id, submission_id, index)
            self.append_event(release_id, submission_id, "submission_evidence_attachment_uploaded", {"item_id": item.item_id, "attachment_id": attachment_id})
            return record

    def record_submission(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> tuple[SubmissionBatch, DomainDocument]:
        with self.lock:
            self._preflight_external_update(release_id, submission_id, item_id, allowed_statuses={"ready"}, require_ready_snapshot=True, payload=payload)
            evidence = self._create_evidence(
                release_id,
                submission_id,
                item_id,
                payload,
                evidence_type="submission_receipt",
                platform_status="submitted",
            )
            batch = self.submission_store.record_submission(release_id, submission_id, item_id, payload)
            self.refresh_report(release_id, submission_id)
            return batch, evidence

    def record_feedback(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> tuple[SubmissionBatch, DomainDocument]:
        with self.lock:
            self._preflight_external_update(release_id, submission_id, item_id, allowed_statuses={"submitted", "feedback_received", "needs_changes"}, require_ready_snapshot=False, payload=payload)
            status = str(payload.get("feedback_status") or payload.get("status") or "needs_changes")
            if status not in {"feedback_received", "needs_changes", "accepted", "rejected"}:
                status = "feedback_received"
            evidence_type = "platform_feedback"
            if status == "needs_changes":
                evidence_type = "needs_changes_notice"
            elif status == "rejected":
                evidence_type = "rejection_notice"
            elif status == "accepted":
                evidence_type = "acceptance_confirmation"
            evidence = self._create_evidence(
                release_id,
                submission_id,
                item_id,
                {**payload, "status": status},
                evidence_type=evidence_type,
                platform_status=status,
            )
            if status == "accepted":
                batch = self.submission_store.mark_accepted(release_id, submission_id, item_id, payload)
            else:
                batch = self.submission_store.record_feedback(release_id, submission_id, item_id, {**payload, "status": status})
            self.refresh_report(release_id, submission_id)
            return batch, evidence

    def mark_accepted(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument | None = None) -> tuple[SubmissionBatch, DomainDocument]:
        payload = payload or {}
        with self.lock:
            self._preflight_external_update(release_id, submission_id, item_id, allowed_statuses={"submitted", "feedback_received", "needs_changes"}, require_ready_snapshot=False, payload=payload)
            self._ensure_acceptance_allowed(release_id, submission_id, item_id)
            evidence = self._create_evidence(
                release_id,
                submission_id,
                item_id,
                payload,
                evidence_type="acceptance_confirmation",
                platform_status="accepted",
            )
            batch = self.submission_store.mark_accepted(release_id, submission_id, item_id, payload)
            self.refresh_report(release_id, submission_id)
            return batch, evidence

    def create_resubmission_round(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            _reject_blocked_payload(payload)
            self._ensure_mutable_evidence(release_id, submission_id)
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            item = _find_item(batch, item_id)
            if item.status not in {"needs_changes", "rejected"}:
                raise SubmissionEvidenceStateError("Resubmission rounds require an item in needs_changes or rejected status.")
            based_on = str(payload.get("based_on_evidence_id") or "").strip()
            index = self.read_index(release_id, submission_id)
            if based_on:
                record = _find_evidence(index, based_on)
                if record.get("item_id") != item.item_id or record.get("evidence_type") not in {"needs_changes_notice", "rejection_notice", "platform_feedback"}:
                    raise SubmissionEvidenceStateError("based_on_evidence_id must reference current feedback evidence for this item.")
                if self._evidence_stale_reasons(record):
                    raise SubmissionEvidenceStateError("Cannot create a resubmission round from stale feedback evidence.")
            round_record = self._new_round(index, batch, item, round_type="resubmission", status="resubmitted", payload=payload)
            self.write_index(release_id, submission_id, index)
            self.append_event(release_id, submission_id, "submission_evidence_resubmission_round_created", {"item_id": item.item_id, "round_id": round_record.get("round_id")})
            return round_record

    def refresh_report(self, release_id: str, submission_id: str) -> DomainDocument:
        with self.lock:
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            index = self.read_index(release_id, submission_id)
            records = _index_records(index)
            attachments = _index_attachments(index)
            rounds = _index_rounds(index)
            checks: list[DomainDocument] = []
            item_checks: list[DomainDocument] = []
            stale_count = 0
            attachment_count = len(attachments)
            evidence_count = len(records)
            for attachment in attachments:
                failures = self._attachment_failure_reasons(attachment)
                item_checks.append(_check("attachment", attachment.get("item_id"), "submission_evidence_attachment_integrity", "failed" if failures else "passed", "blocking", "; ".join(failures) if failures else "Attachment integrity is current.", attachment_id=attachment.get("attachment_id")))
            for record in records:
                stale_reasons = self._evidence_stale_reasons(record)
                integrity_ok = submission_evidence_record_integrity_ok(record)
                if stale_reasons:
                    stale_count += 1
                status = "failed" if stale_reasons or not integrity_ok else "passed"
                message = "; ".join(stale_reasons) if stale_reasons else "Evidence source and integrity are current."
                if not integrity_ok:
                    message = "Evidence integrity hash does not match."
                item_checks.append(_check("evidence", record.get("item_id"), "submission_evidence_record_current", status, "blocking", message, evidence_id=record.get("evidence_id")))
            item_summaries = self.item_summaries(release_id, submission_id, index=index, batch=batch)
            for summary in item_summaries:
                item_id = str(summary.get("item_id") or "")
                status = str(summary.get("status") or "")
                evidence_types = set(_as_list(summary.get("evidence_types")))
                missing_type = None
                if status == "submitted" and not evidence_types.intersection({"submission_receipt", "resubmission_receipt"}):
                    missing_type = "submission_receipt"
                elif status == "feedback_received" and "platform_feedback" not in evidence_types:
                    missing_type = "platform_feedback"
                elif status == "needs_changes" and "needs_changes_notice" not in evidence_types:
                    missing_type = "needs_changes_notice"
                elif status == "accepted" and "acceptance_confirmation" not in evidence_types:
                    missing_type = "acceptance_confirmation"
                elif status == "rejected" and "rejection_notice" not in evidence_types:
                    missing_type = "rejection_notice"
                elif status == "withdrawn" and "withdrawal_confirmation" not in evidence_types:
                    missing_type = "withdrawal_confirmation"
                item_checks.append(_check("item", item_id, "submission_evidence_status_reconciliation", "failed" if missing_type else "passed", "blocking", f"Item status {status} requires {missing_type} evidence." if missing_type else "Item status has matching evidence."))
                if status == "accepted":
                    latest_blocking = _latest_blocking_after_acceptance(summary)
                    item_checks.append(_check("item", item_id, "submission_evidence_acceptance_not_superseded", "failed" if latest_blocking else "passed", "blocking", f"Accepted item has newer unresolved evidence: {latest_blocking}." if latest_blocking else "Accepted evidence is not superseded."))
            checks.append(_check("submission", None, "submission_evidence_package_signed", "passed", "blocking", "Submission package is signed."))
            checks.append(_check("submission", None, "submission_evidence_submission_package_exists", "passed" if self.submission_store.package_zip_path(release_id, submission_id).exists() else "failed", "blocking", "Submission package ZIP exists."))
            blockers = [check for check in [*checks, *item_checks] if check.get("status") == "failed" and check.get("severity") == "blocking"]
            warnings = [check for check in [*checks, *item_checks] if check.get("status") == "warning"]
            report = {
                "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
                "report_id": "ser-000001",
                "release_id": release_id,
                "submission_id": submission_id,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "generated_at": now_iso(),
                "source_hash": stable_hash(self._report_source(batch, index)),
                "summary": {
                    "item_count": len([item for item in batch.items if item.status != "withdrawn"]),
                    "submitted_count": sum(1 for item in batch.items if item.status in SUBMITTED_OR_LATER),
                    "accepted_count": sum(1 for item in batch.items if item.status == "accepted"),
                    "needs_changes_count": sum(1 for item in batch.items if item.status == "needs_changes"),
                    "rejected_count": sum(1 for item in batch.items if item.status == "rejected"),
                    "stale_evidence_count": stale_count,
                    "attachment_count": attachment_count,
                    "round_count": len(rounds),
                    "evidence_count": evidence_count,
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
                "checks": checks,
                "item_checks": item_checks,
                "item_summaries": item_summaries,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = submission_evidence_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
            write_json(self.report_path(release_id, submission_id), report)
            index["latest_report_summary"] = submission_evidence_report_summary(report)
            index["updated_at"] = now_iso()
            self.write_index(release_id, submission_id, index)
            return report

    def export_evidence(self, release_id: str, submission_id: str, *, now: str | None = None, allow_signed: bool = False) -> DomainDocument:
        now = now or now_iso()
        with self.lock:
            if not allow_signed:
                self._ensure_mutable_evidence(release_id, submission_id)
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            report = self.refresh_report(release_id, submission_id)
            export_dir = self.export_dir(release_id, submission_id).resolve()
            root = self.evidence_dir(release_id, submission_id).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []
            submission_zip = self.submission_store.package_zip_path(release_id, submission_id).resolve()
            if not submission_zip.exists() or not submission_zip.is_file() or submission_zip.is_symlink():
                raise SubmissionEvidenceStateError("Submission package ZIP is missing.")
            shutil.copy2(submission_zip, export_dir / "submission-package.zip")
            files.append(_file_record(export_dir, export_dir / "submission-package.zip"))
            _write_json(export_dir / "submission-evidence-report.json", report)
            files.append(_file_record(export_dir, export_dir / "submission-evidence-report.json"))
            index = self.read_index(release_id, submission_id)
            self._write_export_items(export_dir, index, files)
            self._write_readme(export_dir, batch, report)
            files.append(_file_record(export_dir, export_dir / "README.txt"))
            signoff_public = _submission_evidence_signoff_export_summary(self.read_signoff(release_id, submission_id, default={}))
            _write_json(export_dir / "submission-evidence-signoff.json", signoff_public)
            manifest = {
                "schema_version": SUBMISSION_EVIDENCE_EXPORT_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Submission Evidence Export", "version": __version__},
                "release_id": release_id,
                "submission_id": submission_id,
                "generated_at": now,
                "source_hash": report.get("source_hash"),
                "submission_package": {
                    "path": "submission-package.zip",
                    "sha256": _sha256_file(submission_zip),
                    "size_bytes": submission_zip.stat().st_size,
                },
                "report": {
                    "path": "submission-evidence-report.json",
                    "report_hash": submission_evidence_report_integrity_hash(report),
                    "status": report.get("status"),
                },
                "sidecars": {
                    "submission_evidence_signoff": _submission_evidence_signoff_sidecar_record(signoff_public),
                },
                "summary": submission_evidence_report_summary(report),
                "items": self.item_summaries(release_id, submission_id, index=index, batch=batch),
                "files": sorted(files, key=lambda row: row["path"]),
                "redaction_summary": {"status": "passed"},
            }
            _write_json(export_dir / "submission-evidence-manifest.json", manifest)
            return self.read_export_manifest(release_id, submission_id)

    def build_zip(self, release_id: str, submission_id: str, *, now: str | None = None, allow_signed: bool = False) -> DomainDocument:
        now = now or now_iso()
        with self.lock:
            if not allow_signed:
                self._ensure_mutable_evidence(release_id, submission_id)
            self.refresh_export_signoff_summary(release_id, submission_id)
            export_dir = self.export_dir(release_id, submission_id).resolve()
            if not export_dir.exists():
                raise SubmissionEvidenceStateError("Submission evidence export has not been generated.")
            zip_path = self.package_zip_path(release_id, submission_id).resolve()
            _ensure_within(self.evidence_dir(release_id, submission_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest = self.read_export_manifest(release_id, submission_id)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            _write_json(export_dir / "submission-evidence-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256_file(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            self.append_event(release_id, submission_id, "submission_evidence_zip_created", {"sha256": info["sha256"]})
            return sanitize_metadata(info, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def signoff_evidence(self, release_id: str, submission_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        payload = payload or {}
        with self.lock:
            self._ensure_mutable_evidence(release_id, submission_id)
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            report = self.refresh_report(release_id, submission_id)
            require_submitted = bool(payload.get("require_submitted", False))
            require_accepted = bool(payload.get("require_accepted", False))
            self._ensure_report_allows_signoff(report, require_submitted=require_submitted, require_accepted=require_accepted)
            self.export_evidence(release_id, submission_id, now=now, allow_signed=True)
            submission_zip = self.submission_store.package_zip_path(release_id, submission_id)
            pending = {
                "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
                "release_id": release_id,
                "submission_id": submission_id,
                "status": "signed",
                "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
                "signed_at": now,
                "forced": bool(payload.get("force", False)),
                "force_reason": _safe_text(payload.get("override_reason"), 500) if payload.get("force") else None,
                "require_accepted": require_accepted,
                "require_submitted": require_submitted,
                "submission_package_sha256": _sha256_file(submission_zip),
                "report_hash": submission_evidence_report_integrity_hash(report),
                "export_manifest_hash": None,
                "notes": _safe_text(payload.get("notes"), 2000),
            }
            pending["payload_hash"] = submission_evidence_signoff_payload_hash(pending)
            _write_json(self.signoff_path(release_id, submission_id), pending)
            manifest = self.refresh_export_signoff_summary(release_id, submission_id)
            final_hash = stable_hash({key: value for key, value in manifest.items() if key != "zip"})
            signoff = {**pending, "export_manifest_hash": final_hash}
            signoff["payload_hash"] = submission_evidence_signoff_payload_hash(signoff)
            _write_json(self.signoff_path(release_id, submission_id), signoff)
            self.refresh_export_signoff_summary(release_id, submission_id)
            self.build_zip(release_id, submission_id, now=now, allow_signed=True)
            index = self.read_index(release_id, submission_id)
            index["latest_signoff_summary"] = submission_evidence_signoff_summary(signoff)
            index["updated_at"] = now_iso()
            self.write_index(release_id, submission_id, index)
            self.append_event(release_id, submission_id, "submission_evidence_signed", {"require_accepted": require_accepted, "require_submitted": require_submitted})
            return signoff
