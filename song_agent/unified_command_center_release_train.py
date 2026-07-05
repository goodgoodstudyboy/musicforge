from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import ReleaseStore, stable_hash
from song_agent.unified_command_center_release_train_verifier import (
    EXPECTED_EVIDENCE_PACKAGE_TYPES,
    REQUIRED_ENTRIES,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE,
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
    verify_unified_command_center_release_train_package,
    write_unified_command_center_release_train_verification_report,
)


DEFAULT_REQUIRED_EVIDENCE = [
    "ucc",
    "ucc_archive",
    "handoff",
    "continuous_review",
    "evidence_review",
    "reviewer_decision_board",
]


class UnifiedCommandCenterReleaseTrainError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainNotFoundError(UnifiedCommandCenterReleaseTrainError):
    pass


class UnifiedCommandCenterReleaseTrainStateError(UnifiedCommandCenterReleaseTrainError):
    pass


class UnifiedCommandCenterReleaseTrainStore:
    def __init__(self, root: Path | str | None = None, *, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else self.release_store.root.parent / "unified-command-trains"
        self.lock = threading.RLock()

    def train_dir(self, train_id: str) -> Path:
        return self.root / _safe_id(train_id)

    def train_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train.json"

    def source_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-source.json"

    def items_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-items.json"

    def inventory_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "evidence-inventory.json"

    def readiness_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "readiness-matrix.json"

    def dependency_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "dependency-graph.json"

    def wave_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "wave-plan.json"

    def report_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "go-no-go-report.json"

    def runbook_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "safe-runbook.json"

    def runbook_result_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "safe-runbook-result.json"

    def signoff_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-signoff.json"

    def signoff_binding_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-signoff-binding-summary.json"

    def history_path(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "train-history.jsonl"

    def archive_dir(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "archive"

    def archive_manifest_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "manifest.json"

    def zip_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "unified-command-center-release-train.zip"

    def verification_report_path(self, train_id: str) -> Path:
        return self.archive_dir(train_id) / "unified-command-center-release-train-verification-report.json"

    def archive_history_dir(self, train_id: str) -> Path:
        return self.train_dir(train_id) / "archive-history"

    def archive_history_signoff_dir(self, train_id: str, signoff_hash: str) -> Path:
        safe_hash = _safe_id(signoff_hash)
        return self.archive_history_dir(train_id) / (safe_hash[:16] or "unknown")

    def create_train(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            train_id = _safe_id(str(payload.get("train_id") or self._next_train_id()))
            if self.train_path(train_id).exists():
                raise UnifiedCommandCenterReleaseTrainStateError(f"Unified Command Center Release Train already exists: {train_id}")
            now = now_iso()
            train = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_record",
                    "train_id": train_id,
                    "name": _bounded(payload.get("name") or "Unified Command Center Release Train", 200),
                    "profile": _bounded(payload.get("profile") or "ga", 80),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                    "policy": {
                        "required_evidence": _required_evidence(payload.get("required_evidence")),
                        "allow_duplicate_center": bool(payload.get("allow_duplicate_center", False)),
                    },
                }
            )
            train["integrity_hash"] = _integrity_hash(train)
            self.train_dir(train_id).mkdir(parents=True, exist_ok=True)
            write_json(self.train_path(train_id), train)
            self._write_items(train_id, [])
            if payload.get("items"):
                for item in payload.get("items") or []:
                    self.add_item(train_id, dict(item))
            return self.read_train(train_id)

    def list_trains(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        rows = []
        for path in sorted(self.root.glob("uct-*")):
            train_path = path / "train.json"
            if train_path.exists():
                rows.append(read_json(train_path))
        return rows

    def read_train(self, train_id: str) -> dict[str, Any]:
        if not self.train_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainNotFoundError(f"Unified Command Center Release Train not found: {train_id}")
        return read_json(self.train_path(train_id))

    def read_docs(self, train_id: str) -> dict[str, Any]:
        if not self.report_path(train_id).exists():
            raise UnifiedCommandCenterReleaseTrainNotFoundError(f"Unified Command Center Release Train report not found: {train_id}")
        return {
            "train": self.read_train(train_id),
            "source": read_json(self.source_path(train_id)),
            "items": read_json(self.items_path(train_id)),
            "inventory": read_json(self.inventory_path(train_id)),
            "readiness": read_json(self.readiness_path(train_id)),
            "dependency": read_json(self.dependency_path(train_id)),
            "wave": read_json(self.wave_path(train_id)),
            "report": read_json(self.report_path(train_id)),
            "runbook": read_json(self.runbook_path(train_id)),
            "runbook_result": read_json(self.runbook_result_path(train_id)),
        }

    def add_item(self, train_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(train_id)
            train = self.read_train(train_id)
            items_doc = self._read_items(train_id)
            rows = list(items_doc.get("items") or [])
            center_id = _safe_id(str(payload.get("center_id") or ""))
            if not center_id:
                raise UnifiedCommandCenterReleaseTrainStateError("center_id is required.")
            allow_duplicate = bool(payload.get("allow_duplicate_center", train.get("policy", {}).get("allow_duplicate_center", False)))
            if not allow_duplicate and any(row.get("center_id") == center_id for row in rows):
                raise UnifiedCommandCenterReleaseTrainStateError("Duplicate center_id requires allow_duplicate_center=true.")
            item_id = _safe_id(str(payload.get("item_id") or f"item-{len(rows) + 1:03d}"))
            if any(row.get("item_id") == item_id for row in rows):
                raise UnifiedCommandCenterReleaseTrainStateError(f"Duplicate train item_id: {item_id}")
            row = sanitize_metadata(
                {
                    "item_id": item_id,
                    "center_id": center_id,
                    "label": _bounded(payload.get("label") or center_id, 200),
                    "wave": int(payload.get("wave") or len(rows) + 1),
                    "depends_on": [_safe_id(str(item)) for item in payload.get("depends_on", []) if str(item)],
                    "required_evidence": _required_evidence(payload.get("required_evidence") or train.get("policy", {}).get("required_evidence")),
                    "status": "pending",
                }
            )
            rows.append(row)
            self._write_items(train_id, rows)
            train["updated_at"] = now_iso()
            train["integrity_hash"] = _integrity_hash(train)
            write_json(self.train_path(train_id), train)
            return row

    def refresh(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._build_documents(train_id, payload or {})
            self._write_docs(train_id, docs)
            return docs["report"]

    def run_safe(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._ensure_docs(train_id, payload or {})
            current_source = self._build_documents(train_id, payload or {})["source"]["source_hash"]
            if current_source != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train source is stale. Refresh before running safe actions.")
            results = []
            for item in docs["runbook"].get("items", []):
                action = str(item.get("action") or "")
                item_id = str(item.get("item_id") or "")
                if action == "release_train.refresh":
                    refreshed = self._build_documents(train_id, payload or {})
                    self._write_docs(train_id, refreshed)
                    results.append({"item_id": item_id, "action": action, "status": "completed"})
                elif action in {"release_train.export", "release_train.zip", "release_train.verify"}:
                    results.append({"item_id": item_id, "action": action, "status": "manual_required", "reason": "Archive actions require signed Release Train."})
                else:
                    results.append({"item_id": item_id, "action": action, "status": "skipped_unsupported", "reason": "Safe action must be executed by the owning UCC module."})
            result_doc = _runbook_result(train_id, docs["source"].get("source_hash"), results)
            write_json(self.runbook_result_path(train_id), result_doc)
            return result_doc

    def signoff(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(train_id)
            docs = self._build_documents(train_id, payload)
            if docs["report"].get("status") != "go":
                self._write_docs(train_id, docs)
                raise UnifiedCommandCenterReleaseTrainStateError("Unified Command Center Release Train must be GO before signoff.")
            self._write_docs(train_id, docs)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_release_train_signoff",
                    "train_id": train_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "release-train-owner", 120),
                    "role": _bounded(payload.get("role") or "release_train_owner", 80),
                    "reason": _bounded(payload.get("reason") or "Unified Command Center Release Train approved for release.", 1000),
                    "signed_at": now,
                    "source_hash": docs["source"].get("source_hash"),
                    "train_hash": docs["train"].get("integrity_hash"),
                    "items_hash": docs["items"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                    "wave_plan_hash": docs["wave"].get("integrity_hash"),
                    "go_no_go_report_hash": docs["report"].get("integrity_hash"),
                    "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
                    "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                    "summary": docs["report"].get("summary", {}),
                    "tool": {"name": "MusicForge Unified Command Center Release Train Signoff", "version": __version__},
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(train_id), signoff)
            event = self._append_history(
                train_id,
                {
                    "event_type": "ucc_release_train_signoff_created",
                    "created_at": now,
                    "train_id": train_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "go_no_go_report_hash": signoff.get("go_no_go_report_hash"),
                    "evidence_inventory_hash": signoff.get("evidence_inventory_hash"),
                },
            )
            write_json(self.signoff_binding_path(train_id), self._signoff_binding_summary(train_id, signoff, event))
            train = docs["train"]
            train["status"] = "signed"
            train["signed_at"] = now
            train["signoff_hash"] = signoff.get("integrity_hash")
            train["updated_at"] = now
            train["integrity_hash"] = _integrity_hash(train)
            write_json(self.train_path(train_id), train)
            return signoff

    def export_archive(self, train_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._signed_docs_for_export(train_id)
            signoff_hash = docs["signoff"].get("integrity_hash")
            if self._archive_exported_for_signoff(train_id, str(signoff_hash)):
                if self.archive_manifest_path(train_id).exists():
                    return read_json(self.archive_manifest_path(train_id))
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train archive was already exported for this signoff. Create a new train before rebuilding.")
            archive_dir = self.archive_dir(train_id)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = archive_dir / rel
                if isinstance(payload, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, rel))

            write_entry("train.json", docs["train"])
            write_entry("train-source.json", docs["source"])
            write_entry("train-items.json", docs["items"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("dependency-graph.json", docs["dependency"])
            write_entry("wave-plan.json", docs["wave"])
            write_entry("go-no-go-report.json", docs["report"])
            write_entry("safe-runbook.json", docs["runbook"])
            write_entry("safe-runbook-result.json", docs["runbook_result"])
            write_entry("train-signoff.json", docs["signoff"])
            write_entry("train-signoff-binding-summary.json", docs["signoff_binding"])
            write_entry("train-history.jsonl", self.history_path(train_id).read_text(encoding="utf-8") if self.history_path(train_id).exists() else "")
            write_entry("REVIEWER_GUIDE.md", _reviewer_guide(docs))
            write_entry("README.txt", _readme(docs))
            manifest = _manifest_document(train_id, docs, files)
            write_json(self.archive_manifest_path(train_id), manifest)
            self._append_history(train_id, {"event_type": "ucc_release_train_archive_exported", "created_at": now_iso(), "train_id": train_id, "signoff_hash": signoff_hash, "archive_manifest_hash": manifest.get("integrity_hash")})
            return manifest

    def build_zip(self, train_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._signed_docs_for_export(train_id)
            signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
            if self._archive_built_for_signoff(train_id, signoff_hash):
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train archive ZIP already exists for this signoff. Create a new train before rebuilding.")
            if not self.archive_manifest_path(train_id).exists():
                self.export_archive(train_id)
            archive_dir = self.archive_dir(train_id)
            zip_path = self.zip_path(train_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.archive_manifest_path(train_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(archive_dir).as_posix()) for path in sorted(archive_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.archive_manifest_path(train_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(archive_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(archive_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            self._append_history(train_id, {"event_type": "ucc_release_train_archive_built", "created_at": now_iso(), "train_id": train_id, "signoff_hash": signoff_hash, "archive_zip_sha256": final_sha, "archive_manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "train_id": train_id, "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_archive(self, train_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_command_center_release_train_package(
            self.zip_path(train_id),
            strict=bool(payload.get("strict", True)),
            require_go=bool(payload.get("require_go", True)),
            require_signed=bool(payload.get("require_signed", True)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"),
            signoff_binding_path=payload.get("signoff_binding") or payload.get("signoff_binding_path") or payload.get("unified_command_center_release_train_signoff_binding") or self.signoff_binding_path(train_id),
        )
        write_unified_command_center_release_train_verification_report(report, self.verification_report_path(train_id))
        return report

    def gate(
        self,
        train_id: str,
        *,
        required: bool = True,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        external_evidence_manifest_path: Path | str | None = None,
        signoff_binding_path: Path | str | None = None,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        state = self.latest_signoff_state(train_id)
        if state.get("status") != "signed":
            return _gate_failed("Unified Command Center Release Train is not currently signed.", signoff_state=state)
        open_change = self._open_approved_change_request(train_id)
        if open_change:
            return _gate_failed("Unified Command Center Release Train has an approved unapplied Change Request.", change_request=open_change)
        archive_zip = Path(archive_zip_path) if archive_zip_path else self.zip_path(train_id)
        verification_path = Path(verification_report_path) if verification_report_path else self.verification_report_path(train_id)
        if not archive_zip.exists():
            return _gate_failed("Unified Command Center Release Train archive ZIP is missing.")
        if not verification_path.exists():
            return _gate_failed("Unified Command Center Release Train verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_command_center_release_train_package(
                archive_zip,
                strict=True,
                require_go=True,
                require_signed=True,
                external_evidence_manifest_path=external_evidence_manifest_path,
                signoff_binding_path=signoff_binding_path or self.signoff_binding_path(train_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Command Center Release Train verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center Release Train verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center Release Train verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Release Train gate passed.", "archive_zip_sha256": runtime.get("zip_sha256"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, train_id: str) -> None:
        state = self.latest_signoff_state(train_id)
        if state.get("status") == "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Unified Command Center Release Train is signed. Create a new train for changes.")

    def latest_signoff_state(self, train_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        for event in self.read_history(train_id):
            if event.get("event_type") == "ucc_release_train_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "ucc_release_train_signoff_reset":
                latest = {
                    "status": "reset",
                    "signoff_hash": event.get("previous_signoff_hash") or event.get("signoff_hash"),
                    "change_request_id": event.get("change_request_id"),
                    "event": event,
                }
        if latest:
            return latest
        if self.signoff_path(train_id).exists():
            signoff = read_json(self.signoff_path(train_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, train_id: str) -> list[dict[str, Any]]:
        path = self.history_path(train_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def _build_documents(self, train_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        train = self.read_train(train_id)
        items_doc = self._read_items(train_id)
        evidence_manifest = _read_external_manifest(payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path"), payload)
        evidence_rows, item_rows = _build_evidence_rows(items_doc, evidence_manifest)
        now = now_iso()
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_source",
                "train_id": train_id,
                "created_at": now,
                "train_hash": train.get("integrity_hash"),
                "items_hash": items_doc.get("integrity_hash"),
                "external_evidence_manifest_hash": evidence_manifest.get("integrity_hash"),
                "external_evidence_item_count": len(evidence_manifest.get("items", [])),
                "evidence_fingerprints": [{key: row.get(key) for key in ("item_id", "center_id", "evidence_type", "zip_sha256", "manifest_hash", "verification_report_hash", "verification_status")} for row in evidence_rows],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        inventory = _inventory_document(train_id, source["source_hash"], evidence_rows, now)
        readiness = _readiness_document(train_id, source["source_hash"], item_rows, evidence_rows, now)
        dependency = _dependency_document(train_id, source["source_hash"], item_rows, now)
        wave = _wave_document(train_id, source["source_hash"], item_rows, now)
        report = _go_no_go_report(train_id, source["source_hash"], train, readiness, dependency, inventory, now)
        runbook = _runbook_document(train_id, source["source_hash"], readiness, report, now)
        runbook_result = _runbook_result(train_id, source["source_hash"], [])
        return {"train": train, "source": source, "items": items_doc, "inventory": inventory, "readiness": readiness, "dependency": dependency, "wave": wave, "report": report, "runbook": runbook, "runbook_result": runbook_result}

    def _ensure_docs(self, train_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.report_path(train_id).exists():
            return self.read_docs(train_id)
        docs = self._build_documents(train_id, payload)
        self._write_docs(train_id, docs)
        return docs

    def _write_docs(self, train_id: str, docs: dict[str, Any]) -> None:
        for key, path_fn in (
            ("source", self.source_path),
            ("items", self.items_path),
            ("inventory", self.inventory_path),
            ("readiness", self.readiness_path),
            ("dependency", self.dependency_path),
            ("wave", self.wave_path),
            ("report", self.report_path),
            ("runbook", self.runbook_path),
            ("runbook_result", self.runbook_result_path),
        ):
            write_json(path_fn(train_id), docs[key])
        train = docs["train"]
        train["source_hash"] = docs["source"].get("source_hash")
        train["status"] = "ready" if docs["report"].get("status") == "go" else "no_go"
        train["updated_at"] = now_iso()
        train["integrity_hash"] = _integrity_hash(train)
        write_json(self.train_path(train_id), train)
        docs["train"] = train

    def _read_items(self, train_id: str) -> dict[str, Any]:
        if not self.items_path(train_id).exists():
            self._write_items(train_id, [])
        return read_json(self.items_path(train_id))

    def _write_items(self, train_id: str, rows: list[dict[str, Any]]) -> None:
        doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_items", "train_id": train_id, "items": rows, "summary": {"item_count": len(rows)}})
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(self.items_path(train_id), doc)

    def _signed_docs_for_export(self, train_id: str) -> dict[str, Any]:
        train = self.read_train(train_id)
        signoff_path = self.signoff_path(train_id)
        state = self.latest_signoff_state(train_id)
        if state.get("status") != "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train is not currently signed.")
        if not signoff_path.exists() and self.latest_signoff_state(train_id).get("status") == "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff file is missing but history shows a signed state.")
        if not signoff_path.exists():
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train must be signed before archive export.")
        signoff = read_json(signoff_path)
        if not _integrity_ok(signoff) or signoff.get("status") != "signed":
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff integrity failed.")
        if state.get("signoff_hash") and state.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff file does not match latest signed history state.")
        binding = self._read_signoff_binding(train_id, signoff)
        docs = self.read_docs(train_id)
        checks = {
            "items_hash": docs["items"].get("integrity_hash"),
            "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
            "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
            "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
            "wave_plan_hash": docs["wave"].get("integrity_hash"),
            "go_no_go_report_hash": docs["report"].get("integrity_hash"),
            "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
            "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
        }
        for key, value in checks.items():
            if signoff.get(key) != value:
                raise UnifiedCommandCenterReleaseTrainStateError("Release Train signed documents no longer match signoff.")
        docs["signoff"] = signoff
        docs["signoff_binding"] = binding
        return docs

    def _read_signoff_binding(self, train_id: str, signoff: dict[str, Any]) -> dict[str, Any]:
        path = self.signoff_binding_path(train_id)
        if not path.exists():
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding summary is missing.")
        binding = read_json(path)
        if not _integrity_ok(binding):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterReleaseTrainStateError("Release Train signoff binding does not match current signoff.")
        return binding

    def _append_history(self, train_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        history = self.read_history(train_id)
        previous = str(history[-1].get("event_hash") or "") if history else ""
        event = sanitize_metadata({**payload, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        path = self.history_path(train_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _signoff_binding_summary(self, train_id: str, signoff: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        binding = sanitize_metadata(
            {
                "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_release_train_signoff_binding",
                "train_id": train_id,
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "source": {
                    "source_hash": signoff.get("source_hash"),
                    "train_hash": signoff.get("train_hash"),
                    "items_hash": signoff.get("items_hash"),
                    "evidence_inventory_hash": signoff.get("evidence_inventory_hash"),
                    "readiness_matrix_hash": signoff.get("readiness_matrix_hash"),
                    "dependency_graph_hash": signoff.get("dependency_graph_hash"),
                    "wave_plan_hash": signoff.get("wave_plan_hash"),
                    "go_no_go_report_hash": signoff.get("go_no_go_report_hash"),
                    "safe_runbook_hash": signoff.get("safe_runbook_hash"),
                    "safe_runbook_result_hash": signoff.get("safe_runbook_result_hash"),
                },
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _archive_exported_for_signoff(self, train_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "ucc_release_train_archive_exported" and event.get("signoff_hash") == signoff_hash for event in self.read_history(train_id))

    def _archive_built_for_signoff(self, train_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "ucc_release_train_archive_built" and event.get("signoff_hash") == signoff_hash for event in self.read_history(train_id))

    def _open_approved_change_request(self, train_id: str) -> dict[str, Any] | None:
        change_dir = self.train_dir(train_id) / "change-control" / "change-requests"
        if not change_dir.exists():
            return None
        for path in sorted(change_dir.glob("*/train-change-request.json")):
            try:
                request = read_json(path)
            except Exception:
                continue
            if request.get("status") == "approved" and not request.get("applied_at"):
                return {
                    "change_request_id": request.get("change_request_id"),
                    "status": request.get("status"),
                    "reason": request.get("reason"),
                }
        return None

    def _next_train_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob("uct-*/train.json"):
            try:
                max_seen = max(max_seen, int(path.parent.name.split("-")[-1]))
            except ValueError:
                continue
        return f"uct-{max_seen + 1:06d}"


def write_external_evidence_manifest(path: Path | str, *, train_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "train_id": train_id,
        "created_at": now_iso(),
        "items": items,
        "summary": {"item_count": len(items)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    write_json(Path(path), manifest)
    return manifest


def _read_external_manifest(path: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if path:
        return read_json(Path(path))
    rows = payload.get("external_evidence") or payload.get("external_evidence_items") or []
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "train_id": payload.get("train_id"),
        "created_at": now_iso(),
        "items": rows,
        "summary": {"item_count": len(rows)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _build_evidence_rows(items_doc: dict[str, Any], external_manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    external_by_key = {_evidence_key(row): row for row in external_manifest.get("items", []) if isinstance(row, dict)}
    evidence_rows: list[dict[str, Any]] = []
    item_rows: list[dict[str, Any]] = []
    for item in items_doc.get("items", []):
        required = _required_evidence(item.get("required_evidence"))
        blockers: list[str] = []
        passed_count = 0
        for evidence_type in required:
            key = _evidence_key({"item_id": item.get("item_id"), "center_id": item.get("center_id"), "evidence_type": evidence_type})
            external = external_by_key.get(key, {})
            evidence_row = _evidence_row(item, evidence_type, external)
            if evidence_row["status"] == "passed":
                passed_count += 1
            else:
                blockers.extend(evidence_row.get("blockers", []))
            evidence_rows.append(evidence_row)
        status = "ready" if passed_count == len(required) and not blockers else "blocked"
        item_rows.append({**item, "status": status, "required_evidence_count": len(required), "passed_evidence_count": passed_count, "blockers": sorted(set(blockers))})
    return evidence_rows, item_rows


def _evidence_row(item: dict[str, Any], evidence_type: str, external: dict[str, Any]) -> dict[str, Any]:
    row = {
        "item_id": item.get("item_id"),
        "center_id": item.get("center_id"),
        "evidence_type": evidence_type,
        "package_type": EXPECTED_EVIDENCE_PACKAGE_TYPES.get(evidence_type),
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": "missing",
        "status": "missing",
        "blockers": [],
    }
    zip_path = Path(str(external.get("zip_path") or ""))
    report_path = Path(str(external.get("verification_report_path") or ""))
    if not zip_path.exists() or not report_path.exists():
        row["blockers"].append("external_evidence_missing")
        return row
    try:
        report = read_json(report_path)
        row.update(
            {
                "zip_sha256": _sha256_path(zip_path),
                "zip_size_bytes": zip_path.stat().st_size,
                "manifest_hash": _zip_manifest_hash(zip_path),
                "verification_report_hash": _integrity_hash(report),
                "verification_status": report.get("status"),
            }
        )
        expected_type = EXPECTED_EVIDENCE_PACKAGE_TYPES.get(evidence_type)
        if report.get("package_type") != expected_type:
            row["blockers"].append("wrong_package_type")
        if not _integrity_ok(report):
            row["blockers"].append("verification_integrity_failed")
        if report.get("status") != "passed":
            row["blockers"].append("verification_not_passed")
        if row["zip_sha256"] != (report.get("zip_sha256") or report.get("summary", {}).get("zip_sha256")):
            row["blockers"].append("zip_sha256_mismatch")
        if row["manifest_hash"] != (report.get("manifest_hash") or report.get("summary", {}).get("manifest_hash")):
            row["blockers"].append("manifest_hash_mismatch")
    except Exception as exc:
        row["blockers"].append(sanitize_sensitive_text(str(exc)))
    row["status"] = "passed" if not row["blockers"] else "failed"
    return sanitize_metadata(row)


def _inventory_document(train_id: str, source_hash: str, evidence_rows: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_evidence_inventory",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "items": evidence_rows,
            "summary": {
                "evidence_count": len(evidence_rows),
                "passed_count": sum(1 for row in evidence_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in evidence_rows if row.get("status") != "passed"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_document(train_id: str, source_hash: str, items: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    overall = "go" if items and all(row.get("status") == "ready" for row in items) else "no_go"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_readiness_matrix",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "overall_status": overall,
            "items": items,
            "summary": {
                "item_count": len(items),
                "ready_count": sum(1 for row in items if row.get("status") == "ready"),
                "blocked_count": sum(1 for row in items if row.get("status") != "ready"),
                "evidence_count": len(evidence_rows),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _dependency_document(train_id: str, source_hash: str, items: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    item_status = {str(row.get("item_id")): str(row.get("status")) for row in items}
    edges = []
    for item in items:
        for dependency in item.get("depends_on", []):
            edges.append({"from_item_id": dependency, "to_item_id": item.get("item_id")})
    cycle = _has_cycle(edges)
    blocked = [edge for edge in edges if item_status.get(str(edge.get("from_item_id"))) != "ready"]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_dependency_graph",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "nodes": [{"item_id": row.get("item_id"), "center_id": row.get("center_id"), "status": row.get("status")} for row in items],
            "edges": edges,
            "summary": {"cycle_detected": cycle, "blocked_dependency_count": len(blocked), "blocked_dependencies": blocked},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _wave_document(train_id: str, source_hash: str, items: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    waves: dict[str, list[str]] = {}
    for row in items:
        waves.setdefault(str(row.get("wave") or 1), []).append(str(row.get("item_id")))
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_wave_plan", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "waves": waves, "summary": {"wave_count": len(waves)}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _go_no_go_report(train_id: str, source_hash: str, train: dict[str, Any], readiness: dict[str, Any], dependency: dict[str, Any], inventory: dict[str, Any], created_at: str) -> dict[str, Any]:
    blockers = []
    if readiness.get("overall_status") != "go":
        blockers.append("readiness:no_go")
    if dependency.get("summary", {}).get("cycle_detected"):
        blockers.append("dependency:cycle")
    if int(dependency.get("summary", {}).get("blocked_dependency_count") or 0):
        blockers.append("dependency:blocked")
    status = "go" if not blockers else "no_go"
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_go_no_go_report", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "status": status, "blockers": blockers, "summary": {"train_name": train.get("name"), "item_count": readiness.get("summary", {}).get("item_count"), "evidence_failed_count": inventory.get("summary", {}).get("failed_count"), "dependency_blocker_count": dependency.get("summary", {}).get("blocked_dependency_count")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_document(train_id: str, source_hash: str, readiness: dict[str, Any], report: dict[str, Any], created_at: str) -> dict[str, Any]:
    items = [{"item_id": "train-refresh", "action": "release_train.refresh", "safe": True, "status": "pending"}]
    for row in readiness.get("items", []):
        if row.get("status") != "ready":
            items.append({"item_id": f"manual-{row.get('item_id')}", "action": "ucc.remediate", "safe": False, "status": "manual_required", "center_id": row.get("center_id")})
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_safe_runbook", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "items": items, "summary": {"action_count": len(items), "safe_action_count": sum(1 for item in items if item.get("safe")), "manual_action_count": sum(1 for item in items if not item.get("safe")), "go_no_go_status": report.get("status")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_result(train_id: str, source_hash: str | None, results: list[dict[str, Any]]) -> dict[str, Any]:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_safe_runbook_result", "train_id": train_id, "created_at": now_iso(), "source_hash": source_hash, "results": results, "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required"), "skipped_unsupported_count": sum(1 for row in results if row.get("status") == "skipped_unsupported")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(train_id: str, docs: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE,
            "train_id": train_id,
            "created_at": now_iso(),
            "source_hash": docs["source"].get("source_hash"),
            "source": {
                "train_hash": docs["train"].get("integrity_hash"),
                "source_hash": docs["source"].get("integrity_hash"),
                "items_hash": docs["items"].get("integrity_hash"),
                "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "wave_plan_hash": docs["wave"].get("integrity_hash"),
                "go_no_go_report_hash": docs["report"].get("integrity_hash"),
                "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
                "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                "train_signoff_hash": docs["signoff"].get("integrity_hash"),
                "train_signoff_binding_hash": docs["signoff_binding"].get("integrity_hash"),
            },
            "summary": docs["report"].get("summary", {}),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _reviewer_guide(docs: dict[str, Any]) -> str:
    return "\n".join(["# MusicForge UCC Release Train", "", f"Train: {docs['train'].get('train_id')}", f"Status: {docs['report'].get('status')}", "", "Verify with verify-unified-command-center-release-train-package and the external evidence manifest.", ""])


def _readme(docs: dict[str, Any]) -> str:
    return "\n".join(["MusicForge Unified Command Center Release Train", "", f"Train: {docs['train'].get('train_id')}", f"Go/No-Go: {docs['report'].get('status')}", ""])


def _required_evidence(value: Any) -> list[str]:
    if not value:
        return list(DEFAULT_REQUIRED_EVIDENCE)
    rows = [str(item) for item in value if str(item)] if isinstance(value, list) else [str(value)]
    return [item for item in rows if item in EXPECTED_EVIDENCE_PACKAGE_TYPES]


def _evidence_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "center_id", "evidence_type"))


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
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


def _zip_manifest_hash(path: Path | str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            return manifest.get("integrity_hash")
    except Exception:
        return None


def _has_cycle(edges: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = {}
    for row in edges:
        source = str(row.get("from_item_id") or "")
        target = str(row.get("to_item_id") or "")
        if not source or not target:
            continue
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, graph.get(target, []))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))
