from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_audio_baseline_governance_verifier import (
    RELEASE_AUDIO_BASELINE_REGISTRY_PACKAGE_TYPE,
    RELEASE_AUDIO_BASELINE_SCHEMA_VERSION,
    build_baseline_source_binding,
    verify_release_audio_baseline_registry_package,
    write_release_audio_baseline_registry_verification_report,
)
from song_agent.releases import ReleaseStore, stable_hash


class ReleaseAudioBaselineGovernanceError(ValueError):
    pass


class ReleaseAudioBaselineGovernanceNotFoundError(ReleaseAudioBaselineGovernanceError):
    pass


class ReleaseAudioBaselineGovernanceStateError(ReleaseAudioBaselineGovernanceError):
    pass


class ReleaseAudioBaselineGovernanceValidationError(ReleaseAudioBaselineGovernanceError):
    pass


class ReleaseAudioBaselineGovernanceStore:
    def __init__(self, *, root: Path | None = None, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = root or Path(".musicforge") / "audio-baselines"
        self.lock = threading.RLock()

    def registry_path(self) -> Path:
        return self.root / "registry.json"

    def report_path(self) -> Path:
        return self.root / "registry-report.json"

    def active_path(self) -> Path:
        return self.root / "active-baselines.json"

    def baseline_dir(self, baseline_id: str) -> Path:
        return self.root / "baselines" / baseline_id

    def baseline_path(self, baseline_id: str) -> Path:
        return self.baseline_dir(baseline_id) / "baseline.json"

    def export_dir(self) -> Path:
        return self.root / "exports" / "baseline-registry-export"

    def zip_path(self) -> Path:
        return self.root / "exports" / "baseline-registry.zip"

    def verification_report_path(self) -> Path:
        return self.root / "exports" / "baseline-registry-verification-report.json"

    def list_baselines(self) -> list[dict[str, Any]]:
        return [self.read_baseline(path.parent.name) for path in sorted((self.root / "baselines").glob("*/baseline.json"))]

    def read_baseline(self, baseline_id: str) -> dict[str, Any]:
        path = self.baseline_path(baseline_id)
        if not path.exists():
            raise ReleaseAudioBaselineGovernanceNotFoundError(f"Release Audio Baseline not found: {baseline_id}.")
        return read_json(path)

    def read_registry(self) -> dict[str, Any]:
        self._ensure_registry()
        return read_json(self.registry_path())

    def create_from_release(self, release_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self._ensure_registry()
            baseline_id = self._next_id()
            scope = _scope_from_payload(payload)
            source_binding = build_baseline_source_binding(
                release_id=release_id,
                timeline_path=payload.get("timeline") or payload.get("timeline_zip_path"),
                timeline_report_path=payload.get("timeline_verification_report") or payload.get("timeline_verification_report_path"),
                certification_path=payload.get("certification") or payload.get("certification_zip_path"),
                certification_report_path=payload.get("certification_verification_report") or payload.get("certification_verification_report_path"),
            )
            tracks = _tracks_from_binding(source_binding)
            baseline = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION,
                    "baseline_id": baseline_id,
                    "status": "draft",
                    "scope": scope,
                    "source_release": {"release_id": release_id, "release_title": payload.get("release_title") or release_id},
                    "track_set": {
                        "track_count": len(tracks),
                        "track_identity_set_hash": stable_hash([track.get("identity_key") for track in tracks]),
                        "tracks": tracks,
                    },
                    "source_binding": source_binding,
                    "evidence": _evidence_summary(source_binding),
                    "quality_summary": _quality_summary(source_binding),
                    "approval": {},
                    "approval_history": [],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            baseline["source_hash"] = stable_hash(_strip_integrity({"scope": scope, "source_binding": source_binding, "track_set": baseline["track_set"]}))
            baseline["integrity_hash"] = _integrity_hash(baseline)
            self._write_baseline(baseline)
            self._write_registry()
            return baseline

    def approve(self, baseline_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            baseline = self.read_baseline(baseline_id)
            if baseline.get("status") in {"revoked", "superseded"}:
                raise ReleaseAudioBaselineGovernanceStateError("Revoked or superseded baseline cannot be approved.")
            approval = {
                "approved_by": _bounded(payload.get("approved_by") or payload.get("reviewer") or "", 120),
                "role": _bounded(payload.get("role") or "audio-lead", 80),
                "reason": _bounded(payload.get("reason") or "", 1000),
                "approved_at": now_iso(),
            }
            if not approval["approved_by"] or len(approval["reason"]) < 4:
                raise ReleaseAudioBaselineGovernanceValidationError("Baseline approval requires approved_by and reason.")
            baseline["approval"] = approval
            baseline["status"] = "approved"
            baseline["updated_at"] = now_iso()
            self._append_event(baseline, "baseline_approved", {"baseline_id": baseline_id, "approval_hash": stable_hash(approval), "approved_by": approval["approved_by"], "role": approval["role"]})
            self._write_baseline(baseline)
            self._write_registry()
            return baseline

    def activate(self, baseline_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            baseline = self.read_baseline(baseline_id)
            if baseline.get("status") not in {"approved", "active"}:
                raise ReleaseAudioBaselineGovernanceStateError("Only approved baselines can be activated.")
            scope_hash = stable_hash(baseline.get("scope") or {})
            for other in self.list_baselines():
                if other.get("baseline_id") == baseline_id:
                    continue
                if other.get("status") == "active" and stable_hash(other.get("scope") or {}) == scope_hash:
                    if not payload.get("supersede_existing"):
                        raise ReleaseAudioBaselineGovernanceStateError("Another active baseline exists for this scope.")
                    other["status"] = "superseded"
                    other["updated_at"] = now_iso()
                    self._append_event(other, "baseline_superseded", {"baseline_id": other.get("baseline_id"), "superseded_by": baseline_id})
                    self._write_baseline(other)
            baseline["status"] = "active"
            baseline["updated_at"] = now_iso()
            self._append_event(baseline, "baseline_activated", {"baseline_id": baseline_id, "scope_hash": scope_hash})
            self._write_baseline(baseline)
            self._write_registry()
            return baseline

    def revoke(self, baseline_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            baseline = self.read_baseline(baseline_id)
            if baseline.get("status") == "revoked":
                return baseline
            reason = _bounded(payload.get("reason") or "", 1000)
            if len(reason) < 4:
                raise ReleaseAudioBaselineGovernanceValidationError("Baseline revoke requires reason.")
            baseline["status"] = "revoked"
            baseline["updated_at"] = now_iso()
            self._append_event(baseline, "baseline_revoked", {"baseline_id": baseline_id, "reason_hash": stable_hash(reason)})
            self._write_baseline(baseline)
            self._write_registry()
            return baseline

    def preflight_release(self, release_id: str, baseline_id: str) -> dict[str, Any]:
        baseline = self.read_baseline(baseline_id)
        compatible = baseline.get("status") in {"approved", "active"}
        reasons: list[str] = []
        if not compatible:
            reasons.append("baseline_not_approved_or_active")
        if baseline.get("status") == "revoked":
            reasons.append("baseline_revoked")
        return {"status": "passed" if compatible and not reasons else "failed", "release_id": release_id, "baseline_id": baseline_id, "reasons": reasons, "baseline": baseline}

    def gate(self, release_id: str, *, baseline_id: str | None = None, required: bool = True) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            baseline = self.read_baseline(baseline_id) if baseline_id else self._active_baseline_for_release(release_id)
            preflight = self.preflight_release(release_id, str(baseline.get("baseline_id")))
            if preflight["status"] != "passed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Baseline Governance gate failed.", "preflight": preflight}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Baseline Governance gate passed.", "baseline": baseline}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def export_registry(self) -> dict[str, Any]:
        with self.lock:
            self._write_registry()
            export_dir = self.export_dir()
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            registry = self.read_registry()
            report = self._registry_report(registry)
            active = self._active_index()
            write_entry("registry.json", registry)
            write_entry("registry-report.json", report)
            write_entry("active-baselines.json", active)
            for baseline in self.list_baselines():
                write_entry(f"baselines/{baseline['baseline_id']}/baseline.json", baseline)
            write_entry("README.txt", "MusicForge Release Audio Baseline Registry\n")
            manifest = {
                "package_type": RELEASE_AUDIO_BASELINE_REGISTRY_PACKAGE_TYPE,
                "schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION,
                "generated_at": now_iso(),
                "registry_hash": registry.get("integrity_hash"),
                "report_hash": report.get("integrity_hash"),
                "active_baselines_hash": active.get("integrity_hash"),
                "files": files,
                "zip": {},
            }
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": report.get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self) -> dict[str, Any]:
        with self.lock:
            exported = self.export_registry()
            export_dir = self.export_dir()
            zip_path = self.zip_path()
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
            return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, *, strict: bool = True, require_active: bool = False, baseline_evidence: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        if not self.zip_path().exists():
            self.build_zip()
        report = verify_release_audio_baseline_registry_package(self.zip_path(), strict=strict, require_active=require_active, baseline_evidence=baseline_evidence)
        write_release_audio_baseline_registry_verification_report(report, self.verification_report_path())
        return report

    def _ensure_registry(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.registry_path().exists():
            registry = {"schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "baselines": [], "created_at": now_iso(), "updated_at": now_iso()}
            registry["integrity_hash"] = _integrity_hash(registry)
            write_json(self.registry_path(), registry)

    def _next_id(self) -> str:
        existing = [int(path.parent.name.removeprefix("rab-")) for path in (self.root / "baselines").glob("rab-*/baseline.json") if path.parent.name.removeprefix("rab-").isdigit()]
        return f"rab-{(max(existing) + 1) if existing else 1:06d}"

    def _write_baseline(self, baseline: dict[str, Any]) -> None:
        baseline["integrity_hash"] = _integrity_hash(baseline)
        path = self.baseline_path(str(baseline["baseline_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, baseline)

    def _write_registry(self) -> None:
        self._ensure_registry()
        baselines = self.list_baselines()
        registry = {"schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "baselines": [{"baseline_id": item.get("baseline_id"), "status": item.get("status"), "scope": item.get("scope"), "integrity_hash": item.get("integrity_hash")} for item in baselines], "updated_at": now_iso()}
        registry["integrity_hash"] = _integrity_hash(registry)
        write_json(self.registry_path(), registry)
        report = self._registry_report(registry)
        write_json(self.report_path(), report)
        write_json(self.active_path(), self._active_index())

    def _registry_report(self, registry: dict[str, Any]) -> dict[str, Any]:
        baselines = self.list_baselines()
        blockers = [item.get("baseline_id") for item in baselines if item.get("status") == "active" and not (item.get("approval") or {}).get("approved_by")]
        report = {"schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "status": "failed" if blockers else "passed", "registry_hash": registry.get("integrity_hash"), "summary": {"baseline_count": len(baselines), "active_count": len([item for item in baselines if item.get("status") == "active"]), "blockers": blockers}}
        report["integrity_hash"] = _integrity_hash(report)
        return report

    def _active_index(self) -> dict[str, Any]:
        baseline_hashes = {item.get("baseline_id"): item.get("integrity_hash") for item in self.list_baselines()}
        active = {"schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "active": [item.get("baseline_id") for item in self.list_baselines() if item.get("status") == "active"], "baseline_hashes": baseline_hashes}
        active["integrity_hash"] = _integrity_hash(active)
        return active

    def _append_event(self, baseline: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        history = baseline.get("approval_history") if isinstance(baseline.get("approval_history"), list) else []
        previous = history[-1].get("event_hash") if history else None
        event = sanitize_metadata({"schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "event_id": f"rabevt-{len(history) + 1:06d}", "event_type": event_type, "created_at": now_iso(), "previous_event_hash": previous, "payload": payload})
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        history.append(event)
        baseline["approval_history"] = history

    def _active_baseline_for_release(self, release_id: str) -> dict[str, Any]:
        del release_id
        active = [baseline for baseline in self.list_baselines() if baseline.get("status") == "active"]
        if not active:
            raise ReleaseAudioBaselineGovernanceNotFoundError("No active Release Audio Baseline is available.")
        if len(active) > 1:
            raise ReleaseAudioBaselineGovernanceStateError("Multiple active baselines are available; select baseline_id explicitly.")
        return active[0]


def _scope_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
    return sanitize_metadata(
        {
            "scope_type": scope.get("scope_type") or payload.get("scope_type") or "release_line",
            "release_line_id": scope.get("release_line_id") or payload.get("release_line_id") or "default",
            "project_id": scope.get("project_id") or payload.get("project_id"),
            "style_tags": scope.get("style_tags") if isinstance(scope.get("style_tags"), list) else payload.get("style_tags") if isinstance(payload.get("style_tags"), list) else [],
        }
    )


def _tracks_from_binding(binding: dict[str, Any]) -> list[dict[str, Any]]:
    facts = binding.get("facts")
    tracks = facts.get("tracks") if isinstance(facts, dict) else facts if isinstance(facts, list) else []
    output: list[dict[str, Any]] = []
    for index, track in enumerate(tracks if isinstance(tracks, list) else [], start=1):
        title = str(track.get("title") or track.get("track_id") or f"track-{index:03d}")
        output.append(
            {
                "track_id": track.get("track_id") or f"track-{index:03d}",
                "project_id": track.get("project_id"),
                "version_id": track.get("version_id"),
                "title": title,
                "normalized_title": str(track.get("normalized_title") or title.strip().lower()),
                "final_export_hash": track.get("final_export_hash"),
                "identity_key": stable_hash({"project_id": track.get("project_id"), "title": title.strip().lower()}),
            }
        )
    return output


def _evidence_summary(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "certification_zip_sha256": (binding.get("certification") or {}).get("zip_sha256"),
        "certification_manifest_hash": (binding.get("certification") or {}).get("manifest_hash"),
        "certification_verification_report_hash": (binding.get("certification") or {}).get("verification_report_hash"),
        "timeline_zip_sha256": (binding.get("timeline") or {}).get("zip_sha256"),
        "timeline_manifest_hash": (binding.get("timeline") or {}).get("manifest_hash"),
        "timeline_verification_report_hash": (binding.get("timeline") or {}).get("verification_report_hash"),
    }


def _quality_summary(binding: dict[str, Any]) -> dict[str, Any]:
    facts = binding.get("facts")
    tracks = facts.get("tracks") if isinstance(facts, dict) else facts if isinstance(facts, list) else []
    manual_reviews = sum(int(track.get("manual_review_count") or 0) for track in tracks if isinstance(track, dict))
    accepted = sum(1 for track in tracks if isinstance(track, dict) and int(track.get("accepted_review_count") or 0) > 0)
    ratings = [float(track.get("manual_rating") or 0) for track in tracks if isinstance(track, dict)]
    return {
        "manual_acceptance_rate": (accepted / len(tracks)) if tracks else 0,
        "average_manual_rating": (sum(ratings) / len(ratings)) if ratings else 0,
        "manual_review_count": manual_reviews,
        "high_issue_count": sum(int(track.get("high_issue_count") or 0) for track in tracks if isinstance(track, dict)),
        "critical_issue_count": sum(int(track.get("critical_issue_count") or 0) for track in tracks if isinstance(track, dict)),
        "regression_status": "baseline",
    }


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _file_record(path: Path, root: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _strip_integrity(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _strip_integrity(value) for key, value in payload.items() if key != "integrity_hash"}
    if isinstance(payload, list):
        return [_strip_integrity(item) for item in payload]
    return payload
