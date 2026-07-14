from __future__ import annotations

from .dependencies import *

from .part_002 import build_audio_lab_parser

from .part_003 import build_audio_campaign_parser, build_audio_fix_sprint_parser, build_release_audio_certification_parser

from .part_004 import build_release_audio_baseline_parser, build_release_audio_quality_observatory_parser, build_release_audio_regression_parser, build_release_audio_regression_response_parser, build_release_audio_timeline_parser, build_verify_release_audio_baseline_registry_parser, build_verify_release_audio_regression_response_parser

from .part_005 import build_release_audio_command_center_parser, build_release_audio_quality_actions_parser

from .part_006 import _run_audio_lab_command

from .part_007 import _run_audio_campaign_command, _run_audio_fix_sprint_command, _run_release_audio_certification_command, _run_release_audio_timeline_command

from .part_008 import _run_release_audio_baseline_command, _run_release_audio_quality_actions_command, _run_release_audio_quality_observatory_command, _run_release_audio_regression_command, _run_release_audio_regression_response_command

from .part_009 import _print_audio_campaign_result, _print_audio_fix_sprint_result, _print_audio_lab_result, _print_release_audio_certification_result, _run_release_audio_command_center_command

def print_planning_ruleset_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    ruleset = result.get("ruleset") if isinstance(result.get("ruleset"), dict) else {}
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    print("MusicForge planning-ruleset")
    if validation:
        print(f"validation: {validation.get('status')}")
        print(f"ruleset: {validation.get('ruleset_id')}")
        return
    print(f"ruleset: {summary.get('ruleset_id') or ruleset.get('ruleset_id') or '-'}")
    print(f"status: {summary.get('status') or ruleset.get('status') or '-'}")
    print(f"template: {summary.get('template') or '-'}")
    if result.get("rulesets") is not None:
        print(f"rulesets: {len(result.get('rulesets') or [])}")

def print_planning_simulation_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    simulation = result.get("simulation") if isinstance(result.get("simulation"), dict) else {}
    print("MusicForge planning-simulation")
    print(f"simulation: {summary.get('simulation_id') or simulation.get('simulation_id') or '-'}")
    print(f"ruleset: {summary.get('ruleset_id') or simulation.get('ruleset_id') or '-'}")
    print(f"reviews: {summary.get('review_count', 0)}")
    print(f"items: {summary.get('item_count', 0)}")
    print(f"alignment: {summary.get('baseline_alignment_score')} -> {summary.get('simulated_alignment_score')} ({summary.get('alignment_delta')})")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("simulations") is not None:
        print(f"simulations: {len(result.get('simulations') or [])}")

def print_planning_rule_governance_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    promotion = result.get("promotion") if isinstance(result.get("promotion"), dict) else {}
    version = result.get("version") if isinstance(result.get("version"), dict) else {}
    print("MusicForge planning-rule-governance")
    print(f"status: {summary.get('status') or version.get('status') or promotion.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or version.get('version_id') or '-'}")
    if promotion:
        print(f"promotion: {promotion.get('promotion_id')}")
        print(f"recommendation: {(promotion.get('evidence') or {}).get('recommendation')}")
    if result.get("versions") is not None:
        print(f"versions: {len(result.get('versions') or [])}")
    if result.get("promotions") is not None:
        print(f"promotions: {len(result.get('promotions') or [])}")
    if result.get("events") is not None:
        print(f"events: {len(result.get('events') or [])}")

def print_planning_rule_impact_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    report = result.get("impact_report") if isinstance(result.get("impact_report"), dict) else {}
    print("MusicForge planning-rule-impact")
    print(f"report: {summary.get('report_id') or report.get('report_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or '-'}")
    print(f"plans: {summary.get('observed_plan_count', 0)}")
    print(f"reviews: {summary.get('observed_review_count', 0)}")
    print(f"manual_reviews: {summary.get('manual_review_count', 0)}")
    print(f"synthetic_reviews: {summary.get('synthetic_review_count', 0)}")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("reports") is not None:
        print(f"reports: {len(result.get('reports') or [])}")

def print_acceptance_kb_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    recommendation = result.get("recommendation") if isinstance(result.get("recommendation"), dict) else {}
    entry = result.get("entry") if isinstance(result.get("entry"), dict) else {}
    print("MusicForge acceptance-kb")
    if summary:
        print(f"status: {summary.get('status') or '-'}")
        print(f"entries: {summary.get('entry_count', 0)}")
        print(f"effective: {summary.get('effective_count', 0)}")
        print(f"average_score: {summary.get('average_effectiveness_score')}")
    if result.get("entries") is not None:
        print(f"listed_entries: {len(result.get('entries') or [])}")
    if recommendation:
        print(f"recommendation: {recommendation.get('status')}")
        print(f"matches: {recommendation.get('matching_entry_count', 0)}")
    if entry:
        print(f"entry: {entry.get('entry_id')}")

def _acceptance_analytics_fail_on(readiness: str, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"ready": 0, "watch": 1, "needs_work": 2, "blocked": 3, "empty": 0, "missing": 0}
    return order.get(readiness, 0) >= order.get(fail_on, 0)

def _execute_audio_lab(argv: list[str]) -> None:
    raw_args = ['audio-lab', *argv]
    parser = build_audio_lab_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_lab_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_lab_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked"}:
        raise SystemExit(1)
    return

def handle_audio_lab(argv: list[str]) -> None:
    _execute_audio_lab(argv)

def _execute_audio_fix_sprint(argv: list[str]) -> None:
    raw_args = ['audio-fix-sprint', *argv]
    parser = build_audio_fix_sprint_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_fix_sprint_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_fix_sprint_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_audio_fix_sprint(argv: list[str]) -> None:
    _execute_audio_fix_sprint(argv)

def _execute_audio_campaign(argv: list[str]) -> None:
    raw_args = ['audio-campaign', *argv]
    parser = build_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_campaign_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_campaign_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_audio_campaign(argv: list[str]) -> None:
    _execute_audio_campaign(argv)

def _execute_release_audio_certification(argv: list[str]) -> None:
    raw_args = ['release-audio-certification', *argv]
    parser = build_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_certification_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_certification(argv: list[str]) -> None:
    _execute_release_audio_certification(argv)

def _execute_release_audio_timeline(argv: list[str]) -> None:
    raw_args = ['release-audio-timeline', *argv]
    parser = build_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_timeline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_timeline(argv: list[str]) -> None:
    _execute_release_audio_timeline(argv)

def _execute_release_audio_regression(argv: list[str]) -> None:
    raw_args = ['release-audio-regression', *argv]
    parser = build_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_regression(argv: list[str]) -> None:
    _execute_release_audio_regression(argv)

def _execute_release_audio_baseline(argv: list[str]) -> None:
    raw_args = ['release-audio-baseline', *argv]
    parser = build_release_audio_baseline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_baseline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_baseline(argv: list[str]) -> None:
    _execute_release_audio_baseline(argv)

def _execute_release_audio_regression_response(argv: list[str]) -> None:
    raw_args = ['release-audio-regression-response', *argv]
    parser = build_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_response_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_regression_response(argv: list[str]) -> None:
    _execute_release_audio_regression_response(argv)

def _execute_release_audio_quality_observatory(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-observatory', *argv]
    parser = build_release_audio_quality_observatory_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_observatory_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_quality_observatory(argv: list[str]) -> None:
    _execute_release_audio_quality_observatory(argv)

def _execute_release_audio_quality_actions(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-actions', *argv]
    parser = build_release_audio_quality_actions_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_actions_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_quality_actions(argv: list[str]) -> None:
    _execute_release_audio_quality_actions(argv)

def _execute_release_audio_command_center(argv: list[str]) -> None:
    raw_args = ['release-audio-command-center', *argv]
    parser = build_release_audio_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_command_center(argv: list[str]) -> None:
    _execute_release_audio_command_center(argv)

def _execute_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-baseline-registry-package', *argv]
    pass




    parser = build_verify_release_audio_baseline_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_baseline_registry_package(args.zip_path, strict=args.strict, require_active=args.require_active)
    if args.report_out is not None:
        write_release_audio_baseline_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Baseline Registry verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_baseline_registry_verification_exit_code(report))

def handle_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    _execute_verify_release_audio_baseline_registry_package(argv)

def _execute_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-response-package', *argv]
    pass




    parser = build_verify_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_response_package(
        args.zip_path,
        strict=args.strict,
        require_closed=args.require_closed,
        require_signed=args.require_signed,
        require_regression_current=args.require_regression_current,
        release_audio_regression_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
    )
    if args.report_out is not None:
        write_release_audio_regression_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression Response verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_response_verification_exit_code(report))

def handle_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_response_package(argv)

__all__ = ('print_planning_ruleset_result', 'print_planning_simulation_result', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_acceptance_kb_result', '_acceptance_analytics_fail_on', '_execute_audio_lab', 'handle_audio_lab', '_execute_audio_fix_sprint', 'handle_audio_fix_sprint', '_execute_audio_campaign', 'handle_audio_campaign', '_execute_release_audio_certification', 'handle_release_audio_certification', '_execute_release_audio_timeline', 'handle_release_audio_timeline', '_execute_release_audio_regression', 'handle_release_audio_regression', '_execute_release_audio_baseline', 'handle_release_audio_baseline', '_execute_release_audio_regression_response', 'handle_release_audio_regression_response', '_execute_release_audio_quality_observatory', 'handle_release_audio_quality_observatory', '_execute_release_audio_quality_actions', 'handle_release_audio_quality_actions', '_execute_release_audio_command_center', 'handle_release_audio_command_center', '_execute_verify_release_audio_baseline_registry_package', 'handle_verify_release_audio_baseline_registry_package', '_execute_verify_release_audio_regression_response_package', 'handle_verify_release_audio_regression_response_package')
