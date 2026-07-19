# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE as GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION as GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok as ga_readiness_integrity_ok
from song_agent.domains.creation.lts_backup_verifier import verify_maintenance_backup_zip as verify_maintenance_backup_zip
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.distribution_verifier import verify_distribution_package as verify_distribution_package
from song_agent.domains.quality.release_audio_command_center import evidence_to_verifier_kwargs as audio_command_center_evidence_to_kwargs
from song_agent.domains.quality.release_audio_command_center_verifier import verify_release_audio_command_center_package as verify_release_audio_command_center_package
from song_agent.domains.trust.release_operations_verifier import verify_release_operations_package as verify_release_operations_package
from song_agent.domains.delivery.release_verifier import verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submission_verifier import verify_submission_package as verify_submission_package
from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package as verify_trust_operations_hub_package

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

key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global key
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_PACKAGE_TYPE = "musicforge_unified_command_center"
UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_verification"
UNIFIED_COMMAND_CENTER_SCHEMA_VERSION = 1
COMPONENT_KEYS = (
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
)
RUNTIME_COMPONENT_KEYS = {
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
}
EXPECTED_VERIFICATION_PACKAGE_TYPES: dict[str, set[str]] = {
    "release": {"musicforge_release_verification"},
    "distribution": {"musicforge_distribution_verification"},
    "submission": {"musicforge_submission_verification"},
    "operations": {"musicforge_release_operations_verification"},
    "maintenance": {"musicforge_lts_maintenance_backup_verification_report"},
    "audio-command-center": {"release_audio_command_center_verification"},
    "trust-operations-hub": {"musicforge_trust_operations_hub_verification"},
}
REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "source.json",
    "command-center-report.json",
    "evidence-graph.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "gap-plan.json",
    "safe-runbook.json",
    "runbook-result.json",
    "verification-index.json",
    *{f"component-fingerprints/{key}.json" for key in COMPONENT_KEYS},
}
SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]




def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
