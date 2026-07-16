from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import re as re
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json


NODE_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


@dataclass
class NodeRecord:
    node: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    attempt_count: int = 0
    provider_snapshot: dict[str, Any] = field(default_factory=dict)
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    invalidated_at: str | None = None
    invalidated_by: str | None = None
    retry_count: int = 0
    last_error: str | None = None
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeRecord":
        return cls(
            node=str(data["node"]),
            status=str(data["status"]),
            started_at=None if data.get("started_at") is None else str(data.get("started_at")),
            finished_at=None
            if data.get("finished_at") is None
            else str(data.get("finished_at")),
            attempt_count=int(data.get("attempt_count", 0) or 0),
            provider_snapshot=_dict_or_empty(data.get("provider_snapshot")),
            input_summary=_dict_or_empty(data.get("input_summary")),
            output_summary=_dict_or_empty(data.get("output_summary")),
            output=_dict_or_empty(data.get("output")),
            error=None if data.get("error") is None else str(data.get("error")),
            invalidated_at=None
            if data.get("invalidated_at") is None
            else str(data.get("invalidated_at")),
            invalidated_by=None
            if data.get("invalidated_by") is None
            else str(data.get("invalidated_by")),
            retry_count=int(data.get("retry_count", 0) or 0),
            last_error=None if data.get("last_error") is None else str(data.get("last_error")),
            depends_on=[str(item) for item in _list_or_empty(data.get("depends_on"))],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "attempt_count": self.attempt_count,
            "provider_mode": self.provider_snapshot.get("mode"),
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
            "invalidated_at": self.invalidated_at,
            "invalidated_by": self.invalidated_by,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "depends_on": self.depends_on,
            "can_retry": self.status in {"completed", "failed", "skipped", "repaired"},
        }


class NodeStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.nodes_dir = run_dir / "data" / "nodes"

    def node_path(self, node_name: str) -> Path:
        safe_name = validate_node_name(node_name)
        path = (self.nodes_dir / f"{safe_name}.json").resolve()
        base = self.nodes_dir.resolve()
        if path.parent != base:
            raise ValueError("Node path must stay inside data/nodes.")
        return path

    def write_node(self, record: NodeRecord) -> Path:
        validate_node_name(record.node)
        return write_json(self.node_path(record.node), record.to_dict())

    def read_node(self, node_name: str) -> NodeRecord:
        path = self.node_path(node_name)
        if not path.exists():
            raise FileNotFoundError(f"Node record not found: {node_name}.")
        return NodeRecord.from_dict(read_json(path))

    def list_nodes(self) -> list[NodeRecord]:
        if not self.nodes_dir.exists():
            return []
        records: list[NodeRecord] = []
        for path in sorted(self.nodes_dir.glob("*.json")):
            records.append(NodeRecord.from_dict(read_json(path)))
        return sorted(records, key=lambda record: _node_order(record.node))

    def invalidate_nodes(
        self,
        node_names: list[str],
        invalidated_by: str,
    ) -> list[NodeRecord]:
        validate_node_name(invalidated_by)
        invalidated: list[NodeRecord] = []
        now = _utc_now()
        for node_name in node_names:
            validate_node_name(node_name)
            try:
                record = self.read_node(node_name)
            except FileNotFoundError:
                continue
            record.status = "invalidated"
            record.invalidated_at = now
            record.invalidated_by = invalidated_by
            record.last_error = record.error
            record.error = None
            self.write_node(record)
            invalidated.append(record)
        return invalidated

    def read_required_output(self, node_name: str) -> dict[str, Any]:
        record = self.read_node(node_name)
        if record.status not in {"completed", "skipped", "repaired"}:
            raise ValueError(f"Node {node_name} is not completed.")
        if not record.output:
            raise ValueError(f"Node {node_name} has no output.")
        return record.output

    def has_completed_node(self, node_name: str) -> bool:
        try:
            record = self.read_node(node_name)
        except FileNotFoundError:
            return False
        return record.status in {"completed", "skipped", "repaired"}


def validate_node_name(node_name: str) -> str:
    if not NODE_NAME_RE.fullmatch(node_name):
        raise ValueError("Node name may only contain lowercase letters, numbers, '_' and '-'.")
    if ".." in node_name or "/" in node_name or "\\" in node_name:
        raise ValueError("Node name must not contain path traversal or separators.")
    return node_name


def _node_order(node_name: str) -> tuple[int, str]:
    try:
        return PIPELINE_NODE_ORDER.index(node_name), node_name
    except ValueError:
        return len(PIPELINE_NODE_ORDER), node_name


def _dict_or_empty(value: Any) -> ImplementationDocument:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


PIPELINE_NODE_ORDER = [
    "brief_planner",
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
