"""Versioned contracts shared across MusicForge domains."""

from song_agent.platform.contracts.coercion import as_document, as_float, as_int, as_list, as_path, as_text, document_or, list_or
from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument, JsonDocument, JsonPrimitive, JsonValue
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
    "ImplementationDocument",
    "DomainDocument",
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
    "as_document",
    "as_float",
    "as_int",
    "as_list",
    "as_path",
    "as_text",
    "document_or",
    "list_or",
]
