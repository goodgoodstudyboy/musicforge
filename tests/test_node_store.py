import pytest

from song_agent.node_store import NodeRecord, NodeStore


def test_node_store_writes_and_reads_node(tmp_path):
    store = NodeStore(tmp_path)
    record = NodeRecord(
        node="brief_planner",
        status="completed",
        output_summary={"title": "Node Song"},
        output={"title": "Node Song"},
    )

    path = store.write_node(record)
    restored = store.read_node("brief_planner")

    assert path == tmp_path / "data" / "nodes" / "brief_planner.json"
    assert restored.node == "brief_planner"
    assert restored.output["title"] == "Node Song"


def test_node_store_lists_nodes_in_pipeline_order(tmp_path):
    store = NodeStore(tmp_path)
    store.write_node(NodeRecord(node="critic", status="completed"))
    store.write_node(NodeRecord(node="brief_planner", status="completed"))
    store.write_node(NodeRecord(node="style_planner", status="completed"))

    assert [record.node for record in store.list_nodes()] == [
        "brief_planner",
        "style_planner",
        "critic",
    ]


def test_node_store_rejects_path_traversal(tmp_path):
    store = NodeStore(tmp_path)

    with pytest.raises(ValueError):
        store.read_node("../song-plan")


def test_node_store_rejects_invalid_node_name(tmp_path):
    store = NodeStore(tmp_path)

    with pytest.raises(ValueError):
        store.write_node(NodeRecord(node="Brief Planner", status="completed"))


def test_node_store_invalidates_downstream_nodes(tmp_path):
    store = NodeStore(tmp_path)
    store.write_node(
        NodeRecord(
            node="lyric_planner",
            status="completed",
            output={"language": "en", "rhyme_style": "loose", "sections": []},
            retry_count=1,
            depends_on=["brief_planner", "structure_planner"],
        )
    )
    store.write_node(NodeRecord(node="critic", status="completed", output={"passed": True}))

    invalidated = store.invalidate_nodes(
        ["lyric_planner", "critic"],
        invalidated_by="lyric_planner",
    )

    assert [record.node for record in invalidated] == ["lyric_planner", "critic"]
    lyric = store.read_node("lyric_planner")
    assert lyric.status == "invalidated"
    assert lyric.invalidated_by == "lyric_planner"
    assert lyric.invalidated_at is not None
    assert lyric.output["language"] == "en"
    assert lyric.retry_count == 1
    assert lyric.depends_on == ["brief_planner", "structure_planner"]


def test_node_store_read_required_output_rejects_invalidated_node(tmp_path):
    store = NodeStore(tmp_path)
    store.write_node(NodeRecord(node="critic", status="invalidated", output={"passed": True}))

    with pytest.raises(ValueError, match="not completed"):
        store.read_required_output("critic")


def test_node_store_has_completed_node(tmp_path):
    store = NodeStore(tmp_path)
    store.write_node(NodeRecord(node="repair", status="skipped", output={"applied": False}))

    assert store.has_completed_node("repair") is True
    assert store.has_completed_node("critic") is False
