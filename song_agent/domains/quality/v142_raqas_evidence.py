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
_integrity_hash = _make_deferred_global('_integrity_hash')
_manual_item_ids = _make_deferred_global('_manual_item_ids')
_read_jsonl = _make_deferred_global('_read_jsonl')
_safe_int = _make_deferred_global('_safe_int')
_sha256_path = _make_deferred_global('_sha256_path')
check = _make_deferred_global('check')
item_id = _make_deferred_global('item_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseAudioQualityActionQueueSignoffNotFoundError, ReleaseAudioQualityActionQueueSignoffStateError, _integrity_hash, _manual_item_ids, _read_jsonl, _safe_int, _sha256_path
    global check, item_id
    ReleaseAudioQualityActionQueueSignoffNotFoundError = namespace.get('ReleaseAudioQualityActionQueueSignoffNotFoundError', ReleaseAudioQualityActionQueueSignoffNotFoundError)
    ReleaseAudioQualityActionQueueSignoffStateError = namespace.get('ReleaseAudioQualityActionQueueSignoffStateError', ReleaseAudioQualityActionQueueSignoffStateError)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _manual_item_ids = namespace.get('_manual_item_ids', _manual_item_ids)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _safe_int = namespace.get('_safe_int', _safe_int)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    check = namespace.get('check', check)
    item_id = namespace.get('item_id', item_id)
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




class ReleaseAudioQualityActionQueueSignoffStoreEvidenceMixin:
    def _build_closeout(self, queue_id: str, docs: dict[str, DomainDocument], resolutions: DomainDocument, verification: DomainDocument) -> DomainDocument:
        manual_ids = _manual_item_ids(docs["items"], docs["results"], docs["manual_actions"])
        resolved = {str(row.get("item_id")): row for row in resolutions.get("resolutions", []) if isinstance(row, dict)}
        result_rows = [row for row in docs["results"].get("results", []) if isinstance(row, dict)]
        item_rows = [row for row in docs["items"].get("items", []) if isinstance(row, dict)]
        summary_doc = _as_document(docs["summary"].get("summary"))
        checks: list[DomainDocument] = []

        def add(check_id: str, passed: bool, message: str, severity: str = "blocking", details: DomainDocument | None = None) -> None:
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

    def _signed_source(self, queue_id: str) -> DomainDocument:
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

    def _record_history_event(self, queue_id: str, event_type: str, payload: DomainDocument) -> DomainDocument:
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

    def _history_chain_ok(self, rows: list[DomainDocument]) -> bool:
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
