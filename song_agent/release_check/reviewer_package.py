from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import hashlib
import json
from pathlib import Path
import re
from typing import Any


MANIFEST_NAME = "reviewer-package-manifest.json"
REQUIRED_DOCUMENTS = frozenset(
    {
        "README.md",
        "architecture.json",
        "architecture-ratchet.json",
        "source-comparison.json",
        "import-graph.json",
        "duplicate-helpers.json",
        "verifier-migration.json",
        "lifecycle-migration.json",
        "persistence-migration.json",
        "cli-api-compatibility.json",
        "compatibility.json",
        "deprecations.json",
        "migration-rollback.json",
        "ci-matrix.json",
        "release-check-reports.json",
        "performance.json",
        "debt.json",
        "release-alignment.json",
        "security-attack-matrix.json",
        "runtime-verification.json",
        "lts-certification.json",
    }
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def write_reviewer_manifest(package_dir: Path | str, *, final_sha: str = "") -> Path:
    root = Path(package_dir)
    files = [_file_row(path, root) for path in sorted(root.iterdir()) if path.is_file() and path.name != MANIFEST_NAME]
    payload: ImplementationDocument = {
        "schema_version": 1,
        "package_type": "musicforge_v13_reviewer_package_manifest",
        "final_sha": final_sha,
        "files": files,
    }
    payload["integrity_hash"] = _stable_hash(payload)
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def verify_reviewer_package(
    package_dir: Path | str,
    *,
    expected_sha: str = "",
    require_final: bool = True,
) -> DomainDocument:
    root = Path(package_dir)
    checks: list[ImplementationDocument] = []
    manifest = _read_json(root / MANIFEST_NAME)
    entries = {path.name for path in root.iterdir() if path.is_file()} if root.is_dir() else set()
    expected_entries = REQUIRED_DOCUMENTS | {MANIFEST_NAME}
    _check(checks, "reviewer_package_allowed_entries", entries == expected_entries, actual=sorted(entries))
    _check(checks, "reviewer_package_manifest_type", manifest.get("package_type") == "musicforge_v13_reviewer_package_manifest")
    _check(checks, "reviewer_package_manifest_integrity", _integrity_ok(manifest))
    rows = list(manifest.get("files") or [])
    _check(checks, "reviewer_package_manifest_paths", {str(row.get("path")) for row in rows} == REQUIRED_DOCUMENTS)
    for row in rows:
        path = root / str(row.get("path") or "")
        _check(
            checks,
            f"reviewer_package_file_{str(row.get('path')).replace('.', '_').replace('-', '_')}",
            path.is_file()
            and path.stat().st_size == row.get("size_bytes")
            and _sha256(path) == row.get("sha256"),
        )
    runtime = _read_json(root / "runtime-verification.json")
    final_sha = str(runtime.get("final_sha") or manifest.get("final_sha") or "")
    _check(checks, "reviewer_package_final_sha", bool(_SHA_RE.fullmatch(final_sha)))
    _check(checks, "reviewer_package_manifest_final_sha", manifest.get("final_sha") == final_sha)
    if expected_sha:
        _check(checks, "reviewer_package_expected_sha", final_sha == expected_sha)
    if require_final:
        _final_checks(checks, root, runtime, final_sha)
    _check(checks, "reviewer_package_redaction", not _contains_sensitive_or_local_data(root))
    blockers = [row["check_id"] for row in checks if row["status"] == "failed"]
    return {
        "schema_version": 1,
        "package_type": "musicforge_v13_reviewer_package_verification",
        "status": "failed" if blockers else "passed",
        "checks": checks,
        "blockers": blockers,
        "summary": {"final_sha": final_sha, "check_count": len(checks), "failed_count": len(blockers)},
    }


def _final_checks(checks: list[ImplementationDocument], root: Path, runtime: ImplementationDocument, final_sha: str) -> None:
    ci = _read_json(root / "ci-matrix.json")
    release_checks = _read_json(root / "release-check-reports.json")
    certification = _read_json(root / "lts-certification.json")
    architecture = _read_json(root / "architecture.json")
    comparison = _read_json(root / "source-comparison.json")
    import_graph = _read_json(root / "import-graph.json")
    _check(checks, "reviewer_package_runtime_passed", runtime.get("status") == "passed")
    _check(checks, "reviewer_package_runtime_p1_zero", not list(runtime.get("p1_blockers") or []))
    _check(checks, "reviewer_package_architecture_passed", architecture.get("status") == "passed")
    _check(
        checks,
        "reviewer_package_lts_certification",
        certification.get("status") == "passed"
        and certification.get("runtime_status") == "passed"
        and (certification.get("summary") or {}).get("open_p1_count") == 0,
    )
    _check(
        checks,
        "reviewer_package_program_slice",
        not [
            row
            for row in import_graph.get("active_to_compatibility_imports") or []
            if str(row.get("importer") or "").startswith(
                (
                    "song_agent.domains.program",
                    "song_agent.application.program",
                    "song_agent.interfaces.api.routes.program",
                    "song_agent.interfaces.cli.commands.program",
                )
            )
        ],
    )
    baseline = comparison.get("v12.13") if isinstance(comparison.get("v12.13"), dict) else {}
    current = comparison.get("current") if isinstance(comparison.get("current"), dict) else {}
    _check(
        checks,
        "reviewer_package_active_source_reduced",
        isinstance(baseline.get("lines"), int)
        and isinstance(current.get("active_lines"), int)
        and current["active_lines"] <= baseline["lines"]
        and isinstance(current.get("lines"), int),
    )
    for workflow in ("quality", "nightly"):
        row = ci.get(workflow) if isinstance(ci.get(workflow), dict) else {}
        _check(
            checks,
            f"reviewer_package_ci_{workflow}",
            row.get("status") == "passed"
            and row.get("sha") == final_sha
            and row.get("evidence_kind") in {"github_workflow", "local_equivalent"},
        )
    profiles = release_checks.get("profiles") if isinstance(release_checks.get("profiles"), dict) else {}
    for profile in ("full", "v13", "latest", "ga", "security"):
        row = profiles.get(profile) if isinstance(profiles.get(profile), dict) else {}
        _check(checks, f"reviewer_package_release_check_{profile}", row.get("status") == "passed" and row.get("sha") == final_sha)
    suites = runtime.get("tests") if isinstance(runtime.get("tests"), dict) else {}
    for suite in ("active", "legacy"):
        row = suites.get(suite) if isinstance(suites.get(suite), dict) else {}
        _check(checks, f"reviewer_package_tests_{suite}", row.get("status") == "passed" and row.get("sha") == final_sha)
    _release_evidence_checks(checks, root, final_sha)


def _release_evidence_checks(checks: list[ImplementationDocument], root: Path, final_sha: str) -> None:
    migration = _read_json(root / "migration-rollback.json")
    performance = _read_json(root / "performance.json")
    alignment = _read_json(root / "release-alignment.json")
    _check(
        checks,
        "reviewer_package_migration_rehearsal",
        migration.get("status") == "passed"
        and migration.get("sha") == final_sha
        and int(migration.get("file_count") or 0) > 0
        and migration.get("rollback_identical") is True,
    )
    _check(
        checks,
        "reviewer_package_performance",
        performance.get("status") == "passed" and performance.get("sha") == final_sha,
    )
    _check(
        checks,
        "reviewer_package_release_alignment",
        alignment.get("status") == "passed" and alignment.get("sha") == final_sha,
    )


def _file_row(path: Path, root: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _check(checks: list[ImplementationDocument], check_id: str, passed: bool, **detail: Any) -> None:
    checks.append({"check_id": check_id, "status": "passed" if passed else "failed", **detail})


def _read_json(path: Path) -> ImplementationDocument:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _stable_hash(
        {key: value for key, value in payload.items() if key != "integrity_hash"}
    )


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_sensitive_or_local_data(root: Path) -> bool:
    patterns = (
        re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{12,}", re.IGNORECASE),
        re.compile(r"(?:api_key|access_token)\s*[:=]\s*[^*\s][^\s]{7,}", re.IGNORECASE),
        re.compile(r"[A-Za-z]:\\Users\\[^\\]+\\", re.IGNORECASE),
    )
    for path in root.iterdir():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in patterns):
            return True
    return False
