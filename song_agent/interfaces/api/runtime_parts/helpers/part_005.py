from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.part_001 import Any, Path, datetime, hashlib, re, read_release_export_manifest, threading, timezone

from song_agent.interfaces.api.runtime_parts.dependencies.part_005 import SongRequest

from song_agent.interfaces.api.runtime_parts.core import VARIATION_REQUEST_FIELDS

def _generation_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("generation_mode", "local") or "local")
    if mode not in {"local", "provider"}:
        raise ValueError("generation_mode must be either local or provider.")
    return mode

def _pipeline_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("pipeline_mode", "single") or "single")
    if mode not in {"single", "multinode"}:
        raise ValueError("pipeline_mode must be either single or multinode.")
    return mode

def _variation_request_payload(
    parent_request: dict[str, Any],
    request_patch: dict[str, Any],
    *,
    generation_mode: Any = None,
    pipeline_mode: Any = None,
) -> dict[str, Any]:
    unknown = sorted(set(request_patch) - VARIATION_REQUEST_FIELDS)
    if unknown:
        raise ValueError(f"request_patch contains unsupported fields: {', '.join(unknown)}.")
    payload = {key: value for key, value in parent_request.items() if key in VARIATION_REQUEST_FIELDS}
    payload.update(request_patch)
    if generation_mode is not None:
        payload["generation_mode"] = generation_mode
    if pipeline_mode is not None:
        payload["pipeline_mode"] = pipeline_mode
    SongRequest.from_dict(payload)
    _generation_mode(payload)
    _pipeline_mode(payload)
    return payload

def _project_matches_filters(
    document: Any,
    *,
    q: str,
    status: str,
    variant_type: str,
    hidden: str,
) -> bool:
    if hidden == "true" and not document.state.hidden:
        return False
    if hidden == "false" and document.state.hidden:
        return False
    if status:
        if status == "selected" and not document.state.selected_version_id:
            return False
        elif status == "final" and not document.state.final_version_id:
            return False
        elif status == "gate_failed" and not any(version.quality_gate_status == "failed" for version in document.versions):
            return False
        elif status not in {"selected", "final", "gate_failed"} and document.state.status != status:
            return False
    if variant_type and not any(version.variant_type == variant_type for version in document.versions):
        return False
    if q:
        needle = q.lower()
        haystack = " ".join(
            [
                document.state.name,
                document.state.description,
                " ".join(document.state.tags),
                *[version.name for version in document.versions],
                *[version.note for version in document.versions],
            ]
        ).lower()
        if needle not in haystack:
            return False
    return True

def _rfc5987_quote(value: str) -> str:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$&+-.^_`|~"
    return "".join(char if char in allowed else f"%{byte:02X}" for char in value for byte in char.encode("utf-8"))

def _safe_download_filename(filename: str) -> str:
    name = Path(str(filename or "download")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    cleaned = cleaned.strip(" ._")
    if not cleaned:
        cleaned = "download"
    if len(cleaned) > 120:
        suffix = Path(cleaned).suffix[:16]
        stem = Path(cleaned).stem[: max(1, 120 - len(suffix))]
        cleaned = f"{stem}{suffix}"
    return cleaned

def _content_disposition_filename(filename: str) -> str:
    ascii_name = _safe_download_filename(filename)
    utf8_name = "".join(char for char in str(filename) if ord(char) >= 32 and char not in {'"', "\r", "\n"})
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{_rfc5987_quote(utf8_name)}"

def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _server_file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_read_release_export_manifest(release_store: ReleaseStore, release_id: str) -> dict[str, Any]:
    try:
        return read_release_export_manifest(release_store, release_id)
    except FileNotFoundError:
        return {}

def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    return [str(item).strip() for item in value if str(item).strip()]

def _clean_title(value: Any) -> str:
    return str(value or "").strip()

def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

def _start_watchdog(store: JobStore, stop_event: threading.Event) -> threading.Thread:
    def run() -> None:
        while not stop_event.wait(5):
            store.run_watchdog_tick()

    thread = threading.Thread(target=run, name="musicforge-watchdog", daemon=True)
    thread.start()
    return thread

__all__ = ['_clean_title', '_content_disposition_filename', '_dict_or_empty', '_generation_mode', '_parse_iso_datetime', '_pipeline_mode', '_project_matches_filters', '_rfc5987_quote', '_safe_download_filename', '_safe_read_release_export_manifest', '_server_file_sha256', '_start_watchdog', '_string_list', '_variation_request_payload']
