# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import os as os
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.contracts.lifecycle import ResetAuthorization as ResetAuthorization
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, ChangeRequestService as ChangeRequestService, ResetService as ResetService, SignoffService as SignoffService
from song_agent.platform.lifecycle import HistoryChain as HistoryChain
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.repository import sync_active_v12_state as sync_active_v12_state
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.sanitization import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_continuity_command_center import UnifiedReleaseProgramContinuityCommandCenterStore as UnifiedReleaseProgramContinuityCommandCenterStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import ARCHIVE_REQUIRED_ENTRIES as ARCHIVE_REQUIRED_ENTRIES, COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION as COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, HANDOFF_REQUIRED_ENTRIES as HANDOFF_REQUIRED_ENTRIES, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package, write_unified_release_program_continuity_command_center_final_handoff_verification_report as write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report as write_unified_release_program_continuity_command_center_signoff_verification_report
from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_package as verify_unified_release_program_continuity_command_center_package

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

_safe_id = _make_deferred_global('_safe_id')

def bind_globals(namespace: dict[str, object]) -> None:
    global _safe_id
    _safe_id = namespace.get('_safe_id', _safe_id)
    _bind_deferred_defaults(namespace)


RESET_ACTION = "reset_command_center_signoff"
RESET_CHANGE_TYPE = "reset_command_center_signoff"




class UnifiedReleaseProgramContinuityCommandCenterSignoffStoreLifecycleMixin:
    def _preserve_current_archive(self, program_id: str, signoff_hash: object) -> None:
        if not signoff_hash:
            return
        destination = self.archive_history_dir(program_id) / f"a-{_safe_id(str(signoff_hash))[:16]}"
        if destination.exists():
            return
        destination.mkdir(parents=True, exist_ok=False)
        snapshots = (
            (self.signoff_path(program_id), "signoff.json"),
            (self.signoff_binding_path(program_id), "binding.json"),
            (self.archive_zip_path(program_id), "archive.zip"),
            (self.archive_verification_report_path(program_id), "archive-verification.json"),
            (self.final_handoff_zip_path(program_id), "handoff.zip"),
            (self.final_handoff_verification_report_path(program_id), "handoff-verification.json"),
        )
        for path, name in snapshots:
            if path.exists():
                shutil.copy2(path, destination / name)

    def _clear_current_outputs(self, program_id: str) -> None:
        for root in (self.archive_dir(program_id), self.final_handoff_dir(program_id)):
            if root.exists():
                shutil.rmtree(root)
        for path in (self.archive_zip_path(program_id), self.archive_verification_report_path(program_id), self.final_handoff_zip_path(program_id), self.final_handoff_verification_report_path(program_id)):
            path.unlink(missing_ok=True)
