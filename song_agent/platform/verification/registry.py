from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from song_agent.platform.contracts.packages import NestedZipPolicy, PackageSpec
from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document

VerifierCallable = Callable[[Path, Mapping[str, object]], Mapping[str, object]]

@dataclass(frozen=True)
class VerifierCapability:
    capability_id: str
    component_type: str
    module: str
    function: str
    verifier: VerifierCallable
    source_path: Path
    archive_type: str
    verification_report_type: str
    check_prefix: str
    required_entries: frozenset[str]
    optional_entries: frozenset[str] = frozenset()
    allowed_entry_patterns: tuple[str, ...] = ()
    nested_zip_policy: NestedZipPolicy = "deny"
    allowed_nested_entries: frozenset[str] = frozenset()
    allowed_nested_patterns: tuple[str, ...] = ()
    required_proofs: tuple[str, ...] = ()
    lifecycle_bindings: tuple[str, ...] = ()
    identity_fields: tuple[str, ...] = ("program_id", "generation", "current_generation", "source_hash")

    def package_spec(self) -> PackageSpec:
        return PackageSpec(
            self.archive_type, self.verification_report_type, self.check_prefix,
            self.required_entries, self.optional_entries,
            allowed_entry_patterns=self.allowed_entry_patterns, nested_zip_policy=self.nested_zip_policy,
            allowed_nested_entries=self.allowed_nested_entries, allowed_nested_patterns=self.allowed_nested_patterns,
            manifest_entry="manifest.json", max_zip_size_mb=256, max_uncompressed_size_mb=512, max_entry_count=2000,
        )

    def verify(self, package_path: Path, arguments: Mapping[str, object]) -> JsonDocument:
        return normalize_json_document(self.verifier(package_path, arguments))

    def external_proofs_adopted(self) -> bool:
        tree = ast.parse(self.source_path.read_text(encoding="utf-8"), filename=str(self.source_path))
        function = next(
            (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == self.function),
            None,
        )
        if function is None or not self.required_proofs:
            return False
        parameters = {arg.arg for arg in (*function.args.args, *function.args.kwonlyargs)}
        used_names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        return set(self.required_proofs).issubset(parameters & used_names)

    def inventory(self) -> JsonDocument:
        spec = self.package_spec()
        return normalize_json_document({
            "capability_id": self.capability_id,
            "component_type": self.component_type,
            "module": self.module,
            "function": self.function,
            "package_type": spec.package_type,
            "verification_package_type": spec.verification_package_type,
            "manifest_entry": spec.manifest_entry,
            "required_entries": sorted(spec.required_entries),
            "optional_entries": sorted(spec.optional_entries),
            "allowed_entry_patterns": list(spec.allowed_entry_patterns),
            "nested_zip_policy": spec.nested_zip_policy,
            "allowed_nested_entries": sorted(spec.allowed_nested_entries),
            "allowed_nested_patterns": list(spec.allowed_nested_patterns),
            "required_proofs": list(self.required_proofs),
            "identity_fields": list(self.identity_fields),
            "lifecycle_bindings": list(self.lifecycle_bindings),
        })


class VerifierCapabilityRegistry:
    def __init__(self, capabilities: tuple[VerifierCapability, ...]) -> None:
        self._capabilities = capabilities
        ids = [row.capability_id for row in capabilities]
        components = [row.component_type for row in capabilities]
        if len(ids) != len(set(ids)) or len(components) != len(set(components)):
            raise ValueError("Verifier capability identities must be unique.")

    def all(self) -> tuple[VerifierCapability, ...]:
        return self._capabilities

    def get(self, component_type: str) -> VerifierCapability:
        return next(row for row in self._capabilities if row.component_type == component_type)

    def inventory(self) -> list[JsonDocument]:
        return [row.inventory() for row in self._capabilities]

    def adoption_report(self) -> JsonDocument:
        rows = [_verifier_adoption_row(row) for row in self._capabilities]
        package_types = [row["package_type"] for row in rows]
        unique = len(package_types) == len(set(package_types))
        return normalize_json_document({
            "schema_version": 1,
            "status": "passed" if unique and all(row["status"] == "passed" for row in rows) else "failed",
            "package_types_unique": unique,
            "rows": rows,
        })

def _verifier_adoption_row(capability: VerifierCapability) -> JsonDocument:
    source = capability.source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(capability.source_path))
    call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    custom_helpers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_raw_zip_entry_names", "_is_safe_zip_entry", "_zip_has_no_trailing_data"}
    }
    spec = capability.package_spec()
    blockers = []
    if not callable(capability.verifier):
        blockers.append("verifier_entry_missing")
    if "verify_package_envelope" not in call_names:
        blockers.append("shared_envelope_not_called")
    if "PackageSpec" not in call_names:
        blockers.append("package_spec_not_constructed")
    if custom_helpers:
        blockers.append("custom_zip_security_helpers")
    if not capability.external_proofs_adopted():
        blockers.append("external_proof_contract_not_adopted")
    return normalize_json_document({
        **capability.inventory(),
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "package_type": spec.package_type,
    })
