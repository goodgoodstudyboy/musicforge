from __future__ import annotations

import json
import re
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.release_audio_quality_observatory_verifier import (
    RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE,
    verify_release_audio_quality_observatory_package,
    write_release_audio_quality_observatory_verification_report,
)
from song_agent.releases import ReleaseStore, stable_hash


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE = "release_audio_quality_action_queue"
RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION = 1


class ReleaseAudioQualityActionQueueError(ValueError):
    pass


class ReleaseAudioQualityActionQueueNotFoundError(ReleaseAudioQualityActionQueueError):
    pass


class ReleaseAudioQualityActionQueueStateError(ReleaseAudioQualityActionQueueError):
    pass


class ReleaseAudioQualityActionQueueValidationError(ReleaseAudioQualityActionQueueError):
    pass


class ReleaseAudioQualityActionQueueStore:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        release_store: ReleaseStore | None = None,
        observatory_store: ReleaseAudioQualityObservatoryStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else Path(".musicforge") / "audio-quality-actions"
        self.root = self.root.resolve()
        self.observatory_store = observatory_store or ReleaseAudioQualityObservatoryStore(release_store=self.release_store)
        self.lock = threading.RLock()

    def queues_dir(self) -> Path:
        return self.root / "queues"

    def queue_dir(self, queue_id: str) -> Path:
        return self.queues_dir() / _validate_queue_id(queue_id)

    def queue_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-queue.json"

    def source_binding_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "source-binding.json"

    def action_items_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-items.json"

    def action_results_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-results.json"

    def manual_actions_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "manual-actions.json"

    def summary_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "queue-summary.json"

    def history_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "queue-history.jsonl"

    def export_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "export"

    def zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "release-audio-quality-action-queue.zip"

    def verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "verification-report.json"

    def list_queues(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for queue_path in sorted(self.queues_dir().glob("*/action-queue.json")):
            try:
                queue = read_json(queue_path)
                queue_id = str(queue.get("queue_id") or queue_path.parent.name)
                summary = read_json(self.summary_path(queue_id)) if self.summary_path(queue_id).exists() else {}
            except Exception:
                continue
            rows.append({"queue": queue, "summary": summary})
        return rows

    def create_from_observatory(
        self,
        observatory_id: str,
        *,
        name: str | None = None,
        include_risks: bool = True,
        include_recommendations: bool = True,
        severity_floor: str = "warning",
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            observatory_id = _validate_observatory_id(observatory_id)
            queue_id = self._next_queue_id()
            queue_root = self.queue_dir(queue_id)
            if queue_root.exists():
                raise ReleaseAudioQualityActionQueueValidationError(f"Audio Quality Action Queue already exists: {queue_id}.")
            binding = self._build_source_binding(observatory_id)
            docs = self._build_queue_documents(
                queue_id,
                name=name,
                binding=binding,
                include_risks=include_risks,
                include_recommendations=include_recommendations,
                severity_floor=severity_floor,
                policy=policy or {},
            )
            queue_root.mkdir(parents=True, exist_ok=True)
            self._write_documents(queue_id, docs)
            self._append_history_event(queue_id, "queue_created", {"source_hash": binding.get("source_hash"), "item_count": docs["summary"].get("summary", {}).get("item_count")})
            return docs["queue"]

    def read_queue(self, queue_id: str) -> dict[str, Any]:
        path = self.queue_path(queue_id)
        if not path.exists():
            raise ReleaseAudioQualityActionQueueNotFoundError(f"Audio Quality Action Queue not found: {queue_id}.")
        return read_json(path)

    def read_summary(self, queue_id: str) -> dict[str, Any]:
        path = self.summary_path(queue_id)
        if not path.exists():
            raise ReleaseAudioQualityActionQueueNotFoundError(f"Audio Quality Action Queue summary not found: {queue_id}.")
        return read_json(path)

    def refresh_status(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._read_documents(queue_id)
            stale = self._stale_reasons(docs["source_binding"])
            queue = dict(docs["queue"])
            preliminary = _build_summary(queue, docs["source_binding"], docs["items"], docs["results"], docs["manual_actions"], stale_reasons=stale)
            queue["status"] = preliminary.get("status")
            queue["summary"] = preliminary.get("summary", {})
            queue["updated_at"] = now_iso()
            queue["integrity_hash"] = _integrity_hash(queue)
            summary = _build_summary(queue, docs["source_binding"], docs["items"], docs["results"], docs["manual_actions"], stale_reasons=stale)
            write_json(self.queue_path(queue_id), queue)
            write_json(self.summary_path(queue_id), summary)
            return summary

    def run_safe(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._read_documents(queue_id)
            stale = self._stale_reasons(docs["source_binding"])
            if stale:
                raise ReleaseAudioQualityActionQueueStateError("Audio Quality Action Queue source is stale. Refresh Observatory and create a new queue.")
            items = docs["items"].get("items") if isinstance(docs["items"].get("items"), list) else []
            existing_results = {str(row.get("item_id")): row for row in docs["results"].get("results", []) if isinstance(row, dict)}
            result_rows: list[dict[str, Any]] = []
            manual_rows: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("item_id") or "")
                if item_id in existing_results and existing_results[item_id].get("status") in {"completed", "blocked", "failed", "manual_required"}:
                    result_rows.append(existing_results[item_id])
                    if existing_results[item_id].get("status") == "manual_required":
                        manual_rows.append(_manual_action_from_item(item, len(manual_rows) + 1))
                    continue
                outcome = _execute_item(item)
                result_rows.append(outcome)
                if outcome.get("status") == "manual_required":
                    manual_rows.append(_manual_action_from_item(item, len(manual_rows) + 1))
            source_hash = docs["source_binding"].get("source_hash")
            results = {"schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "queue_id": queue_id, "source_hash": source_hash, "results": result_rows, "updated_at": now_iso()}
            results["integrity_hash"] = _integrity_hash(results)
            manual_actions = {"schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "queue_id": queue_id, "source_hash": source_hash, "manual_actions": manual_rows, "updated_at": now_iso()}
            manual_actions["integrity_hash"] = _integrity_hash(manual_actions)
            queue = dict(docs["queue"])
            preliminary = _build_summary(queue, docs["source_binding"], docs["items"], results, manual_actions, stale_reasons=[])
            queue["status"] = preliminary.get("status")
            queue["summary"] = preliminary.get("summary", {})
            queue["updated_at"] = now_iso()
            queue["integrity_hash"] = _integrity_hash(queue)
            summary = _build_summary(queue, docs["source_binding"], docs["items"], results, manual_actions, stale_reasons=[])
            write_json(self.queue_path(queue_id), queue)
            write_json(self.action_results_path(queue_id), results)
            write_json(self.manual_actions_path(queue_id), manual_actions)
            write_json(self.summary_path(queue_id), summary)
            self._append_history_event(queue_id, "queue_run_safe_completed", {"status": summary.get("status"), "summary_hash": summary.get("integrity_hash")})
            return {"status": summary.get("status"), "queue_id": queue_id, "summary": summary.get("summary", {}), "results": results, "manual_actions": manual_actions}

    def export_package(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._current_docs_for_export(queue_id)
            export_dir = self.export_dir(queue_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | list[dict[str, Any]] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                elif rel.endswith(".jsonl"):
                    rows = payload if isinstance(payload, list) else []
                    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in rows) + ("\n" if rows else ""), encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("action-queue.json", docs["queue"])
            write_entry("source-binding.json", docs["source_binding"])
            write_entry("action-items.json", docs["items"])
            write_entry("action-results.json", docs["results"])
            write_entry("manual-actions.json", docs["manual_actions"])
            write_entry("queue-summary.json", docs["summary"])
            if self.history_path(queue_id).exists():
                write_entry("queue-history.jsonl", _read_jsonl(self.history_path(queue_id)))
            write_entry("README.txt", _readme(docs["queue"], docs["summary"]))
            manifest = sanitize_metadata(
                {
                    "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE,
                    "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                    "queue_id": queue_id,
                    "generated_at": now_iso(),
                    "source_hash": docs["summary"].get("source_hash"),
                    "source_binding_hash": docs["source_binding"].get("integrity_hash"),
                    "action_queue_hash": docs["queue"].get("integrity_hash"),
                    "action_items_hash": docs["items"].get("integrity_hash"),
                    "action_results_hash": docs["results"].get("integrity_hash"),
                    "manual_actions_hash": docs["manual_actions"].get("integrity_hash"),
                    "summary_hash": docs["summary"].get("integrity_hash"),
                    "files": sorted(files, key=lambda row: row["path"]),
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["summary"].get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, queue_id: str) -> dict[str, Any]:
        with self.lock:
            exported = self.export_package(queue_id)
            export_dir = self.export_dir(queue_id)
            zip_path = self.zip_path(queue_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, queue_id: str, **kwargs: Any) -> dict[str, Any]:
        from song_agent.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package, write_release_audio_quality_action_queue_verification_report

        with self.lock:
            if not self.zip_path(queue_id).exists():
                self.build_zip(queue_id)
            if not kwargs.get("observatory_zip_path"):
                kwargs["observatory_zip_path"] = self._observatory_zip_from_queue(queue_id)
            if not kwargs.get("observatory_verification_report_path"):
                kwargs["observatory_verification_report_path"] = self._observatory_verification_from_queue(queue_id)
            if not kwargs.get("evidence_root"):
                kwargs["evidence_root"] = self.release_store.root
            report = verify_release_audio_quality_action_queue_package(self.zip_path(queue_id), **kwargs)
            write_release_audio_quality_action_queue_verification_report(report, self.verification_report_path(queue_id))
            return report

    def gate(self, release_id: str, *, queue_id: str | None = None, required: bool, require_no_blocking: bool = True) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            queue_id = queue_id or self._latest_queue_id()
            if not queue_id:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue is missing."}
            report = self.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=require_no_blocking)
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            release_ids = {str(item) for item in summary.get("release_ids", []) if str(item)}
            if release_id not in release_ids:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue does not cover this Release.", "verification": report}
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue verification failed.", "verification": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Quality Action Queue gate passed.", "verification": report, "summary": summary}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _build_source_binding(self, observatory_id: str) -> dict[str, Any]:
        self.observatory_store.release_store = self.release_store
        if not self.observatory_store.zip_path(observatory_id).exists():
            self.observatory_store.build_zip(observatory_id)
        verification = self.observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True, require_no_critical_risk=False)
        if verification.get("status") == "failed":
            raise ReleaseAudioQualityActionQueueStateError("Audio Quality Observatory verification failed.")
        config = self.observatory_store.read_config(observatory_id)
        summary = self.observatory_store.read_summary(observatory_id)
        risk_register = read_json(self.observatory_store.risk_register_path(observatory_id))
        recommendation_report = read_json(self.observatory_store.recommendation_report_path(observatory_id))
        source_hash = stable_hash(
            {
                "observatory_id": observatory_id,
                "observatory_zip_sha256": _sha256_path(self.observatory_store.zip_path(observatory_id)),
                "observatory_zip_size_bytes": self.observatory_store.zip_path(observatory_id).stat().st_size,
                "observatory_manifest_hash": verification.get("manifest_hash"),
                "observatory_source_hash": summary.get("source_hash"),
                "risk_register_hash": risk_register.get("integrity_hash"),
                "recommendation_report_hash": recommendation_report.get("integrity_hash"),
            }
        )
        binding = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "observatory_id": observatory_id,
                "source_hash": source_hash,
                "observatory": {
                    "observatory_id": observatory_id,
                    "zip_sha256": _sha256_path(self.observatory_store.zip_path(observatory_id)),
                    "zip_size_bytes": self.observatory_store.zip_path(observatory_id).stat().st_size,
                    "manifest_hash": verification.get("manifest_hash"),
                    "verification_report_hash": verification.get("integrity_hash"),
                    "verification_status": verification.get("status"),
                    "source_hash": summary.get("source_hash"),
                    "risk_register_hash": risk_register.get("integrity_hash"),
                    "recommendation_report_hash": recommendation_report.get("integrity_hash"),
                    "summary_hash": summary.get("integrity_hash"),
                    "release_ids": (summary.get("summary") or {}).get("release_ids") or [],
                },
                "source_risk_ids": [str(row.get("risk_id")) for row in risk_register.get("risks", []) if isinstance(row, dict) and row.get("risk_id")],
                "source_recommendation_ids": [str(row.get("recommendation_id")) for row in recommendation_report.get("recommendations", []) if isinstance(row, dict) and row.get("recommendation_id")],
                "observatory_config": config,
                "risk_register": risk_register,
                "recommendation_report": recommendation_report,
                "created_at": now_iso(),
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _build_queue_documents(
        self,
        queue_id: str,
        *,
        name: str | None,
        binding: dict[str, Any],
        include_risks: bool,
        include_recommendations: bool,
        severity_floor: str,
        policy: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        now = now_iso()
        source_hash = str(binding.get("source_hash") or "")
        effective_policy = {
            "allow_safe_actions": bool(policy.get("allow_safe_actions", True)),
            "allow_provider_actions": bool(policy.get("allow_provider_actions", False)),
            "allow_mutating_actions": bool(policy.get("allow_mutating_actions", False)),
            "require_manual_for_signoff": True,
            "require_manual_for_baseline_change": True,
            "require_manual_for_music_change": True,
        }
        items = _action_items_from_binding(queue_id, binding, include_risks=include_risks, include_recommendations=include_recommendations, severity_floor=severity_floor)
        queue = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE,
                "queue_id": queue_id,
                "name": _bounded(name or "Audio Quality Action Queue", 120),
                "status": "draft",
                "source": binding.get("observatory", {}),
                "source_hash": source_hash,
                "policy": effective_policy,
                "summary": {},
                "created_at": now,
                "updated_at": now,
            }
        )
        item_doc = {"schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "queue_id": queue_id, "source_hash": source_hash, "items": items, "updated_at": now}
        item_doc["integrity_hash"] = _integrity_hash(item_doc)
        results = {"schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "queue_id": queue_id, "source_hash": source_hash, "results": [], "updated_at": now}
        results["integrity_hash"] = _integrity_hash(results)
        manual_actions = {"schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "queue_id": queue_id, "source_hash": source_hash, "manual_actions": [], "updated_at": now}
        manual_actions["integrity_hash"] = _integrity_hash(manual_actions)
        preliminary = _build_summary(queue, binding, item_doc, results, manual_actions, stale_reasons=[])
        queue["status"] = preliminary.get("status")
        queue["summary"] = preliminary.get("summary", {})
        queue["integrity_hash"] = _integrity_hash(queue)
        summary = _build_summary(queue, binding, item_doc, results, manual_actions, stale_reasons=[])
        return {"queue": queue, "source_binding": binding, "items": item_doc, "results": results, "manual_actions": manual_actions, "summary": summary}

    def _current_docs_for_export(self, queue_id: str) -> dict[str, dict[str, Any]]:
        docs = self._read_documents(queue_id)
        stale = self._stale_reasons(docs["source_binding"])
        if stale:
            raise ReleaseAudioQualityActionQueueStateError("Audio Quality Action Queue source is stale. Refresh Observatory and create a new queue.")
        summary = _build_summary(docs["queue"], docs["source_binding"], docs["items"], docs["results"], docs["manual_actions"], stale_reasons=[])
        docs["summary"] = summary
        write_json(self.summary_path(queue_id), summary)
        return docs

    def _read_documents(self, queue_id: str) -> dict[str, dict[str, Any]]:
        queue_id = _validate_queue_id(queue_id)
        if not self.queue_path(queue_id).exists():
            raise ReleaseAudioQualityActionQueueNotFoundError(f"Audio Quality Action Queue not found: {queue_id}.")
        paths = {
            "queue": self.queue_path(queue_id),
            "source_binding": self.source_binding_path(queue_id),
            "items": self.action_items_path(queue_id),
            "results": self.action_results_path(queue_id),
            "manual_actions": self.manual_actions_path(queue_id),
            "summary": self.summary_path(queue_id),
        }
        return {key: read_json(path) for key, path in paths.items()}

    def _write_documents(self, queue_id: str, docs: dict[str, dict[str, Any]]) -> None:
        write_json(self.queue_path(queue_id), docs["queue"])
        write_json(self.source_binding_path(queue_id), docs["source_binding"])
        write_json(self.action_items_path(queue_id), docs["items"])
        write_json(self.action_results_path(queue_id), docs["results"])
        write_json(self.manual_actions_path(queue_id), docs["manual_actions"])
        write_json(self.summary_path(queue_id), docs["summary"])

    def _stale_reasons(self, binding: dict[str, Any]) -> list[str]:
        observatory_id = str(binding.get("observatory_id") or binding.get("observatory", {}).get("observatory_id") or "")
        if not observatory_id:
            return ["observatory_id_missing"]
        try:
            current = self._build_source_binding(observatory_id)
        except Exception:
            return ["observatory_unreadable"]
        reasons = []
        if current.get("source_hash") != binding.get("source_hash"):
            reasons.append("source_hash")
        for key in ("zip_sha256", "zip_size_bytes", "manifest_hash", "source_hash", "risk_register_hash", "recommendation_report_hash", "summary_hash"):
            if (current.get("observatory") or {}).get(key) != (binding.get("observatory") or {}).get(key):
                reasons.append(f"observatory_{key}")
        return sorted(set(reasons))

    def _observatory_zip_from_queue(self, queue_id: str) -> Path | None:
        binding = read_json(self.source_binding_path(queue_id))
        observatory_id = str(binding.get("observatory_id") or binding.get("observatory", {}).get("observatory_id") or "")
        return self.observatory_store.zip_path(observatory_id) if observatory_id else None

    def _observatory_verification_from_queue(self, queue_id: str) -> Path | None:
        binding = read_json(self.source_binding_path(queue_id))
        observatory_id = str(binding.get("observatory_id") or binding.get("observatory", {}).get("observatory_id") or "")
        return self.observatory_store.verification_report_path(observatory_id) if observatory_id else None

    def _next_queue_id(self) -> str:
        self.queues_dir().mkdir(parents=True, exist_ok=True)
        existing = [int(match.group(1)) for path in self.queues_dir().glob("aqa-*") if (match := re.match(r"aqa-(\d{6})$", path.name))]
        return f"aqa-{(max(existing) if existing else 0) + 1:06d}"

    def _latest_queue_id(self) -> str | None:
        rows = []
        for queue_path in self.queues_dir().glob("*/action-queue.json"):
            try:
                queue = read_json(queue_path)
            except Exception:
                continue
            rows.append((str(queue.get("updated_at") or queue.get("created_at") or ""), str(queue.get("queue_id") or queue_path.parent.name)))
        return sorted(rows, reverse=True)[0][1] if rows else None

    def _append_history_event(self, queue_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = _read_jsonl(self.history_path(queue_id)) if self.history_path(queue_id).exists() else []
        previous = rows[-1].get("event_hash") if rows else None
        event = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "event_id": f"aqaevt-{len(rows) + 1:06d}",
                "event_type": event_type,
                "created_at": now_iso(),
                "previous_event_hash": previous,
                "payload": payload,
            }
        )
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        self.history_path(queue_id).parent.mkdir(parents=True, exist_ok=True)
        with self.history_path(queue_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event


def build_expected_action_documents_from_observatory(
    queue: dict[str, Any],
    source_binding: dict[str, Any],
    *,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> dict[str, Any]:
    if not observatory_zip_path or not observatory_verification_report_path or not evidence_root:
        raise ReleaseAudioQualityActionQueueValidationError("Current Observatory verification requires Observatory ZIP, verification report, and evidence root.")
    observatory_zip = Path(observatory_zip_path)
    verification_path = Path(observatory_verification_report_path)
    verification = read_json(verification_path)
    runtime = verify_release_audio_quality_observatory_package(observatory_zip, strict=True, require_current_evidence=True, evidence_root=evidence_root, require_no_critical_risk=False)
    if verification.get("package_type") != RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE:
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report has the wrong package type.")
    if not _integrity_ok(verification):
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report integrity failed.")
    if verification.get("status") != "passed" or runtime.get("status") != "passed":
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification is not passed.")
    if verification.get("zip_sha256") != _sha256_path(observatory_zip) or int(verification.get("zip_size_bytes") or -1) != observatory_zip.stat().st_size or verification.get("manifest_hash") != runtime.get("manifest_hash"):
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report does not match the current Observatory ZIP.")
    with zipfile.ZipFile(observatory_zip) as archive:
        config = _read_json_entry(archive, "observatory-config.json")
        risk_register = _read_json_entry(archive, "risk-register.json")
        recommendation_report = _read_json_entry(archive, "recommendation-report.json")
        summary = _read_json_entry(archive, "observatory-summary.json")
    expected_binding = _source_binding_from_external(
        config,
        risk_register,
        recommendation_report,
        summary,
        observatory_zip=observatory_zip,
        verification=verification,
    )
    expected_items = _action_items_from_binding(
        str(queue.get("queue_id") or ""),
        expected_binding,
        include_risks=True,
        include_recommendations=True,
        severity_floor="info",
    )
    return {"source_binding": expected_binding, "items": expected_items, "verification": verification, "runtime": runtime}


def _source_binding_from_external(
    config: dict[str, Any],
    risk_register: dict[str, Any],
    recommendation_report: dict[str, Any],
    summary: dict[str, Any],
    *,
    observatory_zip: Path,
    verification: dict[str, Any],
) -> dict[str, Any]:
    observatory_id = str(config.get("observatory_id") or summary.get("observatory_id") or "")
    source_hash = stable_hash(
        {
            "observatory_id": observatory_id,
            "observatory_zip_sha256": _sha256_path(observatory_zip),
            "observatory_zip_size_bytes": observatory_zip.stat().st_size,
            "observatory_manifest_hash": verification.get("manifest_hash"),
            "observatory_source_hash": summary.get("source_hash"),
            "risk_register_hash": risk_register.get("integrity_hash"),
            "recommendation_report_hash": recommendation_report.get("integrity_hash"),
        }
    )
    binding = sanitize_metadata(
        {
            "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
            "observatory_id": observatory_id,
            "source_hash": source_hash,
            "observatory": {
                "observatory_id": observatory_id,
                "zip_sha256": _sha256_path(observatory_zip),
                "zip_size_bytes": observatory_zip.stat().st_size,
                "manifest_hash": verification.get("manifest_hash"),
                "verification_report_hash": verification.get("integrity_hash"),
                "verification_status": verification.get("status"),
                "source_hash": summary.get("source_hash"),
                "risk_register_hash": risk_register.get("integrity_hash"),
                "recommendation_report_hash": recommendation_report.get("integrity_hash"),
                "summary_hash": summary.get("integrity_hash"),
                "release_ids": (summary.get("summary") or {}).get("release_ids") or [],
            },
            "source_risk_ids": [str(row.get("risk_id")) for row in risk_register.get("risks", []) if isinstance(row, dict) and row.get("risk_id")],
            "source_recommendation_ids": [str(row.get("recommendation_id")) for row in recommendation_report.get("recommendations", []) if isinstance(row, dict) and row.get("recommendation_id")],
            "observatory_config": config,
            "risk_register": risk_register,
            "recommendation_report": recommendation_report,
            "created_at": "external",
        }
    )
    binding["integrity_hash"] = _integrity_hash(binding)
    return binding


def _action_items_from_binding(
    queue_id: str,
    binding: dict[str, Any],
    *,
    include_risks: bool,
    include_recommendations: bool,
    severity_floor: str,
) -> list[dict[str, Any]]:
    severity_rank = {"info": 0, "warning": 1, "high": 2, "critical": 3, "blocking": 3}
    floor = severity_rank.get(str(severity_floor or "warning"), 1)
    risks = binding.get("risk_register", {}).get("risks") if isinstance(binding.get("risk_register"), dict) else []
    recommendations = binding.get("recommendation_report", {}).get("recommendations") if isinstance(binding.get("recommendation_report"), dict) else []
    items: list[dict[str, Any]] = []
    fingerprints: set[str] = set()

    def add_item(item: dict[str, Any]) -> None:
        fingerprint = stable_hash(
            {
                "source_type": item.get("source_type"),
                "source_id": item.get("source_id"),
                "action_type": item.get("action_type"),
                "target": item.get("target"),
            }
        )
        if fingerprint in fingerprints:
            return
        fingerprints.add(fingerprint)
        item["item_id"] = f"aqai-{len(items) + 1:06d}"
        item["fingerprint"] = fingerprint
        item["created_at"] = now_iso()
        items.append(sanitize_metadata(item))

    if include_risks:
        for risk in risks or []:
            if not isinstance(risk, dict):
                continue
            severity = str(risk.get("severity") or "warning")
            if severity_rank.get(severity, 1) < floor:
                continue
            action_type, execution_mode = _risk_action(str(risk.get("check_id") or "unknown"), severity)
            add_item(
                {
                    "source_type": "risk",
                    "source_id": risk.get("risk_id"),
                    "source_check_id": risk.get("check_id"),
                    "severity": severity,
                    "status": "pending",
                    "action_type": action_type,
                    "execution_mode": execution_mode,
                    "target": {"release_id": risk.get("release_id"), "track_id": risk.get("track_id"), "issue_type": risk.get("check_id")},
                    "inputs": {"reason": risk.get("message") or risk.get("reason") or risk.get("check_id")},
                    "requires_manual": execution_mode == "manual_required",
                    "can_auto_execute": execution_mode == "safe",
                }
            )
    if include_recommendations:
        for recommendation in recommendations or []:
            if not isinstance(recommendation, dict):
                continue
            action_type, execution_mode = _recommendation_action(str(recommendation.get("action") or "unknown"))
            add_item(
                {
                    "source_type": "recommendation",
                    "source_id": recommendation.get("recommendation_id"),
                    "source_check_id": recommendation.get("source_risk_id") or recommendation.get("action"),
                    "severity": "warning",
                    "status": "pending",
                    "action_type": action_type,
                    "execution_mode": execution_mode,
                    "target": {"release_id": recommendation.get("release_id"), "track_id": recommendation.get("track_id"), "issue_type": recommendation.get("action")},
                    "inputs": {"reason": recommendation.get("reason") or recommendation.get("action")},
                    "requires_manual": execution_mode == "manual_required",
                    "can_auto_execute": execution_mode == "safe",
                }
            )
    return items


def _risk_action(check_id: str, severity: str) -> tuple[str, str]:
    if check_id == "audio_evidence_not_current":
        return "verify_observatory", "safe"
    if check_id in {"manual_rating_floor", "quality_trend_decline"}:
        return "create_audio_quality_review_task", "safe"
    if check_id in {"critical_issue_hotspot", "needs_fix_backlog"}:
        return "create_audio_fix_sprint_draft", "safe"
    if check_id == "baseline_drift_detected":
        return "create_baseline_review_request", "manual_required"
    if severity in {"critical", "blocking"}:
        return "manual_audio_lead_review", "manual_required"
    return "manual_audio_lead_review", "manual_required"


def _recommendation_action(action: str) -> tuple[str, str]:
    if action == "refresh_audio_evidence":
        return "verify_observatory", "safe"
    if action == "open_audio_quality_review":
        return "create_audio_quality_review_task", "safe"
    if action == "open_regression_response":
        return "create_regression_response_plan_draft", "safe"
    if action == "review_baseline_policy":
        return "create_baseline_review_request", "manual_required"
    return "manual_audio_lead_review", "manual_required"


def _execute_item(item: dict[str, Any]) -> dict[str, Any]:
    started = now_iso()
    item_id = str(item.get("item_id") or "")
    action_type = str(item.get("action_type") or "")
    execution_mode = str(item.get("execution_mode") or "")
    if execution_mode == "manual_required" or bool(item.get("requires_manual")):
        return {"item_id": item_id, "status": "manual_required", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {"manual_required": True}, "error": None}
    safe_actions = {"refresh_observatory", "verify_observatory", "create_audio_quality_review_task", "create_audio_fix_sprint_draft", "create_regression_response_plan_draft"}
    if action_type not in safe_actions or execution_mode != "safe":
        return {"item_id": item_id, "status": "blocked", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {}, "error": "Action is not safe for automatic execution."}
    created_type = {
        "refresh_observatory": "observatory_refresh_request",
        "verify_observatory": "observatory_verification_request",
        "create_audio_quality_review_task": "review_task_draft",
        "create_audio_fix_sprint_draft": "audio_fix_sprint_draft",
        "create_regression_response_plan_draft": "regression_response_plan_draft",
    }.get(action_type, "safe_action_result")
    created_id = f"{created_type}-{item_id}"
    return {"item_id": item_id, "status": "completed", "action_type": action_type, "started_at": started, "finished_at": now_iso(), "result": {"created_object_type": created_type, "created_object_id": created_id, "manual_required": action_type.startswith("create_")}, "error": None}


def _manual_action_from_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "manual_action_id": f"aqman-{index:06d}",
            "item_id": item.get("item_id"),
            "action_type": item.get("action_type"),
            "reason": item.get("inputs", {}).get("reason") if isinstance(item.get("inputs"), dict) else "Manual action required.",
            "target": item.get("target", {}),
            "status": "manual_required",
        }
    )


def _build_summary(queue: dict[str, Any], source_binding: dict[str, Any], items: dict[str, Any], results: dict[str, Any], manual_actions: dict[str, Any], *, stale_reasons: list[str]) -> dict[str, Any]:
    item_rows = [row for row in items.get("items", []) if isinstance(row, dict)]
    result_rows = [row for row in results.get("results", []) if isinstance(row, dict)]
    manual_rows = [row for row in manual_actions.get("manual_actions", []) if isinstance(row, dict)]
    completed = sum(1 for row in result_rows if row.get("status") == "completed")
    failed = sum(1 for row in result_rows if row.get("status") == "failed")
    blocked = sum(1 for row in result_rows if row.get("status") == "blocked")
    manual_required = len(manual_rows) + sum(1 for row in result_rows if row.get("status") == "manual_required")
    pending = max(0, len(item_rows) - len(result_rows))
    critical_unhandled = sum(1 for row in item_rows if row.get("severity") in {"critical", "blocking"} and row.get("item_id") not in {result.get("item_id") for result in result_rows if result.get("status") in {"completed", "manual_required"}})
    if stale_reasons:
        status = "stale"
        readiness = "blocked"
    elif failed or blocked:
        status = "failed"
        readiness = "blocked"
    elif pending:
        status = "pending"
        readiness = "pending"
    elif manual_required:
        status = "completed_with_manual_actions"
        readiness = "manual_actions_required"
    else:
        status = "completed"
        readiness = "ready"
    summary = sanitize_metadata(
        {
            "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
            "package_type": "release_audio_quality_action_queue_summary",
            "queue_id": queue.get("queue_id"),
            "status": status,
            "source_hash": source_binding.get("source_hash"),
            "readiness": readiness,
            "stale_reasons": stale_reasons,
            "summary": {
                "item_count": len(item_rows),
                "completed_count": completed,
                "manual_required_count": manual_required,
                "blocked_count": blocked,
                "failed_count": failed,
                "pending_count": pending,
                "critical_source_risk_count": _safe_int((source_binding.get("risk_register") or {}).get("summary", {}).get("critical_risk_count") if isinstance(source_binding.get("risk_register"), dict) else 0),
                "critical_unhandled_count": critical_unhandled,
                "release_ids": (source_binding.get("observatory") or {}).get("release_ids") or [],
            },
            "document_hashes": {
                "action_queue": queue.get("integrity_hash"),
                "source_binding": source_binding.get("integrity_hash"),
                "action_items": items.get("integrity_hash"),
                "action_results": results.get("integrity_hash"),
                "manual_actions": manual_actions.get("integrity_hash"),
            },
            "created_at": now_iso(),
        }
    )
    summary["integrity_hash"] = _integrity_hash(summary)
    return summary


def _validate_queue_id(value: str) -> str:
    if not re.fullmatch(r"aqa-\d{6}", str(value or "")):
        raise ReleaseAudioQualityActionQueueValidationError(f"Invalid queue_id: {value}.")
    return str(value)


def _validate_observatory_id(value: str) -> str:
    if not re.fullmatch(r"aqo-\d{6}", str(value or "")):
        raise ReleaseAudioQualityActionQueueValidationError(f"Invalid observatory_id: {value}.")
    return str(value)


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _semantic_hash(value: Any) -> str:
    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _readme(queue: dict[str, Any], summary: dict[str, Any]) -> str:
    data = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    return "\n".join(
        [
            "MusicForge Release Audio Quality Action Queue",
            f"queue_id: {queue.get('queue_id')}",
            f"status: {summary.get('status')}",
            f"item_count: {data.get('item_count')}",
            f"manual_required_count: {data.get('manual_required_count')}",
            "",
            "This package records safe and manual governance actions derived from Release Audio Quality Observatory evidence.",
            "It does not modify music, signoffs, baselines, or provider state.",
            "",
        ]
    )
