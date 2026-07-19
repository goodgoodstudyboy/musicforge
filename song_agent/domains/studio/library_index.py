# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_int as _as_int, as_list as _as_list

import hashlib as hashlib
import json as json
import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.assets import AssetStore as AssetStore, CreativeAsset as CreativeAsset, asset_content_summary as asset_content_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.reference_analysis import get_analysis_report as get_analysis_report, get_slice_manifest as get_slice_manifest
from song_agent.domains.studio.references import ReferenceItem as ReferenceItem, ReferenceStore as ReferenceStore, reference_metadata_summary as reference_metadata_summary


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
    features: ImplementationDocument = field(default_factory=dict)
    summary: ImplementationDocument = field(default_factory=dict)
    origin: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "LibraryItem":
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

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class LibraryIndex:
    schema_version: int
    built_at: str
    source_counts: dict[str, int]
    items: list[LibraryItem]

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "LibraryIndex":
        return cls(
            schema_version=int(data.get("schema_version", LIBRARY_INDEX_SCHEMA_VERSION) or LIBRARY_INDEX_SCHEMA_VERSION),
            built_at=str(data.get("built_at") or ""),
            source_counts={
                "assets": int((data.get("source_counts") or {}).get("assets") or 0),
                "references": int((data.get("source_counts") or {}).get("references") or 0),
            },
            items=[LibraryItem.from_dict(item) for item in data.get("items", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> DomainDocument:
        return {
            "schema_version": self.schema_version,
            "built_at": self.built_at,
            "source_counts": dict(self.source_counts),
            "items": [item.to_dict() for item in self.items],
        }

    def summary(self) -> DomainDocument:
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

    def append_event(self, event_type: str, payload: DomainDocument, *, now: str | None = None) -> None:
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
    notes = _as_list(asset.content.get("notes"))
    pitches = [
        _as_int(note.get("pitch"))
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
    analysis_summary: ImplementationDocument = {}
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


def search_library(index: LibraryIndex, request: DomainDocument) -> DomainDocument:
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
    results.sort(key=lambda result: str(result.get("item_id") or ""))
    results.sort(key=lambda result: str(result.get("updated_at") or ""), reverse=True)
    results.sort(key=lambda result: int(result.get("quality_score") or 0), reverse=True)
    results.sort(key=lambda result: bool(result.get("favorite")), reverse=True)
    results.sort(key=lambda result: int(result["score"]), reverse=True)
    return {
        "ok": True,
        "results": results[:limit],
        "count": min(len(results), limit),
        "total": len(results),
        "query": _safe_query_summary(request),
    }


def score_library_item(item: LibraryItem, request: DomainDocument) -> tuple[int, list[DomainDocument]]:
    breakdown: list[ImplementationDocument] = []
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


def recommend_library_context(index: LibraryIndex, request: DomainDocument) -> DomainDocument:
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


def recommendation_query(request: DomainDocument) -> DomainDocument:
    source = str(request.get("source") or "song_request")
    goal = str(request.get("goal") or "generate")
    song_request = _as_document(request.get("song_request"))
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


def context_pack_preview_from_results(asset_results: list[DomainDocument], reference_results: list[DomainDocument]) -> DomainDocument:
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


def library_result_dict(item: LibraryItem) -> DomainDocument:
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


from song_agent.domains.studio import v142_li_readiness as _v142_li_readiness
from song_agent.domains.studio.v142_li_readiness import tokenize_library_text as tokenize_library_text, asset_roles as asset_roles, reference_roles as reference_roles, _matches_filters as _matches_filters, _type_role_points as _type_role_points, _style_mood_points as _style_mood_points, _musical_points as _musical_points, _utility_points as _utility_points, _reason as _reason, _safe_query_summary as _safe_query_summary, _has_search_constraints as _has_search_constraints, _role_for_result as _role_for_result, _roles_for_goal as _roles_for_goal, _density_hint as _density_hint, _source_summary as _source_summary, _source_origin as _source_origin, _roles_from_analysis as _roles_from_analysis, _reference_analysis_features as _reference_analysis_features, _compact_analysis_for_index as _compact_analysis_for_index, _tempo_from_analysis as _tempo_from_analysis, _normalize_key as _normalize_key, _string_set as _string_set, _clean_string_list as _clean_string_list, _optional_int as _optional_int, _optional_float as _optional_float, _limit as _limit

_v142_li_readiness.bind_globals(globals())
