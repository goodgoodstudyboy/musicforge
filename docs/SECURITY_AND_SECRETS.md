# Security And Secrets

MusicForge is local-first. Keep credentials and local machine paths out of git,
docs, manifests, public packages, and logs.

## Rules

- Do not put tokens in Git remotes.
- Do not commit `.musicforge/provider.json`.
- Do not commit `.musicforge/renderer.json`.
- Do not paste local absolute paths into public evidence files.
- Do not let APIs read arbitrary server-side `source_path` values unless the
  endpoint explicitly documents a safe local-only workflow.
- Public ZIP verifiers must reject dangerous paths, backslashes, duplicate
  entries, manifest spoofing, nested ZIPs when not allowed, and redaction
  failures.

## Provider Config

Provider configuration is optional. Store it locally and keep it untracked.
Mock provider mode is for tests and smoke checks; do not present mock evidence
as real provider work.

## Renderer Config

Renderer configuration may contain local executable or SoundFont paths. Keep it
local and untracked.

