# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_command_center_verifier import RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE as RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE, verify_release_audio_command_center_component as verify_release_audio_command_center_component, verify_release_audio_command_center_package as verify_release_audio_command_center_package, write_release_audio_command_center_verification_report as write_release_audio_command_center_verification_report
from song_agent.domains.quality.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore as ReleaseAudioQualityActionQueueSignoffStore
from song_agent.domains.quality.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore as ReleaseAudioQualityActionQueueStore
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore as ReleaseAudioQualityObservatoryStore
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash


RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION = 1
RELEASE_AUDIO_COMMAND_CENTER_REPORT_PACKAGE_TYPE = "release_audio_command_center_report"

COMPONENTS: tuple[dict[str, str], ...] = (
    {"key": "certification", "label": "Release Audio Certification", "artifact": "release_audio_certification"},
    {"key": "timeline", "label": "Release Audio Timeline", "artifact": "release_audio_timeline"},
    {"key": "regression", "label": "Release Audio Regression Guard", "artifact": "release_audio_regression"},
    {"key": "baseline_governance", "label": "Release Audio Baseline Governance", "artifact": "release_audio_baseline_governance"},
    {"key": "regression_response", "label": "Release Audio Regression Response", "artifact": "release_audio_regression_response"},
    {"key": "observatory", "label": "Release Audio Quality Observatory", "artifact": "release_audio_quality_observatory"},
    {"key": "action_queue", "label": "Release Audio Quality Action Queue", "artifact": "release_audio_quality_action_queue"},
    {"key": "action_queue_signoff", "label": "Release Audio Quality Action Queue Signoff", "artifact": "release_audio_quality_action_queue_signoff"},
)
COMPONENT_KEYS = tuple(row["key"] for row in COMPONENTS)


class ReleaseAudioCommandCenterError(ValueError):
    pass


class ReleaseAudioCommandCenterNotFoundError(ReleaseAudioCommandCenterError):
    pass


class ReleaseAudioCommandCenterStateError(ReleaseAudioCommandCenterError):
    pass


class ReleaseAudioCommandCenterStore:
    def __init__(
        self,
        *,
        release_store: ReleaseStore | None = None,
        observatory_store: ReleaseAudioQualityObservatoryStore | None = None,
        action_queue_store: ReleaseAudioQualityActionQueueStore | None = None,
        action_signoff_store: ReleaseAudioQualityActionQueueSignoffStore | None = None,
    ) -> None:
        self.release_store = release_store or ReleaseStore()
        self.observatory_store = observatory_store or ReleaseAudioQualityObservatoryStore(release_store=self.release_store)
        self.action_queue_store = action_queue_store or ReleaseAudioQualityActionQueueStore(release_store=self.release_store, observatory_store=self.observatory_store)
        self.action_signoff_store = action_signoff_store or ReleaseAudioQualityActionQueueSignoffStore(queue_store=self.action_queue_store, release_store=self.release_store)
        self.lock = threading.RLock()

    def center_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-command-center"

    def export_dir(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "export"

    def zip_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "release-audio-command-center.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "release-audio-command-center-verification-report.json"

    def command_center_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "command-center.json"

    def report_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "command-center-report.json"

    def inventory_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "evidence-inventory.json"

    def readiness_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "readiness-matrix.json"

    def gap_plan_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "gap-plan.json"

    def runbook_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "runbook.json"

    def runbook_results_path(self, release_id: str) -> Path:
        return self.center_dir(release_id) / "runbook-results.json"

    def refresh(self, release_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            docs = self._build_documents(release_id, evidence or {})
            self._write_docs(release_id, docs)
            return docs["report"]

    def read_report(self, release_id: str) -> DomainDocument:
        if not self.report_path(release_id).exists():
            raise ReleaseAudioCommandCenterNotFoundError(f"Release Audio Command Center report not found for {release_id}.")
        return read_json(self.report_path(release_id))

    def read_inventory(self, release_id: str) -> DomainDocument:
        if not self.inventory_path(release_id).exists():
            raise ReleaseAudioCommandCenterNotFoundError(f"Release Audio Command Center inventory not found for {release_id}.")
        return read_json(self.inventory_path(release_id))

    def create_runbook(self, release_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            docs = self._build_documents(release_id, evidence or {})
            self._write_docs(release_id, docs)
            return docs["runbook"]

    def run_safe(self, release_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            docs = self._ensure_docs(release_id, evidence or {})
            results: list[ImplementationDocument] = []
            for item in docs["runbook"].get("actions", []):
                if not isinstance(item, dict):
                    continue
                action_type = str(item.get("action_type") or "")
                item_id = str(item.get("item_id") or "")
                if item.get("execution_mode") != "safe_auto":
                    results.append({"item_id": item_id, "action_type": action_type, "status": "manual_required", "reason": "Action requires human decision."})
                    continue
                try:
                    if action_type == "refresh_command_center":
                        docs = self._build_documents(release_id, evidence or {})
                        self._write_docs(release_id, docs)
                        results.append({"item_id": item_id, "action_type": action_type, "status": "completed"})
                    elif action_type == "export_command_center":
                        exported = self.export_package(release_id, evidence or {})
                        results.append({"item_id": item_id, "action_type": action_type, "status": "completed", "export_status": exported.get("status")})
                    elif action_type == "build_command_center_zip":
                        zipped = self.build_zip(release_id, evidence or {})
                        results.append({"item_id": item_id, "action_type": action_type, "status": "completed", "zip_sha256": zipped.get("zip_sha256")})
                    elif action_type == "verify_command_center_zip":
                        report = self.verify_zip(release_id, evidence=evidence or {}, strict=True, require_ready=False)
                        results.append({"item_id": item_id, "action_type": action_type, "status": "completed" if report.get("status") != "failed" else "failed", "verification_status": report.get("status")})
                    else:
                        results.append({"item_id": item_id, "action_type": action_type, "status": "blocked", "reason": "Unknown safe action."})
                except Exception as exc:
                    results.append({"item_id": item_id, "action_type": action_type, "status": "failed", "reason": sanitize_sensitive_text(str(exc))})
            result_doc = {
                "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
                "package_type": "release_audio_command_center_runbook_results",
                "release_id": release_id,
                "created_at": now_iso(),
                "results": results,
                "summary": {
                    "completed_count": sum(1 for row in results if row.get("status") == "completed"),
                    "failed_count": sum(1 for row in results if row.get("status") == "failed"),
                    "blocked_count": sum(1 for row in results if row.get("status") == "blocked"),
                    "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required"),
                },
            }
            result_doc["integrity_hash"] = _integrity_hash(result_doc)
            write_json(self.runbook_results_path(release_id), result_doc)
            return result_doc

    def export_package(self, release_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            docs = self._ensure_docs(release_id, evidence or {})
            _sync_report_document_hashes(docs)
            export_dir = self.export_dir(release_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            for rel, doc_key in (
                ("command-center.json", "command_center"),
                ("command-center-report.json", "report"),
                ("evidence-inventory.json", "inventory"),
                ("readiness-matrix.json", "readiness"),
                ("gap-plan.json", "gap_plan"),
                ("runbook.json", "runbook"),
                ("runbook-results.json", "runbook_results"),
            ):
                write_json(export_dir / rel, docs[doc_key])
            (export_dir / "README.txt").write_text(_readme(docs["report"]), encoding="utf-8")
            (export_dir / "evidence-fingerprints").mkdir(parents=True, exist_ok=True)
            (export_dir / "verification-summaries").mkdir(parents=True, exist_ok=True)
            for component in docs["inventory"].get("components", []):
                key = str(component.get("component_key") or "")
                if not key:
                    continue
                write_json(export_dir / "evidence-fingerprints" / f"{key}.json", component.get("fingerprint") or {})
                write_json(export_dir / "verification-summaries" / f"{key}-verification.json", component.get("verification_summary") or {})
            manifest = self._build_manifest(release_id, export_dir, docs)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["report"].get("status"), "release_id": release_id, "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            exported = self.export_package(release_id, evidence or {})
            export_dir = Path(exported["export_dir"])
            zip_path = self.zip_path(release_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {
                "filename": zip_path.name,
                "sha256": _sha256_path(zip_path),
                "size_bytes": zip_path.stat().st_size,
                "entry_count": len(entries),
                "entries": entries,
            }
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported["status"], "release_id": release_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, *, evidence: DomainDocument | None = None, strict: bool = True, require_ready: bool = False) -> DomainDocument:
        report = verify_release_audio_command_center_package(
            self.zip_path(release_id),
            strict=strict,
            require_ready=require_ready,
            **evidence_to_verifier_kwargs(evidence or {}),
        )
        write_release_audio_command_center_verification_report(report, self.verification_report_path(release_id))
        return report

    def gate(
        self,
        release_id: str,
        *,
        required: bool,
        command_center_zip_path: Path | str | None = None,
        command_center_verification_report_path: Path | str | None = None,
        evidence: DomainDocument | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(command_center_zip_path) if command_center_zip_path else self.zip_path(release_id)
        report_path = Path(command_center_verification_report_path) if command_center_verification_report_path else self.verification_report_path(release_id)
        if not zip_path.exists():
            return _gate_failed("Release Audio Command Center ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Release Audio Command Center verification report is missing.")
        try:
            external_report = read_json(report_path)
            runtime = verify_release_audio_command_center_package(
                zip_path,
                strict=True,
                require_ready=True,
                **evidence_to_verifier_kwargs(evidence or {}),
            )
            if external_report.get("integrity_hash") != _integrity_hash(external_report):
                return _gate_failed("Release Audio Command Center verification integrity failed.", verification=external_report)
            if external_report.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Release Audio Command Center verification failed.", verification=runtime)
            if external_report.get("zip_sha256") != _sha256_path(zip_path) or external_report.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Release Audio Command Center verification does not match current ZIP.", verification=runtime)
            release_ids = {str(item) for item in (runtime.get("summary") or {}).get("release_ids", []) if str(item)}
            if release_id not in release_ids:
                return _gate_failed("Release Audio Command Center package does not cover this Release.", verification=runtime)
            return {
                "status": "passed",
                "hard_block": False,
                "message": "Release Audio Command Center gate passed.",
                "zip_sha256": runtime.get("zip_sha256"),
                "manifest_hash": runtime.get("manifest_hash"),
                "verification_hash": external_report.get("integrity_hash"),
                "summary": runtime.get("summary", {}),
            }
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _ensure_docs(self, release_id: str, evidence: ImplementationDocument) -> ImplementationDocument:
        if not self.report_path(release_id).exists():
            return self._build_documents(release_id, evidence)
        return {
            "command_center": read_json(self.command_center_path(release_id)),
            "report": read_json(self.report_path(release_id)),
            "inventory": read_json(self.inventory_path(release_id)),
            "readiness": read_json(self.readiness_path(release_id)),
            "gap_plan": read_json(self.gap_plan_path(release_id)),
            "runbook": read_json(self.runbook_path(release_id)),
            "runbook_results": read_json(self.runbook_results_path(release_id)) if self.runbook_results_path(release_id).exists() else _empty_runbook_results(release_id),
        }

    def _write_docs(self, release_id: str, docs: dict[str, ImplementationDocument]) -> None:
        center_dir = self.center_dir(release_id)
        center_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.command_center_path(release_id), docs["command_center"])
        write_json(self.report_path(release_id), docs["report"])
        write_json(self.inventory_path(release_id), docs["inventory"])
        write_json(self.readiness_path(release_id), docs["readiness"])
        write_json(self.gap_plan_path(release_id), docs["gap_plan"])
        write_json(self.runbook_path(release_id), docs["runbook"])
        if not self.runbook_results_path(release_id).exists():
            write_json(self.runbook_results_path(release_id), docs["runbook_results"])

    def _build_documents(self, release_id: str, evidence: ImplementationDocument) -> dict[str, ImplementationDocument]:
        release = self.release_store.get_release(release_id)
        release_doc = release.to_dict()
        requirements = _requirements(evidence)
        component_rows = []
        verifier_kwargs = evidence_to_verifier_kwargs(evidence)
        for component in COMPONENTS:
            row = _component_row(component, evidence, verifier_kwargs=verifier_kwargs)
            row["required"] = bool(requirements.get(component["key"], True))
            component_rows.append(row)
        required_rows = [row for row in component_rows if row.get("required")]
        blocking_rows = [row for row in required_rows if row.get("status") != "ready"]
        readiness_status = "ready" if not blocking_rows else "blocked"
        source = {
            "release_id": release_id,
            "release_track_hash": stable_hash(release_doc.get("tracks", [])),
            "requirements": requirements,
            "component_fingerprints": {row["component_key"]: row.get("fingerprint") for row in component_rows},
            "component_verification_hashes": {row["component_key"]: (row.get("verification_summary") or {}).get("integrity_hash") for row in component_rows},
            "component_runtime_hashes": {row["component_key"]: (row.get("runtime_summary") or {}).get("integrity_hash") for row in component_rows},
        }
        source_hash = stable_hash(source)
        now = now_iso()
        inventory = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": "release_audio_command_center_evidence_inventory",
            "release_id": release_id,
            "created_at": now,
            "source_hash": source_hash,
            "components": component_rows,
            "summary": {
                "component_count": len(component_rows),
                "required_count": len(required_rows),
                "ready_count": sum(1 for row in required_rows if row.get("status") == "ready"),
                "blocked_count": len(blocking_rows),
            },
        }
        inventory["integrity_hash"] = _integrity_hash(inventory)
        readiness_rows = [_readiness_row(row) for row in component_rows]
        readiness = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": "release_audio_command_center_readiness_matrix",
            "release_id": release_id,
            "created_at": now,
            "source_hash": source_hash,
            "status": readiness_status,
            "rows": readiness_rows,
            "summary": {
                "ready_count": sum(1 for row in readiness_rows if row.get("readiness") == "ready" and row.get("required")),
                "blocked_count": sum(1 for row in readiness_rows if row.get("readiness") != "ready" and row.get("required")),
                "warning_count": sum(1 for row in readiness_rows if row.get("readiness") == "warning"),
            },
        }
        readiness["integrity_hash"] = _integrity_hash(readiness)
        gaps = sorted(
            [_gap_row(row) for row in readiness_rows if row.get("required") and row.get("readiness") != "ready"],
            key=lambda row: (int(row.get("priority") or 999), str(row.get("component_key") or "")),
        )
        gap_plan = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": "release_audio_command_center_gap_plan",
            "release_id": release_id,
            "created_at": now,
            "source_hash": source_hash,
            "status": "passed" if not gaps else "blocked",
            "gaps": gaps,
            "summary": {"gap_count": len(gaps), "blocking_gap_count": len(gaps)},
        }
        gap_plan["integrity_hash"] = _integrity_hash(gap_plan)
        runbook = _build_runbook(release_id, source_hash, gaps, now)
        runbook_results = _empty_runbook_results(release_id, source_hash=source_hash)
        command_center = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": "release_audio_command_center",
            "release_id": release_id,
            "created_at": now,
            "updated_at": now,
            "source_hash": source_hash,
            "requirements": requirements,
            "summary": {
                "readiness_status": readiness_status,
                "component_count": len(component_rows),
                "required_count": len(required_rows),
                "blocking_gap_count": len(gaps),
            },
        }
        command_center["integrity_hash"] = _integrity_hash(command_center)
        report = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": RELEASE_AUDIO_COMMAND_CENTER_REPORT_PACKAGE_TYPE,
            "release_id": release_id,
            "created_at": now,
            "source": source,
            "source_hash": source_hash,
            "status": "passed" if readiness_status == "ready" else "failed",
            "readiness": readiness_status,
            "summary": command_center["summary"],
            "document_hashes": {
                "command_center": command_center["integrity_hash"],
                "evidence_inventory": inventory["integrity_hash"],
                "readiness_matrix": readiness["integrity_hash"],
                "gap_plan": gap_plan["integrity_hash"],
                "runbook": runbook["integrity_hash"],
                "runbook_results": runbook_results["integrity_hash"],
            },
            "blockers": [gap["gap_id"] for gap in gaps],
            "warnings": [],
        }
        report["integrity_hash"] = _integrity_hash(report)
        return {
            "command_center": command_center,
            "report": report,
            "inventory": inventory,
            "readiness": readiness,
            "gap_plan": gap_plan,
            "runbook": runbook,
            "runbook_results": runbook_results,
        }

    def _build_manifest(self, release_id: str, export_dir: Path, docs: ImplementationDocument) -> ImplementationDocument:
        manifest = {
            "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE,
            "release_id": release_id,
            "created_at": now_iso(),
            "source_hash": docs["report"].get("source_hash"),
            "status": docs["report"].get("status"),
            "readiness": docs["report"].get("readiness"),
            "report_hash": docs["report"].get("integrity_hash"),
            "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
            "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
            "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
            "runbook_hash": docs["runbook"].get("integrity_hash"),
            "runbook_results_hash": docs["runbook_results"].get("integrity_hash"),
            "component_keys": list(COMPONENT_KEYS),
            "files": [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"],
        }
        manifest["integrity_hash"] = _integrity_hash(manifest)
        return manifest


def evidence_to_verifier_kwargs(evidence: DomainDocument) -> DomainDocument:
    mapping = {
        "certification": ("certification_zip_path", "certification_verification_report_path"),
        "timeline": ("timeline_zip_path", "timeline_verification_report_path"),
        "regression": ("regression_zip_path", "regression_verification_report_path"),
        "baseline_governance": ("baseline_registry_zip_path", "baseline_registry_verification_report_path"),
        "regression_response": ("regression_response_zip_path", "regression_response_verification_report_path"),
        "observatory": ("observatory_zip_path", "observatory_verification_report_path"),
        "action_queue": ("action_queue_zip_path", "action_queue_verification_report_path"),
        "action_queue_signoff": ("action_queue_signoff_archive_path", "action_queue_signoff_verification_report_path"),
    }
    kwargs: ImplementationDocument = {}
    for key, (zip_arg, report_arg) in mapping.items():
        paths = _as_document(evidence.get(key))
        zip_value = paths.get("zip") or paths.get("zip_path") or evidence.get(zip_arg) or evidence.get(zip_arg.replace("_path", ""))
        report_value = paths.get("verification_report") or paths.get("verification_report_path") or evidence.get(report_arg) or evidence.get(report_arg.replace("_path", ""))
        if zip_value:
            kwargs[zip_arg] = zip_value
        if report_value:
            kwargs[report_arg] = report_value
    if evidence.get("evidence_root"):
        kwargs["evidence_root"] = evidence.get("evidence_root")
    return kwargs


def _requirements(evidence: ImplementationDocument) -> dict[str, bool]:
    raw = _as_document(evidence.get("requirements"))
    return {key: bool(raw.get(key, True)) for key in COMPONENT_KEYS}


from song_agent.domains.quality import v142_racc_readiness as _v142_racc_readiness
from song_agent.domains.quality.v142_racc_readiness import _component_row as _component_row, _public_verification_summary as _public_verification_summary, _sync_report_document_hashes as _sync_report_document_hashes, _readiness_row as _readiness_row, _gap_row as _gap_row, _message_for_readiness as _message_for_readiness, _recommended_action_for_readiness as _recommended_action_for_readiness, _build_runbook as _build_runbook, _empty_runbook_results as _empty_runbook_results, _readme as _readme, _gate_failed as _gate_failed, _integrity_hash as _integrity_hash, _sha256_path as _sha256_path, _file_record as _file_record

_v142_racc_readiness.bind_globals(globals())
