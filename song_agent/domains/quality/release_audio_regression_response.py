from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.quality.release_audio_regression import ReleaseAudioRegressionStore
from song_agent.domains.quality.release_audio_regression_verifier import verify_release_audio_regression_package
from song_agent.domains.quality.release_audio_regression_response_verifier import RELEASE_AUDIO_REGRESSION_RESPONSE_PACKAGE_TYPE, RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION, verify_release_audio_regression_response_package, write_release_audio_regression_response_verification_report
from song_agent.domains.delivery.releases import ReleaseStore, stable_hash


class ReleaseAudioRegressionResponseError(ValueError):
    pass


class ReleaseAudioRegressionResponseNotFoundError(ReleaseAudioRegressionResponseError):
    pass


class ReleaseAudioRegressionResponseStateError(ReleaseAudioRegressionResponseError):
    pass


class ReleaseAudioRegressionResponseValidationError(ReleaseAudioRegressionResponseError):
    pass


class ReleaseAudioRegressionResponseStore:
    def __init__(self, *, release_store: ReleaseStore | None = None, regression_store: ReleaseAudioRegressionStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.regression_store = regression_store or ReleaseAudioRegressionStore(release_store=self.release_store)
        self.lock = threading.RLock()

    def response_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "audio-regression-response"

    def plan_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "response-plan.json"

    def action_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "action-items.json"

    def waiver_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "waiver-register.json"

    def closeout_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "recheck-closeout.json"

    def binding_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "regression-binding.json"

    def signoff_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "response-signoff.json"

    def history_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "response-signoff-history.jsonl"

    def export_dir(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "export"

    def zip_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "release-audio-regression-response.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.response_dir(release_id) / "verification-report.json"

    def read_plan(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.plan_path(release_id).exists():
            if default is not None:
                return default
            raise ReleaseAudioRegressionResponseNotFoundError(f"Release Audio Regression Response not found: {release_id}.")
        return read_json(self.plan_path(release_id))

    def create_plan(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionResponseStateError("Signed Release Audio Regression Response cannot be recreated.")
            docs = self._build_documents(release_id, payload=payload, closeout_override=None)
            self._write_documents(release_id, docs)
            return docs["plan"]

    def add_waiver(self, release_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionResponseStateError("Signed Release Audio Regression Response cannot be changed.")
            docs = self._current_documents_or_build(release_id)
            action_id = str(payload.get("action_id") or "")
            reason = _bounded(payload.get("reason") or "", 1000)
            action = next((row for row in docs["actions"].get("actions", []) if row.get("action_id") == action_id), None)
            if not action:
                raise ReleaseAudioRegressionResponseValidationError("Unknown response action_id.")
            severity = str(action.get("severity") or "warning").lower()
            if severity in {"high", "critical", "blocking"}:
                raise ReleaseAudioRegressionResponseStateError("High and critical regression response actions cannot be waived.")
            if len(reason) < 4:
                raise ReleaseAudioRegressionResponseValidationError("Waiver reason is required.")
            waiver = sanitize_metadata(
                {
                    "waiver_id": f"rarw-{len(docs['waivers'].get('waivers', [])) + 1:06d}",
                    "action_id": action_id,
                    "severity": severity,
                    "reason": reason,
                    "waived_by": _bounded(payload.get("waived_by") or payload.get("reviewer") or "audio-lead", 120),
                    "created_at": now_iso(),
                }
            )
            docs["waivers"]["waivers"].append(waiver)
            self._refresh_derived_docs(docs)
            self._write_documents(release_id, docs)
            return docs["waivers"]

    def run_safe_actions(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionResponseStateError("Signed Release Audio Regression Response cannot run actions.")
            docs = self._current_documents_or_build(release_id)
            results = []
            for action in docs["actions"].get("actions", []):
                if action.get("execution_mode") == "draft_only":
                    action["status"] = "draft_created"
                    action["result"] = {"draft_only": True, "message": "Draft action prepared; manual execution required."}
                    results.append({"action_id": action.get("action_id"), "status": "draft_created"})
                else:
                    results.append({"action_id": action.get("action_id"), "status": "manual_required"})
            self._refresh_derived_docs(docs)
            self._write_documents(release_id, docs)
            return {"status": "completed_with_manual_actions", "results": results, "actions": docs["actions"]}

    def closeout(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionResponseStateError("Signed Release Audio Regression Response cannot be closed again.")
            docs = self._current_documents_or_build(release_id)
            binding = self._regression_binding(release_id)
            if binding.get("regression_status") != "passed" or binding.get("regression_package_verification_status") != "passed":
                raise ReleaseAudioRegressionResponseStateError("Release Audio Regression Response closeout requires current passed Regression Guard recheck.")
            unwaived = [
                row
                for row in docs["actions"].get("actions", [])
                if row.get("status") not in {"resolved", "draft_created"} and str(row.get("severity") or "").lower() in {"high", "critical", "blocking"}
            ]
            if unwaived:
                raise ReleaseAudioRegressionResponseStateError("High or critical response actions remain unresolved.")
            docs["binding"] = binding
            docs["closeout"] = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
                    "response_id": docs["plan"].get("response_id"),
                    "release_id": release_id,
                    "status": "closed",
                    "closed_at": now_iso(),
                    "closed_by": _bounded(payload.get("closed_by") or payload.get("reviewer") or "audio-lead", 120),
                    "reason": _bounded(payload.get("reason") or "Regression response recheck passed.", 1000),
                    "regression_status_after_recheck": binding.get("regression_status"),
                    "regression_binding_hash": binding.get("integrity_hash"),
                    "unresolved_high_critical_count": len(unwaived),
                }
            )
            docs["plan"]["status"] = "closed"
            self._refresh_derived_docs(docs)
            self._write_documents(release_id, docs)
            return docs["closeout"]

    def signoff(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if self._has_active_signoff(release_id):
                raise ReleaseAudioRegressionResponseStateError("Release Audio Regression Response is already signed.")
            docs = self._current_documents_or_build(release_id)
            if docs["closeout"].get("status") != "closed":
                raise ReleaseAudioRegressionResponseStateError("Release Audio Regression Response closeout is not closed.")
            signoff = sanitize_metadata(
                {
                    "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
                    "signoff_id": f"rarrs-{release_id}",
                    "release_id": release_id,
                    "response_id": docs["plan"].get("response_id"),
                    "status": "signed",
                    "signed_at": now_iso(),
                    "signed_by": _bounded(payload.get("signed_by") or payload.get("reviewer") or "audio-lead", 120),
                    "role": _bounded(payload.get("role") or "audio-response-reviewer", 80),
                    "reason": _bounded(payload.get("reason") or "Release audio regression response accepted.", 1000),
                    "source_hash": docs["plan"].get("source_hash"),
                    "plan_hash": docs["plan"].get("integrity_hash"),
                    "actions_hash": docs["actions"].get("integrity_hash"),
                    "waivers_hash": docs["waivers"].get("integrity_hash"),
                    "closeout_hash": docs["closeout"].get("integrity_hash"),
                    "regression_binding_hash": docs["binding"].get("integrity_hash"),
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(release_id), signoff)
            self._append_history_event(
                release_id,
                "response_signoff_created",
                {
                    "signoff_hash": signoff.get("integrity_hash"),
                    "plan_hash": signoff.get("plan_hash"),
                    "actions_hash": signoff.get("actions_hash"),
                    "waivers_hash": signoff.get("waivers_hash"),
                    "closeout_hash": signoff.get("closeout_hash"),
                    "regression_binding_hash": signoff.get("regression_binding_hash"),
                },
            )
            return {"status": "signed", "signoff": signoff, **docs}

    def export_package(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._docs_for_export(release_id)
            export_dir = self.export_dir(release_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload: dict[str, Any] | str) -> None:
                path = export_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                else:
                    write_json(path, payload)
                files.append(_file_record(path, export_dir, rel))

            write_entry("response-plan.json", docs["plan"])
            write_entry("action-items.json", docs["actions"])
            write_entry("waiver-register.json", docs["waivers"])
            write_entry("recheck-closeout.json", docs["closeout"])
            write_entry("regression-binding.json", docs["binding"])
            if self.signoff_path(release_id).exists():
                write_entry("response-signoff.json", read_json(self.signoff_path(release_id)))
            if self.history_path(release_id).exists():
                write_entry("response-signoff-history.jsonl", self.history_path(release_id).read_text(encoding="utf-8"))
            write_entry("README.txt", "MusicForge Release Audio Regression Response\n")
            manifest = {
                "package_type": RELEASE_AUDIO_REGRESSION_RESPONSE_PACKAGE_TYPE,
                "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
                "release_id": release_id,
                "response_id": docs["plan"].get("response_id"),
                "source_hash": docs["plan"].get("source_hash"),
                "plan_hash": docs["plan"].get("integrity_hash"),
                "actions_hash": docs["actions"].get("integrity_hash"),
                "waivers_hash": docs["waivers"].get("integrity_hash"),
                "closeout_hash": docs["closeout"].get("integrity_hash"),
                "regression_binding_hash": docs["binding"].get("integrity_hash"),
                "signoff_hash": read_json(self.signoff_path(release_id)).get("integrity_hash") if self.signoff_path(release_id).exists() else None,
                "generated_at": now_iso(),
                "files": files,
                "zip": {},
            }
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["closeout"].get("status") or docs["plan"].get("status"), "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            exported = self.export_package(release_id)
            export_dir = self.export_dir(release_id)
            zip_path = self.zip_path(release_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(item.filename for item in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, export_dir, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, release_id: str, **kwargs: Any) -> dict[str, Any]:
        if not self.zip_path(release_id).exists():
            self.build_zip(release_id)
        report = verify_release_audio_regression_response_package(self.zip_path(release_id), **kwargs)
        write_release_audio_regression_response_verification_report(report, self.verification_report_path(release_id))
        return report

    def gate(self, release_id: str, *, required: bool = True, require_signed: bool = True) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        try:
            if not self.zip_path(release_id).exists():
                self.build_zip(release_id)
            report = self.verify_zip(release_id, strict=True, require_closed=True, require_signed=require_signed, require_regression_current=True, **self._response_verifier_kwargs(release_id))
            if report.get("status") != "passed":
                return {"status": "failed", "hard_block": True, "message": "Release Audio Regression Response gate failed.", "verification": report}
            return {"status": "passed", "hard_block": False, "message": "Release Audio Regression Response gate passed.", "verification": report}
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _current_documents_or_build(self, release_id: str) -> dict[str, dict[str, Any]]:
        if self.plan_path(release_id).exists():
            return {
                "plan": read_json(self.plan_path(release_id)),
                "actions": read_json(self.action_path(release_id)),
                "waivers": read_json(self.waiver_path(release_id)),
                "closeout": read_json(self.closeout_path(release_id)),
                "binding": read_json(self.binding_path(release_id)),
            }
        return self._build_documents(release_id, payload={}, closeout_override=None)

    def _build_documents(self, release_id: str, *, payload: dict[str, Any], closeout_override: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        binding = self._regression_binding(release_id)
        regression_report = self.regression_store.read_report(release_id)
        blockers = regression_report.get("blockers") if isinstance(regression_report.get("blockers"), list) else []
        actions = _actions_from_regression(regression_report, blockers)
        source = {
            "release_id": release_id,
            "regression_binding_hash": binding.get("integrity_hash"),
            "regression_status": binding.get("regression_status"),
            "blocker_hash": stable_hash(blockers),
            "policy": payload.get("policy") if isinstance(payload.get("policy"), dict) else {},
        }
        source_hash = stable_hash(source)
        plan = sanitize_metadata(
            {
                "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
                "response_id": f"rarr-{release_id}",
                "release_id": release_id,
                "status": "needs_response" if regression_report.get("status") == "failed" else "closed",
                "created_at": now_iso(),
                "source": source,
                "source_hash": source_hash,
                "summary": {
                    "regression_status": regression_report.get("status"),
                    "action_count": len(actions),
                    "high_critical_count": len([row for row in actions if row.get("severity") in {"high", "critical", "blocking"}]),
                },
            }
        )
        action_doc = {"schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION, "release_id": release_id, "response_id": plan["response_id"], "source_hash": source_hash, "actions": actions}
        waiver_doc = {"schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION, "release_id": release_id, "response_id": plan["response_id"], "source_hash": source_hash, "waivers": []}
        closeout = closeout_override or {
            "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
            "release_id": release_id,
            "response_id": plan["response_id"],
            "status": "closed" if regression_report.get("status") == "passed" else "open",
            "regression_status_after_recheck": regression_report.get("status"),
            "regression_binding_hash": binding.get("integrity_hash"),
            "source_hash": source_hash,
        }
        docs = {"plan": plan, "actions": action_doc, "waivers": waiver_doc, "closeout": closeout, "binding": binding}
        self._refresh_derived_docs(docs)
        return docs

    def _refresh_derived_docs(self, docs: dict[str, dict[str, Any]]) -> None:
        source_hash = docs["plan"].get("source_hash")
        for key in ("actions", "waivers", "closeout", "binding"):
            docs[key]["source_hash"] = source_hash
        docs["plan"]["summary"] = {
            **(docs["plan"].get("summary") if isinstance(docs["plan"].get("summary"), dict) else {}),
            "action_count": len(docs["actions"].get("actions", [])),
            "waiver_count": len(docs["waivers"].get("waivers", [])),
            "closeout_status": docs["closeout"].get("status"),
        }
        for key in ("binding", "actions", "waivers", "closeout", "plan"):
            docs[key]["integrity_hash"] = _integrity_hash(docs[key])

    def _write_documents(self, release_id: str, docs: dict[str, dict[str, Any]]) -> None:
        self.response_dir(release_id).mkdir(parents=True, exist_ok=True)
        write_json(self.plan_path(release_id), docs["plan"])
        write_json(self.action_path(release_id), docs["actions"])
        write_json(self.waiver_path(release_id), docs["waivers"])
        write_json(self.closeout_path(release_id), docs["closeout"])
        write_json(self.binding_path(release_id), docs["binding"])

    def _docs_for_export(self, release_id: str) -> dict[str, dict[str, Any]]:
        docs = self._current_documents_or_build(release_id)
        if self._has_active_signoff(release_id):
            self._ensure_signed_export_integrity(release_id, docs)
        return docs

    def _ensure_signed_export_integrity(self, release_id: str, docs: dict[str, dict[str, Any]]) -> None:
        signoff = read_json(self.signoff_path(release_id))
        expected = {
            "plan_hash": docs["plan"].get("integrity_hash"),
            "actions_hash": docs["actions"].get("integrity_hash"),
            "waivers_hash": docs["waivers"].get("integrity_hash"),
            "closeout_hash": docs["closeout"].get("integrity_hash"),
            "regression_binding_hash": docs["binding"].get("integrity_hash"),
        }
        mismatches = [key for key, value in expected.items() if signoff.get(key) != value]
        if signoff.get("integrity_hash") != _integrity_hash(signoff):
            mismatches.append("signoff_integrity_hash")
        history = self._read_history(release_id)
        latest = history[-1] if history else {}
        if not _history_chain_ok(history) or (latest.get("payload") or {}).get("signoff_hash") != signoff.get("integrity_hash"):
            mismatches.append("response_signoff_history")
        if mismatches:
            raise ReleaseAudioRegressionResponseStateError(f"Signed Release Audio Regression Response evidence changed: {', '.join(mismatches)}.")

    def _regression_binding(self, release_id: str) -> dict[str, Any]:
        zip_path = self.regression_store.zip_path(release_id)
        if not zip_path.exists():
            self.regression_store.build_zip(release_id)
        runtime = verify_release_audio_regression_package(zip_path, strict=True, require_signed=True, require_current=True, require_baseline_current=True, **self._regression_verifier_kwargs(release_id))
        regression_report = self.regression_store.read_report(release_id, default={})
        verification_report: dict[str, Any] = {}
        if self.regression_store.verification_report_path(release_id).exists():
            verification_report = read_json(self.regression_store.verification_report_path(release_id))
        binding = {
            "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
            "release_id": release_id,
            "regression_zip_sha256": _sha256_path(zip_path),
            "regression_zip_size_bytes": zip_path.stat().st_size,
            "regression_manifest_hash": runtime.get("manifest_hash"),
            "regression_verification_report_hash": verification_report.get("integrity_hash") or runtime.get("integrity_hash"),
            "regression_verification_status": verification_report.get("status") or runtime.get("status"),
            "regression_package_verification_status": runtime.get("status"),
            "regression_status": regression_report.get("status") or "missing",
            "regression_summary": _public_regression_summary(runtime.get("summary", {})),
        }
        binding["source_hash"] = stable_hash({key: value for key, value in binding.items() if key not in {"source_hash", "integrity_hash"}})
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _regression_verifier_kwargs(self, release_id: str) -> dict[str, Any]:
        config = self.regression_store.read_config(release_id, default={})
        baseline = config.get("baseline") if isinstance(config.get("baseline"), dict) else {}
        current = config.get("current") if isinstance(config.get("current"), dict) else {}
        return {
            "baseline_timeline_path": baseline.get("timeline_zip_path"),
            "baseline_timeline_verification_report_path": baseline.get("timeline_verification_report_path"),
            "baseline_certification_path": baseline.get("certification_zip_path"),
            "baseline_certification_verification_report_path": baseline.get("certification_verification_report_path"),
            "current_timeline_path": current.get("timeline_zip_path"),
            "current_timeline_verification_report_path": current.get("timeline_verification_report_path"),
            "current_certification_path": current.get("certification_zip_path"),
            "current_certification_verification_report_path": current.get("certification_verification_report_path"),
        }

    def _response_verifier_kwargs(self, release_id: str) -> dict[str, Any]:
        return {
            "release_audio_regression_path": self.regression_store.zip_path(release_id),
            "release_audio_regression_verification_report_path": self.regression_store.verification_report_path(release_id),
            **self._regression_verifier_kwargs(release_id),
        }

    def _has_active_signoff(self, release_id: str) -> bool:
        if self.signoff_path(release_id).exists():
            try:
                return read_json(self.signoff_path(release_id)).get("status") == "signed"
            except Exception:
                return True
        return any((event.get("event_type") == "response_signoff_created") for event in self._read_history(release_id))

    def _append_history_event(self, release_id: str, event_type: str, payload: dict[str, Any]) -> None:
        history = self._read_history(release_id)
        previous = history[-1].get("event_hash") if history else None
        event = sanitize_metadata({"schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION, "event_id": f"rarrevt-{len(history) + 1:06d}", "event_type": event_type, "created_at": now_iso(), "previous_event_hash": previous, "payload": payload})
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        self.history_path(release_id).parent.mkdir(parents=True, exist_ok=True)
        with self.history_path(release_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _read_history(self, release_id: str) -> list[dict[str, Any]]:
        path = self.history_path(release_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                item = json.loads(raw)
                if isinstance(item, dict):
                    rows.append(item)
        return rows


def _actions_from_regression(report: dict[str, Any], blockers: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_items = blockers or (report.get("summary") or {}).get("blockers") or []
    for index, item in enumerate(source_items if isinstance(source_items, list) else [], start=1):
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
        lowered = text.lower()
        severity = "critical" if "critical" in lowered or "blocking" in lowered else "high" if "high" in lowered or "failed" in lowered else "warning"
        rows.append(
            sanitize_metadata(
                {
                    "action_id": f"rara-{index:06d}",
                    "source": item,
                    "severity": severity,
                    "status": "pending",
                    "action_type": "draft_audio_fix",
                    "execution_mode": "draft_only",
                    "manual_required": True,
                    "description": sanitize_sensitive_text(text)[:500],
                }
            )
        )
    if not rows and report.get("status") == "failed":
        rows.append({"action_id": "rara-000001", "severity": "high", "status": "pending", "action_type": "draft_audio_fix", "execution_mode": "draft_only", "manual_required": True, "description": "Resolve Release Audio Regression blocker."})
    return rows


def _public_regression_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    allowed = {
        "release_id",
        "baseline_release_id",
        "manifest_hash",
        "check_count",
        "blocker_count",
        "warning_count",
        "track_count",
        "failed_track_count",
        "baseline_track_count",
        "current_track_count",
    }
    return {key: value for key, value in summary.items() if key in allowed}


def _file_record(path: Path, root: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _history_chain_ok(history: list[dict[str, Any]]) -> bool:
    previous: str | None = None
    for event in history:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)
