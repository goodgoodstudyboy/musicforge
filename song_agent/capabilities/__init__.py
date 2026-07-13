"""Product capability registry used by evidence and interface layers."""

from song_agent.capabilities.model import CapabilitySpec, RuntimeVerificationSpec
from song_agent.capabilities.registry import CapabilityRegistry, capability_registry

__all__ = ["CapabilityRegistry", "CapabilitySpec", "RuntimeVerificationSpec", "capability_registry"]
