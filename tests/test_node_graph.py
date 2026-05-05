import pytest

from song_agent.node_graph import affected_nodes_for_retry, downstream_nodes, upstream_nodes


def test_downstream_nodes_for_brief_includes_all_dependents():
    assert downstream_nodes("brief_planner") == [
        "style_planner",
        "structure_planner",
        "lyric_planner",
        "harmony_planner",
        "melody_planner",
        "arrangement_planner",
        "critic",
        "repair",
        "song_plan_builder",
    ]


def test_downstream_nodes_for_critic_only_rebuilds_tail():
    assert downstream_nodes("critic") == ["repair", "song_plan_builder"]
    assert affected_nodes_for_retry("critic") == ["critic", "repair", "song_plan_builder"]


def test_upstream_nodes_for_lyric_planner():
    assert upstream_nodes("lyric_planner") == ["brief_planner", "structure_planner"]


def test_harmony_retry_rebuilds_arrangement_and_tail():
    assert "harmony_planner" in upstream_nodes("arrangement_planner")
    assert affected_nodes_for_retry("harmony_planner") == [
        "harmony_planner",
        "arrangement_planner",
        "critic",
        "repair",
        "song_plan_builder",
    ]


def test_unknown_node_rejected():
    with pytest.raises(ValueError, match="Unknown node"):
        downstream_nodes("missing_node")
