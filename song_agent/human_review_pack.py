from __future__ import annotations

import base64
import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.human_review_verifier import verify_human_review_pack
from song_agent.music_acceptance import (
    AcceptanceNotFoundError,
    AcceptanceStateError,
    AcceptanceStateError,
    AcceptanceStore,
    AcceptanceValidationError,
    listening_review_summary,
    stable_hash,
)
from song_agent.music_health import music_health_summary
from song_agent.projectio import read_json, slugify, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.review_tasks import REVIEW_TASK_SCHEMA_VERSION, ReviewTask, ReviewTaskStore


HUMAN_REVIEW_PACK_SCHEMA_VERSION = 1
HUMAN_REVIEW_IMPORT_SCHEMA_VERSION = 1
HUMAN_REVIEW_MANIFEST_SCHEMA_VERSION = 1
REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
PACK_REQUIRED_FILES = {"manifest.json", "pack.json", "index.html", "response-template.json", "checksums.json", "README.txt"}
DANGEROUS_RESPONSE_KEYS = {"source_path", "local_path", "absolute_path", "file", "path", "api_key", "token", "access_token", "authorization", "secret", "password", "raw_provider_response"}
PACK_METADATA_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


class HumanReviewPackError(ValueError):
    pass


class HumanReviewPackNotFoundError(HumanReviewPackError):
    pass


class HumanReviewPackValidationError(HumanReviewPackError):
    pass


class HumanReviewPackStateError(HumanReviewPackError):
    pass


@dataclass
class HumanReviewPack:
    schema_version: int
    pack_id: str
    suite_id: str
    status: str
    source_hash: str
    created_at: str
    updated_at: str
    case_count: int = 0
    zip_summary: dict[str, Any] = field(default_factory=dict)
    verification_summary: dict[str, Any] = field(default_factory=dict)
    latest_import_summary: dict[str, Any] = field(default_factory=dict)
    cases: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "pack_id": self.pack_id,
                "suite_id": self.suite_id,
                "status": self.status,
                "source_hash": self.source_hash,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "case_count": self.case_count,
                "zip_summary": self.zip_summary,
                "verification_summary": self.verification_summary,
                "latest_import_summary": self.latest_import_summary,
                "cases": self.cases,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanReviewPack":
        if not isinstance(data, dict):
            raise HumanReviewPackValidationError("Human review pack must be an object.")
        pack_id = validate_pack_id(str(data.get("pack_id") or "hrpack-000001"))
        suite_id = _validate_suite_id(str(data.get("suite_id") or "suite-000001"))
        cases = data.get("cases") if isinstance(data.get("cases"), list) else []
        return cls(
            schema_version=int(data.get("schema_version") or HUMAN_REVIEW_PACK_SCHEMA_VERSION),
            pack_id=pack_id,
            suite_id=suite_id,
            status=str(data.get("status") or "created"),
            source_hash=str(data.get("source_hash") or ""),
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now_iso()),
            case_count=int(data.get("case_count") or len(cases)),
            zip_summary=dict(data.get("zip_summary") or {}) if isinstance(data.get("zip_summary"), dict) else {},
            verification_summary=dict(data.get("verification_summary") or {}) if isinstance(data.get("verification_summary"), dict) else {},
            latest_import_summary=dict(data.get("latest_import_summary") or {}) if isinstance(data.get("latest_import_summary"), dict) else {},
            cases=[sanitize_metadata(item) for item in cases if isinstance(item, dict)],
        )


class HumanReviewPackStore:
    def __init__(self, acceptance_store: AcceptanceStore, *, project_store: ProjectStore | None = None) -> None:
        self.acceptance_store = acceptance_store
        self.project_store = project_store or acceptance_store.project_store

    def packs_dir(self, suite_id: str) -> Path:
        return self.acceptance_store.suite_dir(_validate_suite_id(suite_id)) / "human-review-packs"

    def pack_dir(self, suite_id: str, pack_id: str) -> Path:
        base = self.packs_dir(suite_id).resolve()
        target = (base / validate_pack_id(pack_id)).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise HumanReviewPackValidationError("Refusing to operate outside human-review-packs.") from exc
        return target

    def pack_path(self, suite_id: str, pack_id: str) -> Path:
        return self.pack_dir(suite_id, pack_id) / "pack.json"

    def manifest_path(self, suite_id: str, pack_id: str) -> Path:
        return self.pack_dir(suite_id, pack_id) / "manifest.json"

    def zip_path(self, suite_id: str, pack_id: str) -> Path:
        return self.pack_dir(suite_id, pack_id) / f"{suite_id}-{pack_id}-human-review-pack.zip"

    def imports_dir(self, suite_id: str) -> Path:
        return self.acceptance_store.suite_dir(_validate_suite_id(suite_id)) / "review-imports"

    def import_path(self, suite_id: str, import_id: str) -> Path:
        return self.imports_dir(suite_id) / validate_import_id(import_id) / "review-import.json"

    def list_packs(self, suite_id: str) -> list[dict[str, Any]]:
        self.acceptance_store.get_suite(suite_id)
        rows: list[HumanReviewPack] = []
        for path in self.packs_dir(suite_id).glob("hrpack-*/pack.json"):
            try:
                rows.append(HumanReviewPack.from_dict(read_json(path)))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return [item.to_dict() for item in sorted(rows, key=lambda row: row.updated_at, reverse=True)]

    def get_pack(self, suite_id: str, pack_id: str) -> dict[str, Any]:
        path = self.pack_path(suite_id, pack_id)
        if not path.exists():
            raise HumanReviewPackNotFoundError(pack_id)
        pack = HumanReviewPack.from_dict(read_json(path)).to_dict()
        pack["stale"] = self.current_source_hash(suite_id) != pack.get("source_hash")
        return sanitize_metadata(pack)

    def list_imports(self, suite_id: str) -> list[dict[str, Any]]:
        self.acceptance_store.get_suite(suite_id)
        rows = []
        for path in self.imports_dir(suite_id).glob("review-import-*/review-import.json"):
            try:
                value = read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                rows.append(sanitize_metadata(value))
        return sorted(rows, key=lambda row: str(row.get("imported_at") or row.get("created_at") or ""), reverse=True)

    def get_import(self, suite_id: str, import_id: str) -> dict[str, Any]:
        path = self.import_path(suite_id, import_id)
        if not path.exists():
            raise HumanReviewPackNotFoundError(import_id)
        return sanitize_metadata(read_json(path))

    def current_source_hash(self, suite_id: str) -> str:
        suite = self.acceptance_store.get_suite(suite_id)
        return stable_hash(_pack_source_state(self.acceptance_store, suite))

    def create_pack(self, suite_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        suite = self.acceptance_store.get_suite(suite_id)
        try:
            self.acceptance_store.ensure_mutable(suite)
        except AcceptanceStateError as exc:
            raise HumanReviewPackStateError(str(exc)) from exc
        cases = self.acceptance_store.list_cases(suite_id)
        if not cases:
            raise HumanReviewPackStateError("Acceptance suite has no cases to export.")
        pack_id = self._next_pack_id(suite_id)
        pack_dir = self.pack_dir(suite_id, pack_id)
        if pack_dir.exists():
            shutil.rmtree(pack_dir)
        pack_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = pack_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        now = now_iso()
        source_hash = self.current_source_hash(suite_id)
        case_rows: list[dict[str, Any]] = []
        for case in cases:
            case_dir = self.acceptance_store.case_dir(suite_id, case.case_id)
            midi_src = _safe_case_artifact(case_dir, "song.mid")
            if not midi_src.exists():
                raise HumanReviewPackStateError(f"{case.case_id} is missing song.mid.")
            slug = slugify(case.song_id or case.name or case.case_id)
            midi_rel = f"assets/{case.case_id}-{slug}.mid"
            shutil.copy2(midi_src, pack_dir / midi_rel)
            wav_rel = ""
            wav_src = _safe_case_artifact(case_dir, "song.wav")
            if wav_src.exists():
                wav_rel = f"assets/{case.case_id}-{slug}.wav"
                shutil.copy2(wav_src, pack_dir / wav_rel)
            health = self.acceptance_store.read_health(suite_id, case.case_id, default={})
            health_summary = music_health_summary(health)
            duration = case.request_summary.get("duration_seconds") if isinstance(case.request_summary, dict) else None
            case_rows.append(
                sanitize_metadata(
                    {
                        "case_id": case.case_id,
                        "song_id": case.song_id,
                        "songbook_id": case.songbook_id,
                        "songbook_version": case.songbook_version,
                        "name": case.name,
                        "title": case.request_summary.get("title") if isinstance(case.request_summary, dict) else case.name,
                        "style": case.request_summary.get("style") if isinstance(case.request_summary, dict) else None,
                        "theme": case.request_summary.get("theme") if isinstance(case.request_summary, dict) else None,
                        "duration_seconds": duration,
                        "health_summary": health_summary,
                        "midi_path": midi_rel,
                        "wav_path": wav_rel or None,
                        "audio_mode": "wav" if wav_rel else "midi",
                        "source": {"project_id": case.project_id, "version_id": case.version_id, "source_type": case.source_type},
                        "case_source_hash": stable_hash(_case_source_state(self.acceptance_store, suite_id, case.case_id)),
                    }
                )
            )
        pack = HumanReviewPack(
            schema_version=HUMAN_REVIEW_PACK_SCHEMA_VERSION,
            pack_id=pack_id,
            suite_id=suite_id,
            status="created",
            source_hash=source_hash,
            created_at=now,
            updated_at=now,
            case_count=len(case_rows),
            cases=case_rows,
        )
        write_json(pack_dir / "response-template.json", _response_template(pack.to_dict()))
        write_json(pack_dir / "checksums.json", {"schema_version": 1, "pack_id": pack_id, "files": []})
        (pack_dir / "README.txt").write_text(_readme_text(pack.to_dict()), encoding="utf-8")
        (pack_dir / "index.html").write_text(_index_html(pack.to_dict()), encoding="utf-8")
        pack = HumanReviewPack.from_dict({**pack.to_dict(), "status": "packaged", "updated_at": now_iso()})
        write_json(pack_dir / "pack.json", pack.to_dict())
        manifest = self._write_manifest(suite_id, pack_id)
        self.acceptance_store.append_event(suite_id, "human_review_pack_created", {"pack_id": pack_id, "case_count": len(case_rows)})
        return {"pack": pack.to_dict(), "manifest": manifest}

    def build_zip(self, suite_id: str, pack_id: str) -> dict[str, Any]:
        pack = HumanReviewPack.from_dict(self.get_pack(suite_id, pack_id))
        current_hash = self.current_source_hash(suite_id)
        if current_hash != pack.source_hash:
            raise HumanReviewPackStateError("Human review pack is stale. Rebuild it before ZIP export.")
        pack_dir = self.pack_dir(suite_id, pack_id)
        manifest = self._write_manifest(suite_id, pack_id)
        zip_path = self.zip_path(suite_id, pack_id)
        if zip_path.exists():
            zip_path.unlink()
        entries = [item["path"] for item in manifest.get("files", []) if isinstance(item, dict)]
        for sidecar in ("manifest.json", "checksums.json"):
            if sidecar not in entries:
                entries.append(sidecar)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for rel in entries:
                archive.write(pack_dir / rel, rel)
        zip_summary = {
            "filename": zip_path.name,
            "size_bytes": zip_path.stat().st_size,
            "sha256": _sha256_file(zip_path),
            "entry_count": len(entries),
            "entries": entries,
            "created_at": now_iso(),
        }
        pack = HumanReviewPack.from_dict({**pack.to_dict(), "status": "zipped", "zip_summary": zip_summary, "updated_at": now_iso()})
        write_json(self.pack_path(suite_id, pack_id), pack.to_dict())
        manifest = self._write_manifest(suite_id, pack_id, zip_summary=zip_summary)
        self.acceptance_store.append_event(suite_id, "human_review_pack_zipped", {"pack_id": pack_id, "entry_count": len(entries)})
        return {"pack": pack.to_dict(), "manifest": manifest, "zip": zip_summary}

    def verify_pack(self, suite_id: str, pack_id: str, *, strict: bool = False) -> dict[str, Any]:
        if not self.zip_path(suite_id, pack_id).exists():
            self.build_zip(suite_id, pack_id)
        report = verify_human_review_pack(self.zip_path(suite_id, pack_id), strict=strict)
        pack = HumanReviewPack.from_dict(self.get_pack(suite_id, pack_id))
        pack.verification_summary = _verification_summary(report)
        pack.status = "verified" if report.get("status") == "passed" else "verification_failed"
        pack.updated_at = now_iso()
        write_json(self.pack_path(suite_id, pack_id), pack.to_dict())
        self._write_manifest(suite_id, pack_id)
        return report

    def import_response(self, suite_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise HumanReviewPackValidationError("Import payload must be a JSON object.")
        if "source_path" in payload:
            raise HumanReviewPackValidationError("source_path is not allowed for human review response import.")
        suite = self.acceptance_store.get_suite(suite_id)
        try:
            self.acceptance_store.ensure_mutable(suite)
        except AcceptanceStateError as exc:
            raise HumanReviewPackStateError(str(exc)) from exc
        response = _response_from_payload(payload)
        dangerous = _dangerous_key_paths(response)
        if dangerous:
            raise HumanReviewPackValidationError("Human review response contains blocked keys: " + ", ".join(dangerous[:5]))
        pack_id = validate_pack_id(str(response.get("pack_id") or payload.get("pack_id") or ""))
        pack = HumanReviewPack.from_dict(self.get_pack(suite_id, pack_id))
        response_source_hash = str(response.get("pack_source_hash") or response.get("source_hash") or "")
        if response.get("suite_id") != suite_id:
            raise HumanReviewPackValidationError("Human review response suite_id does not match.")
        if response_source_hash != pack.source_hash:
            raise HumanReviewPackStateError("Human review response is stale for this pack.")
        if self.current_source_hash(suite_id) != pack.source_hash:
            raise HumanReviewPackStateError("Acceptance suite changed after the human review pack was built. Rebuild and re-review.")
        if self.zip_path(suite_id, pack_id).exists():
            verification = verify_human_review_pack(self.zip_path(suite_id, pack_id), strict=True)
            if verification.get("status") != "passed":
                raise HumanReviewPackStateError("Human review pack ZIP verification failed; rebuild before importing responses.")
        reviews = response.get("reviews") if isinstance(response.get("reviews"), list) else []
        if not reviews:
            raise HumanReviewPackValidationError("Human review response must contain reviews.")
        case_by_id = {case.case_id: case for case in self.acceptance_store.list_cases(suite_id)}
        pack_case_by_id = {str(item.get("case_id")): item for item in pack.cases if isinstance(item, dict)}
        for review in reviews:
            if not isinstance(review, dict):
                continue
            case_id = _validate_case_id(str(review.get("case_id") or ""))
            if case_id not in pack_case_by_id:
                raise HumanReviewPackValidationError(f"Unknown review case_id: {case_id}.")
            _ensure_review_song_id_matches_pack(case_id, review, pack_case_by_id[case_id])
        import_id = self._next_import_id(suite_id)
        imported: list[dict[str, Any]] = []
        created_review_tasks: list[dict[str, Any]] = []
        accepted_count = 0
        needs_fix_count = 0
        rejected_count = 0
        waived_count = 0
        reviewer = response.get("reviewer") if isinstance(response.get("reviewer"), dict) else {}
        listened_by = _safe_text(reviewer.get("name") or response.get("reviewer_name"), 120) or "human-reviewer"
        for review in reviews:
            if not isinstance(review, dict):
                continue
            case_id = _validate_case_id(str(review.get("case_id") or ""))
            if case_id not in case_by_id or case_id not in pack_case_by_id:
                raise HumanReviewPackValidationError(f"Unknown review case_id: {case_id}.")
            status = str(review.get("status") or "").strip()
            if status not in REVIEW_STATUSES:
                raise HumanReviewPackValidationError("Review status must be accepted, needs_fix, rejected, or waived.")
            rating = int(review.get("rating") or 0)
            playback_confirmed = bool(review.get("playback_confirmed", False))
            if not playback_confirmed:
                raise HumanReviewPackValidationError(f"{case_id} requires playback_confirmed=true.")
            _validate_markers(review, pack_case_by_id[case_id])
            safe_notes = _safe_text(review.get("notes"), 2000)
            if len(safe_notes.strip()) < 10:
                raise HumanReviewPackValidationError(f"{case_id} review notes must be at least 10 characters.")
            review_payload = {
                "status": status,
                "rating": rating,
                "playback_confirmed": playback_confirmed,
                "listened_by": listened_by,
                "listened_at": _safe_text(review.get("listened_at") or response.get("reviewed_at"), 80) or now_iso(),
                "audio_mode": _safe_text(review.get("audio_mode"), 40) or str(pack_case_by_id[case_id].get("audio_mode") or "midi"),
                "notes": safe_notes,
                "issues": [_safe_text(item, 300) for item in review.get("issues", []) if str(item).strip()] if isinstance(review.get("issues"), list) else [],
                "waivers": [_safe_text(item, 500) for item in review.get("waivers", []) if str(item).strip()] if isinstance(review.get("waivers"), list) else [],
                "review_mode": "manual",
                "source": {
                    "source_type": "human_review_pack",
                    "pack_id": pack_id,
                    "import_id": import_id,
                    "reviewer_id": _safe_text(reviewer.get("reviewer_id"), 80),
                    "organization": _safe_text(reviewer.get("organization"), 120),
                },
                "tags": [_safe_text(item, 80) for item in review.get("tags", []) if str(item).strip()] if isinstance(review.get("tags"), list) else [],
                "markers": _safe_markers(review.get("markers")),
            }
            stored = self.acceptance_store.write_review(suite_id, case_id, review_payload)
            imported.append({"case_id": case_id, "status": stored.get("status"), "rating": stored.get("rating"), "summary": listening_review_summary(stored)})
            if status == "accepted":
                accepted_count += 1
            elif status == "needs_fix":
                needs_fix_count += 1
                created_review_tasks.append(self._create_review_task_for_case(suite_id, case_id, pack_id, import_id, stored))
            elif status == "rejected":
                rejected_count += 1
                created_review_tasks.append(self._create_review_task_for_case(suite_id, case_id, pack_id, import_id, stored))
            elif status == "waived":
                waived_count += 1
        summary = {
            "import_id": import_id,
            "pack_id": pack_id,
            "suite_id": suite_id,
            "review_count": len(imported),
            "accepted_count": accepted_count,
            "needs_fix_count": needs_fix_count,
            "rejected_count": rejected_count,
            "waived_count": waived_count,
            "created_review_task_count": len(created_review_tasks),
            "report_status": "pending",
            "release_ready": False,
        }
        record = sanitize_metadata(
            {
                "schema_version": HUMAN_REVIEW_IMPORT_SCHEMA_VERSION,
                "import_id": import_id,
                "suite_id": suite_id,
                "pack_id": pack_id,
                "pack_source_hash": pack.source_hash,
                "imported_at": now_iso(),
                "reviewer": sanitize_metadata(reviewer),
                "summary": summary,
                "reviews": imported,
                "created_review_tasks": created_review_tasks,
                "report_summary": {},
            }
        )
        target = self.import_path(suite_id, import_id)
        write_json(target, record)
        pack.latest_import_summary = summary
        pack.updated_at = now_iso()
        write_json(self.pack_path(suite_id, pack_id), pack.to_dict())
        self._write_manifest(suite_id, pack_id)
        report = self.acceptance_store.build_report(suite_id)
        summary["report_status"] = str(report.get("status") or "missing")
        summary["release_ready"] = bool((report.get("summary") or {}).get("release_ready", False)) if isinstance(report.get("summary"), dict) else False
        record["summary"] = sanitize_metadata(summary)
        record["report_summary"] = sanitize_metadata(report.get("summary", {}) if isinstance(report.get("summary"), dict) else {})
        write_json(target, record)
        pack.latest_import_summary = summary
        pack.updated_at = now_iso()
        write_json(self.pack_path(suite_id, pack_id), pack.to_dict())
        self._write_manifest(suite_id, pack_id)
        self.acceptance_store.append_event(suite_id, "human_review_response_imported", {"pack_id": pack_id, "import_id": import_id, **summary})
        return record

    def _write_manifest(self, suite_id: str, pack_id: str, *, zip_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        pack_dir = self.pack_dir(suite_id, pack_id)
        files = []
        for path in sorted(pack_dir.rglob("*")):
            if not path.is_file() or path.name.endswith(".zip") or path.name in {"manifest.json", "checksums.json"}:
                continue
            rel = path.relative_to(pack_dir).as_posix()
            if not _is_safe_relpath(rel):
                raise HumanReviewPackValidationError(f"Unsafe pack file path: {rel}")
            files.append({"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
        checksums = {"schema_version": 1, "pack_id": pack_id, "files": files}
        write_json(pack_dir / "checksums.json", checksums)
        files = []
        for path in sorted(pack_dir.rglob("*")):
            if not path.is_file() or path.name.endswith(".zip") or path.name in {"manifest.json", "checksums.json"}:
                continue
            rel = path.relative_to(pack_dir).as_posix()
            files.append({"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
        pack = HumanReviewPack.from_dict(read_json(pack_dir / "pack.json"))
        manifest = sanitize_metadata(
            {
                "schema_version": HUMAN_REVIEW_MANIFEST_SCHEMA_VERSION,
                "suite_id": suite_id,
                "pack_id": pack_id,
                "source_hash": pack.source_hash,
                "created_at": pack.created_at,
                "updated_at": now_iso(),
                "case_count": pack.case_count,
                "cases": [
                    {
                        "case_id": item.get("case_id"),
                        "song_id": item.get("song_id"),
                        "midi_path": item.get("midi_path"),
                        "wav_path": item.get("wav_path"),
                        "case_source_hash": item.get("case_source_hash"),
                    }
                    for item in pack.cases
                    if isinstance(item, dict)
                ],
                "files": files,
                "zip": zip_summary or pack.zip_summary or {},
            },
            blocked_keys=PACK_METADATA_BLOCKED_KEYS,
        )
        write_json(pack_dir / "manifest.json", manifest)
        return manifest

    def _next_pack_id(self, suite_id: str) -> str:
        root = self.packs_dir(suite_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            pack_id = f"hrpack-{index:06d}"
            if not (root / pack_id).exists():
                return pack_id
        raise HumanReviewPackValidationError("Unable to allocate human review pack id.")

    def _next_import_id(self, suite_id: str) -> str:
        root = self.imports_dir(suite_id)
        root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            import_id = f"review-import-{index:06d}"
            target = root / import_id
            if not target.exists():
                target.mkdir(parents=True, exist_ok=False)
                return import_id
        raise HumanReviewPackValidationError("Unable to allocate human review import id.")

    def _create_review_task_for_case(self, suite_id: str, case_id: str, pack_id: str, import_id: str, review: dict[str, Any]) -> dict[str, Any]:
        case = self.acceptance_store.get_case(suite_id, case_id)
        title = _safe_text(f"Human review follow-up: {case.name}", 160)
        summary = _safe_text(review.get("notes"), 800)
        if not case.project_id:
            return {"case_id": case_id, "status": "not_created_no_project", "title": title, "summary": summary}
        try:
            project_dir = self.project_store.project_dir(case.project_id)
            self.project_store.ensure_project_dir_is_safe(project_dir)
            self.project_store.get_project(case.project_id)
            task_store = ReviewTaskStore(project_dir)
            with task_store.lock:
                task_id, task_dir = task_store._reserve_task_dir()
                now = now_iso()
                task = ReviewTask.from_dict(
                    {
                        "schema_version": REVIEW_TASK_SCHEMA_VERSION,
                        "task_id": task_id,
                        "project_id": case.project_id,
                        "parent_version_id": case.version_id or "",
                        "preview_id": f"human-review-{pack_id}",
                        "audition_id": f"acceptance-{case_id}",
                        "status": "open",
                        "priority": 82 if review.get("status") == "rejected" else 70,
                        "title": title,
                        "summary": summary,
                        "source": {"source_type": "human_review_pack", "suite_id": suite_id, "case_id": case_id, "pack_id": pack_id, "import_id": import_id},
                        "review_snapshot": {
                            "status": review.get("status"),
                            "rating": review.get("rating"),
                            "notes": review.get("notes"),
                            "markers": review.get("markers") if isinstance(review.get("markers"), list) else [],
                        },
                        "target": {"scope": "project_version", "version_id": case.version_id, "case_id": case_id},
                        "hashes": {"case_source_hash": stable_hash(_case_source_state(self.acceptance_store, suite_id, case_id))},
                        "counts": {"candidate_count": 0, "ready_candidate_count": 0, "failed_candidate_count": 0},
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                write_json(task_dir / "task.json", task.to_dict())
                _append_task_event(task_dir, "review_task_created_from_human_review", {"suite_id": suite_id, "case_id": case_id, "pack_id": pack_id, "import_id": import_id}, now)
            return {"case_id": case_id, "status": "created", "project_id": case.project_id, "task_id": task.task_id, "title": task.title}
        except Exception as exc:
            return {"case_id": case_id, "status": "creation_failed", "error": sanitize_sensitive_text(str(exc))[:300], "title": title}


def human_review_evidence_summary(store: AcceptanceStore, suite_id: str) -> dict[str, Any]:
    helper = HumanReviewPackStore(store)
    try:
        packs = helper.list_packs(suite_id)
        imports = helper.list_imports(suite_id)
    except (AcceptanceNotFoundError, HumanReviewPackError, OSError, ValueError):
        return {"status": "missing", "pack_count": 0, "import_count": 0}
    latest_pack = packs[0] if packs else {}
    latest_import = imports[0] if imports else {}
    summary = latest_import.get("summary") if isinstance(latest_import.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": "imported" if latest_import else "packaged" if latest_pack else "missing",
            "pack_count": len(packs),
            "import_count": len(imports),
            "latest_pack_id": latest_pack.get("pack_id"),
            "latest_pack_status": latest_pack.get("status"),
            "latest_import_id": latest_import.get("import_id"),
            "accepted_count": summary.get("accepted_count", 0),
            "needs_fix_count": summary.get("needs_fix_count", 0),
            "rejected_count": summary.get("rejected_count", 0),
            "created_review_task_count": summary.get("created_review_task_count", 0),
        }
    )


def _verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "suite_id": summary.get("suite_id"),
            "pack_id": summary.get("pack_id"),
            "case_count": summary.get("case_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "verified_at": report.get("generated_at"),
        }
    )


def validate_pack_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("hrpack-") or not text.removeprefix("hrpack-").isdigit():
        raise HumanReviewPackValidationError("Invalid human review pack id.")
    return text


def validate_import_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("review-import-") or not text.removeprefix("review-import-").isdigit():
        raise HumanReviewPackValidationError("Invalid human review import id.")
    return text


def _pack_source_state(store: AcceptanceStore, suite: Any) -> dict[str, Any]:
    cases = [
        _case_source_state(store, suite.suite_id, case.case_id)
        for case in sorted(store.list_cases(suite.suite_id), key=lambda item: item.case_id)
    ]
    return sanitize_metadata(
        {
            "suite_id": suite.suite_id,
            "name": suite.name,
            "mode": suite.mode,
            "profile_id": suite.profile_id,
            "songbook_id": suite.songbook_id,
            "songbook_version": suite.songbook_version,
            "min_rating": suite.min_rating,
            "require_audio_if_renderer_configured": suite.require_audio_if_renderer_configured,
            "require_manual_review": suite.require_manual_review,
            "allow_synthetic_review": suite.allow_synthetic_review,
            "release_ready_profile": suite.release_ready_profile,
            "cases": cases,
        }
    )


def _case_source_state(store: AcceptanceStore, suite_id: str, case_id: str) -> dict[str, Any]:
    case = store.get_case(suite_id, case_id)
    case_dir = store.case_dir(suite_id, case_id)
    return sanitize_metadata(
        {
            "case": {
                "case_id": case.case_id,
                "suite_id": case.suite_id,
                "name": case.name,
                "source_type": case.source_type,
                "song_id": case.song_id,
                "songbook_id": case.songbook_id,
                "songbook_version": case.songbook_version,
                "expectations": case.expectations,
                "request_summary": case.request_summary,
                "job_id": case.job_id,
                "project_id": case.project_id,
                "version_id": case.version_id,
                "artifacts": case.artifacts,
                "health_summary": case.health_summary,
                "created_at": case.created_at,
            },
            "health": store.read_health(suite_id, case_id, default={}),
            "midi_sha256": _sha256_file(case_dir / "song.mid") if (case_dir / "song.mid").exists() else "",
            "wav_sha256": _sha256_file(case_dir / "song.wav") if (case_dir / "song.wav").exists() else "",
        }
    )


def _ensure_review_song_id_matches_pack(case_id: str, review: dict[str, Any], pack_case: dict[str, Any]) -> None:
    if "song_id" not in review:
        return
    review_song_id = "" if review.get("song_id") is None else str(review.get("song_id"))
    pack_song_id = "" if pack_case.get("song_id") is None else str(pack_case.get("song_id"))
    if review_song_id != pack_song_id:
        raise HumanReviewPackValidationError(f"{case_id} song_id does not match human review pack.")


def _response_template(pack: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "schema_version": 1,
            "suite_id": pack.get("suite_id"),
            "pack_id": pack.get("pack_id"),
            "pack_source_hash": pack.get("source_hash"),
            "reviewer": {"name": "", "organization": ""},
            "reviewed_at": "",
            "reviews": [
                {
                    "case_id": item.get("case_id"),
                    "song_id": item.get("song_id"),
                    "status": "",
                    "rating": 0,
                    "playback_confirmed": False,
                    "audio_mode": item.get("audio_mode") or "midi",
                    "notes": "",
                    "issues": [],
                    "tags": [],
                    "markers": [],
                }
                for item in pack.get("cases", [])
                if isinstance(item, dict)
            ],
        }
    )


def _index_html(pack: dict[str, Any]) -> str:
    pack_json = json.dumps(pack, ensure_ascii=False)
    template_json = json.dumps(_response_template(pack), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MusicForge Human Review Pack</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1f2933; background: #f8fafc; }}
main {{ max-width: 1100px; margin: 0 auto; }}
section {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; margin: 12px 0; }}
label {{ display: block; font-size: 13px; font-weight: 600; margin: 10px 0 4px; }}
input, select, textarea {{ width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #bcccdc; border-radius: 6px; }}
textarea {{ min-height: 90px; }}
button {{ padding: 8px 12px; border: 1px solid #52606d; border-radius: 6px; background: #243b53; color: white; cursor: pointer; }}
audio {{ width: 100%; margin-top: 8px; }}
.meta {{ color: #52606d; font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }}
</style>
</head>
<body>
<main>
<h1>MusicForge Human Review Pack</h1>
<p class="meta">Suite {pack.get('suite_id')} / Pack {pack.get('pack_id')}</p>
<section>
<div class="grid">
<label>Reviewer name<input id="reviewerName" autocomplete="name"></label>
<label>Organization<input id="reviewerOrg"></label>
</div>
<button type="button" onclick="downloadResponse()">Download review response JSON</button>
</section>
<div id="cases"></div>
</main>
<script>
const PACK = {pack_json};
const TEMPLATE = {template_json};
const reviews = new Map(TEMPLATE.reviews.map(row => [row.case_id, row]));
function renderCases() {{
  const root = document.getElementById('cases');
  root.innerHTML = '';
  PACK.cases.forEach(item => {{
    const row = document.createElement('section');
    row.innerHTML = `
      <h2>${{item.name || item.case_id}}</h2>
      <p class="meta">${{item.song_id || ''}} ${{item.style || ''}}</p>
      <audio controls src="${{item.wav_path || item.midi_path}}"></audio>
      <label>Status<select data-field="status" data-case="${{item.case_id}}">
        <option value="">Select</option><option value="accepted">Accepted</option><option value="needs_fix">Needs fix</option><option value="rejected">Rejected</option><option value="waived">Waived</option>
      </select></label>
      <label>Rating<input data-field="rating" data-case="${{item.case_id}}" type="number" min="1" max="5" value="0"></label>
      <label><input data-field="playback_confirmed" data-case="${{item.case_id}}" type="checkbox" style="width:auto"> Playback confirmed</label>
      <label>Notes<textarea data-field="notes" data-case="${{item.case_id}}"></textarea></label>
      <label>Issues, comma separated<input data-field="issues" data-case="${{item.case_id}}"></label>
    `;
    root.appendChild(row);
  }});
}}
document.addEventListener('input', event => {{
  const target = event.target;
  const caseId = target.getAttribute('data-case');
  const field = target.getAttribute('data-field');
  if (!caseId || !field) return;
  const row = reviews.get(caseId);
  if (field === 'rating') row[field] = Number(target.value || 0);
  else if (field === 'playback_confirmed') row[field] = Boolean(target.checked);
  else if (field === 'issues') row[field] = String(target.value || '').split(',').map(x => x.trim()).filter(Boolean);
  else row[field] = target.value;
}});
function downloadResponse() {{
  const response = {{
    schema_version: 1,
    suite_id: PACK.suite_id,
    pack_id: PACK.pack_id,
    pack_source_hash: PACK.source_hash,
    reviewer: {{ name: document.getElementById('reviewerName').value, organization: document.getElementById('reviewerOrg').value }},
    reviewed_at: new Date().toISOString(),
    reviews: Array.from(reviews.values())
  }};
  const blob = new Blob([JSON.stringify(response, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `${{PACK.suite_id}}-${{PACK.pack_id}}-review-response.json`; link.click();
  URL.revokeObjectURL(url);
}}
renderCases();
</script>
</body>
</html>
"""


def _readme_text(pack: dict[str, Any]) -> str:
    return (
        "MusicForge Human Review Pack\n\n"
        f"Suite: {pack.get('suite_id')}\n"
        f"Pack: {pack.get('pack_id')}\n"
        f"Cases: {pack.get('case_count')}\n\n"
        "Open index.html in a browser, listen to every case, then export the review response JSON.\n"
        "Do not edit manifest.json or pack.json by hand.\n"
    )


def _response_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("response"), dict):
        return dict(payload["response"])
    if isinstance(payload.get("response_json"), dict):
        return dict(payload["response_json"])
    if isinstance(payload.get("response_base64"), str):
        try:
            raw = base64.b64decode(str(payload["response_base64"]), validate=True)
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HumanReviewPackValidationError(f"response_base64 is not valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise HumanReviewPackValidationError("response_base64 must decode to a JSON object.")
        return value
    return dict(payload)


def _validate_markers(review: dict[str, Any], pack_case: dict[str, Any]) -> None:
    markers = review.get("markers")
    if markers is None:
        return
    if not isinstance(markers, list):
        raise HumanReviewPackValidationError("markers must be a list.")
    duration_seconds = int(pack_case.get("duration_seconds") or 90)
    max_beat = max(4, duration_seconds * 4)
    for index, marker in enumerate(markers[:100]):
        if not isinstance(marker, dict):
            raise HumanReviewPackValidationError(f"markers[{index}] must be an object.")
        beat = marker.get("beat")
        if beat is not None:
            try:
                beat_value = float(beat)
            except (TypeError, ValueError) as exc:
                raise HumanReviewPackValidationError(f"markers[{index}].beat must be numeric.") from exc
            if beat_value < 0 or beat_value > max_beat:
                raise HumanReviewPackValidationError(f"markers[{index}].beat is outside the case duration.")


def _safe_markers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for marker in value[:100]:
        if not isinstance(marker, dict):
            continue
        rows.append(
            sanitize_metadata(
                {
                    "beat": marker.get("beat"),
                    "time_seconds": marker.get("time_seconds"),
                    "severity": _safe_text(marker.get("severity"), 40) or "note",
                    "label": _safe_text(marker.get("label"), 120),
                    "note": _safe_text(marker.get("note"), 500),
                }
            )
        )
    return rows


def _dangerous_key_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in DANGEROUS_RESPONSE_KEYS:
                paths.append(child)
            paths.extend(_dangerous_key_paths(item, prefix=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_dangerous_key_paths(item, prefix=f"{prefix}[{index}]"))
    return paths


def _safe_case_artifact(case_dir: Path, filename: str) -> Path:
    if filename not in {"song.mid", "song.wav"}:
        raise HumanReviewPackValidationError("Unsupported case artifact.")
    base = case_dir.resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HumanReviewPackValidationError("Refusing to operate outside acceptance case directory.") from exc
    if target.is_symlink():
        raise HumanReviewPackValidationError("Refusing to package symlink case artifact.")
    return target


def _is_safe_relpath(value: str) -> bool:
    raw = str(value or "")
    if "\\" in raw or not raw or raw.endswith("/") or raw.startswith("/") or raw.startswith("//"):
        return False
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_task_event(task_dir: Path, event_type: str, payload: dict[str, Any], now: str) -> None:
    path = task_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}), ensure_ascii=False) + "\n")


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]


def _validate_suite_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("suite-") or not text.removeprefix("suite-").isdigit():
        raise HumanReviewPackValidationError("Invalid suite_id.")
    return text


def _validate_case_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("case-") or not text.removeprefix("case-").isdigit():
        raise HumanReviewPackValidationError("Invalid case_id.")
    return text
