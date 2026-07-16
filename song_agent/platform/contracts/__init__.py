"""Versioned contracts shared across MusicForge domains."""

from song_agent.platform.contracts.documents import JsonDocument, JsonPrimitive, JsonValue
from song_agent.platform.contracts.errors import DomainError
from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.contracts.evidence_manifest import ExternalEvidenceManifest
from song_agent.platform.contracts.lifecycle import GenerationRef, ResetAuthorization, SignoffRef
from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.contracts.policy import (
    CurrentGenerationRequirement,
    EvidenceRequirement,
    GateResult,
    NoBlockerRequirement,
    PolicyProfile,
    QuorumRequirement,
    RuntimeVerificationRequirement,
)

__all__ = [
    "DomainError",
    "EvidenceRef",
    "ExternalEvidenceManifest",
    "GenerationRef",
    "JsonDocument",
    "JsonPrimitive",
    "JsonValue",
    "PackageSpec",
    "CurrentGenerationRequirement",
    "EvidenceRequirement",
    "GateResult",
    "NoBlockerRequirement",
    "PolicyProfile",
    "QuorumRequirement",
    "RuntimeVerificationRequirement",
    "ResetAuthorization",
    "SignoffRef",
]
