# ADR-023: v14.2.8 Explicit Any Object Alias Flow

Status: Accepted

Date: 2026-07-23

## Context

Collector schema 10 tainted the syntactic root of an attribute or subscript
write. It did not retain object identity across `Name = Name`. A write through
`Ref` could therefore store an uncertain value in an object also named
`Holder`, while a later read through `Holder` remained trusted.

## Decision

MusicForge v14.2.8 adopts collector schema 11.

- Track a set of possible object identities for each name in every lexical
  scope.
- Copy identities for direct name aliases and chained assignments. Ordinary
  reassignment creates a new identity and disconnects the old alias.
- Merge branch aliases as a may-alias union. If any branch can retain an alias,
  mutation through that name taints all names in the possible alias group.
- Propagate Any-related uncertainty through attribute and subscript mutation,
  in-place augmented assignment, multi-level aliases, class-object aliases,
  and conservative dynamic escape for direct Any or uncertain arguments.
- Distinguish ordinary unresolved indirect values from Any-related uncertainty.
  Both fail closed when consumed as annotations, but ordinary values do not
  taint unrelated call receivers.
- Preserve every schema 10 total, layer, affected-file, per-file, complexity,
  and recovery ceiling. The 10-to-11 migration cannot authorize growth.

## Verification

Unit tests execute list aliases, class aliases, two-level aliases, branch
aliases, direct and derived dynamic escape, in-place augmented mutation, and
an ordinary reassignment negative case. Positive cases must evaluate to
`typing.Any`, create 100 runtime annotations, pass project Ruff and strict
mypy, count 100 annotations, and fail scope, total, layer, and file gates.

`v1428.explicit_any_object_alias_scope_smoke` repeats the attack matrix in all
publishing profiles. Active-tree collection must remain at the schema 10
measurements with zero scope-flow blockers.

## Consequences

Schema 11 is still a bounded static collector rather than a complete Python
semantic analyzer. v14.3 must replace incremental syntax patches with an
explicit symbol and alias data-flow model backed by mature semantic analysis,
or prohibit unsupported dynamic binding forms. ARCH-014 and TYPE-003 remain
open through v14.3.0.
