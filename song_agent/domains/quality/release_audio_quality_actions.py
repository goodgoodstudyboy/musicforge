# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.lifecycle import HistoryChain
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore as ReleaseAudioQualityObservatoryStore
from song_agent.domains.quality.release_audio_quality_observatory_verifier import RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_observatory_package as verify_release_audio_quality_observatory_package, write_release_audio_quality_observatory_verification_report as write_release_audio_quality_observatory_verification_report
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.quality.release_audio_quality_action_semantics import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE, RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION as RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, ReleaseAudioQualityActionQueueError as ReleaseAudioQualityActionQueueError, ReleaseAudioQualityActionQueueValidationError as ReleaseAudioQualityActionQueueValidationError, _action_items_from_binding as _action_items_from_binding, _action_selection as _action_selection, _integrity_hash as _integrity_hash, _integrity_ok as _integrity_ok, _read_json_entry as _read_json_entry, _recommendation_action as _recommendation_action, _risk_action as _risk_action, _selection_from_documents as _selection_from_documents, _sha256_path as _sha256_path, _source_binding_from_external as _source_binding_from_external, _with_action_selection as _with_action_selection, build_expected_action_documents_from_observatory as build_expected_action_documents_from_observatory


from song_agent.domains.quality import v142_raqa_readiness as _v142_raqa_readiness
from song_agent.domains.quality.v142_raqa_readiness import (
    ReleaseAudioQualityActionQueueNotFoundError,
    ReleaseAudioQualityActionQueueStateError,
    _execute_item,
    _manual_action_from_item,
    _build_summary,
    _validate_queue_id,
    _validate_observatory_id,
    _bounded,
    _semantic_hash,
    _file_record,
    _read_jsonl,
    _history_chain_ok,
    _safe_int,
    _readme,
)








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

    def signoff_history_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-queue-signoff-history.jsonl"

    def signoff_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "action-queue-signoff.json"

    def export_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "export"

    def zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "release-audio-quality-action-queue.zip"

    def verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "verification-report.json"

    def list_queues(self) -> list[DomainDocument]:
        rows: list[ImplementationDocument] = []
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
        policy: DomainDocument | None = None,
    ) -> DomainDocument:
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
            self._record_history_event(queue_id, "queue_created", {"source_hash": binding.get("source_hash"), "item_count": docs["summary"].get("summary", {}).get("item_count")})
            return docs["queue"]

    def read_queue(self, queue_id: str) -> DomainDocument:
        path = self.queue_path(queue_id)
        if not path.exists():
            raise ReleaseAudioQualityActionQueueNotFoundError(f"Audio Quality Action Queue not found: {queue_id}.")
        return read_json(path)

    def read_summary(self, queue_id: str) -> DomainDocument:
        path = self.summary_path(queue_id)
        if not path.exists():
            raise ReleaseAudioQualityActionQueueNotFoundError(f"Audio Quality Action Queue summary not found: {queue_id}.")
        return read_json(path)

    def refresh_status(self, queue_id: str) -> DomainDocument:
        with self.lock:
            self._ensure_mutable(queue_id, "refresh status")
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

    def run_safe(self, queue_id: str) -> DomainDocument:
        with self.lock:
            self._ensure_mutable(queue_id, "run safe actions")
            docs = self._read_documents(queue_id)
            stale = self._stale_reasons(docs["source_binding"])
            if stale:
                raise ReleaseAudioQualityActionQueueStateError("Audio Quality Action Queue source is stale. Refresh Observatory and create a new queue.")
            items = _as_list(docs["items"].get("items"))
            existing_results = {str(row.get("item_id")): row for row in docs["results"].get("results", []) if isinstance(row, dict)}
            result_rows: list[ImplementationDocument] = []
            manual_rows: list[ImplementationDocument] = []
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
            self._record_history_event(queue_id, "queue_run_safe_completed", {"status": summary.get("status"), "summary_hash": summary.get("integrity_hash")})
            return {"status": summary.get("status"), "queue_id": queue_id, "summary": summary.get("summary", {}), "results": results, "manual_actions": manual_actions}

    def export_package(self, queue_id: str) -> DomainDocument:
        with self.lock:
            self._ensure_mutable(queue_id, "export queue")
            docs = self._current_docs_for_export(queue_id)
            export_dir = self.export_dir(queue_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[ImplementationDocument] = []

            def write_entry(rel: str, payload: DomainDocument | list[DomainDocument] | str) -> None:
                path = export_dir / rel
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                elif rel.endswith(".jsonl"):
                    rows = _as_list(payload)
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

    def build_zip(self, queue_id: str) -> DomainDocument:
        with self.lock:
            self._ensure_mutable(queue_id, "build queue ZIP")
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

    def verify_zip(self, queue_id: str, **kwargs: Any) -> DomainDocument:
        from song_agent.domains.quality.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package, write_release_audio_quality_action_queue_verification_report

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

    def gate(self, release_id: str, *, queue_id: str | None = None, required: bool, require_no_blocking: bool = True) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            queue_id = queue_id or self._latest_queue_id()
            if not queue_id:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue is missing."}
            report = self.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=require_no_blocking)
            summary = _as_document(report.get("summary"))
            release_ids = {str(item) for item in summary.get("release_ids", []) if str(item)}
            if release_id not in release_ids:
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue does not cover this Release.", "verification": report}
            if report.get("status") == "failed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Quality Action Queue verification failed.", "verification": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Quality Action Queue gate passed.", "verification": report, "summary": summary}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _build_source_binding(self, observatory_id: str) -> ImplementationDocument:
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
        binding: ImplementationDocument,
        include_risks: bool,
        include_recommendations: bool,
        severity_floor: str,
        policy: ImplementationDocument,
    ) -> dict[str, ImplementationDocument]:
        now = now_iso()
        selection = _action_selection(include_risks=include_risks, include_recommendations=include_recommendations, severity_floor=severity_floor)
        binding = _with_action_selection(binding, selection)
        source_hash = str(binding.get("source_hash") or "")
        effective_policy = {
            "allow_safe_actions": bool(policy.get("allow_safe_actions", True)),
            "allow_provider_actions": bool(policy.get("allow_provider_actions", False)),
            "allow_mutating_actions": bool(policy.get("allow_mutating_actions", False)),
            "require_manual_for_signoff": True,
            "require_manual_for_baseline_change": True,
            "require_manual_for_music_change": True,
        }
        items = _action_items_from_binding(
            queue_id,
            binding,
            include_risks=selection["include_risks"],
            include_recommendations=selection["include_recommendations"],
            severity_floor=selection["severity_floor"],
        )
        queue = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE,
                "queue_id": queue_id,
                "name": _bounded(name or "Audio Quality Action Queue", 120),
                "status": "draft",
                "source": binding.get("observatory", {}),
                "source_hash": source_hash,
                "action_selection": selection,
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

    def _current_docs_for_export(self, queue_id: str) -> dict[str, ImplementationDocument]:
        self._ensure_mutable(queue_id, "export queue")
        docs = self._read_documents(queue_id)
        stale = self._stale_reasons(docs["source_binding"])
        if stale:
            raise ReleaseAudioQualityActionQueueStateError("Audio Quality Action Queue source is stale. Refresh Observatory and create a new queue.")
        summary = _build_summary(docs["queue"], docs["source_binding"], docs["items"], docs["results"], docs["manual_actions"], stale_reasons=[])
        docs["summary"] = summary
        write_json(self.summary_path(queue_id), summary)
        return docs

    def _read_documents(self, queue_id: str) -> dict[str, ImplementationDocument]:
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

    def _write_documents(self, queue_id: str, docs: dict[str, ImplementationDocument]) -> None:
        write_json(self.queue_path(queue_id), docs["queue"])
        write_json(self.source_binding_path(queue_id), docs["source_binding"])
        write_json(self.action_items_path(queue_id), docs["items"])
        write_json(self.action_results_path(queue_id), docs["results"])
        write_json(self.manual_actions_path(queue_id), docs["manual_actions"])
        write_json(self.summary_path(queue_id), docs["summary"])

    def _stale_reasons(self, binding: ImplementationDocument) -> list[str]:
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

    def _record_history_event(self, queue_id: str, event_type: str, payload: ImplementationDocument) -> ImplementationDocument:
        chain = HistoryChain(self.history_path(queue_id), sanitizer=sanitize_metadata, hash_mode="payload")
        rows = chain.read()
        return chain.append(
            {
                "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
                "event_id": f"aqaevt-{len(rows) + 1:06d}",
                "event_type": event_type,
                "created_at": now_iso(),
                "payload": payload,
            }
        )

    def _ensure_mutable(self, queue_id: str, action: str) -> None:
        if self._has_effective_signoff(queue_id):
            raise ReleaseAudioQualityActionQueueStateError(f"Audio Quality Action Queue is signed. Reset signoff before attempting to {action}.")

    def _has_effective_signoff(self, queue_id: str) -> bool:
        if self.signoff_path(queue_id).exists():
            return True
        rows = _read_jsonl(self.signoff_history_path(queue_id)) if self.signoff_history_path(queue_id).exists() else []
        if not rows or not _history_chain_ok(rows):
            return False
        return any(row.get("event_type") == "action_queue_signoff_created" for row in rows)

_v142_raqa_readiness.bind_globals(globals())
