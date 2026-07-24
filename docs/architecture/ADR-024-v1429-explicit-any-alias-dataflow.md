# ADR-024: v14.2.9 Explicit Any Alias Data-Flow Kernel

Status: Accepted

Date: 2026-07-24

## Context

Collector schema 11 stored object identities directly on names. That covered
direct aliases but did not model values transported through tuple unpacking,
container members, attributes, or dynamic calls. Each newly discovered syntax
path required another collector branch and could accidentally treat a derived
value as a new trusted object.

## Decision

MusicForge v14.2.9 adopts collector schema 12 and an independent alias
data-flow kernel.

- `FlowValue` separates binding kind, exact object identities, dynamic escape,
  and possible origin identities.
- `ExplicitAnyDataFlow` owns object allocation, literal container cells,
  member reads and writes, unpacking, branch joins, reachability, and taint
  propagation. The AST collector no longer implements alias sets itself.
- Tuple/list literal unpacking and statically keyed attribute/subscript reads
  preserve exact identities.
- Calls and unresolved member reads create a distinct escaped result while
  retaining the identities of arguments, receivers, and base objects as
  possible origins. They are not silently promoted to trusted identities.
- An Any/uncertain write through an escaped result taints both the result and
  every reachable possible origin. Ordinary use of an escaped value does not
  pollute unrelated types.
- Taint is computed from the left-hand object graph before the new right-hand
  value is stored, preventing a write from retroactively tainting the value's
  class or factory.
- All schema 11 total, layer, affected-file, per-file, complexity, and recovery
  ceilings remain unchanged. The updater cannot authorize growth during the
  11-to-12 migration.

## Verification

The release gate executes four source-level attacks: literal destructuring,
container subscript transport, attribute transport, and generic identity-call
transport. Each probe must count 100 annotations and fail scope, total, layer,
and file ratchets. Targeted tests execute the same sources and additionally
prove runtime `typing.Any`, 100 annotations, project Ruff, and strict mypy.

The existing v141 gate in every publishing profile owns the full active-tree
scan; v1429 does not repeat that 700-file scan. Kernel unit tests independently
verify exact cells, unpacking, escaped result
identity, origin propagation, mutation-time taint, and safe reassignment. An
active-tree regression ensures ordinary factory calls remain free of scope
blockers.

## Consequences

Schema 12 replaces the incremental alias-set patches with one bounded abstract
data-flow model. It is intentionally conservative at dynamic escape boundaries
but does not claim full Python interprocedural analysis. Unsupported runtime
metaprogramming remains outside the accepted annotation-authority model and
must be prohibited or analyzed by a mature semantic engine before use in type
alias construction. ARCH-014 and TYPE-003 remain open through v14.3.0.
