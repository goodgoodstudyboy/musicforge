from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.verification.hashing import stable_hash


@dataclass(frozen=True)
class EvidenceEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    ref: EvidenceRef
    capability_id: str
    report_status: str
    runtime_status: str
    current: bool
    lifecycle_status: str = "unknown"
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    runtime_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return (
            self.report_status == "passed"
            and self.runtime_status == "passed"
            and self.current
            and not self.blockers
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["ready"] = self.ready
        return value


@dataclass(frozen=True)
class EvidenceGraph:
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: int = 1

    @property
    def status(self) -> str:
        if self.blockers or any(not node.ready for node in self.nodes):
            return "failed"
        return "warning" if self.warnings or any(node.warnings for node in self.nodes) else "passed"

    @property
    def graph_hash(self) -> str:
        return stable_hash(
            {
                "schema_version": self.schema_version,
                "nodes": [node.to_dict() for node in self.nodes],
                "edges": [edge.to_dict() for edge in self.edges],
                "blockers": list(self.blockers),
                "warnings": list(self.warnings),
            }
        )

    def by_node_id(self) -> dict[str, EvidenceNode]:
        return {node.node_id: node for node in self.nodes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "graph_hash": self.graph_hash,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "summary": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "ready_count": sum(1 for node in self.nodes if node.ready),
            },
        }
