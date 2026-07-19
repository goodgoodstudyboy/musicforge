from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_handoff_verifier import UNIFIED_COMMAND_CENTER_HANDOFF_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_HANDOFF_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION, verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package, write_unified_command_center_handoff_verification_report as write_unified_command_center_handoff_verification_report
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore


class UnifiedCommandCenterHandoffError(ValueError):
    pass


class UnifiedCommandCenterHandoffStateError(UnifiedCommandCenterHandoffError):
    pass


class UnifiedCommandCenterHandoffStore:
    def __init__(self, signoff_store: UnifiedCommandCenterSignoffStore | None = None) -> None:
        self.signoff_store = signoff_store or UnifiedCommandCenterSignoffStore()
        self.lock = threading.RLock()

    @property
    def center_store(self) -> UnifiedCommandCenterStore:
        return self.signoff_store.center_store

    def handoff_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "handoff"

    def manifest_path(self, center_id: str) -> Path:
        return self.handoff_dir(center_id) / "manifest.json"

    def zip_path(self, center_id: str) -> Path:
        return self.handoff_dir(center_id) / "musicforge-final-handoff-pack.zip"

    def verification_report_path(self, center_id: str) -> Path:
        return self.handoff_dir(center_id) / "handoff-verification-report.json"

    def export_handoff(self, center_id: str) -> dict[str, Any]:
        with self.lock:
            source = self._source_state(center_id)
            handoff_dir = self.handoff_dir(center_id)
            if handoff_dir.exists():
                shutil.rmtree(handoff_dir)
            handoff_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = handoff_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            report = _handoff_report(center_id, source)
            package_index = _package_index(center_id, source)
            write_entry("handoff-report.json", report)
            write_entry("package-index.json", package_index)
            write_entry("archive-verification-report.json", source["archive_verification"])
            write_entry("verification-instructions.txt", _instructions(source))
            write_entry("README.txt", _readme(report))
            source_doc = {
                "source_hash": report.get("source_hash"),
                "archive_zip_sha256": source["archive_verification"].get("zip_sha256"),
                "archive_manifest_hash": source["archive_verification"].get("manifest_hash"),
                "archive_verification_hash": source["archive_verification"].get("integrity_hash"),
                "signoff_hash": source["signoff"].get("integrity_hash"),
                "readiness_hash": source["signoff"].get("readiness_hash"),
                "handoff_report_hash": report.get("integrity_hash"),
                "package_index_hash": package_index.get("integrity_hash"),
            }
            manifest = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION,
                    "package_type": UNIFIED_COMMAND_CENTER_HANDOFF_PACKAGE_TYPE,
                    "center_id": center_id,
                    "created_at": now_iso(),
                    "source": source_doc,
                    "summary": report.get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(center_id), manifest)
            return manifest

    def build_handoff_zip(self, center_id: str) -> dict[str, Any]:
        with self.lock:
            manifest = self.export_handoff(center_id)
            handoff_dir = self.handoff_dir(center_id)
            zip_path = self.zip_path(center_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(handoff_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(handoff_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
            manifest = read_json(self.manifest_path(center_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(handoff_dir).as_posix()) for path in sorted(handoff_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(center_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(handoff_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(handoff_dir).as_posix())
            return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_handoff(self, center_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_command_center_handoff_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_archive=bool(payload.get("require_archive", True)),
            archive_zip_path=payload.get("archive_zip") or payload.get("archive_zip_path") or self.signoff_store.archive_zip_path(center_id),
            archive_verification_report_path=payload.get("archive_verification_report") or payload.get("archive_verification_report_path") or self.signoff_store.archive_verification_report_path(center_id),
        )
        write_unified_command_center_handoff_verification_report(report, self.verification_report_path(center_id))
        return report

    def gate(self, center_id: str, *, required: bool = True, handoff_zip_path: Path | str | None = None, handoff_verification_report_path: Path | str | None = None) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        handoff_zip = Path(handoff_zip_path) if handoff_zip_path else self.zip_path(center_id)
        verification_path = Path(handoff_verification_report_path) if handoff_verification_report_path else self.verification_report_path(center_id)
        if not handoff_zip.exists():
            return _gate_failed("Unified Command Center Handoff ZIP is missing.")
        if not verification_path.exists():
            return _gate_failed("Unified Command Center Handoff verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_command_center_handoff_package(
                handoff_zip,
                strict=True,
                require_archive=True,
                archive_zip_path=self.signoff_store.archive_zip_path(center_id),
                archive_verification_report_path=self.signoff_store.archive_verification_report_path(center_id),
            )
            if external.get("integrity_hash") != _integrity_hash(external):
                return _gate_failed("Unified Command Center Handoff verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Handoff verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Handoff verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Handoff gate passed.", "handoff_zip_sha256": runtime.get("zip_sha256"), "handoff_verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            from song_agent.domains.creation.redaction import sanitize_sensitive_text

            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _source_state(self, center_id: str) -> ImplementationDocument:
        signoff = self.signoff_store.read_signoff(center_id)
        archive_zip = self.signoff_store.archive_zip_path(center_id)
        archive_verification_path = self.signoff_store.archive_verification_report_path(center_id)
        if not archive_zip.exists():
            raise UnifiedCommandCenterHandoffStateError("Unified Command Center Archive ZIP is missing.")
        if not archive_verification_path.exists():
            raise UnifiedCommandCenterHandoffStateError("Unified Command Center Archive verification report is missing.")
        archive_verification = read_json(archive_verification_path)
        runtime = verify_unified_command_center_handoff_archive(archive_zip, archive_verification_path)
        if runtime.get("status") != "passed":
            raise UnifiedCommandCenterHandoffStateError("Unified Command Center Archive verification failed.")
        return {"signoff": signoff, "archive_verification": archive_verification, "archive_zip_path": archive_zip}


def verify_unified_command_center_handoff_archive(archive_zip: Path, archive_verification_path: Path) -> dict[str, Any]:
    from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package

    external = read_json(archive_verification_path)
    runtime = verify_unified_command_center_archive_package(archive_zip, strict=True, require_signed=True)
    if external.get("integrity_hash") != _integrity_hash(external):
        return {"status": "failed", "blockers": ["archive_verification_integrity"]}
    if external.get("status") != "passed" or runtime.get("status") != "passed":
        return {"status": "failed", "blockers": ["archive_verification_status"]}
    if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
        return {"status": "failed", "blockers": ["archive_verification_binding"]}
    return {"status": "passed"}


def _handoff_report(center_id: str, source: ImplementationDocument) -> ImplementationDocument:
    signoff = source["signoff"]
    archive_verification = source["archive_verification"]
    report = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION,
            "package_type": "musicforge_final_handoff_report",
            "center_id": center_id,
            "created_at": now_iso(),
            "source": {
                "archive_zip_sha256": archive_verification.get("zip_sha256"),
                "archive_manifest_hash": archive_verification.get("manifest_hash"),
                "archive_verification_hash": archive_verification.get("integrity_hash"),
                "signoff_hash": signoff.get("integrity_hash"),
                "readiness_hash": signoff.get("readiness_hash"),
            },
            "summary": {
                "status": "ready" if archive_verification.get("status") == "passed" and signoff.get("status") == "signed" else "blocked",
                "signed": signoff.get("status") == "signed",
                "signed_by": signoff.get("signed_by"),
                "signed_at": signoff.get("signed_at"),
                "blockers": 0 if archive_verification.get("status") == "passed" else 1,
                "manual_actions": 0,
                "warnings": 0,
            },
            "tool": {"name": "MusicForge Final Handoff Pack", "version": __version__},
        }
    )
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _package_index(center_id: str, source: ImplementationDocument) -> ImplementationDocument:
    archive_verification = source["archive_verification"]
    signoff = source["signoff"]
    source_hash = stable_hash(
        {
            "archive_zip_sha256": archive_verification.get("zip_sha256"),
            "archive_manifest_hash": archive_verification.get("manifest_hash"),
            "archive_verification_hash": archive_verification.get("integrity_hash"),
            "signoff_hash": signoff.get("integrity_hash"),
            "readiness_hash": signoff.get("readiness_hash"),
        }
    )
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION,
            "package_type": "musicforge_final_handoff_package_index",
            "center_id": center_id,
            "source_hash": source_hash,
            "items": [
                {
                    "package_type": "musicforge_unified_command_center_archive",
                    "role": "primary_archive",
                    "zip_sha256": archive_verification.get("zip_sha256"),
                    "zip_size_bytes": archive_verification.get("zip_size_bytes"),
                    "manifest_hash": archive_verification.get("manifest_hash"),
                    "verification_report_hash": archive_verification.get("integrity_hash"),
                    "verification_status": archive_verification.get("status"),
                }
            ],
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _instructions(source: ImplementationDocument) -> str:
    archive_sha = source["archive_verification"].get("zip_sha256")
    return "\n".join(
        [
            "Verify the Final Handoff Pack with:",
            "python -m song_agent.cli verify-unified-command-center-handoff-package <handoff.zip> --strict --require-archive --archive-zip <archive.zip> --archive-verification-report <archive-verification.json>",
            "",
            f"Expected archive sha256: {archive_sha}",
            "",
        ]
    )


def _readme(report: ImplementationDocument) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "MusicForge Final Handoff Pack",
            "",
            f"Center: {report.get('center_id')}",
            f"Status: {summary.get('status')}",
            f"Signed by: {summary.get('signed_by')}",
            "",
            "This pack contains public-safe handoff metadata and fingerprints. It does not embed the underlying archive ZIP.",
            "",
        ]
    )


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
