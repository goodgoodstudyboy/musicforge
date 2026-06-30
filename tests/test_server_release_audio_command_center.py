from __future__ import annotations

import threading
from pathlib import Path

from tests.helpers_release_audio_command_center import append_untrusted_entry, command_center_fixture, json_evidence
from tests.test_server import request_json


def test_release_audio_command_center_server_refresh_uses_runtime_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with command_center_fixture() as fixture:
        thread = threading.Thread(target=fixture.server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = json_evidence(fixture.evidence)
            status, ok_payload = request_json(fixture.server, "POST", f"/api/releases/{fixture.release_id}/audio-command-center/refresh", payload)
            assert status == 200
            assert ok_payload["ok"] is True
            assert ok_payload["status"] == "passed"

            append_untrusted_entry(fixture.evidence["action_queue"]["zip"])

            failed_status, failed_payload = request_json(fixture.server, "POST", f"/api/releases/{fixture.release_id}/audio-command-center/refresh", payload)
            assert failed_status == 200
            assert failed_payload["ok"] is False
            assert failed_payload["status"] == "failed"
            assert "acc-gap-action_queue" in failed_payload["report"]["blockers"]
        finally:
            fixture.server.shutdown()
            thread.join(timeout=5)
