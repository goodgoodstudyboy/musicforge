from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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


class SubmissionEvidenceStore:
    def __init__(self, submission_store: SubmissionStore) -> None:
        self.submission_store = submission_store
        self.lock = threading.RLock()

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

    def read_index(self, release_id: str, submission_id: str) -> dict[str, Any]:
        self.submission_store.get_submission(release_id, submission_id)
        path = self.index_path(release_id, submission_id)
        if not path.exists():
            return self._empty_index(release_id, submission_id)
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else self._empty_index(release_id, submission_id), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_index(self, release_id: str, submission_id: str, index: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(index, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.index_path(release_id, submission_id), clean)
        return clean

    def read_report(self, release_id: str, submission_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionEvidenceNotFoundError("Submission evidence report does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def read_signoff(self, release_id: str, submission_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.signoff_path(release_id, submission_id)
        if not path.exists():
            if default is not None:
                return default
            raise SubmissionEvidenceNotFoundError("Submission evidence signoff does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def overview(self, release_id: str, submission_id: str) -> dict[str, Any]:
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

    def upload_attachment(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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

    def record_submission(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> tuple[SubmissionBatch, dict[str, Any]]:
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

    def record_feedback(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> tuple[SubmissionBatch, dict[str, Any]]:
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

    def mark_accepted(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any] | None = None) -> tuple[SubmissionBatch, dict[str, Any]]:
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

    def create_resubmission_round(self, release_id: str, submission_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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

    def refresh_report(self, release_id: str, submission_id: str) -> dict[str, Any]:
        with self.lock:
            batch = self.submission_store.get_submission(release_id, submission_id)
            self._ensure_signed_submission(batch)
            index = self.read_index(release_id, submission_id)
            records = _index_records(index)
            attachments = _index_attachments(index)
            rounds = _index_rounds(index)
            checks: list[dict[str, Any]] = []
            item_checks: list[dict[str, Any]] = []
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
                evidence_types = set(summary.get("evidence_types") if isinstance(summary.get("evidence_types"), list) else [])
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

    def export_evidence(self, release_id: str, submission_id: str, *, now: str | None = None, allow_signed: bool = False) -> dict[str, Any]:
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
            files: list[dict[str, Any]] = []
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

    def build_zip(self, release_id: str, submission_id: str, *, now: str | None = None, allow_signed: bool = False) -> dict[str, Any]:
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

    def signoff_evidence(self, release_id: str, submission_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def reset_signoff(self, release_id: str, submission_id: str, reason: str) -> dict[str, Any]:
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

    def read_export_manifest(self, release_id: str, submission_id: str) -> dict[str, Any]:
        path = self.export_dir(release_id, submission_id) / "submission-evidence-manifest.json"
        if not path.exists():
            raise SubmissionEvidenceNotFoundError("Submission evidence export has not been generated.")
        return sanitize_metadata(read_json(path), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def refresh_export_signoff_summary(self, release_id: str, submission_id: str) -> dict[str, Any]:
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

    def append_event(self, release_id: str, submission_id: str, event_type: str, payload: dict[str, Any]) -> None:
        path = self.events_path(release_id, submission_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def index_summary(self, index: dict[str, Any], *, batch: SubmissionBatch | None = None) -> dict[str, Any]:
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

    def item_summaries(self, release_id: str, submission_id: str, *, index: dict[str, Any] | None = None, batch: SubmissionBatch | None = None) -> list[dict[str, Any]]:
        index = index or self.read_index(release_id, submission_id)
        batch = batch or self.submission_store.get_submission(release_id, submission_id)
        records = _index_records(index)
        rounds = _index_rounds(index)
        result: list[dict[str, Any]] = []
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

    def _empty_index(self, release_id: str, submission_id: str) -> ImplementationDocument:
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

    def _preflight_external_update(self, release_id: str, submission_id: str, item_id: str, *, allowed_statuses: set[str], require_ready_snapshot: bool, payload: ImplementationDocument) -> None:
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

    def _create_evidence(self, release_id: str, submission_id: str, item_id: str, payload: ImplementationDocument, *, evidence_type: str, platform_status: str) -> ImplementationDocument:
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

    def _create_inline_attachments(self, release_id: str, submission_id: str, item_id: str, payload: ImplementationDocument, index: ImplementationDocument) -> list[str]:
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

    def _round_for_evidence(self, index: ImplementationDocument, batch: SubmissionBatch, item: SubmissionItem, *, evidence_type: str, platform_status: str, payload: ImplementationDocument) -> ImplementationDocument:
        rounds = _index_rounds(index)
        item_rounds = [row for row in rounds if row.get("item_id") == item.item_id]
        if evidence_type == "resubmission_receipt":
            return self._new_round(index, batch, item, round_type="resubmission", status=platform_status, payload=payload)
        if evidence_type == "submission_receipt" and not item_rounds:
            return self._new_round(index, batch, item, round_type="initial_submission", status=platform_status, payload=payload)
        if item_rounds:
            return sorted(item_rounds, key=lambda row: int(row.get("round_number") or 0))[-1]
        return self._new_round(index, batch, item, round_type="initial_submission", status=platform_status, payload=payload)

    def _new_round(self, index: ImplementationDocument, batch: SubmissionBatch, item: SubmissionItem, *, round_type: str, status: str, payload: ImplementationDocument) -> ImplementationDocument:
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

    def _write_record_file(self, release_id: str, submission_id: str, record: ImplementationDocument) -> None:
        path = self.evidence_dir(release_id, submission_id) / "items" / str(record.get("item_id")) / "evidence" / f"{record.get('evidence_id')}.json"
        write_json(path, sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _write_round_files(self, release_id: str, submission_id: str, index: ImplementationDocument) -> None:
        for row in _index_rounds(index):
            path = self.evidence_dir(release_id, submission_id) / "items" / str(row.get("item_id")) / "rounds" / f"{row.get('round_id')}.json"
            write_json(path, sanitize_metadata(row, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))

    def _write_export_items(self, export_dir: Path, index: ImplementationDocument, files: list[ImplementationDocument]) -> None:
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

    def _write_readme(self, export_dir: Path, batch: SubmissionBatch, report: ImplementationDocument) -> None:
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

    def _next_evidence_id(self, index: ImplementationDocument) -> str:
        used = {str(row.get("evidence_id") or "") for row in _index_records(index)}
        for number in range(1, 1_000_000):
            candidate = f"ev-{number:06d}"
            if candidate not in used:
                return candidate
        raise SubmissionEvidenceValidationError("Unable to allocate a unique evidence id.")

    def _next_attachment_id(self, index: ImplementationDocument) -> str:
        used = {str(row.get("attachment_id") or "") for row in _index_attachments(index)}
        for number in range(1, 1_000_000):
            candidate = f"att-{number:06d}"
            if candidate not in used:
                return candidate
        raise SubmissionEvidenceValidationError("Unable to allocate a unique attachment id.")

    def source_snapshot(self, batch: SubmissionBatch, item: SubmissionItem) -> dict[str, Any]:
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

    def _report_source(self, batch: SubmissionBatch, index: ImplementationDocument) -> ImplementationDocument:
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

    def _evidence_stale_reasons(self, record: ImplementationDocument) -> list[str]:
        try:
            batch = self.submission_store.get_submission(str(record.get("release_id")), str(record.get("submission_id")))
            item = _find_item(batch, str(record.get("item_id")))
        except Exception:
            return ["source item is missing"]
        current = self.source_snapshot(batch, item)
        expected = record.get("source_snapshot") if isinstance(record.get("source_snapshot"), dict) else {}
        reasons = [key for key, value in expected.items() if current.get(key) != value]
        if reasons:
            return [f"source snapshot mismatch: {', '.join(sorted(reasons))}"]
        if not submission_evidence_record_integrity_ok(record):
            return ["evidence integrity mismatch"]
        return []

    def _attachment_failure_reasons(self, attachment: ImplementationDocument) -> list[str]:
        reasons: list[str] = []
        if not submission_evidence_attachment_integrity_ok(attachment):
            reasons.append("attachment metadata integrity mismatch")
        redaction = attachment.get("redaction_summary") if isinstance(attachment.get("redaction_summary"), dict) else {}
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

    def _ensure_report_allows_signoff(self, report: ImplementationDocument, *, require_submitted: bool, require_accepted: bool) -> None:
        if not submission_evidence_report_integrity_ok(report):
            raise SubmissionEvidenceStateError("Submission evidence report integrity failed.")
        if report.get("status") == "failed":
            raise SubmissionEvidenceStateError("Submission evidence report failed.")
        summaries = report.get("item_summaries") if isinstance(report.get("item_summaries"), list) else []
        if require_submitted:
            missing = [str(item.get("item_id") or "") for item in summaries if item.get("status") not in SUBMITTED_OR_LATER]
            if missing:
                raise SubmissionEvidenceStateError("Submission evidence signoff requires every item to be submitted.")
        if require_accepted:
            missing = [str(item.get("item_id") or "") for item in summaries if item.get("status") != "accepted"]
            if missing:
                raise SubmissionEvidenceStateError("Submission evidence signoff requires every item to be accepted.")


def submission_evidence_record_integrity_hash(record: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in record.items() if key not in {"integrity_hash", "stale", "warnings"}})


def submission_evidence_record_integrity_ok(record: dict[str, Any]) -> bool:
    return bool(record.get("integrity_hash")) and str(record.get("integrity_hash")) == submission_evidence_record_integrity_hash(record)


def submission_evidence_attachment_integrity_hash(record: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in record.items() if key != "integrity_hash"})


def submission_evidence_attachment_integrity_ok(record: dict[str, Any]) -> bool:
    return bool(record.get("integrity_hash")) and str(record.get("integrity_hash")) == submission_evidence_attachment_integrity_hash(record)


def submission_evidence_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def submission_evidence_report_integrity_ok(report: dict[str, Any]) -> bool:
    return bool(report.get("integrity_hash")) and str(report.get("integrity_hash")) == submission_evidence_report_integrity_hash(report)


def submission_evidence_signoff_payload_hash(signoff: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in signoff.items() if key not in SUBMISSION_EVIDENCE_SIGNOFF_EXCLUDE_KEYS})


def submission_evidence_signoff_summary(signoff: dict[str, Any] | None) -> dict[str, Any]:
    data = signoff if isinstance(signoff, dict) else {}
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


def submission_evidence_report_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
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
    timeline = summary.get("timeline") if isinstance(summary.get("timeline"), list) else []
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
