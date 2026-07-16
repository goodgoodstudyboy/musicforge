from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.delivery.distribution import DistributionNotFoundError as DistributionNotFoundError, DistributionStore as DistributionStore, DistributionTarget as DistributionTarget, SIGNED_DISTRIBUTION_STATUSES as SIGNED_DISTRIBUTION_STATUSES, distribution_signoff_summary as distribution_signoff_summary, distribution_target_summary as distribution_target_summary
from song_agent.domains.delivery.distribution_export import read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash


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


class SubmissionError(Exception):
    pass


class SubmissionNotFoundError(SubmissionError):
    pass


class SubmissionValidationError(SubmissionError):
    pass


class SubmissionStateError(SubmissionError):
    pass


@dataclass
class SubmissionItem:
    schema_version: int
    item_id: str
    release_id: str
    submission_id: str
    target_id: str
    profile_id: str
    target_name: str
    status: str
    package_id: str | None = None
    package_zip_sha256: str | None = None
    distribution_manifest_hash: str | None = None
    distribution_signoff_hash: str | None = None
    distribution_verify_summary: dict[str, Any] = field(default_factory=dict)
    target_summary: dict[str, Any] = field(default_factory=dict)
    external_reference: str | None = None
    submitted_at: str | None = None
    accepted_at: str | None = None
    feedback_summary: dict[str, Any] = field(default_factory=dict)
    stale: bool = False
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "item_id": self.item_id,
                "release_id": self.release_id,
                "submission_id": self.submission_id,
                "target_id": self.target_id,
                "profile_id": self.profile_id,
                "target_name": self.target_name,
                "status": self.status,
                "package_id": self.package_id,
                "package_zip_sha256": self.package_zip_sha256,
                "distribution_manifest_hash": self.distribution_manifest_hash,
                "distribution_signoff_hash": self.distribution_signoff_hash,
                "distribution_verify_summary": self.distribution_verify_summary,
                "target_summary": self.target_summary,
                "external_reference": self.external_reference,
                "submitted_at": self.submitted_at,
                "accepted_at": self.accepted_at,
                "feedback_summary": self.feedback_summary,
                "stale": self.stale,
                "warnings": self.warnings,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubmissionItem":
        created_at = str(data.get("created_at") or now_iso())
        status = str(data.get("status") or "pending")
        if status not in SUBMISSION_ITEM_STATUSES:
            status = "pending"
        return cls(
            schema_version=int(data.get("schema_version") or SUBMISSION_ITEM_SCHEMA_VERSION),
            item_id=_validate_item_id(str(data.get("item_id") or "item-000001")),
            release_id=str(data.get("release_id") or ""),
            submission_id=_validate_submission_id(str(data.get("submission_id") or "sub-000001")),
            target_id=_validate_target_id(str(data.get("target_id") or "target-000001")),
            profile_id=_safe_text(data.get("profile_id"), 80) or "generic_dsp",
            target_name=_safe_text(data.get("target_name"), 120) or "Distribution Target",
            status=status,
            package_id=_optional_id(data.get("package_id"), prefix="package-"),
            package_zip_sha256=_optional_hash(data.get("package_zip_sha256")),
            distribution_manifest_hash=_optional_hash(data.get("distribution_manifest_hash")),
            distribution_signoff_hash=_optional_hash(data.get("distribution_signoff_hash")),
            distribution_verify_summary=_safe_dict(data.get("distribution_verify_summary")),
            target_summary=_safe_dict(data.get("target_summary")),
            external_reference=_optional_text(data.get("external_reference"), 200),
            submitted_at=_optional_text(data.get("submitted_at"), 80),
            accepted_at=_optional_text(data.get("accepted_at"), 80),
            feedback_summary=_safe_dict(data.get("feedback_summary")),
            stale=bool(data.get("stale", False)),
            warnings=[_safe_text(item, 240) for item in data.get("warnings", []) if str(item).strip()],
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


@dataclass
class SubmissionBatch:
    schema_version: int
    submission_id: str
    release_id: str
    name: str
    status: str
    platform_group: str | None = None
    notes: str | None = None
    items: list[SubmissionItem] = field(default_factory=list)
    latest_qa_summary: dict[str, Any] = field(default_factory=dict)
    latest_export_summary: dict[str, Any] = field(default_factory=dict)
    latest_signoff_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "submission_id": self.submission_id,
                "release_id": self.release_id,
                "name": self.name,
                "status": self.status,
                "platform_group": self.platform_group,
                "notes": self.notes,
                "items": [item.to_dict() for item in self.items],
                "latest_qa_summary": self.latest_qa_summary,
                "latest_export_summary": self.latest_export_summary,
                "latest_signoff_summary": self.latest_signoff_summary,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubmissionBatch":
        created_at = str(data.get("created_at") or now_iso())
        status = str(data.get("status") or "draft")
        if status not in SUBMISSION_STATUSES:
            status = "draft"
        return cls(
            schema_version=int(data.get("schema_version") or SUBMISSION_BATCH_SCHEMA_VERSION),
            submission_id=_validate_submission_id(str(data.get("submission_id") or "sub-000001")),
            release_id=str(data.get("release_id") or ""),
            name=_safe_text(data.get("name"), 120) or "Submission Batch",
            status=status,
            platform_group=_optional_text(data.get("platform_group"), 80),
            notes=_optional_text(data.get("notes"), 2000),
            items=[SubmissionItem.from_dict(item) for item in data.get("items", []) if isinstance(item, dict)],
            latest_qa_summary=_safe_dict(data.get("latest_qa_summary")),
            latest_export_summary=_safe_dict(data.get("latest_export_summary")),
            latest_signoff_summary=_safe_dict(data.get("latest_signoff_summary")),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


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

    def create_submission(self, release_id: str, payload: dict[str, Any]) -> SubmissionBatch:
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

    def update_submission(self, release_id: str, submission_id: str, patch: dict[str, Any]) -> SubmissionBatch:
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

    def record_submission(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> SubmissionBatch:
        return self._update_item_external(
            release_id,
            submission_id,
            item_id,
            event_type="submission_item_submitted",
            allowed_statuses={"ready"},
            require_ready_snapshot=True,
            updater=lambda item: _record_item_submitted(item, payload),
        )

    def record_feedback(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> SubmissionBatch:
        return self._update_item_external(
            release_id,
            submission_id,
            item_id,
            event_type="submission_item_feedback_recorded",
            allowed_statuses={"submitted", "feedback_received", "needs_changes"},
            updater=lambda item: _record_item_feedback(item, payload),
        )

    def mark_accepted(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any] | None = None) -> SubmissionBatch:
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

    def read_qa(self, release_id: str, submission_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.qa_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionNotFoundError("Submission QA does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_qa(self, release_id: str, submission_id: str, report: dict[str, Any]) -> dict[str, Any]:
        self.get_submission(release_id, submission_id)
        clean = sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.qa_path(release_id, submission_id), clean)
        return clean

    def update_qa_summary(self, release_id: str, submission_id: str, summary: dict[str, Any]) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_qa_summary = _safe_dict(summary)
        if batch.status not in {"signed", "archived", "submitted", "partially_accepted", "accepted", "needs_changes"}:
            batch.status = {"passed": "qa_passed", "warning": "qa_warning", "failed": "qa_failed", "stale": "qa_failed"}.get(str(summary.get("status") or ""), batch.status)
        return self.save_submission(batch)

    def update_export_summary(self, release_id: str, submission_id: str, summary: dict[str, Any]) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_export_summary = _safe_dict(summary)
        if batch.status not in {"signed", "archived", "submitted", "partially_accepted", "accepted", "needs_changes"}:
            batch.status = "exported"
        return self.save_submission(batch)

    def update_signoff_summary(self, release_id: str, submission_id: str, summary: dict[str, Any]) -> SubmissionBatch:
        batch = self.get_submission(release_id, submission_id)
        batch.latest_signoff_summary = _safe_dict(summary)
        if str(summary.get("status") or "") in SIGNED_SUBMISSION_STATUSES and batch.status != "archived":
            batch.status = "signed"
        return self.save_submission(batch)

    def read_signoff(self, release_id: str, submission_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.signoff_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionNotFoundError("Submission signoff does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_signoff(self, release_id: str, submission_id: str, record: dict[str, Any]) -> dict[str, Any]:
        self.get_submission(release_id, submission_id)
        clean = sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.signoff_path(release_id, submission_id), clean)
        return clean

    def reset_signoff(self, release_id: str, submission_id: str, reason: str) -> dict[str, Any]:
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
        verify_summary: dict[str, Any] = {}
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

    def append_event(self, release_id: str, submission_id: str, event_type: str, payload: dict[str, Any]) -> None:
        path = self.events_path(release_id, submission_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_events(self, release_id: str, submission_id: str) -> list[dict[str, Any]]:
        path = self.events_path(release_id, submission_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
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

    def summary(self, release_id: str) -> dict[str, Any]:
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
        updater: Any,
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


def submission_batch_summary(batch: SubmissionBatch | dict[str, Any] | None) -> dict[str, Any]:
    data = batch.to_dict() if isinstance(batch, SubmissionBatch) else batch if isinstance(batch, dict) else {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    status_counts: dict[str, int] = {}
    for item in items:
        if isinstance(item, dict):
            status = str(item.get("status") or "pending")
            status_counts[status] = status_counts.get(status, 0) + 1
    return sanitize_metadata(
        {
            "submission_id": data.get("submission_id"),
            "release_id": data.get("release_id"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "platform_group": data.get("platform_group"),
            "item_count": len(items),
            "ready_count": status_counts.get("ready", 0),
            "submitted_count": status_counts.get("submitted", 0),
            "accepted_count": status_counts.get("accepted", 0),
            "needs_changes_count": status_counts.get("needs_changes", 0),
            "qa_status": (data.get("latest_qa_summary") or {}).get("status") if isinstance(data.get("latest_qa_summary"), dict) else None,
            "export_status": (data.get("latest_export_summary") or {}).get("status") if isinstance(data.get("latest_export_summary"), dict) else None,
            "signoff_status": (data.get("latest_signoff_summary") or {}).get("status") if isinstance(data.get("latest_signoff_summary"), dict) else None,
            "updated_at": data.get("updated_at"),
            "status_counts": status_counts,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def submission_signoff_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    data = record if isinstance(record, dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "submission_id": data.get("submission_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "qa_source_hash": data.get("qa_source_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
            "forced": bool(data.get("forced", False)),
            "rights_clearance": data.get("rights_clearance") if isinstance(data.get("rights_clearance"), dict) else {},
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def build_submission_signoff_record(
    *,
    batch: SubmissionBatch,
    qa_report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    export_manifest: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    payload = payload or {}
    force = bool(payload.get("force", False))
    if force and not str(payload.get("override_reason") or "").strip():
        raise ValueError("override_reason is required when force=true.")
    blockers = qa_report.get("blockers", []) if isinstance(qa_report.get("blockers"), list) else []
    warnings = qa_report.get("warnings", []) if isinstance(qa_report.get("warnings"), list) else []
    if not force and (qa_report.get("status") not in {"passed", "warning"} or blockers):
        raise ValueError("Submission QA does not allow signoff.")
    record = {
        "schema_version": 1,
        "release_id": batch.release_id,
        "submission_id": batch.submission_id,
        "status": "force_signed" if force else "signed",
        "signed_at": now,
        "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
        "qa_source_hash": qa_report.get("source_hash"),
        "submission_source_hash": qa_report.get("source_hash"),
        "export_manifest_hash": stable_hash(export_manifest) if isinstance(export_manifest, dict) and export_manifest else None,
        "forced": force,
        "override_reason": _safe_text(payload.get("override_reason"), 500) if force else None,
        "acknowledged_blockers": blockers if force else [],
        "acknowledged_warnings": warnings,
        "rights_clearance": payload.get("rights_clearance") if isinstance(payload.get("rights_clearance"), dict) else {},
        "notes": _safe_text(payload.get("notes"), 2000),
    }
    return sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def submission_signoff_history_event(record: dict[str, Any], *, reason: str, now: str | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "timestamp": now or now_iso(),
            "event": "submission_signoff_reset",
            "reason": sanitize_sensitive_text(str(reason or ""))[:500],
            "previous_summary": submission_signoff_summary(record),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def submission_item_current_snapshot(store: SubmissionStore, item: SubmissionItem) -> dict[str, Any]:
    try:
        current = store.snapshot_item(item.release_id, item.submission_id, item.target_id, item_id=item.item_id)
    except (DistributionNotFoundError, ValueError, OSError):
        return {"exists": False, "stale": True, "target_id": item.target_id}
    return sanitize_metadata(
        {
            "exists": True,
            "target_id": current.target_id,
            "package_id": current.package_id,
            "package_zip_sha256": current.package_zip_sha256,
            "distribution_manifest_hash": current.distribution_manifest_hash,
            "distribution_signoff_hash": current.distribution_signoff_hash,
            "distribution_verify_summary": current.distribution_verify_summary,
            "stale": item.package_id != current.package_id
            or item.package_zip_sha256 != current.package_zip_sha256
            or item.distribution_manifest_hash != current.distribution_manifest_hash
            or item.distribution_signoff_hash != current.distribution_signoff_hash,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _safe_distribution_manifest(store: DistributionStore, release_id: str, package_id: str | None) -> ImplementationDocument:
    if not package_id:
        return {}
    try:
        return read_distribution_export_manifest(store, release_id, package_id)
    except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError):
        return {}


def _record_item_submitted(item: SubmissionItem, payload: ImplementationDocument) -> None:
    item.status = "submitted"
    item.submitted_at = str(payload.get("submitted_at") or now_iso())
    item.external_reference = _optional_text(payload.get("external_reference"), 200)


def _record_item_feedback(item: SubmissionItem, payload: ImplementationDocument) -> None:
    status = str(payload.get("status") or "needs_changes")
    if status not in {"feedback_received", "needs_changes", "rejected"}:
        status = "feedback_received"
    item.status = status
    item.feedback_summary = sanitize_metadata(
        {
            "status": status,
            "received_at": str(payload.get("received_at") or now_iso()),
            "message": _safe_text(payload.get("message"), 1000),
            "external_reference": _optional_text(payload.get("external_reference"), 200),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _record_item_accepted(item: SubmissionItem, payload: ImplementationDocument) -> None:
    item.status = "accepted"
    item.accepted_at = str(payload.get("accepted_at") or now_iso())
    if payload.get("external_reference"):
        item.external_reference = _optional_text(payload.get("external_reference"), 200)


def _batch_external_status(items: list[SubmissionItem], fallback: str) -> str:
    active = [item for item in items if item.status != "withdrawn"]
    if active and all(item.status == "accepted" for item in active):
        return "accepted"
    if any(item.status == "accepted" for item in active):
        return "partially_accepted"
    if any(item.status in {"needs_changes", "rejected"} for item in active):
        return "needs_changes"
    if active and all(item.status in {"submitted", "feedback_received"} for item in active):
        return "submitted"
    return fallback


def _preserve_external_status(old: str, new: str) -> str:
    return old if old in {"submitted", "feedback_received", "needs_changes", "accepted", "rejected", "withdrawn"} else new


def _target_ids_from_payload(payload: ImplementationDocument) -> list[str]:
    raw = payload.get("target_ids")
    if not isinstance(raw, list):
        raw = payload.get("targets") if isinstance(payload.get("targets"), list) else []
    ids: list[str] = []
    for value in raw:
        text = str(value.get("target_id") if isinstance(value, dict) else value or "").strip()
        if text:
            ids.append(_validate_target_id(text))
    return ids


def _stale_summary(summary: ImplementationDocument | None, reason: str) -> ImplementationDocument:
    data = dict(summary or {})
    if data:
        data["stale"] = True
        data["status"] = "stale"
        data["stale_reason"] = reason
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _safe_dict(value: Any) -> ImplementationDocument:
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _optional_text(value: Any, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None


def _optional_hash(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return text.lower()
    return None


def _optional_id(value: Any, *, prefix: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith(prefix) or not text.removeprefix(prefix).isdigit():
        raise SubmissionValidationError("Invalid identifier.")
    return text


def _validate_submission_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("sub-") or not text.removeprefix("sub-").isdigit():
        raise SubmissionValidationError("Invalid submission_id.")
    return text


def _validate_item_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("item-") or not text.removeprefix("item-").isdigit():
        raise SubmissionValidationError("Invalid submission item id.")
    return text


def _validate_target_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("target-") or not text.removeprefix("target-").isdigit():
        raise SubmissionValidationError("Invalid distribution target id.")
    return text


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
