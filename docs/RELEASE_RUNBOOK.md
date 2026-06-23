# Release Runbook

This runbook covers a local MusicForge release.

## Prepare

1. Update `pyproject.toml`.
2. Update `song_agent/__init__.py`.
3. Add the top `CHANGELOG.md` section.
4. Keep local runtime config out of git, especially `.musicforge/provider.json`
   and `.musicforge/renderer.json`.

## Verify

```powershell
python -m pytest tests\test_ga_readiness.py tests\test_cli_ga_readiness.py tests\test_release_check.py::test_v100_ga_lts_readiness_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile ga --skip-tests --json
python -m song_agent.cli release-check --profile latest --skip-tests --json
python -m song_agent.cli ga-check --strict --json --report-out runs\ga-readiness\ga-readiness-report.json
python -m song_agent.cli verify-ga-readiness-report runs\ga-readiness\ga-readiness-report.json --strict --json
git diff --check
git status --short --branch
```

Use full `pytest -q` when time allows. If full tests exceed the local time
budget, record the targeted tests and release-check profiles that were run.

## Commit And Tag

```powershell
git add .
git commit -m "Release v10.0.0 GA readiness"
git push origin master
git tag -a v10.0.0 -m "v10.0.0"
git push origin v10.0.0
```

If DNS resolves GitHub to an unreachable front-end, use a one-time Git
`http.curloptResolve` override. Do not change the remote URL for that workaround.

## GitHub Release

Create the GitHub Release only after `master` and the annotated tag are on the
remote and the tag dereferences to the release commit. Use a local token source
outside the repository and do not print the token.
