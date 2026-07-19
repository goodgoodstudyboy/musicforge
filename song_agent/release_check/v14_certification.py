from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import importlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.capabilities import capability_registry
from song_agent.platform.persistence import V14MigrationOrchestrator
from song_agent.platform.verification.registry import active_verifier_registry
from song_agent.platform.lifecycle.registry import active_lifecycle_registry
from song_agent.release_check_lifecycle_kernel import run_lifecycle_kernel_smoke
from song_agent.release_check_verification_kernel import (
    run_kernel_adoption_smoke,
    run_shared_kernel_security_smoke,
    run_verification_kernel_smoke,
)


EXPECTED_CONTEXTS = frozenset({"creation", "studio", "quality", "delivery", "trust", "program"})
DOMAIN_CONTRACTS = {
    "creation": ("song_agent.domains.creation.provider", "song_agent.provider"),
    "studio": ("song_agent.domains.studio.projects", "song_agent.projects"),
    "quality": ("song_agent.domains.quality.audio_campaigns", "song_agent.audio_campaigns"),
    "delivery": ("song_agent.domains.delivery.releases", "song_agent.releases"),
    "trust": ("song_agent.domains.trust.public_trust_center", "song_agent.public_trust_center"),
    "program": ("song_agent.domains.program.unified_release_program", "song_agent.unified_release_program"),
}


def evaluate_v14_domain_vertical_slices(
    root: Path,
    *,
    snapshot: DomainDocument | None = None,
) -> DomainDocument:
    migration = _read_json(root / "architecture-v14-domain-migration.json")
    retirement = _read_json(root / "architecture-v14-compatibility-retirement.json")
    architecture_snapshot = snapshot or build_architecture_snapshot(root)
    blockers: list[str] = []
    if migration.get("schema_version") != 1 or migration.get("baseline_tag") != "v13.8.0":
        blockers.append("v14_domain_migration_identity")
    waves = migration.get("waves") or []
    contexts = {str(context) for wave in waves for context in wave.get("contexts") or []}
    if contexts != EXPECTED_CONTEXTS:
        blockers.append("v14_domain_context_inventory")
    retirement_rows = {str(row.get("module")): row for row in retirement.get("entries") or []}
    context_counts: Counter[str] = Counter()
    module_count = 0
    facade_contract_count = 0
    for wave_index, wave in enumerate(waves, 1):
        modules = wave.get("modules") or []
        if int(wave.get("module_count") or -1) != len(modules):
            blockers.append(f"v14_domain_wave_{wave_index}_count")
        wave_contexts = set(str(value) for value in wave.get("contexts") or [])
        for row in modules:
            module_count += 1
            source = str(row.get("source") or "")
            target = str(row.get("target") or "")
            context = _target_context(target)
            context_counts[context] += 1
            if context not in wave_contexts:
                blockers.append(f"v14_domain_wave_{wave_index}_ownership:{source}")
            target_path = _module_path(root, target)
            source_path = _module_path(root, source)
            if target_path is None:
                blockers.append(f"v14_domain_target_missing:{target}")
            if source_path is None:
                blockers.append(f"v14_domain_facade_missing:{source}")
            elif target_path is not None and _facade_contract_matches(source, target):
                facade_contract_count += 1
            else:
                blockers.append(f"v14_domain_facade_contract:{source}")
            retired = retirement_rows.get(source) or {}
            if retired.get("retirement_status") != "retired" or retired.get("target_module") != target:
                blockers.append(f"v14_domain_retirement_binding:{source}")
    if module_count != 270:
        blockers.append(f"v14_domain_module_count:{module_count}")
    if len(architecture_snapshot.get("active_to_compatibility_imports") or []) != 0:
        blockers.append("v14_domain_active_compatibility_edges")
    contract_results = _domain_contract_results()
    blockers.extend(f"v14_domain_contract:{context}" for context, passed in contract_results.items() if not passed)
    capabilities = capability_registry.all()
    capability_contexts = Counter(row.bounded_context for row in capabilities)
    for row in capabilities:
        if row.bounded_context not in EXPECTED_CONTEXTS:
            blockers.append(f"v14_domain_capability_context:{row.component_type}")
        if not row.application_service or ".legacy_dependencies." in row.application_service:
            blockers.append(f"v14_domain_capability_service:{row.component_type}")
        if ".legacy_dependencies." in row.runtime.module:
            blockers.append(f"v14_domain_capability_verifier:{row.component_type}")
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_domain_vertical_slice_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": {
            "context_count": len(contexts),
            "wave_count": len(waves),
            "module_count": module_count,
            "context_module_counts": dict(sorted(context_counts.items())),
            "contract_context_count": sum(contract_results.values()),
            "facade_contract_count": facade_contract_count,
            "capability_count": len(capabilities),
            "capability_context_counts": dict(sorted(capability_contexts.items())),
            "active_to_compatibility_import_count": len(architecture_snapshot.get("active_to_compatibility_imports") or []),
        },
    }


def evaluate_v14_verification_lifecycle_security(
    root: Path,
    *,
    snapshot: DomainDocument | None = None,
) -> DomainDocument:
    architecture_snapshot = snapshot or build_architecture_snapshot(root)
    verification = run_verification_kernel_smoke(root)
    shared = run_shared_kernel_security_smoke(root)
    lifecycle = run_lifecycle_kernel_smoke(root)
    adoption = run_kernel_adoption_smoke(root)
    verifier_adoption = active_verifier_registry.adoption_report()
    lifecycle_adoption = active_lifecycle_registry.adoption_report()
    signals = {
        "verification_kernel": verification[0],
        "shared_security": shared[0],
        "lifecycle_kernel": lifecycle[0],
        "active_attack_corpora": adoption[0],
        "verifier_registry": verifier_adoption.get("status") == "passed",
        "lifecycle_registry": lifecycle_adoption.get("status") == "passed",
        "custom_zip_helpers_zero": not any((architecture_snapshot.get("security_helper_counts") or {}).values()),
        "custom_lifecycle_algorithms_zero": not any(
            (architecture_snapshot.get("active_custom_lifecycle_algorithm_counts") or {}).values()
        ),
    }
    blockers = [f"v14_security_{name}" for name, passed in signals.items() if not passed]
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_verification_lifecycle_security_report",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "signals": signals,
        "details": {
            "verification": verification[1],
            "shared": shared[1],
            "lifecycle": lifecycle[1],
            "adoption": adoption[1],
            "verifier_capability_count": len(active_verifier_registry.all()),
            "lifecycle_capability_count": len(active_lifecycle_registry.all()),
        },
    }


def evaluate_v14_migration_rollback() -> DomainDocument:
    with tempfile.TemporaryDirectory(prefix="musicforge-v14-migration-smoke-") as temp:
        workspace = Path(temp) / ".musicforge"
        source = workspace / "unified-release-programs" / "release-001"
        source.mkdir(parents=True)
        (source / "program.json").write_text(
            '{"component_type":"unified_release_program","generation":1,"program_id":"release-001","status":"ready"}\n',
            encoding="utf-8",
        )
        (source / "program-signoff-history.jsonl").write_text(
            '{"event_hash":"event-001","event_type":"signed"}\n', encoding="utf-8"
        )
        result = V14MigrationOrchestrator(workspace).rollback_rehearsal()
    return result


def run_v14_domain_vertical_slice_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_v14_domain_vertical_slices(root)
    return report["status"] == "passed", json.dumps(report, sort_keys=True)


def run_v14_verification_lifecycle_security_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_v14_verification_lifecycle_security(root)
    return report["status"] == "passed", json.dumps(report, sort_keys=True)


def run_v14_migration_rollback_smoke(root: Path) -> tuple[bool, str]:
    del root
    report = evaluate_v14_migration_rollback()
    return report["status"] == "passed", json.dumps(report, sort_keys=True)


def _domain_contract_results() -> dict[str, bool]:
    results: dict[str, bool] = {}
    for context, (canonical_name, facade_name) in DOMAIN_CONTRACTS.items():
        canonical = importlib.import_module(canonical_name)
        facade = importlib.import_module(facade_name)
        canonical_public = {name for name in vars(canonical) if not name.startswith("_")}
        facade_public = {name for name in vars(facade) if not name.startswith("_")}
        shared = canonical_public & facade_public
        results[context] = bool(shared) and all(getattr(canonical, name) is getattr(facade, name) for name in shared)
    return results


def _facade_contract_matches(facade_name: str, canonical_name: str) -> bool:
    try:
        canonical = importlib.import_module(canonical_name)
        facade = importlib.import_module(facade_name)
    except (AttributeError, ImportError, ModuleNotFoundError):
        return False
    exports = tuple(str(name) for name in getattr(facade, "__all__", ()) if str(name).isidentifier())
    return not exports or all(
        hasattr(canonical, name) and hasattr(facade, name) and getattr(canonical, name) is getattr(facade, name)
        for name in exports
    )


def _target_context(target: str) -> str:
    parts = target.split(".")
    return parts[2] if len(parts) > 2 and parts[:2] == ["song_agent", "domains"] else "unknown"


def _module_path(root: Path, module: str) -> Path | None:
    relative = Path(*module.split("."))
    path = root / relative.with_suffix(".py")
    if path.is_file():
        return path
    package = root / relative / "__init__.py"
    return package if package.is_file() else None


def _read_json(path: Path) -> ImplementationDocument:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value
