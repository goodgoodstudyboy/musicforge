# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.quality.audio_campaign_governance import AudioCampaignGovernanceStore as AudioCampaignGovernanceStore
from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore as AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaign_remediation import AudioCampaignRemediationStore as AudioCampaignRemediationStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore as AudioCampaignStore
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_certification import ReleaseAudioCertificationStore as ReleaseAudioCertificationStore
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE as RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE, RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION as RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, verify_release_audio_timeline_package as verify_release_audio_timeline_package, write_release_audio_timeline_verification_report as write_release_audio_timeline_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

ReleaseAudioTimelineNotFoundError = _make_deferred_global('ReleaseAudioTimelineNotFoundError')
ReleaseAudioTimelineStateError = _make_deferred_global('ReleaseAudioTimelineStateError')
_bounded = _make_deferred_global('_bounded')
_checks = _make_deferred_global('_checks')
_derive_from_events = _make_deferred_global('_derive_from_events')
_event = _make_deferred_global('_event')
_event_ledger_hash = _make_deferred_global('_event_ledger_hash')
_file_record = _make_deferred_global('_file_record')
_integrity_hash = _make_deferred_global('_integrity_hash')
_read_jsonl = _make_deferred_global('_read_jsonl')
_read_optional_json = _make_deferred_global('_read_optional_json')
_readme = _make_deferred_global('_readme')
_semantic_hash = _make_deferred_global('_semantic_hash')
_sha256_path = _make_deferred_global('_sha256_path')
_write_jsonl = _make_deferred_global('_write_jsonl')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseAudioTimelineNotFoundError, ReleaseAudioTimelineStateError, _bounded, _checks, _derive_from_events, _event, _event_ledger_hash, _file_record
    global _integrity_hash, _read_jsonl, _read_optional_json, _readme, _semantic_hash, _sha256_path, _write_jsonl
    global item
    ReleaseAudioTimelineNotFoundError = namespace.get('ReleaseAudioTimelineNotFoundError', ReleaseAudioTimelineNotFoundError)
    ReleaseAudioTimelineStateError = namespace.get('ReleaseAudioTimelineStateError', ReleaseAudioTimelineStateError)
    _bounded = namespace.get('_bounded', _bounded)
    _checks = namespace.get('_checks', _checks)
    _derive_from_events = namespace.get('_derive_from_events', _derive_from_events)
    _event = namespace.get('_event', _event)
    _event_ledger_hash = namespace.get('_event_ledger_hash', _event_ledger_hash)
    _file_record = namespace.get('_file_record', _file_record)
    _integrity_hash = namespace.get('_integrity_hash', _integrity_hash)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _readme = namespace.get('_readme', _readme)
    _semantic_hash = namespace.get('_semantic_hash', _semantic_hash)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _write_jsonl = namespace.get('_write_jsonl', _write_jsonl)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)






class ReleaseAudioTimelineStoreReadinessMixin:
    def timelines_root(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-timelines"

    def timeline_dir(self, release_id: str, timeline_id: str) -> Path:
        return self.timelines_root(release_id) / timeline_id

    def current_path(self, release_id: str) -> Path:
        return self.timelines_root(release_id) / "current-timeline.json"

    def report_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "audio-timeline-report.json"

    def event_ledger_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "event-ledger.jsonl"

    def track_index_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "track-timeline-index.json"

    def trend_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "quality-trend.json"

    def taxonomy_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "issue-taxonomy.json"

    def risk_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "risk-register.json"

    def bindings_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "evidence-bindings.json"

    def signoff_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "timeline-signoff.json"

    def export_dir(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "export"

    def zip_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "release-audio-timeline.zip"

    def verification_report_path(self, release_id: str, timeline_id: str | None = None) -> Path:
        return self.timeline_dir(release_id, self._resolve_timeline_id(release_id, timeline_id)) / "verification-report.json"

    def list_timelines(self, release_id: str) -> DomainDocument:
        root = self.timelines_root(release_id)
        current = self._current_timeline_id(release_id)
        timelines = []
        if root.exists():
            for path in sorted(root.iterdir()):
                if path.is_dir() and path.name.startswith("ratl-"):
                    report = _read_optional_json(path / "audio-timeline-report.json")
                    signoff = _read_optional_json(path / "timeline-signoff.json")
                    timelines.append({"timeline_id": path.name, "status": report.get("status", "missing"), "signed": signoff.get("status") == "signed", "summary": report.get("summary", {})})
        return {"release_id": release_id, "current_timeline_id": current, "timelines": timelines}

    def read_timeline(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.report_path(release_id, timeline_id)))

    def read_events(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        events = _read_jsonl(self.event_ledger_path(release_id, timeline_id))
        return {"release_id": release_id, "timeline_id": self._resolve_timeline_id(release_id, timeline_id), "events": sanitize_metadata(events)}

    def read_track_index(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.track_index_path(release_id, timeline_id)))

    def read_quality_trend(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.trend_path(release_id, timeline_id)))

    def read_issue_taxonomy(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.taxonomy_path(release_id, timeline_id)))

    def read_risk_register(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.risk_path(release_id, timeline_id)))

    def read_evidence_bindings(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        return sanitize_metadata(read_json(self.bindings_path(release_id, timeline_id)))

    def refresh_timeline(self, release_id: str, *, force_new: bool = False) -> DomainDocument:
        with self.lock:
            docs = self._build_documents(release_id, timeline_id=None)
            current_id = self._current_timeline_id(release_id)
            if current_id:
                current_report = _read_optional_json(self.report_path(release_id, current_id))
                current_signed = self.signoff_path(release_id, current_id).exists()
                same_source = current_report.get("source_hash") == docs["report"].get("source_hash")
                if current_signed and same_source and not force_new:
                    return {"status": current_report.get("status"), "timeline_id": current_id, "report": current_report, "current": True, "signed": True}
                if not current_signed and same_source and not force_new:
                    timeline_id = current_id
                else:
                    timeline_id = self._next_timeline_id(release_id)
            else:
                timeline_id = self._next_timeline_id(release_id)
            docs = self._with_timeline_id(docs, release_id, timeline_id)
            self._write_documents(release_id, timeline_id, docs)
            self._write_current(release_id, timeline_id, docs["report"])
            return {"status": docs["report"].get("status"), "timeline_id": timeline_id, "report": docs["report"], "current": True, "signed": False}

    def signoff_timeline(self, release_id: str, timeline_id: str | None = None, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            if self.signoff_path(release_id, timeline_id).exists():
                raise ReleaseAudioTimelineStateError("Release Audio Timeline is already signed.")
            report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
            if report.get("status") == "failed":
                raise ReleaseAudioTimelineStateError("Release Audio Timeline has blockers.")
            if int((risks.get("summary") or {}).get("blocking_risk_count") or 0) > 0:
                raise ReleaseAudioTimelineStateError("Release Audio Timeline has blocking risks.")
            if ((bindings.get("bindings") or {}).get("release_audio_certification") or {}).get("status") != "passed":
                raise ReleaseAudioTimelineStateError("Release Audio Timeline Certification evidence is not passed.")
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                    "signoff_id": f"ratls-{timeline_id}",
                    "release_id": release_id,
                    "timeline_id": timeline_id,
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-timeline", 120),
                    "role": _bounded(payload.get("role") or "audio-timeline-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release audio timeline accepted.", 1000),
                    "source_hash": report.get("source_hash"),
                    "timeline_report_hash": report.get("integrity_hash"),
                    "event_ledger_hash": _event_ledger_hash(events),
                    "track_index_hash": track_index.get("integrity_hash"),
                    "quality_trend_hash": trend.get("integrity_hash"),
                    "issue_taxonomy_hash": taxonomy.get("integrity_hash"),
                    "risk_register_hash": risks.get("integrity_hash"),
                    "evidence_bindings_hash": bindings.get("integrity_hash"),
                    "summary": report.get("summary", {}),
                }
            )
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id, timeline_id), signoff)
            self._write_current(release_id, timeline_id, report)
            return {"status": "signed", "timeline_id": timeline_id, "signoff": signoff, "report": report}

    def export_timeline(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
            signoff = _read_optional_json(self.signoff_path(release_id, timeline_id))
            export_dir = self.export_dir(release_id, timeline_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[DomainDocument] = []

            def write_entry(rel: str, payload: DomainDocument | list[DomainDocument] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                elif rel.endswith(".jsonl"):
                    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in payload) + "\n", encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("audio-timeline-report.json", report)
            write_entry("track-timeline-index.json", track_index)
            write_entry("event-ledger.jsonl", events)
            write_entry("quality-trend.json", trend)
            write_entry("issue-taxonomy.json", taxonomy)
            write_entry("risk-register.json", risks)
            write_entry("evidence-bindings.json", bindings)
            if signoff:
                write_entry("timeline-signoff.json", signoff)
            write_entry("README.txt", _readme(report, track_index, trend, risks))
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_TIMELINE_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                    "release_id": release_id,
                    "timeline_id": timeline_id,
                    "generated_at": now_iso(),
                    "source_hash": report.get("source_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "track_index_hash": track_index.get("integrity_hash"),
                    "event_ledger_hash": _event_ledger_hash(events),
                    "quality_trend_hash": trend.get("integrity_hash"),
                    "issue_taxonomy_hash": taxonomy.get("integrity_hash"),
                    "risk_register_hash": risks.get("integrity_hash"),
                    "evidence_bindings_hash": bindings.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash") if signoff else None,
                    "summary": report.get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": report.get("status"), "timeline_id": timeline_id, "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str, timeline_id: str | None = None) -> DomainDocument:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            exported = self.export_timeline(release_id, timeline_id)
            export_dir = self.export_dir(release_id, timeline_id)
            zip_path = self.zip_path(release_id, timeline_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "timeline_id": timeline_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, timeline_id: str | None = None, **kwargs: object) -> DomainDocument:
        with self.lock:
            timeline_id = self._resolve_timeline_id(release_id, timeline_id)
            self._assert_current_or_stale_safe(release_id, timeline_id)
            if not self.zip_path(release_id, timeline_id).exists():
                self.build_zip(release_id, timeline_id)
            if kwargs.get("require_current_certification") and not kwargs.get("release_audio_certification_path"):
                kwargs["release_audio_certification_path"] = self.certification_store.zip_path(release_id)
            if kwargs.get("require_current_certification") and not kwargs.get("release_audio_certification_verification_report_path"):
                kwargs["release_audio_certification_verification_report_path"] = self.certification_store.verification_report_path(release_id)
            report = verify_release_audio_timeline_package(self.zip_path(release_id, timeline_id), **kwargs)
            write_release_audio_timeline_verification_report(report, self.verification_report_path(release_id, timeline_id))
            return report

    def gate(self, release_id: str, *, required: bool, require_signed: bool = False, require_current_certification: bool = True) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            timeline_id = self._current_timeline_id(release_id)
            if not timeline_id:
                refreshed = self.refresh_timeline(release_id)
                timeline_id = str(refreshed.get("timeline_id") or "")
            self._assert_current_or_stale_safe(release_id, timeline_id)
            report = self.read_timeline(release_id, timeline_id)
            signoff = _read_optional_json(self.signoff_path(release_id, timeline_id))
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline has blockers.", "timeline_id": timeline_id, "report": report}
            if require_signed and signoff.get("status") != "signed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline signoff is missing.", "timeline_id": timeline_id, "report": report}
            if require_current_certification:
                bindings = self.read_evidence_bindings(release_id, timeline_id)
                cert = ((bindings.get("bindings") or {}).get("release_audio_certification") or {}) if isinstance(bindings.get("bindings"), dict) else {}
                if cert.get("status") != "passed":
                    return {"status": "failed", "hard_block": True, "message": "Release Audio Timeline Certification binding is not passed.", "timeline_id": timeline_id, "report": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Timeline gate passed.", "timeline_id": timeline_id, "report": report, "summary": report.get("summary", {}), "signoff": signoff or None}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _write_documents(self, release_id: str, timeline_id: str, docs: DomainDocument) -> None:
        root = self.timeline_dir(release_id, timeline_id)
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "audio-timeline-report.json", docs["report"])
        write_json(root / "track-timeline-index.json", docs["track_index"])
        _write_jsonl(root / "event-ledger.jsonl", docs["events"])
        write_json(root / "quality-trend.json", docs["trend"])
        write_json(root / "issue-taxonomy.json", docs["taxonomy"])
        write_json(root / "risk-register.json", docs["risks"])
        write_json(root / "evidence-bindings.json", docs["bindings"])

    def _write_current(self, release_id: str, timeline_id: str, report: DomainDocument) -> None:
        current = {"schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION, "release_id": release_id, "timeline_id": timeline_id, "source_hash": report.get("source_hash"), "status": report.get("status"), "updated_at": now_iso()}
        current["integrity_hash"] = _integrity_hash(current)
        write_json(self.current_path(release_id), current)

    def _read_document_set(self, release_id: str, timeline_id: str) -> tuple[DomainDocument, list[DomainDocument], DomainDocument]:
        return (
            sanitize_metadata(read_json(self.report_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.track_index_path(release_id, timeline_id))),
            sanitize_metadata(_read_jsonl(self.event_ledger_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.trend_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.taxonomy_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.risk_path(release_id, timeline_id))),
            sanitize_metadata(read_json(self.bindings_path(release_id, timeline_id))),
        )

    def _assert_current_or_stale_safe(self, release_id: str, timeline_id: str) -> None:
        report = _read_optional_json(self.report_path(release_id, timeline_id))
        if not report:
            raise ReleaseAudioTimelineNotFoundError(f"Release Audio Timeline not found: {timeline_id}.")
        current_docs = self._with_timeline_id(self._build_documents(release_id, timeline_id=timeline_id), release_id, timeline_id)
        if current_docs["report"].get("source_hash") != report.get("source_hash") or current_docs["report"].get("status") != report.get("status"):
            raise ReleaseAudioTimelineStateError("Release Audio Timeline source is stale. Refresh timeline before using timeline evidence.")
        _report, track_index, events, trend, taxonomy, risks, bindings = self._read_document_set(release_id, timeline_id)
        if _semantic_hash(track_index) != _semantic_hash(current_docs["track_index"]) or _semantic_hash(events) != _semantic_hash(current_docs["events"]) or _semantic_hash(trend) != _semantic_hash(current_docs["trend"]) or _semantic_hash(taxonomy) != _semantic_hash(current_docs["taxonomy"]) or _semantic_hash(risks) != _semantic_hash(current_docs["risks"]) or _semantic_hash(bindings) != _semantic_hash(current_docs["bindings"]):
            raise ReleaseAudioTimelineStateError("Release Audio Timeline documents are stale. Refresh timeline before using timeline evidence.")

    def _build_documents(self, release_id: str, timeline_id: str | None) -> DomainDocument:
        release = self.release_store.get_release(release_id)
        timeline_id = timeline_id or "ratl-pending"
        certification_report = self.certification_store.read_report(release_id, default={})
        cert_zip = self.certification_store.zip_path(release_id)
        cert_verification = self._current_certification_verification(release_id)
        cert_binding = {
            "zip_sha256": _sha256_path(cert_zip),
            "zip_size_bytes": cert_zip.stat().st_size if cert_zip.exists() else None,
            "manifest_hash": cert_verification.get("manifest_hash"),
            "verification_report_hash": cert_verification.get("integrity_hash"),
            "status": cert_verification.get("status") or certification_report.get("status") or "missing",
            "report_hash": certification_report.get("integrity_hash"),
        }
        track_rows = []
        events: list[DomainDocument] = []
        blocker_risks: list[DomainDocument] = []
        link = self.planner_store.read_link(release_id, default={})
        campaign_id = str(link.get("campaign_id") or certification_report.get("campaign_id") or "")
        campaign_report = self.campaign_store.refresh_report(campaign_id) if campaign_id else {}
        case_index = _read_optional_json(self.campaign_store.case_index_path(campaign_id)) if campaign_id else {}
        remediation_gate = self.remediation_store.gate(release_id, required=False, require_signed=True)
        governance_gate = self.governance_store.gate(campaign_id, required=False) if campaign_id else {"status": "missing"}
        source_tracks = []
        previous_hash: str | None = None
        seq = 1
        for track in release.tracks:
            row = self._track_event_payload(release_id, track, campaign_report, case_index)
            track_rows.append(row["track"])
            source_tracks.append(row["source"])
            for risk in row["risks"]:
                blocker_risks.append(risk)
            event = _event(release_id, timeline_id, seq, row["track"], "track_certification_summary", row["track"].get("status", "unknown"), "info" if row["track"].get("status") == "certified" else "warning", row, previous_hash)
            previous_hash = event["event_hash"]
            events.append(event)
            seq += 1
        cert_event_payload = {"certification": cert_binding, "report_status": certification_report.get("status"), "governance_status": governance_gate.get("status"), "remediation_status": remediation_gate.get("status")}
        event = _event(release_id, timeline_id, seq, {}, "release_audio_certification_verified", str(cert_binding.get("status") or "missing"), "info" if cert_binding.get("status") == "passed" else "blocking", cert_event_payload, previous_hash)
        events.append(event)

        source = {
            "release_id": release_id,
            "track_sources_hash": stable_hash(source_tracks),
            "campaign_id": campaign_id or None,
            "campaign_report_hash": campaign_report.get("integrity_hash"),
            "case_index_hash": case_index.get("integrity_hash"),
            "governance_gate_hash": stable_hash(governance_gate),
            "remediation_gate_hash": stable_hash(remediation_gate),
            "certification_report_hash": certification_report.get("integrity_hash"),
            "certification_verification_hash": cert_verification.get("integrity_hash"),
            "certification_zip_sha256": cert_binding.get("zip_sha256"),
        }
        source["source_hash"] = stable_hash(source)
        derived = _derive_from_events(release_id, timeline_id, events, source_hash=source["source_hash"])
        track_index = derived["track_index"]
        trend = derived["trend"]
        taxonomy = derived["taxonomy"]
        risks = derived["risks"]
        for risk in blocker_risks:
            if risk not in risks["risks"]:
                risks["risks"].append(risk)
        risks["risks"] = sorted(risks["risks"], key=lambda item: str(item.get("risk_id") or ""))
        risks["summary"] = {"open_risk_count": len(risks["risks"]), "blocking_risk_count": sum(1 for row in risks["risks"] if str(row.get("severity") or "") in {"blocking", "critical"})}
        for doc in (track_index, trend, taxonomy, risks):
            doc["source_hash"] = source["source_hash"]
            doc["integrity_hash"] = _integrity_hash(doc)
        bindings = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                "release_id": release_id,
                "timeline_id": timeline_id,
                "bindings": {
                    "release_audio_certification": cert_binding,
                    "audio_campaign_governance": {"campaign_id": campaign_id or None, "status": governance_gate.get("status"), "archive_zip_sha256": governance_gate.get("archive_zip_sha256"), "verification_report_hash": governance_gate.get("archive_verification_hash")},
                    "audio_campaign_remediation": {"needed": remediation_gate.get("needed"), "status": remediation_gate.get("status"), "message": remediation_gate.get("message")},
                    "final_exports": source_tracks,
                },
                "source_hash": source["source_hash"],
            }
        )
        bindings["integrity_hash"] = _integrity_hash(bindings)
        blocking_risk_count = int(risks["summary"].get("blocking_risk_count") or 0)
        cert_ok = cert_binding.get("status") == "passed"
        status = "passed" if cert_ok and blocking_risk_count == 0 and int(track_index["summary"].get("track_count") or 0) > 0 else "failed"
        report = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_TIMELINE_SCHEMA_VERSION,
                "timeline_id": timeline_id,
                "release_id": release_id,
                "campaign_id": campaign_id or None,
                "status": status,
                "generated_at": now_iso(),
                "source": source,
                "source_hash": source["source_hash"],
                "event_ledger_hash": _event_ledger_hash(events),
                "certification": cert_binding,
                "summary": {
                    **track_index.get("summary", {}),
                    "issue_type_count": taxonomy["summary"].get("issue_type_count"),
                    "open_risk_count": risks["summary"].get("open_risk_count"),
                    "blocking_risk_count": blocking_risk_count,
                    "certification_status": cert_binding.get("status"),
                    "governance_status": governance_gate.get("status"),
                    "remediation_status": remediation_gate.get("status"),
                },
                "checks": _checks(track_index, trend, risks, cert_binding),
            }
        )
        report["integrity_hash"] = _integrity_hash(report)
        return {"report": report, "track_index": track_index, "events": events, "trend": trend, "taxonomy": taxonomy, "risks": risks, "bindings": bindings}
