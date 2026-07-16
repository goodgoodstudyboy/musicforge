"""Shared verification primitives for MusicForge evidence packages."""

from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import (
    canonical_text_bytes,
    integrity_hash,
    integrity_ok,
    sha256_bytes,
    sha256_file,
    sha256_or_integrity,
    sha256_text_file,
    stable_hash,
)
from song_agent.platform.verification.model import build_check, build_verification_report
from song_agent.platform.verification.registry import VerifierCapability, VerifierCapabilityRegistry, active_verifier_registry
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry,
    raw_central_directory_entry_names,
    raw_unsafe_entry_names,
    zip_has_no_trailing_data,
)

__all__ = [
    "build_check",
    "build_verification_report",
    "canonical_text_bytes",
    "integrity_hash",
    "integrity_ok",
    "is_safe_zip_entry",
    "raw_central_directory_entry_names",
    "raw_unsafe_entry_names",
    "sha256_bytes",
    "sha256_file",
    "sha256_or_integrity",
    "sha256_text_file",
    "stable_hash",
    "verify_package_envelope",
    "VerifierCapability",
    "VerifierCapabilityRegistry",
    "active_verifier_registry",
    "zip_has_no_trailing_data",
]
