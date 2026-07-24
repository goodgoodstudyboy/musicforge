from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable


ANY_RELEVANT_KINDS = frozenset(
    {"any", "typing-module", "any-or-typing-module", "uncertain", "unknown"}
)
CellKey = tuple[str, str]


@dataclass(frozen=True)
class FlowValue:
    """A conservative value used by the Explicit Any alias analysis."""

    kind: str = "other"
    identities: frozenset[int] = frozenset()
    escaped: bool = False
    origins: frozenset[int] = frozenset()

    def with_kind(self, kind: str) -> FlowValue:
        return replace(self, kind=kind)


@dataclass
class _ObjectState:
    cells: dict[CellKey, FlowValue] = field(default_factory=dict)
    wildcard: FlowValue | None = None
    escaped: bool = False
    origins: frozenset[int] = frozenset()
    taint: str = "other"


class ExplicitAnyDataFlow:
    """May-alias object graph for the Explicit Any lexical collector.

    The graph only treats direct literals and previously recorded member reads
    as precise. Dynamic calls and unresolved member reads retain every object
    they may expose and are marked escaped. Any-related mutation then taints
    the complete reachable object set instead of inventing a trusted identity.
    """

    def __init__(self) -> None:
        self._next_identity = 0
        self._objects: dict[int, _ObjectState] = {}

    def scalar(self, kind: str = "other") -> FlowValue:
        return FlowValue(kind=kind)

    def object(
        self,
        kind: str = "other",
        *,
        escaped: bool = False,
        origins: frozenset[int] = frozenset(),
    ) -> FlowValue:
        identity = self._new_identity()
        self._objects[identity] = _ObjectState(escaped=escaped, origins=origins)
        return FlowValue(
            kind=kind,
            identities=frozenset({identity}),
            escaped=escaped,
            origins=origins,
        )

    def container(self, elements: Iterable[FlowValue], *, kind: str = "other") -> FlowValue:
        value = self.object(kind)
        state = self._objects[next(iter(value.identities))]
        for index, element in enumerate(elements):
            state.cells[("index", str(index))] = element
        return value

    def mapping(self, entries: Iterable[tuple[str | None, FlowValue]], *, kind: str = "other") -> FlowValue:
        value = self.object(kind)
        state = self._objects[next(iter(value.identities))]
        for key, element in entries:
            if key is None:
                state.wildcard = self.join((state.wildcard, element)) if state.wildcard else element
            else:
                cell = ("index", key)
                state.cells[cell] = self.join((state.cells[cell], element)) if cell in state.cells else element
        return value

    def join(self, values: Iterable[FlowValue | None], *, kind: str | None = None) -> FlowValue:
        rows = [value for value in values if value is not None]
        if not rows:
            return self.scalar(kind or "other")
        merged_kind = kind or merge_flow_kinds(value.kind for value in rows)
        identities = frozenset().union(*(value.identities for value in rows))
        origins = frozenset().union(*(value.origins for value in rows))
        escaped = any(value.escaped for value in rows) or any(
            self._objects.get(identity, _ObjectState()).escaped for identity in identities
        )
        return FlowValue(
            kind=merged_kind,
            identities=identities,
            escaped=escaped,
            origins=origins,
        )

    def escape(self, values: Iterable[FlowValue], *, kind: str = "other") -> FlowValue:
        merged = self.join(values, kind=kind)
        origins = self.taint_reachable(merged)
        return self.object(kind, escaped=True, origins=origins)

    def read_member(self, base: FlowValue, key: CellKey | None) -> FlowValue:
        values: list[FlowValue] = []
        unresolved = base.escaped
        for identity in base.identities:
            state = self._objects.get(identity)
            if state is None:
                unresolved = True
                continue
            if state.taint in ANY_RELEVANT_KINDS:
                values.append(FlowValue(kind=state.taint))
            if key is not None and key in state.cells:
                values.append(state.cells[key])
            elif key is None:
                values.extend(state.cells.values())
                unresolved = True
            else:
                unresolved = True
            if state.wildcard is not None:
                values.append(state.wildcard)
                unresolved = True
            unresolved = unresolved or state.escaped
        if unresolved or not values:
            escaped = self.escape((base,), kind="other")
            values.append(escaped)
        return self.join(values)

    def write_member(self, base: FlowValue, key: CellKey | None, value: FlowValue) -> frozenset[int]:
        identities = self.reachable(base.identities) if base.escaped else base.identities
        for identity in identities:
            state = self._objects.get(identity)
            if state is None:
                continue
            if key is None:
                state.wildcard = self.join((state.wildcard, value)) if state.wildcard else value
            else:
                current = state.cells.get(key)
                state.cells[key] = self.join((current, value)) if current else value
        return identities

    def unpack(self, value: FlowValue, count: int) -> tuple[FlowValue, ...]:
        rows: list[FlowValue] = []
        for index in range(count):
            rows.append(self.read_member(value, ("index", str(index))))
        return tuple(rows)

    def taint(self, value: FlowValue, kind: str) -> frozenset[int]:
        affected = self.taint_reachable(value)
        for identity in affected:
            state = self._objects.get(identity)
            if state is not None:
                state.taint = merge_flow_kinds((state.taint, kind))
        return affected

    def taint_reachable(self, value: FlowValue) -> frozenset[int]:
        pending = list(value.identities | value.origins)
        seen: set[int] = set()
        while pending:
            identity = pending.pop()
            if identity in seen:
                continue
            seen.add(identity)
            state = self._objects.get(identity)
            if state is None:
                continue
            pending.extend(state.origins - seen)
            values = list(state.cells.values())
            if state.wildcard is not None:
                values.append(state.wildcard)
            for item in values:
                pending.extend((item.identities | item.origins) - seen)
        return frozenset(seen)

    def reachable(self, identities: frozenset[int]) -> frozenset[int]:
        pending = list(identities)
        seen: set[int] = set()
        while pending:
            identity = pending.pop()
            if identity in seen:
                continue
            seen.add(identity)
            state = self._objects.get(identity)
            if state is None:
                continue
            values = list(state.cells.values())
            if state.wildcard is not None:
                values.append(state.wildcard)
            for value in values:
                pending.extend(value.identities - seen)
        return frozenset(seen)

    def _new_identity(self) -> int:
        self._next_identity += 1
        return self._next_identity


def merge_flow_kinds(kinds: Iterable[str]) -> str:
    values = set(kinds)
    if not values:
        return "other"
    if "uncertain" in values:
        return "uncertain"
    if "unknown" in values:
        return "unknown"
    if "any-or-typing-module" in values or {"any", "typing-module"}.issubset(values):
        return "any-or-typing-module"
    priority = {
        "other": 0,
        "type-checking-marker": 1,
        "type-alias-marker": 2,
        "typing-module": 3,
        "any": 4,
    }
    return max(values, key=lambda value: priority.get(value, 0))
