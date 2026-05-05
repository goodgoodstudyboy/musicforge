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
