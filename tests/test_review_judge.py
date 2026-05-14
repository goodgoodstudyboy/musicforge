from __future__ import annotations

import json

import pytest

from song_agent.provider import ProviderConfig, ProviderOutputError
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.review_judge import (
    build_judge_report,
    build_review_judge_prompt_payload,
    judge_report_stale,
    judge_report_summary,
    run_provider_review_judge,
)
from song_agent.review_tasks import ReviewTaskStore, build_local_review_candidates, build_review_decision_report
from tests.test_editor_audition import demo_song_plan
from tests.test_review_tasks import _task


def test_review_judge_prompt_sanitizes_and_mock_provider_scores(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan, review={"rating": 4, "status": "needs_fix", "notes": r"judge api_key=sk-secret-value C:\Users\demo\song.wav", "markers": []})
    candidates = [
        store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
        for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, plan, strategies=["balanced", "bold"])
    ]
    ranked = store.rank_candidates(task)
    decision = build_review_decision_report(task=task, candidates=ranked, parent_plan=plan)
    template = PromptTemplateStore(tmp_path / "templates").get_template("provider-review-judge")

    payload = build_review_judge_prompt_payload(task=task, candidates=ranked, parent_plan=plan, decision_report=decision, note=r"focus C:\Users\demo")
    report, snapshot = run_provider_review_judge(project_id="project-001", task=task, candidates=ranked, parent_plan=plan, template=template, config=ProviderConfig(wire_api="mock", model="mock-review", api_key="sk-secret-value"), decision_report=decision)
    serialized = json.dumps({"payload": payload, "report": report, "snapshot": snapshot}, ensure_ascii=False)

    assert report["status"] == "completed"
    assert report["recommended_candidate_id"] in {candidate.candidate_id for candidate in candidates}
    assert len(report["candidate_scores"]) == len(candidates)
    assert judge_report_summary(report)["top_overall"] >= 0
    assert snapshot["operation"] == "provider_review_judge"
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_review_judge_rejects_invalid_candidate_id_and_score(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    stored = store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
    template = PromptTemplateStore(tmp_path / "templates").get_template("provider-review-judge")

    with pytest.raises(ValueError, match="ready candidate"):
        build_judge_report(
            project_id="project-001",
            task=task,
            candidates=[stored],
            parent_plan=plan,
            template=template,
            provider_output={"recommended_candidate_id": "revcand-999", "candidate_scores": [], "comparison_summary": {}, "manual_review_required": True},
            provider_snapshot={"wire_api": "mock", "model": "mock-review"},
        )

    with pytest.raises(ValueError, match="overall"):
        build_judge_report(
            project_id="project-001",
            task=task,
            candidates=[stored],
            parent_plan=plan,
            template=template,
            provider_output={
                "recommended_candidate_id": stored.candidate_id,
                "candidate_scores": [{"candidate_id": stored.candidate_id, "overall": 101, "review_fit": 80, "target_precision": 80, "musicality": 80, "novelty": 50, "risk": 10, "confidence": 0.7, "reason": "bad"}],
                "comparison_summary": {"best_candidate_id": stored.candidate_id},
                "manual_review_required": True,
            },
            provider_snapshot={"wire_api": "mock", "model": "mock-review"},
        )


def test_review_judge_stale_detection_and_provider_output_error(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    stored = store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
    template = PromptTemplateStore(tmp_path / "templates").get_template("provider-review-judge")
    report, _snapshot = run_provider_review_judge(project_id="project-001", task=task, candidates=[stored], parent_plan=plan, template=template, config=ProviderConfig(wire_api="mock", model="mock-review"))
    changed = store.update_candidate(type(stored).from_dict({**stored.to_dict(), "summary": "changed"}))

    assert judge_report_stale(report, task=task, candidates=[stored], parent_plan=plan, template=template) is False
    applied = type(stored).from_dict({**stored.to_dict(), "status": "applied"})
    assert judge_report_stale(report, task=task, candidates=[applied], parent_plan=plan, template=template) is False
    assert judge_report_stale(report, task=task, candidates=[changed], parent_plan=plan, template=template) is True
    with pytest.raises(ProviderOutputError):
        run_provider_review_judge(project_id="project-001", task=task, candidates=[stored], parent_plan=plan, template=template, config=ProviderConfig(wire_api="mock", model="mock-review"), client=__import__("song_agent.providers.mock", fromlist=["MockProviderClient"]).MockProviderClient(mode="invalid_schema"))
