from __future__ import annotations

from .dependencies import *

def build_release_audio_quality_actions_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Quality Action Queue evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create an action queue from a quality observatory.")
    create.add_argument("observatory_id")
    create.add_argument("--name", default=None)
    create.add_argument("--severity-floor", default="warning")
    create.add_argument("--risks-only", action="store_true", help="Only generate actions from risk register rows.")
    create.add_argument("--recommendations-only", action="store_true", help="Only generate actions from recommendations.")
    list_cmd = subparsers.add_parser("list", help="List action queues.")
    del list_cmd
    status = subparsers.add_parser("status", help="Show queue status.")
    status.add_argument("queue_id")
    refresh = subparsers.add_parser("refresh", help="Refresh queue stale status.")
    refresh.add_argument("queue_id")
    run_safe = subparsers.add_parser("run-safe", help="Run only safe queue actions.")
    run_safe.add_argument("queue_id")
    export = subparsers.add_parser("export", help="Export action queue package files.")
    export.add_argument("queue_id")
    zip_cmd = subparsers.add_parser("zip", help="Build action queue ZIP.")
    zip_cmd.add_argument("queue_id")
    verify = subparsers.add_parser("verify", help="Verify action queue ZIP.")
    verify.add_argument("queue_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-current-observatory", action="store_true")
    verify.add_argument("--observatory-zip", type=Path, default=None)
    verify.add_argument("--observatory-verification-report", type=Path, default=None)
    verify.add_argument("--evidence-root", type=Path, default=None)
    verify.add_argument("--allow-blocking", action="store_true", help="Do not fail verification on blocked queue actions.")
    verify.add_argument("--report-out", type=Path, default=None)
    manual = subparsers.add_parser("manual-items", help="List manual action items and resolutions.")
    manual.add_argument("queue_id")
    resolve = subparsers.add_parser("resolve-manual", help="Resolve a manual action item.")
    resolve.add_argument("queue_id")
    resolve.add_argument("item_id")
    resolve.add_argument("--status", default="completed", choices=["completed", "waived", "rejected", "deferred"])
    resolve.add_argument("--resolved-by", default="local-reviewer")
    resolve.add_argument("--role", default="audio_quality_reviewer")
    resolve.add_argument("--reason", default="Manual action completed.")
    closeout = subparsers.add_parser("closeout", help="Refresh closeout report.")
    closeout.add_argument("queue_id")
    signoff = subparsers.add_parser("signoff", help="Sign a passed closeout.")
    signoff.add_argument("queue_id")
    signoff.add_argument("--signed-by", default="audio-quality-lead")
    signoff.add_argument("--role", default="audio_quality_lead")
    signoff.add_argument("--reason", default="Audio Quality Action Queue closeout accepted.")
    archive = subparsers.add_parser("archive", help="Export signoff archive files.")
    archive.add_argument("queue_id")
    archive_zip = subparsers.add_parser("archive-zip", help="Build signoff archive ZIP.")
    archive_zip.add_argument("queue_id")
    verify_archive = subparsers.add_parser("verify-archive", help="Verify signoff archive ZIP.")
    verify_archive.add_argument("queue_id")
    verify_archive.add_argument("--strict", action="store_true")
    verify_archive.add_argument("--no-require-current-queue", dest="require_current_queue", action="store_false", default=True)
    verify_archive.add_argument("--no-require-signed", dest="require_signed", action="store_false", default=True)
    verify_archive.add_argument("--queue-zip", type=Path, default=None)
    verify_archive.add_argument("--queue-verification-report", type=Path, default=None)
    verify_archive.add_argument("--observatory-zip", type=Path, default=None)
    verify_archive.add_argument("--observatory-verification-report", type=Path, default=None)
    verify_archive.add_argument("--evidence-root", type=Path, default=None)
    verify_archive.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_quality_action_queue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Quality Action Queue ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-observatory", action="store_true")
    parser.add_argument("--observatory-zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", type=Path, default=None)
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--allow-blocking", action="store_true", help="Do not fail verification on blocked queue actions.")
    parser.add_argument("--max-zip-size-mb", type=int, default=64)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=128)
    parser.add_argument("--max-entry-count", type=int, default=100)
    return parser

def build_verify_release_audio_quality_action_queue_signoff_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Quality Action Queue Signoff Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-queue", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--queue-zip", type=Path, default=None)
    parser.add_argument("--queue-verification-report", type=Path, default=None)
    parser.add_argument("--observatory-zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", type=Path, default=None)
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--allow-unresolved-manual", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=64)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=128)
    parser.add_argument("--max-entry-count", type=int, default=100)
    return parser

def _add_release_audio_command_center_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--certification-zip", dest="certification_zip", type=Path, default=None)
    parser.add_argument("--certification-verification-report", dest="certification_verification_report", type=Path, default=None)
    parser.add_argument("--timeline-zip", dest="timeline_zip", type=Path, default=None)
    parser.add_argument("--timeline-verification-report", dest="timeline_verification_report", type=Path, default=None)
    parser.add_argument("--regression-zip", dest="regression_zip", type=Path, default=None)
    parser.add_argument("--regression-verification-report", dest="regression_verification_report", type=Path, default=None)
    parser.add_argument("--baseline-registry-zip", dest="baseline_registry_zip", type=Path, default=None)
    parser.add_argument("--baseline-registry-verification-report", dest="baseline_registry_verification_report", type=Path, default=None)
    parser.add_argument("--regression-response-zip", dest="regression_response_zip", type=Path, default=None)
    parser.add_argument("--regression-response-verification-report", dest="regression_response_verification_report", type=Path, default=None)
    parser.add_argument("--observatory-zip", dest="observatory_zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", dest="observatory_verification_report", type=Path, default=None)
    parser.add_argument("--action-queue-zip", dest="action_queue_zip", type=Path, default=None)
    parser.add_argument("--action-queue-verification-report", dest="action_queue_verification_report", type=Path, default=None)
    parser.add_argument("--action-queue-signoff-archive", dest="action_queue_signoff_archive", type=Path, default=None)
    parser.add_argument("--action-queue-signoff-verification-report", dest="action_queue_signoff_verification_report", type=Path, default=None)
    parser.add_argument("--evidence-root", dest="evidence_root", type=Path, default=None)

def build_release_audio_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Command Center evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action, help_text in (
        ("refresh", "Refresh the Command Center report."),
        ("report", "Show the current Command Center report."),
        ("inventory", "Show the evidence inventory."),
        ("readiness", "Show the readiness matrix."),
        ("gap-plan", "Show the gap plan."),
        ("runbook", "Create or show the safe runbook."),
        ("run-safe", "Run only safe Command Center actions."),
        ("export", "Export Command Center package files."),
        ("zip", "Build Command Center ZIP."),
        ("verify", "Verify Command Center ZIP."),
    ):
        cmd = subparsers.add_parser(action, help=help_text)
        cmd.add_argument("release_id")
        if action in {"refresh", "runbook", "run-safe", "export", "zip", "verify"}:
            _add_release_audio_command_center_evidence_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-ready", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Command Center ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    _add_release_audio_command_center_evidence_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_command_center_acceptance_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--review-pack", type=Path, default=None)
    parser.add_argument("--review-pack-verification-report", type=Path, default=None)
    parser.add_argument("--accepted-evidence-dir", type=Path, default=None)
    parser.add_argument("--response-proof-dir", type=Path, default=None)
    parser.add_argument("--command-center-signoff-archive", type=Path, default=None)
    parser.add_argument("--command-center-signoff-archive-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-final-handoff", type=Path, default=None)
    parser.add_argument("--command-center-final-handoff-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-signoff-binding", type=Path, default=None)
    parser.add_argument("--command-center", type=Path, default=None)
    parser.add_argument("--command-center-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-evidence-manifest", type=Path, default=None)

def build_acceptance_check_parser() -> argparse.ArgumentParser:
    acceptance_parser = argparse.ArgumentParser(description="Run a local Music Acceptance Lab suite.")
    acceptance_parser.add_argument("--out", type=Path, default=Path(".musicforge") / "acceptance", help="Acceptance workspace directory.")
    acceptance_parser.add_argument("--profile", default="developer_manual", help="Acceptance profile: midi_smoke, developer_manual, release_candidate, or audio_required.")
    acceptance_parser.add_argument("--cases", type=int, default=6, help="Number of representative generated songs.")
    acceptance_parser.add_argument("--render-audio", choices=["auto", "always", "never", "require"], default="auto", help="Whether to render WAV audio.")
    acceptance_parser.add_argument("--manual-required", action="store_true", help="Require manual reviews; auto-review will not be treated as release evidence.")
    acceptance_parser.add_argument("--auto-review", action="store_true", help="Write synthetic reviews for CI/smoke use.")
    acceptance_parser.add_argument("--min-rating", type=int, default=3, help="Minimum accepted review rating.")
    acceptance_parser.add_argument("--json", action="store_true", help="Print the full acceptance report as JSON.")
    acceptance_parser.add_argument("--report-out", type=Path, default=None, help="Write the acceptance report to this JSON file.")
    return acceptance_parser

def build_audio_health_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic WAV audio health checks.")
    parser.add_argument("wav_path", type=Path, help="Path to a WAV file.")
    parser.add_argument("--json", action="store_true", help="Print the full audio health report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the audio health report to this JSON file.")
    parser.add_argument("--expected-sample-rate", type=int, default=None, help="Expected WAV sample rate.")
    parser.add_argument("--expected-channels", type=int, default=None, help="Expected channel count.")
    parser.add_argument("--expected-bit-depth", type=int, default=None, help="Expected PCM bit depth.")
    return parser

def build_audio_profile_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local renderer profiles.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="List audio profiles.").add_argument("--include-hidden", action="store_true")
    create = subparsers.add_parser("create", help="Create or update an audio profile.")
    create.add_argument("--profile-id", default=None)
    create.add_argument("--name", required=True)
    create.add_argument("--engine", default="fluidsynth")
    create.add_argument("--engine-path", default="fluidsynth")
    create.add_argument("--soundfont", default="")
    create.add_argument("--sample-rate", type=int, default=44100)
    create.add_argument("--gain", type=float, default=0.6)
    create.add_argument("--default", action="store_true")
    test = subparsers.add_parser("test", help="Test an audio profile.")
    test.add_argument("profile_id")
    default = subparsers.add_parser("set-default", help="Set the default audio profile.")
    default.add_argument("profile_id")
    return parser

def build_release_audio_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage per-track Release audio review evidence.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    listing = subparsers.add_parser("list", help="List audio reviews for a Release.")
    listing.add_argument("release_id")
    summary = subparsers.add_parser("summary", help="Build the current per-track audio review summary.")
    summary.add_argument("release_id")
    summary.add_argument("--write", action="store_true", help="Persist release-audio-review-summary.json.")
    add = subparsers.add_parser("add", help="Create a per-track audio review.")
    add.add_argument("release_id")
    add.add_argument("--track-id", required=True)
    add.add_argument("--status", choices=["accepted", "needs_fix", "rejected", "waived"], default="accepted")
    add.add_argument("--review-mode", choices=["manual", "synthetic"], default="manual")
    add.add_argument("--rating", type=int, default=4)
    add.add_argument("--reviewer", default="local-user")
    add.add_argument("--notes", default="")
    add.add_argument("--playback-confirmed", action="store_true", default=False)
    task = subparsers.add_parser("create-task", help="Create a ReviewTask from an audio review marker.")
    task.add_argument("release_id")
    task.add_argument("review_id")
    task.add_argument("marker_id")
    task.add_argument("--title", default="")
    task.add_argument("--instruction", default="")
    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON output.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_encoded_audio_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build encoded audio health and review acceptance evidence for a Release.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="", help="Comma-separated encoded audio profile ids.")
    parser.add_argument("--refresh-health", action="store_true", help="Refresh encoded audio health before building the summary.")
    parser.add_argument("--write", action="store_true", help="Persist encoded audio acceptance summary.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
    return parser

def build_format_decision_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Release Format Decision session and report.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="", help="Comma-separated candidate encoded audio profile ids.")
    parser.add_argument("--select", default="", help="Comma-separated selected delivery profile ids.")
    parser.add_argument("--archive", default="", help="Comma-separated archive profile ids.")
    parser.add_argument("--fallback", default="", help="Comma-separated fallback profile ids.")
    parser.add_argument("--reject", default="", help="Comma-separated rejected profile ids.")
    parser.add_argument("--decided-by", default="local-user", help="Human decision owner.")
    parser.add_argument("--reason", default="", help="Decision rationale.")
    parser.add_argument("--activate", action="store_true", help="Set the generated session as active.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
    return parser

def build_acceptance_diff_parser() -> argparse.ArgumentParser:
    diff_parser = argparse.ArgumentParser(description="Compare two Music Acceptance reports by regression song id.")
    diff_parser.add_argument("left_report", type=Path, help="Baseline music-acceptance-report.json.")
    diff_parser.add_argument("right_report", type=Path, help="Current music-acceptance-report.json.")
    diff_parser.add_argument("--json", action="store_true", help="Print the full diff report as JSON.")
    diff_parser.add_argument("--report-out", type=Path, default=None, help="Write the diff report to this JSON file.")
    return diff_parser

def build_acceptance_analytics_parser() -> argparse.ArgumentParser:
    analytics_parser = argparse.ArgumentParser(description="Build or read local MusicForge Acceptance Analytics.")
    analytics_parser.add_argument("--scope", choices=["global", "suite", "release", "project"], default="global", help="Analytics scope.")
    analytics_parser.add_argument("--suite-id", default=None, help="Suite id for suite scope.")
    analytics_parser.add_argument("--release-id", default=None, help="Release id for release scope.")
    analytics_parser.add_argument("--project-id", default=None, help="Project id for project scope.")
    analytics_parser.add_argument("--refresh", action="store_true", help="Recalculate and persist a fresh analytics report.")
    analytics_parser.add_argument("--json", action="store_true", help="Print the full analytics report as JSON.")
    analytics_parser.add_argument("--report-out", type=Path, default=None, help="Write the analytics report to this JSON file.")
    analytics_parser.add_argument("--fail-on", choices=["blocked", "needs_work", "watch"], default=None, help="Exit 1 when readiness is at or above this severity.")
    return analytics_parser

def build_acceptance_fix_sprint_parser() -> argparse.ArgumentParser:
    fix_parser = argparse.ArgumentParser(description="Manage local MusicForge Acceptance Fix Sprints.")
    subparsers = fix_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Fix Sprint from an Acceptance Analytics report.")
    create.add_argument("--analytics-report-id", required=True, help="Source Acceptance Analytics report id.")
    create.add_argument("--name", default=None, help="Fix Sprint name.")
    create.add_argument("--max-items", type=int, default=20, help="Maximum recommendations to import.")
    create.add_argument("--recommendation-id", action="append", dest="recommendation_ids", default=[], help="Recommendation id to include. Can be repeated.")

    show = subparsers.add_parser("show", help="Show a Fix Sprint.")
    show.add_argument("fix_sprint_id")

    listing = subparsers.add_parser("list", help="List Fix Sprints.")
    listing.add_argument("--include-archived", action="store_true")

    tasks = subparsers.add_parser("create-review-tasks", help="Create or bind ReviewTasks for Fix Sprint items.")
    tasks.add_argument("fix_sprint_id")
    tasks.add_argument("--item-id", default=None)

    recheck = subparsers.add_parser("create-recheck-suite", help="Create a recheck Acceptance Suite.")
    recheck.add_argument("fix_sprint_id")
    recheck.add_argument("--profile", default=None)

    delta = subparsers.add_parser("delta", help="Read or refresh a Fix Sprint delta report.")
    delta.add_argument("fix_sprint_id")
    delta.add_argument("--refresh", action="store_true")

    close = subparsers.add_parser("close", help="Close a Fix Sprint after recheck and delta.")
    close.add_argument("fix_sprint_id")
    close.add_argument("--force", action="store_true")
    close.add_argument("--override-reason", default="")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return fix_parser

__all__ = ('build_release_audio_quality_actions_parser', 'build_verify_release_audio_quality_action_queue_parser', 'build_verify_release_audio_quality_action_queue_signoff_archive_parser', '_add_release_audio_command_center_evidence_args', 'build_release_audio_command_center_parser', 'build_verify_release_audio_command_center_parser', '_add_command_center_acceptance_source_args', 'build_acceptance_check_parser', 'build_audio_health_parser', 'build_audio_profile_parser', 'build_release_audio_review_parser', 'build_encoded_audio_acceptance_parser', 'build_format_decision_parser', 'build_acceptance_diff_parser', 'build_acceptance_analytics_parser', 'build_acceptance_fix_sprint_parser')
