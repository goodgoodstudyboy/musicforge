"""Product capability registry used by evidence and interface layers."""

from song_agent.capabilities.model import CapabilitySpec, RuntimeIdentitySpec, RuntimeVerificationSpec
from song_agent.capabilities.registry import CapabilityRegistry, capability_registry

__all__ = ["CapabilityRegistry", "CapabilitySpec", "RuntimeIdentitySpec", "RuntimeVerificationSpec", "capability_registry"]
