# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_distribution_kit import DISTRIBUTION_KIT_BLOCKED_KEYS as DISTRIBUTION_KIT_BLOCKED_KEYS, PublicTrustCenterDistributionKitStore as PublicTrustCenterDistributionKitStore, distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report as write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE as ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE as ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_manifest_hash as accepted_evidence_manifest_hash, verification_hash as verification_hash


DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION = 1
ACCEPTANCE_RESPONSE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_response"
ACCEPTANCE_TEMPLATE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_template"


ACCEPTANCE_ALLOWED_RESULTS = {"accepted", "needs_changes", "rejected"}



RESPONSE_RECORD_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at"}
RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS = {"response_hash", "payload_hash", "integrity_hash"}
MAX_RESPONSE_BYTES = 512 * 1024


class PublicTrustCenterDistributionKitAcceptanceError(ValueError):
    pass


class PublicTrustCenterDistributionKitAcceptanceNotFoundError(PublicTrustCenterDistributionKitAcceptanceError):
    pass


class PublicTrustCenterDistributionKitAcceptanceStateError(PublicTrustCenterDistributionKitAcceptanceError):
    pass


from song_agent.domains.trust import v142_ptcdka_readiness as _v142_ptcdka_readiness
from song_agent.domains.trust.v142_ptcdka_readiness import PublicTrustCenterDistributionKitAcceptanceStore
from song_agent.domains.trust import v142_ptcdka_evidence as _v142_ptcdka_evidence
from song_agent.domains.trust.v142_ptcdka_evidence import (
    response_template,
    verify_response_document,
    response_payload_hash,
    response_record_hash,
    response_summary,
    accepted_evidence_summary,
    redaction_summary,
    _evidence_documents,
    _public_response,
    _response_binding_summary,
    _response_state_status,
    _response_binding_stale,
    _binding_from_response,
    _require_response_binding,
    _reject_path_payload,
    _payload_bytes,
    _response_payload_from_bytes,
    _read_zip_json,
    _read_json_default,
    _write_json,
    _write_text,
    _read_text,
    _append_jsonl,
    _file_record,
    _zip_entries,
    _is_file,
    _write_zip,
    _sha256,
    _evidence_readme,
    _evidence_verify_text,
    _ensure_within,
    _fs_path,
    _safe_id,
    _next_response_id,
    _next_change_request_id,
    _check,
    _redaction_findings,
    _sanitize,
)

_v142_ptcdka_readiness.bind_globals(globals())
_v142_ptcdka_evidence.bind_globals(globals())
