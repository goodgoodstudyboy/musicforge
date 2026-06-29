from __future__ import annotations

import pytest

from song_agent.cli import _main
from song_agent.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore
from song_agent.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_release_audio_quality_action_queue_cli_verify(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue CLI Track")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        queue_store.build_zip(queue_id)
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-quality-action-queue-package",
                str(queue_store.zip_path(queue_id)),
                "--strict",
                "--require-current-observatory",
                "--observatory-zip",
                str(observatory_store.zip_path(observatory_id)),
                "--observatory-verification-report",
                str(observatory_store.verification_report_path(observatory_id)),
                "--evidence-root",
                str(server.release_store.root),
                "--json",
            ],
        )
        with pytest.raises(SystemExit) as exc:
            _main()
    finally:
        stop_test_server(server)

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '"status": "passed"' in output


def test_release_audio_quality_action_queue_signoff_archive_cli_verify(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Signoff CLI Track")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        queue_store.build_zip(queue_id)
        queue_store.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=False)
        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=queue_store, release_store=server.release_store)
        for item in signoff_store.list_manual_items(queue_id)["manual_items"]:
            signoff_store.resolve_manual_item(queue_id, item["item_id"], {"status": "completed", "resolved_by": "cli", "reason": "Handled."})
        signoff_store.signoff(queue_id, {"signed_by": "cli", "reason": "Accepted."})
        signoff_store.build_archive_zip(queue_id)
        monkeypatch.setattr(
            "sys.argv",
            [
                "song-agent",
                "verify-release-audio-quality-action-queue-signoff-archive-package",
                str(signoff_store.archive_zip_path(queue_id)),
                "--strict",
                "--require-current-queue",
                "--require-signed",
                "--queue-zip",
                str(queue_store.zip_path(queue_id)),
                "--queue-verification-report",
                str(queue_store.verification_report_path(queue_id)),
                "--observatory-zip",
                str(observatory_store.zip_path(observatory_id)),
                "--observatory-verification-report",
                str(observatory_store.verification_report_path(observatory_id)),
                "--evidence-root",
                str(server.release_store.root),
                "--json",
            ],
        )
        with pytest.raises(SystemExit) as exc:
            _main()
    finally:
        stop_test_server(server)

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '"status": "passed"' in output
