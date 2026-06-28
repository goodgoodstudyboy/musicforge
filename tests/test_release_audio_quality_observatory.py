from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package
from song_agent.releases import stable_hash
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_release_audio_quality_observatory_lifecycle_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Observatory Track")
        store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        config = store.create({"release_ids": [release_id]})
        summary = store.refresh(config["observatory_id"])
        zipped = store.build_zip(config["observatory_id"])
        verification = store.verify_zip(config["observatory_id"], strict=True, require_current_evidence=True, require_no_critical_risk=True)
        gate = store.gate(release_id, observatory_id=config["observatory_id"], required=True, require_no_critical_risk=True)
    finally:
        stop_test_server(server)

    assert summary["status"] == "passed", summary
    assert zipped["status"] == "passed"
    assert verification["status"] == "passed", verification.get("blockers")
    assert gate["status"] == "passed"


def test_release_audio_quality_observatory_verifier_rejects_internal_full_resign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Observatory Full Resign")
        store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        config = store.create({"release_ids": [release_id]})
        store.refresh(config["observatory_id"])
        zipped = store.build_zip(config["observatory_id"])
        tampered = tmp_path / "observatory-full-resign.zip"
        _rewrite_observatory_as_ready(Path(zipped["zip_path"]), tampered)
        verification = verify_release_audio_quality_observatory_package(
            tampered,
            strict=True,
            require_current_evidence=True,
            evidence_root=server.release_store.root,
            require_no_critical_risk=True,
        )
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "release_audio_quality_observatory_external_trend_match" in verification["blockers"] or "release_audio_quality_observatory_external_summary_match" in verification["blockers"]


def _rewrite_observatory_as_ready(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as source:
        docs = {info.filename: source.read(info.filename) for info in source.infolist()}
    trend = json.loads(docs["trend-report.json"].decode("utf-8"))
    risks = json.loads(docs["risk-register.json"].decode("utf-8"))
    summary = json.loads(docs["observatory-summary.json"].decode("utf-8"))
    manifest = json.loads(docs["manifest.json"].decode("utf-8"))

    trend["summary"]["average_manual_rating"] = 5.0
    trend["summary"]["minimum_manual_rating"] = 5.0
    trend["integrity_hash"] = stable_hash({key: value for key, value in trend.items() if key != "integrity_hash"})
    risks["status"] = "passed"
    risks["risks"] = []
    risks["summary"] = {"risk_count": 0, "critical_risk_count": 0, "warning_risk_count": 0}
    risks["integrity_hash"] = stable_hash({key: value for key, value in risks.items() if key != "integrity_hash"})
    summary["status"] = "passed"
    summary["readiness"] = "ready"
    summary["summary"]["average_manual_rating"] = 5.0
    summary["summary"]["minimum_manual_rating"] = 5.0
    summary["summary"]["critical_risk_count"] = 0
    summary["summary"]["warning_risk_count"] = 0
    summary["document_hashes"]["trend_report"] = trend["integrity_hash"]
    summary["document_hashes"]["risk_register"] = risks["integrity_hash"]
    summary["integrity_hash"] = stable_hash({key: value for key, value in summary.items() if key != "integrity_hash"})
    docs["trend-report.json"] = (json.dumps(trend, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    docs["risk-register.json"] = (json.dumps(risks, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    docs["observatory-summary.json"] = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    manifest["trend_report_hash"] = trend["integrity_hash"]
    manifest["risk_register_hash"] = risks["integrity_hash"]
    manifest["summary_hash"] = summary["integrity_hash"]
    file_rows = []
    for name, data in sorted(docs.items()):
        if name == "manifest.json":
            continue
        file_rows.append({"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest["files"] = file_rows
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    docs["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(docs.items()):
            archive.writestr(name, data)
