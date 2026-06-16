from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.public_trust_center import PublicTrustCenterStore
from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
from song_agent.public_trust_center_anchor_registry_verifier import (
    verify_public_trust_center_anchor_registry_package,
    write_public_trust_center_anchor_registry_verification_report,
)
from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
from song_agent.public_trust_center_anchor_transparency_verifier import (
    verify_public_trust_center_anchor_transparency_package,
    write_public_trust_center_anchor_transparency_verification_report,
)
from song_agent.public_trust_center_verifier import verify_public_trust_center_package, write_public_trust_center_verification_report
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash


DISTRIBUTION_KIT_SCHEMA_VERSION = 1
DISTRIBUTION_KIT_PACKAGE_TYPE = "musicforge_public_trust_center_distribution_kit"
DISTRIBUTION_KIT_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_distribution_kit_report"
DISTRIBUTION_KIT_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
DISTRIBUTION_KIT_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
DISTRIBUTION_KIT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


class PublicTrustCenterDistributionKitError(ValueError):
    pass


class PublicTrustCenterDistributionKitNotFoundError(PublicTrustCenterDistributionKitError):
    pass


class PublicTrustCenterDistributionKitStateError(PublicTrustCenterDistributionKitError):
    pass


class PublicTrustCenterDistributionKitStore:
    def __init__(
        self,
        *,
        trust_center_store: PublicTrustCenterStore,
        anchor_registry_store: PublicTrustCenterAnchorRegistryStore,
        anchor_transparency_store: PublicTrustCenterAnchorTransparencyStore,
    ) -> None:
        self.trust_center_store = trust_center_store
        self.anchor_registry_store = anchor_registry_store
        self.anchor_transparency_store = anchor_transparency_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.trust_center_store.center_dir(center_id) / "distribution-kit"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "distribution-kit-report.json"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "public-trust-center-distribution-kit.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "distribution-kit-verification-report.json"

    def history_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "distribution-kit-history.json"

    def read_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(center_id), default=default)

    def refresh_report(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            source = self._current_source(center_id)
            checks, blockers, warnings = self._findings(source)
            report = {
                "schema_version": DISTRIBUTION_KIT_SCHEMA_VERSION,
                "package_type": DISTRIBUTION_KIT_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "source_hash": stable_hash(source),
                "summary": _summary_from_source(source, blockers, warnings),
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = distribution_kit_report_hash(report)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            return _sanitize(report)

    def export_kit(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "distribution_kit_exported"):
                raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit export already exists for this source state.")
            export_dir = self.export_dir(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            for relative in ("packages", "anchors", "verification-reports"):
                (export_dir / relative).mkdir(parents=True, exist_ok=True)

            files_to_copy = self._source_files(center_id)
            for target, source_path in files_to_copy.items():
                resolved = source_path.resolve()
                if not resolved.exists() or not resolved.is_file() or resolved.is_symlink():
                    raise PublicTrustCenterDistributionKitStateError(f"Required Distribution Kit file is missing: {target}")
                destination = export_dir / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(resolved, destination)

            _write_json(export_dir / "distribution-kit-report.json", report)
            file_index = self._file_index(export_dir)
            verification_index = self._verification_index(report)
            chain = self._chain_of_custody(report)
            _write_json(export_dir / "file-index.json", file_index)
            _write_json(export_dir / "verification-index.json", verification_index)
            _write_json(export_dir / "chain-of-custody.json", chain)
            _write_readme(export_dir)
            _write_verify(export_dir)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "distribution-kit-manifest.json"]
            manifest = {
                "schema_version": DISTRIBUTION_KIT_SCHEMA_VERSION,
                "package_type": DISTRIBUTION_KIT_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Distribution Kit", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source": report.get("source") if isinstance(report.get("source"), dict) else {},
                "source_hash": report.get("source_hash"),
                "requirements": _requirements(),
                "report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "file_index": {"integrity_hash": file_index.get("integrity_hash"), "source_hash": file_index.get("source_hash")},
                "verification_index": {"integrity_hash": verification_index.get("integrity_hash"), "source_hash": verification_index.get("source_hash")},
                "chain_of_custody": {"integrity_hash": chain.get("integrity_hash"), "source_hash": chain.get("source_hash")},
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = distribution_kit_manifest_hash(manifest)
            _write_json(export_dir / "distribution-kit-manifest.json", manifest)
            self._append_history(center_id, "distribution_kit_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            state = _state_row(report)
            if self._history_has_state_event(center_id, state, "distribution_kit_zip_built"):
                raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit ZIP already exists for this source state.")
            export_dir = self.export_dir(center_id).resolve()
            manifest = _read_json_default(export_dir / "distribution-kit-manifest.json", default={})
            if _manifest_state(manifest) != state:
                raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = distribution_kit_manifest_hash(manifest)
            _write_json(export_dir / "distribution-kit-manifest.json", manifest)
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
            self._append_history(center_id, "distribution_kit_zip_built", {**state, "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(info)

    def verify_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        from song_agent.public_trust_center_distribution_kit_verifier import (
            verify_public_trust_center_distribution_kit_package,
            write_public_trust_center_distribution_kit_verification_report,
        )

        payload = payload or {}
        report = verify_public_trust_center_distribution_kit_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_current=bool(payload.get("require_current", True)),
            require_delivery_readiness=bool(payload.get("require_delivery_readiness", True)),
            require_anchor_registry_current=bool(payload.get("require_anchor_registry_current", True)),
            require_anchor_published=bool(payload.get("require_anchor_published", True)),
            require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", True)),
            require_anchor_transparency_current=bool(payload.get("require_anchor_transparency_current", True)),
            require_anchor_checkpoint=bool(payload.get("require_anchor_checkpoint", True)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", False)),
            acceptance_board_signoff_archive_path=payload.get("acceptance_board_signoff_archive_path"),
            acceptance_board_path=payload.get("acceptance_board_path"),
            acceptance_board_verification_report_path=payload.get("acceptance_board_verification_report_path"),
            accepted_evidence_dir=payload.get("accepted_evidence_dir"),
            now=now,
        )
        write_public_trust_center_distribution_kit_verification_report(report, self.verification_report_path(center_id))
        return report

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        report = self.read_report(center_id, default={})
        verification = _read_json_default(self.verification_report_path(center_id), default={})
        return _sanitize(
            {
                "center_id": center_id,
                "status": report.get("status") or "missing",
                "verification_status": verification.get("status") or "missing",
                "zip_exists": self.zip_path(center_id).exists(),
                "source_hash": report.get("source_hash"),
            }
        )

    def _current_source(self, center_id: str) -> dict[str, Any]:
        ptc_zip = self.trust_center_store.zip_path(center_id)
        anchor_path = self.trust_center_store.delivery_anchor_path(center_id)
        registry_zip = self.anchor_registry_store.zip_path(center_id)
        transparency_zip = self.anchor_transparency_store.zip_path(center_id)
        checkpoint_path = self.anchor_transparency_store.current_checkpoint_path(center_id)
        ptc_verification = self._verify_ptc(center_id)
        registry_verification = self._verify_registry(center_id)
        transparency_verification = self._verify_transparency(center_id)
        ptc_manifest = _read_zip_json(ptc_zip, "trust-center-manifest.json") if ptc_zip.exists() else {}
        registry_manifest = _read_zip_json(registry_zip, "anchor-registry-manifest.json") if registry_zip.exists() else {}
        transparency_manifest = _read_zip_json(transparency_zip, "anchor-transparency-manifest.json") if transparency_zip.exists() else {}
        ptc_report = self.trust_center_store.read_report(center_id, default={})
        registry = self.anchor_registry_store.read_registry(center_id, default={})
        registry_report = self.anchor_registry_store.read_report(center_id, default={})
        transparency_report = self.anchor_transparency_store.read_report(center_id, default={})
        anchor = _read_json_default(anchor_path, default={})
        checkpoint = _read_json_default(checkpoint_path, default={})
        source = {
            "center_id": center_id,
            "ptc_report_hash": ptc_report.get("integrity_hash"),
            "ptc_zip_sha256": _sha256(ptc_zip),
            "ptc_zip_size_bytes": ptc_zip.stat().st_size if ptc_zip.exists() else None,
            "ptc_manifest_hash": ptc_manifest.get("integrity_hash"),
            "ptc_source_hash": ptc_manifest.get("source_hash"),
            "delivery_anchor_hash": anchor.get("anchor_hash"),
            "anchor_registry_current_hash": registry.get("integrity_hash"),
            "anchor_registry_current_entry_id": registry.get("current_entry_id"),
            "anchor_registry_report_hash": registry_report.get("integrity_hash"),
            "anchor_registry_zip_sha256": _sha256(registry_zip),
            "anchor_registry_zip_size_bytes": registry_zip.stat().st_size if registry_zip.exists() else None,
            "anchor_registry_manifest_hash": registry_manifest.get("integrity_hash"),
            "anchor_registry_verification_status": registry_verification.get("status"),
            "anchor_registry_verification_hash": _verification_hash(registry_verification),
            "anchor_transparency_report_hash": transparency_report.get("integrity_hash"),
            "anchor_transparency_zip_sha256": _sha256(transparency_zip),
            "anchor_transparency_zip_size_bytes": transparency_zip.stat().st_size if transparency_zip.exists() else None,
            "anchor_transparency_manifest_hash": transparency_manifest.get("integrity_hash"),
            "anchor_transparency_verification_status": transparency_verification.get("status"),
            "anchor_transparency_verification_hash": _verification_hash(transparency_verification),
            "checkpoint_hash": checkpoint.get("integrity_hash"),
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "ptc_verification_status": ptc_verification.get("status"),
            "ptc_verification_hash": _verification_hash(ptc_verification),
        }
        return _sanitize(source)

    def _verify_ptc(self, center_id: str) -> dict[str, Any]:
        report = verify_public_trust_center_package(
            self.trust_center_store.zip_path(center_id),
            strict=True,
            require_delivery_readiness=False,
            delivery_anchor_path=self.trust_center_store.delivery_anchor_path(center_id),
            anchor_registry_path=self.anchor_registry_store.zip_path(center_id),
            anchor_transparency_path=self.anchor_transparency_store.zip_path(center_id),
            anchor_checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id),
            require_anchor_registry_current=True,
            require_anchor_published=True,
            require_anchor_not_revoked=True,
            require_anchor_transparency_current=True,
            require_anchor_checkpoint=True,
        )
        write_public_trust_center_verification_report(report, self.trust_center_store.verification_report_path(center_id))
        return report

    def _verify_registry(self, center_id: str) -> dict[str, Any]:
        report = verify_public_trust_center_anchor_registry_package(
            self.anchor_registry_store.zip_path(center_id),
            strict=True,
            require_current=True,
            require_anchor_published=True,
            require_anchor_not_revoked=True,
        )
        write_public_trust_center_anchor_registry_verification_report(report, self.anchor_registry_store.verification_report_path(center_id))
        return report

    def _verify_transparency(self, center_id: str) -> dict[str, Any]:
        report = verify_public_trust_center_anchor_transparency_package(
            self.anchor_transparency_store.zip_path(center_id),
            strict=True,
            checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id),
            anchor_registry_path=self.anchor_registry_store.zip_path(center_id),
            require_current_checkpoint=True,
            require_published_anchor=True,
            require_not_revoked=True,
        )
        write_public_trust_center_anchor_transparency_verification_report(report, self.anchor_transparency_store.verification_report_path(center_id))
        return report

    def _source_files(self, center_id: str) -> dict[str, Path]:
        return {
            "packages/public-trust-center.zip": self.trust_center_store.zip_path(center_id),
            "packages/public-trust-center-anchor-registry.zip": self.anchor_registry_store.zip_path(center_id),
            "packages/public-trust-center-anchor-transparency.zip": self.anchor_transparency_store.zip_path(center_id),
            "anchors/public-trust-center.delivery-anchor.json": self.trust_center_store.delivery_anchor_path(center_id),
            "anchors/ptc-anchor-checkpoint-current.json": self.anchor_transparency_store.current_checkpoint_path(center_id),
            "verification-reports/public-trust-center-verification-report.json": self.trust_center_store.verification_report_path(center_id),
            "verification-reports/anchor-registry-verification-report.json": self.anchor_registry_store.verification_report_path(center_id),
            "verification-reports/anchor-transparency-verification-report.json": self.anchor_transparency_store.verification_report_path(center_id),
        }

    def _file_index(self, export_dir: Path) -> dict[str, Any]:
        rows = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name not in {"file-index.json", "distribution-kit-manifest.json"}]
        data = {"schema_version": DISTRIBUTION_KIT_SCHEMA_VERSION, "source_hash": self._report_source_hash(export_dir), "files": sorted(rows, key=lambda item: str(item.get("path") or ""))}
        data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
        return data

    def _verification_index(self, report: dict[str, Any]) -> dict[str, Any]:
        source = report.get("source") if isinstance(report.get("source"), dict) else {}
        rows = [
            {"name": "public_trust_center", "status": source.get("ptc_verification_status"), "verification_hash": source.get("ptc_verification_hash"), "report_path": "verification-reports/public-trust-center-verification-report.json", "package_path": "packages/public-trust-center.zip"},
            {"name": "anchor_registry", "status": source.get("anchor_registry_verification_status"), "verification_hash": source.get("anchor_registry_verification_hash"), "report_path": "verification-reports/anchor-registry-verification-report.json", "package_path": "packages/public-trust-center-anchor-registry.zip"},
            {"name": "anchor_transparency", "status": source.get("anchor_transparency_verification_status"), "verification_hash": source.get("anchor_transparency_verification_hash"), "report_path": "verification-reports/anchor-transparency-verification-report.json", "package_path": "packages/public-trust-center-anchor-transparency.zip"},
        ]
        data = {"schema_version": DISTRIBUTION_KIT_SCHEMA_VERSION, "source_hash": report.get("source_hash"), "verifications": rows}
        data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
        return data

    def _chain_of_custody(self, report: dict[str, Any]) -> dict[str, Any]:
        source = report.get("source") if isinstance(report.get("source"), dict) else {}
        data = {
            "schema_version": DISTRIBUTION_KIT_SCHEMA_VERSION,
            "source_hash": report.get("source_hash"),
            "center_id": report.get("center_id"),
            "events": [
                {"event_type": "public_trust_center_verified", "hash": source.get("ptc_verification_hash"), "status": source.get("ptc_verification_status")},
                {"event_type": "anchor_registry_verified", "hash": source.get("anchor_registry_verification_hash"), "status": source.get("anchor_registry_verification_status")},
                {"event_type": "anchor_transparency_verified", "hash": source.get("anchor_transparency_verification_hash"), "status": source.get("anchor_transparency_verification_status")},
                {"event_type": "distribution_kit_report_ready", "hash": report.get("integrity_hash"), "status": report.get("status")},
            ],
        }
        data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
        return data

    def _report_source_hash(self, export_dir: Path) -> str | None:
        report = _read_json_default(export_dir / "distribution-kit-report.json", default={})
        return report.get("source_hash")

    def _findings(self, source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        checks: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        check("distribution_kit_ptc_verified", source.get("ptc_verification_status") == "passed", "Public Trust Center verification passed.")
        check("distribution_kit_anchor_registry_verified", source.get("anchor_registry_verification_status") == "passed", "Anchor Registry verification passed.")
        check("distribution_kit_anchor_transparency_verified", source.get("anchor_transparency_verification_status") == "passed", "Anchor Transparency verification passed.")
        check("distribution_kit_checkpoint_present", bool(source.get("checkpoint_hash")), "Anchor checkpoint is present.")
        check("distribution_kit_delivery_anchor_present", bool(source.get("delivery_anchor_hash")), "Delivery anchor is present.")
        return checks, blockers, warnings

    def _ensure_exportable(self, center_id: str, report: dict[str, Any]) -> None:
        if not distribution_kit_report_integrity_ok(report):
            raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit Report integrity failed.")
        current = self._current_source(center_id)
        if report.get("source") != current or report.get("source_hash") != stable_hash(current):
            raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit Report is stale. Refresh before export.")
        if report.get("status") == "failed":
            raise PublicTrustCenterDistributionKitStateError("Public Trust Center Distribution Kit Report is failed.")

    def _append_history(self, center_id: str, event_type: str, payload: dict[str, Any], *, now: str) -> None:
        path = self.history_path(center_id)
        history = _read_json_default(path, default={"events": []})
        events = history.setdefault("events", [])
        clean = _sanitize(payload)
        events.append({"event_id": f"ptcdk-history-{len(events) + 1:06d}", "event_type": event_type, "created_at": now, "payload": clean, "payload_hash": stable_hash(clean)})
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


def distribution_kit_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in DISTRIBUTION_KIT_REPORT_HASH_EXCLUDE_KEYS})


def distribution_kit_report_integrity_ok(report: dict[str, Any]) -> bool:
    return bool(report) and str(report.get("integrity_hash") or "") == distribution_kit_report_hash(report)


def distribution_kit_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in DISTRIBUTION_KIT_MANIFEST_HASH_EXCLUDE_KEYS})


def distribution_kit_manifest_integrity_ok(manifest: dict[str, Any]) -> bool:
    return bool(manifest) and str(manifest.get("integrity_hash") or "") == distribution_kit_manifest_hash(manifest)


def distribution_kit_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return _sanitize({"status": report.get("status"), "center_id": report.get("center_id"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0), "source_hash": report.get("source_hash")})


def _summary_from_source(source: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "center_id": source.get("center_id"),
        "ptc_status": source.get("ptc_verification_status"),
        "anchor_registry_status": source.get("anchor_registry_verification_status"),
        "anchor_transparency_status": source.get("anchor_transparency_verification_status"),
        "checkpoint_status": "present" if source.get("checkpoint_hash") else "missing",
        "file_count": 8,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
    }


def _requirements() -> dict[str, bool]:
    return {
        "require_delivery_readiness": True,
        "require_anchor_registry_current": True,
        "require_anchor_published": True,
        "require_anchor_not_revoked": True,
        "require_anchor_transparency_current": True,
        "require_anchor_checkpoint": True,
    }


def _state_row(report: dict[str, Any]) -> dict[str, str]:
    return {"source_hash": str(report.get("source_hash") or ""), "report_hash": str(report.get("integrity_hash") or "")}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    report = manifest.get("report") if isinstance(manifest.get("report"), dict) else {}
    return {"source_hash": str(manifest.get("source_hash") or ""), "report_hash": str(report.get("integrity_hash") or "")}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    return write_json(path, _sanitize(payload))


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}


def _write_readme(export_dir: Path) -> None:
    text = "\n".join(
        [
            "MusicForge Public Trust Center Distribution Kit",
            "",
            "This kit contains the Public Trust Center ZIP, delivery anchor, Anchor Registry ZIP, Anchor Transparency ZIP, checkpoint, and verification reports.",
            "Run VERIFY.txt commands or verify-public-trust-center-distribution-kit-package with --deep before relying on it.",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _write_verify(export_dir: Path) -> None:
    text = "\n".join(
        [
            "Verify this kit:",
            "python -m song_agent.cli verify-public-trust-center-distribution-kit-package public-trust-center-distribution-kit.zip --strict --deep --require-current --json",
            "",
        ]
    )
    (export_dir / "VERIFY.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_hash(report: dict[str, Any]) -> str | None:
    if not report:
        return None
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterDistributionKitStateError("Resolved path escapes Public Trust Center Distribution Kit root.")


def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(payload, blocked_keys=DISTRIBUTION_KIT_BLOCKED_KEYS)
