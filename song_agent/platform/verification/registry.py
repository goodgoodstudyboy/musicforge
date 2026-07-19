from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import ast
import inspect
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec


@dataclass(frozen=True)
class VerifierCapability:
    capability_id: str
    component_type: str
    module: str
    function: str
    package_type_attr: str
    verification_type_attr: str
    check_prefix: str
    required_entries_attr: str
    optional_entries_attr: str = ""
    allowed_entry_patterns: tuple[str, ...] = ()
    nested_zip_policy: str = "deny"
    allowed_nested_entries_attr: str = ""
    allowed_nested_entries: tuple[str, ...] = ()
    allowed_nested_patterns: tuple[str, ...] = ()
    required_proofs: tuple[str, ...] = ()
    lifecycle_bindings: tuple[str, ...] = ()
    identity_fields: tuple[str, ...] = ("program_id", "generation", "current_generation", "source_hash")

    def package_spec(self) -> PackageSpec:
        module = import_module(self.module)
        required = frozenset(str(value) for value in getattr(module, self.required_entries_attr))
        optional = (
            frozenset(str(value) for value in getattr(module, self.optional_entries_attr))
            if self.optional_entries_attr
            else frozenset()
        )
        nested = set(self.allowed_nested_entries)
        if self.allowed_nested_entries_attr:
            nested.update(str(value) for value in getattr(module, self.allowed_nested_entries_attr))
        return PackageSpec(
            package_type=str(getattr(module, self.package_type_attr)),
            verification_package_type=str(getattr(module, self.verification_type_attr)),
            check_prefix=self.check_prefix,
            required_entries=required,
            optional_entries=optional,
            allowed_entry_patterns=self.allowed_entry_patterns,
            nested_zip_policy="allowlisted" if self.nested_zip_policy == "allowlisted" else "deny",
            allowed_nested_entries=frozenset(nested),
            allowed_nested_patterns=self.allowed_nested_patterns,
            manifest_entry="manifest.json",
            max_zip_size_mb=256,
            max_uncompressed_size_mb=512,
            max_entry_count=2000,
        )

    def verifier(self) -> Any:
        return getattr(import_module(self.module), self.function)

    def external_proofs_adopted(self) -> bool:
        module = import_module(self.module)
        function_object = getattr(module, self.function, None)
        source_file = inspect.getsourcefile(function_object) if callable(function_object) else None
        source_path = Path(source_file or str(module.__file__))
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        function = next(
            (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == self.function),
            None,
        )
        if function is None or not self.required_proofs:
            return False
        parameters = {arg.arg for arg in (*function.args.args, *function.args.kwonlyargs)}
        used_names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        return set(self.required_proofs).issubset(parameters & used_names)

    def inventory(self) -> DomainDocument:
        spec = self.package_spec()
        return {
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
        }


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

    def inventory(self) -> list[DomainDocument]:
        return [row.inventory() for row in self._capabilities]

    def adoption_report(self) -> DomainDocument:
        rows = [_verifier_adoption_row(row) for row in self._capabilities]
        package_types = [row["package_type"] for row in rows]
        unique = len(package_types) == len(set(package_types))
        return {
            "schema_version": 1,
            "status": "passed" if unique and all(row["status"] == "passed" for row in rows) else "failed",
            "package_types_unique": unique,
            "rows": rows,
        }


def _capability(
    component_type: str,
    module_leaf: str,
    function: str,
    package_type_attr: str,
    verification_type_attr: str,
    check_prefix: str,
    required_entries_attr: str,
    **kwargs: Any,
) -> VerifierCapability:
    return VerifierCapability(
        capability_id=f"program.{component_type}",
        component_type=component_type,
        module=f"song_agent.domains.program.{module_leaf}",
        function=function,
        package_type_attr=package_type_attr,
        verification_type_attr=verification_type_attr,
        check_prefix=check_prefix,
        required_entries_attr=required_entries_attr,
        **kwargs,
    )


ACTIVE_VERIFIER_CAPABILITIES = (
    _capability(
        "unified_release_program", "unified_release_program_verifier", "verify_unified_release_program_package",
        "UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE", "UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE", "urp_kernel",
        "BASE_REQUIRED_ENTRIES", optional_entries_attr="SIGNED_ENTRIES",
        required_proofs=("external_evidence_manifest_path", "program_signoff_binding_path"),
        lifecycle_bindings=("current_external_evidence", "signoff_binding", "history_chain"),
    ),
    _capability(
        "unified_release_program_operations", "unified_release_program_operations_verifier",
        "verify_unified_release_program_operations_package", "UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE", "urp_ops_kernel", "REQUIRED_ENTRIES",
        required_proofs=("program_zip_path", "program_verification_report_path", "program_signoff_binding_path", "external_evidence_manifest_path"),
        lifecycle_bindings=("current_program", "signoff_binding", "change_request"),
    ),
    _capability(
        "unified_release_program_handoff", "unified_release_program_handoff_verifier",
        "verify_unified_release_program_handoff_package", "UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE", "urph_kernel", "HANDOFF_REQUIRED_ENTRIES",
        required_proofs=("external_evidence_manifest_path", "handoff_signoff_binding_path"),
        lifecycle_bindings=("accepted_evidence", "signoff_binding", "history_chain"),
    ),
    _capability(
        "unified_release_program_vault", "unified_release_program_vault_verifier",
        "verify_unified_release_program_vault_package", "UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE", "urpv_kernel", "STATIC_REQUIRED_ENTRIES",
        allowed_entry_patterns=(r"packages/accepted-evidence/[A-Za-z0-9_.-]+\.zip", r"proofs/accepted-evidence/[A-Za-z0-9_.-]+-(?:verification-report|response-verification-report|response-binding-summary)\.json"),
        nested_zip_policy="allowlisted",
        allowed_nested_entries=("packages/unified-release-program.zip", "packages/unified-release-program-operations.zip", "packages/unified-release-program-handoff.zip"),
        allowed_nested_patterns=(r"packages/accepted-evidence/[A-Za-z0-9_.-]+\.zip",),
        required_proofs=("vault_anchor_path",), lifecycle_bindings=("external_anchor", "nested_runtime_verification"),
    ),
    _capability(
        "unified_release_program_vault_operations", "unified_release_program_vault_operations_verifier",
        "verify_unified_release_program_vault_operations_package", "UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE", "urpvo_kernel", "REQUIRED_ENTRIES",
        nested_zip_policy="allowlisted", allowed_nested_entries=("packages/current-vault.zip",),
        required_proofs=("signoff_binding_path",), lifecycle_bindings=("current_vault", "signoff_binding", "custody_history"),
    ),
    _capability(
        "unified_release_program_continuity", "unified_release_program_continuity_verifier",
        "verify_unified_release_program_continuity_package", "UNIFIED_RELEASE_PROGRAM_CONTINUITY_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE", "urpc_kernel", "REQUIRED_ENTRIES",
        required_proofs=("signoff_binding_path", "vault_operations_archive_path", "vault_operations_verification_report_path", "vault_operations_signoff_binding_path"),
        lifecycle_bindings=("current_vault_operations", "signoff_binding", "recovery_drill"),
    ),
    _capability(
        "unified_release_program_continuity_kit", "unified_release_program_continuity_distribution_verifier",
        "verify_unified_release_program_continuity_distribution_package", "UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE", "urpcdk_kernel", "REQUIRED_ENTRIES",
        nested_zip_policy="allowlisted", allowed_nested_entries_attr="NESTED_ZIP_ENTRIES",
        required_proofs=("kit_verification_report_path",), lifecycle_bindings=("nested_runtime_verification", "receiver_receipt_binding"),
    ),
    _capability(
        "unified_release_program_continuity_acceptance", "unified_release_program_continuity_acceptance_verifier",
        "verify_unified_release_program_continuity_acceptance_package", "UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_ARCHIVE_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE", "urpca_kernel", "FIXED_ARCHIVE_ENTRIES",
        allowed_entry_patterns=(r"responses/[A-Za-z0-9_.-]+\.json", r"responses/[A-Za-z0-9_.-]+-(?:binding-summary|verification-report)\.json", r"accepted-evidence/[A-Za-z0-9_.-]+/(?:accepted-evidence|evidence-report|original-response-public|response-binding-summary|response-verification-summary)\.json"),
        required_proofs=("continuity_kit_path", "continuity_kit_verification_report_path", "signoff_binding_path"),
        lifecycle_bindings=("current_kit", "external_response_proofs", "signoff_binding"),
    ),
    _capability(
        "unified_release_program_continuity_acceptance_change", "unified_release_program_continuity_acceptance_change_verifier",
        "verify_unified_release_program_continuity_acceptance_change_package", "UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE", "urpca_cc_kernel", "FIXED_ARCHIVE_ENTRIES",
        allowed_entry_patterns=(r"cr/[A-Za-z0-9_.-]+/(?:request|binding|approval)\.json", r"rp/[A-Za-z0-9_.-]+/(?:proof|binding)\.json", r"gen/g[0-9]{6}/(?:verification|signoff-binding|source)\.json"),
        required_proofs=("acceptance_archive_path", "acceptance_verification_report_path", "acceptance_signoff_binding_path"),
        lifecycle_bindings=("current_acceptance", "change_request", "reset_proof", "generation_chain"),
    ),
    _capability(
        "unified_release_program_continuity_command_center", "unified_release_program_continuity_command_center_verifier",
        "verify_unified_release_program_continuity_command_center_package", "UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE", "urpccc_kernel", "REQUIRED_ENTRIES",
        required_proofs=("evidence_manifest_path",), lifecycle_bindings=("runtime_evidence_manifest", "current_generation"),
    ),
    _capability(
        "unified_release_program_continuity_command_center_signoff", "unified_release_program_continuity_command_center_signoff_verifier",
        "verify_unified_release_program_continuity_command_center_signoff_package", "COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE",
        "COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE", "urpcccs_kernel", "ARCHIVE_REQUIRED_ENTRIES",
        required_proofs=("signoff_binding_path", "command_center_zip_path", "command_center_verification_report_path", "command_center_external_evidence_manifest_path"),
        lifecycle_bindings=("current_command_center", "signoff_binding", "history_chain", "change_request"),
    ),
    _capability(
        "unified_release_program_receiver_acceptance", "unified_release_program_continuity_command_center_acceptance_verifier",
        "verify_unified_release_program_continuity_command_center_acceptance_package", "ARCHIVE_PACKAGE_TYPE",
        "ARCHIVE_VERIFICATION_PACKAGE_TYPE", "urpccca_kernel", "ARCHIVE_ENTRIES",
        required_proofs=("signoff_binding_path", "review_pack_path", "review_pack_verification_report_path"),
        lifecycle_bindings=("current_handoff", "external_response_proofs", "signoff_binding", "history_chain"),
    ),
    _capability(
        "unified_release_program_receiver_acceptance_change", "unified_release_program_continuity_command_center_acceptance_change_verifier",
        "verify_unified_release_program_continuity_command_center_acceptance_change_package",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_ARCHIVE_PACKAGE_TYPE",
        "UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_ACCEPTANCE_CHANGE_VERIFICATION_PACKAGE_TYPE",
        "urpcccacc_kernel", "FIXED_ARCHIVE_ENTRIES",
        allowed_entry_patterns=(r"cr/[A-Za-z0-9_.-]+/(?:request|binding|approval)\.json", r"rp/[A-Za-z0-9_.-]+/(?:proof|binding)\.json", r"gen/g[0-9]{6}/(?:verification|signoff-binding|source)\.json"),
        required_proofs=("acceptance_archive_path", "acceptance_verification_report_path", "acceptance_signoff_binding_path", "previous_acceptance_root"),
        lifecycle_bindings=("current_acceptance", "previous_acceptance_root", "change_request", "reset_proof", "generation_chain"),
    ),
)


active_verifier_registry = VerifierCapabilityRegistry(ACTIVE_VERIFIER_CAPABILITIES)


def _verifier_adoption_row(capability: VerifierCapability) -> ImplementationDocument:
    module = import_module(capability.module)
    source = Path(str(module.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module.__file__))
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
    if not callable(getattr(module, capability.function, None)):
        blockers.append("verifier_entry_missing")
    if "verify_package_envelope" not in call_names:
        blockers.append("shared_envelope_not_called")
    if "PackageSpec" not in call_names:
        blockers.append("package_spec_not_constructed")
    if custom_helpers:
        blockers.append("custom_zip_security_helpers")
    if not capability.external_proofs_adopted():
        blockers.append("external_proof_contract_not_adopted")
    return {
        **capability.inventory(),
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "package_type": spec.package_type,
    }
