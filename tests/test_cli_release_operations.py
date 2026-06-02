from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from song_agent.release_operations import ReleaseOperationsStore
from song_agent.releases import ReleaseStore


def test_verify_release_operations_package_cli_json_report_out_and_tamper(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops CLI", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)
    store.refresh(release.release_id)
    store.export_operations(release.release_id)
    store.build_zip(release.release_id)
    report_out = tmp_path / "verify-report.json"

    ok = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-package", str(store.zip_path(release.release_id)), "--json", "--report-out", str(report_out)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    saved = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert saved["status"] == "passed"

    tampered_zip = tmp_path / "tampered-cli.zip"
    with zipfile.ZipFile(store.zip_path(release.release_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-report.json":
                doc = json.loads(data.decode("utf-8"))
                doc["current_stage"] = "accepted"
                data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    failed = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "verify-release-operations-package", str(tampered_zip), "--json"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert failed.returncode == 1
    failed_payload = json.loads(failed.stdout)
    assert failed_payload["status"] == "failed"
    assert any(item["check_id"] == "operations_report_integrity" for item in failed_payload["blockers"])
