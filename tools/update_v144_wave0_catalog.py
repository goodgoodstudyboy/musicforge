from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from song_agent.platform.contracts.packages import (
    APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
    _document_hash,
    build_runtime_package_writer_policy,
    validate_runtime_package_registry_projection,
    validate_runtime_package_writer_policy,
)
from song_agent.platform.persistence.file_artifacts import (
    STATE_POLICY_RESOURCE,
    build_runtime_state_authority_policy,
    validate_runtime_state_authority_policy,
)
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.release_check.v14_wave0 import (
    BASELINE_PATH,
    CATALOG_PATH,
    build_wave0_baseline,
    evaluate_wave0,
)
from song_agent.release_check.v14_wave0_inventory import build_wave0_catalog
from song_agent.release_check.v14_wave0_ratchet import (
    dependency_regressions,
    quality_regressions,
    registry_regressions,
)
from song_agent.release_check.v14_wave0_registry import (
    load_wave0_registries,
    validate_wave0_registries,
)


def update(root: Path, *, check: bool = False) -> int:
    catalog_path = root / CATALOG_PATH
    baseline_path = root / BASELINE_PATH
    state_registry_path = root / "architecture-v14.4-state-authority-registry.json"
    runtime_policy_path = root / "song_agent/platform/persistence/runtime-state-authority-policy.json"
    package_writer_policy_path = root / "song_agent/platform/contracts/runtime-package-writer-policy.json"
    package_registry_projection_path = root / "song_agent/platform/contracts/runtime-package-registry.json"
    current_architecture_path = root / "docs/architecture/CURRENT.md"
    if not baseline_path.is_file():
        print("v14.4 Wave 0 approved baseline is missing; automatic bootstrap is forbidden")
        return 1
    existing = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not _frozen_baseline_schema_current(existing):
        print("v14.4 Wave 0 baseline schema migration rejected")
        return 1
    registries = load_wave0_registries(root)
    registry_blockers = validate_wave0_registries(
        registries,
        root=root,
        baseline_integrity_hash=str(existing.get("integrity_hash") or ""),
    )
    if registry_blockers:
        print("v14.4 Wave 0 registry validation failed: " + ", ".join(registry_blockers))
        return 1
    catalog = build_wave0_catalog(root)
    baseline = build_wave0_baseline(root, catalog)
    regressions = [
        *_surface_additions(existing, baseline),
        *_baseline_regressions(existing, baseline, registries["waivers"]),
    ]
    if regressions:
        print("v14.4 Wave 0 baseline regression rejected: " + ", ".join(regressions))
        return 1
    state_registry = registries["state"]
    if baseline.get("integrity_hash") != existing.get("integrity_hash"):
        state_registry = _rebind_state_exceptions(
            registries["state"],
            str(baseline.get("integrity_hash") or ""),
        )
        registry_hashes = catalog.get("registry_hashes")
        if not isinstance(registry_hashes, dict):
            raise ValueError("Wave 0 catalog registry hashes are missing.")
        registry_hashes["state"] = state_registry["integrity_hash"]
        catalog["integrity_hash"] = integrity_hash(catalog)
    generated_registries = dict(registries)
    generated_registries["state"] = state_registry
    runtime_policy = build_runtime_state_authority_policy(state_registry, baseline)
    package_writer_policy = build_runtime_package_writer_policy(registries["packages"])
    package_registry_projection = build_runtime_package_registry_projection(registries["packages"])
    current_architecture = _render_current_architecture_summary(
        current_architecture_path.read_text(encoding="utf-8"),
        catalog,
    )
    documents = {
        catalog_path: catalog,
        baseline_path: baseline,
        runtime_policy_path: runtime_policy,
        package_writer_policy_path: package_writer_policy,
        package_registry_projection_path: package_registry_projection,
    }
    if state_registry is not registries["state"]:
        documents[state_registry_path] = state_registry
    generated_blockers = _generated_document_blockers(
        root,
        generated_registries,
        catalog,
        baseline,
        runtime_policy,
        package_writer_policy,
        package_registry_projection,
    )
    if generated_blockers:
        print(
            "v14.4 Wave 0 generated document validation failed; approved anchor migration required: "
            + ", ".join(generated_blockers)
        )
        return 1
    if check:
        stale = [
            path.name
            for path, document in documents.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != _encoded(document)
        ]
        if current_architecture_path.read_text(encoding="utf-8") != current_architecture:
            stale.append(current_architecture_path.name)
        if stale:
            print("stale v14.4 Wave 0 catalogs: " + ", ".join(stale))
            return 1
        report = evaluate_wave0(root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["status"] == "passed" else 1
    outputs = {path: _encoded(document) for path, document in documents.items()}
    outputs[current_architecture_path] = current_architecture
    try:
        _transactional_write(outputs, verify=lambda: _verify_committed_wave0(root))
    except Exception as exc:
        print(f"v14.4 Wave 0 catalog update failed and was rolled back: {exc}")
        return 1
    print("v14.4 Wave 0 catalogs updated")
    return 0


def _generated_document_blockers(
    root: Path,
    registries: dict[str, dict[str, object]],
    catalog: dict[str, object],
    baseline: dict[str, object],
    state_policy: dict[str, object],
    package_writer_policy: dict[str, object],
    package_registry_projection: dict[str, object],
) -> list[str]:
    blockers = validate_wave0_registries(
        registries,
        root=root,
        baseline_integrity_hash=str(baseline.get("integrity_hash") or ""),
    )
    if not integrity_ok(catalog):
        blockers.append("v144_wave0_generated_catalog_integrity")
    if not integrity_ok(baseline):
        blockers.append("v144_wave0_generated_baseline_integrity")
    registry_hashes = catalog.get("registry_hashes")
    if not isinstance(registry_hashes, dict) or any(
        registry_hashes.get(key) != document.get("integrity_hash")
        for key, document in registries.items()
    ):
        blockers.append("v144_wave0_generated_catalog_registry_binding")
    if state_policy.get("integrity_hash") != STATE_POLICY_RESOURCE[1]:
        blockers.append("v144_wave0_state_runtime_policy_anchor_migration_required")
    blockers.extend(validate_runtime_state_authority_policy(state_policy))
    blockers.extend(validate_runtime_package_registry_projection(package_registry_projection))
    blockers.extend(validate_runtime_package_writer_policy(package_writer_policy, package_registry_projection))
    return sorted(set(blockers))


def _verify_committed_wave0(root: Path) -> None:
    report = evaluate_wave0(root)
    if report["status"] != "passed":
        blockers = report.get("blockers")
        detail = ", ".join(str(value) for value in blockers) if isinstance(blockers, list) else "unknown blocker"
        raise RuntimeError("Committed Wave 0 gate failed: " + detail)


def _transactional_write(outputs: dict[Path, str], *, verify: Callable[[], None]) -> None:
    originals = {path: path.read_bytes() if path.exists() else None for path in outputs}
    staged: dict[Path, Path] = {}
    try:
        for path, content in outputs.items():
            staged[path] = _stage_bytes(path, content.encode("utf-8"))
        for path, temporary in staged.items():
            _commit_replace(temporary, path)
        verify()
    except Exception as exc:
        rollback_errors: list[str] = []
        for path, content in originals.items():
            try:
                _restore_original(path, content)
            except Exception as rollback_exc:
                rollback_errors.append(f"{path}:{rollback_exc}")
        if rollback_errors:
            raise RuntimeError("Wave 0 rollback failed: " + ", ".join(rollback_errors)) from exc
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _stage_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _commit_replace(temporary: Path, path: Path) -> None:
    temporary.replace(path)


def _restore_original(path: Path, content: bytes | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
        return
    temporary = _stage_bytes(path, content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _surface_additions(existing: object, current: dict[str, object]) -> list[str]:
    if not isinstance(existing, dict):
        return ["invalid_existing_baseline"]
    old_freeze = existing.get("surface_freeze")
    new_freeze = current.get("surface_freeze")
    if not isinstance(old_freeze, dict) or not isinstance(new_freeze, dict):
        return ["invalid_surface_freeze"]
    old_sets = old_freeze.get("identity_sets")
    new_sets = new_freeze.get("identity_sets")
    frozen_registry = existing.get("registry_freeze")
    if not isinstance(old_sets, dict) or not isinstance(new_sets, dict):
        return ["invalid_identity_sets"]
    additions: list[str] = []
    for key, values in new_sets.items():
        old_values = old_sets.get(key)
        if not isinstance(values, list) or not isinstance(old_values, list):
            additions.append(f"{key}:invalid")
            continue
        registered = (
            set(cast_registry)
            if isinstance(frozen_registry, dict)
            and isinstance((cast_registry := frozen_registry.get(key)), dict)
            else set()
        )
        additions.extend(f"{key}:{value}" for value in sorted(set(values) - set(old_values) - registered))
    return additions


def _baseline_regressions(
    existing: object,
    current: dict[str, object],
    waivers: dict[str, object] | None = None,
) -> list[str]:
    if not isinstance(existing, dict):
        return ["invalid_existing_baseline"]
    old_quality = existing.get("quality_freeze")
    new_quality = current.get("quality_freeze")
    old_dependency = existing.get("dependency_baseline")
    new_dependency = current.get("dependency_baseline")
    old_registry = existing.get("registry_freeze")
    new_registry = current.get("registry_freeze")
    if not isinstance(old_quality, dict) or not isinstance(new_quality, dict):
        return ["invalid_quality_freeze"]
    if not isinstance(old_dependency, dict) or not isinstance(new_dependency, dict):
        return ["invalid_dependency_baseline"]
    if not isinstance(old_registry, dict) or not isinstance(new_registry, dict):
        return ["invalid_registry_freeze"]
    old_contracts = existing.get("registry_contracts")
    new_contracts = current.get("registry_contracts")
    if not isinstance(old_contracts, dict) or not isinstance(new_contracts, dict):
        return ["invalid_registry_contracts"]
    return [
        *registry_regressions(
            {"registry_contracts": old_contracts},
            {"registry_contracts": new_contracts},
            waivers or {"waivers": []},
            baseline_integrity_hash=str(existing.get("integrity_hash") or ""),
        ),
        *quality_regressions(old_quality, new_quality),
        *dependency_regressions(old_dependency, new_dependency),
        *registry_regressions(
            old_registry,
            new_registry,
            waivers or {"waivers": []},
            baseline_integrity_hash=str(existing.get("integrity_hash") or ""),
        ),
    ]


def _frozen_baseline_schema_current(document: object) -> bool:
    return (
        isinstance(document, dict)
        and document.get("package_type") == "musicforge_v144_wave0_baseline"
        and int(document.get("schema_version") or 0) == 5
    )


def _rebind_state_exceptions(registry: dict[str, object], baseline_integrity_hash: str) -> dict[str, object]:
    rebound = copy.deepcopy(registry)
    rows = rebound.get("writer_overlap_exceptions")
    if not baseline_integrity_hash or not isinstance(rows, list):
        raise ValueError("State exception rebinding requires a baseline hash and exception list.")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("State exception registry contains an invalid row.")
        row["baseline_integrity_hash"] = baseline_integrity_hash
    rebound["integrity_hash"] = integrity_hash(rebound)
    return rebound


def _encoded(document: dict[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_runtime_package_registry_projection(
    registry: dict[str, object],
    *,
    approved_registry_hash: str | None = APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
) -> dict[str, object]:
    registry_hash = str(registry.get("integrity_hash") or "")
    if (
        registry_hash != integrity_hash(registry)
        or (approved_registry_hash is not None and registry_hash != approved_registry_hash)
    ):
        raise ValueError("Package Registry is not the approved Wave 0 registry.")
    formal = {
        str(row.get("package_type") or ""): str(row.get("kind") or "")
        for row in _object_rows(registry.get("package_types"))
    }
    compatibility: dict[str, dict[str, object]] = {}
    for type_set in _object_rows(registry.get("package_type_sets")):
        if type_set.get("purpose") != "runtime_writer":
            continue
        writer_id = str(type_set.get("writer_id") or "")
        kinds = type_set.get("package_type_kinds")
        values = type_set.get("package_types")
        if not isinstance(kinds, dict) or not isinstance(values, list):
            raise ValueError("Runtime package type set declarations are missing.")
        for value in values:
            package_type = str(value or "")
            kind = str(kinds.get(package_type) or "")
            if package_type in formal:
                if formal[package_type] != kind:
                    raise ValueError(f"Package kind conflicts with the formal registry: {package_type}")
                continue
            row = compatibility.setdefault(package_type, {"kind": kind, "writer_ids": []})
            writer_ids = row.get("writer_ids")
            if not package_type or not kind or row.get("kind") != kind or not isinstance(writer_ids, list):
                raise ValueError(f"Compatibility package declaration is invalid: {package_type}")
            if writer_id not in writer_ids:
                writer_ids.append(writer_id)
    for row in compatibility.values():
        writer_ids = row["writer_ids"]
        if isinstance(writer_ids, list):
            writer_ids.sort()
    policy = build_runtime_package_writer_policy(registry)
    document: dict[str, object] = {
        "schema_version": 1,
        "registry_package_type": registry.get("package_type"),
        "registry_schema_version": registry.get("schema_version"),
        "registry_integrity_hash": registry_hash,
        "formal_type_kinds": dict(sorted(formal.items())),
        "compatibility_type_contracts": dict(sorted(compatibility.items())),
        "package_type_sets": policy["package_type_sets"],
        "writer_contracts": policy["writer_contracts"],
    }
    document["integrity_hash"] = _document_hash(document)
    return document


def _object_rows(value: object) -> list[dict[str, object]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _render_current_architecture_summary(text: str, catalog: dict[str, object]) -> str:
    start = "<!-- v14.4-wave0-summary:start -->"
    end = "<!-- v14.4-wave0-summary:end -->"
    if start not in text or end not in text:
        raise ValueError("CURRENT.md is missing the Wave 0 generated summary markers.")
    summary = catalog.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Wave 0 catalog summary is missing.")
    block = (
        f"{start}\n"
        f"- Four human-maintained registries define {summary['capability_count']} semantic capabilities, all "
        f"{summary['stores']} Store roles and physical namespaces, {summary['package_types']} observed package "
        f"types, {summary['package_sites']:,} legacy raw-write sites, and {summary['schemas']} schemas. Source "
        "scanning only verifies these declarations.\n"
        f"{end}"
    )
    prefix, remainder = text.split(start, 1)
    _, suffix = remainder.split(end, 1)
    return prefix + block + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="Update or verify the v14.4 Wave 0 frozen catalogs.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return update(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
