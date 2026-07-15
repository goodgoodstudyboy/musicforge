from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.trust.public_trust_center import PublicTrustCenterStore
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.public_trust_center_anchor_registry_contracts import ANCHOR_ENTRY_HASH_EXCLUDE_KEYS, ANCHOR_ENTRY_STATUSES, ANCHOR_EVENT_HASH_EXCLUDE_KEYS, ANCHOR_MANIFEST_HASH_EXCLUDE_KEYS, ANCHOR_REGISTRY_BLOCKED_KEYS, ANCHOR_REGISTRY_HASH_EXCLUDE_KEYS, ANCHOR_REGISTRY_PACKAGE_TYPE, ANCHOR_REPORT_HASH_EXCLUDE_KEYS, _current_entry, _find_entry, anchor_entry_hash, anchor_entry_signature_ok, anchor_event_hash, anchor_registry_hash, anchor_registry_manifest_hash, anchor_registry_report_hash, anchor_registry_summary, anchor_registry_verification_summary


ANCHOR_REGISTRY_SCHEMA_VERSION = 1

ANCHOR_REGISTRY_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_registry_report"







ANCHOR_DELIVERY_PACKAGE_TYPE = "musicforge_public_trust_center_delivery_anchor"


class PublicTrustCenterAnchorRegistryError(ValueError):
    pass


class PublicTrustCenterAnchorRegistryNotFoundError(PublicTrustCenterAnchorRegistryError):
    pass


class PublicTrustCenterAnchorRegistryStateError(PublicTrustCenterAnchorRegistryError):
    pass


class PublicTrustCenterAnchorRegistryStore:
    def __init__(self, *, trust_center_store: PublicTrustCenterStore) -> None:
        self.trust_center_store = trust_center_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.trust_center_store.center_dir(center_id) / "anchor-registry"

    def registry_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "registry.json"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "anchor-registry-report.json"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "anchor-registry-export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "public-trust-center-anchor-registry.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "anchor-registry-verification-report.json"

    def read_registry(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.registry_path(center_id), default=default)

    def read_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(center_id), default=default)

    def get_entry(self, center_id: str, entry_id: str) -> dict[str, Any]:
        entry = _find_entry(self.read_registry(center_id, default={}), entry_id)
        if not entry:
            raise PublicTrustCenterAnchorRegistryNotFoundError("Public Trust Center Anchor Registry entry not found.")
        return entry

    def register_current_anchor(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            anchor = self._read_current_anchor(center_id)
            self._ensure_anchor_matches_current_ptc(center_id, anchor)
            anchor_hash = str(anchor.get("anchor_hash") or "")
            registry = self._registry_or_empty(center_id, now=now)
            for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
                if isinstance(entry, dict) and entry.get("anchor_hash") == anchor_hash:
                    return sanitize_metadata({"existing": True, "entry": entry, "registry": registry}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)
            entry = self._build_entry(registry, center_id, anchor, payload, status="draft", now=now)
            registry.setdefault("entries", []).append(entry)
            self._append_event(registry, "registered", entry["entry_id"], {"anchor_hash": anchor_hash, "reason": _safe_text(payload.get("reason") or "register current anchor")}, now=now)
            self._finalize_registry(registry, now=now)
            self._write_registry(center_id, registry)
            return sanitize_metadata({"existing": False, "entry": entry, "registry": registry}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def publish_entry(self, center_id: str, entry_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            reason = _reason(payload, default="publish anchor entry")
            registry = self._require_registry(center_id)
            entry = _find_entry_mut(registry, entry_id)
            if entry.get("status") == "revoked":
                raise PublicTrustCenterAnchorRegistryStateError("Revoked anchor entries cannot be published.")
            self._ensure_anchor_matches_current_ptc(center_id, entry.get("anchor") if isinstance(entry.get("anchor"), dict) else {})
            current_id = str(registry.get("current_entry_id") or "")
            if current_id and current_id != entry_id:
                if not bool(payload.get("supersede_current", False)):
                    raise PublicTrustCenterAnchorRegistryStateError("A current anchor entry already exists. Use supersede_current=true to replace it.")
                current = _find_entry_mut(registry, current_id)
                if current.get("status") == "published":
                    current["status"] = "superseded"
                    current["superseded_at"] = now
                    current["superseded_by_entry_id"] = entry_id
                    current["integrity_hash"] = anchor_entry_hash(current)
                    self._append_event(registry, "superseded", current_id, {"replacement_entry_id": entry_id, "reason": reason}, now=now)
            entry["status"] = "published"
            entry["published_at"] = entry.get("published_at") or now
            entry["revoked_at"] = None
            entry["revocation_reason"] = None
            entry["integrity_hash"] = anchor_entry_hash(entry)
            registry["current_entry_id"] = entry_id
            self._append_event(registry, "published", entry_id, {"anchor_hash": entry.get("anchor_hash"), "reason": reason}, now=now)
            self._finalize_registry(registry, now=now)
            self._write_registry(center_id, registry)
            return sanitize_metadata({"entry": entry, "registry": registry}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def revoke_entry(self, center_id: str, entry_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            reason = _reason(payload, default="")
            registry = self._require_registry(center_id)
            entry = _find_entry_mut(registry, entry_id)
            if entry.get("status") not in {"published", "superseded"}:
                raise PublicTrustCenterAnchorRegistryStateError("Only published or superseded anchor entries can be revoked.")
            entry["status"] = "revoked"
            entry["revoked_at"] = now
            entry["revocation_reason"] = reason
            entry["integrity_hash"] = anchor_entry_hash(entry)
            if registry.get("current_entry_id") == entry_id:
                registry["current_entry_id"] = None
            self._append_event(registry, "revoked", entry_id, {"reason_hash": stable_hash(reason)}, now=now)
            self._finalize_registry(registry, now=now)
            self._write_registry(center_id, registry)
            return sanitize_metadata({"entry": entry, "registry": registry}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def supersede_entry(self, center_id: str, entry_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            registered = self.register_current_anchor(center_id, payload, now=now)
            new_entry = registered["entry"]
            if new_entry.get("entry_id") == entry_id:
                raise PublicTrustCenterAnchorRegistryStateError("Replacement anchor must differ from the superseded entry.")
            return self.publish_entry(center_id, str(new_entry.get("entry_id")), {**payload, "supersede_current": True, "reason": _reason(payload, default="supersede anchor entry")}, now=now)

    def refresh_report(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            registry = self.read_registry(center_id, default={}) or self._registry_or_empty(center_id, now=now)
            blockers, warnings, checks = self._findings(center_id, registry)
            current = _current_entry(registry)
            source = {
                "registry_hash": registry.get("integrity_hash"),
                "current_entry_id": registry.get("current_entry_id"),
                "current_entry_hash": current.get("integrity_hash") if current else None,
                "current_anchor_hash": current.get("anchor_hash") if current else None,
                "current_zip_sha256": (current.get("zip_fingerprint") if isinstance(current.get("zip_fingerprint"), dict) else {}).get("zip_sha256") if current else None,
                "current_manifest_hash": (current.get("zip_fingerprint") if isinstance(current.get("zip_fingerprint"), dict) else {}).get("manifest_hash") if current else None,
                "current_source_hash": (current.get("zip_fingerprint") if isinstance(current.get("zip_fingerprint"), dict) else {}).get("source_hash") if current else None,
            }
            report = {
                "schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION,
                "package_type": ANCHOR_REGISTRY_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "summary": anchor_registry_summary(registry),
                "source": source,
                "source_hash": stable_hash(source),
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = anchor_registry_report_hash(report)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            return sanitize_metadata(report, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def export_registry(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            registry = self._require_registry(center_id)
            report = self.read_report(center_id, default={}) or self.refresh_report(center_id, now=now)
            self._ensure_exportable(center_id, registry, report)
            state = _state_tuple(registry, report)
            if self._history_has_state_event(registry, state, "exported"):
                raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry export already exists for this registry state.")
            export_dir = self.export_dir(center_id).resolve()
            root = self.root_dir(center_id).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "anchor-registry-manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry export already exists for this registry state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "entries").mkdir(parents=True, exist_ok=True)
            chain = build_chain_of_custody(registry, report, generated_at=now)
            current = _current_entry(registry)
            _write_json(export_dir / "registry.json", registry)
            _write_json(export_dir / "anchor-registry-report.json", report)
            _write_json(export_dir / "chain-of-custody.json", chain)
            _write_json(export_dir / "current-anchor.json", current.get("anchor") if current else {})
            for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
                if isinstance(entry, dict):
                    _write_json(export_dir / "entries" / f"{_safe_id(str(entry.get('entry_id') or 'entry'))}.json", entry)
            _write_readme(export_dir, registry, report)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "anchor-registry-manifest.json"]
            manifest = {
                "schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION,
                "package_type": ANCHOR_REGISTRY_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Anchor Registry", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "registry": {"integrity_hash": registry.get("integrity_hash"), "current_entry_id": registry.get("current_entry_id"), "current_entry_hash": current.get("integrity_hash") if current else None},
                "registry_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "current_anchor": {"anchor_hash": current.get("anchor_hash") if current else None, "entry_id": current.get("entry_id") if current else None},
                "chain_of_custody": {"integrity_hash": chain.get("integrity_hash"), "source_hash": chain.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
            }
            manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
            _write_json(export_dir / "anchor-registry-manifest.json", manifest)
            self._append_event(registry, "exported", str(registry.get("current_entry_id") or ""), {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            self._finalize_registry(registry, now=now)
            self._write_registry(center_id, registry)
            return sanitize_metadata(manifest, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def build_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            registry = self._require_registry(center_id)
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, registry, report)
            state = _state_tuple(registry, report)
            if self._history_has_state_event(registry, state, "zip_built"):
                raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry ZIP already exists for this registry state.")
            export_dir = self.export_dir(center_id).resolve()
            zip_path = self.zip_path(center_id).resolve()
            root = self.root_dir(center_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "anchor-registry-manifest.json").exists():
                self.export_registry(center_id, now=now)
            manifest = read_json(export_dir / "anchor-registry-manifest.json")
            if _manifest_state(manifest) != state:
                raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry export is stale. Re-export before ZIP.")
            if zip_path.exists():
                existing = _read_zip_json(zip_path, "anchor-registry-manifest.json")
                if _manifest_state(existing) == state:
                    raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry ZIP already exists for this registry state.")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
            _write_json(export_dir / "anchor-registry-manifest.json", manifest)
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
            registry = self._require_registry(center_id)
            self._append_event(registry, "zip_built", str(registry.get("current_entry_id") or ""), {**state, "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            self._finalize_registry(registry, now=now)
            self._write_registry(center_id, registry)
            return sanitize_metadata(info, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        registry = self.read_registry(center_id, default={})
        report = self.read_report(center_id, default={})
        verification = _read_json_default(self.verification_report_path(center_id), default={})
        summary = anchor_registry_summary(registry)
        summary["report_status"] = report.get("status") or "missing"
        summary["verification_status"] = verification.get("status") or "missing"
        return sanitize_metadata(summary, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)

    def _read_current_anchor(self, center_id: str) -> dict[str, Any]:
        anchor_path = self.trust_center_store.delivery_anchor_path(center_id)
        if not anchor_path.exists() or not anchor_path.is_file() or anchor_path.is_symlink():
            raise PublicTrustCenterAnchorRegistryStateError("Public Trust Center delivery anchor does not exist. Build the Trust Center ZIP first.")
        value = read_json(anchor_path)
        anchor = value if isinstance(value, dict) else {}
        if anchor.get("package_type") != ANCHOR_DELIVERY_PACKAGE_TYPE:
            raise PublicTrustCenterAnchorRegistryStateError("Public Trust Center delivery anchor package_type is invalid.")
        expected_hash = stable_hash({key: val for key, val in anchor.items() if key != "anchor_hash"})
        if anchor.get("anchor_hash") != expected_hash:
            raise PublicTrustCenterAnchorRegistryStateError("Public Trust Center delivery anchor integrity failed.")
        return anchor

    def _ensure_anchor_matches_current_ptc(self, center_id: str, anchor: dict[str, Any]) -> None:
        zip_path = self.trust_center_store.zip_path(center_id)
        if not zip_path.exists():
            raise PublicTrustCenterAnchorRegistryStateError("Public Trust Center ZIP does not exist.")
        manifest = self.trust_center_store.read_export_manifest(center_id)
        report = self.trust_center_store.read_report(center_id, default={})
        checks = {
            "center_id": str(anchor.get("center_id") or "") == center_id,
            "zip_sha256": str(anchor.get("zip_sha256") or "") == str(_sha256(zip_path) or ""),
            "zip_size_bytes": str(anchor.get("zip_size_bytes") or "") == str(zip_path.stat().st_size),
            "manifest_hash": str(anchor.get("manifest_hash") or "") == str(manifest.get("integrity_hash") or ""),
            "source_hash": str(anchor.get("source_hash") or "") == str(report.get("source_hash") or ""),
        }
        failed = [key for key, ok in checks.items() if not ok]
        if failed:
            raise PublicTrustCenterAnchorRegistryStateError("Public Trust Center delivery anchor is not current: " + ", ".join(failed))

    def _build_entry(self, registry: dict[str, Any], center_id: str, anchor: dict[str, Any], payload: dict[str, Any], *, status: str, now: str) -> dict[str, Any]:
        anchor_hash = str(anchor.get("anchor_hash") or "")
        sidecars = anchor.get("fingerprint_sidecars") if isinstance(anchor.get("fingerprint_sidecars"), list) else []
        zip_fingerprint = {"zip_sha256": anchor.get("zip_sha256"), "zip_size_bytes": anchor.get("zip_size_bytes"), "manifest_hash": anchor.get("manifest_hash"), "source_hash": anchor.get("source_hash")}
        delivery_summary = {"count": len(sidecars), "fingerprint_sidecars_hash": stable_hash(sidecars)}
        signature_payload = {"anchor_hash": anchor_hash, "zip_fingerprint": zip_fingerprint, "delivery_fingerprint_summary": delivery_summary}
        signature = {
            "mode": "local_deterministic",
            "key_id": str(payload.get("key_id") or "local-anchor-key-default"),
            "signed_payload_hash": stable_hash(signature_payload),
        }
        signature["key_fingerprint"] = stable_hash({"key_id": signature["key_id"], "mode": signature["mode"]})
        signature["signature_hash"] = stable_hash(signature)
        entry = {
            "schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION,
            "entry_id": self._reserve_entry_id(registry),
            "center_id": center_id,
            "status": status,
            "created_at": now,
            "published_at": None,
            "superseded_at": None,
            "revoked_at": None,
            "revocation_reason": None,
            "superseded_by_entry_id": None,
            "reason": sanitize_sensitive_text(str(payload.get("reason") or "register current anchor"))[:1000],
            "anchor": anchor,
            "anchor_hash": anchor_hash,
            "zip_fingerprint": zip_fingerprint,
            "delivery_fingerprint_summary": delivery_summary,
            "signature": signature,
        }
        entry["integrity_hash"] = anchor_entry_hash(entry)
        return entry

    def _registry_or_empty(self, center_id: str, *, now: str) -> dict[str, Any]:
        registry = self.read_registry(center_id, default={})
        if registry:
            return registry
        registry = {
            "schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION,
            "package_type": ANCHOR_REGISTRY_PACKAGE_TYPE,
            "registry_id": f"ptcar-{_safe_id(center_id)}",
            "center_id": center_id,
            "created_at": now,
            "updated_at": now,
            "status": "empty",
            "current_entry_id": None,
            "entry_count": 0,
            "published_count": 0,
            "revoked_count": 0,
            "superseded_count": 0,
            "entries": [],
            "events": [],
        }
        registry["integrity_hash"] = anchor_registry_hash(registry)
        return registry

    def _require_registry(self, center_id: str) -> dict[str, Any]:
        registry = self.read_registry(center_id, default={})
        if not registry:
            raise PublicTrustCenterAnchorRegistryNotFoundError("Public Trust Center Anchor Registry does not exist.")
        return registry

    def _write_registry(self, center_id: str, registry: dict[str, Any]) -> None:
        self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
        _write_json(self.registry_path(center_id), registry)

    def _finalize_registry(self, registry: dict[str, Any], *, now: str) -> None:
        entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
        registry["entry_count"] = len(entries)
        registry["published_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "published")
        registry["revoked_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "revoked")
        registry["superseded_count"] = sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "superseded")
        registry["status"] = "empty" if not entries else "active"
        registry["updated_at"] = now
        registry["integrity_hash"] = anchor_registry_hash(registry)

    def _append_event(self, registry: dict[str, Any], event_type: str, entry_id: str, payload: dict[str, Any], *, now: str) -> None:
        events = registry.setdefault("events", [])
        previous = events[-1].get("event_hash") if events and isinstance(events[-1], dict) else None
        clean_payload = sanitize_metadata(payload if isinstance(payload, dict) else {}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)
        event = {
            "event_id": f"ptcar-event-{len(events) + 1:06d}",
            "event_type": event_type,
            "entry_id": entry_id,
            "created_at": now,
            "payload": clean_payload,
            "payload_hash": stable_hash(clean_payload),
            "previous_event_hash": previous,
        }
        event["event_hash"] = anchor_event_hash(event)
        events.append(event)

    def _findings(self, center_id: str, registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
        check("anchor_registry_integrity", anchor_registry_integrity_ok(registry), "Anchor Registry integrity hash is valid.")
        ids = [str(item.get("entry_id") or "") for item in entries if isinstance(item, dict)]
        check("anchor_entry_ids_unique", len(ids) == len(set(ids)), "Anchor entry ids are unique.")
        for entry in entries:
            if not isinstance(entry, dict):
                check("anchor_entry_shape", False, "Anchor entry must be an object.")
                continue
            entry_id = str(entry.get("entry_id") or "unknown")
            check(f"{entry_id}_integrity", anchor_entry_integrity_ok(entry), f"Anchor entry {entry_id} integrity is valid.")
            check(f"{entry_id}_status", entry.get("status") in ANCHOR_ENTRY_STATUSES, f"Anchor entry {entry_id} status is valid.")
            check(f"{entry_id}_signature", anchor_entry_signature_ok(entry), f"Anchor entry {entry_id} signature envelope is valid.")
            anchor = entry.get("anchor") if isinstance(entry.get("anchor"), dict) else {}
            check(f"{entry_id}_anchor_hash", anchor.get("anchor_hash") == entry.get("anchor_hash") == stable_hash({key: val for key, val in anchor.items() if key != "anchor_hash"}), f"Anchor entry {entry_id} anchor hash is valid.")
            if entry.get("status") == "superseded":
                target = str(entry.get("superseded_by_entry_id") or "")
                check(f"{entry_id}_superseded_target", bool(target) and target in ids, f"Anchor entry {entry_id} replacement exists.")
        current_id = str(registry.get("current_entry_id") or "")
        current = _find_entry(registry, current_id) if current_id else {}
        check("anchor_current_entry_exists", not current_id or bool(current), "Current anchor entry exists when set.")
        check("anchor_current_entry_published", not current_id or current.get("status") == "published", "Current anchor entry is published.")
        if current:
            try:
                self._ensure_anchor_matches_current_ptc(center_id, current.get("anchor") if isinstance(current.get("anchor"), dict) else {})
                current_ok = True
            except PublicTrustCenterAnchorRegistryStateError:
                current_ok = False
            check("anchor_current_matches_ptc", current_ok, "Current anchor entry matches the current Public Trust Center ZIP.")
        check("anchor_event_chain", _event_chain_ok(registry), "Anchor Registry event chain is valid.")
        return blockers, warnings, checks

    def _ensure_exportable(self, center_id: str, registry: dict[str, Any], report: dict[str, Any]) -> None:
        if not anchor_registry_integrity_ok(registry):
            raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry integrity failed.")
        if not anchor_registry_report_integrity_ok(report):
            raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry Report integrity failed.")
        source = report.get("source") if isinstance(report.get("source"), dict) else {}
        if source.get("registry_hash") != registry.get("integrity_hash") or report.get("source_hash") != stable_hash(source):
            raise PublicTrustCenterAnchorRegistryStateError("Anchor Registry Report is stale. Refresh before export.")
        blockers, _warnings, _checks = self._findings(center_id, registry)
        if blockers or report.get("status") == "failed":
            detail = str((blockers[0] if blockers else {}).get("message") or "Anchor Registry Report is failed.")
            raise PublicTrustCenterAnchorRegistryStateError(f"Anchor Registry cannot be exported: {detail}")

    def _reserve_entry_id(self, registry: dict[str, Any]) -> str:
        existing = {str(item.get("entry_id") or "") for item in registry.get("entries", []) if isinstance(item, dict)}
        index = len(existing) + 1
        while f"ptcar-entry-{index:06d}" in existing:
            index += 1
        return f"ptcar-entry-{index:06d}"

    def _history_has_state_event(self, registry: dict[str, Any], state: dict[str, str], event_type: str) -> bool:
        for event in registry.get("events", []) if isinstance(registry.get("events"), list) else []:
            if not isinstance(event, dict) or str(event.get("event_type") or "") != event_type:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if all(str(payload.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False





def anchor_registry_integrity_ok(registry: dict[str, Any] | None) -> bool:
    data = registry if isinstance(registry, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_hash(data)





def anchor_entry_integrity_ok(entry: dict[str, Any] | None) -> bool:
    data = entry if isinstance(entry, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_entry_hash(data)





def anchor_registry_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_report_hash(data)





def anchor_registry_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_registry_manifest_hash(data)














def build_chain_of_custody(registry: dict[str, Any], report: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    events = [dict(item) for item in registry.get("events", []) if isinstance(item, dict)]
    data = {"schema_version": ANCHOR_REGISTRY_SCHEMA_VERSION, "center_id": registry.get("center_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"event_count": len(events), "latest_event_type": events[-1].get("event_type") if events else None, "current_entry_id": registry.get("current_entry_id")}, "events": events}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)


def _state_tuple(registry: dict[str, Any], report: dict[str, Any]) -> dict[str, str]:
    current = _current_entry(registry)
    return {"registry_hash": str(registry.get("integrity_hash") or ""), "report_hash": str(report.get("integrity_hash") or ""), "current_entry_id": str(registry.get("current_entry_id") or ""), "current_entry_hash": str(current.get("integrity_hash") or "")}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    row = manifest.get("registry") if isinstance(manifest.get("registry"), dict) else {}
    report = manifest.get("registry_report") if isinstance(manifest.get("registry_report"), dict) else {}
    return {"registry_hash": str(row.get("integrity_hash") or ""), "report_hash": str(report.get("integrity_hash") or ""), "current_entry_id": str(row.get("current_entry_id") or ""), "current_entry_hash": str(row.get("current_entry_hash") or "")}








def _find_entry_mut(registry: dict[str, Any], entry_id: str) -> dict[str, Any]:
    entry = _find_entry(registry, entry_id)
    if not entry:
        raise PublicTrustCenterAnchorRegistryNotFoundError("Public Trust Center Anchor Registry entry not found.")
    return entry


def _event_chain_ok(registry: dict[str, Any]) -> bool:
    previous = None
    for event in registry.get("events", []) if isinstance(registry.get("events"), list) else []:
        if not isinstance(event, dict):
            return False
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("event_hash") != anchor_event_hash(event):
            return False
        previous = event.get("event_hash")
    return True


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS))


def _write_readme(export_dir: Path, registry: dict[str, Any], report: dict[str, Any]) -> None:
    text = (
        "MusicForge Public Trust Center Anchor Registry\n"
        "This package records public delivery anchors for a Public Trust Center ZIP.\n"
        "The local deterministic signature envelope is not a third-party certificate signature.\n"
        "If a ZIP, delivery anchor, and registry package are all replaced together, pure offline verification still needs an external trust anchor.\n"
        f"Center: {registry.get('center_id')}\n"
        f"Status: {report.get('status')}\n"
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _reason(payload: dict[str, Any], *, default: str) -> str:
    reason = sanitize_sensitive_text(str(payload.get("reason") or default).strip())
    if len(reason) < 4:
        raise PublicTrustCenterAnchorRegistryStateError("reason must be at least 4 characters.")
    return reason[:1000]


def _safe_text(value: Any) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:1000]


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "").strip())
    return text.strip("-") or "default"


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
        raise PublicTrustCenterAnchorRegistryStateError("Resolved path escapes Anchor Registry directory.") from exc
