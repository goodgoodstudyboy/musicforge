from dataclasses import replace
import pytest

from song_agent.agent.multinode_pipeline import (
    PIPELINE_NODE_ORDER,
    critic_report_for_plan,
    generate_multinode_song_plan,
    repair_song_plan,
    rerun_multinode_from_node,
)
from song_agent.node_store import NodeStore
from song_agent.provider import ProviderConfig, ProviderOutputError
from song_agent.providers.mock import MockProviderClient
from song_agent.quality import validate_song_plan
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import NoteEvent, SongPlan, SongRequest, SongSection, TrackPlan


def request() -> SongRequest:
    return SongRequest(
        title="Multinode Song",
        language="en",
        style="city pop, warm synths",
        theme="node pipeline",
        duration_seconds=60,
        tempo_bpm=92,
        key="C major",
    )


def test_multinode_pipeline_outputs_song_plan(tmp_path):
    plan = generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))

    assert plan.title == "Multinode Song"
    assert {track.name for track in plan.tracks} == {"melody", "chords", "bass", "drums"}
    assert plan.quality is not None
    assert plan.quality.scores is not None
    assert plan.quality.scores.overall >= 70
    assert "chorus" in plan.quality.hook_sections


def test_multinode_pipeline_writes_all_nodes(tmp_path):
    store = NodeStore(tmp_path)

    generate_multinode_song_plan(request(), node_store=store)

    assert [record.node for record in store.list_nodes()] == PIPELINE_NODE_ORDER
    assert store.read_node("brief_planner").output_summary["title"] == "Multinode Song"
    assert store.read_node("repair").status == "skipped"


def test_multinode_pipeline_runs_without_provider(tmp_path):
    generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))

    assert (tmp_path / "data" / "nodes" / "song_plan_builder.json").exists()


def test_multinode_pipeline_final_plan_validates(tmp_path):
    plan = generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))

    validate_song_plan(plan)


def test_multinode_pipeline_renders_midi(tmp_path):
    plan = generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))
    midi_path = tmp_path / "renders" / "song.mid"

    render_midi(plan, midi_path)

    assert midi_path.read_bytes().startswith(b"MThd")


def test_provider_brief_node_with_mock(tmp_path):
    store = NodeStore(tmp_path)

    plan = generate_multinode_song_plan(
        request(),
        provider_config=ProviderConfig(wire_api="mock", model="mock-main"),
        provider_snapshot={"mode": "provider", "wire_api": "mock", "api_key_masked": "***"},
        node_store=store,
    )

    assert plan.title == "Multinode Song"
    assert store.read_node("brief_planner").provider_snapshot["mode"] == "provider"


def test_provider_style_node_with_mock(tmp_path):
    store = NodeStore(tmp_path)

    generate_multinode_song_plan(
        request(),
        provider_config=ProviderConfig(wire_api="mock", model="mock-main"),
        provider_snapshot={"mode": "provider", "wire_api": "mock", "api_key_masked": "***"},
        node_store=store,
    )

    assert store.read_node("style_planner").output["lead_instrument"] == "lead synth"


def test_provider_node_invalid_output_fails_job(tmp_path):
    with pytest.raises(ProviderOutputError):
        generate_multinode_song_plan(
            request(),
            provider_config=ProviderConfig(wire_api="mock", model="mock-main"),
            provider_snapshot={"mode": "provider", "wire_api": "mock"},
            node_store=NodeStore(tmp_path),
            client=MockProviderClient(mode="invalid_schema"),
        )


def test_failed_provider_node_writes_failed_record(tmp_path):
    store = NodeStore(tmp_path)

    with pytest.raises(ProviderOutputError):
        generate_multinode_song_plan(
            request(),
            provider_config=ProviderConfig(wire_api="mock", model="mock-main"),
            provider_snapshot={"mode": "provider", "wire_api": "mock"},
            node_store=store,
            client=MockProviderClient(mode="invalid_schema"),
        )

    record = store.read_node("brief_planner")
    assert record.status == "failed"
    assert "brief_planner" in record.error


def test_provider_node_snapshot_is_masked(tmp_path):
    store = NodeStore(tmp_path)

    generate_multinode_song_plan(
        request(),
        provider_config=ProviderConfig(
            wire_api="mock",
            model="mock-main",
            api_key="sk-secret-value",
        ),
        provider_snapshot={
            "mode": "provider",
            "wire_api": "mock",
            "api_key_set": True,
            "api_key_masked": "sk-...alue",
        },
        node_store=store,
    )

    serialized = str(store.read_node("brief_planner").to_dict())
    assert "sk-secret-value" not in serialized
    assert "sk-...alue" in serialized


def test_rerun_multinode_from_lyric_node_reuses_upstream_nodes(tmp_path):
    store = NodeStore(tmp_path)
    generate_multinode_song_plan(request(), node_store=store)
    before_brief = store.read_node("brief_planner").started_at
    before_lyric = store.read_node("lyric_planner").started_at
    before_critic = store.read_node("critic").started_at

    plan = rerun_multinode_from_node(request(), "lyric_planner", node_store=store)

    assert plan.title == "Multinode Song"
    assert store.read_node("brief_planner").started_at == before_brief
    assert store.read_node("lyric_planner").started_at != before_lyric
    assert store.read_node("critic").started_at != before_critic
    assert store.read_node("lyric_planner").retry_count == 1
    assert store.read_node("brief_planner").retry_count == 0


def test_rerun_multinode_from_brief_rebuilds_all_nodes(tmp_path):
    store = NodeStore(tmp_path)
    generate_multinode_song_plan(request(), node_store=store)
    before = {record.node: record.started_at for record in store.list_nodes()}

    rerun_multinode_from_node(request(), "brief_planner", node_store=store)

    after = {record.node: record.started_at for record in store.list_nodes()}
    assert all(after[node] != before[node] for node in PIPELINE_NODE_ORDER)
    assert all(store.read_node(node).retry_count == 1 for node in PIPELINE_NODE_ORDER)


def test_rerun_multinode_from_harmony_rebuilds_arrangement_and_tail(tmp_path):
    store = NodeStore(tmp_path)
    generate_multinode_song_plan(request(), node_store=store)
    before = {record.node: record.started_at for record in store.list_nodes()}

    rerun_multinode_from_node(request(), "harmony_planner", node_store=store)

    assert store.read_node("style_planner").started_at == before["style_planner"]
    assert store.read_node("melody_planner").started_at == before["melody_planner"]
    for node in [
        "harmony_planner",
        "arrangement_planner",
        "critic",
        "repair",
        "song_plan_builder",
    ]:
        assert store.read_node(node).started_at != before[node]
        assert store.read_node(node).retry_count == 1


def test_rerun_multinode_from_unknown_node_fails(tmp_path):
    store = NodeStore(tmp_path)
    generate_multinode_song_plan(request(), node_store=store)

    with pytest.raises(ValueError, match="Unknown node"):
        rerun_multinode_from_node(request(), "missing_node", node_store=store)


def test_critic_detects_missing_tracks():
    plan = valid_plan()
    plan = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, [])

    report = critic_report_for_plan(plan)

    assert report.passed is False
    assert any(issue.code == "missing_tracks" for issue in report.issues)
    assert "melody" in report.dimension_scores


def test_critic_dimension_scores_match_quality_view(tmp_path):
    plan = generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))

    report = critic_report_for_plan(plan)

    assert plan.quality is not None
    assert plan.quality.scores is not None
    scores = plan.quality.scores.to_dict()
    scores.pop("overall")
    assert report.dimension_scores == scores


def test_critic_detects_invalid_note_range():
    plan = valid_plan()
    bad_track = TrackPlan("melody", "lead", [NoteEvent(128, 0, 1)])
    plan = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, [bad_track])

    report = critic_report_for_plan(plan)

    assert any(issue.code == "pitch_out_of_range" for issue in report.issues)


def test_repair_clamps_invalid_notes():
    plan = valid_plan()
    tracks = list(plan.tracks)
    tracks[0] = TrackPlan("melody", "lead", [NoteEvent(128, 0, 0, 200)])
    bad = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, tracks)

    repaired, repair = repair_song_plan(bad, critic_report_for_plan(bad))

    note = repaired.tracks[0].notes[0]
    assert note.pitch == 127
    assert note.velocity == 127
    assert note.duration_beats == 1
    assert repair.applied is True


def test_repair_records_actions():
    plan = valid_plan()
    tracks = [track for track in plan.tracks if track.name != "drums"]
    bad = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, tracks)

    _repaired, repair = repair_song_plan(bad, critic_report_for_plan(bad))

    assert any(action.action == "add_drums" for action in repair.actions)


def test_repaired_plan_validates():
    plan = valid_plan()
    tracks = [track for track in plan.tracks if track.name != "drums"]
    bad = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, tracks)

    repaired, _repair = repair_song_plan(bad, critic_report_for_plan(bad))

    validate_song_plan(repaired)


def test_repair_recomputes_quality_after_low_risk_fix(tmp_path):
    plan = generate_multinode_song_plan(request(), node_store=NodeStore(tmp_path))
    tracks = [
        replace(track, notes=[replace(note, pitch=64) for note in track.notes])
        if track.name == "melody"
        else track
        for track in plan.tracks
    ]
    bad = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, tracks)
    before = critic_report_for_plan(bad).score

    repaired, repair = repair_song_plan(bad, critic_report_for_plan(bad))

    assert repaired.quality is not None
    assert repaired.quality.scores is not None
    assert repaired.quality.scores.overall >= before
    assert any(action.action == "lift_chorus_melody" for action in repair.actions)


def valid_plan() -> SongPlan:
    sections = [SongSection("intro", 1, 1, ["Cmaj7"])]
    return SongPlan(
        title="Valid",
        key="C major",
        tempo_bpm=92,
        meter="4/4",
        sections=sections,
        tracks=[
            TrackPlan("melody", "lead", [NoteEvent(64, 0, 1)]),
            TrackPlan("chords", "keys", [NoteEvent(60, 0, 1)]),
            TrackPlan("bass", "bass", [NoteEvent(36, 0, 1)]),
            TrackPlan("drums", "gm drums", [NoteEvent(36, 0, 0.25)]),
        ],
    )
