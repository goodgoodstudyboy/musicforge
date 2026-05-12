from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.edits import EditIntent, EditedSongPlanResult, apply_edit_intent, validate_edit_intent
from song_agent.editor_audition import EditorAuditionManifest
from song_agent.music_quality import attach_quality
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.schemas.song import SongPlan, SongSection, TrackPlan
from song_agent.song_editor import song_plan_hash


REVIEW_EDIT_SCHEMA_VERSION = 1
MAX_REVIEW_EDIT_INTENTS = 4
MAX_REVIEW_EDIT_TEXT = 2000
REVIEW_EDIT_ID_PATTERN = re.compile(r"^review-edit-[0-9]{3,6}$")

ENERGY_KEYWORDS = ("energy", "lift", "stronger", "bigger", "more intense", "更强", "能量", "加强", "高潮", "更炸")
REDUCE_KEYWORDS = ("too busy", "too dense", "crowded", "reduce", "less", "太满", "太密", "减少", "稀疏")
INCREASE_KEYWORDS = ("more", "add", "fill", "empty", "thin", "太空", "太少", "加一点", "更丰富")
MELODY_KEYWORDS = ("hook", "melody", "variation", "catchy", "旋律", "副歌", "变化")
ARRANGEMENT_KEYWORDS = ("arrangement", "transition", "drop", "build", "break", "编曲", "过渡", "铺垫")
TRACK_ROLE_KEYWORDS = {
    "bass": ("bass", "低音", "贝斯"),
    "drums": ("drum", "drums", "kick", "snare", "鼓", "军鼓", "底鼓"),
    "melody": ("melody", "lead", "hook", "旋律", "主旋律"),
    "chords": ("chord", "harmony", "pad", "和弦", "和声"),
}


class ReviewEditError(ValueError):
    pass


class ReviewEditUnavailableError(ReviewEditError):
    pass


@dataclass(frozen=True)
class ReviewEditIntent:
    schema_version: int
    review_edit_id: str
    project_id: str
    parent_version_id: str
    preview_id: str
    audition_id: str
    source: dict[str, Any]
    mode: str = "local"
    intents: list[dict[str, Any]] = field(default_factory=list)
    instruction: str = ""
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewEditIntent":
        if not isinstance(data, dict):
            raise ReviewEditError("review edit must be an object.")
        return cls(
            schema_version=int(data.get("schema_version", REVIEW_EDIT_SCHEMA_VERSION) or REVIEW_EDIT_SCHEMA_VERSION),
            review_edit_id=validate_review_edit_id(str(data.get("review_edit_id") or "review-edit-001")),
            project_id=str(data.get("project_id") or ""),
            parent_version_id=str(data.get("parent_version_id") or ""),
            preview_id=str(data.get("preview_id") or ""),
            audition_id=str(data.get("audition_id") or ""),
            source=sanitize_metadata(dict(data.get("source") or {})),
            mode=_mode(data.get("mode")),
            intents=[EditIntent.from_dict(dict(item)).to_dict() for item in data.get("intents", []) if isinstance(item, dict)],
            instruction=sanitize_sensitive_text(str(data.get("instruction") or ""))[:MAX_REVIEW_EDIT_TEXT],
            confidence=_confidence(data.get("confidence")),
            warnings=[sanitize_sensitive_text(str(item)) for item in data.get("warnings", [])],
            created_at=str(data.get("created_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReviewEditStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.root = self.project_dir / "review-edits"

    def create_preview(
        self,
        *,
        review_edit: ReviewEditIntent,
        parent_plan: SongPlan,
        result: EditedSongPlanResult,
        validator: dict[str, Any],
        now: str | None = None,
    ) -> ReviewEditIntent:
        now = now or now_iso()
        self.root.mkdir(parents=True, exist_ok=True)
        review_edit_id, edit_dir = self._reserve_review_edit_dir()
        review_edit = ReviewEditIntent.from_dict({**review_edit.to_dict(), "review_edit_id": review_edit_id, "created_at": now})
        try:
            write_json(edit_dir / "review-edit.json", review_edit.to_dict())
            write_json(edit_dir / "candidate-song-plan.json", result.plan.to_dict())
            write_json(edit_dir / "validator-report.json", validator)
            write_json(edit_dir / "summary.json", review_edit_summary(review_edit, result))
        except Exception:
            if edit_dir.exists() and not (edit_dir / "review-edit.json").exists():
                shutil.rmtree(edit_dir)
            raise
        return review_edit

    def read_preview(self, review_edit_id: str) -> ReviewEditIntent:
        return ReviewEditIntent.from_dict(read_json(self.review_edit_dir(review_edit_id) / "review-edit.json"))

    def review_edit_dir(self, review_edit_id: str) -> Path:
        review_edit_id = validate_review_edit_id(review_edit_id)
        base = self.root.resolve()
        target = (base / review_edit_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside review edits.") from exc
        return target

    def _reserve_review_edit_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            review_edit_id = f"review-edit-{index:03d}"
            edit_dir = self.review_edit_dir(review_edit_id)
            try:
                edit_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return review_edit_id, edit_dir
        raise RuntimeError("Could not allocate review edit id.")


def build_review_edit(
    *,
    project_id: str,
    parent_version_id: str,
    parent_plan: SongPlan,
    audition: EditorAuditionManifest,
    audition_plan: SongPlan,
    payload: dict[str, Any] | None = None,
    now: str | None = None,
) -> ReviewEditIntent:
    payload = payload if isinstance(payload, dict) else {}
    mode = _mode(payload.get("mode"))
    source = build_review_edit_source(project_id=project_id, parent_version_id=parent_version_id, audition=audition, audition_plan=audition_plan)
    overrides = payload.get("intent_overrides")
    if overrides is not None:
        intents, warnings = _override_intents(parent_plan, overrides)
    else:
        intents, warnings = infer_review_edit_intents(parent_plan, audition, audition_plan)
    if not intents:
        raise ReviewEditUnavailableError("No safe local edit intent was generated from this review.")
    instruction = _review_edit_instruction(source, intents)
    confidence = _confidence_for_source(source, intents)
    review_edit = ReviewEditIntent.from_dict(
        {
            "schema_version": REVIEW_EDIT_SCHEMA_VERSION,
            "review_edit_id": "review-edit-001",
            "project_id": project_id,
            "parent_version_id": parent_version_id,
            "preview_id": audition.preview_id,
            "audition_id": audition.audition_id,
            "source": source,
            "mode": mode,
            "intents": [intent.to_dict() for intent in intents],
            "instruction": instruction,
            "confidence": confidence,
            "warnings": warnings,
            "created_at": now or now_iso(),
        }
    )
    validate_review_edit(parent_plan, review_edit)
    return review_edit


def build_review_edit_source(
    *,
    project_id: str,
    parent_version_id: str,
    audition: EditorAuditionManifest,
    audition_plan: SongPlan,
) -> dict[str, Any]:
    review = audition.review if isinstance(audition.review, dict) else {}
    markers = [
        {
            "marker_id": marker.get("marker_id"),
            "beat": marker.get("beat"),
            "kind": marker.get("kind"),
            "severity": marker.get("severity"),
            "label": sanitize_sensitive_text(str(marker.get("label") or ""))[:160],
        }
        for marker in review.get("markers", [])
        if isinstance(marker, dict)
    ]
    return sanitize_metadata(
        {
            "project_id": project_id,
            "parent_version_id": parent_version_id,
            "preview_id": audition.preview_id,
            "audition_id": audition.audition_id,
            "audition_source": audition.source,
            "audition_range": dict(audition.range or {}),
            "track_mode": audition.track_mode,
            "track_ids": list(audition.track_ids),
            "rating": int(review.get("rating") or 0),
            "status": str(review.get("status") or "unreviewed"),
            "favorite": bool(review.get("favorite", False)),
            "notes_excerpt": sanitize_sensitive_text(str(review.get("notes") or ""))[:500],
            "tags": [sanitize_sensitive_text(str(tag))[:40] for tag in review.get("tags", [])],
            "markers": markers,
            "marker_kinds": sorted({str(marker.get("kind") or "") for marker in markers if marker.get("kind")}),
            "asset_ids": [str(review.get("last_asset_id"))] if review.get("last_asset_id") else [],
            "source_plan_hash": audition.source_plan_hash or song_plan_hash(audition_plan),
            "audition_plan_hash": song_plan_hash(audition_plan),
            "note_count": audition.note_count,
            "duration_beats": audition.duration_beats,
        }
    )


def infer_review_edit_intents(parent_plan: SongPlan, audition: EditorAuditionManifest, audition_plan: SongPlan) -> tuple[list[EditIntent], list[str]]:
    review = audition.review if isinstance(audition.review, dict) else {}
    rating = int(review.get("rating") or 0)
    status = str(review.get("status") or "unreviewed")
    warnings: list[str] = []
    if status == "reject" or (rating and rating <= 2):
        raise ReviewEditUnavailableError("Review is rejected; no safe local edit intent was generated.")
    text = _review_text(audition)
    markers = [item for item in review.get("markers", []) if isinstance(item, dict)]
    section = _target_section(parent_plan, audition, markers)
    track = _target_track(parent_plan, audition, text)
    intents: list[EditIntent] = []

    if _has_any(text, REDUCE_KEYWORDS) or any(str(marker.get("kind")) in {"fix", "issue"} for marker in markers):
        reduce_track = track or _track_by_role(parent_plan, _role_from_text(text) or "bass")
        if reduce_track is not None:
            intents.append(
                _intent(
                    "track_density",
                    track_name=reduce_track.name,
                    section_name=section.name,
                    strength=4,
                    instruction="Reduce track density based on audition review.",
                    preserve=["tempo", "key", "structure", "lyrics", "harmony"],
                    payload={"density_scale": 0.72, "source": "audition_review"},
                )
            )

    if _has_any(text, INCREASE_KEYWORDS) and not _has_any(text, REDUCE_KEYWORDS):
        increase_track = track or _track_by_role(parent_plan, _role_from_text(text) or "melody")
        if increase_track is not None:
            intents.append(
                _intent(
                    "track_density",
                    track_name=increase_track.name,
                    section_name=section.name,
                    strength=7,
                    instruction="Increase track density based on audition review.",
                    preserve=["tempo", "key", "structure", "lyrics", "harmony"],
                    payload={"density_scale": 1.2, "source": "audition_review"},
                )
            )

    if _has_any(text, ENERGY_KEYWORDS) or any(str(marker.get("kind")) == "drop" for marker in markers) or status == "needs_fix":
        intents.append(
            _intent(
                "section_energy",
                section_name=section.name,
                strength=7,
                instruction="Lift section energy based on audition review.",
                preserve=["tempo", "key", "structure", "lyrics", "harmony"],
                payload={"source": "audition_review"},
            )
        )

    if _has_any(text, MELODY_KEYWORDS) and not any(str(marker.get("kind")) in {"hook", "keep"} for marker in markers):
        intents.append(
            _intent(
                "melody_variation",
                section_name=section.name,
                strength=5,
                instruction="Create a small melody variation from review feedback.",
                preserve=["tempo", "key", "structure", "harmony"],
                payload={"source": "audition_review"},
            )
        )
    elif any(str(marker.get("kind")) in {"hook", "keep"} for marker in markers):
        warnings.append("Hook/keep markers were treated as preserve signals, not edit targets.")

    if _has_any(text, ARRANGEMENT_KEYWORDS):
        intents.append(
            _intent(
                "arrangement_variation",
                section_name=section.name,
                track_name=(track.name if track else None),
                strength=6,
                instruction="Adjust arrangement based on audition review.",
                preserve=["tempo", "key", "structure"],
                payload={"source": "audition_review"},
            )
        )

    deduped: list[EditIntent] = []
    seen: set[str] = set()
    for intent in intents:
        key = json.dumps(intent.to_dict(), sort_keys=True)
        if key in seen:
            continue
        try:
            validate_edit_intent(parent_plan, intent)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        seen.add(key)
        deduped.append(intent)
        if len(deduped) >= MAX_REVIEW_EDIT_INTENTS:
            break
    if not deduped and status == "needs_fix":
        fallback_track = track or _track_by_role(parent_plan, "bass")
        if fallback_track is not None:
            deduped.append(
                _intent(
                    "track_density",
                    track_name=fallback_track.name,
                    section_name=section.name,
                    strength=4,
                    instruction="Apply a conservative density reduction from needs_fix review.",
                    preserve=["tempo", "key", "structure", "lyrics", "harmony"],
                    payload={"density_scale": 0.82, "source": "audition_review_fallback"},
                )
            )
    if not deduped:
        raise ReviewEditUnavailableError("No safe local edit intent was generated from this review.")
    return deduped, warnings


def apply_review_edit(parent_plan: SongPlan, review_edit: ReviewEditIntent) -> EditedSongPlanResult:
    validate_review_edit(parent_plan, review_edit)
    current = parent_plan
    summaries: list[dict[str, Any]] = []
    warnings = list(review_edit.warnings)
    for raw_intent in review_edit.intents:
        intent = EditIntent.from_dict(raw_intent)
        result = apply_edit_intent(current, intent)
        current = result.plan
        summaries.append(result.summary)
        warnings.extend(result.warnings)
    final_plan = attach_quality(current)
    final_plan.validate()
    return EditedSongPlanResult(
        plan=final_plan,
        summary={
            "edit_source": "audition_review",
            "review_edit_id": review_edit.review_edit_id,
            "operation_count": len(review_edit.intents),
            "changed_sections": sorted({section for summary in summaries for section in summary.get("changed_sections", [])}),
            "changed_tracks": sorted({track for summary in summaries for track in summary.get("changed_tracks", [])}),
            "operations": summaries,
            "confidence": review_edit.confidence,
        },
        warnings=warnings,
    )


def validate_review_edit(parent_plan: SongPlan, review_edit: ReviewEditIntent) -> None:
    if not review_edit.intents:
        raise ReviewEditUnavailableError("review edit has no intents.")
    if len(review_edit.intents) > MAX_REVIEW_EDIT_INTENTS:
        raise ReviewEditError(f"review edit supports at most {MAX_REVIEW_EDIT_INTENTS} intents.")
    for raw_intent in review_edit.intents:
        validate_edit_intent(parent_plan, EditIntent.from_dict(raw_intent))


def review_edit_metadata(review_edit: ReviewEditIntent, result: EditedSongPlanResult) -> dict[str, Any]:
    metadata = sanitize_metadata(
        {
            "edit_source": "audition_review",
            "review_edit": review_edit.to_dict(),
            "review_summary": review_edit.source,
            "summary": result.summary,
            "warnings": result.warnings,
        }
    )
    return metadata


def review_edit_summary(review_edit: ReviewEditIntent, result: EditedSongPlanResult | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "review_edit_id": review_edit.review_edit_id,
            "mode": review_edit.mode,
            "preview_id": review_edit.preview_id,
            "audition_id": review_edit.audition_id,
            "intent_count": len(review_edit.intents),
            "edit_types": [item.get("edit_type") for item in review_edit.intents],
            "changed_sections": (result.summary.get("changed_sections") if result else []) if result else [],
            "changed_tracks": (result.summary.get("changed_tracks") if result else []) if result else [],
            "confidence": review_edit.confidence,
            "warnings": review_edit.warnings if result is None else result.warnings,
        }
    )


def review_edit_instruction_for_provider(review_edit: ReviewEditIntent) -> str:
    instruction = sanitize_sensitive_text(review_edit.instruction)
    source = review_edit.source
    marker_text = ", ".join(f"{marker.get('kind')}@{marker.get('beat')}" for marker in source.get("markers", []) if isinstance(marker, dict))
    return (
        f"{instruction}\n"
        f"Review status={source.get('status')} rating={source.get('rating')} favorite={source.get('favorite')}.\n"
        f"Notes: {source.get('notes_excerpt') or ''}\n"
        f"Markers: {marker_text or 'none'}"
    )[:MAX_REVIEW_EDIT_TEXT]


def validate_review_edit_id(review_edit_id: str) -> str:
    if not REVIEW_EDIT_ID_PATTERN.match(review_edit_id):
        raise ValueError("Invalid review edit id.")
    return review_edit_id


def _override_intents(parent_plan: SongPlan, raw: Any) -> tuple[list[EditIntent], list[str]]:
    if not isinstance(raw, list) or not raw:
        raise ReviewEditError("intent_overrides must be a non-empty list.")
    if len(raw) > MAX_REVIEW_EDIT_INTENTS:
        raise ReviewEditError(f"intent_overrides supports at most {MAX_REVIEW_EDIT_INTENTS} items.")
    intents = [EditIntent.from_dict(dict(item)) for item in raw if isinstance(item, dict)]
    if len(intents) != len(raw):
        raise ReviewEditError("intent_overrides items must be objects.")
    for intent in intents:
        validate_edit_intent(parent_plan, intent)
    return intents, ["Used explicit intent overrides."]


def _review_text(audition: EditorAuditionManifest) -> str:
    review = audition.review if isinstance(audition.review, dict) else {}
    parts = [
        str(review.get("notes") or ""),
        " ".join(str(tag) for tag in review.get("tags", [])),
        str(review.get("status") or ""),
        " ".join(str(marker.get("kind") or "") + " " + str(marker.get("label") or "") for marker in review.get("markers", []) if isinstance(marker, dict)),
        str(audition.range.get("section_name") if isinstance(audition.range, dict) else ""),
    ]
    return sanitize_sensitive_text(" ".join(parts))[:MAX_REVIEW_EDIT_TEXT].lower()


def _review_edit_instruction(source: dict[str, Any], intents: list[EditIntent]) -> str:
    notes = str(source.get("notes_excerpt") or "").strip()
    edits = ", ".join(intent.edit_type for intent in intents)
    if notes:
        return sanitize_sensitive_text(f"Review requested {edits}: {notes}")[:MAX_REVIEW_EDIT_TEXT]
    return sanitize_sensitive_text(f"Create review-driven edit: {edits}.")[:MAX_REVIEW_EDIT_TEXT]


def _confidence_for_source(source: dict[str, Any], intents: list[EditIntent]) -> float:
    rating = int(source.get("rating") or 0)
    marker_count = len(source.get("markers") or [])
    score = 0.45 + min(0.25, rating * 0.04) + min(0.2, marker_count * 0.05) + min(0.1, len(intents) * 0.03)
    return round(min(0.95, score), 2)


def _target_section(parent_plan: SongPlan, audition: EditorAuditionManifest, markers: list[dict[str, Any]]) -> SongSection:
    range_data = audition.range if isinstance(audition.range, dict) else {}
    if range_data.get("mode") == "section":
        section_name = str(range_data.get("section_name") or "")
        section = _find_section(parent_plan, section_name)
        if section is not None:
            return section
    if markers:
        beat = _float_or_none(markers[0].get("beat"))
        if beat is not None:
            section = _section_for_beat(parent_plan, beat)
            if section is not None:
                return section
    for section in parent_plan.sections:
        if "chorus" in section.name.lower():
            return section
    for section in parent_plan.sections:
        if "verse" in section.name.lower():
            return section
    return parent_plan.sections[0]


def _target_track(parent_plan: SongPlan, audition: EditorAuditionManifest, text: str) -> TrackPlan | None:
    if audition.track_mode == "solo" and len(audition.track_ids) == 1:
        state = _track_state(parent_plan)
        track_index = state.get(audition.track_ids[0])
        if track_index is not None:
            return parent_plan.tracks[track_index]
    role = _role_from_text(text)
    if role:
        return _track_by_role(parent_plan, role)
    return None


def _role_from_text(text: str) -> str | None:
    for role, keywords in TRACK_ROLE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return role
    return None


def _track_by_role(parent_plan: SongPlan, role: str) -> TrackPlan | None:
    for track in parent_plan.tracks:
        text = f"{track.name} {track.instrument}".lower()
        if role in text or (role == "drums" and "drum" in text) or (role == "chords" and ("chord" in text or "pad" in text)):
            return track
    return None


def _track_state(plan: SongPlan) -> dict[str, int]:
    return {f"track-{index + 1:03d}": index for index, _track in enumerate(plan.tracks)}


def _find_section(plan: SongPlan, name: str) -> SongSection | None:
    for section in plan.sections:
        if section.name.lower() == str(name or "").lower():
            return section
    return None


def _section_for_beat(plan: SongPlan, beat: float) -> SongSection | None:
    for section in plan.sections:
        start = float((section.start_bar - 1) * 4)
        end = start + float(section.bars * 4)
        if start <= beat < end:
            return section
    return None


def _intent(
    edit_type: str,
    *,
    section_name: str | None = None,
    track_name: str | None = None,
    strength: int,
    instruction: str,
    preserve: list[str],
    payload: dict[str, Any],
) -> EditIntent:
    target: dict[str, Any] = {}
    if section_name:
        target["section_name"] = section_name
    if track_name:
        target["track_name"] = track_name
    if edit_type in {"section_energy", "melody_variation", "arrangement_variation"}:
        target["field"] = "notes"
    if edit_type == "track_density":
        target["field"] = "notes"
    return EditIntent.from_dict(
        {
            "edit_type": edit_type,
            "target": target,
            "instruction": instruction,
            "preserve": preserve,
            "strength": strength,
            "provider_mode": "local",
            "payload": payload,
        }
    )


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _mode(value: Any) -> str:
    mode = str(value or "local").strip()
    if mode not in {"local", "provider"}:
        raise ReviewEditError("review edit mode must be local or provider.")
    return mode


def _confidence(value: Any) -> float:
    try:
        confidence = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise ReviewEditError("confidence must be a number.") from exc
    return round(max(0.0, min(1.0, confidence)), 3)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
