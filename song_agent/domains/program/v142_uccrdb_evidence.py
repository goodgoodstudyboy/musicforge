# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path, document_or as _document_or
import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore as UnifiedCommandCenterEvidenceReviewStore
from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package
from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION, verify_unified_command_center_reviewer_decision_board_package as verify_unified_command_center_reviewer_decision_board_package, write_unified_command_center_reviewer_decision_board_verification_report as write_unified_command_center_reviewer_decision_board_verification_report

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

ch = _make_deferred_global('ch')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch
    ch = namespace.get('ch', ch)
    _bind_deferred_defaults(namespace)


DEFAULT_POLICY = {
    "min_accepted_count": 2,
    "min_organization_count": 1,
    "required_roles": ["technical_reviewer", "release_owner"],
    "block_on_required_rejection": True,
    "block_on_any_rejection": False,
    "block_on_high_findings": True,
    "block_on_critical_findings": True,
}




def _sha256_path(path: Path | str | None) -> str | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _zip_manifest_hash(path: Path | str | None) -> str | None:
    if not path:
        return None
    try:
        with zipfile.ZipFile(Path(path)) as archive:
            return json.loads(archive.read("manifest.json").decode("utf-8")).get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None

def _path_or_none(value: object) -> Path | None:
    if not value:
        return None
    return Path(value)

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _safe_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_"})[:80] or "item"
