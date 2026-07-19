# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list
import hashlib as hashlib
import json as json
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore, CreativeAsset as CreativeAsset, asset_content_summary as asset_content_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.reference_analysis import get_analysis_report as get_analysis_report, get_slice_manifest as get_slice_manifest
from song_agent.domains.studio.references import ReferenceItem as ReferenceItem, ReferenceStore as ReferenceStore, reference_metadata_summary as reference_metadata_summary

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

LibraryItem = _make_deferred_global('LibraryItem')
item_tag = _make_deferred_global('item_tag')

def bind_globals(namespace: dict[str, object]) -> None:
    global LibraryItem, item_tag
    LibraryItem = namespace.get('LibraryItem', LibraryItem)
    item_tag = namespace.get('item_tag', item_tag)
    _bind_deferred_defaults(namespace)


LIBRARY_INDEX_SCHEMA_VERSION = 1
MAX_LIBRARY_TOKENS = 200
MAX_LIBRARY_TOKEN_LENGTH = 40
MAX_LIBRARY_RESULTS = 100




def tokenize_library_text(text: object) -> list[str]:
    clean = sanitize_sensitive_text(str(text or "")).lower()
    tokens: list[str] = []
    for token in re.split(r"[\s,.;:!?()\[\]{}<>\"'`|/\\+=*&^%$#@~，。！？、；：（）【】《》]+", clean):
        token = token.strip("-_")
        if 0 < len(token) <= MAX_LIBRARY_TOKEN_LENGTH:
            tokens.append(token)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", clean)
    for run in chinese_runs:
        if len(run) <= MAX_LIBRARY_TOKEN_LENGTH:
            tokens.append(run)
        for index in range(0, max(0, len(run) - 1)):
            tokens.append(run[index : index + 2])
    phrase = clean.strip()
    if 0 < len(phrase) <= MAX_LIBRARY_TOKEN_LENGTH and " " in phrase:
        tokens.append(phrase)
    deduped = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= MAX_LIBRARY_TOKENS:
            break
    return deduped

def asset_roles(asset_type: str) -> list[str]:
    return {
        "motif": ["melody", "hook"],
        "bass_pattern": ["bass"],
        "drum_pattern": ["drums"],
        "chord_progression": ["harmony"],
        "lyric_hook": ["lyrics", "hook"],
        "section_template": ["structure"],
        "arrangement_template": ["arrangement"],
    }.get(asset_type, [])

def reference_roles(reference_type: str) -> list[str]:
    return {
        "midi": ["melody", "harmony", "arrangement"],
        "lyrics_text": ["lyrics", "hook"],
        "style_note": ["style", "arrangement"],
        "audio_wav": ["reference", "audio"],
    }.get(reference_type, ["reference"])

def _matches_filters(item: LibraryItem, request: DomainDocument) -> bool:
    item_kinds = _string_set(request.get("item_kinds"))
    if item_kinds and item.item_kind not in item_kinds:
        return False
    asset_types = _string_set(request.get("asset_types"))
    if asset_types and item.item_kind == "asset" and item.item_type not in asset_types:
        return False
    reference_types = _string_set(request.get("reference_types"))
    if reference_types and item.item_kind == "reference" and item.item_type not in reference_types:
        return False
    roles = _string_set(request.get("roles"))
    if roles and not roles.intersection(_string_set(item.features.get("roles"))):
        return False
    tag = str(request.get("tag") or "").strip().lower()
    if tag and tag not in {item_tag.lower() for item_tag in item.tags}:
        return False
    if bool(request.get("favorite_only", False)) and not item.favorite:
        return False
    return True

def _type_role_points(item: LibraryItem, request: DomainDocument) -> tuple[int, list[DomainDocument]]:
    points = 0
    breakdown = []
    requested_types = _string_set(request.get("asset_types") if item.item_kind == "asset" else request.get("reference_types"))
    if requested_types and item.item_type in requested_types:
        points += 8
        breakdown.append(_reason("type_match", 8, item.item_type))
    requested_roles = _string_set(request.get("roles"))
    item_roles = _string_set(item.features.get("roles"))
    matched_roles = sorted(requested_roles & item_roles)
    if matched_roles:
        role_points = min(12, 6 * len(matched_roles))
        points += role_points
        breakdown.append(_reason("role_match", role_points, ", ".join(matched_roles)))
    return min(20, points), breakdown

def _style_mood_points(item: LibraryItem, request: DomainDocument) -> tuple[int, list[DomainDocument]]:
    points = 0
    breakdown = []
    for field_name, max_points in (("style", 8), ("mood", 7)):
        wanted = tokenize_library_text(request.get(field_name))
        actual = set(tokenize_library_text(getattr(item, field_name)))
        matched = sorted(set(wanted) & actual)
        if matched:
            points += max_points
            breakdown.append(_reason(f"{field}_match", max_points, ", ".join(matched)))
    return min(15, points), breakdown

def _musical_points(item: LibraryItem, request: DomainDocument) -> tuple[int, list[DomainDocument]]:
    points = 0
    breakdown = []
    tempo = _optional_int(request.get("tempo_bpm"))
    if tempo and item.tempo_bpm:
        delta = abs(tempo - item.tempo_bpm)
        tempo_points = 8 if delta <= 3 else 6 if delta <= 8 else 3 if delta <= 16 else 0
        if tempo_points:
            points += tempo_points
            breakdown.append(_reason("tempo_close", tempo_points, f"{item.tempo_bpm} vs {tempo}"))
    key = str(request.get("key") or "").strip().lower()
    if key and item.key and _normalize_key(key) == _normalize_key(item.key):
        points += 5
        breakdown.append(_reason("key_match", 5, item.key))
    meter = str(request.get("meter") or "").strip()
    if meter and item.meter and meter == item.meter:
        points += 2
        breakdown.append(_reason("meter_match", 2, meter))
    return min(15, points), breakdown

def _utility_points(item: LibraryItem) -> tuple[int, list[DomainDocument]]:
    points = 0
    breakdown = []
    if item.quality_score is not None:
        quality_points = min(6, max(0, int(item.quality_score) // 15))
        points += quality_points
        breakdown.append(_reason("quality_score", quality_points, str(item.quality_score)))
    if item.favorite:
        points += 2
        breakdown.append(_reason("favorite", 2, "favorite"))
    if item.usage_count:
        usage_points = min(2, item.usage_count)
        points += usage_points
        breakdown.append(_reason("usage_count", usage_points, str(item.usage_count)))
    return min(10, points), breakdown

def _reason(reason: str, points: int, detail: str) -> DomainDocument:
    return {"reason": reason, "points": int(points), "detail": sanitize_sensitive_text(detail)}

def _safe_query_summary(request: DomainDocument) -> DomainDocument:
    allowed = {"query", "item_kinds", "asset_types", "reference_types", "roles", "style", "mood", "key", "tempo_bpm", "meter", "limit"}
    return sanitize_metadata({key: request.get(key) for key in allowed if key in request})

def _has_search_constraints(request: DomainDocument) -> bool:
    return any(request.get(key) for key in ("query", "item_kinds", "asset_types", "reference_types", "roles", "style", "mood", "key", "tempo_bpm", "meter", "tag", "favorite_only"))

def _role_for_result(result: DomainDocument) -> str:
    roles = result.get("features", {}).get("roles") if isinstance(result.get("features"), dict) else []
    if isinstance(roles, list) and roles:
        return str(roles[0])
    return "reference" if result.get("item_kind") == "reference" else "asset"

def _roles_for_goal(goal: str, text: str) -> list[str]:
    clean = text.lower()
    roles = ["hook", "melody", "harmony"] if goal in {"generate", "variation"} else []
    if any(token in clean for token in ("chorus", "hook", "副歌")):
        roles.extend(["hook", "melody", "lyrics"])
    if any(token in clean for token in ("bass", "低音")):
        roles.append("bass")
    if any(token in clean for token in ("drum", "beat", "鼓")):
        roles.append("drums")
    if any(token in clean for token in ("chord", "harmony", "和弦")):
        roles.append("harmony")
    if any(token in clean for token in ("arrangement", "编曲")):
        roles.append("arrangement")
    return sorted(set(roles or ["reference"]))

def _density_hint(note_count: int, duration_beats: float) -> str:
    density = note_count / max(1.0, duration_beats)
    if density >= 2.5:
        return "dense"
    if density >= 0.75:
        return "medium"
    return "sparse"

def _source_summary(source: DomainDocument) -> DomainDocument:
    return sanitize_metadata({key: source.get(key) for key in ("source_type", "project_id", "version_id", "job_id", "reference_id", "slice_id", "candidate_group_id", "candidate_id") if source.get(key)})

def _source_origin(source: DomainDocument) -> DomainDocument:
    return {
        "project_id": source.get("project_id"),
        "version_id": source.get("version_id"),
        "candidate_group_id": source.get("candidate_group_id"),
    }

def _roles_from_analysis(summary: DomainDocument) -> list[str]:
    roles = []
    for track in summary.get("track_summaries", []) if isinstance(summary.get("track_summaries"), list) else []:
        if isinstance(track, dict) and track.get("likely_role"):
            roles.append(str(track["likely_role"]))
    return roles

def _reference_analysis_features(reference_type: str, summary: DomainDocument) -> DomainDocument:
    features: DomainDocument = {}
    if reference_type == "audio_wav":
        features.update(
            {
                "duration_seconds": summary.get("duration_seconds"),
                "sample_rate": summary.get("sample_rate"),
                "channels": summary.get("channels"),
            }
        )
    elif reference_type == "midi":
        track_summaries = _as_list(summary.get("track_summaries"))
        note_counts = [int(track.get("note_count") or 0) for track in track_summaries if isinstance(track, dict)]
        pitch_values = [
            int(track[key])
            for track in track_summaries
            if isinstance(track, dict)
            for key in ("pitch_min", "pitch_max")
            if isinstance(track.get(key), int)
        ]
        features.update(
            {
                "track_count": summary.get("track_count"),
                "note_count": sum(note_counts),
                "pitch_min": min(pitch_values) if pitch_values else None,
                "pitch_max": max(pitch_values) if pitch_values else None,
            }
        )
    else:
        features.update(
            {
                "line_count": summary.get("line_count"),
                "keyword_hints": summary.get("keywords", [])[:20] if isinstance(summary.get("keywords"), list) else [],
            }
        )
    return features

def _compact_analysis_for_index(summary: DomainDocument) -> DomainDocument:
    compact: DomainDocument = {
        key: summary.get(key)
        for key in ("duration_seconds", "sample_rate", "channels", "track_count", "tempo_bpm", "meter", "line_count", "keywords", "safe_excerpt")
        if key in summary
    }
    if isinstance(summary.get("track_summaries"), list):
        compact["track_summaries"] = [
            {
                "track_index": track.get("track_index"),
                "likely_role": track.get("likely_role"),
                "note_count": track.get("note_count"),
                "pitch_min": track.get("pitch_min"),
                "pitch_max": track.get("pitch_max"),
            }
            for track in summary["track_summaries"][:8]
            if isinstance(track, dict)
        ]
    return compact

def _tempo_from_analysis(summary: DomainDocument) -> int | None:
    for key in ("tempo_bpm", "manual_tempo_bpm"):
        value = _optional_int(summary.get(key))
        if value:
            return value
    tempos = summary.get("tempos")
    if isinstance(tempos, list) and tempos:
        first = tempos[0]
        if isinstance(first, dict):
            return _optional_int(first.get("bpm"))
    return None

def _normalize_key(value: str) -> str:
    return value.lower().replace("major", "").replace("minor", "m").replace(" ", "")

def _string_set(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()

def _clean_string_list(value: object) -> list[str]:
    return sorted(_string_set(value))

def _optional_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None

def _optional_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _limit(value: object) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 20
    return max(1, min(limit, MAX_LIBRARY_RESULTS))
