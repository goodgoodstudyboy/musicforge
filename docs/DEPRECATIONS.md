# Deprecation Catalog

The machine-readable source of truth is [deprecations.json](deprecations.json).
Every entry records its replacement, repository usage, compatibility surface,
schema impact, removal version, and rollback strategy. v13 may remove an entry
only after production imports are zero and archived evidence remains readable.

v13 removes the superseded `release_check_matrix.py` and
`release_check_runner.py` facades. Legacy v1-v11 release checks still run
through `full`, `nightly`, or explicit historical profiles and remain available
through the 51-line `song_agent.release_checks` archive adapter until v13.1.
New production code must import `song_agent.release_check` directly.

The legacy CLI/API/Web dispatcher implementations reached their v13 removal
target. Their public files remain as bounded entrypoint facades over the
interface registries; those facades are compatibility surfaces, not duplicate
dispatch implementations.
