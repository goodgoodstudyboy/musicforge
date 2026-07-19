# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.delivery.distribution import DistributionNotFoundError as DistributionNotFoundError, DistributionStore as DistributionStore, DistributionTarget as DistributionTarget, SIGNED_DISTRIBUTION_STATUSES as SIGNED_DISTRIBUTION_STATUSES, distribution_signoff_summary as distribution_signoff_summary, distribution_target_summary as distribution_target_summary
from song_agent.domains.delivery.distribution_export import read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

SubmissionBatch = _make_deferred_global('SubmissionBatch')
SubmissionItem = _make_deferred_global('SubmissionItem')
SubmissionNotFoundError = _make_deferred_global('SubmissionNotFoundError')
SubmissionStateError = _make_deferred_global('SubmissionStateError')
SubmissionValidationError = _make_deferred_global('SubmissionValidationError')
_batch_external_status = _make_deferred_global('_batch_external_status')
_file_sha256 = _make_deferred_global('_file_sha256')
_optional_text = _make_deferred_global('_optional_text')
_preserve_external_status = _make_deferred_global('_preserve_external_status')
_record_item_accepted = _make_deferred_global('_record_item_accepted')
_record_item_feedback = _make_deferred_global('_record_item_feedback')
_record_item_submitted = _make_deferred_global('_record_item_submitted')
_safe_dict = _make_deferred_global('_safe_dict')
_safe_distribution_manifest = _make_deferred_global('_safe_distribution_manifest')
_safe_text = _make_deferred_global('_safe_text')
_stale_summary = _make_deferred_global('_stale_summary')
_target_ids_from_payload = _make_deferred_global('_target_ids_from_payload')
_validate_item_id = _make_deferred_global('_validate_item_id')
_validate_submission_id = _make_deferred_global('_validate_submission_id')
_validate_target_id = _make_deferred_global('_validate_target_id')
key = _make_deferred_global('key')
row = _make_deferred_global('row')
submission_item_current_snapshot = _make_deferred_global('submission_item_current_snapshot')
submission_signoff_history_event = _make_deferred_global('submission_signoff_history_event')

def bind_globals(namespace: dict[str, object]) -> None:
    global SubmissionBatch, SubmissionItem, SubmissionNotFoundError, SubmissionStateError, SubmissionValidationError, _batch_external_status, _file_sha256
    global _optional_text, _preserve_external_status, _record_item_accepted, _record_item_feedback, _record_item_submitted, _safe_dict, _safe_distribution_manifest, _safe_text
    global _stale_summary, _target_ids_from_payload, _validate_item_id, _validate_submission_id, _validate_target_id, key, row, submission_item_current_snapshot
    global submission_signoff_history_event
    SubmissionBatch = namespace.get('SubmissionBatch', SubmissionBatch)
    SubmissionItem = namespace.get('SubmissionItem', SubmissionItem)
    SubmissionNotFoundError = namespace.get('SubmissionNotFoundError', SubmissionNotFoundError)
    SubmissionStateError = namespace.get('SubmissionStateError', SubmissionStateError)
    SubmissionValidationError = namespace.get('SubmissionValidationError', SubmissionValidationError)
    _batch_external_status = namespace.get('_batch_external_status', _batch_external_status)
    _file_sha256 = namespace.get('_file_sha256', _file_sha256)
    _optional_text = namespace.get('_optional_text', _optional_text)
    _preserve_external_status = namespace.get('_preserve_external_status', _preserve_external_status)
    _record_item_accepted = namespace.get('_record_item_accepted', _record_item_accepted)
    _record_item_feedback = namespace.get('_record_item_feedback', _record_item_feedback)
    _record_item_submitted = namespace.get('_record_item_submitted', _record_item_submitted)
    _safe_dict = namespace.get('_safe_dict', _safe_dict)
    _safe_distribution_manifest = namespace.get('_safe_distribution_manifest', _safe_distribution_manifest)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _stale_summary = namespace.get('_stale_summary', _stale_summary)
    _target_ids_from_payload = namespace.get('_target_ids_from_payload', _target_ids_from_payload)
    _validate_item_id = namespace.get('_validate_item_id', _validate_item_id)
    _validate_submission_id = namespace.get('_validate_submission_id', _validate_submission_id)
    _validate_target_id = namespace.get('_validate_target_id', _validate_target_id)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    submission_item_current_snapshot = namespace.get('submission_item_current_snapshot', submission_item_current_snapshot)
    submission_signoff_history_event = namespace.get('submission_signoff_history_event', submission_signoff_history_event)
    _bind_deferred_defaults(namespace)


SUBMISSION_ROOT_NAME = "submissions"
SUBMISSION_BATCH_SCHEMA_VERSION = 1
SUBMISSION_ITEM_SCHEMA_VERSION = 1
SUBMISSION_STATUSES = {
    "draft",
    "qa_failed",
    "qa_warning",
    "qa_passed",
    "exported",
    "signed",
    "submitted",
    "partially_accepted",
    "accepted",
    "needs_changes",
    "archived",
}
SUBMISSION_ITEM_STATUSES = {
    "pending",
    "ready",
    "submitted",
    "feedback_received",
    "needs_changes",
    "accepted",
    "rejected",
    "withdrawn",
}
SIGNED_SUBMISSION_STATUSES = {"signed", "force_signed"}




class SubmissionStore:
    def __init__(self, release_store: ReleaseStore, distribution_store: DistributionStore | None = None) -> None:
        self.release_store = release_store
        self.distribution_store = distribution_store or DistributionStore(release_store)
        self.lock = threading.RLock()

    def submissions_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / SUBMISSION_ROOT_NAME

    def submission_dir(self, release_id: str, submission_id: str) -> Path:
        return self.submissions_dir(release_id) / _validate_submission_id(submission_id)

    def submission_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission.json"

    def qa_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-qa.json"

    def export_dir(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-export"

    def package_zip_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-package.zip"

    def signoff_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-signoff.json"

    def signoff_history_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-signoff-history.jsonl"

    def events_path(self, release_id: str, submission_id: str) -> Path:
        return self.submission_dir(release_id, submission_id) / "submission-events.jsonl"

    def list_submissions(self, release_id: str) -> list[SubmissionBatch]:
        self.release_store.get_release(release_id)
        rows: list[SubmissionBatch] = []
        for path in sorted(self.submissions_dir(release_id).glob("sub-*/submission.json")):
            try:
                rows.append(SubmissionBatch.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return sorted(rows, key=lambda item: item.updated_at, reverse=True)

    def get_submission(self, release_id: str, submission_id: str) -> SubmissionBatch:
        self.release_store.get_release(release_id)
        path = self.submission_path(release_id, submission_id)
        if not path.exists():
            raise SubmissionNotFoundError(submission_id)
        return SubmissionBatch.from_dict(read_json(path))

    def create_submission(self, release_id: str, payload: DomainDocument) -> SubmissionBatch:
        with self.lock:
            release = self.release_store.get_release(release_id)
            if release.status == "archived":
                raise SubmissionStateError("Archived releases cannot create submission batches.")
            submission_id = self._reserve_submission_id(release_id)
            now = now_iso()
            batch = SubmissionBatch(
                schema_version=SUBMISSION_BATCH_SCHEMA_VERSION,
                submission_id=submission_id,
                release_id=release_id,
                name=_safe_text(payload.get("name"), 120) or f"Submission {submission_id}",
                status="draft",
                platform_group=_optional_text(payload.get("platform_group"), 80),
                notes=_optional_text(payload.get("notes"), 2000),
                created_at=now,
                updated_at=now,
            )
            for target_id in _target_ids_from_payload(payload):
                batch.items.append(self.snapshot_item(release_id, submission_id, target_id, now=now, item_id=self._next_item_id(batch)))
            self.save_submission(batch, touch=False)
            self.append_event(release_id, submission_id, "submission_created", {"target_count": len(batch.items)})
            return batch

    def save_submission(self, batch: SubmissionBatch, *, touch: bool = True) -> SubmissionBatch:
        if batch.status not in SUBMISSION_STATUSES:
            raise SubmissionValidationError(f"Unsupported submission status: {batch.status}.")
        if touch:
            batch.updated_at = now_iso()
        batch.items = sorted(batch.items, key=lambda item: item.item_id)
        write_json(self.submission_path(batch.release_id, batch.submission_id), batch.to_dict())
        return batch

    def update_submission(self, release_id: str, submission_id: str, patch: DomainDocument) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            if "name" in patch or "notes" in patch or "platform_group" in patch:
                self.ensure_mutable(batch)
            if "name" in patch:
                batch.name = _safe_text(patch.get("name"), 120) or batch.name
            if "notes" in patch:
                batch.notes = _optional_text(patch.get("notes"), 2000)
            if "platform_group" in patch:
                batch.platform_group = _optional_text(patch.get("platform_group"), 80)
            batch.latest_qa_summary = _stale_summary(batch.latest_qa_summary, "submission_updated")
            batch.latest_export_summary = _stale_summary(batch.latest_export_summary, "submission_updated")
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_updated", {})
            return batch

    def add_target(self, release_id: str, submission_id: str, target_id: str) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            self.ensure_mutable(batch)
            target_id = _validate_target_id(target_id)
            if any(item.target_id == target_id and item.status != "withdrawn" for item in batch.items):
                raise SubmissionValidationError("Distribution target is already in this submission batch.")
            batch.items.append(self.snapshot_item(release_id, submission_id, target_id, item_id=self._next_item_id(batch)))
            batch.latest_qa_summary = _stale_summary(batch.latest_qa_summary, "target_added")
            batch.latest_export_summary = _stale_summary(batch.latest_export_summary, "target_added")
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_target_added", {"target_id": target_id})
            return batch

    def remove_target(self, release_id: str, submission_id: str, item_id: str) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            self.ensure_mutable(batch)
            before = len(batch.items)
            batch.items = [item for item in batch.items if item.item_id != _validate_item_id(item_id)]
            if len(batch.items) == before:
                raise SubmissionNotFoundError(item_id)
            batch.latest_qa_summary = _stale_summary(batch.latest_qa_summary, "target_removed")
            batch.latest_export_summary = _stale_summary(batch.latest_export_summary, "target_removed")
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_target_removed", {"item_id": item_id})
            return batch

    def refresh_items(self, release_id: str, submission_id: str) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            self.ensure_mutable(batch)
            refreshed: list[SubmissionItem] = []
            for item in batch.items:
                current = self.snapshot_item(release_id, submission_id, item.target_id, item_id=item.item_id)
                current.status = _preserve_external_status(item.status, current.status)
                current.external_reference = item.external_reference
                current.submitted_at = item.submitted_at
                current.accepted_at = item.accepted_at
                current.feedback_summary = item.feedback_summary
                refreshed.append(current)
            batch.items = refreshed
            batch.latest_qa_summary = _stale_summary(batch.latest_qa_summary, "items_refreshed")
            batch.latest_export_summary = _stale_summary(batch.latest_export_summary, "items_refreshed")
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_items_refreshed", {"item_count": len(batch.items)})
            return batch

    def record_submission(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> SubmissionBatch:
        return self._update_item_external(
            release_id,
            submission_id,
            item_id,
            event_type="submission_item_submitted",
            allowed_statuses={"ready"},
            require_ready_snapshot=True,
            updater=lambda item: _record_item_submitted(item, payload),
        )

    def record_feedback(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument) -> SubmissionBatch:
        return self._update_item_external(
            release_id,
            submission_id,
            item_id,
            event_type="submission_item_feedback_recorded",
            allowed_statuses={"submitted", "feedback_received", "needs_changes"},
            updater=lambda item: _record_item_feedback(item, payload),
        )

    def mark_accepted(self, release_id: str, submission_id: str, item_id: str, payload: DomainDocument | None = None) -> SubmissionBatch:
        return self._update_item_external(
            release_id,
            submission_id,
            item_id,
            event_type="submission_item_accepted",
            allowed_statuses={"submitted", "feedback_received", "needs_changes"},
            updater=lambda item: _record_item_accepted(item, payload or {}),
        )

    def archive_submission(self, release_id: str, submission_id: str) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            batch.status = "archived"
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_archived", {})
            return batch

    def read_qa(self, release_id: str, submission_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.qa_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionNotFoundError("Submission QA does not exist.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_qa(self, release_id: str, submission_id: str, report: DomainDocument) -> DomainDocument:
        self.get_submission(release_id, submission_id)
        clean = sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.qa_path(release_id, submission_id), clean)
        return clean

    def update_qa_summary(self, release_id: str, submission_id: str, summary: DomainDocument) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_qa_summary = _safe_dict(summary)
        if batch.status not in {"signed", "archived", "submitted", "partially_accepted", "accepted", "needs_changes"}:
            batch.status = {"passed": "qa_passed", "warning": "qa_warning", "failed": "qa_failed", "stale": "qa_failed"}.get(str(summary.get("status") or ""), batch.status)
        return self.save_submission(batch)

    def update_export_summary(self, release_id: str, submission_id: str, summary: DomainDocument) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_export_summary = _safe_dict(summary)
        if batch.status not in {"signed", "archived", "submitted", "partially_accepted", "accepted", "needs_changes"}:
            batch.status = "exported"
        return self.save_submission(batch)

    def update_signoff_summary(self, release_id: str, submission_id: str, summary: DomainDocument) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_signoff_summary = _safe_dict(summary)
        if str(summary.get("status") or "") in SIGNED_SUBMISSION_STATUSES and batch.status != "archived":
            batch.status = "signed"
        return self.save_submission(batch)

    def read_signoff(self, release_id: str, submission_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.signoff_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionNotFoundError("Submission signoff does not exist.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_signoff(self, release_id: str, submission_id: str, record: DomainDocument) -> DomainDocument:
        self.get_submission(release_id, submission_id)
        clean = sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.signoff_path(release_id, submission_id), clean)
        return clean

    def reset_signoff(self, release_id: str, submission_id: str, reason: str) -> DomainDocument:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            existing = self.read_signoff(release_id, submission_id, default={})
            event = submission_signoff_history_event(existing, reason=reason, now=now_iso())
            if existing:
                history_path = self.signoff_history_path(release_id, submission_id)
                history_path.parent.mkdir(parents=True, exist_ok=True)
                with history_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, ensure_ascii=False) + "\n")
            signoff_path = self.signoff_path(release_id, submission_id)
            if signoff_path.exists():
                signoff_path.unlink()
            sidecar = self.export_dir(release_id, submission_id) / "submission-signoff.json"
            if sidecar.exists():
                sidecar.unlink()
            batch.latest_signoff_summary = {"status": "not_signed"}
            if batch.status == "signed":
                batch.status = "exported" if batch.latest_export_summary.get("exists") else "qa_passed"
            self.save_submission(batch)
            self.append_event(release_id, submission_id, "submission_signoff_reset", {"reason": event.get("reason")})
            return event

    def ensure_mutable(self, batch: SubmissionBatch) -> None:
        if batch.status == "archived":
            raise SubmissionStateError("Archived submission batches are read-only.")
        if self._has_signed_package(batch):
            raise SubmissionStateError("Signed submission packages cannot be modified. Reset submission signoff before changing this batch.")

    def snapshot_item(self, release_id: str, submission_id: str, target_id: str, *, item_id: str | None = None, now: str | None = None) -> SubmissionItem:
        now = now or now_iso()
        target = self.distribution_store.get_target(release_id, target_id)
        package_id = self.distribution_store.latest_package_id(target)
        zip_sha = _file_sha256(self.distribution_store.package_zip_path(release_id, package_id)) if package_id else None
        manifest = _safe_distribution_manifest(self.distribution_store, release_id, package_id)
        signoff = self.distribution_store.read_signoff(release_id, target, default={})
        verify_summary: DomainDocument = {}
        warnings: list[str] = []
        if package_id and self.distribution_store.package_zip_path(release_id, package_id).exists():
            verify_report = verify_distribution_package(self.distribution_store.package_zip_path(release_id, package_id))
            verify_summary = distribution_verification_summary(verify_report)
            if verify_report.get("status") not in {"passed", "warning"}:
                warnings.append("Distribution package verification failed.")
        else:
            warnings.append("Distribution package ZIP is missing.")
        if target.status not in SIGNED_DISTRIBUTION_STATUSES and target.latest_signoff_summary.get("status") not in SIGNED_DISTRIBUTION_STATUSES:
            warnings.append("Distribution target is not signed.")
        if signoff.get("status") not in SIGNED_DISTRIBUTION_STATUSES:
            warnings.append("Distribution signoff is missing.")
        status = "ready" if not warnings else "pending"
        return SubmissionItem(
            schema_version=SUBMISSION_ITEM_SCHEMA_VERSION,
            item_id=item_id or "item-000001",
            release_id=release_id,
            submission_id=submission_id,
            target_id=target.target_id,
            profile_id=target.profile_id,
            target_name=target.name,
            status=status,
            package_id=package_id,
            package_zip_sha256=zip_sha,
            distribution_manifest_hash=stable_hash({key: value for key, value in manifest.items() if key != "zip"}) if manifest else None,
            distribution_signoff_hash=stable_hash(signoff) if signoff else None,
            distribution_verify_summary=verify_summary,
            target_summary=distribution_target_summary(target),
            stale=False,
            warnings=warnings,
            created_at=now,
            updated_at=now,
        )

    def append_event(self, release_id: str, submission_id: str, event_type: str, payload: DomainDocument) -> None:
        path = self.events_path(release_id, submission_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_events(self, release_id: str, submission_id: str) -> list[DomainDocument]:
        path = self.events_path(release_id, submission_id)
        if not path.exists():
            return []
        rows: list[DomainDocument] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return sanitize_metadata(rows, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def summary(self, release_id: str) -> DomainDocument:
        rows = self.list_submissions(release_id)
        return sanitize_metadata(
            {
                "submission_count": len(rows),
                "latest_submission_id": rows[0].submission_id if rows else None,
                "latest_status": rows[0].status if rows else "missing",
                "signed_count": sum(1 for row in rows if row.latest_signoff_summary.get("status") in SIGNED_SUBMISSION_STATUSES or row.status == "signed"),
                "accepted_count": sum(1 for row in rows if row.status == "accepted"),
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    def _reserve_submission_id(self, release_id: str) -> str:
        root = self.submissions_dir(release_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            submission_id = f"sub-{index:06d}"
            path = root / submission_id
            try:
                path.mkdir(parents=True, exist_ok=False)
                return submission_id
            except FileExistsError:
                continue
        raise SubmissionValidationError("Unable to allocate a unique submission id.")

    def _next_item_id(self, batch: SubmissionBatch) -> str:
        used = {item.item_id for item in batch.items}
        for index in range(1, 1_000_000):
            item_id = f"item-{index:06d}"
            if item_id not in used:
                return item_id
        raise SubmissionValidationError("Unable to allocate a unique submission item id.")

    def _has_signed_package(self, batch: SubmissionBatch) -> bool:
        if batch.status == "signed" or batch.latest_signoff_summary.get("status") in SIGNED_SUBMISSION_STATUSES:
            return True
        signoff = self.read_signoff(batch.release_id, batch.submission_id, default={})
        return signoff.get("status") in SIGNED_SUBMISSION_STATUSES

    def _update_item_external(
        self,
        release_id: str,
        submission_id: str,
        item_id: str,
        *,
        event_type: str,
        updater: object,
        allowed_statuses: set[str],
        require_ready_snapshot: bool = False,
    ) -> SubmissionBatch:
        with self.lock:
            batch = self.get_submission(release_id, submission_id)
            if not self._has_signed_package(batch):
                raise SubmissionStateError("Submission batch must be signed before recording external submission status.")
            found = False
            validated_item_id = _validate_item_id(item_id)
            for item in batch.items:
                if item.item_id != validated_item_id:
                    continue
                self._ensure_external_item_transition(batch, item, allowed_statuses=allowed_statuses, require_ready_snapshot=require_ready_snapshot)
                updater(item)
                item.updated_at = now_iso()
                found = True
                self.append_event(release_id, submission_id, event_type, {"item_id": item_id, "target_id": item.target_id, "status": item.status})
                break
            if not found:
                raise SubmissionNotFoundError(item_id)
            batch.status = _batch_external_status(batch.items, batch.status)
            self.save_submission(batch)
            return batch

    def _ensure_external_item_transition(self, batch: SubmissionBatch, item: SubmissionItem, *, allowed_statuses: set[str], require_ready_snapshot: bool) -> None:
        if item.status not in allowed_statuses:
            allowed = ", ".join(sorted(allowed_statuses))
            raise SubmissionStateError(f"Submission item {item.item_id} must be in one of [{allowed}] before this external status update.")
        if item.stale:
            raise SubmissionStateError(f"Submission item {item.item_id} snapshot is stale. Refresh the submission batch before recording external status.")
        if item.warnings:
            raise SubmissionStateError(f"Submission item {item.item_id} is not ready: {item.warnings[0]}")
        current = submission_item_current_snapshot(self, item)
        if current.get("stale"):
            raise SubmissionStateError(f"Submission item {item.item_id} snapshot is stale. Refresh the submission batch before recording external status.")
        if require_ready_snapshot:
            current_item = self.snapshot_item(item.release_id, item.submission_id, item.target_id, item_id=item.item_id)
            if current_item.status != "ready":
                reason = current_item.warnings[0] if current_item.warnings else "Distribution package is not ready."
                raise SubmissionStateError(f"Submission item {item.item_id} is not ready: {reason}")
