from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from song_agent.platform.verification.hashing import integrity_ok
from song_agent.release_check.v14_wave0_package_registry import validate_package_registry
from song_agent.release_check.v14_wave0_state_registry import validate_state_registry


CAPABILITY_REGISTRY_PATH = "architecture-v14.4-capability-registry.json"
STATE_REGISTRY_PATH = "architecture-v14.4-state-authority-registry.json"
PACKAGE_REGISTRY_PATH = "architecture-v14.4-package-schema-registry.json"
WAIVER_REGISTRY_PATH = "architecture-v14.4-wave0-waivers.json"

REGISTRY_TYPES = {
    "capabilities": "musicforge_v144_canonical_capability_registry",
    "state": "musicforge_v144_state_authority_registry",
    "packages": "musicforge_v144_package_schema_registry",
    "waivers": "musicforge_v144_wave0_waiver_registry",
}
REGISTRY_CONTRACTS = {
    "capabilities": {"package_type": REGISTRY_TYPES["capabilities"], "schema_version": 1},
    "state": {"package_type": REGISTRY_TYPES["state"], "schema_version": 4},
    "packages": {"package_type": REGISTRY_TYPES["packages"], "schema_version": 7},
    "waivers": {"package_type": REGISTRY_TYPES["waivers"], "schema_version": 2},
}
WAVE0_TARGET_VERSION = "14.4.0"
WAIVER_APPROVERS = {"architecture-reviewers", "release-owner", "security-reviewer"}
SURFACE_KEYS = (
    "stores",
    "cli_commands",
    "cli_registration_points",
    "api_routes",
    "packages",
    "package_types",
    "package_sites",
    "verifiers",
    "schemas",
    "studio_panels",
    "release_checks",
)
CLASSIFICATIONS = {
    "authority",
    "projection",
    "workflow",
    "evidence_package",
    "compatibility_adapter",
}
def load_wave0_registries(root: Path) -> dict[str, dict[str, object]]:
    return {
        "capabilities": _read(root / CAPABILITY_REGISTRY_PATH),
        "state": _read(root / STATE_REGISTRY_PATH),
        "packages": _read(root / PACKAGE_REGISTRY_PATH),
        "waivers": _read(root / WAIVER_REGISTRY_PATH),
    }


def validate_wave0_registries(
    registries: dict[str, dict[str, object]],
    *,
    root: Path | None = None,
    baseline_integrity_hash: str | None = None,
) -> list[str]:
    blockers: list[str] = []
    for key, contract in REGISTRY_CONTRACTS.items():
        document = registries.get(key) or {}
        if document.get("package_type") != contract["package_type"] or not integrity_ok(document):
            blockers.append(f"v144_wave0_registry_integrity:{key}")
        if document.get("schema_version") != contract["schema_version"]:
            blockers.append(f"v144_wave0_registry_schema:{key}")
    capabilities = cast(list[dict[str, object]], registries["capabilities"].get("capabilities") or [])
    capability_ids = _unique_ids(capabilities, "capability_id", "capability", blockers)
    surface_owner = _capability_checks(capabilities, capability_ids, blockers, root=root)
    validate_state_registry(
        registries["state"],
        capability_ids,
        surface_owner["stores"],
        blockers,
        root=root,
        baseline_integrity_hash=baseline_integrity_hash,
    )
    validate_package_registry(registries["packages"], capability_ids, surface_owner, blockers)
    _waiver_checks(
        registries["waivers"],
        blockers,
        root=root,
        baseline_integrity_hash=baseline_integrity_hash,
    )
    return sorted(set(blockers))


def capability_surface_owner(registry: dict[str, object]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {key: {} for key in SURFACE_KEYS}
    for row in cast(list[dict[str, object]], registry.get("capabilities") or []):
        capability_id = str(row.get("capability_id") or "")
        surfaces = cast(dict[str, object], row.get("surfaces") or {})
        for key in SURFACE_KEYS:
            for identity in cast(list[object], surfaces.get(key) or []):
                result[key][str(identity)] = capability_id
    return result


def waiver_for(registry: dict[str, object], *, target_type: str, target_id: str, field: str) -> dict[str, object] | None:
    for row in cast(list[dict[str, object]], registry.get("waivers") or []):
        if (
            row.get("target_type") == target_type
            and row.get("target_id") == target_id
            and field in cast(list[object], row.get("fields") or [])
        ):
            return row
    return None


def _capability_checks(
    rows: list[dict[str, object]],
    capability_ids: set[str],
    blockers: list[str],
    *,
    root: Path | None,
) -> dict[str, dict[str, str]]:
    surface_owner: dict[str, dict[str, str]] = {key: {} for key in SURFACE_KEYS}
    for row in rows:
        capability_id = str(row.get("capability_id") or "")
        for field in ("bounded_context", "owner", "source_of_truth", "classification"):
            if not str(row.get(field) or "").strip():
                blockers.append(f"v144_wave0_capability_field:{capability_id}:{field}")
        if row.get("classification") not in CLASSIFICATIONS:
            blockers.append(f"v144_wave0_capability_classification:{capability_id}")
        dependencies = row.get("depends_on")
        if not isinstance(dependencies, list):
            blockers.append(f"v144_wave0_capability_dependencies:{capability_id}")
        else:
            for dependency in dependencies:
                if dependency not in capability_ids or dependency == capability_id:
                    blockers.append(f"v144_wave0_capability_dependency:{capability_id}:{dependency}")
            declaration = row.get("dependency_declaration")
            if not isinstance(declaration, dict) or not str(declaration.get("reason") or ""):
                blockers.append(f"v144_wave0_capability_dependency_declaration:{capability_id}")
        tests = row.get("tests")
        if not isinstance(tests, list) or not tests:
            blockers.append(f"v144_wave0_capability_tests:{capability_id}")
        elif root is not None:
            for test in tests:
                if not (root / str(test)).is_file():
                    blockers.append(f"v144_wave0_capability_test_missing:{capability_id}:{test}")
        for field in ("migration", "rollback"):
            declaration = row.get(field)
            if (
                not isinstance(declaration, dict)
                or declaration.get("status") not in {"declared", "not_applicable"}
                or not str(declaration.get("reason") or "")
            ):
                blockers.append(f"v144_wave0_capability_{field}:{capability_id}")
        surfaces = row.get("surfaces")
        if not isinstance(surfaces, dict):
            blockers.append(f"v144_wave0_capability_surfaces:{capability_id}")
            continue
        for key in SURFACE_KEYS:
            values = surfaces.get(key)
            if not isinstance(values, list) or len(values) != len(set(values)):
                blockers.append(f"v144_wave0_capability_surface_list:{capability_id}:{key}")
                continue
            for identity in values:
                identity_text = str(identity)
                previous = surface_owner[key].get(identity_text)
                if previous is not None and previous != capability_id:
                    blockers.append(f"v144_wave0_surface_owner_conflict:{key}:{identity_text}")
                surface_owner[key][identity_text] = capability_id
    return surface_owner


def _waiver_checks(
    registry: dict[str, object],
    blockers: list[str],
    *,
    root: Path | None,
    baseline_integrity_hash: str | None,
) -> None:
    rows = cast(list[dict[str, object]], registry.get("waivers") or [])
    _unique_ids(rows, "waiver_id", "waiver", blockers)
    for row in rows:
        waiver_id = str(row.get("waiver_id") or "")
        for field in (
            "target_type",
            "target_id",
            "reason",
            "owner",
            "expires_version",
            "adr",
            "approved_by",
            "approved_at",
            "baseline_integrity_hash",
            "old_value_hash",
            "new_value_hash",
        ):
            if not str(row.get(field) or ""):
                blockers.append(f"v144_wave0_waiver_field:{waiver_id}:{field}")
        fields = row.get("fields")
        if not isinstance(fields, list) or len(fields) != 1:
            blockers.append(f"v144_wave0_waiver_fields:{waiver_id}")
        if row.get("status") != "approved":
            blockers.append(f"v144_wave0_waiver_status:{waiver_id}")
        if row.get("approved_by") not in WAIVER_APPROVERS:
            blockers.append(f"v144_wave0_waiver_approver:{waiver_id}")
        if str(row.get("owner") or "").strip().lower() in {"nobody", "unknown", "none"}:
            blockers.append(f"v144_wave0_waiver_owner:{waiver_id}")
        if _version_key(str(row.get("expires_version") or "")) < _version_key(WAVE0_TARGET_VERSION):
            blockers.append(f"v144_wave0_waiver_expired:{waiver_id}")
        if baseline_integrity_hash is None or row.get("baseline_integrity_hash") != baseline_integrity_hash:
            blockers.append(f"v144_wave0_waiver_baseline:{waiver_id}")
        for field in ("baseline_integrity_hash", "old_value_hash", "new_value_hash"):
            if not _sha256_text(row.get(field)):
                blockers.append(f"v144_wave0_waiver_hash:{waiver_id}:{field}")
        try:
            approved_at = datetime.fromisoformat(str(row.get("approved_at") or "").replace("Z", "+00:00"))
            if approved_at.tzinfo is None:
                raise ValueError
        except ValueError:
            blockers.append(f"v144_wave0_waiver_approved_at:{waiver_id}")
        if root is not None and row.get("adr"):
            adr_path = root / str(row["adr"])
            if not adr_path.is_file():
                blockers.append(f"v144_wave0_waiver_adr:{waiver_id}")
            else:
                text = adr_path.read_text(encoding="utf-8")
                expected = (
                    f"Waiver-ID: {waiver_id}",
                    f"Waiver-Target: {row.get('target_type')}/{row.get('target_id')}",
                    f"Waiver-Field: {fields[0] if isinstance(fields, list) and fields else ''}",
                    f"Waiver-Old-Value-SHA256: {row.get('old_value_hash')}",
                    f"Waiver-New-Value-SHA256: {row.get('new_value_hash')}",
                )
                if any(marker not in text for marker in expected):
                    blockers.append(f"v144_wave0_waiver_adr_binding:{waiver_id}")


def _unique_ids(rows: list[dict[str, object]], key: str, label: str, blockers: list[str]) -> set[str]:
    values = [str(row.get(key) or "") for row in rows]
    if "" in values or len(values) != len(set(values)):
        blockers.append(f"v144_wave0_registry_ids:{label}")
    return set(values) - {""}


def _sha256_text(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _version_key(value: str) -> tuple[int, ...]:
    result: list[int] = []
    for token in value.lstrip("v").split("."):
        try:
            result.append(int(token))
        except ValueError:
            result.append(0)
    return tuple(result)


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, object], value)
