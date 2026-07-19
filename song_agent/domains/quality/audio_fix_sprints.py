# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import shutil as shutil
import threading as threading
from pathlib import Path as Path
from typing import Any as Any, Callable as Callable

from song_agent.domains.quality.audio_lab import AudioLabStore as AudioLabStore
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.creation.schemas.song import SongRequest as SongRequest
from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.creation.renderers.midi import render_midi as render_midi


AUDIO_FIX_SCHEMA_VERSION = 1
AUDIO_FIX_ROOT = Path(".musicforge") / "audio-fix-sprints"
HIGH_SEVERITIES = {"high", "critical"}
FIX_CATEGORIES = {"mix_balance", "timing", "arrangement", "noise", "mastering", "performance", "other"}


from song_agent.domains.quality import v142_afs_readiness_2 as _v142_afs_readiness_2
from song_agent.domains.quality.v142_afs_readiness_2 import (
    AudioFixSprintError,
    AudioFixSprintNotFoundError,
    AudioFixSprintStateError,
    AudioFixSprintValidationError,
    _collect_fix_items,
    _priority,
    _recommended_actions,
    _session_ids_from_payload,
    _session_source_hash,
    _selected_item_ids,
    _build_draft,
    _candidate_review,
    _manual_review,
    _find_item_candidate,
    _candidate_by_id,
    _candidate_is_stale,
    _candidate_selected_stale,
    _closeout_blockers,
    _closeout_summary,
    _recheck_status,
    _recheck_summary,
    _sprint_summary,
    _sprint_warnings,
    _issue_index_row,
    _top_category,
    _public_sprint,
    _public_item,
    _fix_item_source,
    _review_core,
    _integrity_hash,
    _sha256_path,
    _rel_to_sprint,
    _bounded,
    _validate_id,
    _append_event,
    _style_for_category,
)









class AudioFixSprintStore:
    def __init__(
        self,
        root: Path | str = AUDIO_FIX_ROOT,
        *,
        audio_lab_store: AudioLabStore | None = None,
        wav_writer: Callable[[Path, Path], Path] | None = None,
    ) -> None:
        self.root = Path(root)
        self.audio_lab_store = audio_lab_store or AudioLabStore()
        self.wav_writer = wav_writer
        self.lock = threading.RLock()

    def create_sprint(self, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        session_ids = _session_ids_from_payload(payload)
        include_test_audio = bool(payload.get("include_test_audio"))
        name = _bounded(payload.get("name"), 160) or "Audio Fix Sprint"
        with self.lock:
            sessions = [self.audio_lab_store.read_session(session_id) for session_id in session_ids]
            existing_keys = self._open_source_keys()
            items = _collect_fix_items(sessions, include_test_audio=include_test_audio, existing_keys=existing_keys)
            if not items:
                raise AudioFixSprintStateError("No eligible Audio Lab needs_fix/rejected marker found for Audio Fix Sprint.")
            sprint_id = self._next_id("afs")
            now = now_iso()
            source = {
                "source_type": "audio_lab_sessions",
                "session_ids": session_ids,
                "session_source_hashes": [_session_source_hash(session) for session in sessions],
                "include_test_audio": include_test_audio,
            }
            source["source_hash"] = stable_hash(source)
            sprint = {
                "schema_version": AUDIO_FIX_SCHEMA_VERSION,
                "fix_sprint_id": sprint_id,
                "name": name,
                "status": "open",
                "created_at": now,
                "updated_at": now,
                "source": source,
                "items": items,
                "summary": _sprint_summary(items, "open"),
                "warnings": _sprint_warnings(items),
            }
            sprint["source_hash"] = stable_hash({"source": source, "items": [_fix_item_source(item) for item in items]})
            sprint["integrity_hash"] = _integrity_hash(sprint)
            self._write_sprint(sprint)
            self._write_issue_index(sprint)
            _append_event(self.sprint_dir(sprint_id) / "events.jsonl", "audio_fix_sprint_created", {"issue_count": len(items)})
            return self.read_sprint(sprint_id)

    def list_sprints(self) -> list[DomainDocument]:
        rows = []
        for path in self.root.glob("afs-*/sprint.json"):
            try:
                sprint = read_json(path)
                rows.append(
                    {
                        "fix_sprint_id": sprint.get("fix_sprint_id"),
                        "name": sprint.get("name"),
                        "status": sprint.get("status"),
                        "summary": sprint.get("summary", {}),
                        "created_at": sprint.get("created_at"),
                        "updated_at": sprint.get("updated_at"),
                    }
                )
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("fix_sprint_id") or ""))

    def read_sprint(self, sprint_id: str) -> DomainDocument:
        path = self.sprint_dir(sprint_id) / "sprint.json"
        if not path.exists():
            raise AudioFixSprintNotFoundError(f"Audio Fix Sprint not found: {sprint_id}.")
        sprint = read_json(path)
        sprint = self._refresh_stale_flags(sprint)
        sprint["summary"] = _sprint_summary(sprint.get("items", []), str(sprint.get("status") or "open"))
        sprint["integrity_hash"] = _integrity_hash(sprint)
        self._write_sprint(sprint)
        return _public_sprint(sprint)

    def refresh_sprint(self, sprint_id: str) -> DomainDocument:
        with self.lock:
            sprint = self._read_raw_sprint(sprint_id)
            sprint = self._refresh_stale_flags(sprint)
            sprint["updated_at"] = now_iso()
            sprint["summary"] = _sprint_summary(sprint.get("items", []), str(sprint.get("status") or "open"))
            sprint["integrity_hash"] = _integrity_hash(sprint)
            self._write_sprint(sprint)
            self._write_issue_index(sprint)
            return _public_sprint(sprint)

    def create_drafts(self, sprint_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        draft_type = str(payload.get("draft_type") or payload.get("type") or "review_task").strip()
        if draft_type not in {"review_task", "audio_revision", "mix_patch"}:
            raise AudioFixSprintValidationError("draft_type must be review_task, audio_revision, or mix_patch.")
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            item_ids = _selected_item_ids(payload, sprint.get("items", []))
            drafts = []
            for item in sprint.get("items", []):
                if item.get("fix_item_id") not in item_ids:
                    continue
                draft = _build_draft(sprint, item, draft_type)
                item.setdefault("drafts", {})[draft_type] = draft
                path = self.fix_item_dir(sprint_id, item["fix_item_id"]) / "drafts" / f"{draft_type}-draft.json"
                write_json(path, draft)
                drafts.append(draft)
                if item.get("status") == "open":
                    item["status"] = "drafted"
            self._touch_sprint(sprint)
            _append_event(self.sprint_dir(sprint_id) / "events.jsonl", "audio_fix_drafts_created", {"draft_type": draft_type, "count": len(drafts)})
            return {"sprint": _public_sprint(sprint), "drafts": drafts}

    def generate_candidates(self, sprint_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        mode = str(payload.get("mode") or "local").strip()
        if mode != "local":
            raise AudioFixSprintValidationError("Only local Audio Fix Sprint candidates are supported.")
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            item_ids = _selected_item_ids(payload, sprint.get("items", []))
            candidates = []
            for item in sprint.get("items", []):
                if item.get("fix_item_id") not in item_ids:
                    continue
                candidate = self._generate_candidate(sprint, item)
                item.setdefault("candidates", []).append(candidate)
                if item.get("status") in {"open", "drafted"}:
                    item["status"] = "candidate_ready"
                candidates.append(candidate)
            self._touch_sprint(sprint)
            _append_event(self.sprint_dir(sprint_id) / "events.jsonl", "audio_fix_candidates_generated", {"count": len(candidates)})
            return {"sprint": _public_sprint(sprint), "candidates": candidates}

    def review_candidate(self, sprint_id: str, item_id: str, candidate_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            item, candidate = _find_item_candidate(sprint, item_id, candidate_id)
            if _candidate_is_stale(candidate, self.sprint_dir(sprint_id)):
                raise AudioFixSprintStateError("Audio Fix candidate is stale. Regenerate before review.")
            review = _candidate_review(payload)
            comparison = {
                "comparison_id": f"afc-{candidate_id}-ab",
                "status": "passed",
                "left": candidate.get("comparison", {}).get("left", {}),
                "right": candidate.get("comparison", {}).get("right", {}),
                "review": review,
                "source_hash": stable_hash({"candidate_source_hash": candidate.get("source_hash"), "review": _review_core(review)}),
            }
            comparison["integrity_hash"] = _integrity_hash(comparison)
            candidate["comparison"] = comparison
            candidate["review"] = review
            candidate["status"] = "reviewed"
            write_json(self.candidate_dir(sprint_id, item_id, candidate_id) / "comparison.json", comparison)
            write_json(self.candidate_dir(sprint_id, item_id, candidate_id) / "review.json", review)
            self._touch_sprint(sprint)
            return {"sprint": _public_sprint(sprint), "item": _public_item(item), "candidate": candidate}

    def select_candidate(self, sprint_id: str, item_id: str, candidate_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            item, candidate = _find_item_candidate(sprint, item_id, candidate_id)
            if _candidate_is_stale(candidate, self.sprint_dir(sprint_id)):
                raise AudioFixSprintStateError("Audio Fix candidate is stale. Regenerate before select.")
            review = _as_document(candidate.get("review"))
            if review.get("review_mode") != "manual" or review.get("playback_confirmed") is not True:
                raise AudioFixSprintStateError("Candidate requires manual A/B review before select.")
            if review.get("preferred") == "left":
                raise AudioFixSprintStateError("Candidate cannot be selected when A/B review prefers the original audio.")
            candidate["status"] = "selected"
            item["selected_candidate_id"] = candidate_id
            item["status"] = "selected"
            selected = {
                "fix_item_id": item_id,
                "candidate_id": candidate_id,
                "selected_at": now_iso(),
                "selected_by": _bounded((payload or {}).get("selected_by"), 120) or "audio-fix-sprint",
                "candidate_source_hash": candidate.get("source_hash"),
                "candidate_artifact_hashes": candidate.get("artifact_hashes", {}),
                "release_ready": candidate.get("release_ready") is True,
            }
            selected["integrity_hash"] = _integrity_hash(selected)
            write_json(self.fix_item_dir(sprint_id, item_id) / "selected-candidate.json", selected)
            self._touch_sprint(sprint)
            return {"sprint": _public_sprint(sprint), "item": _public_item(item), "selected": selected}

    def create_recheck_session(self, sprint_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            selected_items = [item for item in sprint.get("items", []) if item.get("selected_candidate_id")]
            if not selected_items:
                raise AudioFixSprintStateError("At least one selected Audio Fix candidate is required before recheck.")
            session_id = f"alrs-{sprint_id}"
            now = now_iso()
            items = []
            for index, item in enumerate(selected_items, start=1):
                candidate = _candidate_by_id(item, str(item.get("selected_candidate_id")))
                re_item = {
                    "item_id": f"item-{index:03d}",
                    "song_id": item.get("target", {}).get("song_id"),
                    "title": f"Recheck {item.get('category')} {item.get('severity')}",
                    "source_fix_item_id": item.get("fix_item_id"),
                    "source_candidate_id": candidate.get("candidate_id"),
                    "artifact_relpaths": dict(candidate.get("artifacts") or {}),
                    "artifact_hashes": dict(candidate.get("artifact_hashes") or {}),
                    "audio_status": "rendered" if candidate.get("artifact_hashes", {}).get("wav_sha256") else "skipped_renderer_not_configured",
                    "renderer": dict(candidate.get("renderer") or {}),
                    "audio_health_summary": candidate.get("audio_health_summary") or {},
                    "music_health_summary": candidate.get("music_health_summary") or {},
                    "source_hash": stable_hash({"fix_item_source_hash": item.get("source_hash"), "candidate_source_hash": candidate.get("source_hash")}),
                    "review": {},
                    "markers": [],
                    "stale": False,
                    "created_at": now,
                    "updated_at": now,
                }
                items.append(re_item)
            session = {
                "schema_version": AUDIO_FIX_SCHEMA_VERSION,
                "session_id": session_id,
                "status": "needs_review",
                "created_at": now,
                "updated_at": now,
                "source": {"source_type": "audio_fix_sprint_recheck", "fix_sprint_id": sprint_id, "sprint_source_hash": sprint.get("source_hash")},
                "items": items,
            }
            session["summary"] = _recheck_summary(items, "needs_review")
            session["source_hash"] = stable_hash({"source": session["source"], "items": [_fix_item_source(item) for item in items]})
            session["integrity_hash"] = _integrity_hash(session)
            sprint["recheck"] = {"session_id": session_id, "session_source_hash": session["source_hash"], "created_at": now}
            self._touch_sprint(sprint)
            write_json(self.sprint_dir(sprint_id) / "recheck" / "listening-session-ref.json", session)
            return {"sprint": _public_sprint(sprint), "recheck_session": session}

    def review_recheck_item(self, sprint_id: str, item_id: str, payload: DomainDocument) -> DomainDocument:
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            session = _as_document(self._read_recheck_session(sprint_id))
            item = next((row for row in _as_list(session.get("items")) if isinstance(row, dict) and row.get("item_id") == item_id), None)
            if not item:
                raise AudioFixSprintNotFoundError(f"Recheck item not found: {item_id}.")
            review = _manual_review(payload)
            item["review"] = review
            item["updated_at"] = now_iso()
            session["status"] = _recheck_status(_as_document(session).get("items", []))
            session["summary"] = _recheck_summary(_as_document(session).get("items", []), session["status"])
            session["source_hash"] = stable_hash({"source": _as_document(session).get("source"), "items": [_fix_item_source(row) for row in _as_document(session).get("items", [])]})
            session["integrity_hash"] = _integrity_hash(_as_document(session))
            write_json(self.sprint_dir(sprint_id) / "recheck" / "listening-session-ref.json", session)
            _as_document(sprint.get("recheck"))["session_source_hash"] = session["source_hash"]
            self._touch_sprint(sprint)
            return {"sprint": _public_sprint(sprint), "recheck_session": session, "review": review}

    def closeout_report(self, sprint_id: str) -> DomainDocument:
        sprint = self.read_sprint(sprint_id)
        recheck = self._read_recheck_session(sprint_id, missing_ok=True)
        blockers, warnings = _closeout_blockers(sprint, recheck, self.sprint_dir(sprint_id))
        status = "passed" if not blockers else "failed"
        report = {
            "schema_version": AUDIO_FIX_SCHEMA_VERSION,
            "closeout_id": f"afco-{sprint_id}",
            "fix_sprint_id": sprint_id,
            "generated_at": now_iso(),
            "status": status,
            "summary": _closeout_summary(sprint, recheck, status),
            "blockers": blockers,
            "warnings": warnings,
            "source": {"sprint_source_hash": sprint.get("source_hash"), "recheck_source_hash": (recheck or {}).get("source_hash")},
        }
        report["source_hash"] = stable_hash(report["source"])
        report["integrity_hash"] = _integrity_hash(report)
        write_json(self.sprint_dir(sprint_id) / "closeout-report.json", report)
        return report

    def close_sprint(self, sprint_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            sprint = self._require_open_current(sprint_id)
            report = self.closeout_report(sprint_id)
            if report.get("status") != "passed":
                raise AudioFixSprintStateError("Audio Fix Sprint closeout has blockers.")
            sprint = self._read_raw_sprint(sprint_id)
            sprint["status"] = "closed"
            sprint["closed_at"] = now_iso()
            sprint["closeout"] = {"status": "closed", "closed_by": _bounded((payload or {}).get("closed_by"), 120) or "audio-fix-sprint", "closeout_hash": report.get("integrity_hash")}
            self._touch_sprint(sprint)
            _append_event(self.sprint_dir(sprint_id) / "events.jsonl", "audio_fix_sprint_closed", {"closeout_hash": report.get("integrity_hash")})
            return {"sprint": _public_sprint(sprint), "closeout": report}

    def sprint_dir(self, sprint_id: str) -> Path:
        return self.root / _validate_id(sprint_id, "afs")

    def fix_item_dir(self, sprint_id: str, item_id: str) -> Path:
        return self.sprint_dir(sprint_id) / "fix-items" / _validate_id(item_id, "afi")

    def candidate_dir(self, sprint_id: str, item_id: str, candidate_id: str) -> Path:
        return self.fix_item_dir(sprint_id, item_id) / "candidates" / _validate_id(candidate_id, "afc")

    def _next_id(self, prefix: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob(f"{prefix}-*"):
            try:
                max_seen = max(max_seen, int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"{prefix}-{max_seen + 1:06d}"

    def _read_raw_sprint(self, sprint_id: str) -> ImplementationDocument:
        path = self.sprint_dir(sprint_id) / "sprint.json"
        if not path.exists():
            raise AudioFixSprintNotFoundError(f"Audio Fix Sprint not found: {sprint_id}.")
        return read_json(path)

    def _write_sprint(self, sprint: ImplementationDocument) -> None:
        path = self.sprint_dir(str(sprint.get("fix_sprint_id"))) / "sprint.json"
        write_json(path, sprint)

    def _touch_sprint(self, sprint: ImplementationDocument) -> None:
        sprint["updated_at"] = now_iso()
        sprint["summary"] = _sprint_summary(sprint.get("items", []), str(sprint.get("status") or "open"))
        sprint["integrity_hash"] = _integrity_hash(sprint)
        self._write_sprint(sprint)
        self._write_issue_index(sprint)

    def _write_issue_index(self, sprint: ImplementationDocument) -> ImplementationDocument:
        items = sorted([_issue_index_row(item) for item in sprint.get("items", [])], key=lambda row: (-int(row.get("priority") or 0), str(row.get("fix_item_id") or "")))
        index = {
            "schema_version": AUDIO_FIX_SCHEMA_VERSION,
            "fix_sprint_id": sprint.get("fix_sprint_id"),
            "generated_at": now_iso(),
            "summary": {
                "issue_count": len(items),
                "critical_count": sum(1 for item in items if item.get("severity") == "critical"),
                "high_count": sum(1 for item in items if item.get("severity") == "high"),
                "top_category": _top_category(items),
            },
            "items": items,
        }
        index["integrity_hash"] = _integrity_hash(index)
        write_json(self.sprint_dir(str(sprint.get("fix_sprint_id"))) / "issue-index.json", index)
        return index

    def _open_source_keys(self) -> set[str]:
        keys: set[str] = set()
        for path in self.root.glob("afs-*/sprint.json"):
            try:
                sprint = read_json(path)
            except (OSError, ValueError):
                continue
            if sprint.get("status") not in {"open", "in_progress"}:
                continue
            for item in sprint.get("items", []):
                key = str(item.get("source_key") or "")
                if key:
                    keys.add(key)
        return keys

    def _refresh_stale_flags(self, sprint: ImplementationDocument) -> ImplementationDocument:
        stale = False
        reasons: list[str] = []
        current_hashes = []
        for session_id in sprint.get("source", {}).get("session_ids", []):
            try:
                current_hashes.append(_session_source_hash(self.audio_lab_store.read_session(str(session_id))))
            except Exception:
                current_hashes.append("missing")
        expected_hashes = list(sprint.get("source", {}).get("session_source_hashes") or sprint.get("source", {}).get("session_report_hashes") or [])
        if current_hashes != expected_hashes:
            stale = True
            reasons.append("source_session_changed")
        for item in sprint.get("items", []):
            item_stale = False
            item_reasons = []
            if _candidate_selected_stale(item, self.sprint_dir(str(sprint.get("fix_sprint_id")))):
                item_stale = True
                item_reasons.append("candidate_artifact_changed")
            item["stale"] = item_stale
            item["stale_reasons"] = item_reasons
            stale = stale or item_stale
            reasons.extend(item_reasons)
        sprint["stale"] = stale
        sprint["stale_reasons"] = sorted(set(reasons))
        return sprint

    def _require_open_current(self, sprint_id: str) -> ImplementationDocument:
        sprint = self._refresh_stale_flags(self._read_raw_sprint(sprint_id))
        if sprint.get("status") not in {"open", "in_progress"}:
            raise AudioFixSprintStateError("Audio Fix Sprint is not open.")
        if sprint.get("stale"):
            raise AudioFixSprintStateError("Audio Fix Sprint source is stale. Refresh before continuing.")
        return sprint

    def _generate_candidate(self, sprint: ImplementationDocument, item: ImplementationDocument) -> ImplementationDocument:
        sprint_id = str(sprint.get("fix_sprint_id"))
        item_id = str(item.get("fix_item_id"))
        next_index = len(item.get("candidates") or []) + 1
        candidate_id = f"afc-{next_index:06d}"
        candidate_dir = self.candidate_dir(sprint_id, item_id, candidate_id)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        request = SongRequest.from_dict(
            {
                "title": f"Audio Fix {item.get('category') or 'issue'}",
                "language": "instrumental",
                "style": _style_for_category(str(item.get("category") or "other")),
                "theme": f"deterministic audio fix candidate for {item.get('severity') or 'medium'} issue",
                "duration_seconds": 90,
                "vocal_mode": "instrumental",
            }
        )
        plan = SongAgent().generate(request)
        plan_path = candidate_dir / "song-plan.json"
        midi_path = candidate_dir / "song.mid"
        wav_path = candidate_dir / "song.wav"
        write_json(plan_path, plan.to_dict())
        render_midi(plan, midi_path)
        renderer = {"runner_kind": "none", "release_ready": False}
        if self.wav_writer:
            self.wav_writer(midi_path, wav_path)
            renderer = {"runner_kind": "test_fake", "profile_id": "test", "release_ready": False}
        elif item.get("artifact_relpaths", {}).get("wav"):
            source_wav = self.audio_lab_store.root / str(item.get("artifact_relpaths", {}).get("wav"))
            if source_wav.exists():
                shutil.copyfile(source_wav, wav_path)
                source_renderer = _as_document(item.get("renderer"))
                if source_renderer.get("runner_kind") == "real" and source_renderer.get("release_ready") is True:
                    renderer = {**source_renderer, "runner_kind": "real", "copied_source": True, "release_ready": True}
                else:
                    renderer = {"runner_kind": "copied_source", "source_runner_kind": source_renderer.get("runner_kind"), "release_ready": False}
        artifact_hashes = {
            "song_plan_hash": stable_hash(plan.to_dict()),
            "midi_sha256": _sha256_path(midi_path),
            "wav_sha256": _sha256_path(wav_path) if wav_path.exists() else None,
        }
        music_health = analyze_music_health(plan, case_id=candidate_id, midi_path=midi_path, wav_path=wav_path if wav_path.exists() else None)
        write_json(candidate_dir / "music-health.json", music_health)
        artifacts = {
            "song_plan": _rel_to_sprint(candidate_dir / "song-plan.json", self.sprint_dir(sprint_id)),
            "midi": _rel_to_sprint(midi_path, self.sprint_dir(sprint_id)),
            "wav": _rel_to_sprint(wav_path, self.sprint_dir(sprint_id)) if wav_path.exists() else None,
            "music_health": _rel_to_sprint(candidate_dir / "music-health.json", self.sprint_dir(sprint_id)),
        }
        comparison = {
            "left": {"label": "original", "artifact_hash": item.get("artifact_hashes", {}).get("wav_sha256"), "source": "source_audio_lab_item"},
            "right": {"label": "candidate", "artifact_hash": artifact_hashes.get("wav_sha256"), "source": "audio_fix_candidate"},
        }
        candidate = {
            "candidate_id": candidate_id,
            "fix_item_id": item_id,
            "status": "ready",
            "candidate_type": "mix_patch_candidate",
            "created_at": now_iso(),
            "source": {"fix_item_source_hash": item.get("source_hash"), "base_artifact_hash": item.get("artifact_hashes", {}).get("wav_sha256"), "patch_hash": stable_hash({"category": item.get("category"), "severity": item.get("severity")})},
            "artifacts": artifacts,
            "artifact_hashes": artifact_hashes,
            "renderer": renderer,
            "audio_health_summary": {"status": "not_analyzed" if not wav_path.exists() else "warning" if renderer.get("runner_kind") != "real" else "passed"},
            "music_health_summary": music_health.get("summary", {}),
            "comparison": comparison,
            "review": {},
            "release_ready": renderer.get("release_ready") is True,
        }
        candidate["source_hash"] = stable_hash(candidate["source"])
        candidate["integrity_hash"] = _integrity_hash(candidate)
        write_json(candidate_dir / "candidate.json", candidate)
        return candidate

    def _read_recheck_session(self, sprint_id: str, *, missing_ok: bool = False) -> ImplementationDocument | None:
        path = self.sprint_dir(sprint_id) / "recheck" / "listening-session-ref.json"
        if not path.exists():
            if missing_ok:
                return None
            raise AudioFixSprintStateError("Audio Fix Sprint recheck session is missing.")
        return read_json(path)

_v142_afs_readiness_2.bind_globals(globals())
