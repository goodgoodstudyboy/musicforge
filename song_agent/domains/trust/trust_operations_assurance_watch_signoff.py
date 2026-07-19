# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore as TrustOperationsAssuranceWatchStore
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore as TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_assurance_watch_signoff_contracts import ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES as ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE, watch_signoff_hash as watch_signoff_hash, watch_signoff_history_event_hash as watch_signoff_history_event_hash, watch_signoff_history_event_payload_hash as watch_signoff_history_event_payload_hash, watch_signoff_manifest_hash as watch_signoff_manifest_hash
from song_agent.domains.trust.v142_toaws_readiness import TrustOperationsAssuranceWatchSignoffStoreReadinessMixin
from song_agent.domains.trust import v142_toaws_readiness as _v142_toaws_readiness
from song_agent.domains.trust.v142_toaws_evidence import TrustOperationsAssuranceWatchSignoffStoreEvidenceMixin
from song_agent.domains.trust import v142_toaws_evidence as _v142_toaws_evidence








TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_change_request"








class TrustOperationsAssuranceWatchSignoffError(ValueError):
    pass


class TrustOperationsAssuranceWatchSignoffNotFoundError(TrustOperationsAssuranceWatchSignoffError):
    pass


class TrustOperationsAssuranceWatchSignoffStateError(TrustOperationsAssuranceWatchSignoffError):
    pass


class TrustOperationsAssuranceWatchSignoffStore(TrustOperationsAssuranceWatchSignoffStoreReadinessMixin, TrustOperationsAssuranceWatchSignoffStoreEvidenceMixin):
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations" / "assurance-watch-signoffs",
        *,
        watch_store: TrustOperationsAssuranceWatchStore | None = None,
        assurance_store: TrustOperationsAssuranceStore | None = None,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.assurance_store = assurance_store or TrustOperationsAssuranceStore(hub_store=self.hub_store)
        self.watch_store = watch_store or TrustOperationsAssuranceWatchStore(hub_store=self.hub_store, assurance_store=self.assurance_store)
        self.lock = threading.RLock()





















































def _history_hash(events: list[ImplementationDocument]) -> str:
    return stable_hash({"events": events})


def _blocker(code: str, message: str) -> ImplementationDocument:
    item = {"code": code, "message": message, "severity": "blocking"}
    item["integrity_hash"] = stable_hash(item)
    return item


def _read_json_required(path: Path, message: str) -> ImplementationDocument:
    if not path.exists():
        raise TrustOperationsAssuranceWatchSignoffStateError(message)
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchSignoffStateError(message) from exc


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path:
        raise TrustOperationsAssuranceWatchSignoffStateError(f"Required ZIP entry is missing or invalid: {entry}")
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchSignoffStateError(f"Required ZIP entry is missing or invalid: {entry}") from exc


def _read_json_default(path: Path, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        if not path or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "MusicForge Trust Operations Assurance Watch Signoff Archive\n"
        "This package contains signed local continuous assurance watch closeout evidence.\n",
        encoding="utf-8",
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_hash(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
    if value:
        return str(value)
    return None


def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes: list[int] = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value

_v142_toaws_readiness.bind_globals(globals())
_v142_toaws_evidence.bind_globals(globals())
