from __future__ import annotations

from pathlib import Path

from tests.test_server_acceptance_fix_sprints import _project_with_acceptance_issue
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_acceptance_kb_api_refresh_entries_search_recommend_and_hide(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _project_id, _suite_id, _case_id, analytics = _project_with_acceptance_issue(server)
        fix_status, fix = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics["report_id"]})
        fix_sprint_id = fix["fix_sprint"]["fix_sprint_id"]
        items_status, items = request_json(server, "GET", f"/api/acceptance/fix-sprints/{fix_sprint_id}/items")
        item_id = items["items"][0]["item_id"]
        request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/items/{item_id}/waive", {"reason": "manual correction verified"})
        recheck_status, recheck = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck["suite"]["suite_id"]
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = detail["cases"][0]["case_id"]
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Accepted."})
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/delta/refresh")
        close_status, _close = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
        refresh_status, refreshed = request_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})
        entries_status, entries = request_json(server, "GET", "/api/acceptance/kb/entries")
        entry_id = entries["entries"][0]["entry_id"]
        detail_entry_status, detail_entry = request_json(server, "GET", f"/api/acceptance/kb/entries/{entry_id}")
        search_status, search = request_json(server, "GET", "/api/acceptance/kb/search?issue_type=hook")
        recommend_status, recommend = request_json(server, "POST", "/api/acceptance/kb/recommend", {"issue_types": ["hook"], "song_id": "rap_beat_001"})
        hide_status, _hidden = request_json(server, "POST", f"/api/acceptance/kb/entries/{entry_id}/hide")
        hidden_search_status, hidden_search = request_json(server, "GET", "/api/acceptance/kb/search?issue_type=hook")
    finally:
        stop_test_server(server)

    assert fix_status == 201
    assert items_status == 200
    assert recheck_status == 201
    assert detail_status == 200
    assert close_status == 200
    assert refresh_status == 201
    assert refreshed["summary"]["entry_count"] == 1
    assert entries_status == 200
    assert detail_entry_status == 200
    assert detail_entry["entry"]["entry_id"] == entry_id
    assert search_status == 200
    assert search["summary"]["entry_count"] == 1
    assert recommend_status == 200
    assert recommend["recommendation"]["status"] == "available"
    assert hide_status == 200
    assert hidden_search_status == 200
    assert hidden_search["summary"]["entry_count"] == 0
