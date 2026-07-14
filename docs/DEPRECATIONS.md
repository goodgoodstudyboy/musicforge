# Deprecation Catalog

The machine-readable source of truth is [deprecations.json](deprecations.json).
Every entry records its replacement, repository usage, compatibility surface,
schema impact, removal version, and rollback strategy. v13 may remove an entry
only after production imports are zero and archived evidence remains readable.

v13 removed the superseded matrix/runner facades and v13.7 removed the expired
`song_agent.release_checks` adapter after repository imports reached zero.
Legacy v1-v12 checks still run through labeled full/nightly or historical-major
profiles. New code imports `song_agent.release_check` directly.

The legacy CLI/API/Web dispatcher implementations reached their v13 removal
target. Their public files remain as bounded entrypoint facades over the
interface registries; those facades are compatibility surfaces, not duplicate
dispatch implementations.
