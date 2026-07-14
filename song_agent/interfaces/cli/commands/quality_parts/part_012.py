from __future__ import annotations

from .dependencies import *

from .part_003 import build_verify_audio_campaign_archive_parser, build_verify_audio_campaign_parser, build_verify_audio_campaign_remediation_parser

from .part_004 import build_verify_release_audio_certification_parser, build_verify_release_audio_regression_parser, build_verify_release_audio_timeline_parser

from .part_005 import build_acceptance_check_parser, build_audio_health_parser, build_audio_profile_parser

from .part_009 import print_acceptance_check_report, run_acceptance_check

def _execute_verify_audio_campaign_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-package', *argv]
    pass
    parser = build_verify_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_package(
        args.zip_path,
        strict=args.strict,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_fix_sprints_closed=args.require_fix_sprints_closed,
        require_signed=args.require_signed,
        require_no_open_high=args.require_no_open_high,
        require_no_open_critical=args.require_no_open_critical,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_verification_exit_code(report))

def handle_verify_audio_campaign_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_package(argv)

def _execute_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-archive-package', *argv]
    pass




    parser = build_verify_audio_campaign_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_verification_passed=args.require_verification_passed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_archive_verification_exit_code(report))

def handle_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_archive_package(argv)

def _execute_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-remediation-package', *argv]
    pass




    parser = build_verify_audio_campaign_remediation_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_remediation_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_remediation_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Remediation verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_remediation_verification_exit_code(report))

def handle_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_remediation_package(argv)

def _execute_verify_release_audio_certification_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-certification-package', *argv]
    pass




    parser = build_verify_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_certification_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_remediation_when_needed=args.require_remediation_when_needed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_certification_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Certification verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_certification_verification_exit_code(report))

def handle_verify_release_audio_certification_package(argv: list[str]) -> None:
    _execute_verify_release_audio_certification_package(argv)

def _execute_verify_release_audio_timeline_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-timeline-package', *argv]
    pass




    parser = build_verify_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_timeline_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_current_certification=args.require_current_certification,
        release_audio_certification_path=args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_timeline_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Timeline verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_timeline_verification_exit_code(report))

def handle_verify_release_audio_timeline_package(argv: list[str]) -> None:
    _execute_verify_release_audio_timeline_package(argv)

def _execute_verify_release_audio_regression_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-package', *argv]
    pass




    parser = build_verify_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_baseline_current=args.require_baseline_current,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_regression_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_verification_exit_code(report))

def handle_verify_release_audio_regression_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_package(argv)

def _execute_acceptance_check(argv: list[str]) -> None:
    raw_args = ['acceptance-check', *argv]
    parser = build_acceptance_check_parser()
    args = parser.parse_args(raw_args[1:])
    report = run_acceptance_check(
        out_dir=args.out,
        profile_id=args.profile,
        cases=args.cases,
        render_audio_mode=args.render_audio,
        auto_review=args.auto_review,
        min_rating=args.min_rating,
        manual_required=args.manual_required,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_check_report(report)
    raise SystemExit(0 if report.get("status") in {"passed", "needs_review"} else 1)

def handle_acceptance_check(argv: list[str]) -> None:
    _execute_acceptance_check(argv)

def _execute_audio_health(argv: list[str]) -> None:
    raw_args = ['audio-health', *argv]
    pass
    parser = build_audio_health_parser()
    args = parser.parse_args(raw_args[1:])
    report = analyze_wav_health(
        args.wav_path,
        expected_sample_rate=args.expected_sample_rate,
        expected_channels=args.expected_channels,
        expected_bit_depth=args.expected_bit_depth,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge audio-health\nstatus: {report.get('status')}\nwav_sha256: {report.get('wav_sha256')}")
    raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)

def handle_audio_health(argv: list[str]) -> None:
    _execute_audio_health(argv)

def _execute_audio_profile(argv: list[str]) -> None:
    raw_args = ['audio-profile', *argv]
    pass
    parser = build_audio_profile_parser()
    args = parser.parse_args(raw_args[1:])
    store = AudioProfileStore()
    if args.action == "list":
        result = {"profiles": [profile.public_summary() for profile in store.list_profiles(include_hidden=args.include_hidden)]}
    elif args.action == "create":
        profile = store.upsert_profile(
            {
                "profile_id": args.profile_id,
                "name": args.name,
                "engine": args.engine,
                "engine_path": args.engine_path,
                "soundfont_path": args.soundfont,
                "sample_rate": args.sample_rate,
                "gain": args.gain,
                "is_default": args.default,
            }
        )
        result = {"profile": profile.public_summary()}
    elif args.action == "test":
        result = store.test_profile(args.profile_id)
    elif args.action == "set-default":
        result = {"profile": store.set_default(args.profile_id).public_summary()}
    else:
        result = {}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("status") != "failed" else 1)

def handle_audio_profile(argv: list[str]) -> None:
    _execute_audio_profile(argv)

__all__ = ('_execute_verify_audio_campaign_package', 'handle_verify_audio_campaign_package', '_execute_verify_audio_campaign_archive_package', 'handle_verify_audio_campaign_archive_package', '_execute_verify_audio_campaign_remediation_package', 'handle_verify_audio_campaign_remediation_package', '_execute_verify_release_audio_certification_package', 'handle_verify_release_audio_certification_package', '_execute_verify_release_audio_timeline_package', 'handle_verify_release_audio_timeline_package', '_execute_verify_release_audio_regression_package', 'handle_verify_release_audio_regression_package', '_execute_acceptance_check', 'handle_acceptance_check', '_execute_audio_health', 'handle_audio_health', '_execute_audio_profile', 'handle_audio_profile')
