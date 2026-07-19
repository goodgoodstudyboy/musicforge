# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.acceptance_profiles import AcceptanceProfile as AcceptanceProfile, get_acceptance_profile as get_acceptance_profile, profile_payload as profile_payload
from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_summary as audio_health_summary
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health, music_health_allows_review as music_health_allows_review, music_health_summary as music_health_summary
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.regression_songbook import BUILTIN_SONGBOOK_ID as BUILTIN_SONGBOOK_ID, BUILTIN_SONGBOOK_VERSION as BUILTIN_SONGBOOK_VERSION, list_regression_songs as list_regression_songs
from song_agent.domains.creation.renderers.audio import RendererError as RendererError, load_renderer_config as load_renderer_config, render_audio as render_audio, renderer_configured as renderer_configured
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongRequest as SongRequest

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

AcceptanceCase = _make_deferred_global('AcceptanceCase')
AcceptanceNotFoundError = _make_deferred_global('AcceptanceNotFoundError')
AcceptanceStateError = _make_deferred_global('AcceptanceStateError')
AcceptanceSuite = _make_deferred_global('AcceptanceSuite')
AcceptanceValidationError = _make_deferred_global('AcceptanceValidationError')
_report_integrity_core = _make_deferred_global('_report_integrity_core')
_report_verification = _make_deferred_global('_report_verification')
_request_summary = _make_deferred_global('_request_summary')
acceptance_source_state = _make_deferred_global('acceptance_source_state')
build_acceptance_report = _make_deferred_global('build_acceptance_report')
item = _make_deferred_global('item')
stable_hash = _make_deferred_global('stable_hash')

def bind_globals(namespace: dict[str, object]) -> None:
    global AcceptanceCase, AcceptanceNotFoundError, AcceptanceStateError, AcceptanceSuite, AcceptanceValidationError, _report_integrity_core, _report_verification
    global _request_summary, acceptance_source_state, build_acceptance_report, item, stable_hash
    AcceptanceCase = namespace.get('AcceptanceCase', AcceptanceCase)
    AcceptanceNotFoundError = namespace.get('AcceptanceNotFoundError', AcceptanceNotFoundError)
    AcceptanceStateError = namespace.get('AcceptanceStateError', AcceptanceStateError)
    AcceptanceSuite = namespace.get('AcceptanceSuite', AcceptanceSuite)
    AcceptanceValidationError = namespace.get('AcceptanceValidationError', AcceptanceValidationError)
    _report_integrity_core = namespace.get('_report_integrity_core', _report_integrity_core)
    _report_verification = namespace.get('_report_verification', _report_verification)
    _request_summary = namespace.get('_request_summary', _request_summary)
    acceptance_source_state = namespace.get('acceptance_source_state', acceptance_source_state)
    build_acceptance_report = namespace.get('build_acceptance_report', build_acceptance_report)
    item = namespace.get('item', item)
    stable_hash = namespace.get('stable_hash', stable_hash)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_SUITE_SCHEMA_VERSION = 1
ACCEPTANCE_CASE_SCHEMA_VERSION = 1
LISTENING_REVIEW_SCHEMA_VERSION = 1
ACCEPTANCE_REPORT_SCHEMA_VERSION = 1
ACCEPTANCE_SIGNOFF_SCHEMA_VERSION = 1
SUITE_STATUSES = {"draft", "generated", "needs_review", "passed", "failed", "signed", "archived"}
CASE_STATUSES = {"pending", "generated", "health_failed", "needs_review", "accepted", "waived", "rejected"}
SIGNED_ACCEPTANCE_STATUSES = {"signed", "force_signed"}




class AcceptanceStoreEvidenceMixin:
    def verify_report(self, suite_id: str, report: DomainDocument | None = None) -> DomainDocument:
        report_data = sanitize_metadata(_document_or(report, read_json(self.report_path(suite_id))))
        current = build_acceptance_report(self, self.get_suite(suite_id))
        verification = _report_verification(
            str(report_data.get("source_hash") or ""),
            stable_hash(acceptance_source_state(self, self.get_suite(suite_id))),
            stable_hash(_report_integrity_core(report_data)),
            stable_hash(_report_integrity_core(current)),
        )
        report_data["verification"] = verification
        if verification["status"] != "passed":
            report_data["status"] = "failed"
            blockers = list(report_data.get("blockers", []) if isinstance(report_data.get("blockers"), list) else [])
            if verification["source_status"] != "passed" and "acceptance report source hash mismatch" not in blockers:
                blockers.append("acceptance report source hash mismatch")
            if verification["content_status"] != "passed" and "acceptance report content hash mismatch" not in blockers:
                blockers.append("acceptance report content hash mismatch")
            report_data["blockers"] = blockers
            summary = dict(_as_document(report_data.get("summary")))
            summary["blocking_count"] = int(summary.get("blocking_count", 0) or 0) + 1
            report_data["summary"] = summary
        return sanitize_metadata(report_data)

    def read_events(self, suite_id: str) -> list[DomainDocument]:
        path = self.events_path(suite_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return sanitize_metadata(rows)

    def ensure_mutable(self, suite: AcceptanceSuite) -> None:
        if suite.status == "archived":
            raise AcceptanceStateError("Archived acceptance suites are read-only.")
        if suite.status == "signed" or suite.latest_signoff_summary.get("status") in SIGNED_ACCEPTANCE_STATUSES or self.read_signoff(suite.suite_id, default={}).get("status") in SIGNED_ACCEPTANCE_STATUSES:
            raise AcceptanceStateError("Signed acceptance suites cannot be modified. Reset signoff before changing this suite.")

    def append_event(self, suite_id: str, event_type: str, payload: DomainDocument) -> None:
        path = self.events_path(suite_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload})
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _copy_project_version_artifacts(self, case: AcceptanceCase) -> None:
        if not case.project_id or not case.version_id:
            raise AcceptanceValidationError("project_id and version_id are required for project_version cases.")
        document = self.project_store.get_project(case.project_id)
        version = next((item for item in document.versions if item.version_id == case.version_id), None)
        if version is None:
            raise AcceptanceNotFoundError(case.version_id)
        run_dir = Path(version.output_dir)
        case_dir = self.case_dir(case.suite_id, case.case_id)
        required = {
            run_dir / "data" / "song-plan.json": case_dir / "song-plan.json",
            run_dir / "renders" / "song.mid": case_dir / "song.mid",
        }
        for source, target in required.items():
            if not source.exists():
                raise AcceptanceStateError(f"Project version artifact is missing: {source.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name in ("validator-report.json", "quality.json", "quality-report.json", "run-summary.json"):
            source = run_dir / "data" / name
            if source.exists():
                shutil.copy2(source, case_dir / name)
        audio_source = run_dir / "renders" / "song.wav"
        if audio_source.exists():
            shutil.copy2(audio_source, case_dir / "song.wav")
        case.job_id = version.job_id
        case.request_summary = _request_summary(version.request)

    def _reserve_suite_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            suite_id = f"suite-{index:06d}"
            try:
                (self.root / suite_id).mkdir(parents=True, exist_ok=False)
                return suite_id
            except FileExistsError:
                continue
        raise AcceptanceValidationError("Unable to allocate acceptance suite id.")

    def _next_case_id(self, suite_id: str) -> str:
        used = {case.case_id for case in self.list_cases(suite_id)}
        self.cases_dir(suite_id).mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            case_id = f"case-{index:06d}"
            if case_id not in used:
                return case_id
        raise AcceptanceValidationError("Unable to allocate acceptance case id.")

    def _recalculate_suite(self, suite: AcceptanceSuite) -> None:
        try:
            cases = self._read_cases(suite.suite_id) if self.cases_dir(suite.suite_id).exists() else []
        except AcceptanceNotFoundError:
            cases = []
        suite.case_count = len(cases)
        suite.accepted_count = sum(1 for case in cases if case.status in {"accepted", "waived"})
        suite.failed_count = sum(1 for case in cases if case.status in {"health_failed", "rejected"})
