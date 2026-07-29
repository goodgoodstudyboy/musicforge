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
    callable_role: str = ""

    def with_kind(self, kind: str) -> FlowValue:
        return replace(self, kind=kind)


@dataclass
class _ObjectState:
    cells: dict[CellKey, FlowValue] = field(default_factory=dict)
    wildcard: FlowValue | None = None
    call_exposed: bool = False
    length: int | None = None
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
        self._parents: dict[int, int] = {}
        self._members: dict[int, set[int]] = {}
        self._component_cells: dict[int, dict[CellKey, FlowValue]] = {}
        self._component_wildcards: dict[int, FlowValue | None] = {}
        self._component_exposed: dict[int, bool] = {}
        self._component_escaped: dict[int, bool] = {}
        self._component_taints: dict[int, str] = {}
        self._component_roots_cache: dict[
            tuple[frozenset[int], frozenset[int]], frozenset[int]
        ] = {}
        self._component_members_cache: dict[int, frozenset[int]] = {}

    def scalar(self, kind: str = "other") -> FlowValue:
        return FlowValue(kind=kind)

    def checkpoint(self) -> int:
        """Return the highest identity allocated before a nested analysis."""

        return self._next_identity

    def object(
        self,
        kind: str = "other",
        *,
        escaped: bool = False,
        origins: frozenset[int] = frozenset(),
        callable_role: str = "",
    ) -> FlowValue:
        identity = self._new_identity()
        canonical_origins = self._canonical_roots(origins)
        self._objects[identity] = _ObjectState(escaped=escaped, origins=canonical_origins)
        self._component_escaped[identity] = escaped
        return FlowValue(
            kind=kind,
            identities=frozenset({identity}),
            escaped=escaped,
            origins=canonical_origins,
            callable_role=callable_role,
        )

    def container(self, elements: Iterable[FlowValue], *, kind: str = "other") -> FlowValue:
        value = self.object(kind)
        state = self._objects[next(iter(value.identities))]
        rows = tuple(elements)
        state.length = len(rows)
        for index, element in enumerate(rows):
            key = ("index", str(index))
            state.cells[key] = element
            self._component_cells[self._find(next(iter(value.identities)))][key] = element
        return value

    def mapping(self, entries: Iterable[tuple[str | None, FlowValue]], *, kind: str = "other") -> FlowValue:
        value = self.object(kind)
        state = self._objects[next(iter(value.identities))]
        for key, element in entries:
            if key is None:
                state.wildcard = self.join((state.wildcard, element)) if state.wildcard else element
                root = self._find(next(iter(value.identities)))
                current = self._component_wildcards[root]
                self._component_wildcards[root] = self.join((current, element)) if current else element
            else:
                cell = ("index", key)
                state.cells[cell] = self.join((state.cells[cell], element)) if cell in state.cells else element
                root = self._find(next(iter(value.identities)))
                current = self._component_cells[root].get(cell)
                self._component_cells[root][cell] = self.join((current, element)) if current else element
        return value

    def join(self, values: Iterable[FlowValue | None], *, kind: str | None = None) -> FlowValue:
        rows = [value for value in values if value is not None]
        if not rows:
            return self.scalar(kind or "other")
        merged_kind = kind or merge_flow_kinds(value.kind for value in rows)
        identities = self._canonical_roots(
            frozenset().union(*(value.identities for value in rows))
        )
        origins = self._canonical_roots(
            frozenset().union(*(value.origins for value in rows))
        )
        roles = {value.callable_role for value in rows if value.callable_role}
        callable_role = next(iter(roles)) if len(roles) == 1 else ("callable" if roles else "")
        escaped = any(value.escaped for value in rows) or any(
            self._objects.get(identity, _ObjectState()).escaped for identity in identities
        )
        return FlowValue(
            kind=merged_kind,
            identities=identities,
            escaped=escaped,
            origins=origins,
            callable_role=callable_role,
        )

    def escape(self, values: Iterable[FlowValue], *, kind: str = "other") -> FlowValue:
        merged = self.join(values, kind=kind)
        origins = self.taint_reachable(merged)
        return self.object(kind, escaped=True, origins=origins, callable_role=merged.callable_role)

    def call_effect(self, values: Iterable[FlowValue], *, kind: str = "other") -> FlowValue:
        """Conservatively model an unresolved call's alias and storage effects.

        A call may retain any object participant, store one participant inside
        another, and return an alias derived from that set. The component is
        built even when no participant is Any-related yet so a later mutation
        cannot launder the earlier alias transport.
        """

        rows = tuple(values)
        component = self.connect(rows, expose_members=True)
        result = self.object(kind, escaped=True, origins=component)
        if component:
            merged = FlowValue(identities=component, escaped=True)
            self.connect((merged, result), expose_members=False)
        return result

    def connect(
        self,
        values: Iterable[FlowValue],
        *,
        expose_members: bool,
    ) -> frozenset[int]:
        """Join values into one may-alias component without claiming equality."""

        rows = tuple(values)
        component: set[int] = set()
        for value in rows:
            component.update(self.component_roots(value))
        if not component:
            return frozenset()

        frozen = frozenset(component)
        root = next(iter(frozen))
        for identity in frozen - {root}:
            root = self._union(root, identity)
        root = self._find(root)
        for identity in frozen:
            state = self._objects.get(identity)
            if state is None:
                continue
            state.escaped = True
            if expose_members:
                state.call_exposed = True
        if expose_members:
            self._component_exposed[self._find(root)] = True
        self._component_escaped[self._find(root)] = True
        return frozenset({root})

    def related(self, left: FlowValue, right: FlowValue) -> bool:
        """Return whether two values may expose the same runtime object."""

        return bool(self.component_roots(left) & self.component_roots(right))

    def has_storage_effect(self, value: FlowValue) -> bool:
        """Return whether a value may be retained by a call or object write."""

        for root in self.component_roots(value):
            if self._component_exposed.get(root, False):
                return True
            if len(self._members.get(root, ())) > 1:
                return True
        return False

    def prior_component(self, value: FlowValue, checkpoint: int) -> FlowValue | None:
        """Return captured identities that predate a nested function analysis."""

        return self.prior_component_roots(self.component_roots(value), checkpoint)

    def prior_component_roots(
        self,
        roots: Iterable[int],
        checkpoint: int,
    ) -> FlowValue | None:
        """Return captured roots without resolving the same value twice."""

        identities: set[int] = set()
        for identity in roots:
            root = self._find(identity)
            if any(identity <= checkpoint for identity in self._members.get(root, {root})):
                identities.add(root)
        if not identities:
            return None
        return FlowValue(identities=frozenset(identities), escaped=True)

    def component_roots(self, value: FlowValue) -> frozenset[int]:
        identities = value.identities
        origins = value.origins
        if not identities and not origins:
            return frozenset()
        cache_key = (identities, origins)
        cached = self._component_roots_cache.get(cache_key)
        if cached is not None:
            return cached
        if not origins and len(identities) == 1:
            identity = next(iter(identities))
            if identity not in self._parents:
                return frozenset()
            root = self._find(identity)
            result = identities if root == identity else frozenset({root})
        elif not identities and len(origins) == 1:
            identity = next(iter(origins))
            if identity not in self._parents:
                return frozenset()
            root = self._find(identity)
            result = origins if root == identity else frozenset({root})
        elif len(identities) == 1 and len(origins) == 1:
            identity = next(iter(identities))
            origin = next(iter(origins))
            identity_root = self._find(identity) if identity in self._parents else None
            origin_root = self._find(origin) if origin in self._parents else None
            if identity_root is None:
                result = frozenset() if origin_root is None else frozenset({origin_root})
            elif origin_root is None:
                result = identities if identity_root == identity else frozenset({identity_root})
            elif origin_root == identity_root:
                if identity_root == identity:
                    result = identities
                elif origin_root == origin:
                    result = origins
                else:
                    result = frozenset({identity_root})
            else:
                result = frozenset({identity_root, origin_root})
        else:
            result = frozenset(
                self._find(identity)
                for identity in identities | origins
                if identity in self._parents
            )
        self._component_roots_cache[cache_key] = result
        return result

    def component_identities(self, value: FlowValue) -> frozenset[int]:
        """Return every original identity represented by a may-alias value."""

        return frozenset(
            identity
            for root in self.component_roots(value)
            for identity in self._component_members(root)
        )

    def _component_members(self, root: int) -> frozenset[int]:
        canonical = self._find(root)
        cached = self._component_members_cache.get(canonical)
        if cached is None:
            cached = frozenset(self._members.get(canonical, {canonical}))
            self._component_members_cache[canonical] = cached
        return cached

    def stored_values(self, value: FlowValue) -> tuple[FlowValue, ...]:
        """Return values held directly by any object in the alias component."""

        rows: list[FlowValue] = []
        for root in self.component_roots(value):
            rows.extend(self._component_cells.get(root, {}).values())
            wildcard = self._component_wildcards.get(root)
            if wildcard is not None:
                rows.append(wildcard)
        return tuple(dict.fromkeys(rows))

    def stored_value_closure(self, values: Iterable[FlowValue]) -> tuple[FlowValue, ...]:
        """Return participants plus every statically known nested stored value."""

        pending = list(values)
        rows: list[FlowValue] = []
        seen_values: set[FlowValue] = set()
        seen_roots: set[int] = set()
        while pending:
            value = pending.pop()
            if value in seen_values:
                continue
            seen_values.add(value)
            rows.append(value)
            roots = self.component_roots(value)
            fresh = roots - seen_roots
            if not fresh:
                continue
            seen_roots.update(fresh)
            for root in fresh:
                pending.extend(self._component_cells.get(root, {}).values())
                wildcard = self._component_wildcards.get(root)
                if wildcard is not None:
                    pending.append(wildcard)
        return tuple(rows)

    def read_member(self, base: FlowValue, key: CellKey | None) -> FlowValue:
        values: list[FlowValue] = []
        unresolved = base.escaped
        roots = self.component_roots(base)
        for root in roots:
            taint = self._component_taints.get(root, "other")
            if taint in ANY_RELEVANT_KINDS:
                values.append(FlowValue(kind=taint))
            cells = self._component_cells.get(root, {})
            if key is not None and key in cells:
                values.append(cells[key])
            elif key is None:
                values.extend(cells.values())
                unresolved = True
            else:
                unresolved = True
            wildcard = self._component_wildcards.get(root)
            if wildcard is not None:
                values.append(wildcard)
                unresolved = True
            if self._component_exposed.get(root, False):
                values.append(FlowValue(identities=frozenset({root}), escaped=True, origins=frozenset({root})))
                unresolved = True
            unresolved = unresolved or self._component_escaped.get(root, False)
        if unresolved or not values:
            escaped = self.escape((base,), kind="other")
            values.append(escaped)
        return self.join(values)

    def write_member(self, base: FlowValue, key: CellKey | None, value: FlowValue) -> frozenset[int]:
        roots = self.component_roots(base)
        identities = roots
        for root in roots:
            if key is None:
                current = self._component_wildcards.get(root)
                self._component_wildcards[root] = self.join((current, value)) if current else value
            else:
                current = self._component_cells[root].get(key)
                self._component_cells[root][key] = self.join((current, value)) if current else value
        return identities

    def unpack(
        self,
        value: FlowValue,
        count: int,
        *,
        starred_index: int | None = None,
    ) -> tuple[FlowValue, ...]:
        if starred_index is None:
            return tuple(self.read_member(value, ("index", str(index))) for index in range(count))
        if not 0 <= starred_index < count:
            raise ValueError("starred_index must identify an unpack target")

        length = self._known_length(value)
        suffix_count = count - starred_index - 1
        if length is None or length < count - 1:
            # A starred suffix cannot be mapped safely without the source
            # length. Preserve every possible origin and make each result an
            # unknown value so annotation consumption fails closed.
            return tuple(self.escape((value,), kind="unknown") for _ in range(count))

        prefix = [
            self.read_member(value, ("index", str(index)))
            for index in range(starred_index)
        ]
        middle_end = length - suffix_count
        middle = self.container(
            self.read_member(value, ("index", str(index)))
            for index in range(starred_index, middle_end)
        )
        suffix = [
            self.read_member(value, ("index", str(index)))
            for index in range(middle_end, length)
        ]
        return tuple([*prefix, middle, *suffix])

    def has_unresolved_escape(self, value: FlowValue) -> bool:
        """Return whether a value depends on an escaped object with no source origin."""

        for root in self.component_roots(value):
            if not self._component_escaped.get(root, False):
                continue
            members = self._members.get(root, {root})
            if any(
                identity not in self._objects
                or (self._objects[identity].escaped and not self._objects[identity].origins)
                for identity in members
            ):
                return True
        return value.escaped and not (value.identities or value.origins)

    def taint(self, value: FlowValue, kind: str) -> frozenset[int]:
        affected = self.taint_reachable(value)
        for root in {self._find(identity) for identity in affected if identity in self._parents}:
            self._component_taints[root] = merge_flow_kinds((self._component_taints[root], kind))
        return affected

    def taint_reachable(self, value: FlowValue) -> frozenset[int]:
        pending = list(self.component_roots(value))
        seen_roots: set[int] = set()
        seen: set[int] = set()
        while pending:
            root = self._find(pending.pop())
            if root in seen_roots:
                continue
            seen_roots.add(root)
            seen.add(root)
            values = list(self._component_cells.get(root, {}).values())
            wildcard = self._component_wildcards.get(root)
            if wildcard is not None:
                values.append(wildcard)
            for item in values:
                pending.extend(self.component_roots(item) - seen_roots)
        return frozenset(seen)

    def reachable(self, identities: frozenset[int]) -> frozenset[int]:
        pending = [self._find(identity) for identity in identities if identity in self._parents]
        seen_roots: set[int] = set()
        seen: set[int] = set()
        while pending:
            root = self._find(pending.pop())
            if root in seen_roots:
                continue
            seen_roots.add(root)
            seen.add(root)
            values = list(self._component_cells.get(root, {}).values())
            wildcard = self._component_wildcards.get(root)
            if wildcard is not None:
                values.append(wildcard)
            for value in values:
                pending.extend(self.component_roots(value) - seen_roots)
        return frozenset(seen)

    def _known_length(self, value: FlowValue) -> int | None:
        roots = self.component_roots(value)
        if value.escaped or len(roots) != 1:
            return None
        root = next(iter(roots))
        if (
            self._component_escaped.get(root, False)
            or self._component_exposed.get(root, False)
            or self._component_wildcards.get(root) is not None
            or len(self._members.get(root, ())) != 1
        ):
            return None
        lengths: set[int] = set()
        for identity in self._members.get(root, ()):
            state = self._objects.get(identity)
            if state is None or state.escaped or state.wildcard is not None or state.length is None:
                return None
            lengths.add(state.length)
        return next(iter(lengths)) if len(lengths) == 1 else None

    def _new_identity(self) -> int:
        self._next_identity += 1
        identity = self._next_identity
        self._parents[identity] = identity
        self._members[identity] = {identity}
        self._component_cells[identity] = {}
        self._component_wildcards[identity] = None
        self._component_exposed[identity] = False
        self._component_escaped[identity] = False
        self._component_taints[identity] = "other"
        return identity

    def _canonical_roots(self, identities: Iterable[int]) -> frozenset[int]:
        return frozenset(
            self._find(identity)
            for identity in identities
            if identity in self._parents
        )

    def _find(self, identity: int) -> int:
        parent = self._parents.get(identity, identity)
        if parent != identity:
            parent = self._find(parent)
            self._parents[identity] = parent
        return parent

    def _union(self, left: int, right: int) -> int:
        left_root = self._find(left)
        right_root = self._find(right)
        if left_root == right_root:
            return left_root
        if len(self._members[left_root]) < len(self._members[right_root]):
            left_root, right_root = right_root, left_root
        self._parents[right_root] = left_root
        self._members[left_root].update(self._members.pop(right_root))
        left_cells = self._component_cells[left_root]
        for key, value in self._component_cells.pop(right_root).items():
            current = left_cells.get(key)
            left_cells[key] = self.join((current, value)) if current else value
        left_wildcard = self._component_wildcards[left_root]
        right_wildcard = self._component_wildcards.pop(right_root)
        if right_wildcard is not None:
            self._component_wildcards[left_root] = (
                self.join((left_wildcard, right_wildcard)) if left_wildcard else right_wildcard
            )
        self._component_exposed[left_root] = self._component_exposed[left_root] or self._component_exposed.pop(
            right_root
        )
        self._component_escaped[left_root] = self._component_escaped[left_root] or self._component_escaped.pop(
            right_root
        )
        self._component_taints[left_root] = merge_flow_kinds(
            (self._component_taints[left_root], self._component_taints.pop(right_root))
        )
        self._component_roots_cache.clear()
        self._component_members_cache.clear()
        return left_root

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
