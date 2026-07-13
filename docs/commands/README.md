# Command Reference

Use `python -m song_agent.cli --help` for the generated command inventory and
`python -m song_agent.cli release-check --list --json` for release checks.

Primary workflows:

- `doctor`: local configuration and workspace health.
- `serve`: local Studio and HTTP API.
- `release-check`: profile-based release validation.
- `ga-check`: GA policy and evidence-manifest evaluation.
- `maintenance`: backup, restore, migration, and periodic checks.

CLI compatibility aliases are listed in [the deprecation catalog](../DEPRECATIONS.md).
