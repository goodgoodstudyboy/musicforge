from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan
from song_agent.song_editor import build_editor_state, song_plan_hash


REVIEW_STATUSES = {"unreviewed", "keep", "maybe", "reject", "needs_fix"}
MARKER_KINDS = {"hook", "drop", "issue", "keep", "fix", "note"}
MARKER_SEVERITIES = {"info", "warning", "critical"}
SUPPORTED_AUDITION_ASSET_TYPES = {"motif", "bass_pattern", "drum_pattern", "chord_progression"}
MAX_REVIEW_NOTES_LENGTH = 2000
MAX_REVIEW_TAGS = 20
MAX_REVIEW_TAG_LENGTH = 40
MAX_MARKERS = 100
MAX_MARKER_LABEL_LENGTH = 160
MAX_ASSET_NOTES = 512


class EditorReviewError(ValueError):
    pass


@dataclass(frozen=True)
class AuditionMarker:
    marker_id: str
    beat: float
    kind: str = "note"
    label: str = ""
    severity: str = "info"
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, duration_beats: float | None = None) -> "AuditionMarker":
        if not isinstance(data, dict):
            raise EditorReviewError("marker must be an object.")
        marker_id = validate_marker_id(str(data.get("marker_id") or "marker-001"))
        beat = _float(data.get("beat"), "marker.beat")
        if duration_beats is not None and (beat < 0 or beat > duration_beats + 0.001):
            raise EditorReviewError("marker beat must be within audition duration.")
        kind = str(data.get("kind") or "note").strip()
        if kind not in MARKER_KINDS:
            raise EditorReviewError("marker kind is not supported.")
        severity = str(data.get("severity") or "info").strip()
        if severity not in MARKER_SEVERITIES:
            raise EditorReviewError("marker severity is not supported.")
        created_at = str(data.get("created_at") or "")
        return cls(
            marker_id=marker_id,
            beat=beat,
            kind=kind,
            label=_bounded_text(data.get("label"), MAX_MARKER_LABEL_LENGTH),
            severity=severity,
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditionReview:
    rating: int = 0
    favorite: bool = False
    status: str = "unreviewed"
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    markers: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str | None = None
    asset_count: int = 0
    last_asset_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, duration_beats: float | None = None) -> "AuditionReview":
        raw = data if isinstance(data, dict) else {}
        rating = _int(raw.get("rating"), "review.rating", default=0)
        if rating < 0 or rating > 5:
            raise EditorReviewError("review.rating must be between 0 and 5.")
        status = str(raw.get("status") or "unreviewed").strip()
        if status not in REVIEW_STATUSES:
            status = "unreviewed"
        markers = [AuditionMarker.from_dict(dict(item), duration_beats=duration_beats).to_dict() for item in raw.get("markers", []) if isinstance(item, dict)]
        if len(markers) > MAX_MARKERS:
            raise EditorReviewError(f"review markers supports at most {MAX_MARKERS} items.")
        asset_count = max(0, _int(raw.get("asset_count"), "review.asset_count", default=0))
        last_asset_id = str(raw.get("last_asset_id") or "").strip() or None
        return cls(
            rating=rating,
            favorite=bool(raw.get("favorite", False)),
            status=status,
            notes=_bounded_text(raw.get("notes"), MAX_REVIEW_NOTES_LENGTH),
            tags=_clean_tags(raw.get("tags")),
            markers=markers,
            updated_at=str(raw.get("updated_at") or "") or None,
            asset_count=asset_count,
            last_asset_id=last_asset_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_review() -> dict[str, Any]:
    return AuditionReview().to_dict()


def normalize_review(value: Any, *, duration_beats: float | None = None) -> dict[str, Any]:
    return AuditionReview.from_dict(value if isinstance(value, dict) else {}, duration_beats=duration_beats).to_dict()


def apply_review_patch(review_value: Any, patch: dict[str, Any], *, duration_beats: float, now: str | None = None) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise EditorReviewError("review patch must be an object.")
    review = AuditionReview.from_dict(review_value if isinstance(review_value, dict) else {}, duration_beats=duration_beats)
    data = review.to_dict()
    allowed = {"rating", "favorite", "status", "notes", "tags"}
    unknown = sorted(set(patch) - allowed)
    if unknown:
        raise EditorReviewError(f"review patch contains unsupported fields: {', '.join(unknown)}.")
    if "rating" in patch:
        rating = _int(patch.get("rating"), "review.rating", default=0)
        if rating < 0 or rating > 5:
            raise EditorReviewError("review.rating must be between 0 and 5.")
        data["rating"] = rating
    if "favorite" in patch:
        data["favorite"] = bool(patch.get("favorite", False))
    if "status" in patch:
        status = str(patch.get("status") or "unreviewed").strip()
        if status not in REVIEW_STATUSES:
            raise EditorReviewError("review.status is not supported.")
        data["status"] = status
    if "notes" in patch:
        data["notes"] = _bounded_text(patch.get("notes"), MAX_REVIEW_NOTES_LENGTH)
    if "tags" in patch:
        data["tags"] = _clean_tags(patch.get("tags"))
    data["updated_at"] = now or now_iso()
    return AuditionReview.from_dict(data, duration_beats=duration_beats).to_dict()


def add_marker(review_value: Any, payload: dict[str, Any], *, duration_beats: float, now: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EditorReviewError("marker payload must be an object.")
    now = now or now_iso()
    review = AuditionReview.from_dict(review_value if isinstance(review_value, dict) else {}, duration_beats=duration_beats)
    markers = list(review.markers)
    if len(markers) >= MAX_MARKERS:
        raise EditorReviewError(f"review markers supports at most {MAX_MARKERS} items.")
    marker_id = _next_marker_id(markers)
    marker = AuditionMarker.from_dict(
        {
            "marker_id": marker_id,
            "beat": payload.get("beat"),
            "kind": payload.get("kind") or "note",
            "label": payload.get("label") or "",
            "severity": payload.get("severity") or "info",
            "created_at": now,
            "updated_at": now,
        },
        duration_beats=duration_beats,
    ).to_dict()
    data = review.to_dict()
    data["markers"] = [*markers, marker]
    data["updated_at"] = now
    return AuditionReview.from_dict(data, duration_beats=duration_beats).to_dict()


def update_marker(review_value: Any, marker_id: str, patch: dict[str, Any], *, duration_beats: float, now: str | None = None) -> dict[str, Any]:
    marker_id = validate_marker_id(marker_id)
    if not isinstance(patch, dict):
        raise EditorReviewError("marker patch must be an object.")
    unknown = sorted(set(patch) - {"beat", "kind", "label", "severity"})
    if unknown:
        raise EditorReviewError(f"marker patch contains unsupported fields: {', '.join(unknown)}.")
    now = now or now_iso()
    review = AuditionReview.from_dict(review_value if isinstance(review_value, dict) else {}, duration_beats=duration_beats)
    updated_markers: list[dict[str, Any]] = []
    found = False
    for item in review.markers:
        if item.get("marker_id") != marker_id:
            updated_markers.append(item)
            continue
        found = True
        marker = AuditionMarker.from_dict({**item, **patch, "updated_at": now}, duration_beats=duration_beats)
        updated_markers.append(marker.to_dict())
    if not found:
        raise FileNotFoundError(marker_id)
    data = review.to_dict()
    data["markers"] = updated_markers
    data["updated_at"] = now
    return AuditionReview.from_dict(data, duration_beats=duration_beats).to_dict()


def delete_marker(review_value: Any, marker_id: str, *, duration_beats: float, now: str | None = None) -> dict[str, Any]:
    marker_id = validate_marker_id(marker_id)
    review = AuditionReview.from_dict(review_value if isinstance(review_value, dict) else {}, duration_beats=duration_beats)
    markers = [item for item in review.markers if item.get("marker_id") != marker_id]
    if len(markers) == len(review.markers):
        raise FileNotFoundError(marker_id)
    data = review.to_dict()
    data["markers"] = markers
    data["updated_at"] = now or now_iso()
    return AuditionReview.from_dict(data, duration_beats=duration_beats).to_dict()


def record_asset_created(review_value: Any, asset_id: str, *, duration_beats: float, now: str | None = None) -> dict[str, Any]:
    review = AuditionReview.from_dict(review_value if isinstance(review_value, dict) else {}, duration_beats=duration_beats)
    data = review.to_dict()
    data["asset_count"] = int(data.get("asset_count") or 0) + 1
    data["last_asset_id"] = str(asset_id)
    data["updated_at"] = now or now_iso()
    return AuditionReview.from_dict(data, duration_beats=duration_beats).to_dict()


def review_board(auditions: list[Any], filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    rows = [audition_review_row(item) for item in auditions]
    rows = [row for row in rows if _matches_filters(row, filters)]
    rows = _sort_rows(rows, filters)
    limit = _limit(filters.get("limit"), default=100)
    return {"summary": review_summary(rows), "auditions": rows[:limit], "filters": sanitize_metadata(filters)}


def review_summary(auditions_or_rows: list[Any]) -> dict[str, Any]:
    rows = [item if isinstance(item, dict) and "review" in item else audition_review_row(item) for item in auditions_or_rows]
    ratings = [int((row.get("review") or {}).get("rating") or 0) for row in rows if int((row.get("review") or {}).get("rating") or 0) > 0]
    status_counts = {status: 0 for status in sorted(REVIEW_STATUSES)}
    marker_count = 0
    asset_count = 0
    favorite_count = 0
    for row in rows:
        review = row.get("review") if isinstance(row.get("review"), dict) else {}
        status = str(review.get("status") or "unreviewed")
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1
        marker_count += len(review.get("markers") or [])
        asset_count += int(review.get("asset_count") or 0)
        if review.get("favorite"):
            favorite_count += 1
    return sanitize_metadata(
        {
            "audition_count": len(rows),
            "reviewed_count": sum(1 for row in rows if _reviewed(row.get("review") or {})),
            "favorite_count": favorite_count,
            "best_rating": max(ratings, default=0),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "status_counts": {key: value for key, value in status_counts.items() if value},
            "marker_count": marker_count,
            "asset_count": asset_count,
        }
    )


def audition_review_row(manifest: Any) -> dict[str, Any]:
    data = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    review = normalize_review(data.get("review"), duration_beats=float(data.get("duration_beats") or 0.0))
    row = {
        "audition_id": data.get("audition_id"),
        "project_id": data.get("project_id"),
        "preview_id": data.get("preview_id"),
        "parent_version_id": data.get("parent_version_id"),
        "source": data.get("source"),
        "range": sanitize_metadata(dict(data.get("range") or {})),
        "track_mode": data.get("track_mode"),
        "track_ids": list(data.get("track_ids") or []),
        "track_count": int(data.get("track_count") or 0),
        "note_count": int(data.get("note_count") or 0),
        "duration_beats": float(data.get("duration_beats") or 0.0),
        "midi": sanitize_metadata(dict(data.get("midi") or {})),
        "audio": sanitize_metadata(dict(data.get("audio") or {})),
        "created_at": data.get("created_at") or "",
        "updated_at": data.get("updated_at") or data.get("created_at") or "",
        "review": review,
    }
    return sanitize_metadata(row)


def audition_asset_payload(plan: SongPlan, manifest: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EditorReviewError("asset payload must be an object.")
    data = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    asset_type = str(payload.get("asset_type") or "motif").strip()
    if asset_type not in SUPPORTED_AUDITION_ASSET_TYPES:
        raise EditorReviewError("asset_type must be motif, bass_pattern, drum_pattern, or chord_progression.")
    track_id = str(payload.get("track_id") or "").strip()
    section = _section_from_range(plan, data.get("range") if isinstance(data.get("range"), dict) else {})
    track = _select_asset_track(plan, asset_type, track_id)
    content: dict[str, Any]
    source_track_name = None
    if asset_type == "chord_progression":
        content = {
            "kind": "chord_progression",
            "section_name": section.name,
            "chords": list(section.chords),
            "bars": section.bars,
            "harmonic_rhythm": 4.0,
            "key": plan.key,
        }
        source_track_name = None
    else:
        if track is None:
            raise EditorReviewError("Track not found for audition asset.")
        notes = list(track.notes)[:MAX_ASSET_NOTES]
        if not notes:
            raise EditorReviewError("Audition track has no notes for asset.")
        source_track_name = track.name
        rel_notes = [_relative_note(note) for note in notes]
        if asset_type == "motif":
            content = _motif_content(section, track, notes, rel_notes)
        elif asset_type == "bass_pattern":
            content = {"kind": "bass_pattern", "section_name": section.name, "track_name": track.name, "notes": rel_notes, "root_motion": _root_motion(notes)}
        else:
            content = {"kind": "drum_pattern", "section_name": section.name, "track_name": track.name, "notes": rel_notes, "meter": plan.meter}
    name = _bounded_text(payload.get("name"), 120) or f"{data.get('audition_id') or 'audition'} {asset_type}"
    source = sanitize_metadata(
        {
            "source_type": "editor_audition",
            "project_id": data.get("project_id"),
            "preview_id": data.get("preview_id"),
            "audition_id": data.get("audition_id"),
            "parent_version_id": data.get("parent_version_id"),
            "parent_job_id": data.get("parent_job_id"),
            "source": data.get("source"),
            "range": data.get("range") if isinstance(data.get("range"), dict) else {},
            "track_mode": data.get("track_mode"),
            "track_ids": data.get("track_ids") or [],
            "track_name": source_track_name,
            "source_plan_hash": data.get("source_plan_hash") or song_plan_hash(plan),
            "audition_review": review_summary([data]),
        }
    )
    return {
        "asset_type": asset_type,
        "name": name,
        "description": _bounded_text(payload.get("description"), 1000) or f"Saved from audition {data.get('audition_id') or ''}.",
        "tags": _clean_tags(payload.get("tags")),
        "style": _bounded_text(payload.get("style"), 120),
        "key": plan.key,
        "tempo_bpm": plan.tempo_bpm,
        "meter": plan.meter,
        "duration_beats": max(1.0, float(data.get("duration_beats") or _plan_duration(plan))),
        "quality_score": plan.quality.scores.overall if plan.quality and plan.quality.scores else None,
        "favorite": bool(payload.get("favorite", False)),
        "source": source,
        "content": content,
        "source_fragment": {
            "schema_version": 1,
            "source": source,
            "content": content,
            "extracted_at": now_iso(),
        },
    }


def validate_marker_id(marker_id: str) -> str:
    if not re.match(r"^marker-[0-9]{3,6}$", marker_id):
        raise ValueError("Invalid marker id.")
    return marker_id


def _matches_filters(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("source") and row.get("source") != filters.get("source"):
        return False
    review = row.get("review") if isinstance(row.get("review"), dict) else {}
    if filters.get("status") and review.get("status") != filters.get("status"):
        return False
    if str(filters.get("favorite") or "").lower() in {"true", "false"}:
        expected = str(filters.get("favorite")).lower() == "true"
        if bool(review.get("favorite")) != expected:
            return False
    min_rating = _int(filters.get("min_rating"), "min_rating", default=0)
    if min_rating and int(review.get("rating") or 0) < min_rating:
        return False
    if filters.get("track_mode") and row.get("track_mode") != filters.get("track_mode"):
        return False
    if filters.get("range_mode") and (row.get("range") or {}).get("mode") != filters.get("range_mode"):
        return False
    return True


def _sort_rows(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    sort = str(filters.get("sort") or "updated").strip()
    if sort not in {"rating", "updated", "created", "note_count", "duration"}:
        sort = "updated"
    reverse = str(filters.get("order") or "desc").strip() != "asc"

    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        review = row.get("review") if isinstance(row.get("review"), dict) else {}
        if sort == "rating":
            primary = int(review.get("rating") or 0)
        elif sort == "created":
            primary = row.get("created_at") or ""
        elif sort == "note_count":
            primary = int(row.get("note_count") or 0)
        elif sort == "duration":
            primary = float(row.get("duration_beats") or 0.0)
        else:
            primary = review.get("updated_at") or row.get("updated_at") or row.get("created_at") or ""
        return (primary, row.get("updated_at") or "", row.get("audition_id") or "")

    return sorted(rows, key=key, reverse=reverse)


def _reviewed(review: dict[str, Any]) -> bool:
    return bool(review.get("rating")) or bool(review.get("favorite")) or str(review.get("status") or "unreviewed") != "unreviewed" or bool(review.get("notes")) or bool(review.get("tags")) or bool(review.get("markers"))


def _next_marker_id(markers: list[dict[str, Any]]) -> str:
    existing = {str(item.get("marker_id") or "") for item in markers}
    for index in range(1, 1_000_000):
        marker_id = f"marker-{index:03d}"
        if marker_id not in existing:
            return marker_id
    raise EditorReviewError("Could not allocate marker id.")


def _clean_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EditorReviewError("review tags must be a list.")
    tags: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = _bounded_text(item, MAX_REVIEW_TAG_LENGTH)
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
        if len(tags) >= MAX_REVIEW_TAGS:
            break
    return tags


def _bounded_text(value: Any, limit: int) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    return text[:limit].rstrip()


def _float(value: Any, name: str) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError) as exc:
        raise EditorReviewError(f"{name} must be a number.") from exc


def _int(value: Any, name: str, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise EditorReviewError(f"{name} must be an integer.") from exc


def _limit(value: Any, *, default: int) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, 500))


def _section_from_range(plan: SongPlan, range_data: dict[str, Any]) -> SongSection:
    mode = str(range_data.get("mode") or "")
    if mode == "section":
        section_name = str(range_data.get("section_name") or "")
        if section_name:
            for section in plan.sections:
                if section.name == section_name:
                    return section
    start = float(range_data.get("start_beat") or 0.0)
    for section in plan.sections:
        section_start = float((section.start_bar - 1) * 4)
        section_end = section_start + float(section.bars * 4)
        if section_start <= start < section_end:
            return section
    return plan.sections[0]


def _select_asset_track(plan: SongPlan, asset_type: str, track_id: str) -> TrackPlan | None:
    state = build_editor_state(plan)
    if track_id:
        for index, track_state in enumerate(state.get("tracks", [])):
            if track_state.get("track_id") == track_id:
                return plan.tracks[index]
        raise EditorReviewError("Unknown track_id.")
    if asset_type == "chord_progression":
        return None
    role = {"motif": "melody", "bass_pattern": "bass", "drum_pattern": "drums"}[asset_type]
    for track in plan.tracks:
        text = f"{track.name} {track.instrument}".lower()
        if role in text or (role == "drums" and "drum" in text):
            return track
    raise EditorReviewError(f"{role} track not found.")


def _relative_note(note: NoteEvent) -> dict[str, Any]:
    return {
        "pitch": note.pitch,
        "start_beat": round(float(note.start_beat), 3),
        "duration_beats": round(float(note.duration_beats), 3),
        "velocity": note.velocity,
    }


def _motif_content(section: SongSection, track: TrackPlan, notes: list[NoteEvent], rel_notes: list[dict[str, Any]]) -> dict[str, Any]:
    anchor = notes[0].pitch
    return {
        "kind": "motif",
        "section_name": section.name,
        "track_name": track.name,
        "rhythm_pattern": [round(note.duration_beats, 3) for note in notes[:16]],
        "pitch_intervals": [note.pitch - anchor for note in notes[:16]],
        "anchor_pitch": anchor,
        "start_pattern": [round(note.start_beat - notes[0].start_beat, 3) for note in notes[:16]],
        "notes": rel_notes,
    }


def _root_motion(notes: list[NoteEvent]) -> list[int]:
    return [note.pitch % 12 for note in notes[:16]]


def _plan_duration(plan: SongPlan) -> float:
    return max((section.start_bar - 1 + section.bars) * 4 for section in plan.sections)
