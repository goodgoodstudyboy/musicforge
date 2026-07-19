# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import tempfile as tempfile
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package as verify_public_trust_center_acceptance_board_signoff_archive_package
from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package as verify_public_trust_center_acceptance_board_package
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import acceptance_board_verification_hash as acceptance_board_verification_hash
from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package as verify_public_trust_center_anchor_registry_package
from song_agent.domains.trust.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package as verify_public_trust_center_anchor_transparency_package
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import verification_hash as _accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.trust.public_trust_center_publication_contracts import PUBLICATION_BLOCKED_KEYS as PUBLICATION_BLOCKED_KEYS, PUBLICATION_PACKAGE_TYPE as PUBLICATION_PACKAGE_TYPE, PUBLICATION_REQUIRED_PACKAGE_KEYS as PUBLICATION_REQUIRED_PACKAGE_KEYS, PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE as PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE, publication_channel_state_hash as publication_channel_state_hash, publication_manifest_hash as publication_manifest_hash, publication_report_hash as publication_report_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _bind_deferred_defaults(namespace)


PUBLICATION_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 512
BASE_REQUIRED_ENTRIES = {
    "README.txt",
    "publication-manifest.json",
    "publication-report.json",
    "package-index.json",
    "verification-index.json",
    "mirror-policy.json",
    "checksum/SHA256SUMS.txt",
    "checksum/SHA256SUMS.json",
    "site/index.html",
    "site/trust-center.html",
    "site/packages.html",
    "site/verification.html",
    "anchors/ptc-anchor-checkpoint-current.json",
    "anchors/public-trust-center.delivery-anchor.json",
}
FIXED_PACKAGE_PATHS = {
    "packages/public-trust-center.zip",
    "packages/public-trust-center-distribution-kit.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
    "packages/public-trust-center-acceptance-board.zip",
    "packages/public-trust-center-acceptance-board-signoff-archive.zip",
}
FIXED_VERIFICATION_PATHS = {
    "verification-reports/public-trust-center-verification-report.json",
    "verification-reports/distribution-kit-verification-report.json",
    "verification-reports/anchor-registry-verification-report.json",
    "verification-reports/anchor-transparency-verification-report.json",
    "verification-reports/acceptance-board-verification-report.json",
    "verification-reports/acceptance-board-signoff-archive-verification-report.json",
}




def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _verification_hash(report: DomainDocument) -> str | None:
    if not report:
        return None
    if report.get("package_kind") == "public_trust_center_acceptance_board":
        return acceptance_board_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}

def _read_json_file(path: Path | None) -> DomainDocument:
    if path is None:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return _as_document(value)

def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

def _redaction_findings(name: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        regex = pattern[0] if isinstance(pattern, tuple) else pattern
        if regex.search(text):
            findings.append({"path": name, "pattern": regex.pattern[:80]})
    return findings

def _blocked_key_findings(name: str, value: object) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": str(key)})
            findings.extend(_blocked_key_findings(name, nested))
    elif isinstance(value, list):
        for nested in value:
            findings.extend(_blocked_key_findings(name, nested))
    return findings

def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())

def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text

def _from_fs_path(value: str) -> Path:
    if os.name != "nt":
        return Path(value)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value.removeprefix("\\\\?\\UNC\\"))
    if value.startswith("\\\\?\\"):
        return Path(value.removeprefix("\\\\?\\"))
    return Path(value)
