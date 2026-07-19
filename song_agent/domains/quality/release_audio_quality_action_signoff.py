# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

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
from song_agent.domains.quality.v142_raqas_readiness import ReleaseAudioQualityActionQueueSignoffStoreReadinessMixin
from song_agent.domains.quality import v142_raqas_readiness as _v142_raqas_readiness
from song_agent.domains.quality.v142_raqas_evidence import ReleaseAudioQualityActionQueueSignoffStoreEvidenceMixin
from song_agent.domains.quality import v142_raqas_evidence as _v142_raqas_evidence



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


class ReleaseAudioQualityActionQueueSignoffStore(ReleaseAudioQualityActionQueueSignoffStoreReadinessMixin, ReleaseAudioQualityActionQueueSignoffStoreEvidenceMixin):
    def __init__(
        self,
        *,
        queue_store: ReleaseAudioQualityActionQueueStore | None = None,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.queue_store = queue_store or ReleaseAudioQualityActionQueueStore(release_store=self.release_store)
        self.lock = threading.RLock()































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
    rows: list[ImplementationDocument] = []
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

_v142_raqas_readiness.bind_globals(globals())
_v142_raqas_evidence.bind_globals(globals())
