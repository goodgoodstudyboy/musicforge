from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

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


class AudioFixSprintError(ValueError):
    pass


class AudioFixSprintNotFoundError(AudioFixSprintError):
    pass


class AudioFixSprintStateError(AudioFixSprintError):
    pass


class AudioFixSprintValidationError(AudioFixSprintError, ValueError):
    pass


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

    def create_sprint(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def list_sprints(self) -> list[dict[str, Any]]:
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

    def read_sprint(self, sprint_id: str) -> dict[str, Any]:
        path = self.sprint_dir(sprint_id) / "sprint.json"
        if not path.exists():
            raise AudioFixSprintNotFoundError(f"Audio Fix Sprint not found: {sprint_id}.")
        sprint = read_json(path)
        sprint = self._refresh_stale_flags(sprint)
        sprint["summary"] = _sprint_summary(sprint.get("items", []), str(sprint.get("status") or "open"))
        sprint["integrity_hash"] = _integrity_hash(sprint)
        self._write_sprint(sprint)
        return _public_sprint(sprint)

    def refresh_sprint(self, sprint_id: str) -> dict[str, Any]:
        with self.lock:
            sprint = self._read_raw_sprint(sprint_id)
            sprint = self._refresh_stale_flags(sprint)
            sprint["updated_at"] = now_iso()
            sprint["summary"] = _sprint_summary(sprint.get("items", []), str(sprint.get("status") or "open"))
            sprint["integrity_hash"] = _integrity_hash(sprint)
            self._write_sprint(sprint)
            self._write_issue_index(sprint)
            return _public_sprint(sprint)

    def create_drafts(self, sprint_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def generate_candidates(self, sprint_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def review_candidate(self, sprint_id: str, item_id: str, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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

    def select_candidate(self, sprint_id: str, item_id: str, candidate_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def create_recheck_session(self, sprint_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def review_recheck_item(self, sprint_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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

    def closeout_report(self, sprint_id: str) -> dict[str, Any]:
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

    def close_sprint(self, sprint_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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


def _collect_fix_items(sessions: list[ImplementationDocument], *, include_test_audio: bool, existing_keys: set[str]) -> list[ImplementationDocument]:
    collected: list[dict[str, Any]] = []
    categories: dict[str, int] = {}
    counter = 0
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        for item in session.get("items", []):
            if item.get("stale"):
                continue
            renderer = _as_document(item.get("renderer"))
            if renderer.get("runner_kind") == "test_fake" and not include_test_audio:
                continue
            if not item.get("artifact_hashes", {}).get("wav_sha256"):
                continue
            review = _as_document(item.get("review"))
            markers = [marker for marker in item.get("markers", []) if isinstance(marker, dict)]
            review_status = str(review.get("status") or "")
            review_markers = [marker for marker in markers if str(marker.get("severity") or "") in HIGH_SEVERITIES or str(marker.get("category") or "") in FIX_CATEGORIES]
            if review_status in {"needs_fix", "rejected"} and not review_markers:
                review_markers = [{"marker_id": "review", "severity": "high" if review_status == "rejected" else "medium", "category": "other", "message": review.get("notes") or review_status, "source_hash": review.get("source_hash")}]
            for marker in review_markers:
                key = stable_hash({"session_id": session_id, "item_id": item.get("item_id"), "marker_id": marker.get("marker_id"), "marker_source_hash": marker.get("source_hash")})
                if key in existing_keys:
                    raise AudioFixSprintStateError("Audio Lab marker is already assigned to an open Audio Fix Sprint.")
                counter += 1
                severity = str(marker.get("severity") or "medium")
                category = str(marker.get("category") or "other")
                categories[category] = categories.get(category, 0) + 1
                fix_item = {
                    "fix_item_id": f"afi-{counter:06d}",
                    "status": "open",
                    "priority": 0,
                    "category": category,
                    "severity": severity,
                    "source_key": key,
                    "source_marker": {
                        "session_id": session_id,
                        "item_id": item.get("item_id"),
                        "marker_id": marker.get("marker_id"),
                        "marker_source_hash": marker.get("source_hash"),
                        "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256"),
                    },
                    "target": {
                        "song_id": item.get("song_id"),
                        "title": item.get("title"),
                        "time_seconds": marker.get("time_seconds"),
                        "track_hint": marker.get("track_hint") or category,
                    },
                    "review_status": review_status,
                    "recommended_actions": _recommended_actions(category),
                    "artifact_relpaths": dict(item.get("artifact_relpaths") or {}),
                    "artifact_hashes": dict(item.get("artifact_hashes") or {}),
                    "renderer": renderer,
                    "drafts": {},
                    "candidates": [],
                    "selected_candidate_id": None,
                    "resolution": None,
                    "stale": False,
                    "stale_reasons": [],
                }
                fix_item["priority"] = _priority(fix_item, repeated_category=False)
                fix_item["source_hash"] = stable_hash(_fix_item_source(fix_item))
                fix_item["integrity_hash"] = _integrity_hash(fix_item)
                collected.append(fix_item)
    for item in collected:
        if categories.get(str(item.get("category") or ""), 0) > 1:
            item["priority"] = _priority(item, repeated_category=True)
    return sorted(collected, key=lambda row: (-int(row.get("priority") or 0), str(row.get("fix_item_id") or "")))


def _priority(item: ImplementationDocument, *, repeated_category: bool) -> int:
    score = {"critical": 50, "high": 35, "medium": 20, "low": 10}.get(str(item.get("severity") or ""), 10)
    score += {"rejected": 40, "needs_fix": 25}.get(str(item.get("review_status") or ""), 0)
    if repeated_category:
        score += 10
    if item.get("renderer", {}).get("runner_kind") == "test_fake":
        score -= 20
    return max(0, score)


def _recommended_actions(category: str) -> list[str]:
    if category in {"mix_balance", "mastering"}:
        return ["mix_patch", "audio_revision", "review_task"]
    if category in {"timing", "arrangement", "performance"}:
        return ["audio_revision", "review_task"]
    return ["review_task", "audio_revision", "mix_patch"]


def _session_ids_from_payload(payload: ImplementationDocument) -> list[str]:
    raw = payload.get("session_ids") or payload.get("from_sessions") or payload.get("from_session") or payload.get("session_id")
    if isinstance(raw, list):
        session_ids = [str(item).strip() for item in raw if str(item).strip()]
    else:
        session_ids = [str(raw or "").strip()]
    session_ids = [_validate_id(item, "als") for item in session_ids if item]
    if not session_ids:
        raise AudioFixSprintValidationError("from_session is required.")
    return session_ids


def _session_source_hash(session: ImplementationDocument) -> str:
    items = []
    for item in session.get("items", []):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "item_id": item.get("item_id"),
                "source_hash": item.get("source_hash"),
                "artifact_hashes": item.get("artifact_hashes"),
                "audio_status": item.get("audio_status"),
                "renderer": item.get("renderer"),
                "review": _review_core(item.get("review") or {}) if isinstance(item.get("review"), dict) else {},
                "markers": [
                    {
                        "marker_id": marker.get("marker_id"),
                        "severity": marker.get("severity"),
                        "category": marker.get("category"),
                        "source_hash": marker.get("source_hash"),
                    }
                    for marker in item.get("markers", [])
                    if isinstance(marker, dict)
                ],
            }
        )
    return stable_hash({"session_id": session.get("session_id"), "source": session.get("source"), "items": items})


def _selected_item_ids(payload: ImplementationDocument, items: list[ImplementationDocument]) -> set[str]:
    raw = payload.get("fix_item_ids") or payload.get("item_ids")
    if not raw:
        raw = [item.get("fix_item_id") for item in items]
    if not isinstance(raw, list):
        raw = [raw]
    selected = {_validate_id(str(item), "afi") for item in raw if str(item).strip()}
    if not selected:
        raise AudioFixSprintValidationError("At least one fix_item_id is required.")
    return selected


def _build_draft(sprint: ImplementationDocument, item: ImplementationDocument, draft_type: str) -> ImplementationDocument:
    prefix = {"review_task": "alfsrt", "audio_revision": "alfsar", "mix_patch": "alfsmp"}[draft_type]
    draft = {
        "schema_version": AUDIO_FIX_SCHEMA_VERSION,
        "draft_id": f"{prefix}-{item.get('fix_item_id')}",
        "draft_type": draft_type,
        "status": "draft",
        "created_at": now_iso(),
        "fix_sprint_id": sprint.get("fix_sprint_id"),
        "fix_item_id": item.get("fix_item_id"),
        "title": f"Fix {item.get('category')} {item.get('severity')}",
        "instruction": f"Address Audio Lab marker {item.get('source_marker', {}).get('marker_id')} from session {item.get('source_marker', {}).get('session_id')}.",
        "provenance": {
            "source_type": "audio_fix_sprint_item",
            "sprint_source_hash": sprint.get("source_hash"),
            "fix_item_source_hash": item.get("source_hash"),
            "marker_source_hash": item.get("source_marker", {}).get("marker_source_hash"),
            "wav_sha256": item.get("source_marker", {}).get("wav_sha256"),
        },
        "auto_apply": False,
    }
    draft["integrity_hash"] = _integrity_hash(draft)
    return draft


def _candidate_review(payload: ImplementationDocument) -> ImplementationDocument:
    if bool(payload.get("playback_confirmed")) is not True:
        raise AudioFixSprintValidationError("Candidate A/B review requires playback_confirmed=true.")
    review_mode = str(payload.get("review_mode") or "manual")
    if review_mode != "manual":
        raise AudioFixSprintValidationError("Candidate A/B review must be manual.")
    preferred = str(payload.get("preferred") or "").strip()
    if preferred not in {"left", "right", "same"}:
        raise AudioFixSprintValidationError("preferred must be left, right, or same.")
    reviewer = _as_document(payload.get("reviewer"))
    name = _bounded(reviewer.get("name") or payload.get("reviewer_name") or payload.get("reviewer"), 120)
    role = _bounded(reviewer.get("role") or payload.get("role"), 80)
    if not name or not role:
        raise AudioFixSprintValidationError("Candidate A/B review requires reviewer name and role.")
    review = {
        "status": "accepted" if preferred in {"right", "same"} else "rejected",
        "preferred": preferred,
        "rating": max(1, min(5, int(payload.get("rating") or 0))),
        "rating_delta": int(payload.get("rating_delta") or 0),
        "review_mode": "manual",
        "playback_confirmed": True,
        "reviewer": {"name": name, "role": role},
        "notes": _bounded(payload.get("notes"), 1000),
        "created_at": now_iso(),
    }
    review["source_hash"] = stable_hash(_review_core(review))
    review["integrity_hash"] = _integrity_hash(review)
    return review


def _manual_review(payload: ImplementationDocument) -> ImplementationDocument:
    result = str(payload.get("result") or payload.get("status") or "").strip()
    if result not in {"accepted", "needs_fix", "rejected"}:
        raise AudioFixSprintValidationError("result must be accepted, needs_fix, or rejected.")
    review = _candidate_review({**payload, "preferred": "right" if result == "accepted" else "left"})
    review["status"] = result
    review["source_hash"] = stable_hash(_review_core(review))
    review["integrity_hash"] = _integrity_hash(review)
    return review


def _find_item_candidate(sprint: ImplementationDocument, item_id: str, candidate_id: str) -> tuple[ImplementationDocument, ImplementationDocument]:
    item_id = _validate_id(item_id, "afi")
    candidate_id = _validate_id(candidate_id, "afc")
    item = next((row for row in sprint.get("items", []) if row.get("fix_item_id") == item_id), None)
    if not item:
        raise AudioFixSprintNotFoundError(f"Audio Fix item not found: {item_id}.")
    candidate = _candidate_by_id(item, candidate_id)
    if not candidate:
        raise AudioFixSprintNotFoundError(f"Audio Fix candidate not found: {candidate_id}.")
    return item, candidate


def _candidate_by_id(item: ImplementationDocument, candidate_id: str) -> ImplementationDocument:
    return next((row for row in item.get("candidates", []) if row.get("candidate_id") == candidate_id), {})


def _candidate_is_stale(candidate: ImplementationDocument, sprint_dir: Path) -> bool:
    artifacts = _as_document(candidate.get("artifacts"))
    hashes = _as_document(candidate.get("artifact_hashes"))
    midi_rel = artifacts.get("midi")
    wav_rel = artifacts.get("wav")
    if midi_rel and (not (sprint_dir / str(midi_rel)).exists() or _sha256_path(sprint_dir / str(midi_rel)) != hashes.get("midi_sha256")):
        return True
    if wav_rel and (not (sprint_dir / str(wav_rel)).exists() or _sha256_path(sprint_dir / str(wav_rel)) != hashes.get("wav_sha256")):
        return True
    return False


def _candidate_selected_stale(item: ImplementationDocument, sprint_dir: Path) -> bool:
    candidate_id = item.get("selected_candidate_id")
    if not candidate_id:
        return False
    candidate = _candidate_by_id(item, str(candidate_id))
    return bool(candidate and _candidate_is_stale(candidate, sprint_dir))


def _closeout_blockers(sprint: ImplementationDocument, recheck: ImplementationDocument | None, sprint_dir: Path) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if sprint.get("stale"):
        blockers.append("sprint_stale")
    items = sprint.get("items", [])
    if any(not item.get("selected_candidate_id") for item in items):
        blockers.append("unselected_fix_items")
    if any(_candidate_selected_stale(item, sprint_dir) for item in items):
        blockers.append("selected_candidate_stale")
    if not recheck:
        blockers.append("recheck_session_missing")
    else:
        summary = _recheck_summary(recheck.get("items", []), str(recheck.get("status") or "needs_review"))
        if summary.get("stale_count"):
            blockers.append("recheck_stale")
        if int(summary.get("manual_review_count") or 0) < int(summary.get("item_count") or 0):
            blockers.append("manual_recheck_missing")
        if summary.get("needs_fix_count") or summary.get("rejected_count"):
            blockers.append("recheck_not_accepted")
        if summary.get("test_fake_count"):
            blockers.append("test_fake_audio_not_release_ready")
        if int(summary.get("release_ready_audio_count") or 0) < int(summary.get("item_count") or 0):
            blockers.append("audio_recheck_not_release_ready")
    return sorted(set(blockers)), warnings


def _closeout_summary(sprint: ImplementationDocument, recheck: ImplementationDocument | None, status: str) -> ImplementationDocument:
    items = sprint.get("items", [])
    recheck_summary = _recheck_summary((recheck or {}).get("items", []), str((recheck or {}).get("status") or "missing")) if recheck else {"item_count": 0, "manual_review_count": 0, "test_fake_count": 0, "release_ready_audio_count": 0, "accepted_count": 0, "needs_fix_count": 0, "rejected_count": 0}
    return {
        "status": status,
        "fix_item_count": len(items),
        "selected_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "resolved_count": recheck_summary.get("accepted_count", 0),
        "unresolved_count": len(items) - int(recheck_summary.get("accepted_count") or 0),
        "manual_recheck_count": recheck_summary.get("manual_review_count", 0),
        "test_fake_count": recheck_summary.get("test_fake_count", 0),
        "release_ready_audio_count": recheck_summary.get("release_ready_audio_count", 0),
    }


def _recheck_status(items: list[ImplementationDocument]) -> str:
    summary = _recheck_summary(items, "needs_review")
    if summary["stale_count"]:
        return "stale"
    if summary["manual_review_count"] < summary["item_count"]:
        return "needs_review"
    if summary["rejected_count"]:
        return "failed"
    if summary["needs_fix_count"]:
        return "needs_fix"
    return "passed"


def _recheck_summary(items: list[ImplementationDocument], status: str) -> ImplementationDocument:
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    return {
        "status": status,
        "item_count": len(items),
        "manual_review_count": sum(1 for review in reviews if _as_document(review).get("review_mode") == "manual"),
        "accepted_count": sum(1 for review in reviews if _as_document(review).get("status") == "accepted"),
        "needs_fix_count": sum(1 for review in reviews if _as_document(review).get("status") == "needs_fix"),
        "rejected_count": sum(1 for review in reviews if _as_document(review).get("status") == "rejected"),
        "stale_count": sum(1 for item in items if item.get("stale")),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake" or item.get("renderer", {}).get("source_runner_kind") == "test_fake"),
        "release_ready_audio_count": sum(1 for item in items if item.get("renderer", {}).get("release_ready") is True),
    }


def _sprint_summary(items: list[ImplementationDocument], status: str) -> ImplementationDocument:
    return {
        "status": status,
        "issue_count": len(items),
        "high_or_critical_count": sum(1 for item in items if item.get("severity") in HIGH_SEVERITIES),
        "candidate_count": sum(len(item.get("candidates") or []) for item in items),
        "selected_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "resolved_count": sum(1 for item in items if item.get("status") == "resolved"),
        "needs_recheck_count": sum(1 for item in items if item.get("selected_candidate_id")),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake" or item.get("renderer", {}).get("source_runner_kind") == "test_fake"),
    }


def _sprint_warnings(items: list[ImplementationDocument]) -> list[str]:
    warnings = []
    if any(item.get("renderer", {}).get("runner_kind") == "test_fake" for item in items):
        warnings.append("test_fake_audio_not_release_ready")
    return warnings


def _issue_index_row(item: ImplementationDocument) -> ImplementationDocument:
    reasons = [str(item.get("severity") or "medium"), str(item.get("review_status") or "marker")]
    if item.get("renderer", {}).get("runner_kind") == "test_fake":
        reasons.append("test_fake_source")
    return {"fix_item_id": item.get("fix_item_id"), "priority": item.get("priority"), "category": item.get("category"), "severity": item.get("severity"), "status": item.get("status"), "reason": reasons}


def _top_category(items: list[ImplementationDocument]) -> str | None:
    counts: dict[str, int] = {}
    for item in items:
        category = str(item.get("category") or "")
        counts[category] = counts.get(category, 0) + 1
    return max(counts.items(), key=lambda row: row[1])[0] if counts else None


def _public_sprint(sprint: ImplementationDocument) -> ImplementationDocument:
    public = {key: value for key, value in sprint.items() if key != "items"}
    public["items"] = [_public_item(item) for item in sprint.get("items", [])]
    return public


def _public_item(item: ImplementationDocument) -> ImplementationDocument:
    return dict(item)


def _fix_item_source(item: ImplementationDocument) -> ImplementationDocument:
    return {"source_marker": item.get("source_marker"), "artifact_hashes": item.get("artifact_hashes"), "renderer": item.get("renderer"), "selected_candidate_id": item.get("selected_candidate_id")}


def _review_core(review: ImplementationDocument) -> ImplementationDocument:
    return {key: review.get(key) for key in ("status", "preferred", "rating", "rating_delta", "review_mode", "playback_confirmed", "reviewer")}


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_to_sprint(path: Path, sprint_dir: Path) -> str:
    return path.resolve().relative_to(sprint_dir.resolve()).as_posix()


def _bounded(value: Any, limit: int = 240) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    return text[:limit]


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(f"{prefix}-") or any(ch in text for ch in "/\\:"):
        raise AudioFixSprintValidationError(f"Invalid {prefix} id.")
    return text


def _append_event(path: Path, event: str, payload: ImplementationDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"created_at": now_iso(), "event": event, "payload": payload}
    row["event_hash"] = stable_hash(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _style_for_category(category: str) -> str:
    if category in {"mix_balance", "mastering"}:
        return "balanced instrumental pop"
    if category in {"timing", "performance"}:
        return "tight rhythmic instrumental"
    if category == "arrangement":
        return "clear structured instrumental"
    return "instrumental demo"
