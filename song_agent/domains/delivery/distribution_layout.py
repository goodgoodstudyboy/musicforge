# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any
import hashlib as hashlib
import json as json

from song_agent.domains.quality.audio_encoding import normalize_required_profiles as normalize_required_profiles
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_templates import DistributionTemplateError as DistributionTemplateError, template_file_naming as template_file_naming, template_summary as template_summary
from song_agent.domains.studio.projectio import slugify as slugify
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash as stable_hash


DISTRIBUTION_LAYOUT_SCHEMA_VERSION = 1
DISTRIBUTION_LAYOUT_COLLISION_STRATEGY = "append-index"

DEFAULT_FILE_NAMING = {
    "audio": "audio/{track_number:02d}-{slug_title}.{ext}",
    "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt",
    "artwork": "artwork/cover.{ext}",
}

RESERVED_LAYOUT_PATHS = {
    "distribution-manifest.json",
    "distribution-signoff.json",
    "package.json",
    "release.json",
    "tracklist.json",
    "README.txt",
    "template-pack.json",
    "template-summary.json",
    "docs/checklist.json",
    "docs/checklist.md",
    "docs/submission-notes.md",
    "release-metadata.json",
    "platform-metadata.csv",
    "template-platform-metadata.csv",
    "credits.csv",
    "layout/manifest-layout.json",
    "layout/file-tree.txt",
}

AUDIO_VARIABLES = {"track_number", "track_number:02d", "disc_number", "slug_title", "track_id", "isrc", "ext", "format", "profile_id", "codec", "bitrate_kbps"}
LYRICS_VARIABLES = AUDIO_VARIABLES | {"language"}
ARTWORK_VARIABLES = {"release_slug", "release_id", "upc", "profile_id", "target_id", "ext"}
KIND_VARIABLES = {"audio": AUDIO_VARIABLES, "lyrics": LYRICS_VARIABLES, "artwork": ARTWORK_VARIABLES}


def effective_file_naming(template: DomainDocument | None) -> dict[str, str]:
    naming = dict(DEFAULT_FILE_NAMING)
    naming.update(template_file_naming(template) if template else {})
    return normalize_file_naming(naming)


def normalize_file_naming(naming: dict[str, str]) -> dict[str, str]:
    return {
        "audio": _with_default_prefix(naming["audio"], "audio"),
        "lyrics": _with_default_prefix(naming["lyrics"], "lyrics"),
        "artwork": _with_default_prefix(naming["artwork"], "artwork"),
    }


def build_distribution_layout_plan(
    *,
    release_id: str,
    target: Any,
    release: Any | dict[str, Any],
    release_manifest: DomainDocument,
    release_metadata: DomainDocument | None = None,
    template: DomainDocument | None = None,
    artwork: DomainDocument | None = None,
    release_export_dir: Path | None = None,
    encoded_audio_summary: DomainDocument | None = None,
    encoded_audio_root: Path | None = None,
) -> DomainDocument:
    release_metadata = _as_document(release_metadata)
    release_info = _release_info(release, release_metadata)
    target_info = _target_info(target)
    naming_errors: list[ImplementationDocument] = []
    try:
        naming = effective_file_naming(template)
    except DistributionTemplateError as exc:
        raw = dict(DEFAULT_FILE_NAMING)
        raw.update(_as_document(template.get("file_naming")) if isinstance(template, dict) else {})
        naming = normalize_file_naming({key: str(raw.get(key) or DEFAULT_FILE_NAMING[key]) for key in DEFAULT_FILE_NAMING})
        naming_errors.append({"check_id": "file_naming_shape", "message": str(exc)})
    rules = _as_document(template.get("rules")) if isinstance(template, dict) else {}
    entries: list[ImplementationDocument] = []
    warnings: list[ImplementationDocument] = []
    errors: list[ImplementationDocument] = list(naming_errors)
    used_paths: dict[str, str] = {}
    metadata_by_id = _metadata_tracks_by_id(release_metadata)

    for kind, pattern in naming.items():
        errors.extend(_pattern_errors(kind, pattern))

    tracks = _as_list(release_manifest.get("tracks"))
    audio_profile_ids = _target_audio_profile_ids(target_info, _as_document(rules))
    for track in tracks:
        if not isinstance(track, dict):
            continue
        metadata_track = metadata_by_id.get(str(track.get("track_id") or ""))
        context = _track_context(track, metadata_track, release_info)
        for profile_id in audio_profile_ids:
            audio_rel, audio_ext, audio_source_kind, audio_format = _audio_source_rel(release_export_dir, track, target_info=target_info, encoded_audio_summary=encoded_audio_summary, encoded_audio_root=encoded_audio_root, profile_id=profile_id)
            audio_root = encoded_audio_root if audio_source_kind == "encoded_audio" else release_export_dir
            audio_exists = _source_exists(audio_root, audio_rel)
            audio_required = bool(_as_document(rules).get("require_audio")) or bool(target_info["options"].get("require_audio", False)) or bool(target_info["options"].get("require_encoded_audio", False)) or profile_id != "wav_master"
            if not (audio_exists or audio_required):
                continue
            entry = _entry(
                kind="audio",
                track=context,
                pattern=naming["audio"],
                source_rel=audio_rel,
                source_kind=audio_source_kind,
                ext=audio_ext,
                audio_format=audio_format,
                required=audio_required,
                exists=audio_exists,
                release_info=release_info,
                target_info=target_info,
            )
            _add_entry(entries, warnings, errors, used_paths, entry)

        lyrics_rel = _lyrics_source_rel(context)
        lyrics_exists = _source_exists(release_export_dir, lyrics_rel)
        has_lyrics = bool(str(context.get("lyrics") or "").strip())
        if lyrics_exists or has_lyrics or bool(_as_document(rules).get("require_lyrics")):
            entry = _entry(
                kind="lyrics",
                track=context,
                pattern=naming["lyrics"],
                source_rel=lyrics_rel,
                source_kind="release_export",
                ext="txt",
                audio_format={},
                required=bool(_as_document(rules).get("require_lyrics")),
                exists=lyrics_exists or (has_lyrics and release_export_dir is None),
                release_info=release_info,
                target_info=target_info,
            )
            _add_entry(entries, warnings, errors, used_paths, entry)

    artwork_exists = bool(artwork)
    if artwork_exists or bool(_as_document(rules).get("require_artwork")) or bool(target_info["options"].get("require_artwork", False)):
        suffix = Path(str((artwork or {}).get("stored_filename") or (artwork or {}).get("filename") or "cover.png")).suffix.lower().lstrip(".") or "png"
        entry = _entry(
            kind="artwork",
            track=None,
            pattern=naming["artwork"],
            source_rel=_artwork_source_rel(artwork),
            source_kind="artwork",
            ext=suffix,
            audio_format={},
            required=bool(_as_document(rules).get("require_artwork")) or bool(target_info["options"].get("require_artwork", False)),
            exists=artwork_exists,
            release_info=release_info,
            target_info=target_info,
        )
        _add_entry(entries, warnings, errors, used_paths, entry)

    for entry in entries:
        if entry.get("required") and not entry.get("exists"):
            errors.append(
                {
                    "entry_id": entry.get("entry_id"),
                    "check_id": f"layout_required_{entry.get('kind')}_present",
                    "message": f"Required {entry.get('kind')} source is missing.",
                }
            )
            entry["status"] = "missing"

    source_hash = stable_hash(
        {
            "release_id": release_id,
            "target": target_info,
            "release": release_info,
            "template": template_summary(template) if template else {},
            "naming": naming,
            "entries": [_entry_hash_payload(entry) for entry in entries],
            "errors": errors,
            "warnings": warnings,
        }
    )
    plan = {
        "schema_version": DISTRIBUTION_LAYOUT_SCHEMA_VERSION,
        "release_id": release_id,
        "target_id": target_info["target_id"],
        "template_pack_id": (template or {}).get("template_pack_id"),
        "template_hash": (template or {}).get("template_hash"),
        "source_hash": source_hash,
        "collision_strategy": DISTRIBUTION_LAYOUT_COLLISION_STRATEGY,
        "naming": naming,
        "entries": entries,
        "warnings": warnings,
        "errors": errors,
    }
    plan["layout_hash"] = stable_hash(_layout_hash_payload(plan))
    plan["summary"] = layout_summary(plan)
    return sanitize_metadata(plan, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def layout_summary(plan: DomainDocument | None) -> DomainDocument:
    data = _as_document(plan)
    entries = _as_list(data.get("entries"))
    warnings = _as_list(data.get("warnings"))
    errors = _as_list(data.get("errors"))
    return sanitize_metadata(
        {
            "status": "failed" if errors else "warning" if warnings else "passed",
            "entry_count": len(entries),
            "audio_count": sum(1 for entry in entries if isinstance(entry, dict) and entry.get("kind") == "audio"),
            "lyrics_count": sum(1 for entry in entries if isinstance(entry, dict) and entry.get("kind") == "lyrics"),
            "artwork_count": sum(1 for entry in entries if isinstance(entry, dict) and entry.get("kind") == "artwork"),
            "collision_count": sum(1 for entry in entries if isinstance(entry, dict) and entry.get("collision")),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "layout_hash": data.get("layout_hash"),
            "source_hash": data.get("source_hash"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def layout_manifest_payload(plan: DomainDocument, file_records: list[DomainDocument]) -> DomainDocument:
    by_path = {str(item.get("path") or ""): item for item in file_records if isinstance(item, dict)}
    entries: list[ImplementationDocument] = []
    for entry in plan.get("entries", []) if isinstance(plan.get("entries"), list) else []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        record = by_path.get(path, {})
        payload = {
            "entry_id": entry.get("entry_id"),
            "kind": entry.get("kind"),
            "track_id": entry.get("track_id"),
            "source_rel": entry.get("source_rel"),
            "source_kind": entry.get("source_kind"),
            "path": path,
            "pattern": entry.get("pattern"),
            "original_path": entry.get("original_path"),
            "collision": bool(entry.get("collision", False)),
            "collision_index": entry.get("collision_index"),
            "ext": entry.get("ext"),
            "audio_format": _as_document(entry.get("audio_format")),
            "required": bool(entry.get("required", False)),
            "exists": bool(entry.get("exists", False)),
            "status": entry.get("status") or "planned",
            "size_bytes": record.get("size_bytes"),
            "sha256": record.get("sha256"),
        }
        entries.append({key: value for key, value in payload.items() if value not in (None, "")})
    layout = {
        "schema_version": DISTRIBUTION_LAYOUT_SCHEMA_VERSION,
        "layout_hash": plan.get("layout_hash"),
        "source_hash": plan.get("source_hash"),
        "release_id": plan.get("release_id"),
        "target_id": plan.get("target_id"),
        "template_pack_id": plan.get("template_pack_id"),
        "template_hash": plan.get("template_hash"),
        "collision_strategy": plan.get("collision_strategy") or DISTRIBUTION_LAYOUT_COLLISION_STRATEGY,
        "naming": _as_document(plan.get("naming")),
        "entries": entries,
        "warnings": _as_list(plan.get("warnings")),
        "errors": _as_list(plan.get("errors")),
        "summary": _document_or(plan.get("summary"), layout_summary(plan)),
    }
    layout["payload_hash"] = layout_payload_hash(layout)
    return sanitize_metadata(layout, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def layout_payload_hash(layout: DomainDocument) -> str:
    payload = sanitize_metadata({key: value for key, value in layout.items() if key != "payload_hash"}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS - {"path"})
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def layout_file_tree_text(paths: list[str]) -> str:
    lines = ["Distribution Package Layout", ""]
    tree: ImplementationDocument = {}
    for path in sorted(paths):
        parts = [part for part in str(path).split("/") if part]
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def walk(node: DomainDocument, depth: int) -> None:
        for name, child in sorted(node.items()):
            suffix = "/" if child else ""
            lines.append("  " * depth + name + suffix)
            if child:
                walk(child, depth + 1)

    walk(tree, 0)
    return "\n".join(lines) + "\n"


def layout_check_items(plan: DomainDocument) -> list[DomainDocument]:
    summary = layout_summary(plan)
    errors = _as_list(plan.get("errors"))
    warnings = _as_list(plan.get("warnings"))
    return [
        _check("layout_plan_valid", summary.get("status") != "failed", "blocking", "Distribution layout plan is valid." if summary.get("status") != "failed" else "Distribution layout plan has blocking errors.", count=len(errors)),
        _check("template_file_naming_valid", not any(str(item.get("check_id") or "").startswith("file_naming_") for item in errors), "blocking", "Template file_naming variables are valid."),
        _check("layout_no_reserved_collision", not any(item.get("check_id") == "layout_reserved_collision" for item in errors), "blocking", "Layout does not target fixed sidecars."),
        _check("layout_no_unsafe_paths", not any(item.get("check_id") == "layout_unsafe_path" for item in errors), "blocking", "Layout paths are safe."),
        _check("layout_collision_resolved", not any(entry.get("collision") for entry in plan.get("entries", []) if isinstance(entry, dict)), "warning", "Layout rendered path collisions were resolved.", count=summary.get("collision_count", 0), warning_when_false=True),
        _check("layout_required_artwork_present", not any(item.get("check_id") == "layout_required_artwork_present" for item in errors), "blocking", "Required artwork layout entry is present."),
        _check("layout_required_audio_present", not any(item.get("check_id") == "layout_required_audio_present" for item in errors), "blocking", "Required audio layout entries are present."),
        _check("layout_warnings", not warnings, "warning", "Distribution layout has warnings.", count=len(warnings), warning_when_false=True),
    ]


def _entry(
    *,
    kind: str,
    track: ImplementationDocument | None,
    pattern: str,
    source_rel: str,
    source_kind: str,
    ext: str,
    audio_format: ImplementationDocument,
    required: bool,
    exists: bool,
    release_info: ImplementationDocument,
    target_info: ImplementationDocument,
) -> ImplementationDocument:
    track_id = str((track or {}).get("track_id") or "")
    profile_id = str(audio_format.get("profile_id") or "") if kind == "audio" and isinstance(audio_format, dict) else ""
    entry_id = f"{kind}:{track_id}" if track_id else f"{kind}:cover"
    if kind == "audio" and track_id and profile_id and profile_id != "wav_master":
        entry_id = f"{entry_id}:{profile_id}"
    try:
        path = _render_pattern(kind, pattern, track=track, release_info=release_info, target_info=target_info, ext=ext, audio_format=audio_format)
        status = "planned" if exists else "missing"
        error = None
    except ValueError as exc:
        path = ""
        status = "failed"
        error = str(exc)
    entry = {
        "entry_id": entry_id,
        "kind": kind,
        "track_id": track_id or None,
        "source_rel": source_rel,
        "source_kind": source_kind,
        "path": path,
        "pattern": pattern,
        "ext": ext,
        "audio_format": audio_format if kind == "audio" else {},
        "required": required,
        "exists": exists,
        "status": status,
    }
    if error:
        entry["error"] = error
    return sanitize_metadata(entry, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _add_entry(entries: list[ImplementationDocument], warnings: list[ImplementationDocument], errors: list[ImplementationDocument], used_paths: dict[str, str], entry: ImplementationDocument) -> None:
    if entry.get("error"):
        error_text = str(entry.get("error") or "")
        kind = str(entry.get("kind") or "entry")
        check_id = f"layout_{kind}_extension_mismatch" if "extension" in error_text.lower() else "layout_unsafe_path"
        errors.append({"entry_id": entry.get("entry_id"), "check_id": check_id, "message": entry.get("error")})
        entries.append(entry)
        return
    path = str(entry.get("path") or "")
    if path in RESERVED_LAYOUT_PATHS:
        errors.append({"entry_id": entry.get("entry_id"), "check_id": "layout_reserved_collision", "message": f"Layout path targets fixed sidecar: {path}."})
        entries.append(entry)
        return
    if path in used_paths:
        original = path
        index = 2
        while path in used_paths or path in RESERVED_LAYOUT_PATHS:
            path = _append_index(original, index)
            index += 1
        entry["original_path"] = original
        entry["path"] = path
        entry["collision"] = True
        entry["collision_index"] = index - 1
        warnings.append({"entry_id": entry.get("entry_id"), "check_id": "layout_collision_resolved", "message": f"Layout path collision resolved: {original} -> {path}."})
    used_paths[path] = str(entry.get("entry_id") or "")
    entries.append(entry)


def _render_pattern(kind: str, pattern: str, *, track: ImplementationDocument | None, release_info: ImplementationDocument, target_info: ImplementationDocument, ext: str, audio_format: ImplementationDocument | None = None) -> str:
    _ensure_variables_allowed(kind, pattern)
    audio_format = _as_document(audio_format)
    values: ImplementationDocument = {
        "ext": ext.strip(".").lower(),
        "format": _slug_value(audio_format.get("format"), ext.strip(".").lower() or "audio"),
        "profile_id": _slug_value(audio_format.get("profile_id") or target_info.get("profile_id"), "profile"),
        "codec": _slug_value(audio_format.get("codec"), "codec"),
        "bitrate_kbps": int(audio_format.get("bitrate_kbps") or 0),
        "release_slug": slugify(str(release_info.get("name") or release_info.get("release_id") or "release"))[:80],
        "release_id": _slug_value(release_info.get("release_id"), "release"),
        "upc": _slug_value(release_info.get("upc"), "upc"),
        "target_id": _slug_value(target_info.get("target_id"), "target"),
    }
    if track:
        values.update(
            {
                "track_number": int(track.get("track_number") or 1),
                "disc_number": int(track.get("disc_number") or 1),
                "slug_title": slugify(str(track.get("title") or track.get("track_id") or "track"))[:80],
                "track_id": _slug_value(track.get("track_id"), "track"),
                "isrc": _slug_value(track.get("isrc"), "isrc"),
                "language": _slug_value(track.get("language"), "language"),
            }
        )
    try:
        rendered = pattern.format(**values)
    except (KeyError, ValueError) as exc:
        raise ValueError("Distribution file naming pattern is invalid.") from exc
    path = validate_layout_path(rendered)
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    expected = ext.strip(".").lower()
    if path not in RESERVED_LAYOUT_PATHS and suffix != expected:
        raise ValueError(f"{kind} layout path extension must match source extension .{expected}.")
    return path


def validate_layout_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise ValueError("Layout path must use POSIX separators.")
    if not raw or raw.startswith("/") or raw.startswith("//") or raw.endswith("/"):
        raise ValueError("Layout path must be a relative file path.")
    if "://" in raw:
        raise ValueError("Layout path must not contain a URL.")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Layout path contains an unsafe path segment.")
    if any(":" in part for part in parts):
        raise ValueError("Layout path contains an unsafe ':' character.")
    return PurePosixPath(*parts).as_posix()


def _pattern_errors(kind: str, pattern: str) -> list[ImplementationDocument]:
    errors: list[ImplementationDocument] = []
    try:
        _ensure_variables_allowed(kind, pattern)
        validate_layout_path(_replace_pattern_vars(pattern))
    except ValueError as exc:
        errors.append({"check_id": f"file_naming_{kind}_variables", "kind": kind, "message": str(exc)})
    return errors


def _ensure_variables_allowed(kind: str, pattern: str) -> None:
    allowed = KIND_VARIABLES.get(kind, set())
    for variable in _pattern_variables(pattern):
        if variable not in allowed:
            raise ValueError(f"{kind} naming cannot use variable {{{variable}}}.")


def _pattern_variables(pattern: str) -> list[str]:
    import re

    return re.findall(r"\{([^{}]+)\}", str(pattern or ""))


def _replace_pattern_vars(pattern: str) -> str:
    import re

    return re.sub(r"\{[^{}]+\}", "x", str(pattern or ""))


def _append_index(path: str, index: int) -> str:
    posix = PurePosixPath(path)
    suffix = "".join(posix.suffixes)
    stem = posix.name[: -len(suffix)] if suffix else posix.name
    return str(posix.with_name(f"{stem}-{index}{suffix}"))


def _with_default_prefix(pattern: str, prefix: str) -> str:
    text = str(pattern or DEFAULT_FILE_NAMING[prefix])
    if "/" in text or text in RESERVED_LAYOUT_PATHS:
        return text
    return f"{prefix}/{text}"


def _release_info(release: Any | ImplementationDocument, metadata: ImplementationDocument) -> ImplementationDocument:
    meta_release = _as_document(metadata.get("release"))
    return {
        "release_id": _attr(release, "release_id") or (release.get("release_id") if isinstance(release, dict) else None),
        "name": _attr(release, "name") or (release.get("name") if isinstance(release, dict) else None) or meta_release.get("title"),
        "upc": meta_release.get("upc"),
        "language": meta_release.get("language") or _attr(release, "language") or (release.get("language") if isinstance(release, dict) else None),
    }


def _target_info(target: Any) -> ImplementationDocument:
    options = _attr(target, "options") if not isinstance(target, dict) else target.get("options")
    return {
        "target_id": _attr(target, "target_id") or (target.get("target_id") if isinstance(target, dict) else None),
        "profile_id": _attr(target, "profile_id") or (target.get("profile_id") if isinstance(target, dict) else None),
        "options": _as_document(options),
    }


def _metadata_tracks_by_id(metadata: ImplementationDocument) -> dict[str, ImplementationDocument]:
    tracks = _as_list(metadata.get("tracks"))
    return {str(item.get("track_id") or ""): item for item in tracks if isinstance(item, dict) and item.get("track_id")}


from song_agent.domains.delivery import v142_dl_readiness as _v142_dl_readiness
from song_agent.domains.delivery.v142_dl_readiness import _track_context as _track_context, _audio_source_rel as _audio_source_rel, _encoded_profile_summary as _encoded_profile_summary, _target_audio_profile_ids as _target_audio_profile_ids, _normalize_profile_ids as _normalize_profile_ids, _validate_profile_id as _validate_profile_id, _lyrics_source_rel as _lyrics_source_rel, _artwork_source_rel as _artwork_source_rel, _source_exists as _source_exists, _slug_value as _slug_value, _attr as _attr, _entry_hash_payload as _entry_hash_payload, _layout_hash_payload as _layout_hash_payload, _check as _check

_v142_dl_readiness.bind_globals(globals())
