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

SubmissionEvidenceNotFoundError = _make_deferred_global('SubmissionEvidenceNotFoundError')
SubmissionEvidenceStateError = _make_deferred_global('SubmissionEvidenceStateError')
SubmissionEvidenceValidationError = _make_deferred_global('SubmissionEvidenceValidationError')
_attachment_hashes = _make_deferred_global('_attachment_hashes')
_default_evidence_title = _make_deferred_global('_default_evidence_title')
_file_record = _make_deferred_global('_file_record')
_find_item = _make_deferred_global('_find_item')
_index_attachments = _make_deferred_global('_index_attachments')
_index_records = _make_deferred_global('_index_records')
_index_rounds = _make_deferred_global('_index_rounds')
_item_source_payload = _make_deferred_global('_item_source_payload')
_reject_blocked_payload = _make_deferred_global('_reject_blocked_payload')
_safe_text = _make_deferred_global('_safe_text')
_safe_url = _make_deferred_global('_safe_url')
_sha256_file = _make_deferred_global('_sha256_file')
_submission_evidence_signoff_export_summary = _make_deferred_global('_submission_evidence_signoff_export_summary')
_submission_evidence_signoff_sidecar_record = _make_deferred_global('_submission_evidence_signoff_sidecar_record')
_validate_evidence_type = _make_deferred_global('_validate_evidence_type')
_validate_platform_status = _make_deferred_global('_validate_platform_status')
_validate_relative_path = _make_deferred_global('_validate_relative_path')
_validated_attachment_ids = _make_deferred_global('_validated_attachment_ids')
_write_json = _make_deferred_global('_write_json')
key = _make_deferred_global('key')
submission_evidence_record_integrity_hash = _make_deferred_global('submission_evidence_record_integrity_hash')
submission_evidence_record_integrity_ok = _make_deferred_global('submission_evidence_record_integrity_ok')
submission_evidence_signoff_summary = _make_deferred_global('submission_evidence_signoff_summary')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global SubmissionEvidenceNotFoundError, SubmissionEvidenceStateError, SubmissionEvidenceValidationError, _attachment_hashes, _default_evidence_title, _file_record, _find_item, _index_attachments
    global _index_records, _index_rounds, _item_source_payload, _reject_blocked_payload, _safe_text, _safe_url, _sha256_file
    global _submission_evidence_signoff_export_summary, _submission_evidence_signoff_sidecar_record, _validate_evidence_type, _validate_platform_status, _validate_relative_path, _validated_attachment_ids, _write_json, key
    global submission_evidence_record_integrity_hash, submission_evidence_record_integrity_ok, submission_evidence_signoff_summary, value
    SubmissionEvidenceNotFoundError = namespace.get('SubmissionEvidenceNotFoundError', SubmissionEvidenceNotFoundError)
    SubmissionEvidenceStateError = namespace.get('SubmissionEvidenceStateError', SubmissionEvidenceStateError)
    SubmissionEvidenceValidationError = namespace.get('SubmissionEvidenceValidationError', SubmissionEvidenceValidationError)
    _attachment_hashes = namespace.get('_attachment_hashes', _attachment_hashes)
    _default_evidence_title = namespace.get('_default_evidence_title', _default_evidence_title)
    _file_record = namespace.get('_file_record', _file_record)
    _find_item = namespace.get('_find_item', _find_item)
    _index_attachments = namespace.get('_index_attachments', _index_attachments)
    _index_records = namespace.get('_index_records', _index_records)
    _index_rounds = namespace.get('_index_rounds', _index_rounds)
    _item_source_payload = namespace.get('_item_source_payload', _item_source_payload)
    _reject_blocked_payload = namespace.get('_reject_blocked_payload', _reject_blocked_payload)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _safe_url = namespace.get('_safe_url', _safe_url)
    _sha256_file = namespace.get('_sha256_file', _sha256_file)
    _submission_evidence_signoff_export_summary = namespace.get('_submission_evidence_signoff_export_summary', _submission_evidence_signoff_export_summary)
    _submission_evidence_signoff_sidecar_record = namespace.get('_submission_evidence_signoff_sidecar_record', _submission_evidence_signoff_sidecar_record)
    _validate_evidence_type = namespace.get('_validate_evidence_type', _validate_evidence_type)
    _validate_platform_status = namespace.get('_validate_platform_status', _validate_platform_status)
    _validate_relative_path = namespace.get('_validate_relative_path', _validate_relative_path)
    _validated_attachment_ids = namespace.get('_validated_attachment_ids', _validated_attachment_ids)
    _write_json = namespace.get('_write_json', _write_json)
    key = namespace.get('key', key)
    submission_evidence_record_integrity_hash = namespace.get('submission_evidence_record_integrity_hash', submission_evidence_record_integrity_hash)
    submission_evidence_record_integrity_ok = namespace.get('submission_evidence_record_integrity_ok', submission_evidence_record_integrity_ok)
    submission_evidence_signoff_summary = namespace.get('submission_evidence_signoff_summary', submission_evidence_signoff_summary)
    value = namespace.get('value', value)
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




class SubmissionEvidenceStoreEvidenceMixin:
    def reset_signoff(self, release_id: str, submission_id: str, reason: str) -> DomainDocument:
        reason = sanitize_sensitive_text(str(reason or "").strip())
        if not reason:
            raise SubmissionEvidenceValidationError("reason is required.")
        with self.lock:
            existing = self.read_signoff(release_id, submission_id, default={})
            event = {"timestamp": now_iso(), "event": "submission_evidence_signoff_reset", "reason": reason[:500], "previous_summary": submission_evidence_signoff_summary(existing)}
            if existing:
                path = self.signoff_history_path(release_id, submission_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(sanitize_metadata(event, blocked_keys=DISTRIBUTION_BLOCKED_KEYS), ensure_ascii=False) + "\n")
            signoff_path = self.signoff_path(release_id, submission_id)
            if signoff_path.exists():
                signoff_path.unlink()
            sidecar = self.export_dir(release_id, submission_id) / "submission-evidence-signoff.json"
            if sidecar.exists():
                sidecar.unlink()
            index = self.read_index(release_id, submission_id)
            index["latest_signoff_summary"] = {"status": "not_signed"}
            index["updated_at"] = now_iso()
            self.write_index(release_id, submission_id, index)
            self.append_event(release_id, submission_id, "submission_evidence_signoff_reset", {"reason": reason[:500]})
            return sanitize_metadata(event, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def read_export_manifest(self, release_id: str, submission_id: str) -> DomainDocument:
        path = self.export_dir(release_id, submission_id) / "submission-evidence-manifest.json"
        if not path.exists():
            raise SubmissionEvidenceNotFoundError("Submission evidence export has not been generated.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def refresh_export_signoff_summary(self, release_id: str, submission_id: str) -> DomainDocument:
        export_dir = self.export_dir(release_id, submission_id)
        manifest_path = export_dir / "submission-evidence-manifest.json"
        if not manifest_path.exists():
            raise SubmissionEvidenceNotFoundError("Submission evidence export has not been generated.")
        signoff_public = _submission_evidence_signoff_export_summary(self.read_signoff(release_id, submission_id, default={}))
        _write_json(export_dir / "submission-evidence-signoff.json", signoff_public)
        manifest = self.read_export_manifest(release_id, submission_id)
        manifest["sidecars"] = {"submission_evidence_signoff": _submission_evidence_signoff_sidecar_record(signoff_public)}
        manifest["files"] = sorted([row for row in manifest.get("files", []) if isinstance(row, dict) and row.get("path") != "submission-evidence-signoff.json"], key=lambda row: row["path"])
        _write_json(manifest_path, manifest)
        return self.read_export_manifest(release_id, submission_id)

    def append_event(self, release_id: str, submission_id: str, event_type: str, payload: DomainDocument) -> None:
        path = self.events_path(release_id, submission_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def index_summary(self, index: DomainDocument, *, batch: SubmissionBatch | None = None) -> DomainDocument:
        records = _index_records(index)
        attachments = _index_attachments(index)
        rounds = _index_rounds(index)
        return sanitize_metadata(
            {
                "status": index.get("latest_report_summary", {}).get("status") if isinstance(index.get("latest_report_summary"), dict) else "not_started",
                "signoff_status": index.get("latest_signoff_summary", {}).get("status") if isinstance(index.get("latest_signoff_summary"), dict) else "not_signed",
                "evidence_count": len(records),
                "attachment_count": len(attachments),
                "round_count": len(rounds),
                "submitted_count": sum(1 for item in (batch.items if batch else []) if item.status in SUBMITTED_OR_LATER),
                "accepted_count": sum(1 for item in (batch.items if batch else []) if item.status == "accepted"),
                "stale_count": sum(1 for record in records if self._evidence_stale_reasons(record)),
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    def item_summaries(self, release_id: str, submission_id: str, *, index: DomainDocument | None = None, batch: SubmissionBatch | None = None) -> list[DomainDocument]:
        index = index or self.read_index(release_id, submission_id)
        batch = batch or self.submission_store.get_submission(release_id, submission_id)
        records = _index_records(index)
        rounds = _index_rounds(index)
        result: list[DomainDocument] = []
        for item in batch.items:
            item_records = [record for record in records if record.get("item_id") == item.item_id and record.get("status") != "archived"]
            item_rounds = [row for row in rounds if row.get("item_id") == item.item_id]
            latest = sorted(item_records, key=lambda row: str(row.get("recorded_at") or ""))[-1] if item_records else {}
            result.append(
                sanitize_metadata(
                    {
                        "item_id": item.item_id,
                        "target_id": item.target_id,
                        "target_name": item.target_name,
                        "profile_id": item.profile_id,
                        "status": item.status,
                        "external_reference": item.external_reference,
                        "evidence_count": len(item_records),
                        "round_count": len(item_rounds),
                        "attachment_count": len([row for row in _index_attachments(index) if row.get("item_id") == item.item_id]),
                        "evidence_types": sorted({str(record.get("evidence_type") or "") for record in item_records if record.get("evidence_type")}),
                        "latest_evidence_id": latest.get("evidence_id"),
                        "latest_platform_status": latest.get("platform_status"),
                        "timeline": [
                            {
                                "evidence_id": record.get("evidence_id"),
                                "evidence_type": record.get("evidence_type"),
                                "platform_status": record.get("platform_status"),
                                "recorded_at": record.get("recorded_at"),
                            }
                            for record in sorted(item_records, key=lambda row: str(row.get("recorded_at") or ""))
                        ],
                    },
                    blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
                )
            )
        return result

    def _empty_index(self, release_id: str, submission_id: str) -> DomainDocument:
        now = now_iso()
        return {
            "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
            "release_id": release_id,
            "submission_id": submission_id,
            "created_at": now,
            "updated_at": now,
            "evidence_records": [],
            "attachments": [],
            "rounds": [],
            "latest_report_summary": {"status": "not_started"},
            "latest_signoff_summary": {"status": "not_signed"},
        }

    def _preflight_external_update(self, release_id: str, submission_id: str, item_id: str, *, allowed_statuses: set[str], require_ready_snapshot: bool, payload: DomainDocument) -> None:
        _reject_blocked_payload(payload)
        self._ensure_mutable_evidence(release_id, submission_id)
        batch = self.submission_store.get_submission(release_id, submission_id)
        signoff = self.submission_store.read_signoff(batch.release_id, batch.submission_id, default={})
        if batch.latest_signoff_summary.get("status") not in SIGNED_SUBMISSION_STATUSES and signoff.get("status") not in SIGNED_SUBMISSION_STATUSES:
            raise SubmissionEvidenceStateError("Submission package must be signed before recording evidence.")
        item = _find_item(batch, item_id)
        self.submission_store._ensure_external_item_transition(batch, item, allowed_statuses=allowed_statuses, require_ready_snapshot=require_ready_snapshot)  # noqa: SLF001
        self._ensure_signed_submission(batch)

    def _ensure_signed_submission(self, batch: SubmissionBatch) -> None:
        signoff = self.submission_store.read_signoff(batch.release_id, batch.submission_id, default={})
        if batch.latest_signoff_summary.get("status") not in SIGNED_SUBMISSION_STATUSES and signoff.get("status") not in SIGNED_SUBMISSION_STATUSES:
            raise SubmissionEvidenceStateError("Submission package must be signed before recording evidence.")
        zip_path = self.submission_store.package_zip_path(batch.release_id, batch.submission_id)
        if not zip_path.exists() or not zip_path.is_file() or zip_path.is_symlink():
            raise SubmissionEvidenceStateError("Submission package ZIP is missing.")

    def _ensure_mutable_evidence(self, release_id: str, submission_id: str) -> None:
        signoff = self.read_signoff(release_id, submission_id, default={})
        if signoff.get("status") in {"signed", "force_signed"}:
            raise SubmissionEvidenceStateError("Submission evidence archive is signed. Reset evidence signoff before changing evidence.")

    def _create_evidence(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument, *, evidence_type: str, platform_status: str) -> DomainDocument:
        _reject_blocked_payload(payload)
        evidence_type = _validate_evidence_type(evidence_type)
        platform_status = _validate_platform_status(platform_status)
        batch = self.submission_store.get_submission(release_id, submission_id)
        item = _find_item(batch, item_id)
        index = self.read_index(release_id, submission_id)
        attachment_ids = self._create_inline_attachments(release_id, submission_id, item.item_id, payload, index)
        attachment_ids.extend(_validated_attachment_ids(index, item.item_id, payload.get("attachment_ids")))
        round_record = self._round_for_evidence(index, batch, item, evidence_type=evidence_type, platform_status=platform_status, payload=payload)
        source_snapshot = self.source_snapshot(batch, item)
        evidence_id = self._next_evidence_id(index)
        content = {
            "external_reference": _safe_text(payload.get("external_reference"), 200),
            "platform_name": _safe_text(payload.get("platform_name"), 120) or _safe_text(payload.get("platform"), 120) or "Generic Platform",
            "recorded_by": _safe_text(payload.get("recorded_by"), 120) or "local-user",
            "occurred_at": _safe_text(payload.get("occurred_at"), 80),
            "title": _safe_text(payload.get("title"), 160) or _default_evidence_title(evidence_type),
            "message": _safe_text(payload.get("message") or payload.get("notes"), 2000),
            "safe_url": _safe_url(payload.get("safe_url") or payload.get("url")),
            "category": _safe_text(payload.get("category"), 80),
            "severity": _safe_text(payload.get("severity"), 40),
            "changed_summary": _safe_text(payload.get("changed_summary"), 1000),
        }
        record = {
            "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
            "evidence_id": evidence_id,
            "release_id": release_id,
            "submission_id": submission_id,
            "item_id": item.item_id,
            "target_id": item.target_id,
            "round_id": round_record.get("round_id"),
            "evidence_type": evidence_type,
            "status": "current",
            "platform_status": platform_status,
            "external_reference": content["external_reference"],
            "platform_name": content["platform_name"],
            "recorded_by": content["recorded_by"],
            "recorded_at": str(payload.get("recorded_at") or now_iso()),
            "occurred_at": content["occurred_at"] or str(payload.get("recorded_at") or now_iso()),
            "title": content["title"],
            "message": content["message"],
            "safe_url": content["safe_url"],
            "category": content["category"],
            "severity": content["severity"],
            "changed_summary": content["changed_summary"],
            "attachment_ids": sorted(set(attachment_ids)),
            "source_snapshot": source_snapshot,
            "content_hash": stable_hash(content),
            "source_hash": stable_hash(
                {
                    "evidence_type": evidence_type,
                    "release_id": release_id,
                    "submission_id": submission_id,
                    "item_id": item.item_id,
                    "round_id": round_record.get("round_id"),
                    "source_snapshot": source_snapshot,
                    "content": content,
                    "attachments": _attachment_hashes(index, attachment_ids),
                }
            ),
            "stale": False,
            "warnings": [],
        }
        record["integrity_hash"] = submission_evidence_record_integrity_hash(record)
        records = _index_records(index)
        records.append(record)
        index["evidence_records"] = sorted(records, key=lambda row: str(row.get("evidence_id") or ""))
        for round_row in _index_rounds(index):
            if round_row.get("round_id") == round_record.get("round_id"):
                ids = [str(value) for value in round_row.get("evidence_ids", []) if str(value).strip()]
                if evidence_id not in ids:
                    ids.append(evidence_id)
                round_row["evidence_ids"] = ids
                round_row["status"] = platform_status
                if evidence_type in {"acceptance_confirmation", "rejection_notice", "needs_changes_notice", "withdrawal_confirmation"}:
                    round_row["closing_evidence_id"] = evidence_id
                    round_row["closed_at"] = now_iso()
                round_row["integrity_hash"] = stable_hash({key: value for key, value in round_row.items() if key != "integrity_hash"})
        index["updated_at"] = now_iso()
        self.write_index(release_id, submission_id, index)
        self._write_record_file(release_id, submission_id, record)
        self._write_round_files(release_id, submission_id, index)
        self.append_event(release_id, submission_id, "submission_evidence_recorded", {"item_id": item.item_id, "evidence_id": evidence_id, "evidence_type": evidence_type})
        return record

    def _create_inline_attachments(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument, index: DomainDocument) -> list[str]:
        raw = payload.get("attachments")
        if not isinstance(raw, list):
            return []
        ids: list[str] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            uploaded = self.upload_attachment(release_id, submission_id, item_id, item)
            ids.append(str(uploaded.get("attachment_id") or ""))
            latest = self.read_index(release_id, submission_id)
            index["attachments"] = latest.get("attachments", [])
        return [value for value in ids if value]

    def _round_for_evidence(self, index: DomainDocument, batch: SubmissionBatch, item: SubmissionItem, *, evidence_type: str, platform_status: str, payload: DomainDocument) -> DomainDocument:
        rounds = _index_rounds(index)
        item_rounds = [row for row in rounds if row.get("item_id") == item.item_id]
        if evidence_type == "resubmission_receipt":
            return self._new_round(index, batch, item, round_type="resubmission", status=platform_status, payload=payload)
        if evidence_type == "submission_receipt" and not item_rounds:
            return self._new_round(index, batch, item, round_type="initial_submission", status=platform_status, payload=payload)
        if item_rounds:
            return sorted(item_rounds, key=lambda row: int(row.get("round_number") or 0))[-1]
        return self._new_round(index, batch, item, round_type="initial_submission", status=platform_status, payload=payload)

    def _new_round(self, index: DomainDocument, batch: SubmissionBatch, item: SubmissionItem, *, round_type: str, status: str, payload: DomainDocument) -> DomainDocument:
        rounds = _index_rounds(index)
        item_rounds = [row for row in rounds if row.get("item_id") == item.item_id]
        round_number = len(item_rounds) + 1
        round_id = f"round-{round_number:06d}"
        if any(row.get("round_id") == round_id and row.get("item_id") == item.item_id for row in rounds):
            for index_number in range(round_number + 1, 1_000_000):
                candidate = f"round-{index_number:06d}"
                if not any(row.get("round_id") == candidate and row.get("item_id") == item.item_id for row in rounds):
                    round_id = candidate
                    round_number = index_number
                    break
        row = {
            "schema_version": SUBMISSION_EVIDENCE_SCHEMA_VERSION,
            "round_id": round_id,
            "release_id": batch.release_id,
            "submission_id": batch.submission_id,
            "item_id": item.item_id,
            "round_number": round_number,
            "round_type": round_type,
            "status": status,
            "started_at": now_iso(),
            "closed_at": None,
            "opening_evidence_id": None,
            "closing_evidence_id": None,
            "evidence_ids": [],
            "based_on_evidence_id": _safe_text(payload.get("based_on_evidence_id"), 80),
            "changed_summary": _safe_text(payload.get("changed_summary"), 1000),
            "source_hash": stable_hash({"item": _item_source_payload(item), "submission_signoff": self.submission_store.read_signoff(batch.release_id, batch.submission_id, default={})}),
        }
        row["integrity_hash"] = stable_hash({key: value for key, value in row.items() if key != "integrity_hash"})
        rounds.append(row)
        index["rounds"] = sorted(rounds, key=lambda value: (str(value.get("item_id") or ""), int(value.get("round_number") or 0)))
        return row

    def _write_record_file(self, release_id: str, submission_id: str, record: DomainDocument) -> None:
        path = self.evidence_dir(release_id, submission_id) / "items" / str(record.get("item_id")) / "evidence" / f"{record.get('evidence_id')}.json"
        write_json(path, sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _write_round_files(self, release_id: str, submission_id: str, index: DomainDocument) -> None:
        for row in _index_rounds(index):
            path = self.evidence_dir(release_id, submission_id) / "items" / str(row.get("item_id")) / "rounds" / f"{row.get('round_id')}.json"
            write_json(path, sanitize_metadata(row, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _write_export_items(self, export_dir: Path, index: DomainDocument, files: list[DomainDocument]) -> None:
        records = _index_records(index)
        rounds = _index_rounds(index)
        attachments = _index_attachments(index)
        item_ids = sorted({str(row.get("item_id") or "") for row in [*records, *rounds, *attachments] if str(row.get("item_id") or "")})
        for item_id in item_ids:
            item_dir = export_dir / "items" / _validate_relative_path(item_id)
            timeline = [record for record in sorted(records, key=lambda row: str(row.get("recorded_at") or "")) if record.get("item_id") == item_id]
            _write_json(item_dir / "timeline.json", {"schema_version": 1, "item_id": item_id, "events": timeline})
            files.append(_file_record(export_dir, item_dir / "timeline.json"))
            for row in rounds:
                if row.get("item_id") != item_id:
                    continue
                path = item_dir / "rounds" / f"{_validate_relative_path(str(row.get('round_id')))}.json"
                _write_json(path, row)
                files.append(_file_record(export_dir, path))
            for record in records:
                if record.get("item_id") != item_id:
                    continue
                path = item_dir / "evidence" / f"{_validate_relative_path(str(record.get('evidence_id')))}.json"
                _write_json(path, record)
                files.append(_file_record(export_dir, path))
            for attachment in attachments:
                if attachment.get("item_id") != item_id:
                    continue
                source_dir = self.evidence_dir(str(attachment.get("release_id")), str(attachment.get("submission_id"))) / "items" / item_id / "attachments"
                meta_source = source_dir / f"{attachment.get('attachment_id')}.json"
                bin_source = source_dir / str(attachment.get("stored_filename") or f"{attachment.get('attachment_id')}.bin")
                dest_dir = item_dir / "attachments"
                dest_dir.mkdir(parents=True, exist_ok=True)
                meta_dest = dest_dir / f"{_validate_relative_path(str(attachment.get('attachment_id')))}.json"
                bin_dest = dest_dir / f"{_validate_relative_path(str(attachment.get('attachment_id')))}.bin"
                if meta_source.exists():
                    shutil.copy2(meta_source, meta_dest)
                    files.append(_file_record(export_dir, meta_dest))
                if bin_source.exists():
                    shutil.copy2(bin_source, bin_dest)
                    files.append(_file_record(export_dir, bin_dest))

    def _write_readme(self, export_dir: Path, batch: SubmissionBatch, report: DomainDocument) -> None:
        lines = [
            f"MusicForge Submission Evidence Package: {sanitize_sensitive_text(batch.name)}",
            "",
            f"Submission ID: {batch.submission_id}",
            f"Release ID: {batch.release_id}",
            f"Evidence report: {report.get('status', 'missing')}",
            "",
            "This archive contains locally uploaded platform submission evidence.",
            "It does not contain platform credentials, upload tokens, or server local source paths.",
        ]
        (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _next_evidence_id(self, index: DomainDocument) -> str:
        used = {str(row.get("evidence_id") or "") for row in _index_records(index)}
        for number in range(1, 1_000_000):
            candidate = f"ev-{number:06d}"
            if candidate not in used:
                return candidate
        raise SubmissionEvidenceValidationError("Unable to allocate a unique evidence id.")

    def _next_attachment_id(self, index: DomainDocument) -> str:
        used = {str(row.get("attachment_id") or "") for row in _index_attachments(index)}
        for number in range(1, 1_000_000):
            candidate = f"att-{number:06d}"
            if candidate not in used:
                return candidate
        raise SubmissionEvidenceValidationError("Unable to allocate a unique attachment id.")

    def source_snapshot(self, batch: SubmissionBatch, item: SubmissionItem) -> DomainDocument:
        signoff = self.submission_store.read_signoff(batch.release_id, batch.submission_id, default={})
        submission_zip = self.submission_store.package_zip_path(batch.release_id, batch.submission_id)
        source = {
            "release_id": batch.release_id,
            "submission_id": batch.submission_id,
            "item_id": item.item_id,
            "target_id": item.target_id,
            "package_id": item.package_id,
            "submission_signoff_hash": stable_hash(signoff) if signoff else None,
            "submission_package_zip_sha256": _sha256_file(submission_zip) if submission_zip.exists() else None,
            "distribution_package_zip_sha256": item.package_zip_sha256,
            "distribution_signoff_hash": item.distribution_signoff_hash,
            "item_snapshot_hash": stable_hash(_item_source_payload(item)),
        }
        return sanitize_metadata(source, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def _report_source(self, batch: SubmissionBatch, index: DomainDocument) -> DomainDocument:
        signoff = self.submission_store.read_signoff(batch.release_id, batch.submission_id, default={})
        submission_zip = self.submission_store.package_zip_path(batch.release_id, batch.submission_id)
        return {
            "submission_signoff_hash": stable_hash(signoff) if signoff else None,
            "submission_package_zip_sha256": _sha256_file(submission_zip) if submission_zip.exists() else None,
            "items": [_item_source_payload(item) for item in batch.items],
            "evidence_records": _index_records(index),
            "rounds": _index_rounds(index),
            "attachments": _index_attachments(index),
        }

    def _evidence_stale_reasons(self, record: DomainDocument) -> list[str]:
        try:
            batch = self.submission_store.get_submission(str(record.get("release_id")), str(record.get("submission_id")))
            item = _find_item(batch, str(record.get("item_id")))
        except Exception:
            return ["source item is missing"]
        current = self.source_snapshot(batch, item)
        expected = _as_document(record.get("source_snapshot"))
        reasons = [key for key, value in expected.items() if current.get(key) != value]
        if reasons:
            return [f"source snapshot mismatch: {', '.join(sorted(reasons))}"]
        if not submission_evidence_record_integrity_ok(record):
            return ["evidence integrity mismatch"]
        return []
