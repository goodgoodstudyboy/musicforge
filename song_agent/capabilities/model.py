from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable


@dataclass(frozen=True)
class RuntimeVerificationSpec:
    module: str
    function: str
    package_type: str
    verification_package_type: str
    defaults: tuple[tuple[str, Any], ...] = ()
    proof_arguments: tuple[tuple[str, str], ...] = ()
    required_proofs: tuple[str, ...] = ()

    def verifier(self) -> Callable[..., dict[str, Any]]:
        return getattr(import_module(self.module), self.function)


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
