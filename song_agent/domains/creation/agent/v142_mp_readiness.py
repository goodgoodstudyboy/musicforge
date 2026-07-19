# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.documents import DomainDocument
from copy import deepcopy as deepcopy
from dataclasses import replace as replace
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Callable as Callable, Protocol as Protocol, TypeVar as TypeVar
from song_agent.domains.creation.agent.pipeline import _make_bass_notes as _make_bass_notes, _make_chord_notes as _make_chord_notes, _make_drum_notes as _make_drum_notes, _make_drum_notes_for_sections as _make_drum_notes_for_sections, _make_melody as _make_melody, _make_melody_for_sections as _make_melody_for_sections
from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, attach_quality as attach_quality, quality_issues_for_plan as quality_issues_for_plan, repair_quality_metadata as repair_quality_metadata
from song_agent.domains.creation.agent.provider_pipeline import _client_for_config as _client_for_config
from song_agent.domains.creation.node_graph import NODE_DEPENDENCIES as NODE_DEPENDENCIES, affected_nodes_for_retry as affected_nodes_for_retry
from song_agent.domains.creation.node_store import NodeRecord as NodeRecord, NodeStore as NodeStore, PIPELINE_NODE_ORDER as PIPELINE_NODE_ORDER
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig, ProviderOutputError as ProviderOutputError
from song_agent.domains.quality.quality import REQUIRED_TRACKS as REQUIRED_TRACKS, validate_song_plan as validate_song_plan
from song_agent.domains.creation.schemas.agent_nodes import ArrangementPlan as ArrangementPlan, ArrangementTrack as ArrangementTrack, CriticIssue as CriticIssue, CriticReport as CriticReport, HarmonyPlan as HarmonyPlan, LyricPlan as LyricPlan, LyricSection as LyricSection, MelodyPhrase as MelodyPhrase, MelodyPlan as MelodyPlan, RepairAction as RepairAction, RepairPlan as RepairPlan, SectionHarmony as SectionHarmony, SongBrief as SongBrief, SonicPalette as SonicPalette, StructurePlan as StructurePlan, StructureSectionPlan as StructureSectionPlan
from song_agent.domains.creation.schemas.song import MotifPlan as MotifPlan, NoteEvent as NoteEvent, SongPlan as SongPlan, SongRequest as SongRequest, SongSection as SongSection, TrackPlan as TrackPlan

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

NODE_PROMPT_DIR = _make_deferred_global('NODE_PROMPT_DIR')
existing = _make_deferred_global('existing')
issue = _make_deferred_global('issue')
phrase = _make_deferred_global('phrase')
section = _make_deferred_global('section')
tag = _make_deferred_global('tag')

def bind_globals(namespace: dict[str, object]) -> None:
    global NODE_PROMPT_DIR, existing, issue, phrase, section, tag
    NODE_PROMPT_DIR = namespace.get('NODE_PROMPT_DIR', NODE_PROMPT_DIR)
    existing = namespace.get('existing', existing)
    issue = namespace.get('issue', issue)
    phrase = namespace.get('phrase', phrase)
    section = namespace.get('section', section)
    tag = namespace.get('tag', tag)
    _bind_deferred_defaults(namespace)


ControlFn = Callable[[str, str], None]
_NodeValueT = TypeVar("_NodeValueT")


class _NodeSchema(Protocol[_NodeValueT]):
    @classmethod
    def from_dict(cls, data: DomainDocument) -> _NodeValueT:
        ...


PROVIDER_BACKED_NODES = {
    "brief_planner",
    "style_planner",
    "structure_planner",
    "lyric_planner",
    "harmony_planner",
}
__all__ = [
    "PIPELINE_NODE_ORDER",
    "PROVIDER_BACKED_NODES",
    "build_arrangement_plan",
    "build_harmony_plan",
    "build_lyric_plan",
    "build_melody_plan",
    "build_song_brief",
    "build_song_plan",
    "build_song_sections",
    "build_sonic_palette",
    "build_structure_plan",
    "critic_report_for_plan",
    "generate_multinode_song_plan",
    "load_node_prompt",
    "repair_song_plan",
    "rerun_multinode_from_node",
]




def critic_report_for_plan(plan: SongPlan) -> CriticReport:
    issues: list[CriticIssue] = []
    if not plan.sections:
        issues.append(_issue("error", "missing_sections", "SongPlan has no sections.", "sections"))
    if not plan.tracks:
        issues.append(_issue("error", "missing_tracks", "SongPlan has no tracks.", "tracks"))

    normalized_roles = {_track_role(track.name) for track in plan.tracks}
    for role in sorted(REQUIRED_TRACKS - normalized_roles):
        issues.append(
            _issue("error", f"missing_{role}", f"SongPlan is missing {role}.", "tracks")
        )

    total_bars = sum(section.bars for section in plan.sections)
    total_beats = total_bars * 4
    for track_index, track in enumerate(plan.tracks):
        if not track.notes:
            issues.append(
                _issue(
                    "error",
                    "empty_track",
                    f"Track {track.name} has no notes.",
                    f"tracks.{track_index}.notes",
                )
            )
        for note_index, note in enumerate(track.notes):
            target = f"tracks.{track_index}.notes.{note_index}"
            if note.pitch < 0 or note.pitch > 127:
                issues.append(_issue("error", "pitch_out_of_range", "Pitch is outside 0..127.", target))
            if note.velocity < 1 or note.velocity > 127:
                issues.append(
                    _issue("error", "velocity_out_of_range", "Velocity is outside 1..127.", target)
                )
            if note.duration_beats <= 0:
                issues.append(
                    _issue("error", "non_positive_duration", "Duration must be positive.", target)
                )
            if total_beats and note.start_beat + note.duration_beats > total_beats + 0.001:
                issues.append(
                    _issue("error", "note_beyond_song", "Note extends beyond song length.", target)
                )

    score = max(0, 100 - len([issue for issue in issues if issue.severity == "error"]) * 20)
    quality = analyze_song_quality(plan)
    quality_issues = quality_issues_for_plan(plan)
    issues.extend(
        issue
        for issue in quality_issues
        if issue.code not in {existing.code for existing in issues}
    )
    score = quality.scores.overall if quality.scores else score
    dimension_scores = quality.scores.to_dict() if quality.scores else {}
    dimension_scores.pop("overall", None)
    return CriticReport(
        passed=not any(issue.severity == "error" for issue in issues),
        score=score,
        issues=issues,
        dimension_scores=dimension_scores,
        summary=quality.summary,
    )

def repair_song_plan(plan: SongPlan, critic: CriticReport) -> tuple[SongPlan, RepairPlan]:
    repaired = deepcopy(plan)
    actions: list[RepairAction] = []

    tracks = list(repaired.tracks)
    normalized_roles = {_track_role(track.name) for track in tracks}
    total_bars = sum(section.bars for section in repaired.sections) or 1
    if "bass" not in normalized_roles:
        tracks.append(TrackPlan("bass", "electric bass", _make_bass_notes(repaired.sections)))
        actions.append(RepairAction("tracks", "add_bass", "SongPlan was missing bass."))
    if "drums" not in normalized_roles:
        tracks.append(TrackPlan("drums", "gm drums", _make_drum_notes(total_bars)))
        actions.append(RepairAction("tracks", "add_drums", "SongPlan was missing drums."))

    fixed_tracks: list[TrackPlan] = []
    for track_index, track in enumerate(tracks):
        fixed_notes: list[NoteEvent] = []
        for note_index, note in enumerate(track.notes):
            fixed_note = note
            if fixed_note.pitch < 0 or fixed_note.pitch > 127:
                fixed_note = replace(fixed_note, pitch=_clamp_int(fixed_note.pitch, 0, 127))
                actions.append(
                    RepairAction(
                        f"tracks.{track_index}.notes.{note_index}.pitch",
                        "clamp",
                        "Pitch was outside 0..127.",
                    )
                )
            if fixed_note.velocity < 1 or fixed_note.velocity > 127:
                fixed_note = replace(fixed_note, velocity=_clamp_int(fixed_note.velocity, 1, 127))
                actions.append(
                    RepairAction(
                        f"tracks.{track_index}.notes.{note_index}.velocity",
                        "clamp",
                        "Velocity was outside 1..127.",
                    )
                )
            if fixed_note.duration_beats <= 0:
                fixed_note = replace(fixed_note, duration_beats=1)
                actions.append(
                    RepairAction(
                        f"tracks.{track_index}.notes.{note_index}.duration_beats",
                        "set_duration",
                        "Duration was non-positive.",
                    )
                )
            fixed_notes.append(fixed_note)
        fixed_tracks.append(
            TrackPlan(name=track.name, instrument=track.instrument, notes=fixed_notes)
        )

    repaired = SongPlan(
        title=repaired.title,
        key=repaired.key,
        tempo_bpm=repaired.tempo_bpm,
        meter=repaired.meter,
        sections=repaired.sections,
        tracks=fixed_tracks,
        quality=repaired.quality,
    )
    repaired, quality_actions = repair_quality_metadata(repaired)
    for action in quality_actions:
        actions.append(RepairAction("quality", action, "Applied low-risk quality metadata repair."))
    return repaired, RepairPlan(applied=bool(actions), actions=actions)

def load_node_prompt(node_name: str) -> str:
    path = NODE_PROMPT_DIR / f"{node_name}.md"
    return path.read_text(encoding="utf-8")

def _run_schema_node(
    node_name: str,
    schema: _NodeSchema[_NodeValueT],
    deterministic: Callable[[], _NodeValueT],
    *,
    node_store: NodeStore,
    request: SongRequest,
    input_summary: DomainDocument,
    provider_config: ProviderConfig | None,
    provider_snapshot: DomainDocument | None,
    provider_input: DomainDocument,
    client: object | None,
    control: ControlFn | None,
    retrying: bool = False,
) -> _NodeValueT:
    def produce() -> _NodeValueT:
        if provider_config is None or node_name not in PROVIDER_BACKED_NODES:
            return deterministic()
        if client is None:
            raise ProviderOutputError("Provider client is required for provider-backed nodes.")
        try:
            data = client.generate_node_json(
                node_name,
                provider_input,
                provider_config,
                load_node_prompt(node_name),
            )
            return schema.from_dict(data)
        except ProviderOutputError:
            raise
        except ValueError as exc:
            raise ProviderOutputError(
                f"Provider node {node_name} output did not match schema: {exc}"
            ) from exc

    return _run_node(
        node_name,
        produce,
        node_store=node_store,
        input_summary=input_summary,
        output_summary=_node_output_summary,
        provider_snapshot=_node_provider_snapshot(
            node_name,
            request,
            provider_config,
            provider_snapshot,
        ),
        control=control,
        retrying=retrying,
    )

def _schema_node_value(
    node_name: str,
    schema: _NodeSchema[_NodeValueT],
    deterministic: Callable[[], _NodeValueT],
    *,
    affected_nodes: set[str],
    retrying: bool,
    node_store: NodeStore,
    request: SongRequest,
    input_summary: DomainDocument,
    provider_config: ProviderConfig | None,
    provider_snapshot: DomainDocument | None,
    provider_input: DomainDocument,
    client: object | None,
    control: ControlFn | None,
) -> _NodeValueT:
    if retrying and node_name not in affected_nodes:
        return schema.from_dict(node_store.read_required_output(node_name))
    return _run_schema_node(
        node_name,
        schema,
        deterministic,
        node_store=node_store,
        request=request,
        input_summary=input_summary,
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input=provider_input,
        client=client,
        control=control,
        retrying=retrying,
    )

def _node_value(
    node_name: str,
    schema: _NodeSchema[_NodeValueT],
    produce: Callable[[], _NodeValueT],
    *,
    affected_nodes: set[str],
    retrying: bool,
    node_store: NodeStore,
    input_summary: DomainDocument,
    output_summary: Callable[[_NodeValueT], DomainDocument],
    provider_snapshot: DomainDocument,
    control: ControlFn | None,
    success_status: str = "completed",
) -> _NodeValueT:
    if retrying and node_name not in affected_nodes:
        return schema.from_dict(node_store.read_required_output(node_name))
    return _run_node(
        node_name,
        produce,
        node_store=node_store,
        input_summary=input_summary,
        output_summary=output_summary,
        provider_snapshot=provider_snapshot,
        control=control,
        success_status=success_status,
        retrying=retrying,
    )

def _run_node(
    node_name: str,
    produce: Callable[[], _NodeValueT],
    *,
    node_store: NodeStore,
    input_summary: DomainDocument,
    output_summary: Callable[[_NodeValueT], DomainDocument],
    provider_snapshot: DomainDocument,
    control: ControlFn | None,
    success_status: str = "completed",
    retrying: bool = False,
) -> _NodeValueT:
    if control is not None:
        control("before_node", node_name)
    started_at = _utc_now()
    attempt_count, retry_count, last_error = _next_node_counts(
        node_store,
        node_name,
        retrying=retrying,
    )
    node_store.write_node(
        NodeRecord(
            node=node_name,
            status="running",
            started_at=started_at,
            attempt_count=attempt_count,
            provider_snapshot=provider_snapshot,
            input_summary=input_summary,
            retry_count=retry_count,
            last_error=last_error,
            depends_on=NODE_DEPENDENCIES.get(node_name, []),
        )
    )
    try:
        output = produce()
        output_data = output.to_dict() if hasattr(output, "to_dict") else output
        record = NodeRecord(
            node=node_name,
            status=success_status,
            started_at=started_at,
            finished_at=_utc_now(),
            attempt_count=attempt_count,
            provider_snapshot=provider_snapshot,
            input_summary=input_summary,
            output_summary=output_summary(output),
            output=output_data,
            retry_count=retry_count,
            last_error=last_error,
            depends_on=NODE_DEPENDENCIES.get(node_name, []),
        )
        node_store.write_node(record)
    except Exception as exc:
        node_store.write_node(
            NodeRecord(
                node=node_name,
                status="failed",
                started_at=started_at,
                finished_at=_utc_now(),
                attempt_count=attempt_count,
                provider_snapshot=provider_snapshot,
                input_summary=input_summary,
                error=str(exc),
                retry_count=retry_count,
                last_error=last_error,
                depends_on=NODE_DEPENDENCIES.get(node_name, []),
            )
        )
        raise
    if control is not None:
        control("after_node", node_name)
    return output

def _next_node_counts(
    node_store: NodeStore,
    node_name: str,
    *,
    retrying: bool,
) -> tuple[int, int, str | None]:
    try:
        previous = node_store.read_node(node_name)
    except FileNotFoundError:
        return 1, 0, None
    attempt_count = previous.attempt_count + 1
    retry_count = previous.retry_count + 1 if retrying else previous.retry_count
    last_error = previous.error or previous.last_error
    return attempt_count, retry_count, last_error

def _node_provider_snapshot(
    node_name: str,
    request: SongRequest,
    provider_config: ProviderConfig | None,
    provider_snapshot: DomainDocument | None,
) -> DomainDocument:
    if provider_config is not None and node_name in PROVIDER_BACKED_NODES:
        return provider_snapshot or provider_config.to_snapshot("provider", _utc_now())
    return {
        "mode": "local",
        "summary": "Deterministic node",
        "request_title": request.title,
    }

def _node_output_summary(output: object) -> DomainDocument:
    if isinstance(output, SongBrief):
        return {"title": output.title, "tempo_bpm": output.tempo_bpm, "key": output.key}
    if isinstance(output, SonicPalette):
        return {
            "genre_count": len(output.genre_tags),
            "instrument_count": len(output.instrumentation),
            "lead_instrument": output.lead_instrument,
        }
    if isinstance(output, StructurePlan):
        return {"meter": output.meter, "section_count": len(output.sections)}
    if isinstance(output, LyricPlan):
        return {"language": output.language, "section_count": len(output.sections)}
    if isinstance(output, HarmonyPlan):
        return {"key": output.key, "section_count": len(output.progressions)}
    if isinstance(output, MelodyPlan):
        return {
            "lead_instrument": output.lead_instrument,
            "phrase_count": len(output.phrases),
            "note_count": sum(len(phrase.notes) for phrase in output.phrases),
        }
    if isinstance(output, ArrangementPlan):
        return {
            "track_count": len(output.tracks),
            "note_count": sum(len(track.notes) for track in output.tracks),
        }
    return {}

def _song_plan_summary(plan: SongPlan) -> DomainDocument:
    return {
        "title": plan.title,
        "tempo_bpm": plan.tempo_bpm,
        "key": plan.key,
        "section_count": len(plan.sections),
        "track_count": len(plan.tracks),
        "note_count": sum(len(track.notes) for track in plan.tracks),
    }

def _style_tags(style: str) -> list[str]:
    return [tag.strip().lower() for tag in style.split(",") if tag.strip()]

def _issue(severity: str, code: str, message: str, target: str | None = None) -> CriticIssue:
    return CriticIssue(severity=severity, code=code, message=message, target=target)

def _track_role(name: str) -> str:
    lower_name = name.lower()
    for role in REQUIRED_TRACKS:
        if role in lower_name:
            return role
    return lower_name.strip()

def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
