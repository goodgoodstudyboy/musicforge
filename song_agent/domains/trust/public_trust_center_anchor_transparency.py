from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_anchor_registry import ANCHOR_REGISTRY_BLOCKED_KEYS as ANCHOR_REGISTRY_BLOCKED_KEYS, PublicTrustCenterAnchorRegistryStore as PublicTrustCenterAnchorRegistryStore, anchor_registry_summary as anchor_registry_summary, anchor_registry_verification_summary as anchor_registry_verification_summary
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_anchor_transparency_contracts import ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS as ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS, ANCHOR_CHECKPOINT_PACKAGE_TYPE as ANCHOR_CHECKPOINT_PACKAGE_TYPE, ANCHOR_TRANSPARENCY_BLOCKED_KEYS as ANCHOR_TRANSPARENCY_BLOCKED_KEYS, ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS, ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS, ANCHOR_TRANSPARENCY_PACKAGE_TYPE as ANCHOR_TRANSPARENCY_PACKAGE_TYPE, ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS as ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS, _checkpoint_payload_hash as _checkpoint_payload_hash, anchor_checkpoint_hash as anchor_checkpoint_hash, anchor_checkpoint_integrity_ok as anchor_checkpoint_integrity_ok, anchor_checkpoint_signature_ok as anchor_checkpoint_signature_ok, anchor_transparency_event_hash as anchor_transparency_event_hash, anchor_transparency_ledger_hash as anchor_transparency_ledger_hash, anchor_transparency_manifest_hash as anchor_transparency_manifest_hash, anchor_transparency_report_hash as anchor_transparency_report_hash, anchor_transparency_summary as anchor_transparency_summary


ANCHOR_TRANSPARENCY_SCHEMA_VERSION = 1

ANCHOR_TRANSPARENCY_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_transparency_report"








class PublicTrustCenterAnchorTransparencyError(ValueError):
    pass


class PublicTrustCenterAnchorTransparencyNotFoundError(PublicTrustCenterAnchorTransparencyError):
    pass


class PublicTrustCenterAnchorTransparencyStateError(PublicTrustCenterAnchorTransparencyError):
    pass


class PublicTrustCenterAnchorTransparencyStore:
    def __init__(self, *, anchor_registry_store: PublicTrustCenterAnchorRegistryStore) -> None:
        self.anchor_registry_store = anchor_registry_store
        self.trust_center_store = anchor_registry_store.trust_center_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.anchor_registry_store.root_dir(center_id) / "transparency"

    def ledger_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "ledger.jsonl"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "anchor-transparency-report.json"

    def checkpoints_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "checkpoints"

    def current_checkpoint_path(self, center_id: str = "ptc-default") -> Path:
        return self.checkpoints_dir(center_id) / "ptc-anchor-checkpoint-current.json"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "public-trust-center-anchor-transparency.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "anchor-transparency-verification-report.json"

    def history_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "transparency-history.json"

    def read_ledger(self, center_id: str = "ptc-default") -> list[dict[str, Any]]:
        path = self.ledger_path(center_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events

    def read_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(center_id), default=default)

    def read_checkpoint(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.current_checkpoint_path(center_id), default=default)

    def append_event_from_registry_state(
        self,
        center_id: str = "ptc-default",
        event_type: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            state = self._current_registry_state(center_id)
            events = self.read_ledger(center_id)
            event_type = event_type or _event_type_for_state(state)
            if events and events[-1].get("state_hash") == state.get("state_hash") and events[-1].get("event_type") == event_type:
                return sanitize_metadata(events[-1], blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)
            event = self._build_event(events, center_id, event_type, state, payload or {}, now=now)
            events.append(event)
            self._write_ledger(center_id, events)
            return sanitize_metadata(event, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def create_checkpoint(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            events = self.read_ledger(center_id)
            if not events:
                self.append_event_from_registry_state(center_id, payload=payload, now=now)
                events = self.read_ledger(center_id)
            latest = events[-1] if events else {}
            if not latest:
                raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency ledger has no events.")
            existing = self.read_checkpoint(center_id, default={})
            if existing.get("latest_event_hash") == latest.get("event_hash") and anchor_checkpoint_integrity_ok(existing) and anchor_checkpoint_signature_ok(existing):
                return sanitize_metadata(existing, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)
            state = latest.get("state") if isinstance(latest.get("state"), dict) else {}
            sequence = int(latest.get("sequence") or len(events))
            checkpoint = {
                "schema_version": ANCHOR_TRANSPARENCY_SCHEMA_VERSION,
                "package_type": ANCHOR_CHECKPOINT_PACKAGE_TYPE,
                "center_id": center_id,
                "checkpoint_id": f"ptc-anchor-checkpoint-{sequence:06d}",
                "created_at": now,
                "sequence": sequence,
                "latest_event_hash": latest.get("event_hash"),
                "ledger_hash": anchor_transparency_ledger_hash(events),
                "current_entry_id": state.get("current_entry_id"),
                "current_anchor_hash": state.get("current_anchor_hash"),
                "current_entry_status": state.get("current_entry_status"),
                "registry_hash": state.get("registry_hash"),
                "registry_zip_sha256": state.get("registry_zip_sha256"),
                "registry_zip_size_bytes": state.get("registry_zip_size_bytes"),
                "registry_manifest_hash": state.get("registry_manifest_hash"),
                "registry_verification_status": state.get("registry_verification_status"),
                "registry_verification_report_hash": state.get("registry_verification_report_hash"),
                "ptc_zip_sha256": state.get("ptc_zip_sha256"),
                "ptc_zip_size_bytes": state.get("ptc_zip_size_bytes"),
                "ptc_manifest_hash": state.get("ptc_manifest_hash"),
                "ptc_source_hash": state.get("ptc_source_hash"),
            }
            checkpoint["signature"] = _signature_envelope(_checkpoint_payload_hash(checkpoint), key_id=str((payload or {}).get("key_id") or "musicforge-local-anchor-transparency-v1"))
            checkpoint["integrity_hash"] = anchor_checkpoint_hash(checkpoint)
            self.checkpoints_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.checkpoints_dir(center_id) / f"{checkpoint['checkpoint_id']}.json", checkpoint)
            _write_json(self.current_checkpoint_path(center_id), checkpoint)
            return sanitize_metadata(checkpoint, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def refresh_report(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            self.append_event_from_registry_state(center_id, payload=payload, now=now)
            events = self.read_ledger(center_id)
            checkpoint = self.read_checkpoint(center_id, default={})
            if not checkpoint or checkpoint.get("latest_event_hash") != (events[-1].get("event_hash") if events else None):
                checkpoint = self.create_checkpoint(center_id, payload=payload, now=now)
            source = self._source_from_current(center_id, events, checkpoint)
            blockers, warnings, checks = self._findings(events, checkpoint, source)
            report = {
                "schema_version": ANCHOR_TRANSPARENCY_SCHEMA_VERSION,
                "package_type": ANCHOR_TRANSPARENCY_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "status": "failed" if blockers else "warning" if warnings else "current",
                "source": source,
                "source_hash": stable_hash(source),
                "summary": _summary_from_source(source, blockers, warnings),
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = anchor_transparency_report_hash(report)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            return sanitize_metadata(report, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def export_transparency(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            events = self.read_ledger(center_id)
            report = self.read_report(center_id, default={})
            checkpoint = self.read_checkpoint(center_id, default={})
            self._ensure_exportable(center_id, events, report, checkpoint)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "transparency_exported"):
                raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency export already exists for this source state.")
            export_dir = self.export_dir(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "anchor-transparency-report.json", report)
            (export_dir / "ledger.jsonl").write_text(_ledger_text(events), encoding="utf-8")
            for path in sorted(self.checkpoints_dir(center_id).glob("*.json")):
                shutil.copyfile(path, export_dir / "checkpoints" / path.name)
            registry_verification = _read_json_default(self.anchor_registry_store.verification_report_path(center_id), default={})
            registry = self.anchor_registry_store.read_registry(center_id, default={})
            current = _current_entry(registry)
            registry_summary = {
                "center_id": center_id,
                "registry_hash": registry.get("integrity_hash"),
                "summary": anchor_registry_summary(registry),
                "current_entry": _current_entry_summary(current),
                "current_anchor": current.get("anchor") if isinstance(current.get("anchor"), dict) else {},
            }
            verification_summary = _registry_verification_summary(registry_verification)
            chain = {
                "schema_version": ANCHOR_TRANSPARENCY_SCHEMA_VERSION,
                "center_id": center_id,
                "source_hash": report.get("source_hash"),
                "event_count": len(events),
                "latest_event_hash": events[-1].get("event_hash") if events else None,
                "events": events,
            }
            chain["integrity_hash"] = stable_hash({key: value for key, value in chain.items() if key != "integrity_hash"})
            _write_json(export_dir / "registry-verification-summary.json", verification_summary)
            _write_json(export_dir / "current-anchor-registry-summary.json", registry_summary)
            _write_json(export_dir / "chain-of-custody.json", chain)
            _write_readme(export_dir, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "anchor-transparency-manifest.json"]
            manifest = {
                "schema_version": ANCHOR_TRANSPARENCY_SCHEMA_VERSION,
                "package_type": ANCHOR_TRANSPARENCY_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Anchor Transparency", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "ledger": {"hash": source_or_none(report, "ledger_hash"), "latest_event_hash": source_or_none(report, "latest_event_hash")},
                "checkpoint": {"integrity_hash": checkpoint.get("integrity_hash"), "checkpoint_id": checkpoint.get("checkpoint_id"), "sequence": checkpoint.get("sequence")},
                "registry_verification_summary": {"hash": stable_hash(verification_summary), "status": verification_summary.get("status")},
                "current_anchor_registry_summary": {"hash": stable_hash(registry_summary), "current_entry_id": registry_summary.get("summary", {}).get("current_entry_id")},
                "chain_of_custody": {"integrity_hash": chain.get("integrity_hash"), "source_hash": chain.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
            }
            manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
            _write_json(export_dir / "anchor-transparency-manifest.json", manifest)
            self._append_history(center_id, "transparency_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def build_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            events = self.read_ledger(center_id)
            report = self.read_report(center_id, default={})
            checkpoint = self.read_checkpoint(center_id, default={})
            self._ensure_exportable(center_id, events, report, checkpoint)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "transparency_zip_built"):
                raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency ZIP already exists for this source state.")
            export_dir = self.export_dir(center_id).resolve()
            manifest = _read_json_default(export_dir / "anchor-transparency-manifest.json", default={})
            if _manifest_state(manifest) != state:
                raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
            _write_json(export_dir / "anchor-transparency-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            self._append_history(center_id, "transparency_zip_built", {**state, "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        report = self.read_report(center_id, default={})
        checkpoint = self.read_checkpoint(center_id, default={})
        verification = _read_json_default(self.verification_report_path(center_id), default={})
        return sanitize_metadata(
            {
                "center_id": center_id,
                "status": report.get("status") or "missing",
                "checkpoint_id": checkpoint.get("checkpoint_id"),
                "latest_event_hash": checkpoint.get("latest_event_hash"),
                "verification_status": verification.get("status") or "missing",
                "event_count": len(self.read_ledger(center_id)),
            },
            blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS,
        )

    def _current_registry_state(self, center_id: str) -> ImplementationDocument:
        registry = self.anchor_registry_store.read_registry(center_id, default={})
        if not registry:
            raise PublicTrustCenterAnchorTransparencyNotFoundError("Public Trust Center Anchor Registry does not exist.")
        current = _current_entry(registry)
        anchor = current.get("anchor") if isinstance(current.get("anchor"), dict) else {}
        verification = _read_json_default(self.anchor_registry_store.verification_report_path(center_id), default={})
        registry_zip = self.anchor_registry_store.zip_path(center_id)
        registry_manifest = _read_zip_json(registry_zip, "anchor-registry-manifest.json") if registry_zip.exists() else _read_json_default(self.anchor_registry_store.export_dir(center_id) / "anchor-registry-manifest.json", default={})
        state = {
            "center_id": center_id,
            "registry_hash": registry.get("integrity_hash"),
            "registry_report_hash": (self.anchor_registry_store.read_report(center_id, default={}) or {}).get("integrity_hash"),
            "registry_zip_sha256": _sha256(registry_zip),
            "registry_zip_size_bytes": registry_zip.stat().st_size if registry_zip.exists() else None,
            "registry_manifest_hash": registry_manifest.get("integrity_hash"),
            "registry_verification_status": verification.get("status") or "missing",
            "registry_verification_report_hash": stable_hash(verification) if verification else None,
            "current_entry_id": current.get("entry_id") if current else None,
            "current_entry_hash": current.get("integrity_hash") if current else None,
            "current_anchor_hash": current.get("anchor_hash") if current else None,
            "current_entry_status": current.get("status") if current else None,
            "ptc_zip_sha256": anchor.get("zip_sha256"),
            "ptc_zip_size_bytes": anchor.get("zip_size_bytes"),
            "ptc_manifest_hash": anchor.get("manifest_hash"),
            "ptc_source_hash": anchor.get("source_hash"),
        }
        state["state_hash"] = stable_hash(state)
        return state

    def _build_event(self, events: list[ImplementationDocument], center_id: str, event_type: str, state: ImplementationDocument, payload: ImplementationDocument, *, now: str) -> ImplementationDocument:
        previous = events[-1].get("event_hash") if events else None
        event = {
            "schema_version": ANCHOR_TRANSPARENCY_SCHEMA_VERSION,
            "event_id": f"ptcat-event-{len(events) + 1:06d}",
            "center_id": center_id,
            "sequence": len(events) + 1,
            "event_type": event_type,
            "created_at": now,
            "actor": _safe_text(payload.get("actor") or "local"),
            "reason": _safe_text(payload.get("reason") or event_type.replace("_", " ")),
            "anchor_entry_id": state.get("current_entry_id"),
            "anchor_hash": state.get("current_anchor_hash"),
            "registry_hash": state.get("registry_hash"),
            "registry_zip": {"zip_sha256": state.get("registry_zip_sha256"), "zip_size_bytes": state.get("registry_zip_size_bytes"), "manifest_hash": state.get("registry_manifest_hash")},
            "registry_verification": {"status": state.get("registry_verification_status"), "report_hash": state.get("registry_verification_report_hash")},
            "ptc_package": {"zip_sha256": state.get("ptc_zip_sha256"), "zip_size_bytes": state.get("ptc_zip_size_bytes"), "manifest_hash": state.get("ptc_manifest_hash"), "source_hash": state.get("ptc_source_hash")},
            "current_entry_status": state.get("current_entry_status"),
            "state": state,
            "state_hash": state.get("state_hash"),
            "previous_event_hash": previous,
        }
        event["event_hash"] = anchor_transparency_event_hash(event)
        return sanitize_metadata(event, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def _write_ledger(self, center_id: str, events: list[ImplementationDocument]) -> None:
        path = self.ledger_path(center_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_ledger_text(events), encoding="utf-8")

    def _source_from_current(self, center_id: str, events: list[ImplementationDocument], checkpoint: ImplementationDocument) -> ImplementationDocument:
        latest = events[-1] if events else {}
        state = latest.get("state") if isinstance(latest.get("state"), dict) else {}
        source = {
            "center_id": center_id,
            "registry_hash": state.get("registry_hash"),
            "registry_zip_sha256": state.get("registry_zip_sha256"),
            "registry_zip_size_bytes": state.get("registry_zip_size_bytes"),
            "registry_manifest_hash": state.get("registry_manifest_hash"),
            "registry_verification_status": state.get("registry_verification_status"),
            "registry_verification_report_hash": state.get("registry_verification_report_hash"),
            "current_entry_id": state.get("current_entry_id"),
            "current_entry_hash": state.get("current_entry_hash"),
            "current_entry_status": state.get("current_entry_status"),
            "current_anchor_hash": state.get("current_anchor_hash"),
            "ptc_zip_sha256": state.get("ptc_zip_sha256"),
            "ptc_zip_size_bytes": state.get("ptc_zip_size_bytes"),
            "ptc_manifest_hash": state.get("ptc_manifest_hash"),
            "ptc_source_hash": state.get("ptc_source_hash"),
            "event_count": len(events),
            "latest_sequence": latest.get("sequence"),
            "latest_event_hash": latest.get("event_hash"),
            "ledger_hash": anchor_transparency_ledger_hash(events),
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "checkpoint_hash": checkpoint.get("integrity_hash"),
            "checkpoint_sequence": checkpoint.get("sequence"),
        }
        return sanitize_metadata(source, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)

    def _findings(self, events: list[ImplementationDocument], checkpoint: ImplementationDocument, source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        latest = events[-1] if events else {}
        check("anchor_transparency_ledger_non_empty", bool(events), "Anchor Transparency ledger has events.")
        check("anchor_transparency_event_chain", _event_chain_ok(events), "Anchor Transparency event chain is valid.")
        check("anchor_transparency_registry_verified", source.get("registry_verification_status") == "passed", "Anchor Registry verification status is passed.")
        check("anchor_transparency_checkpoint_integrity", anchor_checkpoint_integrity_ok(checkpoint), "Anchor checkpoint integrity is valid.")
        check("anchor_transparency_checkpoint_signature", anchor_checkpoint_signature_ok(checkpoint), "Anchor checkpoint signature envelope is valid.")
        check("anchor_transparency_checkpoint_latest_event", checkpoint.get("latest_event_hash") == latest.get("event_hash"), "Anchor checkpoint binds the latest ledger event.")
        check("anchor_transparency_checkpoint_ledger", checkpoint.get("ledger_hash") == anchor_transparency_ledger_hash(events), "Anchor checkpoint binds the ledger hash.")
        for key in ("current_entry_id", "current_anchor_hash", "registry_hash", "registry_zip_sha256", "registry_manifest_hash", "ptc_zip_sha256", "ptc_manifest_hash", "ptc_source_hash"):
            check(f"anchor_transparency_checkpoint_{key}", checkpoint.get(key) == source.get(key), f"Anchor checkpoint {key} matches source.")
        return blockers, warnings, checks

    def _ensure_exportable(self, center_id: str, events: list[ImplementationDocument], report: ImplementationDocument, checkpoint: ImplementationDocument) -> None:
        if not events:
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency ledger is empty.")
        if not anchor_transparency_report_integrity_ok(report):
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency Report integrity failed.")
        if report.get("source_hash") != stable_hash(report.get("source") if isinstance(report.get("source"), dict) else {}):
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency Report source hash failed.")
        current_source = self._source_from_current(center_id, events, checkpoint)
        if report.get("source") != current_source:
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency Report is stale. Refresh before export.")
        latest = events[-1] if events else {}
        latest_state = latest.get("state") if isinstance(latest.get("state"), dict) else {}
        registry_state = self._current_registry_state(center_id)
        if latest_state.get("state_hash") != registry_state.get("state_hash"):
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency Report is stale. Refresh before export.")
        if report.get("status") == "failed":
            raise PublicTrustCenterAnchorTransparencyStateError("Anchor Transparency Report is failed.")

    def _append_history(self, center_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        path = self.history_path(center_id)
        history = _read_json_default(path, default={"events": []})
        events = history.setdefault("events", [])
        clean = sanitize_metadata(payload, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS)
        events.append({"event_id": f"ptcat-history-{len(events) + 1:06d}", "event_type": event_type, "created_at": now, "payload": clean, "payload_hash": stable_hash(clean)})
        history["updated_at"] = now
        _write_json(path, history)

    def _history_has_state_event(self, center_id: str, state: dict[str, str], event_type: str) -> bool:
        history = _read_json_default(self.history_path(center_id), default={})
        for event in history.get("events", []) if isinstance(history.get("events"), list) else []:
            if not isinstance(event, dict) or str(event.get("event_type") or "") != event_type:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if all(str(payload.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False




















def anchor_transparency_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_transparency_report_hash(data)





def anchor_transparency_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_transparency_manifest_hash(data)








def _signature_envelope(payload_hash: str, *, key_id: str) -> ImplementationDocument:
    signature = {
        "mode": "local_deterministic_checkpoint",
        "key_id": key_id,
        "payload_hash": payload_hash,
    }
    signature["key_fingerprint"] = stable_hash({"key_id": signature["key_id"], "mode": signature["mode"]})
    signature["signature_hash"] = stable_hash(signature)
    return signature


def _event_type_for_state(state: ImplementationDocument) -> str:
    if state.get("current_entry_status") == "revoked":
        return "anchor_revoked"
    if state.get("current_entry_status") == "published":
        return "anchor_published" if state.get("registry_verification_status") != "passed" else "anchor_registry_verified"
    return "anchor_registered"


def _summary_from_source(source: ImplementationDocument, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    return {
        "center_id": source.get("center_id"),
        "status": "failed" if blockers else "warning" if warnings else "current",
        "event_count": source.get("event_count", 0),
        "latest_sequence": source.get("latest_sequence"),
        "latest_event_hash": source.get("latest_event_hash"),
        "checkpoint_id": source.get("checkpoint_id"),
        "checkpoint_hash": source.get("checkpoint_hash"),
        "current_entry_id": source.get("current_entry_id"),
        "current_anchor_hash": source.get("current_anchor_hash"),
        "current_entry_status": source.get("current_entry_status"),
        "registry_verification_status": source.get("registry_verification_status"),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _registry_verification_summary(report: ImplementationDocument) -> ImplementationDocument:
    summary = anchor_registry_verification_summary(report if isinstance(report, dict) else {})
    return sanitize_metadata(
        {
            "status": report.get("status") if isinstance(report, dict) else "missing",
            "zip_sha256": report.get("zip_sha256") if isinstance(report, dict) else None,
            "zip_size_bytes": report.get("zip_size_bytes") if isinstance(report, dict) else None,
            "manifest_hash": report.get("manifest_hash") if isinstance(report, dict) else None,
            "verification_report_hash": stable_hash(report) if report else None,
            "summary": summary,
        },
        blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS,
    )


def _current_entry_summary(entry: ImplementationDocument) -> ImplementationDocument:
    anchor = entry.get("anchor") if isinstance(entry.get("anchor"), dict) else {}
    return {
        "entry_id": entry.get("entry_id"),
        "status": entry.get("status"),
        "integrity_hash": entry.get("integrity_hash"),
        "anchor_hash": entry.get("anchor_hash"),
        "ptc_zip_sha256": anchor.get("zip_sha256"),
        "ptc_manifest_hash": anchor.get("manifest_hash"),
        "ptc_source_hash": anchor.get("source_hash"),
    }


def _current_entry(registry: ImplementationDocument) -> ImplementationDocument:
    current_id = str(registry.get("current_entry_id") or "")
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == current_id:
            return entry
    return {}


def _event_chain_ok(events: list[ImplementationDocument]) -> bool:
    previous = None
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            return False
        if event.get("sequence") != index:
            return False
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("event_hash") != anchor_transparency_event_hash(event):
            return False
        previous = event.get("event_hash")
    return True


def source_or_none(report: dict[str, Any], key: str) -> Any:
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    return source.get(key)


def _state_row(report: ImplementationDocument) -> dict[str, str]:
    return {
        "source_hash": str(report.get("source_hash") or ""),
        "report_hash": str(report.get("integrity_hash") or ""),
        "latest_event_hash": str(source_or_none(report, "latest_event_hash") or ""),
        "checkpoint_hash": str(source_or_none(report, "checkpoint_hash") or ""),
    }


def _manifest_state(manifest: ImplementationDocument) -> dict[str, str]:
    report = manifest.get("report") if isinstance(manifest.get("report"), dict) else {}
    ledger = manifest.get("ledger") if isinstance(manifest.get("ledger"), dict) else {}
    checkpoint = manifest.get("checkpoint") if isinstance(manifest.get("checkpoint"), dict) else {}
    return {
        "source_hash": str(manifest.get("source_hash") or ""),
        "report_hash": str(report.get("integrity_hash") or ""),
        "latest_event_hash": str(ledger.get("latest_event_hash") or ""),
        "checkpoint_hash": str(checkpoint.get("integrity_hash") or ""),
    }


def _ledger_text(events: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events)


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(Path(path), sanitize_metadata(payload, blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS))


def _write_readme(export_dir: Path, report: ImplementationDocument) -> None:
    text = (
        "MusicForge Public Trust Center Anchor Transparency\n"
        "This package records an append-only local transparency ledger for Public Trust Center Anchor Registry states.\n"
        "External checkpoint files are the portable trust anchor for detecting whole-package replacement.\n"
        f"Center: {report.get('center_id')}\n"
        f"Status: {report.get('status')}\n"
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _safe_text(value: Any) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:1000]


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PublicTrustCenterAnchorTransparencyStateError("Resolved path escapes Anchor Transparency directory.") from exc
