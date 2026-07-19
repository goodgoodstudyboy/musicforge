from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

from dataclasses import dataclass, field
from importlib import import_module
from typing import Callable


@dataclass(frozen=True)
class RuntimeIdentitySpec:
    """Extracts a canonical evidence identity from verifier-owned output."""

    component_id_fields: tuple[str, ...] = (
        "component_id",
        "program_id",
        "release_id",
        "center_id",
        "target_id",
        "submission_id",
        "operations_id",
    )
    generation_fields: tuple[str, ...] = ("generation", "current_generation")
    current_generation_fields: tuple[str, ...] = ("current_generation", "generation")
    current_fields: tuple[str, ...] = ("current",)
    source_hash_fields: tuple[str, ...] = ("source_hash", "manifest_hash")
    default_generation: int = 1

    def extract(
        self,
        report: DomainDocument,
        *,
        component_type: str,
        package_type: str,
    ) -> DomainDocument:
        component_id = _first_report_value(report, self.component_id_fields)
        generation = _positive_int(
            _first_report_value(report, self.generation_fields),
            default=self.default_generation,
        )
        current_generation = _positive_int(
            _first_report_value(report, self.current_generation_fields),
            default=generation,
        )
        explicit_current = _first_report_value(report, self.current_fields)
        current = (
            bool(explicit_current)
            if isinstance(explicit_current, bool)
            else report.get("status") == "passed" and generation == current_generation
        )
        return {
            "component_type": str(component_type),
            "component_id": str(component_id or ""),
            "generation": generation,
            "current_generation": current_generation,
            "current": current,
            "package_type": str(package_type),
            "source_hash": str(_first_report_value(report, self.source_hash_fields) or ""),
        }


@dataclass(frozen=True)
class RuntimeVerificationSpec:
    module: str
    function: str
    package_type: str
    verification_package_type: str
    defaults: tuple[tuple[str, object], ...] = ()
    proof_arguments: tuple[tuple[str, str], ...] = ()
    required_proofs: tuple[str, ...] = ()
    identity: RuntimeIdentitySpec = field(default_factory=RuntimeIdentitySpec)

    def verifier(self) -> Callable[..., DomainDocument]:
        return getattr(import_module(self.module), self.function)

    def extract_identity(self, report: DomainDocument, *, component_type: str) -> DomainDocument:
        return self.identity.extract(
            report,
            component_type=component_type,
            package_type=self.package_type,
        )


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    component_type: str
    bounded_context: str
    application_service: str
    runtime: RuntimeVerificationSpec
    gate_policies: tuple[str, ...] = ()
    cli_commands: tuple[str, ...] = ()
    api_routes: tuple[str, ...] = ()
    web_panel: str = ""
    release_checks: tuple[str, ...] = ()
    compatibility_aliases: tuple[str, ...] = ()


def _report_containers(report: ImplementationDocument) -> tuple[ImplementationDocument, ...]:
    identity_value = report.get("identity")
    summary_value = report.get("summary")
    source_value = report.get("source")
    identity: ImplementationDocument = _as_document(identity_value)
    summary: ImplementationDocument = _as_document(summary_value)
    verification_value = summary.get("verification")
    verification: ImplementationDocument = _as_document(verification_value)
    source: ImplementationDocument = _as_document(source_value)
    return identity, summary, report, verification, source


def _first_report_value(report: ImplementationDocument, fields: tuple[str, ...]) -> object:
    for container in _report_containers(report):
        for name in fields:
            value = container.get(name)
            if value not in (None, ""):
                return value
    return None


def _positive_int(value: object, *, default: int) -> int:
    if not isinstance(value, (int, float, str, bytes, bytearray)):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
