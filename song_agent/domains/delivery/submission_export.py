from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import csv as csv
import hashlib as hashlib
import io as io
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_export import read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package, write_distribution_verification_report as write_distribution_verification_report
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore as RightsClearanceStore
from song_agent.domains.delivery.submission_qa import submission_qa_allows_export as submission_qa_allows_export, submission_source_state as submission_source_state
from song_agent.domains.delivery.submissions import SubmissionBatch as SubmissionBatch, SubmissionStore as SubmissionStore, build_submission_signoff_record as build_submission_signoff_record, submission_batch_summary as submission_batch_summary, submission_signoff_summary as submission_signoff_summary


SUBMISSION_EXPORT_SCHEMA_VERSION = 1
SUBMISSION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class SubmissionExportError(ValueError):
    pass


def build_submission_export_bundle(
    *,
    store: SubmissionStore,
    release_id: str,
    submission: SubmissionBatch,
    qa_report: DomainDocument,
    now: str | None = None,
) -> DomainDocument:
    now = now or now_iso()
    store.ensure_mutable(submission)
    current_source_hash = stable_hash(submission_source_state(store=store, release_id=release_id, submission=submission))
    if not submission_qa_allows_export(qa_report, current_source_hash=current_source_hash):
        raise SubmissionExportError("Submission QA gate failed. Refresh Submission QA before export.")
    submission_dir = store.submission_dir(release_id, submission.submission_id).resolve()
    export_dir = store.export_dir(release_id, submission.submission_id).resolve()
    _ensure_within(submission_dir, export_dir)
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    files: list[ImplementationDocument] = []
    target_rows: list[ImplementationDocument] = []
    for item in submission.items:
        if item.status == "withdrawn":
            continue
        if not item.package_id:
            raise SubmissionExportError(f"Submission item {item.item_id} has no distribution package.")
        target = store.distribution_store.get_target(release_id, item.target_id)
        zip_source = store.distribution_store.package_zip_path(release_id, item.package_id).resolve()
        if not zip_source.exists() or not zip_source.is_file() or zip_source.is_symlink():
            raise SubmissionExportError(f"Distribution package ZIP is missing for target {item.target_id}.")
        target_dir = (export_dir / "targets" / _validate_relative_path(item.target_id)).resolve()
        _ensure_within(export_dir, target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        zip_dest = target_dir / "distribution-package.zip"
        shutil.copy2(zip_source, zip_dest)
        files.append(_file_record(export_dir, zip_dest))
        manifest = read_distribution_export_manifest(store.distribution_store, release_id, item.package_id)
        _write_json(target_dir / "distribution-manifest.json", manifest)
        files.append(_file_record(export_dir, target_dir / "distribution-manifest.json"))
        verify_report = verify_distribution_package(zip_source)
        write_distribution_verification_report(verify_report, target_dir / "distribution-verify-report.json")
        files.append(_file_record(export_dir, target_dir / "distribution-verify-report.json"))
        target_rows.append(
            {
                "item_id": item.item_id,
                "target_id": item.target_id,
                "target_name": item.target_name,
                "profile_id": item.profile_id,
                "package_id": item.package_id,
                "status": item.status,
                "zip_sha256": item.package_zip_sha256,
                "verify_status": verify_report.get("status"),
                "external_reference": item.external_reference or "",
            }
        )
        _ = target

    signoff_public = _submission_signoff_export_summary({})
    _write_json(export_dir / "submission-signoff.json", signoff_public)
    report_path = export_dir / "submission-report.json"
    targets_path = export_dir / "submission-targets.csv"
    events_path = export_dir / "submission-events.jsonl"
    _write_json(report_path, _submission_report_payload(submission, qa_report, now))
    _write_targets_csv(targets_path, target_rows)
    events_path.write_text(_events_jsonl(store.read_events(release_id, submission.submission_id)), encoding="utf-8")
    rights_clearance_summary = _write_rights_clearance_sidecars(store, release_id, export_dir, files)
    _write_readme(export_dir, submission, qa_report, target_rows)
    files.extend(_file_record(export_dir, path) for path in [report_path, targets_path, events_path, export_dir / "README.txt"])

    manifest = {
        "schema_version": SUBMISSION_EXPORT_SCHEMA_VERSION,
        "tool": {"name": "MusicForge Submission Export", "version": __version__},
        "release_id": release_id,
        "submission_id": submission.submission_id,
        "submission_name": submission.name,
        "generated_at": now,
        "source_hash": current_source_hash,
        "qa_source_hash": qa_report.get("source_hash"),
        "submission": submission_batch_summary(submission),
        "items": [item.to_dict() for item in submission.items],
        "targets": target_rows,
        "sidecars": {
            "submission_signoff": _submission_signoff_sidecar_record(signoff_public),
        },
        "rights_clearance": rights_clearance_summary,
        "files": sorted(files, key=lambda item: item["path"]),
        "summary": {
            "status": "exported",
            "item_count": len(target_rows),
            "file_count": len(files),
            "total_bytes": sum(int(item.get("size_bytes") or 0) for item in files),
            "qa_status": qa_report.get("status"),
            "signoff_status": signoff_public.get("status"),
        },
        "redaction_summary": {"status": "passed"},
    }
    _write_json(export_dir / "submission-manifest.json", sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    manifest = read_submission_export_manifest(store, release_id, submission.submission_id)
    submission.latest_export_summary = submission_export_summary(manifest)
    submission.latest_signoff_summary = {"status": "not_signed"}
    store.save_submission(submission)
    store.append_event(release_id, submission.submission_id, "submission_export_created", {"file_count": len(files)})
    return manifest


def build_submission_package_zip(store: SubmissionStore, release_id: str, submission: SubmissionBatch, *, now: str | None = None, allow_signed: bool = False) -> DomainDocument:
    now = now or now_iso()
    if not allow_signed:
        store.ensure_mutable(submission)
    refresh_submission_export_signoff_summary(store, release_id, submission.submission_id)
    export_dir = store.export_dir(release_id, submission.submission_id).resolve()
    zip_path = store.package_zip_path(release_id, submission.submission_id).resolve()
    _ensure_within(store.submission_dir(release_id, submission.submission_id).resolve(), export_dir)
    _ensure_within(store.submission_dir(release_id, submission.submission_id).resolve(), zip_path)
    if not export_dir.exists():
        raise FileNotFoundError("Submission export has not been generated.")
    entries = _zip_entries(export_dir)
    manifest = read_submission_export_manifest(store, release_id, submission.submission_id)
    manifest["zip"] = {
        "created_at": now,
        "filename": zip_path.name,
        "entry_count": len(entries),
        "entries": [entry for _path, entry in entries],
    }
    _write_json(export_dir / "submission-manifest.json", sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
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
    zip_info = {
        "created_at": now,
        "filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256_file(zip_path),
        "entry_count": len(entries),
        "entries": [entry for _path, entry in entries],
    }
    manifest = read_submission_export_manifest(store, release_id, submission.submission_id)
    submission.latest_export_summary = submission_export_summary(manifest)
    store.save_submission(submission)
    store.append_event(release_id, submission.submission_id, "submission_package_zip_created", {"sha256": zip_info.get("sha256")})
    return sanitize_metadata(zip_info, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def sign_submission_package(
    *,
    store: SubmissionStore,
    release_id: str,
    submission: SubmissionBatch,
    qa_report: DomainDocument,
    payload: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
    now = now or now_iso()
    store.ensure_mutable(submission)
    existing = store.read_signoff(release_id, submission.submission_id, default={})
    if existing:
        raise SubmissionExportError("Submission package is already signed off. Reset submission signoff before signing again.")
    manifest = read_submission_export_manifest(store, release_id, submission.submission_id)
    zip_path = store.package_zip_path(release_id, submission.submission_id)
    if not zip_path.exists() or not isinstance(manifest.get("zip"), dict) or not manifest["zip"].get("entry_count"):
        raise SubmissionExportError("Submission ZIP has not been generated.")
    pending = build_submission_signoff_record(batch=submission, qa_report=qa_report, payload=payload or {}, export_manifest={}, now=now)
    store.write_signoff(release_id, submission.submission_id, {**pending, "export_manifest_hash": None})
    final_manifest = refresh_submission_export_signoff_summary(store, release_id, submission.submission_id)
    final_manifest.pop("zip", None)
    final_hash = stable_hash(final_manifest)
    signoff = store.write_signoff(release_id, submission.submission_id, {**pending, "export_manifest_hash": final_hash})
    refresh_submission_export_signoff_summary(store, release_id, submission.submission_id)
    build_submission_package_zip(store, release_id, submission, now=now, allow_signed=True)
    store.update_signoff_summary(release_id, submission.submission_id, submission_signoff_summary(signoff))
    store.append_event(release_id, submission.submission_id, "submission_package_signed", {"forced": bool((payload or {}).get("force"))})
    return signoff


def refresh_submission_export_signoff_summary(store: SubmissionStore, release_id: str, submission_id: str) -> DomainDocument:
    export_dir = store.export_dir(release_id, submission_id)
    manifest_path = export_dir / "submission-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Submission export has not been generated.")
    signoff = store.read_signoff(release_id, submission_id, default={})
    signoff_public = _submission_signoff_export_summary(signoff)
    _write_json(export_dir / "submission-signoff.json", signoff_public)
    manifest = read_submission_export_manifest(store, release_id, submission_id)
    summary = _as_document(manifest.get("summary"))
    summary["signoff_status"] = signoff_public.get("status")
    manifest["summary"] = summary
    sidecars = _as_document(manifest.get("sidecars"))
    sidecars["submission_signoff"] = _submission_signoff_sidecar_record(signoff_public)
    manifest["sidecars"] = sidecars
    manifest["files"] = sorted([item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("path") != "submission-signoff.json"], key=lambda item: item["path"])
    _write_json(manifest_path, sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    return read_submission_export_manifest(store, release_id, submission_id)


def read_submission_export_manifest(store: SubmissionStore, release_id: str, submission_id: str) -> DomainDocument:
    path = store.export_dir(release_id, submission_id) / "submission-manifest.json"
    if not path.exists():
        raise FileNotFoundError("Submission export has not been generated.")
    value = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def submission_export_summary(manifest: DomainDocument | None) -> DomainDocument:
    data = _as_document(manifest)
    summary = _as_document(data.get("summary"))
    zip_info = _as_document(data.get("zip"))
    return sanitize_metadata(
        {
            "status": "exported" if data else "missing",
            "exists": bool(data),
            "release_id": data.get("release_id"),
            "submission_id": data.get("submission_id"),
            "generated_at": data.get("generated_at"),
            "source_hash": data.get("source_hash"),
            "qa_source_hash": data.get("qa_source_hash"),
            "item_count": summary.get("item_count", 0),
            "file_count": summary.get("file_count", 0),
            "total_bytes": summary.get("total_bytes", 0),
            "zip_filename": zip_info.get("filename"),
            "zip_sha256": zip_info.get("sha256"),
            "zip_entry_count": zip_info.get("entry_count"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _submission_report_payload(submission: SubmissionBatch, qa_report: ImplementationDocument, now: str) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "schema_version": 1,
            "generated_at": now,
            "submission": submission.to_dict(),
            "summary": submission_batch_summary(submission),
            "qa_summary": _as_document(qa_report.get("summary")),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _write_readme(export_dir: Path, submission: SubmissionBatch, qa_report: ImplementationDocument, rows: list[ImplementationDocument]) -> None:
    lines = [
        f"MusicForge Submission Package: {sanitize_sensitive_text(submission.name)}",
        "",
        f"Submission ID: {submission.submission_id}",
        f"Release ID: {submission.release_id}",
        f"QA: {qa_report.get('status', 'missing')}",
        "",
        "Targets:",
    ]
    for row in rows:
        lines.append(f"- {row.get('target_id')} {sanitize_sensitive_text(str(row.get('target_name') or 'Distribution Target'))} ({row.get('profile_id')})")
    lines.extend(["", "This package was prepared locally. It does not contain platform credentials or upload tokens."])
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_rights_clearance_sidecars(store: SubmissionStore, release_id: str, export_dir: Path, records: list[ImplementationDocument]) -> ImplementationDocument:
    try:
        summary = RightsClearanceStore(store.release_store).export_package_summary(release_id, export_dir)
    except Exception:
        summary = {"status": "missing", "summary_path": "rights/summary.json"}
    target_path = export_dir / str(summary.get("summary_path") or "rights/summary.json")
    if target_path.exists():
        records.append(_file_record(export_dir, target_path))
    return sanitize_metadata(summary, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _write_targets_csv(path: Path, rows: list[ImplementationDocument]) -> None:
    headers = ["item_id", "target_id", "target_name", "profile_id", "package_id", "status", "zip_sha256", "verify_status", "external_reference"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _escape_csv_cell(str(row.get(key) or "")) for key in headers})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _escape_csv_cell(cell: str) -> str:
    text = str(cell or "")
    if text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"):
        return "'" + text
    return text


def _events_jsonl(events: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(sanitize_metadata(event, blocked_keys=DISTRIBUTION_BLOCKED_KEYS), ensure_ascii=False) + "\n" for event in events)


def _submission_signoff_export_summary(signoff: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "not_signed",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "forced": bool(signoff.get("forced", False)),
            "qa_source_hash": signoff.get("qa_source_hash"),
            "export_manifest_hash": signoff.get("export_manifest_hash"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _submission_signoff_sidecar_record(signoff_public: ImplementationDocument) -> ImplementationDocument:
    return {
        "path": "submission-signoff.json",
        "payload_hash": stable_hash(_submission_signoff_hash_payload(signoff_public)),
        "payload_hash_excludes": sorted(SUBMISSION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS),
    }


def _submission_signoff_hash_payload(signoff_public: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in signoff_public.items() if key not in SUBMISSION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


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
            raise SubmissionExportError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise SubmissionExportError("Unsafe relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise SubmissionExportError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SubmissionExportError("Refusing to operate outside submission export boundaries.") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
