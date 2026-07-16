from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import re
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.domains.quality.release_audio_quality_observatory_verifier import RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_observatory_package, write_release_audio_quality_observatory_verification_report
from song_agent.domains.delivery.releases import ReleaseStore, stable_hash


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE = "release_audio_quality_action_queue"


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION = 1


class ReleaseAudioQualityActionQueueError(ValueError):
    pass


class ReleaseAudioQualityActionQueueValidationError(ReleaseAudioQualityActionQueueError):
    pass


def build_expected_action_documents_from_observatory(
    queue: dict[str, Any],
    source_binding: dict[str, Any],
    *,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> dict[str, Any]:
    if not observatory_zip_path or not observatory_verification_report_path or not evidence_root:
        raise ReleaseAudioQualityActionQueueValidationError("Current Observatory verification requires Observatory ZIP, verification report, and evidence root.")
    observatory_zip = Path(observatory_zip_path)
    verification_path = Path(observatory_verification_report_path)
    verification = read_json(verification_path)
    runtime = verify_release_audio_quality_observatory_package(observatory_zip, strict=True, require_current_evidence=True, evidence_root=evidence_root, require_no_critical_risk=False)
    if verification.get("package_type") != RELEASE_AUDIO_QUALITY_OBSERVATORY_VERIFICATION_PACKAGE_TYPE:
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report has the wrong package type.")
    if not _integrity_ok(verification):
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report integrity failed.")
    if verification.get("status") != "passed" or runtime.get("status") != "passed":
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification is not passed.")
    if verification.get("zip_sha256") != _sha256_path(observatory_zip) or int(verification.get("zip_size_bytes") or -1) != observatory_zip.stat().st_size or verification.get("manifest_hash") != runtime.get("manifest_hash"):
        raise ReleaseAudioQualityActionQueueValidationError("Observatory verification report does not match the current Observatory ZIP.")
    with zipfile.ZipFile(observatory_zip) as archive:
        config = _read_json_entry(archive, "observatory-config.json")
        risk_register = _read_json_entry(archive, "risk-register.json")
        recommendation_report = _read_json_entry(archive, "recommendation-report.json")
        summary = _read_json_entry(archive, "observatory-summary.json")
    expected_binding = _source_binding_from_external(
        config,
        risk_register,
        recommendation_report,
        summary,
        observatory_zip=observatory_zip,
        verification=verification,
    )
    selection = _selection_from_documents(queue, source_binding)
    expected_binding = _with_action_selection(expected_binding, selection)
    expected_items = _action_items_from_binding(
        str(queue.get("queue_id") or ""),
        expected_binding,
        include_risks=selection["include_risks"],
        include_recommendations=selection["include_recommendations"],
        severity_floor=selection["severity_floor"],
    )
    return {"source_binding": expected_binding, "items": expected_items, "verification": verification, "runtime": runtime}


def _source_binding_from_external(
    config: ImplementationDocument,
    risk_register: ImplementationDocument,
    recommendation_report: ImplementationDocument,
    summary: ImplementationDocument,
    *,
    observatory_zip: Path,
    verification: ImplementationDocument,
) -> ImplementationDocument:
    observatory_id = str(config.get("observatory_id") or summary.get("observatory_id") or "")
    source_hash = stable_hash(
        {
            "observatory_id": observatory_id,
            "observatory_zip_sha256": _sha256_path(observatory_zip),
            "observatory_zip_size_bytes": observatory_zip.stat().st_size,
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
                "zip_sha256": _sha256_path(observatory_zip),
                "zip_size_bytes": observatory_zip.stat().st_size,
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
            "created_at": "external",
        }
    )
    binding["integrity_hash"] = _integrity_hash(binding)
    return binding


def _action_items_from_binding(
    queue_id: str,
    binding: ImplementationDocument,
    *,
    include_risks: bool,
    include_recommendations: bool,
    severity_floor: str,
) -> list[ImplementationDocument]:
    severity_rank = {"info": 0, "warning": 1, "high": 2, "critical": 3, "blocking": 3}
    floor = severity_rank.get(str(severity_floor or "warning"), 1)
    risks = binding.get("risk_register", {}).get("risks") if isinstance(binding.get("risk_register"), dict) else []
    recommendations = binding.get("recommendation_report", {}).get("recommendations") if isinstance(binding.get("recommendation_report"), dict) else []
    items: list[dict[str, Any]] = []
    fingerprints: set[str] = set()

    def add_item(item: dict[str, Any]) -> None:
        fingerprint = stable_hash(
            {
                "source_type": item.get("source_type"),
                "source_id": item.get("source_id"),
                "action_type": item.get("action_type"),
                "target": item.get("target"),
            }
        )
        if fingerprint in fingerprints:
            return
        fingerprints.add(fingerprint)
        item["item_id"] = f"aqai-{len(items) + 1:06d}"
        item["fingerprint"] = fingerprint
        item["created_at"] = now_iso()
        items.append(sanitize_metadata(item))

    if include_risks:
        for risk in risks or []:
            if not isinstance(risk, dict):
                continue
            severity = str(risk.get("severity") or "warning")
            if severity_rank.get(severity, 1) < floor:
                continue
            action_type, execution_mode = _risk_action(str(risk.get("check_id") or "unknown"), severity)
            add_item(
                {
                    "source_type": "risk",
                    "source_id": risk.get("risk_id"),
                    "source_check_id": risk.get("check_id"),
                    "severity": severity,
                    "status": "pending",
                    "action_type": action_type,
                    "execution_mode": execution_mode,
                    "target": {"release_id": risk.get("release_id"), "track_id": risk.get("track_id"), "issue_type": risk.get("check_id")},
                    "inputs": {"reason": risk.get("message") or risk.get("reason") or risk.get("check_id")},
                    "requires_manual": execution_mode == "manual_required",
                    "can_auto_execute": execution_mode == "safe",
                }
            )
    if include_recommendations:
        for recommendation in recommendations or []:
            if not isinstance(recommendation, dict):
                continue
            action_type, execution_mode = _recommendation_action(str(recommendation.get("action") or "unknown"))
            add_item(
                {
                    "source_type": "recommendation",
                    "source_id": recommendation.get("recommendation_id"),
                    "source_check_id": recommendation.get("source_risk_id") or recommendation.get("action"),
                    "severity": "warning",
                    "status": "pending",
                    "action_type": action_type,
                    "execution_mode": execution_mode,
                    "target": {"release_id": recommendation.get("release_id"), "track_id": recommendation.get("track_id"), "issue_type": recommendation.get("action")},
                    "inputs": {"reason": recommendation.get("reason") or recommendation.get("action")},
                    "requires_manual": execution_mode == "manual_required",
                    "can_auto_execute": execution_mode == "safe",
                }
            )
    return items


def _action_selection(*, include_risks: bool, include_recommendations: bool, severity_floor: str) -> ImplementationDocument:
    floor = str(severity_floor or "warning").strip().lower()
    if floor not in {"info", "warning", "high", "critical", "blocking"}:
        floor = "warning"
    return {
        "include_risks": bool(include_risks),
        "include_recommendations": bool(include_recommendations),
        "severity_floor": floor,
    }


def _selection_from_documents(queue: ImplementationDocument, source_binding: ImplementationDocument) -> ImplementationDocument:
    selection = source_binding.get("action_selection") if isinstance(source_binding.get("action_selection"), dict) else {}
    if not selection and isinstance(queue.get("action_selection"), dict):
        selection = queue.get("action_selection") or {}
    return _action_selection(
        include_risks=selection.get("include_risks", True),
        include_recommendations=selection.get("include_recommendations", True),
        severity_floor=str(selection.get("severity_floor") or "warning"),
    )


def _with_action_selection(binding: ImplementationDocument, selection: ImplementationDocument) -> ImplementationDocument:
    updated = dict(binding)
    updated["action_selection"] = _action_selection(
        include_risks=selection.get("include_risks", True),
        include_recommendations=selection.get("include_recommendations", True),
        severity_floor=str(selection.get("severity_floor") or "warning"),
    )
    updated["integrity_hash"] = _integrity_hash(updated)
    return updated


def _risk_action(check_id: str, severity: str) -> tuple[str, str]:
    if check_id == "audio_evidence_not_current":
        return "verify_observatory", "safe"
    if check_id in {"manual_rating_floor", "quality_trend_decline"}:
        return "create_audio_quality_review_task", "safe"
    if check_id in {"critical_issue_hotspot", "needs_fix_backlog"}:
        return "create_audio_fix_sprint_draft", "safe"
    if check_id == "baseline_drift_detected":
        return "create_baseline_review_request", "manual_required"
    if severity in {"critical", "blocking"}:
        return "manual_audio_lead_review", "manual_required"
    return "manual_audio_lead_review", "manual_required"


def _recommendation_action(action: str) -> tuple[str, str]:
    if action == "refresh_audio_evidence":
        return "verify_observatory", "safe"
    if action == "open_audio_quality_review":
        return "create_audio_quality_review_task", "safe"
    if action == "open_regression_response":
        return "create_regression_response_plan_draft", "safe"
    if action == "review_baseline_policy":
        return "create_baseline_review_request", "manual_required"
    return "manual_audio_lead_review", "manual_required"


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))
