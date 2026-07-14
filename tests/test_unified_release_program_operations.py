from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_operations import UnifiedReleaseProgramOperationsStateError, UnifiedReleaseProgramOperationsStore
from song_agent.unified_release_program_operations_verifier import verify_unified_release_program_operations_package
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program import _program_with_handoff, _signed_handoff_fixture
from song_agent.unified_release_program import write_external_evidence_manifest


def _signed_program(tmp_path: Path):
    store, program_id, manifest_path, _handoff = _program_with_handoff(tmp_path)
    store.refresh_report(program_id, {"external_evidence_manifest": manifest_path})
    store.signoff(program_id, {"external_evidence_manifest": manifest_path, "signed_by": "program owner", "role": "release_owner"})
    store.build_zip(program_id)
    verification = store.verify_package(program_id, {"strict": True, "require_current": True, "require_signed": True, "external_evidence_manifest": manifest_path, "program_signoff_binding": store.signoff_binding_path(program_id)})
    assert verification["status"] == "passed", verification.get("blockers")
    return store, program_id, manifest_path


def _ops_payload(store, program_id: str, manifest_path: Path) -> dict:
    return {
        "external_evidence_manifest": manifest_path,
        "program_zip": store.zip_path(program_id),
        "program_verification_report": store.verification_report_path(program_id),
        "program_signoff_binding": store.signoff_binding_path(program_id),
    }


def test_unified_release_program_operations_archive_and_reset(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)
    store = UnifiedReleaseProgramOperationsStore(program_store)
    payload = _ops_payload(program_store, program_id, manifest_path)

    review = store.refresh_continuous_review(program_id, payload)
    lifecycle = store.refresh_lifecycle_audit(program_id, payload)
    zipped = store.build_operations_archive_zip(program_id, payload)
    verified = store.verify_operations_archive_zip(program_id, payload)

    assert review["status"] == "passed"
    assert lifecycle["status"] == "passed"
    assert Path(zipped["zip_path"]).exists()
    assert verified["status"] == "passed", verified.get("blockers")

    cr = store.create_change_request(program_id, payload)
    approval = store.approve_change_request(program_id, cr["change_request_id"], payload)
    reset = store.reset_program_signoff(program_id, {**payload, "change_request_id": cr["change_request_id"]})

    assert approval["status"] == "approved"
    assert reset["status"] == "applied"
    assert program_store.latest_signoff_state(program_id)["status"] == "reset"
    with pytest.raises(UnifiedReleaseProgramOperationsStateError):
        store.build_operations_archive_zip(program_id, payload)
    with pytest.raises(UnifiedReleaseProgramOperationsStateError):
        store.reset_program_signoff(program_id, {**payload, "change_request_id": cr["change_request_id"]})


def test_unified_release_program_operations_reset_requires_allowed_action(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)
    store = UnifiedReleaseProgramOperationsStore(program_store)
    payload = _ops_payload(program_store, program_id, manifest_path)

    cr = store.create_change_request(program_id, {**payload, "allowed_actions": ["refresh_program_report"]})
    store.approve_change_request(program_id, cr["change_request_id"], payload)

    with pytest.raises(UnifiedReleaseProgramOperationsStateError):
        store.reset_program_signoff(program_id, {**payload, "change_request_id": cr["change_request_id"]})


def test_unified_release_program_operations_rejects_wrong_program_verification_type(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)
    store = UnifiedReleaseProgramOperationsStore(program_store)
    payload = _ops_payload(program_store, program_id, manifest_path)
    zipped = store.build_operations_archive_zip(program_id, payload)
    bad_report_path = tmp_path / "wrong-program-verification-report.json"
    bad_report = read_json(program_store.verification_report_path(program_id))
    bad_report["package_type"] = "wrong_package_type"
    bad_report["integrity_hash"] = stable_hash({key: value for key, value in bad_report.items() if key != "integrity_hash"})
    write_json(bad_report_path, bad_report)

    with pytest.raises(UnifiedReleaseProgramOperationsStateError):
        store.build_operations_archive_zip(program_id, {**payload, "program_verification_report": bad_report_path})

    report = verify_unified_release_program_operations_package(
        Path(zipped["zip_path"]),
        strict=True,
        require_current=True,
        require_signed_program=True,
        require_continuous_review_clear=True,
        require_lifecycle_audit=True,
        program_zip_path=program_store.zip_path(program_id),
        program_verification_report_path=bad_report_path,
        program_signoff_binding_path=program_store.signoff_binding_path(program_id),
        external_evidence_manifest_path=manifest_path,
    )

    assert report["status"] == "failed"
    assert "urp_ops_current_program_verification_package_type" in report["blockers"]


def test_unified_release_program_operations_verifier_rejects_declared_extra(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)
    store = UnifiedReleaseProgramOperationsStore(program_store)
    payload = _ops_payload(program_store, program_id, manifest_path)
    zipped = store.build_operations_archive_zip(program_id, payload)

    extra_zip = tmp_path / "operations-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_operations_extra)
    report = verify_unified_release_program_operations_package(extra_zip, strict=True)

    assert report["status"] == "failed"
    assert "urp_ops_allowed_entries" in report["blockers"]


def test_unified_release_program_operations_cli_archive(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)

    review = _run_cli(["unified-release-program-operations", "--json", "continuous-review-refresh", program_id, "--external-evidence-manifest", str(manifest_path)], tmp_path)
    lifecycle = _run_cli(["unified-release-program-operations", "--json", "lifecycle-refresh", program_id], tmp_path)
    zipped = _run_cli(["unified-release-program-operations", "--json", "archive-zip", program_id, "--external-evidence-manifest", str(manifest_path)], tmp_path)
    verify = _run_cli(["unified-release-program-operations", "--json", "archive-verify", program_id, "--strict", "--require-current", "--require-signed-program", "--require-continuous-review-clear", "--require-lifecycle-audit", "--external-evidence-manifest", str(manifest_path)], tmp_path)
    standalone = _run_cli(
        [
            "verify-unified-release-program-operations-package",
            "--json",
            str(program_store.program_dir(program_id) / "operations" / "operations-archive.zip"),
            "--strict",
            "--require-current",
            "--require-signed-program",
            "--require-continuous-review-clear",
            "--require-lifecycle-audit",
            "--program-zip",
            str(program_store.zip_path(program_id)),
            "--program-verification-report",
            str(program_store.verification_report_path(program_id)),
            "--program-signoff-binding",
            str(program_store.signoff_binding_path(program_id)),
            "--external-evidence-manifest",
            str(manifest_path),
        ],
        tmp_path,
    )

    assert review.returncode == 0, review.stderr
    assert json.loads(review.stdout)["status"] == "passed"
    assert lifecycle.returncode == 0, lifecycle.stderr
    assert zipped.returncode == 0, zipped.stderr
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["verification"]["status"] == "passed"
    assert standalone.returncode == 0, standalone.stderr
    assert json.loads(standalone.stdout)["status"] == "passed"


def test_unified_release_program_operations_cli_reset_requires_allowed_action(tmp_path: Path) -> None:
    program_store, program_id, manifest_path = _signed_program(tmp_path)

    created = _run_cli(
        [
            "unified-release-program-operations",
            "--json",
            "change-request-create",
            program_id,
            "--external-evidence-manifest",
            str(manifest_path),
            "--allowed-action",
            "refresh_program_report",
        ],
        tmp_path,
    )
    assert created.returncode == 0, created.stderr
    request_id = json.loads(created.stdout)["change_request"]["change_request_id"]
    approved = _run_cli(
        [
            "unified-release-program-operations",
            "--json",
            "change-request-approve",
            program_id,
            request_id,
            "--external-evidence-manifest",
            str(manifest_path),
        ],
        tmp_path,
    )
    reset = _run_cli(
        [
            "unified-release-program-operations",
            "--json",
            "reset-signoff",
            program_id,
            "--change-request-id",
            request_id,
            "--external-evidence-manifest",
            str(manifest_path),
        ],
        tmp_path,
    )

    assert approved.returncode == 0, approved.stderr
    assert reset.returncode != 0
    assert program_store.latest_signoff_state(program_id)["status"] == "signed"


def test_unified_release_program_operations_api_minimal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    handoff = _signed_handoff_fixture(tmp_path)
    manifest_path = tmp_path / "urp-api-ops-external.json"
    write_external_evidence_manifest(
        manifest_path,
        program_id="urp-api-ops",
        items=[
            {
                "item_id": "train-a",
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            }
        ],
    )
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/unified-release-programs", {"program_id": "urp-api-ops"})
        request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/items", {"item_id": "train-a", "train_id": handoff["train_id"], "handoff_id": handoff["handoff_id"], "handoff_zip": str(handoff["handoff_zip"]), "handoff_verification_report": str(handoff["handoff_verification_report"]), "handoff_signoff_binding": str(handoff["handoff_signoff_binding"])})
        request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/refresh", {"external_evidence_manifest": str(manifest_path)})
        request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/signoff", {"external_evidence_manifest": str(manifest_path), "signed_by": "program owner"})
        request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/zip", {})
        request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/verify", {"strict": True, "require_current": True, "require_signed": True, "external_evidence_manifest": str(manifest_path)})
        review_status, review_body = request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/operations/continuous-review/refresh", {"external_evidence_manifest": str(manifest_path)})
        zip_status, zip_body = request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/operations/archive/zip", {"external_evidence_manifest": str(manifest_path)})
        verify_status, verify_body = request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/operations/archive/verify", {"strict": True, "require_current": True, "require_signed_program": True, "require_continuous_review_clear": True, "require_lifecycle_audit": True, "external_evidence_manifest": str(manifest_path)})
        cr_status, cr_body = request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/operations/change-requests", {"external_evidence_manifest": str(manifest_path), "allowed_actions": ["refresh_program_report"]})
        request_id = cr_body["change_request"]["change_request_id"]
        approve_status, approve_body = request_json(server, "POST", f"/api/unified-release-programs/urp-api-ops/operations/change-requests/{request_id}/approve", {"external_evidence_manifest": str(manifest_path)})
        reset_status, reset_body = request_json(server, "POST", "/api/unified-release-programs/urp-api-ops/operations/reset-signoff", {"external_evidence_manifest": str(manifest_path), "change_request_id": request_id})
    finally:
        stop_test_server(server)

    assert review_status == 200, review_body
    assert review_body["status"] == "passed"
    assert zip_status == 200, zip_body
    assert verify_status == 200, verify_body
    assert verify_body["status"] == "passed"
    assert cr_status == 201, cr_body
    assert approve_status == 200, approve_body
    assert reset_status == 409, reset_body


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "song_agent.cli", *args],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        text=True,
        capture_output=True,
        check=False,
    )


def _add_declared_operations_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected operations file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
