from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json

from song_agent.audio_encoding import normalize_required_profiles
from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS
from song_agent.distribution_templates import DistributionTemplateError, template_file_naming, template_summary
from song_agent.projectio import slugify
from song_agent.redaction import sanitize_metadata
from song_agent.releases import stable_hash


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


def effective_file_naming(template: dict[str, Any] | None) -> dict[str, str]:
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
    release_manifest: dict[str, Any],
    release_metadata: dict[str, Any] | None = None,
    template: dict[str, Any] | None = None,
    artwork: dict[str, Any] | None = None,
    release_export_dir: Path | None = None,
    encoded_audio_summary: dict[str, Any] | None = None,
    encoded_audio_root: Path | None = None,
) -> dict[str, Any]:
    release_metadata = release_metadata if isinstance(release_metadata, dict) else {}
    release_info = _release_info(release, release_metadata)
    target_info = _target_info(target)
    naming_errors: list[dict[str, Any]] = []
    try:
        naming = effective_file_naming(template)
    except DistributionTemplateError as exc:
        raw = dict(DEFAULT_FILE_NAMING)
        raw.update(template.get("file_naming") if isinstance(template, dict) and isinstance(template.get("file_naming"), dict) else {})
        naming = normalize_file_naming({key: str(raw.get(key) or DEFAULT_FILE_NAMING[key]) for key in DEFAULT_FILE_NAMING})
        naming_errors.append({"check_id": "file_naming_shape", "message": str(exc)})
    rules = template.get("rules") if isinstance(template, dict) and isinstance(template.get("rules"), dict) else {}
    entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = list(naming_errors)
    used_paths: dict[str, str] = {}
    metadata_by_id = _metadata_tracks_by_id(release_metadata)

    for kind, pattern in naming.items():
        errors.extend(_pattern_errors(kind, pattern))

    tracks = release_manifest.get("tracks") if isinstance(release_manifest.get("tracks"), list) else []
    audio_profile_ids = _target_audio_profile_ids(target_info, rules)
    for track in tracks:
        if not isinstance(track, dict):
            continue
        metadata_track = metadata_by_id.get(str(track.get("track_id") or ""))
        context = _track_context(track, metadata_track, release_info)
        for profile_id in audio_profile_ids:
            audio_rel, audio_ext, audio_source_kind, audio_format = _audio_source_rel(release_export_dir, track, target_info=target_info, encoded_audio_summary=encoded_audio_summary, encoded_audio_root=encoded_audio_root, profile_id=profile_id)
            audio_root = encoded_audio_root if audio_source_kind == "encoded_audio" else release_export_dir
            audio_exists = _source_exists(audio_root, audio_rel)
            audio_required = bool(rules.get("require_audio")) or bool(target_info["options"].get("require_audio", False)) or bool(target_info["options"].get("require_encoded_audio", False)) or profile_id != "wav_master"
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
        if lyrics_exists or has_lyrics or bool(rules.get("require_lyrics")):
            entry = _entry(
                kind="lyrics",
                track=context,
                pattern=naming["lyrics"],
                source_rel=lyrics_rel,
                source_kind="release_export",
                ext="txt",
                audio_format={},
                required=bool(rules.get("require_lyrics")),
                exists=lyrics_exists or (has_lyrics and release_export_dir is None),
                release_info=release_info,
                target_info=target_info,
            )
            _add_entry(entries, warnings, errors, used_paths, entry)

    artwork_exists = bool(artwork)
    if artwork_exists or bool(rules.get("require_artwork")) or bool(target_info["options"].get("require_artwork", False)):
        suffix = Path(str((artwork or {}).get("stored_filename") or (artwork or {}).get("filename") or "cover.png")).suffix.lower().lstrip(".") or "png"
        entry = _entry(
            kind="artwork",
            track=None,
            pattern=naming["artwork"],
            source_rel=_artwork_source_rel(artwork),
            source_kind="artwork",
            ext=suffix,
            audio_format={},
            required=bool(rules.get("require_artwork")) or bool(target_info["options"].get("require_artwork", False)),
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


def layout_summary(plan: dict[str, Any] | None) -> dict[str, Any]:
    data = plan if isinstance(plan, dict) else {}
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
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


def layout_manifest_payload(plan: dict[str, Any], file_records: list[dict[str, Any]]) -> dict[str, Any]:
    by_path = {str(item.get("path") or ""): item for item in file_records if isinstance(item, dict)}
    entries: list[dict[str, Any]] = []
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
            "audio_format": entry.get("audio_format") if isinstance(entry.get("audio_format"), dict) else {},
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
        "naming": plan.get("naming") if isinstance(plan.get("naming"), dict) else {},
        "entries": entries,
        "warnings": plan.get("warnings") if isinstance(plan.get("warnings"), list) else [],
        "errors": plan.get("errors") if isinstance(plan.get("errors"), list) else [],
        "summary": plan.get("summary") if isinstance(plan.get("summary"), dict) else layout_summary(plan),
    }
    layout["payload_hash"] = layout_payload_hash(layout)
    return sanitize_metadata(layout, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def layout_payload_hash(layout: dict[str, Any]) -> str:
    payload = sanitize_metadata({key: value for key, value in layout.items() if key != "payload_hash"}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS - {"path"})
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def layout_file_tree_text(paths: list[str]) -> str:
    lines = ["Distribution Package Layout", ""]
    tree: dict[str, Any] = {}
    for path in sorted(paths):
        parts = [part for part in str(path).split("/") if part]
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def walk(node: dict[str, Any], depth: int) -> None:
        for name, child in sorted(node.items()):
            suffix = "/" if child else ""
            lines.append("  " * depth + name + suffix)
            if child:
                walk(child, depth + 1)

    walk(tree, 0)
    return "\n".join(lines) + "\n"


def layout_check_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    summary = layout_summary(plan)
    errors = plan.get("errors") if isinstance(plan.get("errors"), list) else []
    warnings = plan.get("warnings") if isinstance(plan.get("warnings"), list) else []
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
    track: dict[str, Any] | None,
    pattern: str,
    source_rel: str,
    source_kind: str,
    ext: str,
    audio_format: dict[str, Any],
    required: bool,
    exists: bool,
    release_info: dict[str, Any],
    target_info: dict[str, Any],
) -> dict[str, Any]:
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


def _add_entry(entries: list[dict[str, Any]], warnings: list[dict[str, Any]], errors: list[dict[str, Any]], used_paths: dict[str, str], entry: dict[str, Any]) -> None:
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


def _render_pattern(kind: str, pattern: str, *, track: dict[str, Any] | None, release_info: dict[str, Any], target_info: dict[str, Any], ext: str, audio_format: dict[str, Any] | None = None) -> str:
    _ensure_variables_allowed(kind, pattern)
    audio_format = audio_format if isinstance(audio_format, dict) else {}
    values: dict[str, Any] = {
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


def _pattern_errors(kind: str, pattern: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
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


def _release_info(release: Any | dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    meta_release = metadata.get("release") if isinstance(metadata.get("release"), dict) else {}
    return {
        "release_id": _attr(release, "release_id") or (release.get("release_id") if isinstance(release, dict) else None),
        "name": _attr(release, "name") or (release.get("name") if isinstance(release, dict) else None) or meta_release.get("title"),
        "upc": meta_release.get("upc"),
        "language": meta_release.get("language") or _attr(release, "language") or (release.get("language") if isinstance(release, dict) else None),
    }


def _target_info(target: Any) -> dict[str, Any]:
    options = _attr(target, "options") if not isinstance(target, dict) else target.get("options")
    return {
        "target_id": _attr(target, "target_id") or (target.get("target_id") if isinstance(target, dict) else None),
        "profile_id": _attr(target, "profile_id") or (target.get("profile_id") if isinstance(target, dict) else None),
        "options": options if isinstance(options, dict) else {},
    }


def _metadata_tracks_by_id(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tracks = metadata.get("tracks") if isinstance(metadata.get("tracks"), list) else []
    return {str(item.get("track_id") or ""): item for item in tracks if isinstance(item, dict) and item.get("track_id")}


def _track_context(track: dict[str, Any], metadata: dict[str, Any] | None, release_info: dict[str, Any]) -> dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else {}
    merged = {**track, **{key: value for key, value in metadata.items() if value not in (None, "", [])}}
    merged["language"] = merged.get("language") or release_info.get("language")
    return merged


def _audio_source_rel(root: Path | None, track: dict[str, Any], *, target_info: dict[str, Any], encoded_audio_summary: dict[str, Any] | None, encoded_audio_root: Path | None, profile_id: str) -> tuple[str, str, str, dict[str, Any]]:
    profile_id = _validate_profile_id(profile_id or "wav_master")
    if profile_id != "wav_master":
        profile = _encoded_profile_summary(encoded_audio_summary, profile_id)
        ext = str(profile.get("extension") or "").strip(".").lower()
        if ext:
            track_id = str(track.get("track_id") or "")
            rel = validate_layout_path(f"formats/{profile_id}/tracks/{track_id}/song.{ext}")
            return rel, ext, "encoded_audio", profile
    directory = str(track.get("directory") or "").strip("/")
    candidates = [f"{directory}/song.wav" if directory else "song.wav", f"{directory}/song.mid" if directory else "song.mid"]
    for rel in candidates:
        if _source_exists(root, rel):
            return validate_layout_path(rel), Path(rel).suffix.lower().lstrip(".") or "wav", "release_export", {"profile_id": "wav_master", "format": "wav", "extension": "wav", "codec": "pcm_s16le"}
    fallback = candidates[0]
    return validate_layout_path(fallback), Path(fallback).suffix.lower().lstrip(".") or "wav", "release_export", {"profile_id": "wav_master", "format": "wav", "extension": "wav", "codec": "pcm_s16le"}


def _encoded_profile_summary(summary: dict[str, Any] | None, profile_id: str) -> dict[str, Any]:
    profiles = summary.get("profiles") if isinstance(summary, dict) and isinstance(summary.get("profiles"), list) else []
    for row in profiles:
        if isinstance(row, dict) and row.get("profile_id") == profile_id:
            return row
    return {"profile_id": profile_id, "format": profile_id.split("_", 1)[0], "extension": profile_id.split("_", 1)[0], "codec": ""}


def _target_audio_profile_ids(target_info: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    options = target_info.get("options") if isinstance(target_info.get("options"), dict) else {}
    profiles = _normalize_profile_ids(options.get("audio_format_profiles"))
    if not profiles:
        profiles = _normalize_profile_ids(rules.get("required_audio_formats"))
    if not profiles:
        profiles = _normalize_profile_ids(options.get("primary_audio_format") or rules.get("primary_audio_format"))
    return profiles or ["wav_master"]


def _normalize_profile_ids(value: Any) -> list[str]:
    return normalize_required_profiles(value)


def _validate_profile_id(value: str) -> str:
    return normalize_required_profiles([value])[0]


def _lyrics_source_rel(track: dict[str, Any]) -> str:
    title = slugify(str(track.get("title") or track.get("track_id") or "track"))[:60]
    return validate_layout_path(f"lyrics/{int(track.get('track_number') or 1):02d}-{title}.txt")


def _artwork_source_rel(artwork: dict[str, Any] | None) -> str:
    if not artwork:
        return "distribution-artwork/missing"
    return validate_layout_path(f"distribution-artwork/{_slug_value(artwork.get('artwork_id') or artwork.get('stored_filename'), 'cover')}")


def _source_exists(root: Path | None, rel: str) -> bool:
    if root is None:
        return False
    try:
        path = (root / validate_layout_path(rel)).resolve()
        path.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return path.exists() and path.is_file() and not path.is_symlink()


def _slug_value(value: Any, default: str) -> str:
    return slugify(str(value or default))[:80] or default


def _attr(value: Any, name: str) -> Any:
    return getattr(value, name, None)


def _entry_hash_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: entry.get(key) for key in ("entry_id", "kind", "track_id", "source_rel", "source_kind", "path", "pattern", "ext", "audio_format", "required", "exists", "status", "collision", "original_path", "collision_index")}


def _layout_hash_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"layout_hash", "summary"}
    }


def _check(check_id: str, passed: bool, severity: str, message: str, *, count: int | None = None, warning_when_false: bool = False) -> dict[str, Any]:
    status = "passed" if passed else "warning" if warning_when_false else "failed"
    item: dict[str, Any] = {"scope": "layout", "check_id": check_id, "status": status, "severity": severity, "message": message}
    if count is not None:
        item["count"] = count
    return sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
