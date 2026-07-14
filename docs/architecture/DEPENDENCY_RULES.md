# Dependency Rules

## Allowed Direction

```text
interfaces -> application -> domains -> platform
```

- Platform code cannot import application, domain, interface, or release-check
  modules.
- Application code cannot import CLI, Server, WebUI, or release-check modules.
- Domain code cannot import CLI, Server, WebUI, or release-check modules.
- Production modules cannot import release-check helpers.
- Release-check may call public application and interface APIs for integration
  verification, but it cannot import private interface symbols.
- Compatibility facades may import their replacement; replacements cannot
  import the facade.
- New production import cycles are release blockers.

## Ratchets

- Every production module must appear in `architecture-baseline.json` with one
  layer and, for domains/interfaces, one context.
- Existing production cycles may disappear but no new cycle may appear.
- `server.py`, `cli.py`, and `webui.py` cannot exceed their v12.14 line
  baselines; the expired `release_checks.py` facade is absent.
- Counts of `_raw_zip_entry_names`, `_is_safe_zip_entry`, and
  `_zip_has_no_trailing_data` cannot increase.
- Dynamic imports must not be used to hide a dependency from the AST scan.

Run the guardrails with:

```powershell
python -m pytest tests\test_architecture_boundaries.py tests\test_architecture_metrics.py -q
python -m song_agent.cli release-check --only v1214.architecture_guardrails_smoke --skip-tests --json
```
