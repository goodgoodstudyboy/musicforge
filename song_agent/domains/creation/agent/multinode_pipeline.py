# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from copy import deepcopy as deepcopy
from dataclasses import replace as replace
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any, Callable as Callable

from song_agent.domains.creation.agent.pipeline import _make_bass_notes as _make_bass_notes, _make_chord_notes as _make_chord_notes, _make_drum_notes as _make_drum_notes, _make_drum_notes_for_sections as _make_drum_notes_for_sections, _make_melody as _make_melody, _make_melody_for_sections as _make_melody_for_sections
from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, attach_quality as attach_quality, quality_issues_for_plan as quality_issues_for_plan, repair_quality_metadata as repair_quality_metadata
from song_agent.domains.creation.agent.provider_pipeline import _client_for_config as _client_for_config
from song_agent.domains.creation.node_graph import NODE_DEPENDENCIES as NODE_DEPENDENCIES, affected_nodes_for_retry as affected_nodes_for_retry
from song_agent.domains.creation.node_store import NodeRecord as NodeRecord, NodeStore as NodeStore, PIPELINE_NODE_ORDER as PIPELINE_NODE_ORDER
from song_agent.domains.creation.provider import ProviderConfig as ProviderConfig, ProviderOutputError as ProviderOutputError
from song_agent.domains.quality.quality import REQUIRED_TRACKS as REQUIRED_TRACKS, validate_song_plan as validate_song_plan
from song_agent.domains.creation.schemas.agent_nodes import ArrangementPlan as ArrangementPlan, ArrangementTrack as ArrangementTrack, CriticIssue as CriticIssue, CriticReport as CriticReport, HarmonyPlan as HarmonyPlan, LyricPlan as LyricPlan, LyricSection as LyricSection, MelodyPhrase as MelodyPhrase, MelodyPlan as MelodyPlan, RepairAction as RepairAction, RepairPlan as RepairPlan, SectionHarmony as SectionHarmony, SongBrief as SongBrief, SonicPalette as SonicPalette, StructurePlan as StructurePlan, StructureSectionPlan as StructureSectionPlan
from song_agent.domains.creation.schemas.song import MotifPlan as MotifPlan, NoteEvent as NoteEvent, SongPlan as SongPlan, SongRequest as SongRequest, SongSection as SongSection, TrackPlan as TrackPlan


ControlFn = Callable[[str, str], None]
PROVIDER_BACKED_NODES = {
    "brief_planner",
    "style_planner",
    "structure_planner",
    "lyric_planner",
    "harmony_planner",
}
NODE_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "nodes"


def generate_multinode_song_plan(
    request: SongRequest,
    *,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: DomainDocument | None = None,
    node_store: NodeStore,
    control: ControlFn | None = None,
    client: Any | None = None,
) -> SongPlan:
    return _run_multinode_pipeline(
        request,
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        node_store=node_store,
        control=control,
        client=client,
        rerun_from_node=None,
    )


def rerun_multinode_from_node(
    request: SongRequest,
    node_name: str,
    *,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: DomainDocument | None = None,
    node_store: NodeStore,
    control: ControlFn | None = None,
    client: Any | None = None,
) -> SongPlan:
    return _run_multinode_pipeline(
        request,
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        node_store=node_store,
        control=control,
        client=client,
        rerun_from_node=node_name,
    )


def _run_multinode_pipeline(
    request: SongRequest,
    *,
    provider_config: ProviderConfig | None,
    provider_snapshot: ImplementationDocument | None,
    node_store: NodeStore,
    control: ControlFn | None,
    client: Any | None,
    rerun_from_node: str | None,
) -> SongPlan:
    client = client or (_client_for_config(provider_config) if provider_config is not None else None)
    affected_nodes = (
        set(PIPELINE_NODE_ORDER)
        if rerun_from_node is None
        else set(affected_nodes_for_retry(rerun_from_node))
    )
    retrying = rerun_from_node is not None

    brief = _schema_node_value(
        "brief_planner",
        SongBrief,
        lambda: build_song_brief(request),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"request_title": request.title},
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input={"request": request.to_dict()},
        client=client,
        control=control,
    )
    palette = _schema_node_value(
        "style_planner",
        SonicPalette,
        lambda: build_sonic_palette(brief),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"style": brief.style},
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input={"brief": brief.to_dict()},
        client=client,
        control=control,
    )
    structure = _schema_node_value(
        "structure_planner",
        StructurePlan,
        lambda: build_structure_plan(brief),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"duration_seconds": brief.duration_seconds},
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input={"brief": brief.to_dict(), "palette": palette.to_dict()},
        client=client,
        control=control,
    )
    lyric_plan = _schema_node_value(
        "lyric_planner",
        LyricPlan,
        lambda: build_lyric_plan(request, brief, structure),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"language": brief.language, "vocal_mode": brief.vocal_mode},
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input={"brief": brief.to_dict(), "structure": structure.to_dict()},
        client=client,
        control=control,
    )
    harmony = _schema_node_value(
        "harmony_planner",
        HarmonyPlan,
        lambda: build_harmony_plan(brief, structure),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"key": brief.key, "sections": len(structure.sections)},
        provider_config=provider_config,
        provider_snapshot=provider_snapshot,
        provider_input={"brief": brief.to_dict(), "structure": structure.to_dict()},
        client=client,
        control=control,
    )
    sections = build_song_sections(structure, harmony, lyric_plan)
    melody = _schema_node_value(
        "melody_planner",
        MelodyPlan,
        lambda: build_melody_plan(palette, sections),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"sections": len(sections)},
        provider_config=None,
        provider_snapshot=None,
        provider_input={},
        client=None,
        control=control,
    )
    arrangement = _schema_node_value(
        "arrangement_planner",
        ArrangementPlan,
        lambda: build_arrangement_plan(palette, structure, sections, melody),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        request=request,
        input_summary={"phrases": len(melody.phrases)},
        provider_config=None,
        provider_snapshot=None,
        provider_input={},
        client=None,
        control=control,
    )
    draft_plan = build_song_plan(brief, structure, harmony, lyric_plan, arrangement)
    critic = _node_value(
        "critic",
        CriticReport,
        lambda: critic_report_for_plan(draft_plan),
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        input_summary={"track_count": len(draft_plan.tracks)},
        output_summary=lambda report: {
            "passed": report.passed,
            "score": report.score,
            "issue_count": len(report.issues),
        },
        provider_snapshot={"mode": "local", "summary": "Deterministic critic"},
        control=control,
    )
    repaired_plan, draft_repair_plan = repair_song_plan(draft_plan, critic)
    repair_plan = _node_value(
        "repair",
        RepairPlan,
        lambda: draft_repair_plan,
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        input_summary={"critic_passed": critic.passed, "issue_count": len(critic.issues)},
        output_summary=lambda plan: {
            "applied": plan.applied,
            "action_count": len(plan.actions),
        },
        provider_snapshot={"mode": "local", "summary": "Deterministic repair"},
        control=control,
        success_status="repaired" if draft_repair_plan.applied else "skipped",
    )
    if repair_plan.applied:
        repaired_plan, _repair_for_builder = repair_song_plan(draft_plan, critic)
    final_plan = _node_value(
        "song_plan_builder",
        SongPlan,
        lambda: repaired_plan,
        affected_nodes=affected_nodes,
        retrying=retrying,
        node_store=node_store,
        input_summary={"repair_applied": repair_plan.applied},
        output_summary=lambda plan: _song_plan_summary(plan),
        provider_snapshot={"mode": "local", "summary": "SongPlan builder"},
        control=control,
    )
    validate_song_plan(final_plan)
    return final_plan


def build_song_brief(request: SongRequest) -> SongBrief:
    return SongBrief(
        title=request.title,
        language=request.language,
        style=request.style,
        theme=request.theme,
        duration_seconds=request.duration_seconds,
        vocal_mode=request.vocal_mode,
        tempo_bpm=request.tempo_bpm or 92,
        key=request.key or "C major",
        target_listener=None,
        use_case="local demo",
        mood_tags=_style_tags(request.style)[:4],
        must_include=[],
        avoid=[],
    )


def build_sonic_palette(brief: SongBrief) -> SonicPalette:
    tags = _style_tags(brief.style) or ["pop"]
    lead = "lead synth" if any("synth" in tag for tag in tags) else "lead"
    bass_style = "electric bass"
    if any("lo-fi" in tag or "hip hop" in tag for tag in tags):
        bass_style = "round sub bass"
    drum_style = "tight acoustic kit"
    if any("game" in tag for tag in tags):
        drum_style = "punchy electronic kit"
    return SonicPalette(
        genre_tags=tags,
        instrumentation=[lead, "electric piano", bass_style, "gm drums"],
        lead_instrument=lead,
        bass_style=bass_style,
        drum_style=drum_style,
        texture_notes=f"Theme focus: {brief.theme}",
        mix_notes="Keep the arrangement clear enough for MIDI inspection.",
    )


def build_structure_plan(brief: SongBrief) -> StructurePlan:
    return StructurePlan(
        meter="4/4",
        sections=[
            StructureSectionPlan("intro", 1, 4, 2, "establish the groove", 2, 2, "establish", "open into verse", False),
            StructureSectionPlan("verse", 5, 8, 4, "state the main idea", 4, 4, "narrative", "build toward hook", False),
            StructureSectionPlan("chorus", 13, 8, 7, "raise energy and hook", 6, 7, "hook", "land the hook", True),
            StructureSectionPlan("outro", 21, 4, 3, "resolve the loop", 2, 3, "resolve", "reduce density", False),
        ],
    )


def build_lyric_plan(
    request: SongRequest,
    brief: SongBrief,
    structure: StructurePlan,
) -> LyricPlan:
    if brief.vocal_mode == "instrumental":
        return LyricPlan(language="instrumental", rhyme_style="none", sections=[])
    sections: list[LyricSection] = []
    for section in structure.sections:
        lyrics = request.lyrics if section.name == "verse" and request.lyrics else None
        sections.append(
            LyricSection(
                section_name=section.name,
                lyrics=lyrics,
                syllable_notes="guide melody follows two-beat motif",
            )
        )
    return LyricPlan(language=brief.language, rhyme_style="loose", sections=sections)


def build_harmony_plan(brief: SongBrief, structure: StructurePlan) -> HarmonyPlan:
    chords = ["Cmaj7", "Am7", "Dm7", "G7"]
    return HarmonyPlan(
        key=brief.key,
        progressions=[
            SectionHarmony(section_name=section.name, chords=chords)
            for section in structure.sections
        ],
    )


def build_song_sections(
    structure: StructurePlan,
    harmony: HarmonyPlan,
    lyric_plan: LyricPlan,
) -> list[SongSection]:
    harmony_by_section = {
        progression.section_name: progression.chords for progression in harmony.progressions
    }
    lyrics_by_section = {
        section.section_name: section.lyrics for section in lyric_plan.sections
    }
    return [
        SongSection(
            name=section.name,
            start_bar=section.start_bar,
            bars=section.bars,
            chords=harmony_by_section.get(section.name, ["Cmaj7", "Am7", "Dm7", "G7"]),
            lyrics=lyrics_by_section.get(section.name),
        )
        for section in structure.sections
    ]


def build_melody_plan(palette: SonicPalette, sections: list[SongSection]) -> MelodyPlan:
    phrases: list[MelodyPhrase] = []
    all_notes = _make_melody_for_sections(sections)
    primary_motif = MotifPlan(
        name="primary hook",
        description="A two-bar rising and falling guide phrase reused across sections.",
        rhythm_pattern=[1.5, 1.5, 1.5, 1.5],
        pitch_intervals=[0, 3, 2, 2, -1, -2],
        anchor_section="chorus",
    )
    for section in sections:
        start = (section.start_bar - 1) * 4
        end = start + section.bars * 4
        lower_name = section.name.lower()
        phrases.append(
            MelodyPhrase(
                section_name=section.name,
                notes=[
                    note
                    for note in all_notes
                    if note.start_beat >= start and note.start_beat < end
                ],
                motif_name=primary_motif.name,
                contour="rising" if "chorus" in lower_name else "arch" if "verse" in lower_name else "mixed",
                phrase_role="hook" if "chorus" in lower_name else "support",
            )
        )
    return MelodyPlan(
        lead_instrument=palette.lead_instrument,
        phrases=phrases,
        primary_motif=primary_motif,
        hook_phrase_section="chorus",
    )


def build_arrangement_plan(
    palette: SonicPalette,
    structure: StructurePlan,
    sections: list[SongSection],
    melody: MelodyPlan,
) -> ArrangementPlan:
    melody_notes = [
        note for phrase in melody.phrases for note in phrase.notes
    ]
    section_behavior = {
        section.name: _arrangement_behavior(section)
        for section in structure.sections
    }
    return ArrangementPlan(
        tracks=[
            ArrangementTrack(
                name="melody",
                instrument=melody.lead_instrument,
                role="melody",
                notes=melody_notes,
                density=5,
                section_behavior=section_behavior,
            ),
            ArrangementTrack(
                name="chords",
                instrument="electric piano",
                role="chords",
                notes=_make_chord_notes(sections),
                density=5,
                section_behavior=section_behavior,
            ),
            ArrangementTrack(
                name="bass",
                instrument=palette.bass_style or "electric bass",
                role="bass",
                notes=_make_bass_notes(sections),
                density=5,
                section_behavior=section_behavior,
            ),
            ArrangementTrack(
                name="drums",
                instrument="gm drums",
                role="drums",
                notes=_make_drum_notes_for_sections(sections),
                density=6,
                section_behavior=section_behavior,
            ),
        ]
    )


def _arrangement_behavior(section: StructureSectionPlan) -> str:
    if section.hook_candidate or "chorus" in section.name.lower():
        return "full backbeat with lifted melody"
    if "intro" in section.name.lower():
        return "sparse groove"
    if "outro" in section.name.lower():
        return "reduce density and resolve"
    return "steady support"


def build_song_plan(
    brief: SongBrief,
    structure: StructurePlan,
    harmony: HarmonyPlan,
    lyric_plan: LyricPlan,
    arrangement: ArrangementPlan,
) -> SongPlan:
    sections = build_song_sections(structure, harmony, lyric_plan)
    plan = SongPlan(
        title=brief.title,
        key=harmony.key,
        tempo_bpm=brief.tempo_bpm,
        meter=structure.meter,
        sections=sections,
        tracks=[
            TrackPlan(
                name=track.name,
                instrument=track.instrument,
                notes=track.notes,
            )
            for track in arrangement.tracks
        ],
    )
    return attach_quality(plan)


from song_agent.domains.creation.agent import v142_mp_readiness as _v142_mp_readiness
from song_agent.domains.creation.agent.v142_mp_readiness import (
    critic_report_for_plan,
    repair_song_plan,
    load_node_prompt,
    _run_schema_node,
    _schema_node_value,
    _node_value,
    _run_node,
    _next_node_counts,
    _node_provider_snapshot,
    _node_output_summary,
    _song_plan_summary,
    _style_tags,
    _issue,
    _track_role,
    _clamp_int,
    _utc_now,
)

































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

_v142_mp_readiness.bind_globals(globals())
