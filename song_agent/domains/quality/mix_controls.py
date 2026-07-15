from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import NoteEvent, SongPlan, TrackPlan
from song_agent.domains.studio.song_editor import section_id_for_index, track_id_for_index


MIX_STATE_SCHEMA_VERSION = 1
MIX_PATCH_SCHEMA_VERSION = 1
SUPPORTED_MIX_OPS = {
    "set_track_volume",
    "set_track_pan",
    "set_track_mute",
    "set_track_solo",
    "set_track_velocity_scale",
    "set_section_track_volume_delta",
    "set_section_track_velocity_scale",
    "reset_track_mix",
    "reset_section_track_mix",
}
MIX_STATE_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}
MIX_PATCH_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}


class MixControlError(ValueError):
    pass


class MixControlStateError(MixControlError):
    pass


@dataclass(frozen=True)
class SectionAutomation:
    section_id: str
    volume_db_delta: float = 0.0
    velocity_scale: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionAutomation":
        section_id = _validate_section_id(str(data.get("section_id") or ""))
        return cls(
            section_id=section_id,
            volume_db_delta=_volume_db_delta(data.get("volume_db_delta", 0.0)),
            velocity_scale=_velocity_scale(data.get("velocity_scale", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MixTrackState:
    track_id: str
    role: str
    name: str
    instrument: str
    volume_db: float = 0.0
    pan: int = 0
    mute: bool = False
    solo: bool = False
    velocity_scale: float = 1.0
    note_count: int = 0
    section_automation: list[SectionAutomation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MixTrackState":
        return cls(
            track_id=_validate_track_id(str(data.get("track_id") or "")),
            role=sanitize_sensitive_text(str(data.get("role") or ""))[:80],
            name=sanitize_sensitive_text(str(data.get("name") or ""))[:120],
            instrument=sanitize_sensitive_text(str(data.get("instrument") or ""))[:120],
            volume_db=_volume_db(data.get("volume_db", 0.0)),
            pan=_pan(data.get("pan", 0)),
            mute=bool(data.get("mute", False)),
            solo=bool(data.get("solo", False)),
            velocity_scale=_velocity_scale(data.get("velocity_scale", 1.0)),
            note_count=max(0, int(data.get("note_count") or 0)),
            section_automation=[
                SectionAutomation.from_dict(item)
                for item in data.get("section_automation", [])
                if isinstance(item, dict)
            ][:256],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["section_automation"] = [item.to_dict() for item in self.section_automation]
        return data


@dataclass(frozen=True)
class MixState:
    schema_version: int
    mix_state_id: str
    project_id: str
    version_id: str
    base_song_plan_hash: str
    base_midi_hash: str
    source: dict[str, Any]
    source_hash: str
    tracks: list[MixTrackState]
    created_at: str
    updated_at: str
    integrity_hash: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MixState":
        return cls(
            schema_version=int(data.get("schema_version", MIX_STATE_SCHEMA_VERSION) or MIX_STATE_SCHEMA_VERSION),
            mix_state_id=_validate_mix_state_id(str(data.get("mix_state_id") or "mixstate-000001")),
            project_id=str(data.get("project_id") or ""),
            version_id=str(data.get("version_id") or ""),
            base_song_plan_hash=str(data.get("base_song_plan_hash") or ""),
            base_midi_hash=str(data.get("base_midi_hash") or ""),
            source=sanitize_metadata(data.get("source") if isinstance(data.get("source"), dict) else {}),
            source_hash=str(data.get("source_hash") or ""),
            tracks=[MixTrackState.from_dict(item) for item in data.get("tracks", []) if isinstance(item, dict)],
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            integrity_hash=str(data.get("integrity_hash") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mix_state_id": self.mix_state_id,
            "project_id": self.project_id,
            "version_id": self.version_id,
            "base_song_plan_hash": self.base_song_plan_hash,
            "base_midi_hash": self.base_midi_hash,
            "source": self.source,
            "source_hash": self.source_hash,
            "tracks": [track.to_dict() for track in self.tracks],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class MixPatch:
    schema_version: int
    patch_id: str
    project_id: str
    version_id: str
    base_mix_state_hash: str
    base_song_plan_hash: str
    operations: list[dict[str, Any]]
    source: dict[str, Any]
    source_hash: str
    created_at: str
    updated_at: str
    label: str = ""
    integrity_hash: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MixPatch":
        if not isinstance(data, dict):
            raise MixControlError("mix patch must be an object.")
        operations = data.get("operations")
        if not isinstance(operations, list) or not operations:
            raise MixControlError("mix patch operations must be a non-empty list.")
        if len(operations) > 200:
            raise MixControlError("mix patch supports at most 200 operations.")
        cleaned = [_clean_operation(item) for item in operations if isinstance(item, dict)]
        if len(cleaned) != len(operations):
            raise MixControlError("mix patch operations must be objects.")
        return cls(
            schema_version=int(data.get("schema_version", MIX_PATCH_SCHEMA_VERSION) or MIX_PATCH_SCHEMA_VERSION),
            patch_id=_validate_mix_patch_id(str(data.get("patch_id") or "mixpatch-000001")),
            project_id=str(data.get("project_id") or ""),
            version_id=str(data.get("version_id") or ""),
            base_mix_state_hash=str(data.get("base_mix_state_hash") or ""),
            base_song_plan_hash=str(data.get("base_song_plan_hash") or ""),
            operations=cleaned,
            source=sanitize_metadata(data.get("source") if isinstance(data.get("source"), dict) else {}),
            source_hash=str(data.get("source_hash") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            label=sanitize_sensitive_text(str(data.get("label") or ""))[:160],
            integrity_hash=str(data.get("integrity_hash") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MixPatchResult:
    state: MixState
    plan: SongPlan
    track_pans: dict[int, int]
    track_volumes: dict[int, int]
    summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class MixControlStore:
    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.root = self.project_dir / "mix"

    def version_dir(self, version_id: str) -> Path:
        version_id = _validate_version_id(version_id)
        base = self.root.resolve()
        target = (base / version_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise MixControlError("Refusing to access mix data outside project mix directory.") from exc
        return target

    def state_path(self, version_id: str) -> Path:
        return self.version_dir(version_id) / "mix-state.json"

    def patch_dir(self, version_id: str, patch_id: str) -> Path:
        patch_id = _validate_mix_patch_id(patch_id)
        base = (self.version_dir(version_id) / "patches").resolve()
        target = (base / patch_id).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise MixControlError("Refusing to access patch data outside project mix directory.") from exc
        return target

    def read_state(self, version_id: str) -> MixState:
        return MixState.from_dict(read_json(self.state_path(version_id)))

    def write_state(self, state: MixState) -> MixState:
        clean = with_mix_state_integrity(state)
        write_json(self.state_path(clean.version_id), clean.to_dict())
        return clean

    def get_or_create_state(self, *, project_id: str, version_id: str, plan: SongPlan, midi_path: Path, now: str) -> MixState:
        path = self.state_path(version_id)
        if path.exists():
            state = MixState.from_dict(read_json(path))
            if state.base_song_plan_hash == song_plan_hash(plan) and state.base_midi_hash == file_sha256(midi_path):
                return state
        state = default_mix_state(project_id=project_id, version_id=version_id, plan=plan, midi_path=midi_path, now=now)
        return self.write_state(state)

    def reset_state(self, *, project_id: str, version_id: str, plan: SongPlan, midi_path: Path, now: str) -> MixState:
        state = default_mix_state(project_id=project_id, version_id=version_id, plan=plan, midi_path=midi_path, now=now)
        return self.write_state(state)

    def reserve_patch_id(self, version_id: str) -> str:
        root = self.version_dir(version_id) / "patches"
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            patch_id = f"mixpatch-{index:06d}"
            if not (root / patch_id).exists():
                return patch_id
        raise MixControlError("Could not allocate mix patch id.")

    def write_patch(self, patch: MixPatch) -> MixPatch:
        clean = with_mix_patch_integrity(patch)
        patch_dir = self.patch_dir(clean.version_id, clean.patch_id)
        patch_dir.mkdir(parents=True, exist_ok=True)
        write_json(patch_dir / "mix-patch.json", clean.to_dict())
        return clean

    def read_patch(self, version_id: str, patch_id: str) -> MixPatch:
        return MixPatch.from_dict(read_json(self.patch_dir(version_id, patch_id) / "mix-patch.json"))


def default_mix_state(*, project_id: str, version_id: str, plan: SongPlan, midi_path: Path, now: str) -> MixState:
    source = _source_state(plan=plan, midi_path=midi_path, project_id=project_id, version_id=version_id)
    tracks = [
        MixTrackState(
            track_id=track_id_for_index(index),
            role=track_role(track.name),
            name=track.name,
            instrument=track.instrument,
            note_count=len(track.notes),
        )
        for index, track in enumerate(plan.tracks)
    ]
    state = MixState(
        schema_version=MIX_STATE_SCHEMA_VERSION,
        mix_state_id="mixstate-000001",
        project_id=project_id,
        version_id=version_id,
        base_song_plan_hash=str(source["song_plan_hash"]),
        base_midi_hash=str(source["midi_sha256"]),
        source=source,
        source_hash=stable_hash(source),
        tracks=tracks,
        created_at=now,
        updated_at=now,
    )
    return with_mix_state_integrity(state)


def build_mix_patch(
    *,
    patch_id: str,
    project_id: str,
    version_id: str,
    state: MixState,
    plan: SongPlan,
    operations: list[dict[str, Any]],
    source: dict[str, Any] | None = None,
    label: str = "",
    now: str,
) -> MixPatch:
    source = sanitize_metadata(source or {})
    patch = MixPatch(
        schema_version=MIX_PATCH_SCHEMA_VERSION,
        patch_id=patch_id,
        project_id=project_id,
        version_id=version_id,
        base_mix_state_hash=mix_state_hash(state),
        base_song_plan_hash=song_plan_hash(plan),
        operations=[_clean_operation(item) for item in operations],
        source=source,
        source_hash=stable_hash(source),
        created_at=now,
        updated_at=now,
        label=sanitize_sensitive_text(label)[:160],
    )
    return with_mix_patch_integrity(patch)


def apply_mix_patch_to_state(state: MixState, patch: MixPatch, plan: SongPlan, *, now: str) -> MixState:
    if not mix_state_integrity_ok(state):
        raise MixControlStateError("Mix state integrity failed.")
    if not mix_patch_integrity_ok(patch):
        raise MixControlStateError("Mix patch integrity failed.")
    if patch.base_mix_state_hash and patch.base_mix_state_hash != mix_state_hash(state):
        raise MixControlStateError("Mix patch is stale because the base mix state changed.")
    if patch.base_song_plan_hash and patch.base_song_plan_hash != song_plan_hash(plan):
        raise MixControlStateError("Mix patch is stale because the base SongPlan changed.")
    tracks = {track.track_id: track for track in state.tracks}
    for operation in patch.operations:
        op = str(operation.get("op") or "")
        track_id = _validate_track_id(str(operation.get("track_id") or ""))
        if op in {"set_section_track_volume_delta", "set_section_track_velocity_scale", "reset_section_track_mix"}:
            section_id = _validate_section_id(str(operation.get("section_id") or ""))
            if track_id not in tracks:
                raise MixControlError(f"Unknown track_id: {track_id}.")
            track = tracks[track_id]
            automation = {item.section_id: item for item in track.section_automation}
            current = automation.get(section_id, SectionAutomation(section_id=section_id))
            if op == "set_section_track_volume_delta":
                automation[section_id] = SectionAutomation(section_id=section_id, volume_db_delta=_volume_db_delta(operation.get("volume_db_delta")), velocity_scale=current.velocity_scale)
            elif op == "set_section_track_velocity_scale":
                automation[section_id] = SectionAutomation(section_id=section_id, volume_db_delta=current.volume_db_delta, velocity_scale=_velocity_scale(operation.get("velocity_scale")))
            else:
                automation.pop(section_id, None)
            tracks[track_id] = _replace_track(track, section_automation=[automation[key] for key in sorted(automation)])
            continue
        if track_id not in tracks:
            raise MixControlError(f"Unknown track_id: {track_id}.")
        track = tracks[track_id]
        if op == "set_track_volume":
            track = _replace_track(track, volume_db=_volume_db(operation.get("volume_db")))
        elif op == "set_track_pan":
            track = _replace_track(track, pan=_pan(operation.get("pan")))
        elif op == "set_track_mute":
            track = _replace_track(track, mute=bool(operation.get("mute", True)))
        elif op == "set_track_solo":
            track = _replace_track(track, solo=bool(operation.get("solo", True)))
        elif op == "set_track_velocity_scale":
            track = _replace_track(track, velocity_scale=_velocity_scale(operation.get("velocity_scale")))
        elif op == "reset_track_mix":
            track = _replace_track(track, volume_db=0.0, pan=0, mute=False, solo=False, velocity_scale=1.0, section_automation=[])
        tracks[track_id] = track
    ordered = [tracks[track.track_id] for track in state.tracks]
    updated = MixState(
        schema_version=state.schema_version,
        mix_state_id=state.mix_state_id,
        project_id=state.project_id,
        version_id=state.version_id,
        base_song_plan_hash=state.base_song_plan_hash,
        base_midi_hash=state.base_midi_hash,
        source=state.source,
        source_hash=state.source_hash,
        tracks=ordered,
        created_at=state.created_at,
        updated_at=now,
    )
    return with_mix_state_integrity(updated)


def apply_mix_state_to_plan(plan: SongPlan, state: MixState, *, ignore_solo: bool = False) -> tuple[SongPlan, dict[int, int], dict[int, int], dict[str, Any]]:
    tracks_by_id = {track.track_id: track for track in state.tracks}
    any_solo = any(track.solo for track in state.tracks)
    changed_tracks: list[str] = []
    muted_tracks: list[str] = []
    track_pans: dict[int, int] = {}
    track_volumes: dict[int, int] = {}
    new_tracks: list[TrackPlan] = []
    for index, track in enumerate(plan.tracks):
        track_id = track_id_for_index(index)
        mix = tracks_by_id.get(track_id)
        if mix is None:
            new_tracks.append(track)
            continue
        muted = mix.mute or (any_solo and not mix.solo and not ignore_solo)
        if muted:
            muted_tracks.append(track_id)
            track_volumes[index] = 0
        automation = {item.section_id: item for item in mix.section_automation}
        notes = [
            NoteEvent(note.pitch, note.start_beat, note.duration_beats, _scaled_velocity(note, mix, _automation_for_note(note, plan, automation)))
            for note in track.notes
        ]
        if muted or notes != track.notes:
            changed_tracks.append(track_id)
        new_tracks.append(TrackPlan(track.name, track.instrument, notes))
        track_pans[index] = pan_to_midi_cc(mix.pan)
    mixed = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, list(plan.sections), new_tracks, plan.quality)
    mixed.validate()
    return mixed, track_pans, track_volumes, {"changed_tracks": changed_tracks, "muted_tracks": muted_tracks, "solo_active": any_solo and not ignore_solo}


def apply_patch_and_render_plan(state: MixState, patch: MixPatch, plan: SongPlan, *, now: str) -> MixPatchResult:
    updated = apply_mix_patch_to_state(state, patch, plan, now=now)
    mixed_plan, track_pans, track_volumes, summary = apply_mix_state_to_plan(plan, updated)
    summary.update({"operation_count": len(patch.operations), "patch_id": patch.patch_id, "mix_state_hash": mix_state_hash(updated)})
    return MixPatchResult(state=updated, plan=mixed_plan, track_pans=track_pans, track_volumes=track_volumes, summary=summary, warnings=[])


def marker_to_mix_patch_operations(marker: dict[str, Any], review: dict[str, Any], plan: SongPlan, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = payload or {}
    text = " ".join(
        [
            str(marker.get("message") or ""),
            str(marker.get("category") or ""),
            str(review.get("notes") or ""),
        ]
    ).lower()
    mapped = marker.get("mapped") if isinstance(marker.get("mapped"), dict) else {}
    section_id = str(payload.get("section_id") or mapped.get("section_id") or "")
    operations: list[dict[str, Any]] = []
    target = _first_track(plan, preferred_roles=_roles_from_payload(payload))
    if any(token in text for token in ("鼓太大", "drums loud", "kick loud", "snare loud", "drum loud")):
        target = _first_track(plan, preferred_roles=["drums"])
        operations.append({"op": "set_track_velocity_scale", "track_id": target, "velocity_scale": 0.85})
    elif any(token in text for token in ("bass 太大", "bass太大", "bass muddy", "bass loud", "低频太大")):
        target = _first_track(plan, preferred_roles=["bass"])
        operations.append({"op": "set_track_volume", "track_id": target, "volume_db": -2.0})
    elif any(token in text for token in ("melody 太小", "melody太小", "hook weak", "hook 不够", "主旋律太小")):
        target = _first_track(plan, preferred_roles=["melody"])
        operations.append({"op": "set_track_volume", "track_id": target, "volume_db": 1.5})
    elif any(token in text for token in ("太空", "too sparse", "empty", "单薄")):
        target = _first_track(plan, preferred_roles=["chords", "pad", "harmony"])
        operations.append({"op": "set_track_volume", "track_id": target, "volume_db": 1.0})
    elif any(token in text for token in ("太吵", "too busy", "crowded", "muddy")) and section_id:
        for index, track in enumerate(plan.tracks):
            if track_role(track.name) == "melody":
                continue
            operations.append({"op": "set_section_track_velocity_scale", "track_id": track_id_for_index(index), "section_id": section_id, "velocity_scale": 0.9})
    if not operations:
        operations.append({"op": "set_track_volume", "track_id": target, "volume_db": -1.0})
    return operations[:16]


def mix_state_hash(state: MixState | dict[str, Any]) -> str:
    data = state.to_dict() if isinstance(state, MixState) else dict(state)
    return stable_hash({key: value for key, value in data.items() if key not in MIX_STATE_INTEGRITY_EXCLUDE_KEYS})


def mix_state_integrity_hash(state: MixState | dict[str, Any]) -> str:
    return mix_state_hash(state)


def mix_state_integrity_ok(state: MixState | dict[str, Any]) -> bool:
    data = state.to_dict() if isinstance(state, MixState) else dict(state)
    expected = str(data.get("integrity_hash") or "")
    return bool(expected) and expected == mix_state_integrity_hash(data)


def with_mix_state_integrity(state: MixState) -> MixState:
    data = state.to_dict()
    data["integrity_hash"] = mix_state_integrity_hash(data)
    return MixState.from_dict(data)


def mix_patch_hash(patch: MixPatch | dict[str, Any]) -> str:
    data = patch.to_dict() if isinstance(patch, MixPatch) else dict(patch)
    return stable_hash({key: value for key, value in data.items() if key not in MIX_PATCH_INTEGRITY_EXCLUDE_KEYS})


def mix_patch_integrity_ok(patch: MixPatch | dict[str, Any]) -> bool:
    data = patch.to_dict() if isinstance(patch, MixPatch) else dict(patch)
    expected = str(data.get("integrity_hash") or "")
    return bool(expected) and expected == mix_patch_hash(data)


def with_mix_patch_integrity(patch: MixPatch) -> MixPatch:
    data = patch.to_dict()
    data["integrity_hash"] = mix_patch_hash(data)
    return MixPatch.from_dict(data)


def mix_state_stale_reasons(state: MixState | dict[str, Any], *, plan: SongPlan, midi_path: Path) -> list[str]:
    data = state.to_dict() if isinstance(state, MixState) else dict(state)
    reasons = []
    if not mix_state_integrity_ok(data):
        reasons.append("mix_state_integrity")
    if data.get("base_song_plan_hash") != song_plan_hash(plan):
        reasons.append("base_song_plan_hash")
    if data.get("base_midi_hash") != file_sha256(midi_path):
        reasons.append("base_midi_hash")
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    expected_source = _source_state(plan=plan, midi_path=midi_path, project_id=str(data.get("project_id") or ""), version_id=str(data.get("version_id") or ""))
    if any(source.get(key) != value for key, value in expected_source.items()):
        reasons.append("source_state")
    if data.get("source_hash") != stable_hash(source):
        reasons.append("source_hash")
    return reasons


def source_state_for_version(*, project_id: str, version_id: str, plan_path: Path, midi_path: Path) -> dict[str, Any]:
    return _source_state(plan=SongPlan.from_dict(read_json(plan_path)), midi_path=midi_path, project_id=project_id, version_id=version_id)


def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    clean = sanitize_metadata(value)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def track_role(name: str) -> str:
    lower = str(name or "").lower()
    for role in ("melody", "chords", "bass", "drums", "pad", "harmony"):
        if role in lower:
            return role
    return re.sub(r"[^a-z0-9]+", "-", lower).strip("-") or "track"


def pan_to_midi_cc(pan: int) -> int:
    return int(round((_pan(pan) + 100) * 127 / 200))


def _source_state(*, plan: SongPlan, midi_path: Path, project_id: str, version_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "version_id": version_id,
        "song_plan_hash": song_plan_hash(plan),
        "midi_sha256": file_sha256(midi_path),
        "track_count": len(plan.tracks),
        "tracks": [{"track_id": track_id_for_index(index), "name": track.name, "role": track_role(track.name), "note_count": len(track.notes)} for index, track in enumerate(plan.tracks)],
        "sections": [{"section_id": section_id_for_index(index), "name": section.name, "start_bar": section.start_bar, "bars": section.bars} for index, section in enumerate(plan.sections)],
    }


def _clean_operation(operation: dict[str, Any]) -> dict[str, Any]:
    op = str(operation.get("op") or "").strip()
    if op not in SUPPORTED_MIX_OPS:
        raise MixControlError(f"Unsupported mix operation: {op}.")
    cleaned: dict[str, Any] = {"op": op, "track_id": _validate_track_id(str(operation.get("track_id") or ""))}
    if op == "set_track_volume":
        cleaned["volume_db"] = _volume_db(operation.get("volume_db"))
    elif op == "set_track_pan":
        cleaned["pan"] = _pan(operation.get("pan"))
    elif op == "set_track_mute":
        cleaned["mute"] = bool(operation.get("mute", True))
    elif op == "set_track_solo":
        cleaned["solo"] = bool(operation.get("solo", True))
    elif op == "set_track_velocity_scale":
        cleaned["velocity_scale"] = _velocity_scale(operation.get("velocity_scale"))
    elif op == "set_section_track_volume_delta":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
        cleaned["volume_db_delta"] = _volume_db_delta(operation.get("volume_db_delta"))
    elif op == "set_section_track_velocity_scale":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
        cleaned["velocity_scale"] = _velocity_scale(operation.get("velocity_scale"))
    elif op == "reset_section_track_mix":
        cleaned["section_id"] = _validate_section_id(str(operation.get("section_id") or ""))
    return cleaned


def _automation_for_note(note: NoteEvent, plan: SongPlan, automation: dict[str, SectionAutomation]) -> SectionAutomation | None:
    for index, section in enumerate(plan.sections):
        start = max(0, section.start_bar - 1) * 4.0
        end = start + max(0, section.bars) * 4.0
        if start <= note.start_beat < end:
            return automation.get(section_id_for_index(index))
    return None


def _scaled_velocity(note: NoteEvent, mix: MixTrackState, automation: SectionAutomation | None) -> int:
    volume_db = mix.volume_db + (automation.volume_db_delta if automation else 0.0)
    velocity_scale = mix.velocity_scale * (automation.velocity_scale if automation else 1.0)
    gain = math.pow(10.0, volume_db / 20.0)
    value = int(round(note.velocity * gain * velocity_scale))
    return max(1, min(127, value))


def _replace_track(track: MixTrackState, **changes: Any) -> MixTrackState:
    data = track.to_dict()
    data.update(changes)
    if "section_automation" in data:
        data["section_automation"] = [item.to_dict() if isinstance(item, SectionAutomation) else item for item in data["section_automation"]]
    return MixTrackState.from_dict(data)


def _first_track(plan: SongPlan, *, preferred_roles: list[str] | None = None) -> str:
    preferred = [role.lower() for role in (preferred_roles or []) if role]
    for role in preferred:
        for index, track in enumerate(plan.tracks):
            if role in track_role(track.name):
                return track_id_for_index(index)
    return track_id_for_index(0) if plan.tracks else "track-001"


def _roles_from_payload(payload: dict[str, Any]) -> list[str]:
    value = payload.get("target_roles")
    if isinstance(value, list):
        return [str(item) for item in value]
    value = payload.get("target_role")
    return [str(value)] if value else []


def _volume_db(value: Any) -> float:
    try:
        number = round(float(value), 3)
    except (TypeError, ValueError) as exc:
        raise MixControlError("volume_db must be numeric.") from exc
    if number < -36.0 or number > 12.0:
        raise MixControlError("volume_db must be between -36 and 12.")
    return number


def _volume_db_delta(value: Any) -> float:
    try:
        number = round(float(value), 3)
    except (TypeError, ValueError) as exc:
        raise MixControlError("volume_db_delta must be numeric.") from exc
    if number < -24.0 or number > 12.0:
        raise MixControlError("volume_db_delta must be between -24 and 12.")
    return number


def _pan(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MixControlError("pan must be an integer.") from exc
    if number < -100 or number > 100:
        raise MixControlError("pan must be between -100 and 100.")
    return number


def _velocity_scale(value: Any) -> float:
    try:
        number = round(float(value), 4)
    except (TypeError, ValueError) as exc:
        raise MixControlError("velocity_scale must be numeric.") from exc
    if number < 0.0 or number > 2.0:
        raise MixControlError("velocity_scale must be between 0 and 2.")
    return number


def _validate_track_id(value: str) -> str:
    if not re.match(r"^track-[0-9]{3}$", value):
        raise MixControlError("track_id must look like track-001.")
    return value


def _validate_section_id(value: str) -> str:
    if not re.match(r"^section-[0-9]{3}$", value):
        raise MixControlError("section_id must look like section-001.")
    return value


def _validate_mix_state_id(value: str) -> str:
    if not re.match(r"^mixstate-[0-9]{6}$|^mixstate-[0-9]{3}$", value):
        raise MixControlError("Invalid mix_state_id.")
    return value


def _validate_mix_patch_id(value: str) -> str:
    if not re.match(r"^mixpatch-[0-9]{6}$|^mixpatch-[0-9]{3}$", value):
        raise MixControlError("Invalid mix_patch_id.")
    return value


def _validate_version_id(value: str) -> str:
    if not re.match(r"^v[0-9]{3,}$", value):
        raise MixControlError("Invalid version_id.")
    return value
