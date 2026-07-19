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

SubmissionEvidenceStateError = _make_deferred_global('SubmissionEvidenceStateError')
_index_records = _make_deferred_global('_index_records')
_sha256_file = _make_deferred_global('_sha256_file')
item = _make_deferred_global('item')
row = _make_deferred_global('row')
submission_evidence_attachment_integrity_ok = _make_deferred_global('submission_evidence_attachment_integrity_ok')
submission_evidence_report_integrity_ok = _make_deferred_global('submission_evidence_report_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global SubmissionEvidenceStateError, _index_records, _sha256_file, item, row, submission_evidence_attachment_integrity_ok, submission_evidence_report_integrity_ok
    SubmissionEvidenceStateError = namespace.get('SubmissionEvidenceStateError', SubmissionEvidenceStateError)
    _index_records = namespace.get('_index_records', _index_records)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    item = namespace.get('item', item)
    row = namespace.get('row', row)
    submission_evidence_attachment_integrity_ok = namespace.get('submission_evidence_attachment_integrity_ok', submission_evidence_attachment_integrity_ok)
    submission_evidence_report_integrity_ok = namespace.get('submission_evidence_report_integrity_ok', submission_evidence_report_integrity_ok)
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




class SubmissionEvidenceStoreLifecycleMixin:
    def _attachment_failure_reasons(self, attachment: DomainDocument) -> list[str]:
        reasons: list[str] = []
        if not submission_evidence_attachment_integrity_ok(attachment):
            reasons.append("attachment metadata integrity mismatch")
        redaction = _as_document(attachment.get("redaction_summary"))
        if redaction.get("status") == "failed":
            reasons.append("attachment redaction scan failed")
        path = self.evidence_dir(str(attachment.get("release_id")), str(attachment.get("submission_id"))) / "items" / str(attachment.get("item_id")) / "attachments" / str(attachment.get("stored_filename") or "")
        if not path.exists() or not path.is_file() or path.is_symlink():
            reasons.append("attachment bytes missing")
            return reasons
        if path.stat().st_size != int(attachment.get("size_bytes") or -1):
            reasons.append("attachment size mismatch")
        if _sha256_file(path) != str(attachment.get("sha256") or ""):
            reasons.append("attachment sha256 mismatch")
        return reasons

    def _ensure_acceptance_allowed(self, release_id: str, submission_id: str, item_id: str) -> None:
        index = self.read_index(release_id, submission_id)
        records = [row for row in _index_records(index) if row.get("item_id") == item_id and not self._evidence_stale_reasons(row)]
        if not any(row.get("evidence_type") in {"submission_receipt", "resubmission_receipt"} for row in records):
            raise SubmissionEvidenceStateError("Acceptance requires a current submission receipt evidence record.")
        blocking = [row for row in records if row.get("evidence_type") in {"needs_changes_notice", "rejection_notice"}]
        accepted_time = max([str(row.get("recorded_at") or "") for row in records if row.get("evidence_type") == "acceptance_confirmation"], default="")
        if accepted_time and any(str(row.get("recorded_at") or "") > accepted_time for row in blocking):
            raise SubmissionEvidenceStateError("Acceptance evidence is superseded by newer unresolved feedback.")

    def _ensure_report_allows_signoff(self, report: DomainDocument, *, require_submitted: bool, require_accepted: bool) -> None:
        if not submission_evidence_report_integrity_ok(report):
            raise SubmissionEvidenceStateError("Submission evidence report integrity failed.")
        if report.get("status") == "failed":
            raise SubmissionEvidenceStateError("Submission evidence report failed.")
        summaries = _as_list(report.get("item_summaries"))
        if require_submitted:
            missing = [str(item.get("item_id") or "") for item in summaries if item.get("status") not in SUBMITTED_OR_LATER]
            if missing:
                raise SubmissionEvidenceStateError("Submission evidence signoff requires every item to be submitted.")
        if require_accepted:
            missing = [str(item.get("item_id") or "") for item in summaries if item.get("status") != "accepted"]
            if missing:
                raise SubmissionEvidenceStateError("Submission evidence signoff requires every item to be accepted.")
