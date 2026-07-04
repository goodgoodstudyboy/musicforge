from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train import DEFAULT_REQUIRED_EVIDENCE, write_external_evidence_manifest
from song_agent.unified_command_center_release_train_verifier import EXPECTED_EVIDENCE_PACKAGE_TYPES
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _fake_evidence(base: Path, item_id: str, center_id: str, evidence_type: str) -> dict:
    evidence_dir = base / "external" / evidence_type
    evidence_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "package_type": f"fake-{evidence_type}", "files": []}
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    zip_path = evidence_dir / f"{evidence_type}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    report = {
        "schema_version": 1,
        "package_type": EXPECTED_EVIDENCE_PACKAGE_TYPES[evidence_type],
        "status": "passed",
        "zip_sha256": zip_sha,
        "manifest_hash": manifest["integrity_hash"],
        "summary": {"zip_sha256": zip_sha, "manifest_hash": manifest["integrity_hash"]},
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    report_path = evidence_dir / f"{evidence_type}-verification-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"item_id": item_id, "center_id": center_id, "evidence_type": evidence_type, "zip_path": str(zip_path), "verification_report_path": str(report_path)}


def test_unified_command_center_release_train_api_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_status, create_body = request_json(server, "POST", "/api/unified-command-center-release-trains", {"train_id": "uct-api", "required_evidence": DEFAULT_REQUIRED_EVIDENCE})
        item_status, item_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/items", {"item_id": "item-001", "center_id": "ucc-api"})
        rows = [_fake_evidence(tmp_path, "item-001", "ucc-api", evidence_type) for evidence_type in DEFAULT_REQUIRED_EVIDENCE]
        manifest_path = tmp_path / "external-evidence.json"
        write_external_evidence_manifest(manifest_path, train_id="uct-api", items=rows)
        refresh_status, refresh_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/refresh", {"external_evidence_manifest": str(manifest_path)})
        signoff_status, signoff_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "api train lead"})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/archive/zip", {})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/archive/verify", {"strict": True, "require_go": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
        detail_status, detail_body = request_json(server, "GET", "/api/unified-command-center-release-trains/uct-api")
        Path(".musicforge/unified-command-trains/uct-api/train-signoff.json").unlink()
        mutation_status, mutation_body = request_json(server, "POST", "/api/unified-command-center-release-trains/uct-api/items", {"item_id": "item-002", "center_id": "ucc-after-signoff"})
    finally:
        stop_test_server(server)

    assert create_status == 201, create_body
    assert item_status == 201, item_body
    assert refresh_status == 200, refresh_body
    assert refresh_body["status"] == "go"
    assert signoff_status == 201, signoff_body
    assert signoff_body["status"] == "signed"
    assert zip_status == 200, zip_body
    assert Path(zip_body["zip_path"]).exists()
    assert verify_status == 200, verify_body
    assert verify_body["verification"]["status"] == "passed", verify_body["verification"].get("blockers")
    assert detail_status == 200, detail_body
    assert detail_body["status"] == "go"
    assert mutation_status == 409, mutation_body
