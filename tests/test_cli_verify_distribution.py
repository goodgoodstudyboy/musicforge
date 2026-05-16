from __future__ import annotations

import json
import sys

import pytest

from song_agent.cli import main
from tests.test_distribution import _signed_release_with_metadata, _png
from song_agent.distribution import DistributionStore
from song_agent.distribution_artwork import import_distribution_artwork
from song_agent.distribution_export import build_distribution_export_package, build_distribution_package_zip, sign_distribution_package
from song_agent.distribution_qa import build_distribution_qa_report


def test_cli_verify_distribution_package_json_and_report_out(tmp_path, monkeypatch, capsys):
    release_store, release_id = _signed_release_with_metadata(tmp_path)
    store = DistributionStore(release_store)
    target = store.create_target(release_id, {"profile_id": "demo_pitch"})
    import base64

    import_distribution_artwork(store, release_id, {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
    qa = store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=store, release_id=release_id, target=target))
    manifest = build_distribution_export_package(store=store, release_id=release_id, target=target, qa_report=qa)
    target = store.get_target(release_id, target.target_id)
    build_distribution_package_zip(store, release_id, target)
    sign_distribution_package(store=store, release_id=release_id, target=store.get_target(release_id, target.target_id), qa_report=qa, payload={"signed_by": "tester"})
    report_path = tmp_path / "distribution-verification-report.json"

    monkeypatch.setattr(sys, "argv", ["song-agent", "verify-distribution-package", str(store.package_zip_path(release_id, manifest["package_id"])), "--json", "--report-out", str(report_path)])
    with pytest.raises(SystemExit) as exc:
        main()

    output = capsys.readouterr().out
    report = json.loads(output)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert exc.value.code == 0
    assert report["status"] == "passed"
    assert saved["status"] == "passed"
