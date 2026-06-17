from __future__ import annotations

import json
import os
from pathlib import Path

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc
from tests.test_public_trust_center_publication import _ready_publication

from song_agent.public_trust_center_publication_monitoring import (
    PublicTrustCenterPublicationMonitoringStore,
    monitoring_hash,
    monitoring_manifest_hash,
)
from song_agent.public_trust_center_publication_monitoring_verifier import verify_public_trust_center_publication_monitoring_package


def test_publication_monitoring_roundtrip_and_current_state(tmp_path: Path, monkeypatch) -> None:
    publication_store, publication = _ready_publication(tmp_path, monkeypatch)
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    monitor = store.create_monitor("ptc-default", "c", {"monitor_id": "mon", "name": "Release Monitor"})
    run_result = store.run_monitor("ptc-default", "c", monitor["monitor_id"])
    run_id = run_result["monitor_run"]["run_id"]
    manifest = store.export_monitoring_run("ptc-default", "c", "mon", run_id)
    zip_info = store.build_monitoring_zip("ptc-default", "c", "mon", run_id)
    verification = verify_public_trust_center_publication_monitoring_package(
        store.zip_path("ptc-default", "c", "mon", run_id),
        strict=True,
        require_current=True,
        require_no_revoked=True,
        require_ready=True,
        require_no_drift=True,
        require_no_open_critical_incidents=True,
        publication_channel_state_path=publication_store.channel_state_path("ptc-default", "c"),
    )

    assert publication["status"] == "ready"
    assert run_result["monitor_run"]["status"] == "passed", run_result["drift_report"]
    assert manifest["package_type"] == "musicforge_public_trust_center_publication_monitoring"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")


def test_publication_monitoring_detects_mirror_drift_and_incident(tmp_path: Path, monkeypatch) -> None:
    publication_store, publication = _ready_publication(tmp_path, monkeypatch)
    mirror = publication_store.export_dir("ptc-default", "c", publication["publication_id"])
    (mirror / "README.txt").write_text("tampered", encoding="utf-8")
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    monitor = store.create_monitor("ptc-default", "c", {"monitor_id": "mon"})
    result = store.run_monitor("ptc-default", "c", "mon")

    assert result["monitor_run"]["status"] == "failed"
    assert any(item["drift_type"].startswith("mirror_") for item in result["drift_report"]["drifts"])
    assert result["incident_report"]["summary"]["critical_count"] >= 1


def test_publication_monitoring_old_zip_fails_after_revoke_and_supersede(tmp_path: Path, monkeypatch) -> None:
    publication_store, publication = _ready_publication(tmp_path, monkeypatch)
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    monitor = store.create_monitor("ptc-default", "c", {"monitor_id": "mon"})
    result = store.run_monitor("ptc-default", "c", "mon")
    run_id = result["monitor_run"]["run_id"]
    store.export_monitoring_run("ptc-default", "c", "mon", run_id)
    store.build_monitoring_zip("ptc-default", "c", "mon", run_id)
    zip_path = store.zip_path("ptc-default", "c", "mon", run_id)
    state = publication_store.channel_state_path("ptc-default", "c")

    baseline = verify_public_trust_center_publication_monitoring_package(zip_path, strict=True, require_current=True, require_no_revoked=True, publication_channel_state_path=state)
    publication_store.revoke_publication("ptc-default", "c", publication["publication_id"], {"reason": "Withdraw monitored publication."})
    revoked = verify_public_trust_center_publication_monitoring_package(zip_path, strict=True, require_current=True, require_no_revoked=True, publication_channel_state_path=state)

    replacement = publication_store.refresh_publication("ptc-default", "c", {"publication_id": "for-supersede"})
    publication_store.export_publication("ptc-default", "c", replacement["publication_id"])
    publication_store.build_publication_zip("ptc-default", "c", replacement["publication_id"])
    monitor2 = store.create_monitor("ptc-default", "c", {"monitor_id": "mon2", "publication_id": replacement["publication_id"]})
    result2 = store.run_monitor("ptc-default", "c", monitor2["monitor_id"])
    run_id2 = result2["monitor_run"]["run_id"]
    store.export_monitoring_run("ptc-default", "c", "mon2", run_id2)
    store.build_monitoring_zip("ptc-default", "c", "mon2", run_id2)
    zip_path2 = store.zip_path("ptc-default", "c", "mon2", run_id2)
    publication_store.supersede_publication("ptc-default", "c", replacement["publication_id"], {"reason": "Replace monitored publication."})
    superseded = verify_public_trust_center_publication_monitoring_package(zip_path2, strict=True, require_current=True, require_no_revoked=True, publication_channel_state_path=state)

    assert baseline["status"] == "passed", baseline.get("blockers")
    assert _has_blocker(revoked, "ptcpm_require_no_revoked")
    assert _has_blocker(superseded, "ptcpm_require_no_revoked")


def test_publication_monitoring_verifier_rejects_tamper_and_zip_edges(tmp_path: Path, monkeypatch) -> None:
    publication_store, _publication = _ready_publication(tmp_path, monkeypatch)
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    monitor = store.create_monitor("ptc-default", "c", {"monitor_id": "mon"})
    result = store.run_monitor("ptc-default", "c", "mon")
    run_id = result["monitor_run"]["run_id"]
    store.export_monitoring_run("ptc-default", "c", "mon", run_id)
    store.build_monitoring_zip("ptc-default", "c", "mon", run_id)
    source_zip = store.zip_path("ptc-default", "c", "mon", run_id)
    short_source_zip = tmp_path / "monitoring.zip"
    _copy_zip(source_zip, short_source_zip)

    missing_state = verify_public_trust_center_publication_monitoring_package(source_zip, strict=True, require_current=True)
    drift_tamper = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "drift-tamper.zip", _tamper_drift_report), strict=True)
    incident_tamper = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "incident-tamper.zip", _tamper_incident_summary), strict=True)
    duplicate = verify_public_trust_center_publication_monitoring_package(_duplicate_zip(short_source_zip, tmp_path / "duplicate.zip"), strict=True)
    dangerous = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"})), strict=True)
    backslash = verify_public_trust_center_publication_monitoring_package(_backslash_zip(tmp_path / "backslash.zip"), strict=True)
    case_musicforge = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"})), strict=True)
    nested = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested.zip": b"PK\x05\x06" + b"\0" * 18})), strict=True)
    spoof = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "spoof.zip", _spoof_manifest_zip_entries), strict=True)
    redaction = verify_public_trust_center_publication_monitoring_package(_rewrite_zip(short_source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n')), strict=True)

    assert _has_blocker(missing_state, "ptcpm_channel_state_required")
    assert _has_blocker(drift_tamper, "ptcpm_drift_report_integrity") or _has_blocker(drift_tamper, "ptcpm_manifest_file_hashes")
    assert _has_blocker(incident_tamper, "ptcpm_incident_summary_matches_incidents")
    assert _has_blocker(duplicate, "ptcpm_zip_duplicate_entries")
    assert _has_blocker(dangerous, "ptcpm_zip_entry_path_safe")
    assert _has_blocker(backslash, "ptcpm_zip_entry_path_safe")
    assert _has_blocker(case_musicforge, "ptcpm_zip_no_internal_entries")
    assert _has_blocker(nested, "ptcpm_zip_nested_allowlist")
    assert _has_blocker(spoof, "ptcpm_manifest_zip_entries_reference_only")
    assert _has_blocker(redaction, "ptcpm_redaction_scan")


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report.get("blockers", []))


def _copy_zip(source: Path, target: Path) -> None:
    with open(_fs_path(source), "rb") as src, target.open("wb") as dst:
        dst.write(src.read())


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value


def _tamper_drift_report(docs: dict[str, bytes]) -> None:
    drift = _read_doc(docs, "drift-report.json")
    drift["status"] = "passed"
    drift["summary"] = {"drift_count": 0, "critical_count": 0, "high_count": 0, "warning_count": 0}
    docs["drift-report.json"] = _doc_bytes(drift)
    _sync_manifest_file(_read_doc(docs, "monitoring-manifest.json"), "drift-report.json", docs["drift-report.json"])


def _tamper_incident_summary(docs: dict[str, bytes]) -> None:
    incident = _read_doc(docs, "incident-report.json")
    incident["summary"] = {"incident_count": len(incident.get("incidents", [])) + 1, "open_count": 1, "critical_count": 1, "waived_count": 0, "resolved_count": 0}
    incident["integrity_hash"] = monitoring_hash(incident)
    docs["incident-report.json"] = _doc_bytes(incident)
    manifest = _read_doc(docs, "monitoring-manifest.json")
    _sync_manifest_file(manifest, "incident-report.json", docs["incident-report.json"])
    manifest["integrity_hash"] = monitoring_manifest_hash(manifest)
    docs["monitoring-manifest.json"] = _doc_bytes(manifest)


def _spoof_manifest_zip_entries(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "monitoring-manifest.json")
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = monitoring_manifest_hash(manifest)
    docs["monitoring-manifest.json"] = _doc_bytes(manifest)
