from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.assets import AssetStore, CreativeAsset, asset_content_summary
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.reference_analysis import get_analysis_report, get_slice_manifest
from song_agent.references import ReferenceItem, ReferenceStore, reference_metadata_summary


LIBRARY_ROOT = Path(".musicforge") / "library"
LIBRARY_INDEX_SCHEMA_VERSION = 1
MAX_LIBRARY_TOKENS = 200
MAX_LIBRARY_TOKEN_LENGTH = 40
MAX_LIBRARY_RESULTS = 100


@dataclass(frozen=True)
class LibraryItem:
    schema_version: int
    item_id: str
    item_kind: str
    source_id: str
    source_hash: str
    title: str
    item_type: str
    tags: list[str] = field(default_factory=list)
    style: str = ""
    mood: str = ""
    key: str = ""
    tempo_bpm: int | None = None
    meter: str = ""
    duration_beats: float | None = None
    quality_score: int | None = None
    favorite: bool = False
    hidden: bool = False
    usage_count: int = 0
    updated_at: str = ""
    features: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    origin: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LibraryItem":
        return cls(
            schema_version=int(data.get("schema_version", LIBRARY_INDEX_SCHEMA_VERSION) or LIBRARY_INDEX_SCHEMA_VERSION),
            item_id=str(data.get("item_id") or ""),
            item_kind=str(data.get("item_kind") or ""),
            source_id=str(data.get("source_id") or ""),
            source_hash=str(data.get("source_hash") or ""),
            title=sanitize_sensitive_text(str(data.get("title") or "")),
            item_type=str(data.get("item_type") or ""),
            tags=_clean_string_list(data.get("tags")),
            style=sanitize_sensitive_text(str(data.get("style") or "")),
            mood=sanitize_sensitive_text(str(data.get("mood") or "")),
            key=sanitize_sensitive_text(str(data.get("key") or "")),
            tempo_bpm=_optional_int(data.get("tempo_bpm")),
            meter=sanitize_sensitive_text(str(data.get("meter") or "")),
            duration_beats=_optional_float(data.get("duration_beats")),
            quality_score=_optional_int(data.get("quality_score")),
            favorite=bool(data.get("favorite", False)),
            hidden=bool(data.get("hidden", False)),
            usage_count=max(0, int(data.get("usage_count") or 0)),
            updated_at=str(data.get("updated_at") or ""),
            features=sanitize_metadata(dict(data.get("features") or {})),
            summary=sanitize_metadata(dict(data.get("summary") or {})),
            origin=sanitize_metadata(dict(data.get("origin") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LibraryIndex:
    schema_version: int
    built_at: str
    source_counts: dict[str, int]
    items: list[LibraryItem]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LibraryIndex":
        return cls(
            schema_version=int(data.get("schema_version", LIBRARY_INDEX_SCHEMA_VERSION) or LIBRARY_INDEX_SCHEMA_VERSION),
            built_at=str(data.get("built_at") or ""),
            source_counts={
                "assets": int((data.get("source_counts") or {}).get("assets") or 0),
                "references": int((data.get("source_counts") or {}).get("references") or 0),
            },
            items=[LibraryItem.from_dict(item) for item in data.get("items", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "built_at": self.built_at,
            "source_counts": dict(self.source_counts),
            "items": [item.to_dict() for item in self.items],
        }

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "built_at": self.built_at,
            "source_counts": dict(self.source_counts),
            "item_count": len(self.items),
        }


class LibraryIndexStore:
    def __init__(self, root: Path | str = LIBRARY_ROOT):
        self.root = Path(root)

    def read_index(self) -> LibraryIndex:
        path = self.index_path()
        if not path.exists():
            raise FileNotFoundError("Library index has not been built.")
        return LibraryIndex.from_dict(read_json(path))

    def load_or_build(self, asset_store: AssetStore, reference_store: ReferenceStore) -> LibraryIndex:
        try:
            return self.read_index()
        except FileNotFoundError:
            return self.rebuild(asset_store, reference_store)

    def rebuild(self, asset_store: AssetStore, reference_store: ReferenceStore, *, now: str | None = None) -> LibraryIndex:
        index = build_library_index(asset_store, reference_store, now=now)
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.index_path(), index.to_dict())
        self.append_event("library_index_rebuilt", {"item_count": len(index.items), "source_counts": index.source_counts}, now=index.built_at)
        return index

    def append_event(self, event_type: str, payload: dict[str, Any], *, now: str | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": now or now_iso(),
            "type": event_type,
            "payload": sanitize_metadata(payload),
        }
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def index_path(self) -> Path:
        return self.root / "index.json"


def build_library_index(asset_store: AssetStore, reference_store: ReferenceStore, *, now: str | None = None) -> LibraryIndex:
    assets = asset_store.list_assets(include_hidden=True)
    references = reference_store.list_references(include_hidden=True)
    items = [extract_asset_item(asset) for asset in assets]
    items.extend(extract_reference_item(reference, reference_store) for reference in references)
    return LibraryIndex(
        schema_version=LIBRARY_INDEX_SCHEMA_VERSION,
        built_at=now or now_iso(),
        source_counts={"assets": len(assets), "references": len(references)},
        items=sorted(items, key=lambda item: item.item_id),
    )


def extract_asset_item(asset: CreativeAsset) -> LibraryItem:
    content_summary = asset_content_summary(asset)
    notes = asset.content.get("notes") if isinstance(asset.content.get("notes"), list) else []
    pitches = [
        int(note.get("pitch"))
        for note in notes
        if isinstance(note, dict) and isinstance(note.get("pitch"), int)
    ]
    roles = asset_roles(asset.asset_type)
    token_source = " ".join(
        [
            asset.name,
            asset.description,
            asset.asset_type,
            asset.style,
            asset.mood,
            " ".join(asset.tags),
            " ".join(roles),
        ]
    )
    features = {
        "roles": roles,
        "tokens": tokenize_library_text(token_source),
        "note_count": len(notes),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "density_hint": _density_hint(len(notes), asset.duration_beats),
        "analysis_status": "not_applicable",
        "slice_count": 0,
    }
    return LibraryItem(
        schema_version=LIBRARY_INDEX_SCHEMA_VERSION,
        item_id=f"asset:{asset.asset_id}",
        item_kind="asset",
        source_id=asset.asset_id,
        source_hash=asset_source_hash(asset),
        title=asset.name,
        item_type=asset.asset_type,
        tags=list(asset.tags),
        style=asset.style,
        mood=asset.mood,
        key=asset.key,
        tempo_bpm=asset.tempo_bpm,
        meter=asset.meter,
        duration_beats=asset.duration_beats,
        quality_score=asset.quality_score,
        favorite=asset.favorite,
        hidden=asset.hidden,
        usage_count=asset.usage_count,
        updated_at=asset.updated_at or asset.created_at,
        features=sanitize_metadata(features),
        summary=sanitize_metadata(
            {
                "description": asset.description,
                "content_summary": content_summary,
                "source": _source_summary(asset.source),
            }
        ),
        origin=_source_origin(asset.source),
    )


def extract_reference_item(reference: ReferenceItem, store: ReferenceStore) -> LibraryItem:
    analysis_status = "not_analyzed"
    analysis_summary: dict[str, Any] = {}
    slice_count = 0
    roles: list[str] = reference_roles(reference.reference_type)
    try:
        report = get_analysis_report(store, reference.reference_id)
        analysis_status = str(report.get("status") or "not_analyzed")
        if report.get("stale"):
            analysis_status = "stale"
        analysis_summary = dict(report.get("summary") or {})
        slices = get_slice_manifest(store, reference.reference_id)
        if not slices.get("stale"):
            slice_count = len(slices.get("slices") or [])
    except (OSError, ValueError, TypeError):
        analysis_summary = {}
    roles.extend(_roles_from_analysis(analysis_summary))
    features = {
        "roles": sorted(set(roles)),
        "tokens": tokenize_library_text(
            " ".join(
                [
                    reference.title,
                    reference.description,
                    reference.reference_type,
                    " ".join(reference.tags),
                    str(reference_metadata_summary(reference)),
                    str(_compact_analysis_for_index(analysis_summary)),
                ]
            )
        ),
        "analysis_status": analysis_status,
        "slice_count": slice_count,
        **_reference_analysis_features(reference.reference_type, analysis_summary),
    }
    return LibraryItem(
        schema_version=LIBRARY_INDEX_SCHEMA_VERSION,
        item_id=f"reference:{reference.reference_id}",
        item_kind="reference",
        source_id=reference.reference_id,
        source_hash=reference.sha256,
        title=reference.title,
        item_type=reference.reference_type,
        tags=list(reference.tags),
        style="",
        mood="",
        key=reference.key,
        tempo_bpm=reference.tempo_bpm or _tempo_from_analysis(analysis_summary),
        meter=reference.meter or str(analysis_summary.get("meter") or ""),
        duration_beats=None,
        quality_score=None,
        favorite=reference.favorite,
        hidden=reference.hidden,
        usage_count=reference.usage_count,
        updated_at=reference.updated_at or reference.created_at,
        features=sanitize_metadata(features),
        summary=sanitize_metadata(
            {
                "description": reference.description,
                "metadata_summary": reference_metadata_summary(reference),
                "analysis_summary": _compact_analysis_for_index(analysis_summary),
            }
        ),
        origin={"project_id": None, "version_id": None, "candidate_group_id": None},
    )


def search_library(index: LibraryIndex, request: dict[str, Any]) -> dict[str, Any]:
    include_hidden = bool(request.get("include_hidden", False))
    include_stale = bool(request.get("include_stale", False))
    limit = _limit(request.get("limit"))
    results = []
    for item in index.items:
        if item.hidden and not include_hidden:
            continue
        if item.features.get("analysis_status") == "stale" and not include_stale:
            continue
        if not _matches_filters(item, request):
            continue
        score, breakdown = score_library_item(item, request)
        if score <= 0 and _has_search_constraints(request):
            continue
        results.append({"score": score, "score_breakdown": breakdown, **library_result_dict(item)})
    results.sort(
        key=lambda result: (
            -int(result["score"]),
            not bool(result.get("favorite")),
            -int(result.get("quality_score") or 0),
            str(result.get("updated_at") or ""),
            str(result.get("item_id") or ""),
        )
    )
    return {
        "ok": True,
        "results": results[:limit],
        "count": min(len(results), limit),
        "total": len(results),
        "query": _safe_query_summary(request),
    }


def score_library_item(item: LibraryItem, request: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    breakdown: list[dict[str, Any]] = []
    score = 0
    query_tokens = tokenize_library_text(str(request.get("query") or ""))
    item_tokens = set(str(token) for token in item.features.get("tokens", []) if isinstance(token, str))
    if query_tokens:
        matched = sorted(set(query_tokens) & item_tokens)
        points = min(35, int(round(35 * len(matched) / max(1, len(set(query_tokens))))))
        score += points
        breakdown.append(_reason("query_token_match", points, ", ".join(matched[:12])))
    type_points = _type_role_points(item, request)
    score += type_points[0]
    breakdown.extend(type_points[1])
    style_mood_points = _style_mood_points(item, request)
    score += style_mood_points[0]
    breakdown.extend(style_mood_points[1])
    musical_points = _musical_points(item, request)
    score += musical_points[0]
    breakdown.extend(musical_points[1])
    utility_points = _utility_points(item)
    score += utility_points[0]
    breakdown.extend(utility_points[1])
    freshness_points = 5 if item.features.get("analysis_status") != "stale" and not item.hidden else 0
    score += freshness_points
    breakdown.append(_reason("freshness_safety", freshness_points, str(item.features.get("analysis_status") or "fresh")))
    return min(100, score), breakdown


def recommend_library_context(index: LibraryIndex, request: dict[str, Any]) -> dict[str, Any]:
    query = recommendation_query(request)
    search_request = {
        **query,
        "include_hidden": False,
        "include_stale": False,
        "limit": max(10, int(request.get("limit") or 10) * 2),
    }
    results = search_library(index, search_request)["results"]
    asset_results = [item for item in results if item["item_kind"] == "asset"][:5]
    reference_results = [item for item in results if item["item_kind"] == "reference"][:5]
    preview = context_pack_preview_from_results(asset_results, reference_results)
    return {
        "ok": True,
        "recommendation": {
            "query": query,
            "asset_results": asset_results,
            "reference_results": reference_results,
            "context_pack_preview": preview,
        },
    }


def recommendation_query(request: dict[str, Any]) -> dict[str, Any]:
    source = str(request.get("source") or "song_request")
    goal = str(request.get("goal") or "generate")
    song_request = request.get("song_request") if isinstance(request.get("song_request"), dict) else {}
    text_parts = [
        str(song_request.get("title") or ""),
        str(song_request.get("style") or ""),
        str(song_request.get("theme") or ""),
        str(request.get("edit_instruction") or ""),
        str(request.get("candidate_goal") or ""),
    ]
    roles = _roles_for_goal(goal, " ".join(text_parts))
    return sanitize_metadata(
        {
            "source": source,
            "goal": goal,
            "query": " ".join(part for part in text_parts if part).strip(),
            "tokens": tokenize_library_text(" ".join(text_parts)),
            "style": str(song_request.get("style") or request.get("style") or ""),
            "mood": str(song_request.get("mood") or request.get("mood") or ""),
            "tempo_bpm": _optional_int(song_request.get("tempo_bpm") or request.get("tempo_bpm")),
            "key": str(song_request.get("key") or request.get("key") or ""),
            "roles": roles,
        }
    )


def context_pack_preview_from_results(asset_results: list[dict[str, Any]], reference_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "asset_refs": [
            {
                "asset_id": result["source_id"],
                "role": _role_for_result(result),
                "strength": 0.8,
                "source_hash": result.get("source_hash"),
            }
            for result in asset_results[:5]
        ],
        "reference_refs": [
            {
                "reference_id": result["source_id"],
                "role": _role_for_result(result),
                "strength": 0.6,
                "source_hash": result.get("source_hash"),
            }
            for result in reference_results[:5]
        ],
        "warnings": [],
    }


def library_result_dict(item: LibraryItem) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "item_id": item.item_id,
            "item_kind": item.item_kind,
            "source_id": item.source_id,
            "source_hash": item.source_hash,
            "title": item.title,
            "item_type": item.item_type,
            "tags": list(item.tags),
            "style": item.style,
            "mood": item.mood,
            "key": item.key,
            "tempo_bpm": item.tempo_bpm,
            "meter": item.meter,
            "duration_beats": item.duration_beats,
            "quality_score": item.quality_score,
            "favorite": item.favorite,
            "hidden": item.hidden,
            "usage_count": item.usage_count,
            "updated_at": item.updated_at,
            "features": item.features,
            "summary": item.summary,
        }
    )


def asset_source_hash(asset: CreativeAsset) -> str:
    data = {
        "asset_type": asset.asset_type,
        "name": asset.name,
        "description": asset.description,
        "tags": list(asset.tags),
        "style": asset.style,
        "mood": asset.mood,
        "key": asset.key,
        "tempo_bpm": asset.tempo_bpm,
        "meter": asset.meter,
        "duration_beats": asset.duration_beats,
        "quality_score": asset.quality_score,
        "source": asset.source,
        "content": asset.content,
    }
    return stable_source_hash(data)


def stable_source_hash(data: Any) -> str:
    cleaned = sanitize_metadata(data)
    payload = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tokenize_library_text(text: Any) -> list[str]:
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


def _matches_filters(item: LibraryItem, request: dict[str, Any]) -> bool:
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


def _type_role_points(item: LibraryItem, request: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
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


def _style_mood_points(item: LibraryItem, request: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    points = 0
    breakdown = []
    for field, max_points in (("style", 8), ("mood", 7)):
        wanted = tokenize_library_text(request.get(field))
        actual = set(tokenize_library_text(getattr(item, field)))
        matched = sorted(set(wanted) & actual)
        if matched:
            points += max_points
            breakdown.append(_reason(f"{field}_match", max_points, ", ".join(matched)))
    return min(15, points), breakdown


def _musical_points(item: LibraryItem, request: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
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


def _utility_points(item: LibraryItem) -> tuple[int, list[dict[str, Any]]]:
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


def _reason(reason: str, points: int, detail: str) -> dict[str, Any]:
    return {"reason": reason, "points": int(points), "detail": sanitize_sensitive_text(detail)}


def _safe_query_summary(request: dict[str, Any]) -> dict[str, Any]:
    allowed = {"query", "item_kinds", "asset_types", "reference_types", "roles", "style", "mood", "key", "tempo_bpm", "meter", "limit"}
    return sanitize_metadata({key: request.get(key) for key in allowed if key in request})


def _has_search_constraints(request: dict[str, Any]) -> bool:
    return any(request.get(key) for key in ("query", "item_kinds", "asset_types", "reference_types", "roles", "style", "mood", "key", "tempo_bpm", "meter", "tag", "favorite_only"))


def _role_for_result(result: dict[str, Any]) -> str:
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


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata({key: source.get(key) for key in ("source_type", "project_id", "version_id", "job_id", "reference_id", "slice_id", "candidate_group_id", "candidate_id") if source.get(key)})


def _source_origin(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": source.get("project_id"),
        "version_id": source.get("version_id"),
        "candidate_group_id": source.get("candidate_group_id"),
    }


def _roles_from_analysis(summary: dict[str, Any]) -> list[str]:
    roles = []
    for track in summary.get("track_summaries", []) if isinstance(summary.get("track_summaries"), list) else []:
        if isinstance(track, dict) and track.get("likely_role"):
            roles.append(str(track["likely_role"]))
    return roles


def _reference_analysis_features(reference_type: str, summary: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, Any] = {}
    if reference_type == "audio_wav":
        features.update(
            {
                "duration_seconds": summary.get("duration_seconds"),
                "sample_rate": summary.get("sample_rate"),
                "channels": summary.get("channels"),
            }
        )
    elif reference_type == "midi":
        track_summaries = summary.get("track_summaries") if isinstance(summary.get("track_summaries"), list) else []
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


def _compact_analysis_for_index(summary: dict[str, Any]) -> dict[str, Any]:
    compact = {
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


def _tempo_from_analysis(summary: dict[str, Any]) -> int | None:
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


def _string_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


def _clean_string_list(value: Any) -> list[str]:
    return sorted(_string_set(value))


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 20
    return max(1, min(limit, MAX_LIBRARY_RESULTS))
