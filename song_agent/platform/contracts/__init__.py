"""Versioned contracts shared across MusicForge domains."""

from song_agent.platform.contracts.coercion import (
    as_document,
    as_documents,
    as_float,
    as_int,
    as_list,
    as_path,
    as_string_list,
    as_text,
    document_or,
    list_or,
)
from song_agent.platform.contracts.documents import (
    JsonDocument,
    JsonPrimitive,
    JsonValue,
    is_json_document,
    is_json_document_list,
    is_json_value,
)
from song_agent.platform.contracts.errors import DomainError
from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.contracts.evidence_manifest import ExternalEvidenceManifest
from song_agent.platform.contracts.lifecycle import GenerationRef, ResetAuthorization, SignoffRef
from song_agent.platform.contracts.packages import PackageSpec, require_registered_package_type
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
    "require_registered_package_type",
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
    "as_documents",
    "as_float",
    "as_int",
    "as_list",
    "as_path",
    "as_string_list",
    "as_text",
    "document_or",
    "list_or",
    "is_json_document",
    "is_json_document_list",
    "is_json_value",
]
