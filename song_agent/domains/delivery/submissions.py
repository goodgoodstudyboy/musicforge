# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

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
    distribution_verify_summary: ImplementationDocument = field(default_factory=dict)
    target_summary: ImplementationDocument = field(default_factory=dict)
    external_reference: str | None = None
    submitted_at: str | None = None
    accepted_at: str | None = None
    feedback_summary: ImplementationDocument = field(default_factory=dict)
    stale: bool = False
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "SubmissionItem":
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
    latest_qa_summary: ImplementationDocument = field(default_factory=dict)
    latest_export_summary: ImplementationDocument = field(default_factory=dict)
    latest_signoff_summary: ImplementationDocument = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "SubmissionBatch":
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


from song_agent.domains.delivery import v142_s_readiness as _v142_s_readiness
from song_agent.domains.delivery.v142_s_readiness import SubmissionStore
from song_agent.domains.delivery import v142_s_evidence as _v142_s_evidence
from song_agent.domains.delivery.v142_s_evidence import (
    submission_batch_summary,
    submission_signoff_summary,
    build_submission_signoff_record,
    submission_signoff_history_event,
    submission_item_current_snapshot,
    _safe_distribution_manifest,
    _record_item_submitted,
    _record_item_feedback,
    _record_item_accepted,
    _batch_external_status,
    _preserve_external_status,
    _target_ids_from_payload,
    _stale_summary,
    _safe_dict,
    _safe_text,
    _optional_text,
    _optional_hash,
    _optional_id,
    _validate_submission_id,
    _validate_item_id,
    _validate_target_id,
    _file_sha256,
)

_v142_s_readiness.bind_globals(globals())
_v142_s_evidence.bind_globals(globals())
