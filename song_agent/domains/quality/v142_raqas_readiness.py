# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_quality_actions import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, ReleaseAudioQualityActionQueueStore as ReleaseAudioQualityActionQueueStore
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE, verify_release_audio_quality_action_queue_signoff_archive_package as verify_release_audio_quality_action_queue_signoff_archive_package, write_release_audio_quality_action_queue_signoff_archive_verification_report as write_release_audio_quality_action_queue_signoff_archive_verification_report
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

ReleaseAudioQualityActionQueueSignoffNotFoundError = _make_deferred_global('ReleaseAudioQualityActionQueueSignoffNotFoundError')
ReleaseAudioQualityActionQueueSignoffStateError = _make_deferred_global('ReleaseAudioQualityActionQueueSignoffStateError')
ReleaseAudioQualityActionQueueSignoffValidationError = _make_deferred_global('ReleaseAudioQualityActionQueueSignoffValidationError')
_archive_readme = _make_deferred_global('_archive_readme')
_bounded = _make_deferred_global('_bounded')
_file_record = _make_deferred_global('_file_record')
_gate_failed = _make_deferred_global('_gate_failed')
_integrity_hash = _make_deferred_global('_integrity_hash')
_manual_item_ids = _make_deferred_global('_manual_item_ids')
_public_queue_verification_report = _make_deferred_global('_public_queue_verification_report')
_sha256_path = _make_deferred_global('_sha256_path')
info = _make_deferred_global('info')
key = _make_deferred_global('key')
row = _make_deferred_global('row')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseAudioQualityActionQueueSignoffNotFoundError, ReleaseAudioQualityActionQueueSignoffStateError, ReleaseAudioQualityActionQueueSignoffValidationError, _archive_readme, _bounded, _file_record, _gate_failed, _integrity_hash
    global _manual_item_ids, _public_queue_verification_report, _sha256_path, info, key, row, value
    ReleaseAudioQualityActionQueueSignoffNotFoundError = namespace.get('ReleaseAudioQualityActionQueueSignoffNotFoundError', ReleaseAudioQualityActionQueueSignoffNotFoundError)
    ReleaseAudioQualityActionQueueSignoffStateError = namespace.get('ReleaseAudioQualityActionQueueSignoffStateError', ReleaseAudioQualityActionQueueSignoffStateError)
    ReleaseAudioQualityActionQueueSignoffValidationError = namespace.get('ReleaseAudioQualityActionQueueSignoffValidationError', ReleaseAudioQualityActionQueueSignoffValidationError)
    _archive_readme = namespace.get('_archive_readme', _archive_readme)
    _bounded = namespace.get('_bounded', _bounded)
    _file_record = namespace.get('_file_record', _file_record)
    _gate_failed = namespace.get('_gate_failed', _gate_failed)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _manual_item_ids = namespace.get('_manual_item_ids', _manual_item_ids)
    _public_queue_verification_report = namespace.get('_public_queue_verification_report', _public_queue_verification_report)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    info = namespace.get('info', info)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


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




class ReleaseAudioQualityActionQueueSignoffStoreReadinessMixin:
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

    def list_manual_items(self, queue_id: str) -> DomainDocument:
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

    def read_manual_resolutions(self, queue_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.manual_resolutions_path(queue_id)
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseAudioQualityActionQueueSignoffNotFoundError(f"Manual resolutions not found for {queue_id}.")
        return read_json(path)

    def resolve_manual_item(self, queue_id: str, item_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def refresh_closeout(self, queue_id: str) -> DomainDocument:
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

    def read_closeout(self, queue_id: str) -> DomainDocument:
        if not self.closeout_path(queue_id).exists():
            raise ReleaseAudioQualityActionQueueSignoffNotFoundError(f"Closeout report not found for {queue_id}.")
        return read_json(self.closeout_path(queue_id))

    def signoff(self, queue_id: str, payload: DomainDocument | None = None) -> DomainDocument:
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

    def export_archive(self, queue_id: str) -> DomainDocument:
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

    def build_archive_zip(self, queue_id: str) -> DomainDocument:
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

    def verify_archive(self, queue_id: str, **kwargs: object) -> DomainDocument:
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
    ) -> DomainDocument:
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

    def _queue_docs(self, queue_id: str) -> dict[str, DomainDocument]:
        return {
            "queue": read_json(self.queue_store.queue_path(queue_id)),
            "source_binding": read_json(self.queue_store.source_binding_path(queue_id)),
            "items": read_json(self.queue_store.action_items_path(queue_id)),
            "results": read_json(self.queue_store.action_results_path(queue_id)),
            "manual_actions": read_json(self.queue_store.manual_actions_path(queue_id)),
            "summary": read_json(self.queue_store.summary_path(queue_id)),
        }

    def _write_archive_dir(self, queue_id: str, source: DomainDocument) -> DomainDocument:
        archive_dir = self.archive_dir(queue_id)
        files: list[DomainDocument] = []

        def write_entry(rel: str, payload: DomainDocument | list[DomainDocument] | str) -> None:
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

    def _empty_resolutions(self, queue_id: str, docs: dict[str, DomainDocument]) -> DomainDocument:
        manual_count = len(_manual_item_ids(docs["items"], docs["results"], docs["manual_actions"]))
        doc: object = {
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

    def _finalize_resolutions(self, resolutions: DomainDocument, docs: dict[str, DomainDocument]) -> None:
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
