import json
from pathlib import Path

import pytest

from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center import UnifiedCommandCenterStateError, UnifiedCommandCenterStore
from song_agent.unified_command_center_verifier import verify_unified_command_center_component, verify_unified_command_center_package


def _release_check_report(path: Path, *, ok: bool) -> Path:
    report = {
        "ok": ok,
        "summary": {"total": 1, "passed": 1 if ok else 0, "failed": 0 if ok else 1},
        "results": [
            {"check_id": "synthetic.passed" if ok else "synthetic.failed", "status": "passed" if ok else "failed"}
        ],
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _verification_report(path: Path, *, package_type: str, status: str = "passed", release_id: str = "release-001", target_id: str | None = None, submission_id: str | None = None, zip_sha256: str = "a" * 64) -> Path:
    summary = {"release_id": release_id, "entry_count": 1, "blocker_count": 0}
    if target_id:
        summary["target_id"] = target_id
    if submission_id:
        summary["submission_id"] = submission_id
    report = {
        "package_type": package_type,
        "status": status,
        "input": {"sha256": zip_sha256, "size_bytes": 1},
        "summary": summary,
        "blockers": [] if status == "passed" else ["synthetic.failed"],
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _store(tmp_path: Path) -> UnifiedCommandCenterStore:
    return UnifiedCommandCenterStore(root=tmp_path / ".musicforge" / "unified-command-centers")


def _create_release_check_center(store: UnifiedCommandCenterStore) -> str:
    center = store.create(
        {
            "center_id": "ucc-test",
            "requirements": {
                "audio-command-center": False,
                "trust-operations-hub": False,
                "public-trust-center": False,
                "ga-readiness": False,
                "release-check": True,
            },
        }
    )
    return center["center_id"]


def test_unified_command_center_builds_ready_package(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check.json", ok=True)
    store = _store(tmp_path)
    center_id = _create_release_check_center(store)
    evidence = {"release-check": {"report": passed}}

    report = store.refresh(center_id, evidence)
    zipped = store.build_zip(center_id, evidence)
    verification = store.verify_zip(center_id, evidence=evidence, strict=True, require_ready=True)

    assert report["status"] == "ready"
    assert Path(zipped["zip_path"]).exists()
    assert verification["status"] == "passed"
    assert verification["summary"]["center_id"] == center_id


def test_unified_command_center_verifier_rejects_stale_release_check_evidence(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check-passed.json", ok=True)
    failed = _release_check_report(tmp_path / "release-check-failed.json", ok=False)
    store = _store(tmp_path)
    center_id = _create_release_check_center(store)
    zipped = store.build_zip(center_id, {"release-check": {"report": passed}})

    verification = verify_unified_command_center_package(
        zipped["zip_path"],
        strict=True,
        require_ready=True,
        release_check_report_path=failed,
    )

    assert verification["status"] == "failed"
    assert "ucc_release-check_fingerprint_binding" in verification["blockers"]


def test_unified_command_center_verifier_rejects_declared_extra_file(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check.json", ok=True)
    store = _store(tmp_path)
    center_id = _create_release_check_center(store)
    zipped = store.build_zip(center_id, {"release-check": {"report": passed}})
    tampered = tmp_path / "tampered.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered, _add_declared_extra)

    verification = verify_unified_command_center_package(
        tampered,
        strict=True,
        require_ready=True,
        release_check_report_path=passed,
    )

    assert verification["status"] == "failed"
    assert "ucc_zip_allowed_entries" in verification["blockers"]


def test_unified_command_center_run_safe_blocks_stale_source(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check-passed.json", ok=True)
    failed = _release_check_report(tmp_path / "release-check-failed.json", ok=False)
    store = _store(tmp_path)
    center_id = _create_release_check_center(store)
    store.refresh(center_id, {"release-check": {"report": passed}})

    with pytest.raises(UnifiedCommandCenterStateError):
        store.run_safe(center_id, {"release-check": {"report": failed}})


def test_unified_command_center_run_safe_does_not_fake_external_actions(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check.json", ok=True)
    store = _store(tmp_path)
    center = store.create(
        {
            "center_id": "ucc-run-safe",
            "requirements": {
                "audio-command-center": False,
                "trust-operations-hub": False,
                "public-trust-center": False,
                "ga-readiness": False,
                "release-check": True,
                "release": True,
            },
        }
    )
    result = store.run_safe(center["center_id"], {"release-check": {"report": passed}})

    skipped = [row for row in result["results"] if row.get("status") == "skipped_unsupported"]
    assert any(row.get("action") == "release.verify" for row in skipped)
    assert result["summary"]["skipped_unsupported_count"] >= 1


def test_unified_command_center_multi_distribution_requires_all_external_reports(tmp_path: Path) -> None:
    passed = _release_check_report(tmp_path / "release-check.json", ok=True)
    zip_one = tmp_path / "target-001.zip"
    zip_two = tmp_path / "target-002.zip"
    zip_one.write_bytes(b"1")
    zip_two.write_bytes(b"2")
    report_one = _verification_report(tmp_path / "target-001.json", package_type="musicforge_distribution_verification", target_id="target-001", zip_sha256=_sha256_bytes(b"1"))
    report_two = _verification_report(tmp_path / "target-002.json", package_type="musicforge_distribution_verification", target_id="target-002", zip_sha256=_sha256_bytes(b"2"))
    store = _store(tmp_path)
    center = store.create(
        {
            "center_id": "ucc-multi",
            "requirements": {
                "audio-command-center": False,
                "trust-operations-hub": False,
                "public-trust-center": False,
                "ga-readiness": False,
                "release-check": True,
                "distribution": True,
            },
        }
    )
    evidence = {
        "release-check": {"report": passed},
        "distribution": {"zips": [zip_one, zip_two], "verification_reports": [report_one, report_two]},
    }
    store.refresh(center["center_id"], evidence)
    zipped = store.build_zip(center["center_id"], evidence)

    missing_second = verify_unified_command_center_package(
        zipped["zip_path"],
        strict=True,
        require_ready=True,
        release_check_report_path=passed,
        distribution_zip_paths=[zip_one],
        distribution_verification_report_paths=[report_one],
    )

    assert missing_second["status"] == "failed"
    assert "ucc_distribution_fingerprint_binding" in missing_second["blockers"]


def test_unified_command_center_rejects_wrong_external_report_package_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "distribution.zip"
    package.write_bytes(b"distribution-package")
    report = _verification_report(
        tmp_path / "wrong-type.json",
        package_type="musicforge_release_verification",
        zip_sha256=_sha256_bytes(package.read_bytes()),
    )

    def _fake_distribution_runtime(path: Path | str, *, strict: bool = False) -> dict:
        return {
            "package_type": "musicforge_distribution_verification",
            "status": "passed",
            "input": {"sha256": _sha256_bytes(Path(path).read_bytes()), "size_bytes": Path(path).stat().st_size},
            "summary": {"target_id": "target-001", "entry_count": 1, "blocker_count": 0},
            "blockers": [],
        }

    monkeypatch.setattr(
        "song_agent.unified_command_center_verifier.verify_distribution_package",
        _fake_distribution_runtime,
    )

    result = verify_unified_command_center_component(
        "distribution",
        zip_path=package,
        verification_report_path=report,
    )

    assert result["status"] == "failed"
    assert "ucc_distribution_external_package_type" in result["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
