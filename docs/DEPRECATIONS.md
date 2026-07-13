# Deprecation Catalog

The machine-readable source of truth is [deprecations.json](deprecations.json).
Every entry records its replacement, repository usage, compatibility surface,
schema impact, removal version, and rollback strategy. v13 may remove an entry
only after production imports are zero and archived evidence remains readable.

Legacy v1-v11 release checks are not deleted in v12.20. They run through the
`full`, `nightly`, or explicit historical profiles and remain available through
the `song_agent.release_checks` compatibility facade.
