from __future__ import annotations

from song_agent.platform.contracts import JsonDocument, as_document as _as_document

from song_agent.interfaces.bootstrap.api.core import CandidateGroup, Path, json, unquote

from song_agent.interfaces.bootstrap.api.creation_quality import read_json

def _job_artifacts(
    run_dir: Path,
    plan_path: Path,
    midi_path: Path,
    validator_report_path: Path,
) -> dict[str, str]:
    artifacts = {
        "request": str(run_dir / "data" / "request.json"),
        "song_plan": str(plan_path),
        "run_summary": str(run_dir / "data" / "run-summary.json"),
        "validator_report": str(validator_report_path),
        "job_state": str(run_dir / "data" / "job-state.json"),
        "events": str(run_dir / "logs" / "events.jsonl"),
        "midi": str(midi_path),
    }
    provider_snapshot_path = run_dir / "data" / "provider-snapshot.json"
    if provider_snapshot_path.exists():
        artifacts["provider_snapshot"] = str(provider_snapshot_path)
    edit_metadata_path = run_dir / "data" / "edit-metadata.json"
    if edit_metadata_path.exists():
        artifacts["edit_metadata"] = str(edit_metadata_path)
    nodes_dir = run_dir / "data" / "nodes"
    if nodes_dir.exists():
        artifacts["nodes"] = str(nodes_dir)
    return artifacts

def _read_events(path: Path) -> list[JsonDocument]:
    if not path.exists():
        return []
    events: list[JsonDocument] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

def _read_critic_report(run_dir: Path) -> JsonDocument | None:
    path = run_dir / "data" / "nodes" / "critic.json"
    if not path.exists():
        return None
    try:
        record = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    output = record.get("output")
    return output if isinstance(output, dict) else None

def _read_edit_metadata_for_run(run_dir: Path) -> JsonDocument | None:
    path = run_dir / "data" / "edit-metadata.json"
    if not path.exists():
        return None
    try:
        metadata = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return metadata

def _top_ranked_candidate_id(group: CandidateGroup) -> str | None:
    if group.ranking:
        return str(group.ranking[0].get("candidate_id") or "") or None
    ready = [candidate for candidate in group.candidates if candidate.status == "ready"]
    if not ready:
        return None
    return max(ready, key=lambda candidate: int(candidate.scores.get("combined") or 0)).candidate_id

def _optional_positive_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None

def _candidate_source_summary(value: object) -> JsonDocument:
    data = _as_document(value)
    return {
        "candidate_group_id": str(data.get("candidate_group_id") or ""),
        "candidate_id": str(data.get("candidate_id") or ""),
        "rank": _optional_positive_int(data.get("rank")),
        "score": _optional_positive_int(data.get("score")),
        "quality_overall": _optional_positive_int(data.get("quality_overall")),
        "summary": str(data.get("summary") or "")[:240],
        "status": str(data.get("status") or ""),
        "created_at": str(data.get("created_at") or ""),
    }

def _prompt_ab_template_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("template_ids must be a list.")
    template_ids = [str(item).strip() for item in value if str(item).strip()]
    if len(template_ids) < 2:
        raise ValueError("Prompt A/B requires at least two template ids.")
    if len(template_ids) > 4:
        raise ValueError("Prompt A/B supports at most four template ids.")
    return template_ids

def _match_job_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if "/" in rest:
        job_id, tail = rest.split("/", 1)
        return unquote(job_id), "/" + tail
    return unquote(rest), ""

def _match_batch_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/batches/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import-csv":
        return None
    if "/" in rest:
        batch_id, tail = rest.split("/", 1)
        return unquote(batch_id), "/" + tail
    return unquote(rest), ""

def _match_project_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        project_id, tail = rest.split("/", 1)
        return unquote(project_id), "/" + tail
    return unquote(rest), ""

def _match_release_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/releases/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        release_id, tail = rest.split("/", 1)
        return unquote(release_id), "/" + tail
    return unquote(rest), ""

def _match_acceptance_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/suites/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        suite_id, tail = rest.split("/", 1)
        return unquote(suite_id), "/" + tail
    return unquote(rest), ""

def _match_acceptance_analytics_report_route(path: str) -> str | None:
    prefix = "/api/acceptance/analytics/reports/"
    if not path.startswith(prefix):
        return None
    report_id = unquote(path[len(prefix) :].strip("/"))
    return report_id or None

def _match_acceptance_analytics_recommendation_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/analytics/reports/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 4 and parts[1] == "recommendations" and parts[3] == "create-review-task":
        return parts[0], parts[2]
    return None

def _match_acceptance_kb_report_route(path: str) -> str | None:
    prefix = "/api/acceptance/kb/reports/"
    if not path.startswith(prefix):
        return None
    report_id = unquote(path[len(prefix) :].strip("/"))
    return report_id or None

def _match_acceptance_kb_entry_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/kb/entries/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"hide", "unhide"}:
        return parts[0], parts[1]
    return None

def _match_acceptance_fix_plan_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/fix-plans/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive", "create-fix-sprint", "outcome-review"}:
        return parts[0], parts[1]
    if len(parts) == 3 and parts[1] == "outcome-review" and parts[2] == "refresh":
        return parts[0], "outcome-review/refresh"
    return None

def _match_acceptance_fix_plan_review_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/fix-plan-reviews/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

def _match_planning_ruleset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rulesets/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"clone", "archive", "validate"}:
        return parts[0], parts[1]
    return None

def _match_planning_simulation_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-simulations/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

def _match_planning_rule_governance_version_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-governance/versions/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    return None

def _match_planning_rule_governance_promotion_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-governance/promotions/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"approve", "reject", "promote"}:
        return parts[0], parts[1]
    return None

def _match_planning_rule_impact_report_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-impact/reports/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

__all__ = ['_candidate_source_summary', '_job_artifacts', '_match_acceptance_analytics_recommendation_route', '_match_acceptance_analytics_report_route', '_match_acceptance_fix_plan_review_route', '_match_acceptance_fix_plan_route', '_match_acceptance_kb_entry_route', '_match_acceptance_kb_report_route', '_match_acceptance_route', '_match_batch_route', '_match_job_route', '_match_planning_rule_governance_promotion_route', '_match_planning_rule_governance_version_route', '_match_planning_rule_impact_report_route', '_match_planning_ruleset_route', '_match_planning_simulation_route', '_match_project_route', '_match_release_route', '_optional_positive_int', '_prompt_ab_template_ids', '_read_critic_report', '_read_edit_metadata_for_run', '_read_events', '_top_ranked_candidate_id']
