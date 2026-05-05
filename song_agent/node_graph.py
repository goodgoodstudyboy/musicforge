from __future__ import annotations

from song_agent.node_store import PIPELINE_NODE_ORDER, validate_node_name


NODE_DEPENDENCIES: dict[str, list[str]] = {
    "brief_planner": [],
    "style_planner": ["brief_planner"],
    "structure_planner": ["brief_planner", "style_planner"],
    "lyric_planner": ["brief_planner", "structure_planner"],
    "harmony_planner": ["brief_planner", "structure_planner"],
    "melody_planner": ["style_planner", "structure_planner"],
    "arrangement_planner": [
        "style_planner",
        "structure_planner",
        "harmony_planner",
        "melody_planner",
    ],
    "critic": ["arrangement_planner", "harmony_planner", "lyric_planner"],
    "repair": ["critic"],
    "song_plan_builder": ["repair"],
}


def upstream_nodes(node_name: str) -> list[str]:
    node_name = _known_node(node_name)
    return list(NODE_DEPENDENCIES[node_name])


def downstream_nodes(node_name: str) -> list[str]:
    node_name = _known_node(node_name)
    downstream: list[str] = []
    seen: set[str] = set()

    def visit(parent: str) -> None:
        for candidate in PIPELINE_NODE_ORDER:
            if candidate in seen:
                continue
            if parent in NODE_DEPENDENCIES[candidate]:
                seen.add(candidate)
                downstream.append(candidate)
                visit(candidate)

    visit(node_name)
    return sorted(downstream, key=PIPELINE_NODE_ORDER.index)


def affected_nodes_for_retry(node_name: str) -> list[str]:
    node_name = _known_node(node_name)
    return [node_name, *downstream_nodes(node_name)]


def _known_node(node_name: str) -> str:
    validate_node_name(node_name)
    if node_name not in NODE_DEPENDENCIES:
        raise ValueError(f"Unknown node: {node_name}.")
    return node_name
