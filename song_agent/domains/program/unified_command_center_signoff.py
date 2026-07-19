from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterNotFoundError as UnifiedCommandCenterNotFoundError, UnifiedCommandCenterStateError as UnifiedCommandCenterStateError, UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import UNIFIED_COMMAND_CENTER_ARCHIVE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_ARCHIVE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_ARCHIVE_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_ARCHIVE_SCHEMA_VERSION, verify_unified_command_center_archive_package as verify_unified_command_center_archive_package, write_unified_command_center_archive_verification_report as write_unified_command_center_archive_verification_report
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package as verify_unified_command_center_package


UNIFIED_COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION = 1


class UnifiedCommandCenterSignoffError(ValueError):
    pass


class UnifiedCommandCenterSignoffNotFoundError(UnifiedCommandCenterSignoffError):
    pass


class UnifiedCommandCenterSignoffStateError(UnifiedCommandCenterSignoffError):
    pass


class UnifiedCommandCenterSignoffStore:
    def __init__(self, center_store: UnifiedCommandCenterStore | None = None) -> None:
        self.center_store = center_store or UnifiedCommandCenterStore()
        self.lock = threading.RLock()

    def signoff_path(self, center_id: str) -> Path:
        return self.center_store.signoff_path(center_id)

    def history_path(self, center_id: str) -> Path:
        return self.center_store.signoff_history_path(center_id)

    def signoff_binding_path(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "signoff-binding-summary.json"

    def change_request_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "change-requests"

    def archive_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "archive"

    def archive_zip_path(self, center_id: str) -> Path:
        return self.archive_dir(center_id) / "unified-command-center-archive.zip"

    def archive_manifest_path(self, center_id: str) -> Path:
        return self.archive_dir(center_id) / "manifest.json"

    def archive_verification_report_path(self, center_id: str) -> Path:
        return self.archive_dir(center_id) / "unified-command-center-archive-verification-report.json"

    def read_signoff(self, center_id: str) -> DomainDocument:
        path = self.signoff_path(center_id)
        if not path.exists():
            raise UnifiedCommandCenterSignoffNotFoundError(f"Unified Command Center signoff not found: {center_id}.")
        return read_json(path)

    def signoff(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.center_store.ensure_mutable(center_id)
            source = self._source_state(center_id, require_ready=True)
            verification = source["verification"]
            if verification.get("status") != "passed":
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center verification must pass before signoff.")
            if source["report"].get("status") != "ready":
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center report must be ready before signoff.")
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_signoff",
                    "center_id": center_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "release-owner", 120),
                    "signed_at": now,
                    "role": _bounded(payload.get("role") or "release_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Unified Command Center approved for handoff.", 1000),
                    "source_hash": source["report"].get("source_hash"),
                    "ucc_zip_sha256": source["ucc_zip_sha256"],
                    "ucc_zip_size_bytes": source["ucc_zip_size_bytes"],
                    "ucc_manifest_hash": verification.get("manifest_hash"),
                    "verification_hash": verification.get("integrity_hash"),
                    "report_hash": source["report"].get("integrity_hash"),
                    "readiness_hash": source["readiness"].get("integrity_hash"),
                    "inventory_hash": source["inventory"].get("integrity_hash"),
                    "center_hash": source["center"].get("integrity_hash"),
                    "summary": source["report"].get("summary", {}),
                    "tool": {"name": "MusicForge Unified Command Center Signoff", "version": __version__},
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(center_id), signoff)
            signoff_event = self._append_history(
                center_id,
                {
                    "event_type": "ucc_signoff_created",
                    "created_at": now,
                    "center_id": center_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "report_hash": signoff.get("report_hash"),
                    "readiness_hash": signoff.get("readiness_hash"),
                    "inventory_hash": signoff.get("inventory_hash"),
                    "verification_hash": signoff.get("verification_hash"),
                    "ucc_zip_sha256": signoff.get("ucc_zip_sha256"),
                    "ucc_manifest_hash": signoff.get("ucc_manifest_hash"),
                },
            )
            write_json(self.signoff_binding_path(center_id), self._signoff_binding_summary(center_id, signoff, signoff_event))
            center = self.center_store.read_center(center_id)
            center["status"] = "signed"
            center["signed_at"] = now
            center["signoff_hash"] = signoff.get("integrity_hash")
            center["integrity_hash"] = _integrity_hash(center)
            write_json(self.center_store.center_path(center_id), center)
            return signoff

    def create_change_request(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            signoff = self.read_signoff(center_id)
            if signoff.get("status") != "signed":
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center must be signed before creating a Change Request.")
            cr_id = self._next_change_request_id(center_id)
            now = now_iso()
            cr = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_change_request",
                    "change_request_id": cr_id,
                    "center_id": center_id,
                    "status": "draft",
                    "created_at": now,
                    "created_by": _bounded(payload.get("created_by") or payload.get("requested_by") or "developer", 120),
                    "reason": _bounded(payload.get("reason"), 1000),
                    "risk": _bounded(payload.get("risk") or "medium", 40),
                    "requested_actions": ["reset_unified_command_center_signoff"],
                    "source": {
                        "center_id": center_id,
                        "signoff_hash": signoff.get("integrity_hash"),
                        "ucc_zip_sha256": signoff.get("ucc_zip_sha256"),
                        "verification_hash": signoff.get("verification_hash"),
                    },
                    "approval": {},
                    "applied": {"applied_at": None, "reset_event_hash": None},
                }
            )
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(center_id) / f"{cr_id}.json", cr)
            return cr

    def approve_change_request(self, center_id: str, change_request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            cr = self._read_change_request(center_id, change_request_id)
            if cr.get("status") not in {"draft", "submitted"}:
                raise UnifiedCommandCenterSignoffStateError("Only draft or submitted Change Requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_by": _bounded(payload.get("approved_by") or payload.get("reviewer") or "reviewer", 120),
                "approved_at": now_iso(),
                "reason": _bounded(payload.get("reason") or cr.get("reason"), 1000),
            }
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(center_id) / f"{change_request_id}.json", cr)
            return cr

    def reset_signoff(self, center_id: str, change_request_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            signoff = self.read_signoff(center_id)
            cr = self._read_change_request(center_id, change_request_id)
            if not _integrity_ok(cr):
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center Change Request integrity failed.")
            if cr.get("status") != "approved":
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center reset requires an approved Change Request.")
            if cr.get("applied", {}).get("applied_at"):
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center Change Request has already been applied.")
            if cr.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise UnifiedCommandCenterSignoffStateError("Unified Command Center Change Request does not match current signoff.")
            event = self._append_history(
                center_id,
                {
                    "event_type": "ucc_signoff_reset",
                    "created_at": now_iso(),
                    "center_id": center_id,
                    "change_request_id": change_request_id,
                    "reason": _bounded(payload.get("reason") or cr.get("reason"), 1000),
                    "previous_signoff_hash": signoff.get("integrity_hash"),
                    "previous_status": "signed",
                },
            )
            self.signoff_path(center_id).unlink(missing_ok=True)
            self.signoff_binding_path(center_id).unlink(missing_ok=True)
            center = self.center_store.read_center(center_id)
            center["status"] = "draft"
            center.pop("signed_at", None)
            center.pop("signoff_hash", None)
            center["updated_at"] = now_iso()
            center["integrity_hash"] = _integrity_hash(center)
            write_json(self.center_store.center_path(center_id), center)
            cr["status"] = "applied"
            cr["applied"] = {"applied_at": event.get("created_at"), "reset_event_hash": event.get("event_hash")}
            cr["integrity_hash"] = _integrity_hash(cr)
            write_json(self.change_request_dir(center_id) / f"{change_request_id}.json", cr)
            return {"status": "reset", "center": center, "change_request": cr, "reset_event": event}

    def export_archive(self, center_id: str) -> DomainDocument:
        with self.lock:
            source = self._source_state(center_id, require_ready=True)
            self._ensure_archive_mutable(center_id, source["signoff"].get("integrity_hash"))
            archive_dir = self.archive_dir(center_id)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            files: list[ImplementationDocument] = []

            def write_entry(rel: str, payload: DomainDocument | str) -> None:
                path = archive_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("center.json", source["center"])
            write_entry("command-center-report.json", source["report"])
            write_entry("readiness-matrix.json", source["readiness"])
            write_entry("evidence-inventory.json", source["inventory"])
            write_entry("verification-report.json", source["verification"])
            write_entry("signoff.json", source["signoff"])
            write_entry("signoff-binding-summary.json", source["signoff_binding"])
            write_entry("signoff-history.jsonl", self.history_path(center_id).read_text(encoding="utf-8") if self.history_path(center_id).exists() else "")
            write_entry("change-requests.json", self._change_request_index(center_id))
            write_entry("README.txt", _archive_readme(source))
            manifest = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_ARCHIVE_SCHEMA_VERSION,
                    "package_type": UNIFIED_COMMAND_CENTER_ARCHIVE_PACKAGE_TYPE,
                    "center_id": center_id,
                    "created_at": now_iso(),
                    "source": {
                        "center_hash": source["center"].get("integrity_hash"),
                        "report_hash": source["report"].get("integrity_hash"),
                        "readiness_hash": source["readiness"].get("integrity_hash"),
                        "inventory_hash": source["inventory"].get("integrity_hash"),
                        "verification_hash": source["verification"].get("integrity_hash"),
                        "signoff_hash": source["signoff"].get("integrity_hash"),
                        "signoff_binding_hash": source["signoff_binding"].get("integrity_hash"),
                        "ucc_zip_sha256": source["ucc_zip_sha256"],
                        "ucc_manifest_hash": source["verification"].get("manifest_hash"),
                    },
                    "summary": source["report"].get("summary", {}),
                    "files": files,
                    "zip": {},
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(center_id), manifest)
            return manifest

    def build_archive_zip(self, center_id: str) -> DomainDocument:
        with self.lock:
            source = self._source_state(center_id, require_ready=True)
            self._ensure_archive_mutable(center_id, source["signoff"].get("integrity_hash"))
            self.export_archive(center_id)
            archive_dir = self.archive_dir(center_id)
            zip_path = self.archive_zip_path(center_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
            manifest = read_json(self.archive_manifest_path(center_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(center_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            self._append_history(
                center_id,
                {
                    "event_type": "ucc_archive_built",
                    "created_at": now_iso(),
                    "center_id": center_id,
                    "signoff_hash": source["signoff"].get("integrity_hash"),
                    "archive_zip_sha256": final_sha,
                    "archive_manifest_hash": manifest.get("integrity_hash"),
                },
            )
            return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_archive(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        report = verify_unified_command_center_archive_package(
            self.archive_zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current_ucc=bool(payload.get("require_current_ucc", True)),
            command_center_zip_path=payload.get("command_center_zip") or payload.get("command_center_zip_path") or self.center_store.zip_path(center_id),
            command_center_verification_report_path=payload.get("command_center_verification_report") or payload.get("command_center_verification_report_path") or self.center_store.verification_report_path(center_id),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or self.signoff_binding_path(center_id),
        )
        write_unified_command_center_archive_verification_report(report, self.archive_verification_report_path(center_id))
        return report

    def gate(self, center_id: str, *, required: bool = True, archive_zip_path: Path | str | None = None, archive_verification_report_path: Path | str | None = None) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        archive_zip = Path(archive_zip_path) if archive_zip_path else self.archive_zip_path(center_id)
        verification_path = Path(archive_verification_report_path) if archive_verification_report_path else self.archive_verification_report_path(center_id)
        if not archive_zip.exists():
            return _gate_failed("Unified Command Center Archive ZIP is missing.")
        if not verification_path.exists():
            return _gate_failed("Unified Command Center Archive verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_command_center_archive_package(
                archive_zip,
                strict=True,
                require_signed=True,
                require_current_ucc=True,
                command_center_zip_path=self.center_store.zip_path(center_id),
                command_center_verification_report_path=self.center_store.verification_report_path(center_id),
                signoff_binding_path=self.signoff_binding_path(center_id),
            )
            if external.get("integrity_hash") != _integrity_hash(external):
                return _gate_failed("Unified Command Center Archive verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Archive verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Archive verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Signoff Archive gate passed.", "archive_zip_sha256": runtime.get("zip_sha256"), "archive_verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _source_state(self, center_id: str, *, require_ready: bool) -> ImplementationDocument:
        center = self.center_store.read_center(center_id)
        signoff = read_json(self.signoff_path(center_id)) if self.signoff_path(center_id).exists() else {}
        if signoff.get("status") != "signed" and self.center_store.latest_signoff_state(center_id).get("status") == "signed":
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center signoff file is missing but history shows a signed state.")
        signoff_binding: ImplementationDocument = {}
        if signoff.get("status") == "signed":
            signoff_binding = self._read_signoff_binding(center_id, signoff)
        report = read_json(self.center_store.report_path(center_id))
        readiness = read_json(self.center_store.readiness_path(center_id))
        inventory = read_json(self.center_store.inventory_path(center_id))
        if not self.center_store.zip_path(center_id).exists():
            self.center_store.build_zip(center_id)
        verification_path = self.center_store.verification_report_path(center_id)
        if not verification_path.exists():
            verification = self.center_store.verify_zip(center_id, strict=True, require_ready=require_ready)
        else:
            verification = read_json(verification_path)
        if verification.get("integrity_hash") != _integrity_hash(verification):
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center verification integrity failed.")
        if verification.get("zip_sha256") != _sha256_path(self.center_store.zip_path(center_id)):
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center verification does not match current ZIP.")
        return {
            "center": center,
            "signoff": signoff,
            "signoff_binding": signoff_binding,
            "report": report,
            "readiness": readiness,
            "inventory": inventory,
            "verification": verification,
            "ucc_zip_sha256": _sha256_path(self.center_store.zip_path(center_id)),
            "ucc_zip_size_bytes": self.center_store.zip_path(center_id).stat().st_size if self.center_store.zip_path(center_id).exists() else None,
        }

    def _ensure_archive_mutable(self, center_id: str, signoff_hash: str | None) -> None:
        if not signoff_hash:
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center must be signed before archive.")
        if self._archive_built_for_signoff(center_id, str(signoff_hash)):
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center Archive already exists for this signoff. Reset signoff before rebuilding archive.")

    def _archive_built_for_signoff(self, center_id: str, signoff_hash: str) -> bool:
        built = False
        for event in self.center_store.read_signoff_history(center_id):
            if event.get("event_type") == "ucc_archive_built" and event.get("signoff_hash") == signoff_hash:
                built = True
            if event.get("event_type") == "ucc_signoff_reset" and event.get("previous_signoff_hash") == signoff_hash:
                built = False
        return built

    def _append_history(self, center_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        history = self.center_store.read_signoff_history(center_id)
        previous = str(history[-1].get("event_hash") or "") if history else ""
        event = sanitize_metadata({**payload, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        path = self.history_path(center_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _next_change_request_id(self, center_id: str) -> str:
        self.change_request_dir(center_id).mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.change_request_dir(center_id).glob("ucccr-*.json"):
            try:
                max_seen = max(max_seen, int(path.stem.split("-")[-1]))
            except ValueError:
                continue
        return f"ucccr-{max_seen + 1:06d}"

    def _read_change_request(self, center_id: str, change_request_id: str) -> ImplementationDocument:
        path = self.change_request_dir(center_id) / f"{_safe_id(change_request_id)}.json"
        if not path.exists():
            raise UnifiedCommandCenterSignoffNotFoundError(f"Unified Command Center Change Request not found: {change_request_id}.")
        return read_json(path)

    def _change_request_index(self, center_id: str) -> ImplementationDocument:
        rows = []
        for path in sorted(self.change_request_dir(center_id).glob("ucccr-*.json")):
            try:
                rows.append(read_json(path))
            except (OSError, ValueError):
                continue
        doc = {"schema_version": UNIFIED_COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_change_request_index", "center_id": center_id, "items": rows}
        doc["integrity_hash"] = _integrity_hash(doc)
        return doc

    def _read_signoff_binding(self, center_id: str, signoff: ImplementationDocument) -> ImplementationDocument:
        path = self.signoff_binding_path(center_id)
        if not path.exists():
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center signoff binding summary is missing.")
        binding = read_json(path)
        if not _integrity_ok(binding):
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center signoff binding integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterSignoffStateError("Unified Command Center signoff binding does not match current signoff.")
        return binding

    def _signoff_binding_summary(self, center_id: str, signoff: ImplementationDocument, signoff_event: ImplementationDocument) -> ImplementationDocument:
        binding = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_SIGNOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_signoff_binding",
                "center_id": center_id,
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "history_event_hash": signoff_event.get("event_hash"),
                "history_event_payload_hash": signoff_event.get("payload_hash"),
                "history_previous_event_hash": signoff_event.get("previous_event_hash") or "",
                "source": {
                    "source_hash": signoff.get("source_hash"),
                    "center_hash": signoff.get("center_hash"),
                    "report_hash": signoff.get("report_hash"),
                    "readiness_hash": signoff.get("readiness_hash"),
                    "inventory_hash": signoff.get("inventory_hash"),
                    "verification_hash": signoff.get("verification_hash"),
                    "ucc_zip_sha256": signoff.get("ucc_zip_sha256"),
                    "ucc_zip_size_bytes": signoff.get("ucc_zip_size_bytes"),
                    "ucc_manifest_hash": signoff.get("ucc_manifest_hash"),
                },
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding


def _archive_readme(source: ImplementationDocument) -> str:
    signoff = source.get("signoff", {})
    return "\n".join(
        [
            "MusicForge Unified Command Center Archive",
            "",
            f"Center: {signoff.get('center_id')}",
            f"Signed by: {signoff.get('signed_by')}",
            f"Signed at: {signoff.get('signed_at')}",
            "",
            "Verify this archive with verify-unified-command-center-archive-package.",
            "",
        ]
    )


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


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
