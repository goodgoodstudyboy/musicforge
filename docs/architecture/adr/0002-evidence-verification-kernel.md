# ADR 0002: Evidence Verification Kernel

Status: Accepted and active since v12.15.

## Decision

ZIP envelope safety, manifest validation, redaction, history validation, and
external evidence matching will be implemented once in a composable
verification kernel. Domain verifiers provide only package specifications and
semantic checks.

## Constraints

Migration must preserve blocker IDs where they are externally consumed, reject
declared extras and unsafe paths, detect trailing data, and retain runtime
external binding. Differential tests must compare legacy and kernel results.

## Consequences

Duplicate verifier helpers are frozen at the v12.14 count and must decline as
active v12 packages migrate.
