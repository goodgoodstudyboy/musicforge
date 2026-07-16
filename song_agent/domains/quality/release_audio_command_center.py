from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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

    def refresh(self, release_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            docs = self._build_documents(release_id, evidence or {})
            self._write_docs(release_id, docs)
            return docs["report"]

    def read_report(self, release_id: str) -> dict[str, Any]:
        if not self.report_path(release_id).exists():
            raise ReleaseAudioCommandCenterNotFoundError(f"Release Audio Command Center report not found for {release_id}.")
        return read_json(self.report_path(release_id))

    def read_inventory(self, release_id: str) -> dict[str, Any]:
        if not self.inventory_path(release_id).exists():
            raise ReleaseAudioCommandCenterNotFoundError(f"Release Audio Command Center inventory not found for {release_id}.")
        return read_json(self.inventory_path(release_id))

    def create_runbook(self, release_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            docs = self._build_documents(release_id, evidence or {})
            self._write_docs(release_id, docs)
            return docs["runbook"]

    def run_safe(self, release_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            docs = self._ensure_docs(release_id, evidence or {})
            results: list[dict[str, Any]] = []
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

    def export_package(self, release_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def build_zip(self, release_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_zip(self, release_id: str, *, evidence: dict[str, Any] | None = None, strict: bool = True, require_ready: bool = False) -> dict[str, Any]:
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
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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


def evidence_to_verifier_kwargs(evidence: dict[str, Any]) -> dict[str, Any]:
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
    kwargs: dict[str, Any] = {}
    for key, (zip_arg, report_arg) in mapping.items():
        paths = evidence.get(key) if isinstance(evidence.get(key), dict) else {}
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
    raw = evidence.get("requirements") if isinstance(evidence.get("requirements"), dict) else {}
    return {key: bool(raw.get(key, True)) for key in COMPONENT_KEYS}


def _component_row(component: dict[str, str], evidence: ImplementationDocument, *, verifier_kwargs: ImplementationDocument) -> ImplementationDocument:
    key = component["key"]
    paths = evidence.get(key) if isinstance(evidence.get(key), dict) else {}
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
    zip_arg, report_arg = mapping[key]
    zip_path = paths.get("zip") or paths.get("zip_path") or verifier_kwargs.get(zip_arg)
    report_path = paths.get("verification_report") or paths.get("verification_report_path") or verifier_kwargs.get(report_arg)
    status = "missing"
    readiness = "missing"
    message = "Evidence ZIP or verification report is missing."
    fingerprint = {
        "component_key": key,
        "artifact_type": component["artifact"],
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": None,
        "runtime_verification_status": None,
        "runtime_manifest_hash": None,
        "runtime_failed_count": 0,
        "runtime_blockers": [],
    }
    verification_summary: dict[str, Any] = {"component_key": key, "status": "missing"}
    runtime_summary: dict[str, Any] = {"component_key": key, "status": "missing", "blockers": []}
    if zip_path and report_path:
        runtime = verify_release_audio_command_center_component(key, zip_path, report_path, **verifier_kwargs)
        fingerprint.update(runtime.get("fingerprint") or {})
        fingerprint["artifact_type"] = component["artifact"]
        external_report = runtime.get("external_report") if isinstance(runtime.get("external_report"), dict) else {}
        verification_summary = _public_verification_summary(key, external_report) if external_report else verification_summary
        runtime_summary = {
            "component_key": key,
            "status": runtime.get("status"),
            "readiness": runtime.get("readiness"),
            "blockers": runtime.get("blockers", []),
            "runtime_report": runtime.get("runtime_report", {}),
        }
        runtime_summary["integrity_hash"] = _integrity_hash(runtime_summary)
        if runtime.get("status") == "passed":
            status = "ready"
            readiness = "ready"
            message = "Evidence is current and runtime verification passed."
        else:
            status = "blocked"
            readiness = str(runtime.get("readiness") or "blocked")
            message = _message_for_readiness(readiness, component["label"])
    fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    if "integrity_hash" not in verification_summary:
        verification_summary["integrity_hash"] = _integrity_hash(verification_summary)
    return sanitize_metadata(
        {
            "component_key": key,
            "artifact_type": component["artifact"],
            "label": component["label"],
            "status": status,
            "readiness": readiness,
            "message": message,
            "fingerprint": fingerprint,
            "verification_summary": verification_summary,
            "runtime_summary": runtime_summary,
        }
    )


def _public_verification_summary(component_key: str, report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    public = {
        "component_key": component_key,
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "original_integrity_hash": report.get("integrity_hash"),
        "summary": {key: value for key, value in summary.items() if key not in {"zip_path"}},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return sanitize_metadata(public)


def _sync_report_document_hashes(docs: ImplementationDocument) -> None:
    report = docs.get("report") if isinstance(docs.get("report"), dict) else {}
    report["document_hashes"] = {
        "command_center": docs.get("command_center", {}).get("integrity_hash"),
        "evidence_inventory": docs.get("inventory", {}).get("integrity_hash"),
        "readiness_matrix": docs.get("readiness", {}).get("integrity_hash"),
        "gap_plan": docs.get("gap_plan", {}).get("integrity_hash"),
        "runbook": docs.get("runbook", {}).get("integrity_hash"),
        "runbook_results": docs.get("runbook_results", {}).get("integrity_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)


def _readiness_row(row: ImplementationDocument) -> ImplementationDocument:
    status = "ready" if row.get("status") == "ready" else str(row.get("readiness") or "blocked") if row.get("required") else "not_required"
    return {
        "component_key": row.get("component_key"),
        "artifact_type": row.get("artifact_type"),
        "label": row.get("label"),
        "required": bool(row.get("required")),
        "readiness": status,
        "message": row.get("message"),
        "verification_status": (row.get("fingerprint") or {}).get("verification_status"),
        "runtime_verification_status": (row.get("fingerprint") or {}).get("runtime_verification_status"),
        "runtime_blockers": (row.get("fingerprint") or {}).get("runtime_blockers", []),
        "next_action": "none" if status == "ready" else f"refresh_or_verify_{row.get('component_key')}",
    }


def _gap_row(row: ImplementationDocument) -> ImplementationDocument:
    priority = {
        "runtime_failed": 10,
        "stale": 20,
        "verification_failed": 30,
        "missing": 40,
        "manual_required": 50,
        "blocked": 60,
    }.get(str(row.get("readiness") or ""), 90)
    gap = {
        "gap_id": f"acc-gap-{row.get('component_key')}",
        "component_key": row.get("component_key"),
        "severity": "blocking",
        "priority": priority,
        "readiness": row.get("readiness"),
        "reason": row.get("message") or "Required evidence is not ready.",
        "recommended_action": _recommended_action_for_readiness(row),
    }
    gap["integrity_hash"] = _integrity_hash(gap)
    return gap


def _message_for_readiness(readiness: str, label: str) -> str:
    if readiness == "missing":
        return f"{label} ZIP or verification report is missing."
    if readiness == "stale":
        return f"{label} verification report does not match current evidence."
    if readiness == "verification_failed":
        return f"{label} verification report is failed or invalid."
    if readiness == "runtime_failed":
        return f"{label} runtime verification failed."
    if readiness == "manual_required":
        return f"{label} requires manual follow-up."
    return f"{label} is blocked."


def _recommended_action_for_readiness(row: ImplementationDocument) -> str:
    readiness = str(row.get("readiness") or "")
    key = str(row.get("component_key") or "component")
    if readiness == "runtime_failed":
        return f"rerun_runtime_verifier_for_{key}"
    if readiness == "stale":
        return f"rebuild_and_reverify_{key}"
    if readiness == "verification_failed":
        return f"inspect_verification_report_for_{key}"
    if readiness == "missing":
        return f"generate_and_verify_{key}"
    if readiness == "manual_required":
        return f"complete_manual_action_for_{key}"
    return row.get("next_action") or f"refresh_or_verify_{key}"


def _build_runbook(release_id: str, source_hash: str, gaps: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    actions = [
        {"item_id": "acc-safe-001", "action_type": "refresh_command_center", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-002", "action_type": "export_command_center", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-003", "action_type": "build_command_center_zip", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-004", "action_type": "verify_command_center_zip", "execution_mode": "safe_auto", "requires_manual": False},
    ]
    for index, gap in enumerate(gaps, start=1):
        actions.append(
            {
                "item_id": f"acc-manual-{index:03d}",
                "action_type": str(gap.get("recommended_action") or "resolve_gap"),
                "execution_mode": "manual_required",
                "requires_manual": True,
                "source_gap_id": gap.get("gap_id"),
            }
        )
    runbook = {
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "package_type": "release_audio_command_center_runbook",
        "release_id": release_id,
        "created_at": created_at,
        "source_hash": source_hash,
        "actions": actions,
        "summary": {
            "action_count": len(actions),
            "safe_action_count": sum(1 for row in actions if row.get("execution_mode") == "safe_auto"),
            "manual_required_count": sum(1 for row in actions if row.get("execution_mode") == "manual_required"),
        },
    }
    runbook["integrity_hash"] = _integrity_hash(runbook)
    return runbook


def _empty_runbook_results(release_id: str, *, source_hash: str | None = None) -> ImplementationDocument:
    doc = {
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "package_type": "release_audio_command_center_runbook_results",
        "release_id": release_id,
        "created_at": now_iso(),
        "source_hash": source_hash,
        "results": [],
        "summary": {"completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0},
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readme(report: ImplementationDocument) -> str:
    return "\n".join(
        [
            "MusicForge Release Audio Command Center",
            "",
            f"Release: {report.get('release_id')}",
            f"Status: {report.get('status')}",
            f"Readiness: {report.get('readiness')}",
            "",
            "This package summarizes audio release evidence. Verify it with verify-release-audio-command-center-package and external evidence ZIP/report files.",
            "",
        ]
    )


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


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


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}
