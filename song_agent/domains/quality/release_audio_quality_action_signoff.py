from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_quality_actions import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, ReleaseAudioQualityActionQueueStore as ReleaseAudioQualityActionQueueStore
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE, verify_release_audio_quality_action_queue_signoff_archive_package as verify_release_audio_quality_action_queue_signoff_archive_package, write_release_audio_quality_action_queue_signoff_archive_verification_report as write_release_audio_quality_action_queue_signoff_archive_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_MANUAL_RESOLUTIONS_PACKAGE_TYPE = "release_audio_quality_action_queue_manual_resolutions"
RELEASE_AUDIO_QUALITY_ACTION_QUEUE_CLOSEOUT_PACKAGE_TYPE = "release_audio_quality_action_queue_closeout"
RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_PACKAGE_TYPE = "release_audio_quality_action_queue_signoff"

ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "action-queue.json",
    "source-binding.json",
    "action-items.json",
    "action-results.json",
    "manual-actions.json",
    "manual-resolutions.json",
    "queue-summary.json",
    "queue-verification-report.json",
    "closeout-report.json",
    "action-queue-signoff.json",
    "action-queue-signoff-history.jsonl",
}


class ReleaseAudioQualityActionQueueSignoffError(ValueError):
    pass


class ReleaseAudioQualityActionQueueSignoffNotFoundError(ReleaseAudioQualityActionQueueSignoffError):
    pass


class ReleaseAudioQualityActionQueueSignoffStateError(ReleaseAudioQualityActionQueueSignoffError):
    pass


class ReleaseAudioQualityActionQueueSignoffValidationError(ReleaseAudioQualityActionQueueSignoffError):
    pass


class ReleaseAudioQualityActionQueueSignoffStore:
    def __init__(
        self,
        *,
        queue_store: ReleaseAudioQualityActionQueueStore | None = None,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.queue_store = queue_store or ReleaseAudioQualityActionQueueStore(release_store=self.release_store)
        self.lock = threading.RLock()

    def manual_resolutions_path(self, queue_id: str) -> Path:
        return self.queue_store.queue_dir(queue_id) / "manual-resolutions.json"

    def closeout_path(self, queue_id: str) -> Path:
        return self.queue_store.queue_dir(queue_id) / "closeout-report.json"

    def signoff_path(self, queue_id: str) -> Path:
        return self.queue_store.signoff_path(queue_id)

    def history_path(self, queue_id: str) -> Path:
        return self.queue_store.signoff_history_path(queue_id)

    def archive_dir(self, queue_id: str) -> Path:
        return self.queue_store.queue_dir(queue_id) / "archive"

    def archive_zip_path(self, queue_id: str) -> Path:
        return self.queue_store.queue_dir(queue_id) / "release-audio-quality-action-queue-signoff-archive.zip"

    def archive_verification_report_path(self, queue_id: str) -> Path:
        return self.archive_dir(queue_id) / "verification-report.json"

    def list_manual_items(self, queue_id: str) -> dict[str, Any]:
        docs = self._queue_docs(queue_id)
        manual_ids = _manual_item_ids(docs["items"], docs["results"], docs["manual_actions"])
        items_by_id = {str(row.get("item_id")): row for row in docs["items"].get("items", []) if isinstance(row, dict)}
        manual_by_id = {str(row.get("item_id")): row for row in docs["manual_actions"].get("manual_actions", []) if isinstance(row, dict)}
        resolutions = self.read_manual_resolutions(queue_id, default=self._empty_resolutions(queue_id, docs))
        resolved_by_item = {str(row.get("item_id")): row for row in resolutions.get("resolutions", []) if isinstance(row, dict)}
        rows = []
        for item_id in sorted(manual_ids):
            item = items_by_id.get(item_id, {})
            rows.append(
                sanitize_metadata(
                    {
                        "item_id": item_id,
                        "manual_action": manual_by_id.get(item_id, {}),
                        "item": item,
                        "resolution": resolved_by_item.get(item_id),
                        "status": "resolved" if item_id in resolved_by_item else "manual_required",
                    }
                )
            )
        return {"queue_id": queue_id, "manual_items": rows, "summary": resolutions.get("summary", {})}

    def read_manual_resolutions(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.manual_resolutions_path(queue_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioQualityActionQueueSignoffNotFoundError(f"Manual resolutions not found for {queue_id}.")
        return read_json(path)

    def resolve_manual_item(self, queue_id: str, item_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(queue_id, "resolve manual item")
            docs = self._queue_docs(queue_id)
            item_id = str(item_id or payload.get("item_id") or "")
            manual_ids = _manual_item_ids(docs["items"], docs["results"], docs["manual_actions"])
            if item_id not in manual_ids:
                raise ReleaseAudioQualityActionQueueSignoffValidationError("Manual item does not exist or does not require manual resolution.")
            status = str(payload.get("status") or payload.get("resolution") or "completed").strip().lower()
            if status not in {"completed", "waived", "rejected", "deferred"}:
                raise ReleaseAudioQualityActionQueueSignoffValidationError("Manual resolution status must be completed, waived, rejected, or deferred.")
            reason = _bounded(payload.get("reason") or payload.get("notes"), 1000)
            if status in {"waived", "rejected", "deferred"} and len(reason) < 6:
                raise ReleaseAudioQualityActionQueueSignoffValidationError("Manual resolution reason is required.")
            resolutions = self.read_manual_resolutions(queue_id, default=self._empty_resolutions(queue_id, docs))
            existing = [row for row in resolutions.get("resolutions", []) if isinstance(row, dict) and str(row.get("item_id")) != item_id]
            manual_action = next((row for row in docs["manual_actions"].get("manual_actions", []) if isinstance(row, dict) and str(row.get("item_id")) == item_id), {})
            resolution = sanitize_metadata(
                {
                    "resolution_id": f"aqres-{len(existing) + 1:06d}",
                    "item_id": item_id,
                    "manual_action_id": manual_action.get("manual_action_id"),
                    "status": status,
                    "resolution_type": f"manual_{status}",
                    "resolved_by": _bounded(payload.get("resolved_by") or payload.get("reviewer") or payload.get("signed_by") or "local-user", 120),
                    "role": _bounded(payload.get("role") or "audio_quality_reviewer", 80),
                    "reason": reason or "Manual action completed.",
                    "evidence": sanitize_metadata(_as_document(payload.get("evidence"))),
                    "created_at": now_iso(),
                }
            )
            resolution["payload_hash"] = stable_hash({key: value for key, value in resolution.items() if key != "payload_hash"})
            resolutions["resolutions"] = sorted([*existing, resolution], key=lambda row: str(row.get("item_id") or ""))
            self._finalize_resolutions(resolutions, docs)
            write_json(self.manual_resolutions_path(queue_id), resolutions)
            return resolution

    def refresh_closeout(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(queue_id, "refresh closeout")
            docs = self._queue_docs(queue_id)
            if not self.queue_store.zip_path(queue_id).exists():
                self.queue_store.build_zip(queue_id)
            verification = self.queue_store.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=False)
            resolutions = self.read_manual_resolutions(queue_id, default=self._empty_resolutions(queue_id, docs))
            self._finalize_resolutions(resolutions, docs)
            write_json(self.manual_resolutions_path(queue_id), resolutions)
            closeout = self._build_closeout(queue_id, docs, resolutions, verification)
            write_json(self.closeout_path(queue_id), closeout)
            return closeout

    def read_closeout(self, queue_id: str) -> dict[str, Any]:
        if not self.closeout_path(queue_id).exists():
            raise ReleaseAudioQualityActionQueueSignoffNotFoundError(f"Closeout report not found for {queue_id}.")
        return read_json(self.closeout_path(queue_id))

    def signoff(self, queue_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(queue_id, "sign queue")
            closeout = self.refresh_closeout(queue_id)
            if closeout.get("status") != "passed":
                raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue closeout has blockers.")
            verification = read_json(self.queue_store.verification_report_path(queue_id))
            queue_zip = self.queue_store.zip_path(queue_id)
            signed_by = _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-quality-lead", 120)
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                    "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_PACKAGE_TYPE,
                    "queue_id": queue_id,
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": signed_by,
                    "role": _bounded(payload.get("role") or "audio_quality_lead", 80),
                    "reason": _bounded(payload.get("reason") or "Audio Quality Action Queue closeout accepted.", 1000),
                    "source": {
                        "closeout_hash": closeout.get("integrity_hash"),
                        "manual_resolutions_hash": closeout.get("source", {}).get("manual_resolutions_hash"),
                        "queue_verification_report_hash": verification.get("integrity_hash"),
                        "queue_zip_sha256": _sha256_path(queue_zip),
                        "queue_zip_size_bytes": queue_zip.stat().st_size if queue_zip.exists() else None,
                        "queue_manifest_hash": verification.get("manifest_hash"),
                        "queue_source_hash": closeout.get("source_hash"),
                    },
                    "summary": closeout.get("summary", {}),
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(queue_id), signoff)
            self._record_history_event(
                queue_id,
                "action_queue_signoff_created",
                {
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason_hash": stable_hash(signoff.get("reason")),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "closeout_hash": closeout.get("integrity_hash"),
                    "queue_verification_report_hash": verification.get("integrity_hash"),
                    "queue_zip_sha256": _sha256_path(queue_zip),
                    "queue_manifest_hash": verification.get("manifest_hash"),
                },
            )
            return {"status": "signed", "queue_id": queue_id, "signoff": signoff, "closeout": closeout}

    def export_archive(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._signed_source(queue_id)
            signoff_hash = str(source["signoff"].get("integrity_hash") or "")
            if self._history_has_event(queue_id, "action_queue_signoff_archive_exported", signoff_hash):
                raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff archive was already exported for this signoff.")
            archive_dir = self.archive_dir(queue_id)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            manifest = self._write_archive_dir(queue_id, source)
            self._record_history_event(queue_id, "action_queue_signoff_archive_exported", {"signoff_hash": signoff_hash, "manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "queue_id": queue_id, "archive_dir": str(archive_dir), "manifest": manifest}

    def build_archive_zip(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._signed_source(queue_id)
            signoff_hash = str(source["signoff"].get("integrity_hash") or "")
            if self._history_has_event(queue_id, "action_queue_signoff_archive_zip_built", signoff_hash):
                raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff archive ZIP was already built for this signoff.")
            if not (self.archive_dir(queue_id) / "manifest.json").exists():
                if self._history_has_event(queue_id, "action_queue_signoff_archive_exported", signoff_hash):
                    raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff archive was already exported for this signoff.")
                archive_dir = self.archive_dir(queue_id)
                if archive_dir.exists():
                    shutil.rmtree(archive_dir)
                archive_dir.mkdir(parents=True, exist_ok=True)
                self._write_archive_dir(queue_id, source)
                self._record_history_event(queue_id, "action_queue_signoff_archive_exported", {"signoff_hash": signoff_hash, "manifest_hash": read_json(archive_dir / "manifest.json").get("integrity_hash")})
            archive_dir = self.archive_dir(queue_id)
            zip_path = self.archive_zip_path(queue_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(archive_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(archive_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            self._record_history_event(queue_id, "action_queue_signoff_archive_zip_built", {"signoff_hash": signoff_hash, "archive_zip_sha256": final_sha, "manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "queue_id": queue_id, "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_archive(self, queue_id: str, **kwargs: Any) -> dict[str, Any]:
        with self.lock:
            report = verify_release_audio_quality_action_queue_signoff_archive_package(
                self.archive_zip_path(queue_id),
                queue_zip_path=kwargs.get("queue_zip_path") or self.queue_store.zip_path(queue_id),
                queue_verification_report_path=kwargs.get("queue_verification_report_path") or self.queue_store.verification_report_path(queue_id),
                observatory_zip_path=kwargs.get("observatory_zip_path") or self.queue_store._observatory_zip_from_queue(queue_id),
                observatory_verification_report_path=kwargs.get("observatory_verification_report_path") or self.queue_store._observatory_verification_from_queue(queue_id),
                evidence_root=kwargs.get("evidence_root") or self.release_store.root,
                strict=bool(kwargs.get("strict", True)),
                require_signed=bool(kwargs.get("require_signed", True)),
                require_current_queue=bool(kwargs.get("require_current_queue", True)),
                require_no_unresolved_manual=bool(kwargs.get("require_no_unresolved_manual", True)),
            )
            write_release_audio_quality_action_queue_signoff_archive_verification_report(report, self.archive_verification_report_path(queue_id))
            return report

    def gate(
        self,
        release_id: str,
        *,
        queue_id: str | None = None,
        required: bool,
        archive_zip_path: Path | str | None = None,
        archive_verification_report_path: Path | str | None = None,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            queue_id = queue_id or self._latest_queue_id()
            if not queue_id:
                return _gate_failed("Release Audio Quality Action Queue signoff archive is missing.")
            archive_zip = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(queue_id)
            verification_path = Path(archive_verification_report_path) if archive_verification_report_path else self.archive_verification_report_path(queue_id)
            if not archive_zip.exists():
                return _gate_failed("Release Audio Quality Action Queue signoff archive ZIP is missing.")
            if not verification_path.exists():
                return _gate_failed("Release Audio Quality Action Queue signoff archive verification report is missing.")
            verification = read_json(verification_path)
            runtime = verify_release_audio_quality_action_queue_signoff_archive_package(
                archive_zip,
                strict=True,
                require_signed=True,
                require_current_queue=True,
                queue_zip_path=self.queue_store.zip_path(queue_id),
                queue_verification_report_path=self.queue_store.verification_report_path(queue_id),
                observatory_zip_path=self.queue_store._observatory_zip_from_queue(queue_id),
                observatory_verification_report_path=self.queue_store._observatory_verification_from_queue(queue_id),
                evidence_root=self.release_store.root,
                require_no_unresolved_manual=True,
            )
            summary = _as_document(runtime.get("summary"))
            release_ids = {str(item) for item in summary.get("release_ids", []) if str(item)}
            if release_id not in release_ids:
                return _gate_failed("Release Audio Quality Action Queue signoff archive does not cover this Release.", verification=runtime)
            if verification.get("integrity_hash") != _integrity_hash(verification):
                return _gate_failed("Release Audio Quality Action Queue signoff archive verification integrity failed.", verification=verification)
            if verification.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Release Audio Quality Action Queue signoff archive verification failed.", verification=runtime)
            if verification.get("zip_sha256") != _sha256_path(archive_zip) or verification.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Release Audio Quality Action Queue signoff archive verification does not match current ZIP.", verification=runtime)
            return {
                "status": "passed",
                "hard_block": False,
                "message": "Release Audio Quality Action Queue signoff gate passed.",
                "queue_id": queue_id,
                "archive_zip_sha256": runtime.get("zip_sha256"),
                "archive_verification_hash": verification.get("integrity_hash"),
                "summary": summary,
            }
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _queue_docs(self, queue_id: str) -> dict[str, ImplementationDocument]:
        return {
            "queue": read_json(self.queue_store.queue_path(queue_id)),
            "source_binding": read_json(self.queue_store.source_binding_path(queue_id)),
            "items": read_json(self.queue_store.action_items_path(queue_id)),
            "results": read_json(self.queue_store.action_results_path(queue_id)),
            "manual_actions": read_json(self.queue_store.manual_actions_path(queue_id)),
            "summary": read_json(self.queue_store.summary_path(queue_id)),
        }

    def _write_archive_dir(self, queue_id: str, source: ImplementationDocument) -> ImplementationDocument:
        archive_dir = self.archive_dir(queue_id)
        files: list[dict[str, Any]] = []

        def write_entry(rel: str, payload: dict[str, Any] | list[dict[str, Any]] | str) -> None:
            path = archive_dir / rel
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            elif rel.endswith(".jsonl"):
                path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in payload) + ("\n" if payload else ""), encoding="utf-8")
            else:
                write_json(path, payload)
            files.append(_file_record(path, rel))

        write_entry("action-queue.json", source["queue"])
        write_entry("source-binding.json", source["source_binding"])
        write_entry("action-items.json", source["items"])
        write_entry("action-results.json", source["results"])
        write_entry("manual-actions.json", source["manual_actions"])
        write_entry("manual-resolutions.json", source["manual_resolutions"])
        write_entry("queue-summary.json", source["summary"])
        public_queue_verification = _public_queue_verification_report(source["queue_verification"])
        write_entry("queue-verification-report.json", public_queue_verification)
        write_entry("closeout-report.json", source["closeout"])
        write_entry("action-queue-signoff.json", source["signoff"])
        write_entry("action-queue-signoff-history.jsonl", source["history"])
        write_entry("README.txt", _archive_readme(source["signoff"], source["closeout"]))
        latest_hash = source["history"][-1].get("event_hash") if source["history"] else None
        manifest = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
                "queue_id": queue_id,
                "generated_at": now_iso(),
                "source_hash": source["closeout"].get("source_hash"),
                "queue_zip_sha256": source["signoff"].get("source", {}).get("queue_zip_sha256"),
                "queue_manifest_hash": source["signoff"].get("source", {}).get("queue_manifest_hash"),
                "closeout_hash": source["closeout"].get("integrity_hash"),
                "signoff_hash": source["signoff"].get("integrity_hash"),
                "queue_verification_report_hash": source["queue_verification"].get("integrity_hash"),
                "embedded_queue_verification_report_hash": public_queue_verification.get("integrity_hash"),
                "history_latest_event_hash": latest_hash,
                "files": sorted(files, key=lambda row: row["path"]),
                "zip": {},
            }
        )
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(archive_dir / "manifest.json", manifest)
        return manifest

    def _empty_resolutions(self, queue_id: str, docs: dict[str, ImplementationDocument]) -> ImplementationDocument:
        manual_count = len(_manual_item_ids(docs["items"], docs["results"], docs["manual_actions"]))
        doc: _InferenceType = {
            "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
            "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_MANUAL_RESOLUTIONS_PACKAGE_TYPE,
            "queue_id": queue_id,
            "source_hash": docs["source_binding"].get("source_hash"),
            "queue_integrity_hash": docs["queue"].get("integrity_hash"),
            "items_hash": docs["items"].get("integrity_hash"),
            "manual_actions_hash": docs["manual_actions"].get("integrity_hash"),
            "resolutions": [],
            "summary": {"manual_required_count": manual_count, "resolved_count": 0, "waived_count": 0, "rejected_count": 0, "deferred_count": 0, "unresolved_count": manual_count},
        }
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _finalize_resolutions(self, resolutions: ImplementationDocument, docs: dict[str, ImplementationDocument]) -> None:
        manual_ids = _manual_item_ids(docs["items"], docs["results"], docs["manual_actions"])
        rows = [row for row in resolutions.get("resolutions", []) if isinstance(row, dict) and str(row.get("item_id")) in manual_ids]
        resolved_ids = {str(row.get("item_id")) for row in rows}
        resolutions["source_hash"] = docs["source_binding"].get("source_hash")
        resolutions["queue_integrity_hash"] = docs["queue"].get("integrity_hash")
        resolutions["items_hash"] = docs["items"].get("integrity_hash")
        resolutions["manual_actions_hash"] = docs["manual_actions"].get("integrity_hash")
        resolutions["resolutions"] = sorted(rows, key=lambda row: str(row.get("item_id") or ""))
        resolutions["summary"] = {
            "manual_required_count": len(manual_ids),
            "resolved_count": len(resolved_ids),
            "waived_count": sum(1 for row in rows if row.get("status") == "waived"),
            "rejected_count": sum(1 for row in rows if row.get("status") == "rejected"),
            "deferred_count": sum(1 for row in rows if row.get("status") == "deferred"),
            "unresolved_count": len(manual_ids - resolved_ids),
        }
        resolutions["integrity_hash"] = _integrity_hash(resolutions)

    def _build_closeout(self, queue_id: str, docs: dict[str, ImplementationDocument], resolutions: ImplementationDocument, verification: ImplementationDocument) -> ImplementationDocument:
        manual_ids = _manual_item_ids(docs["items"], docs["results"], docs["manual_actions"])
        resolved = {str(row.get("item_id")): row for row in resolutions.get("resolutions", []) if isinstance(row, dict)}
        result_rows = [row for row in docs["results"].get("results", []) if isinstance(row, dict)]
        item_rows = [row for row in docs["items"].get("items", []) if isinstance(row, dict)]
        summary_doc = _as_document(docs["summary"].get("summary"))
        checks: list[dict[str, Any]] = []

        def add(check_id: str, passed: bool, message: str, severity: str = "blocking", details: dict[str, Any] | None = None) -> None:
            checks.append({"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}})

        unresolved = sorted(manual_ids - set(resolved))
        rejected = sorted(item_id for item_id, row in resolved.items() if row.get("status") == "rejected")
        deferred = sorted(item_id for item_id, row in resolved.items() if row.get("status") == "deferred")
        waived = sorted(item_id for item_id, row in resolved.items() if row.get("status") == "waived")
        critical_ids = {str(row.get("item_id")) for row in item_rows if row.get("severity") in {"critical", "blocking"}}
        critical_waived = sorted(set(waived) & critical_ids)
        blocked = sum(1 for row in result_rows if row.get("status") == "blocked")
        failed = sum(1 for row in result_rows if row.get("status") == "failed")
        pending = max(0, len(item_rows) - len(result_rows))
        critical_unhandled = _safe_int(summary_doc.get("critical_unhandled_count"))
        add("queue_verification_passed", verification.get("status") == "passed", "Queue verification passed.")
        add("queue_no_failed_or_blocked_actions", blocked == 0 and failed == 0, "Queue has no failed or blocked actions.", details={"blocked": blocked, "failed": failed})
        add("queue_no_pending_actions", pending == 0, "Queue has no pending actions.", details={"pending": pending})
        add("manual_items_resolved", not unresolved, "All manual items have resolutions.", details={"unresolved": unresolved})
        add("manual_no_rejected", not rejected, "No manual resolution was rejected.", details={"rejected": rejected})
        add("manual_no_deferred", not deferred, "No manual resolution was deferred.", details={"deferred": deferred})
        add("manual_no_critical_waiver", not critical_waived, "Critical/blocking manual items are not waived.", details={"critical_waived": critical_waived})
        add("queue_no_critical_unhandled", critical_unhandled == 0, "Queue has no unhandled critical items.", details={"critical_unhandled": critical_unhandled})
        blockers = [check for check in checks if check["status"] == "failed" and check["severity"] == "blocking"]
        closeout = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_CLOSEOUT_PACKAGE_TYPE,
                "queue_id": queue_id,
                "status": "failed" if blockers else "passed",
                "readiness": "blocked" if blockers else "ready_for_signoff",
                "source_hash": docs["source_binding"].get("source_hash"),
                "source": {
                    "queue_integrity_hash": docs["queue"].get("integrity_hash"),
                    "source_binding_hash": docs["source_binding"].get("integrity_hash"),
                    "items_hash": docs["items"].get("integrity_hash"),
                    "results_hash": docs["results"].get("integrity_hash"),
                    "manual_actions_hash": docs["manual_actions"].get("integrity_hash"),
                    "manual_resolutions_hash": resolutions.get("integrity_hash"),
                    "queue_summary_hash": docs["summary"].get("integrity_hash"),
                    "queue_verification_report_hash": verification.get("integrity_hash"),
                    "queue_zip_sha256": verification.get("zip_sha256"),
                    "queue_manifest_hash": verification.get("manifest_hash"),
                },
                "summary": {
                    "item_count": len(item_rows),
                    "completed_count": sum(1 for row in result_rows if row.get("status") == "completed"),
                    "manual_required_count": len(manual_ids),
                    "manual_resolved_count": len(set(resolved) & manual_ids),
                    "manual_unresolved_count": len(unresolved),
                    "waived_count": len(waived),
                    "rejected_count": len(rejected),
                    "deferred_count": len(deferred),
                    "blocked_count": blocked,
                    "failed_count": failed,
                    "pending_count": pending,
                    "critical_unhandled_count": critical_unhandled,
                    "release_ids": summary_doc.get("release_ids") or [],
                },
                "checks": checks,
                "warnings": [],
                "created_at": now_iso(),
            }
        )
        closeout["integrity_hash"] = _integrity_hash(closeout)
        return closeout

    def _signed_source(self, queue_id: str) -> ImplementationDocument:
        if not self.signoff_path(queue_id).exists():
            if self._has_effective_signoff(queue_id):
                raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff file is missing but history is signed.")
            raise ReleaseAudioQualityActionQueueSignoffNotFoundError("Audio Quality Action Queue signoff is missing.")
        docs = self._queue_docs(queue_id)
        closeout = read_json(self.closeout_path(queue_id))
        signoff = read_json(self.signoff_path(queue_id))
        resolutions = read_json(self.manual_resolutions_path(queue_id))
        verification = read_json(self.queue_store.verification_report_path(queue_id))
        history = _read_jsonl(self.history_path(queue_id))
        if not self._history_chain_ok(history):
            raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff history integrity failed.")
        if signoff.get("integrity_hash") != _integrity_hash(signoff):
            raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff integrity failed.")
        if closeout.get("integrity_hash") != _integrity_hash(closeout) or closeout.get("status") != "passed":
            raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue closeout is not passed.")
        signoff_event = next(
            (
                row
                for row in reversed(history)
                if row.get("event_type") == "action_queue_signoff_created"
                and isinstance(row.get("payload"), dict)
                and row.get("payload", {}).get("signoff_hash") == signoff.get("integrity_hash")
            ),
            {},
        )
        if not signoff_event:
            raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff history does not bind current signoff.")
        signoff_payload = _as_document(signoff_event.get("payload"))
        if signoff_payload.get("signoff_payload_hash") != signoff.get("payload_hash"):
            raise ReleaseAudioQualityActionQueueSignoffStateError("Audio Quality Action Queue signoff payload history does not match current signoff.")
        bindings = {
            "closeout_hash": closeout.get("integrity_hash"),
            "manual_resolutions_hash": resolutions.get("integrity_hash"),
            "queue_verification_report_hash": verification.get("integrity_hash"),
            "queue_zip_sha256": _sha256_path(self.queue_store.zip_path(queue_id)),
            "queue_zip_size_bytes": self.queue_store.zip_path(queue_id).stat().st_size if self.queue_store.zip_path(queue_id).exists() else None,
            "queue_manifest_hash": verification.get("manifest_hash"),
        }
        source = _as_document(signoff.get("source"))
        for key, value in bindings.items():
            if source.get(key) != value:
                raise ReleaseAudioQualityActionQueueSignoffStateError(f"Audio Quality Action Queue signoff binding mismatch: {key}.")
        return {**docs, "manual_resolutions": resolutions, "closeout": closeout, "signoff": signoff, "queue_verification": verification, "history": history}

    def _record_history_event(self, queue_id: str, event_type: str, payload: ImplementationDocument) -> ImplementationDocument:
        chain = HistoryChain(self.history_path(queue_id), sanitizer=sanitize_metadata, hash_mode="payload")
        rows = chain.read()
        return chain.append(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "event_id": f"aqsig-event-{len(rows) + 1:06d}",
                "event_type": event_type,
                "queue_id": queue_id,
                "created_at": now_iso(),
                "payload": payload,
            }
        )

    def _history_chain_ok(self, rows: list[ImplementationDocument]) -> bool:
        previous = None
        for row in rows:
            payload = _as_document(row.get("payload"))
            if row.get("previous_event_hash") != previous:
                return False
            if row.get("payload_hash") != stable_hash(payload):
                return False
            if row.get("event_hash") != stable_hash({key: value for key, value in row.items() if key != "event_hash"}):
                return False
            previous = str(row.get("event_hash") or "")
        return bool(rows)

    def _has_effective_signoff(self, queue_id: str) -> bool:
        if self.signoff_path(queue_id).exists():
            return True
        rows = _read_jsonl(self.history_path(queue_id))
        return bool(rows and self._history_chain_ok(rows) and any(row.get("event_type") == "action_queue_signoff_created" for row in rows))

    def _ensure_unsigned(self, queue_id: str, action: str) -> None:
        if self._has_effective_signoff(queue_id):
            raise ReleaseAudioQualityActionQueueSignoffStateError(f"Audio Quality Action Queue is signed. Reset signoff before attempting to {action}.")

    def _history_has_event(self, queue_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(row.get("event_type") == event_type and (row.get("payload") or {}).get("signoff_hash") == signoff_hash for row in _read_jsonl(self.history_path(queue_id)))

    def _latest_queue_id(self) -> str | None:
        rows = []
        for queue_path in self.queue_store.queues_dir().glob("*/action-queue.json"):
            try:
                queue = read_json(queue_path)
            except Exception:
                continue
            rows.append((str(queue.get("created_at") or ""), str(queue.get("queue_id") or queue_path.parent.name)))
        if not rows:
            return None
        return sorted(rows)[-1][1]


def _manual_item_ids(items: ImplementationDocument, results: ImplementationDocument, manual_actions: ImplementationDocument) -> set[str]:
    ids = {str(row.get("item_id")) for row in manual_actions.get("manual_actions", []) if isinstance(row, dict) and row.get("item_id")}
    ids.update(str(row.get("item_id")) for row in results.get("results", []) if isinstance(row, dict) and row.get("status") == "manual_required" and row.get("item_id"))
    ids.update(str(row.get("item_id")) for row in items.get("items", []) if isinstance(row, dict) and (row.get("execution_mode") == "manual_required" or row.get("requires_manual")) and row.get("item_id"))
    return ids


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _archive_readme(signoff: ImplementationDocument, closeout: ImplementationDocument) -> str:
    return "\n".join(
        [
            "MusicForge Release Audio Quality Action Queue Signoff Archive",
            f"queue_id: {signoff.get('queue_id')}",
            f"status: {signoff.get('status')}",
            f"closeout_status: {closeout.get('status')}",
            "",
            "This archive records manual resolution, closeout, and signoff evidence for an Audio Quality Action Queue.",
            "It does not contain audio files, local workspace paths, provider credentials, or external upload secrets.",
            "",
        ]
    )


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _public_queue_verification_report(report: ImplementationDocument) -> ImplementationDocument:
    public = {
        key: value
        for key, value in report.items()
        if key not in {"summary", "checks", "integrity_hash"}
    }
    summary = _as_document(report.get("summary"))
    public["summary"] = {key: value for key, value in summary.items() if key != "zip_path"}
    public["original_integrity_hash"] = report.get("integrity_hash")
    public["integrity_hash"] = _integrity_hash(public)
    return sanitize_metadata(public)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}
